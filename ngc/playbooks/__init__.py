"""Playbooks -- game-specific patching scripts."""

from pathlib import Path

# Project root = parent of ngc/ package
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WORK_DIR = PROJECT_ROOT / "unpacked"
OUT_DIR = PROJECT_ROOT / "out"
