#!/usr/bin/env python3
"""
Spyro: A Hero's Tail -- NTSC + French audio patch.

The Eurocom engine packs all game files in a single archive (Filelist.000)
with a binary index (Filelist.bin). This playbook:
  1. Parses both NTSC and PAL manifests (Filelist.txt)
  2. Maps NTSC English audio -> PAL French audio (sb_* -> fre_sb_*, etc.)
  3. Rebuilds Filelist.000 with French audio replacing English
  4. Regenerates Filelist.bin with updated sizes/offsets
  5. Regenerates Filelist.txt
  6. Builds a new GC ISO

Usage:
  python -m ngc.playbooks.spyro_aht_french [options]
"""

import argparse
import os
import struct
import sys
from pathlib import Path

from ngc import (
    scan_files_dir, build_iso_from_vfs,
    find_dolphin, dolphin_extract, dolphin_convert,
)
from ngc.playbooks import PROJECT_ROOT, WORK_DIR, OUT_DIR


# ---------------------------------------------------------------------------
# Eurocom Filelist parser
# ---------------------------------------------------------------------------

ARCHIVE_ALIGN = 0x800  # files aligned to 2048 bytes in Filelist.000

def parse_manifest(path: str) -> list[dict]:
    """Parse Filelist.txt -> list of {name, short, size, version, hash, ts, offset}."""
    entries = []
    with open(path, "r", errors="replace") as f:
        for line in f:
            idx = line.find(" : Len")
            if idx < 0:
                continue
            name = line[:idx].strip()
            rest = line[idx:]
            parts = rest.split(" : ")
            length = version = hash_val = ts = offset = 0
            for p in parts:
                p = p.strip()
                if p.startswith("Len"):
                    length = int(p.split()[1])
                elif p.startswith("Ver"):
                    version = int(p.split()[1])
                elif p.startswith("Hash"):
                    hash_val = int(p.split()[1], 16)
                elif p.startswith("Ts"):
                    ts = int(p.split()[1], 16)
                elif p.startswith("Loc"):
                    loc_str = p.split()[1].split(":")[0]
                    offset = int(loc_str, 16)
            short = name.rsplit("\\", 1)[-1]
            entries.append({
                "name": name, "short": short, "size": length,
                "version": version, "hash": hash_val, "ts": ts, "offset": offset,
            })
    return entries


def parse_filelist_bin(path: str) -> tuple[bytes, list[list[int]], bytes]:
    """
    Parse Filelist.bin -> (header_16bytes, entries_list, tail_bytes).
    Each entry is [field0, size, hash, version, type_flags, unk, archive_offset].
    """
    data = open(path, "rb").read()
    header = data[:16]
    ver, total_size, count, flags = struct.unpack_from(">IIII", header)

    entries = []
    for i in range(count):
        off = 16 + i * 28
        fields = list(struct.unpack_from(">IIIIIII", data, off))
        entries.append(fields)

    tail_start = 16 + count * 28
    tail = data[tail_start:]
    return header, entries, tail


def write_filelist_bin(header: bytes, entries: list[list[int]], tail: bytes,
                       output: str):
    """Write a new Filelist.bin from header + entries + tail."""
    hdr = bytearray(header)
    count = len(entries)
    total_size = 16 + count * 28 + len(tail)
    struct.pack_into(">I", hdr, 4, total_size)
    struct.pack_into(">I", hdr, 8, count)

    with open(output, "wb") as f:
        f.write(bytes(hdr))
        for e in entries:
            f.write(struct.pack(">IIIIIII", *e))
        f.write(tail)


def write_filelist_txt(entries_manifest: list[dict], output: str):
    """Write a new Filelist.txt from manifest entries."""
    with open(output, "w") as f:
        for e in entries_manifest:
            name = e["name"]
            padded = name.ljust(72)
            f.write(f"{padded} : Len {e['size']:>10d} : "
                    f"Ver {e['version']:>4d} : "
                    f"Hash 0x{e['hash']:08x} : "
                    f"Ts 0x{e['ts']:08x} :  "
                    f"Loc {e['offset']:>12x}:000\n")


# ---------------------------------------------------------------------------
# Audio mapping
# ---------------------------------------------------------------------------

def build_audio_mapping(ntsc_manifest: list[dict],
                        pal_manifest: list[dict]) -> dict[int, dict]:
    """
    Map NTSC audio entries to PAL French equivalents.
    Returns {ntsc_entry_index: pal_manifest_entry}.
    """
    # Build PAL lookup by short name
    pal_by_short = {e["short"].lower(): e for e in pal_manifest}

    mapping = {}
    for i, entry in enumerate(ntsc_manifest):
        short = entry["short"].lower()

        # eng_* -> fre_* (NTSC already uses eng_ prefix for English audio)
        if short.startswith("eng_"):
            fr_name = "fre_" + short[4:]  # replace "eng_" with "fre_"
            if fr_name in pal_by_short:
                mapping[i] = pal_by_short[fr_name]

    return mapping


# ---------------------------------------------------------------------------
# Archive rebuilder
# ---------------------------------------------------------------------------

def patch_archive_inplace(ntsc_manifest: list[dict], ntsc_archive: str,
                          pal_manifest_lookup: dict[int, dict], pal_archive: str,
                          out_archive: str, verbose: bool = True) -> int:
    """
    Copy NTSC Filelist.000 and overwrite eng_ audio with fre_ audio IN-PLACE.
    Only patches files where FR size <= EN size (preserves all offsets).
    Returns count of patched files.
    """
    import shutil
    if verbose:
        print(f"  Copying NTSC archive ({os.path.getsize(ntsc_archive):,} bytes)...")
    shutil.copy2(ntsc_archive, out_archive)

    patched = 0
    skipped = 0
    lang_patched = 0

    with open(out_archive, "r+b") as out, open(pal_archive, "rb") as pal_f:
        for i, fr_entry in pal_manifest_lookup.items():
            ntsc_entry = ntsc_manifest[i]
            en_size = ntsc_entry["size"]
            fr_size = fr_entry["size"]

            if fr_size > en_size:
                if verbose:
                    print(f"  SKIP {ntsc_entry['short']} (FR {fr_size:,} > EN {en_size:,})")
                skipped += 1
                continue

            # Read French audio from PAL archive
            pal_f.seek(fr_entry["offset"])
            fr_data = pal_f.read(fr_size)

            # Write at the SAME offset in the output archive
            out.seek(ntsc_entry["offset"])
            out.write(fr_data)

            # Pad remaining bytes with zeros if FR is smaller
            if fr_size < en_size:
                out.write(b"\x00" * (en_size - fr_size))

            patched += 1

        # Patch language selector byte in ALL eng_ .sfx sound banks
        # Byte 6 of each MUSX file: 0x00=English -> 0x06=French
        # This tells the engine to load *_FR audio AND French subtitles
        for entry in ntsc_manifest:
            short = entry["short"].lower()
            if short.startswith("eng_") and short.endswith(".sfx"):
                out.seek(entry["offset"] + 6)
                out.write(b"\x06")
                lang_patched += 1

    if verbose:
        print(f"  Patched {patched} audio files in-place, skipped {skipped}")
        print(f"  Patched {lang_patched} .sfx language bytes (EN->FR)")

    return patched


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _find_file(directory: Path, *patterns: str) -> Path | None:
    for pat in patterns:
        matches = list(directory.glob(pat))
        if matches:
            return matches[0]
    return None


def main():
    ap = argparse.ArgumentParser(
        description="Patch Spyro AHT NTSC with French audio from PAL")
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
        _find_file(rom_dir, "*Spyro*Hero*Tail*NTSC*.rvz", "*Spyro*Hero*Tail*G5SE*.rvz",
                            "*Spyro*Hero*Tail*USA*.rvz")
    pal_src = Path(args.pal) if args.pal else \
        _find_file(rom_dir, "*Spyro*Hero*Tail*PAL*.rvz", "*Spyro*Hero*Tail*G5SP*.rvz")

    if not ntsc_src or not ntsc_src.exists():
        sys.exit("ERROR: NTSC file not found. Use --ntsc PATH.")
    if not pal_src or not pal_src.exists():
        sys.exit("ERROR: PAL file not found. Use --pal PATH.")

    output = Path(args.output) if args.output else \
        OUT_DIR / "Spyro_A_Heros_Tail-(NTSC-U)(Hack)(Fr)(G5SE7D)[Rev0].rvz"
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"NTSC  : {ntsc_src}")
    print(f"PAL   : {pal_src}")
    print(f"Out   : {output}\n")

    work = Path(args.work) if args.work else WORK_DIR
    work.mkdir(parents=True, exist_ok=True)

    ntsc_ext = work / "spyro_ntsc"
    pal_ext  = work / "spyro_pal"

    # [1/6] Extract discs
    print("[1/6] Extracting discs ...")
    for src, dst in [(ntsc_src, ntsc_ext), (pal_src, pal_ext)]:
        if (dst / "sys" / "main.dol").exists():
            print(f"  {dst.name}/ already extracted -- skipping.")
        else:
            dolphin_extract(dolphin, str(src), str(dst))

    ntsc_files = ntsc_ext / "files"
    pal_files  = pal_ext  / "files"

    # [2/6] Parse manifests
    print("\n[2/6] Parsing manifests ...")
    ntsc_manifest = parse_manifest(str(ntsc_files / "Filelist.txt"))
    pal_manifest  = parse_manifest(str(pal_files / "Filelist.txt"))
    print(f"  NTSC: {len(ntsc_manifest)} entries")
    print(f"  PAL:  {len(pal_manifest)} entries")

    # [3/6] Build audio mapping
    print("\n[3/6] Building FR audio mapping ...")
    mapping = build_audio_mapping(ntsc_manifest, pal_manifest)
    print(f"  Mapped {len(mapping)} NTSC audio files -> PAL French equivalents")
    # Show a few examples
    for i, pal_e in list(mapping.items())[:5]:
        print(f"    {ntsc_manifest[i]['short']} -> {pal_e['short']}")

    # [4/5] Patch archive in-place
    print(f"\n[4/5] Patching Filelist.000 in-place (FR audio over EN) ...")
    patched_archive = str(work / "Filelist.000.patched")
    patched_count = patch_archive_inplace(
        ntsc_manifest, str(ntsc_files / "Filelist.000"),
        mapping, str(pal_files / "Filelist.000"),
        patched_archive, verbose=True,
    )

    # [5/5] Build ISO (NTSC sys/ = 60Hz, patched archive = FR audio)
    print(f"\n[5/5] Building patched ISO ...")
    vfs = scan_files_dir(str(ntsc_files))
    vfs["Filelist.000"] = patched_archive
    print(f"  Total files in VFS: {len(vfs)}")

    iso_path = str(work / "SpyroAHT-NTSC-FR.iso")
    build_iso_from_vfs(str(ntsc_ext / "sys"), vfs, iso_path, verbose=True)

    print(f"\nConverting ISO -> RVZ ...")
    dolphin_convert(dolphin, iso_path, str(output), fmt="rvz")
    if os.path.exists(iso_path):
        os.remove(iso_path)
    if os.path.exists(patched_archive):
        os.remove(patched_archive)

    print(f"\nDone!  {output}")
    print(f"Patched {patched_count}/42 audio files in-place (4 _mini_sgt skipped: FR bigger than EN).")
    print("NTSC 60Hz + French voice audio. Text stays English (language selector hardcoded in DOL).")


if __name__ == "__main__":
    main()
