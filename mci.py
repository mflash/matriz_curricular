#!/usr/bin/env python3
"""Thin entry point — delegates to the mci package.

Usage:
  python mci.py <input.json> [--links arrows|paths]
  python -m mci  <input.json> [--links arrows|paths]
"""
import sys
from mci.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
