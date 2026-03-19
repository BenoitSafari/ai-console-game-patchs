#!/usr/bin/env python3
"""
Paper Mario: The Thousand-Year Door -- NTSC + French text patch.

Text is in separate msg/XX/ directories (US, FR, DE, SP, IT).
This playbook copies PAL's msg/FR/*.txt over msg/US/ and e/fr/ over e/us/.

Usage:
  python -m ngc.playbooks.pm_french [options]
"""

import argparse
import os
import sys
from pathlib import Path

from ngc import (
    scan_files_dir, build_iso_from_vfs,
    find_dolphin, dolphin_extract, dolphin_convert,
)
from ngc.playbooks import PROJECT_ROOT, WORK_DIR, OUT_DIR


def _find_file(directory: Path, *patterns: str) -> Path | None:
    for pat in patterns:
        matches = list(directory.glob(pat))
        if matches:
            return matches[0]
    return None


def build_fr_vfs(ntsc_files: Path, pal_files: Path) -> dict[str, str]:
    print("  Scanning NTSC files ...")
    vfs = scan_files_dir(str(ntsc_files))

    fr_msg = pal_files / "msg" / "FR"
    txt_count = 0
    if fr_msg.exists():
        for fr_file in sorted(fr_msg.iterdir()):
            if fr_file.is_file():
                vfs[f"msg/US/{fr_file.name}"] = str(fr_file)
                txt_count += 1
    print(f"  French text        : {txt_count} files (msg/FR -> msg/US)")

    fr_eff = pal_files / "e" / "fr"
    eff_count = 0
    if fr_eff.exists():
        for fr_file in sorted(fr_eff.iterdir()):
            if fr_file.is_file():
                vfs[f"e/us/{fr_file.name}"] = str(fr_file)
                eff_count += 1
    print(f"  French effects     : {eff_count} files (e/fr -> e/us)")

    print(f"  Total files in VFS : {len(vfs)}")
    return vfs


def main():
    ap = argparse.ArgumentParser(
        description="Patch Paper Mario TTYD NTSC with French text from PAL")
    ap.add_argument("--ntsc",    metavar="PATH")
    ap.add_argument("--pal",     metavar="PATH")
    ap.add_argument("--output",  metavar="PATH")
    ap.add_argument("--dolphin", metavar="PATH")
    ap.add_argument("--work",    metavar="DIR")
    args = ap.parse_args()

    dolphin = args.dolphin or find_dolphin()
    if not dolphin:
        sys.exit("ERROR: DolphinTool.exe not found. Add it to PATH.")
    print(f"DolphinTool : {dolphin}\n")

    rom_dir = PROJECT_ROOT.parent
    ntsc_src = Path(args.ntsc) if args.ntsc else \
        _find_file(rom_dir, "*Paper*Mario*USA*.rvz", "*Paper*Mario*G8ME*.rvz",
                            "*Paper*Mario*NTSC*.rvz")
    pal_src = Path(args.pal) if args.pal else \
        _find_file(rom_dir, "*Paper*Mario*PAL*.rvz", "*Paper*Mario*G8MP*.rvz")

    if not ntsc_src or not ntsc_src.exists():
        sys.exit("ERROR: NTSC file not found. Use --ntsc PATH.")
    if not pal_src or not pal_src.exists():
        sys.exit("ERROR: PAL file not found. Use --pal PATH.")

    output = Path(args.output) if args.output else \
        OUT_DIR / "Paper_Mario_TTYD-(NTSC-U)(Hack)(Fr)(G8ME01)[Rev0].rvz"
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"NTSC  : {ntsc_src}")
    print(f"PAL   : {pal_src}")
    print(f"Out   : {output}\n")

    work = Path(args.work) if args.work else WORK_DIR
    work.mkdir(parents=True, exist_ok=True)

    ntsc_ext = work / "pm_ntsc"
    pal_ext  = work / "pm_pal"

    print("[1/4] Extracting discs ...")
    for src, dst in [(ntsc_src, ntsc_ext), (pal_src, pal_ext)]:
        if (dst / "sys" / "main.dol").exists():
            print(f"  {dst.name}/ already extracted -- skipping.")
        else:
            dolphin_extract(dolphin, str(src), str(dst))

    ntsc_sys   = ntsc_ext / "sys"
    ntsc_files = ntsc_ext / "files"
    pal_files  = pal_ext  / "files"

    print("\n[2/4] Building merged VFS ...")
    vfs = build_fr_vfs(ntsc_files, pal_files)

    iso_path = str(work / "PM-TTYD-NTSC-FR.iso")
    print(f"\n[3/4] Building patched ISO ...")
    build_iso_from_vfs(str(ntsc_sys), vfs, iso_path, verbose=True)

    print(f"\n[4/4] Converting ISO -> RVZ ...")
    dolphin_convert(dolphin, iso_path, str(output), fmt="rvz")
    if os.path.exists(iso_path):
        os.remove(iso_path)

    print(f"\nDone!  {output}")


if __name__ == "__main__":
    main()
