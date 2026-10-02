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
    return "".join((ROOT / "static/styles" / f"{name}.css").read_text()
                   for name in PARTS)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = ROOT / "static/style.css"
    content = build()
    if args.check:
        if target.read_text() != content:
            parser.exit(1, "static/style.css is out of date; run tools/build_styles.py\n")
    else:
        target.write_text(content)


if __name__ == "__main__":
    main()
