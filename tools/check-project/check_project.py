#!/usr/bin/env python3
"""Check maintained source without importing the app or changing host services.

Requires Python 3.9+, Git, Bash and Node.js. Third-party source is verified by
its lock file, never reformatted. This is a static check, not runtime acceptance.
"""

import argparse
import ast
import json
import os
from pathlib import Path
import re
import shutil
import string
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
VENDORED = ("third_party/", "src/web/static/third_party/",
            "src/web/static/licenses/", "src/web/static/icons/lucide/")


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def fields(value):
    return sorted(field for _, field, _, _ in string.Formatter().parse(value)
                  if field is not None)


def anchors(text):
    found = set()
    counts = {}
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        if fenced:
            continue
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match:
            title = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", match[1])
            title = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
            count = counts.get(title, 0)
            counts[title] = count + 1
            found.add(title if not count else f"{title}-{count}")
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", default=os.environ.get("NODE", "node"),
                        help="Node.js executable (or NODE environment variable)")
    args = parser.parse_args()
    errors = []
    node = shutil.which(args.node)
    if not node:
        errors.append("Node.js is required; use --node /absolute/path/to/node")
    raw = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT)
    files = sorted({os.fsdecode(name) for name in raw.split(b"\0") if name})
    document_names = set()
    counts = {"python": 0, "shell": 0, "javascript": 0, "json": 0, "documents": 0}

    def run(command):
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        if result.returncode:
            errors.append(result.stderr.strip() or result.stdout.strip() or str(command))

    for name in files:
        path = ROOT / name
        if not path.is_file() or name.startswith(VENDORED):
            continue
        try:
            if path.suffix == ".py":
                ast.parse(path.read_text(encoding="utf-8"), filename=name, feature_version=(3, 9))
                counts["python"] += 1
            elif path.suffix == ".sh":
                run(["bash", "-n", str(path)])
                counts["shell"] += 1
                for snippet in re.findall(r"<<'PY'[^\n]*\n(.*?)^PY$", path.read_text(encoding="utf-8"), re.M | re.S):
                    ast.parse(snippet, filename=name + ":heredoc", feature_version=(3, 9))
            elif path.suffix == ".js" and node:
                run([node, "--check", str(path)])
                counts["javascript"] += 1
            elif path.suffix == ".json":
                load_json(path)
                counts["json"] += 1
            elif path.suffix == ".md":
                text = path.read_text(encoding="utf-8")
                counts["documents"] += 1
                if len(re.findall(r"^# [^\n]+", text, re.M)) != 1:
                    errors.append(f"{name}: expected one document title")
                if path.name == "README.md":
                    if text.startswith("---\n"):
                        errors.append(f"{name}: README must not have frontmatter")
                else:
                    header = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
                    if not header:
                        errors.append(f"{name}: missing document frontmatter")
                    else:
                        frontmatter = header[1]
                        keys = re.findall(r"^([a-z_]+):", frontmatter, re.M)
                        if set(keys) != {"name", "description", "metadata"}:
                            errors.append(f"{name}: invalid frontmatter fields")
                        identity = re.search(r"^name: ([a-z0-9-]{1,64})$", frontmatter, re.M)
                        if not identity or identity[1] in document_names:
                            errors.append(f"{name}: invalid or duplicate document name")
                        else:
                            document_names.add(identity[1])
                        if not re.search(r'^  version: "[0-9]+\.[0-9]+\.[0-9]+"$', frontmatter, re.M):
                            errors.append(f"{name}: missing quoted document version")
                # Inline links used by project documents, including image links.
                for target in re.findall(r"\]\(([^\s)]+)(?:\s+[^)]*)?\)", text):
                    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("//"):
                        continue
                    location, _, fragment = unquote(target.strip("<>")).partition("#")
                    linked = (path.parent / location).resolve() if location else path
                    if not linked.is_relative_to(ROOT) or not linked.exists():
                        errors.append(f"{name}: missing local link {target}")
                    elif fragment and linked.suffix == ".md" and fragment not in anchors(linked.read_text(encoding="utf-8")):
                        errors.append(f"{name}: missing anchor {target}")
        except (OSError, ValueError, SyntaxError) as exc:
            errors.append(f"{name}: {exc}")

    for directory in sorted((ROOT / "lang").iterdir()):
        if not directory.is_dir() or not list(directory.glob("*.json")):
            continue
        try:
            source = load_json(directory / "zh-CN.json")
            for language in ("en", "es"):
                translation = load_json(directory / f"{language}.json")
                if source.keys() != translation.keys():
                    errors.append(f"{directory.name}/{language}: translation keys differ")
                for key in source.keys() & translation.keys():
                    if not isinstance(source[key], str) or not isinstance(translation[key], str):
                        errors.append(f"{directory.name}/{language}/{key}: expected string")
                    elif fields(source[key]) != fields(translation[key]):
                        errors.append(f"{directory.name}/{language}/{key}: format fields differ")
        except (OSError, ValueError) as exc:
            errors.append(f"{directory.name}: {exc}")

    for directory in sorted((ROOT / "lang").iterdir()):
        if not directory.is_dir() or not list(directory.glob("*.sh")):
            continue
        catalogs = {}
        for language in ("zh-CN", "en", "es"):
            path = directory / f"{language}.sh"
            if not path.is_file():
                errors.append(f"{directory.name}: missing {language} shell catalog")
                continue
            catalogs[language] = dict(re.findall(
                r"^\s*([a-zA-Z0-9_]+)\) fmt='(.*)' ;;$",
                path.read_text(encoding="utf-8"), re.M))
        if "zh-CN" not in catalogs:
            continue
        source = catalogs["zh-CN"]
        for language, translation in catalogs.items():
            if source.keys() != translation.keys():
                errors.append(f"{directory.name}/{language}: shell catalog keys differ")
            for key in source.keys() & translation.keys():
                pattern = r"%(?:[0-9]+\$)?[-+ #0]*[0-9]*(?:\.[0-9]+)?[sdiufgboxXc]"
                if re.findall(pattern, source[key]) != re.findall(pattern, translation[key]):
                    errors.append(f"{directory.name}/{language}/{key}: printf fields differ")

    installer = (ROOT / "deploy/install.sh").read_text(encoding="utf-8")
    documented = set(re.findall(r"^([A-Z][A-Z0-9_]*)=", (ROOT / ".env.example").read_text(encoding="utf-8"), re.M))
    for group in ("KNOWN_VARS", "SCRIPT_VARS"):
        match = re.search(rf'{group}="([^"]+)"', installer)
        if not match:
            errors.append(f"installer: missing {group}")
        else:
            for variable in sorted(set(match[1].split()) - documented):
                errors.append(f".env.example: missing {variable}")

    run([sys.executable, "tools/build-styles/build_styles.py", "--check"])
    run([sys.executable, "tools/verify-dependencies/verify_dependencies.py"])
    run(["git", "diff", "--check"])
    print("Checked " + ", ".join(f"{count} {kind}" for kind, count in counts.items()))
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        print(f"FAIL: {len(errors)} issue(s)", file=sys.stderr)
        return 1
    print("PASS: static checks, translations, local links, configuration and artifact hashes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
