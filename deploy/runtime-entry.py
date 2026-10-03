#!/usr/bin/env python3
"""Compatibility entry for installations that start $PREFIX/app.py."""

from src.web.app import main


if __name__ == "__main__":
    main()
