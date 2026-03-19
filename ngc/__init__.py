"""
ngc -- GameCube disc image tools.

Public API
----------
    GCDisc              Read / extract a GameCube ISO.
    DiscHeader          Parse & modify the 0x440-byte disc header.
    build_iso           Build ISO from sys/ + files/ directories.
    build_iso_from_vfs  Build ISO from sys/ + virtual file dict.
    scan_files_dir      Turn a directory into a VFS dict.
    patch_iso           Replace files in an existing ISO.
    get_dol_size        Compute DOL executable size from its header.
    align_up            Round up to alignment boundary.

DolphinTool helpers
-------------------
    find_dolphin        Locate DolphinTool.exe on disk.
    dolphin_extract     Extract a disc image via DolphinTool.
    dolphin_convert     Convert between disc formats via DolphinTool.
"""

from .core import (
    GCDisc,
    DiscHeader,
    build_iso,
    build_iso_from_vfs,
    scan_files_dir,
    patch_iso,
    get_dol_size,
    align_up,
)

from .dolphin import (
    find_dolphin,
    dolphin_extract,
    dolphin_convert,
)

__all__ = [
    "GCDisc", "DiscHeader",
    "build_iso", "build_iso_from_vfs", "scan_files_dir", "patch_iso",
    "get_dol_size", "align_up",
    "find_dolphin", "dolphin_extract", "dolphin_convert",
]
