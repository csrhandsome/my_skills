#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compatibility wrapper for the shared note-index scanner.
"""

from pathlib import Path
import runpy
import sys


TARGET = Path(__file__).resolve().parents[2] / "start-my-day" / "scripts" / "scan_existing_notes.py"

if not TARGET.exists():
    raise SystemExit(f"Missing shared script: {TARGET}")

sys.path.insert(0, str(TARGET.parent))
runpy.run_path(str(TARGET), run_name="__main__")
