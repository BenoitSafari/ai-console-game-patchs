#!/usr/bin/env python3
"""
Ultimate Spider-Man -- NTSC + French patch.

Creates a hybrid disc:
  - NTSC-U base (NTSC timing)
  - French voice audio  (_FR.WBK from PAL, kept as-is)
  - French text          (PAL amalga_gc.pak + country code 'F')
  - PAL intro movies     (optional)

Usage:
  python -m ngc.playbooks.usm_french [options]
"""

import argparse
import os
import re
import shutil
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


def build_fr_vfs(ntsc_files: Path, pal_files: Path,
                 include_audio: bool = True,
                 include_movies: bool = True) -> dict[str, str]:
    print("  Scanning NTSC files ...")
    vfs = scan_files_dir(str(ntsc_files))

    if include_audio:
        audio_count = 0
        for fr_file in pal_files.rglob("*_FR.WBK"):
            rel = fr_file.relative_to(pal_files).as_posix()
            vfs[rel] = str(fr_file)
            audio_count += 1
        print(f"  French audio banks : {audio_count} files (_FR.WBK kept as-is)")

    pak_src = pal_files / "packs" / "amalga_gc.pak"
    if pak_src.exists():
        ntsc_pak_size = (ntsc_files / "packs" / "amalga_gc.pak").stat().st_size \
            if (ntsc_files / "packs" / "amalga_gc.pak").exists() else 0
        print(f"  French text pak    : {pak_src.stat().st_size:,} B "
              f"(NTSC was {ntsc_pak_size:,} B)")
        vfs["packs/amalga_gc.pak"] = str(pak_src)
    else:
        print("  WARNING: packs/amalga_gc.pak not found in PAL.")

    if include_movies:
        movie_count = 0
        for pal_movie in pal_files.rglob("*_PAL.h4m"):
            rel      = pal_movie.relative_to(pal_files).as_posix()
            ntsc_rel = re.sub(r"_PAL\.h4m$", ".h4m", rel, flags=re.IGNORECASE)
            vfs[ntsc_rel] = str(pal_movie)
            movie_count += 1
        if movie_count:
            print(f"  PAL movies         : {movie_count} files (_PAL.h4m -> .h4m)")

    print(f"  Total files in VFS : {len(vfs)}")
    return vfs


def main():
    ap = argparse.ArgumentParser(description="Patch USM NTSC with French from PAL")
    ap.add_argument("--ntsc",    metavar="PATH")
    ap.add_argument("--pal",     metavar="PATH")
    ap.add_argument("--output",  metavar="PATH")
    ap.add_argument("--dolphin", metavar="PATH")
    ap.add_argument("--work",    metavar="DIR")
    ap.add_argument("--no-audio",  action="store_true")
    ap.add_argument("--no-movies", action="store_true")
    args = ap.parse_args()

    dolphin = args.dolphin or find_dolphin()
    if not dolphin:
        sys.exit("ERROR: DolphinTool.exe not found. Add it to PATH.")
    print(f"DolphinTool : {dolphin}\n")

    rom_dir = PROJECT_ROOT.parent
    ntsc_src = Path(args.ntsc) if args.ntsc else \
        _find_file(rom_dir, "*SpiderMan*NTSC*US*.rvz", "*SpiderMan*GUTE*.rvz",
                            "*SpiderMan*NTSC*En*.rvz")
    pal_src  = Path(args.pal) if args.pal else \
        _find_file(rom_dir, "*SpiderMan*PAL*Fr*.rvz", "*SpiderMan*GUTF*.rvz")

    if not ntsc_src or not ntsc_src.exists():
        sys.exit("ERROR: NTSC file not found. Use --ntsc PATH.")
    if not pal_src or not pal_src.exists():
        sys.exit("ERROR: PAL FR file not found. Use --pal PATH.")

    output = Path(args.output) if args.output else \
        OUT_DIR / "Ultimate_SpiderMan-(NTSC-U)(Hack)(Fr)(GUTE52)(Rev0).rvz"
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"NTSC  : {ntsc_src}")
    print(f"PAL   : {pal_src}")
    print(f"Out   : {output}\n")

    work = Path(args.work) if args.work else WORK_DIR
    work.mkdir(parents=True, exist_ok=True)

    ntsc_ext = work / "usm_ntsc"
    pal_ext  = work / "usm_pal"

    print("[1/5] Extracting discs ...")
    for src, dst in [(ntsc_src, ntsc_ext), (pal_src, pal_ext)]:
        if (dst / "sys" / "main.dol").exists():
            print(f"  {dst.name}/ already extracted -- skipping.")
        else:
            dolphin_extract(dolphin, str(src), str(dst))

    ntsc_sys   = ntsc_ext / "sys"
    ntsc_files = ntsc_ext / "files"
    pal_files  = pal_ext  / "files"

    print("\n[2/5] Building merged VFS ...")
    vfs = build_fr_vfs(ntsc_files, pal_files,
                       include_audio=not args.no_audio,
                       include_movies=not args.no_movies)

    patched_sys = work / "usm_patched_sys"
    if patched_sys.exists():
        shutil.rmtree(patched_sys)
    shutil.copytree(ntsc_sys, patched_sys)

    boot_bin = patched_sys / "boot.bin"
    data = bytearray(boot_bin.read_bytes())
    old_cc = chr(data[3])
    data[3] = ord("F")
    boot_bin.write_bytes(bytes(data))
    new_id = data[0:6].decode("ascii", errors="replace")
    print(f"\n[3/5] Patched boot.bin  country '{old_cc}' -> 'F'  (Game ID: {new_id})")

    patched_iso = str(work / "USM-NTSC-FR.iso")
    print(f"\n[4/5] Building patched ISO ...")
    build_iso_from_vfs(str(patched_sys), vfs, patched_iso, verbose=True)

    print(f"\n[5/5] Converting ISO -> RVZ ...")
    dolphin_convert(dolphin, patched_iso, str(output), fmt="rvz")
    if os.path.exists(patched_iso):
        os.remove(patched_iso)

    print(f"\nDone!  {output}")


if __name__ == "__main__":
    main()
