#!/usr/bin/env python3
"""Build or check the token-based frontend using the locked npm dependencies."""
import argparse
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    subprocess.run(["npm", "run", "check" if args.check else "build"], cwd=ROOT / "web", check=True)
if __name__ == "__main__":
    main()
