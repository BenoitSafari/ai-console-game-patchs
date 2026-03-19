#!/usr/bin/env python3
"""
Animal Crossing -- Extract standalone French version from PAL disc.

The PAL disc contains per-language TGC sub-discs. This playbook extracts
the French TGC (forest_Frn_Final_PAL50.tgc) and rebuilds it as a standalone ISO.

Usage:
  python -m ngc.playbooks.ac_french [options]
"""

import argparse
import os
import struct
import sys
from pathlib import Path

from ngc import (
    DiscHeader, build_iso_from_vfs, scan_files_dir,
    find_dolphin, dolphin_extract, dolphin_convert,
)
from ngc.core import (
    HEADER_SIZE, BI2_OFFSET, BI2_SIZE, APPLOADER_OFFSET, get_dol_size,
)
from ngc.playbooks import PROJECT_ROOT, WORK_DIR, OUT_DIR


TGC_MAGIC = 0xAE0F38A2


def extract_tgc(tgc_path: str, output_dir: str, verbose: bool = True):
    """Extract a GameCube TGC sub-disc to *output_dir* (sys/ + files/)."""
    out = Path(output_dir)
    sys_d = out / "sys"
    fil_d = out / "files"
    sys_d.mkdir(parents=True, exist_ok=True)
    fil_d.mkdir(parents=True, exist_ok=True)

    with open(tgc_path, "rb") as f:
        hdr = f.read(0x40)
        magic = struct.unpack_from(">I", hdr, 0x00)[0]
        assert magic == TGC_MAGIC, f"Not a TGC file (magic=0x{magic:08X})"

        hdr_size     = struct.unpack_from(">I", hdr, 0x08)[0]
        fst_off_tgc  = struct.unpack_from(">I", hdr, 0x10)[0]
        fst_size     = struct.unpack_from(">I", hdr, 0x14)[0]
        dol_off_tgc  = struct.unpack_from(">I", hdr, 0x1C)[0]
        dol_size     = struct.unpack_from(">I", hdr, 0x20)[0]
        file_area    = struct.unpack_from(">I", hdr, 0x24)[0]
        file_area_sz = struct.unpack_from(">I", hdr, 0x28)[0]
        fst_base     = struct.unpack_from(">I", hdr, 0x34)[0]

        if verbose:
            print(f"  TGC header size : 0x{hdr_size:X}")
            print(f"  DOL in TGC      : 0x{dol_off_tgc:08X} ({dol_size:,} B)")
            print(f"  FST in TGC      : 0x{fst_off_tgc:08X} ({fst_size} B)")
            print(f"  File area       : 0x{file_area:08X} ({file_area_sz:,} B)")

        f.seek(hdr_size)
        boot_bin = f.read(HEADER_SIZE)
        (sys_d / "boot.bin").write_bytes(boot_bin)

        f.seek(hdr_size + BI2_OFFSET)
        (sys_d / "bi2.bin").write_bytes(f.read(BI2_SIZE))

        f.seek(hdr_size + APPLOADER_OFFSET)
        al_hdr = f.read(0x20)
        al_code = struct.unpack_from(">I", al_hdr, 0x14)[0]
        al_tail = struct.unpack_from(">I", al_hdr, 0x18)[0]
        f.seek(hdr_size + APPLOADER_OFFSET)
        (sys_d / "apploader.img").write_bytes(f.read(0x20 + al_code + al_tail))

        f.seek(dol_off_tgc)
        (sys_d / "main.dol").write_bytes(f.read(dol_size))

        f.seek(fst_off_tgc)
        fst_data = f.read(fst_size)
        (sys_d / "fst.bin").write_bytes(fst_data)

        total_entries = struct.unpack_from(">I", fst_data, 8)[0]
        str_base = total_entries * 12

        entries = []
        for i in range(total_entries):
            base  = i * 12
            w0    = struct.unpack_from(">I", fst_data, base)[0]
            v1    = struct.unpack_from(">I", fst_data, base + 4)[0]
            v2    = struct.unpack_from(">I", fst_data, base + 8)[0]
            is_dir = (w0 >> 24) & 0xFF
            name_off = w0 & 0xFFFFFF
            if i == 0:
                name = ""
            else:
                ns = str_base + name_off
                ne = fst_data.index(b"\x00", ns)
                name = fst_data[ns:ne].decode("utf-8", errors="replace")
            entries.append((is_dir, name, v1, v2))

        file_count = 0

        def _walk(idx: int, cur_dir: Path):
            nonlocal file_count
            is_dir, name, v1, v2 = entries[idx]
            if is_dir:
                sub = (cur_dir / name) if name else cur_dir
                sub.mkdir(exist_ok=True)
                i = idx + 1
                end = v2
                while i < end:
                    child_dir, child_name, cv1, cv2 = entries[i]
                    _walk(i, sub)
                    i = cv2 if child_dir else i + 1
            else:
                tgc_pos = v1 - fst_base + file_area
                dest = cur_dir / name
                f.seek(tgc_pos)
                dest.write_bytes(f.read(v2))
                file_count += 1
                if verbose:
                    print(f"\r  Extracted {file_count} files...", end="", flush=True)

        _walk(0, fil_d)
        if verbose:
            print()
            hdr_obj = DiscHeader(boot_bin)
            print(f"  Game ID: {hdr_obj.game_id}")

    return str(sys_d), str(fil_d)


def main():
    ap = argparse.ArgumentParser(
        description="Extract standalone French Animal Crossing from PAL disc")
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
    pal_src = Path(args.pal) if args.pal else None
    if not pal_src:
        for pat in ["*Animal*Crossing*PAL*.rvz", "*Animal*Crossing*GAFP*.rvz"]:
            matches = list(rom_dir.glob(pat))
            if matches:
                pal_src = matches[0]
                break
    if not pal_src or not pal_src.exists():
        sys.exit("ERROR: PAL Animal Crossing not found. Use --pal PATH.")

    output = Path(args.output) if args.output else \
        OUT_DIR / "Animal_Crossing-(PAL)(Hack)(Fr)(GAFP01)[Rev0].rvz"
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"PAL   : {pal_src}")
    print(f"Out   : {output}\n")

    work = Path(args.work) if args.work else WORK_DIR
    work.mkdir(parents=True, exist_ok=True)

    pal_ext = work / "ac_pal"
    print("[1/4] Extracting PAL disc ...")
    if (pal_ext / "sys" / "main.dol").exists():
        print("  Already extracted -- skipping.")
    else:
        dolphin_extract(dolphin, str(pal_src), str(pal_ext))

    tgc_path = pal_ext / "files" / "tgc" / "forest_Frn_Final_PAL50.tgc"
    if not tgc_path.exists():
        sys.exit(f"ERROR: French TGC not found: {tgc_path}")

    tgc_extracted = work / "ac_fr_tgc"
    print(f"\n[2/4] Extracting French TGC ...")
    if (tgc_extracted / "sys" / "main.dol").exists():
        print("  Already extracted -- skipping.")
    else:
        extract_tgc(str(tgc_path), str(tgc_extracted))

    boot_path = tgc_extracted / "sys" / "boot.bin"
    boot_data = bytearray(boot_path.read_bytes())
    old_cc = chr(boot_data[3])
    boot_data[3] = ord("F")
    boot_path.write_bytes(bytes(boot_data))
    new_id = boot_data[0:6].decode("ascii", errors="replace")
    print(f"  Patched country '{old_cc}' -> 'F'  (Game ID: {new_id})")

    iso_path = str(work / "AC-FR-Standalone.iso")
    print(f"\n[3/4] Building standalone French ISO ...")
    vfs = scan_files_dir(str(tgc_extracted / "files"))
    build_iso_from_vfs(str(tgc_extracted / "sys"), vfs, iso_path, verbose=True)

    print(f"\n[4/4] Converting ISO -> RVZ ...")
    dolphin_convert(dolphin, iso_path, str(output), fmt="rvz")
    if os.path.exists(iso_path):
        os.remove(iso_path)

    print(f"\nDone!  {output}")
    print("Note: PAL French version (50Hz). Force 60Hz in Dolphin if needed.")


if __name__ == "__main__":
    main()
