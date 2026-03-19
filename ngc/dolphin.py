"""DolphinTool helpers -- locate, extract, and convert disc images."""

import os
import shutil
import subprocess
from pathlib import Path

def find_dolphin() -> str | None:
    """Return DolphinTool if found on PATH, or *None*."""
    return shutil.which("DolphinTool") or shutil.which("DolphinTool.exe")


def dolphin_extract(dolphin: str, src: str, out_dir: str,
                    work_dir: str | None = None, quiet: bool = True):
    """Extract a disc image (RVZ/ISO/GCZ/...) to *out_dir*."""
    cmd = [dolphin, "extract", "-i", src, "-o", out_dir]
    if quiet:
        cmd.append("-q")
    if work_dir:
        cmd += ["-u", work_dir]
    print(f"  Extracting {Path(src).name} ...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("STDOUT:", r.stdout)
        print("STDERR:", r.stderr)
        raise RuntimeError(f"DolphinTool extract failed (exit {r.returncode})")


def dolphin_convert(dolphin: str, src: str, dst: str, fmt: str = "rvz",
                    compress: str = "zstd", block: int = 131072,
                    level: int = 5, work_dir: str | None = None):
    """Convert a disc image between formats."""
    cmd = [dolphin, "convert", "-i", src, "-o", dst, "-f", fmt]
    if fmt in ("rvz", "gcz", "wia"):
        cmd += ["-b", str(block), "-c", compress, "-l", str(level)]
    if work_dir:
        cmd += ["-u", work_dir]
    print(f"  Converting -> {fmt.upper()}: {Path(dst).name}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("STDOUT:", r.stdout)
        print("STDERR:", r.stderr)
        raise RuntimeError(f"DolphinTool convert failed (exit {r.returncode})")
