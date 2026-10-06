#!/usr/bin/env python3
"""Build the served CSS from ordered feature sources without changing rule order."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARTS = (
    "foundation", "modules", "select", "shell", "frp", "components",
    "login", "settings", "forms", "feedback", "dashboard", "speedtest",
    "visitors", "changelog", "iperf", "data-layout", "proxy",
    "responsive", "nodes",
)


def build():
    return "".join((ROOT / "src/web/static/styles" / f"{name}.css").read_text(encoding="utf-8")
                   for name in PARTS)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = ROOT / "src/web/static/style.css"
    content = build()
    if args.check:
        if target.read_text(encoding="utf-8") != content:
            parser.exit(1, "src/web/static/style.css is out of date; run python3 tools/build-styles/build_styles.py\n")
    else:
        target.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
