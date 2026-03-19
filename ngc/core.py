"""
core.py – GameCube disc image parser, extractor & builder.

Supports .iso / .gcm GameCube disc images only.
For RVZ/GCZ/WIA use DolphinTool to convert to/from ISO first.
"""

import struct
import os
import shutil
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def align_up(value: int, alignment: int) -> int:
    """Round value up to the next multiple of alignment."""
    if alignment <= 1:
        return value
    return (value + alignment - 1) & ~(alignment - 1)


# ---------------------------------------------------------------------------
# Disc Header
# ---------------------------------------------------------------------------

HEADER_OFFSET    = 0x0000
HEADER_SIZE      = 0x0440
BI2_OFFSET       = 0x0440
BI2_SIZE         = 0x2000
APPLOADER_OFFSET = 0x2440

GC_MAGIC  = 0xC2339F3D
WII_MAGIC = 0x5D1C9EA3


class DiscHeader:
    """Parses and (re)writes the 0x440-byte GameCube disc header."""

    def __init__(self, data: bytes):
        assert len(data) >= HEADER_SIZE, "Header data too short"
        self._raw = bytearray(data[:HEADER_SIZE])

        self.game_id      = data[0:6].decode("ascii", errors="replace").rstrip("\x00")
        self.disc_num     = data[6]
        self.disc_version = data[7]
        gc_magic  = struct.unpack_from(">I", data, 0x1C)[0]
        wii_magic = struct.unpack_from(">I", data, 0x18)[0]
        self.is_gc  = (gc_magic  == GC_MAGIC)
        self.is_wii = (wii_magic == WII_MAGIC)
        self.title      = data[0x20:0x420].decode("utf-8", errors="replace").rstrip("\x00")
        self.dol_offset = struct.unpack_from(">I", data, 0x420)[0]
        self.fst_offset = struct.unpack_from(">I", data, 0x424)[0]
        self.fst_size   = struct.unpack_from(">I", data, 0x428)[0]

    @property
    def country_code(self) -> str:
        return chr(self._raw[3])

    @country_code.setter
    def country_code(self, c: str):
        self._raw[3] = ord(c[0])

    def update_offsets(self, dol_offset: int, fst_offset: int, fst_size: int):
        self.dol_offset = dol_offset
        self.fst_offset = fst_offset
        self.fst_size   = fst_size
        struct.pack_into(">I", self._raw, 0x420, dol_offset)
        struct.pack_into(">I", self._raw, 0x424, fst_offset)
        struct.pack_into(">I", self._raw, 0x428, fst_size)
        struct.pack_into(">I", self._raw, 0x42C, fst_size)

    def to_bytes(self) -> bytes:
        return bytes(self._raw)


# ---------------------------------------------------------------------------
# DOL size
# ---------------------------------------------------------------------------

def get_dol_size(data: bytes) -> int:
    """
    Compute the byte size of a DOL executable from its 0x100-byte header.
    DOL header layout (all big-endian u32):
      0x00 – 7  text section offsets (from DOL start)
      0x1C – 11 data section offsets
      0x90 – 7  text section sizes
      0xAC – 11 data section sizes
    """
    max_end = 0x100  # at minimum the header itself
    for i in range(7):
        off  = struct.unpack_from(">I", data, 0x00 + i * 4)[0]
        size = struct.unpack_from(">I", data, 0x90 + i * 4)[0]
        if off and size:
            max_end = max(max_end, off + size)
    for i in range(11):
        off  = struct.unpack_from(">I", data, 0x1C + i * 4)[0]
        size = struct.unpack_from(">I", data, 0xAC + i * 4)[0]
        if off and size:
            max_end = max(max_end, off + size)
    return max_end


# ---------------------------------------------------------------------------
# FST (File System Table)
# ---------------------------------------------------------------------------

_ENTRY_SIZE = 12


class _FSTEntry:
    __slots__ = ("is_dir", "name_off", "value1", "value2", "name", "children")

    def __init__(self, is_dir, name_off, value1, value2):
        self.is_dir   = is_dir
        self.name_off = name_off
        self.value1   = value1   # file: ISO data offset  |  dir: parent entry index
        self.value2   = value2   # file: file size         |  dir: next entry after dir
        self.name     = ""
        self.children: list["_FSTEntry"] = []


def _parse_fst(fst_data: bytes) -> _FSTEntry:
    """Return the root _FSTEntry with the full tree populated."""
    total = struct.unpack_from(">I", fst_data, 8)[0]
    str_base = total * _ENTRY_SIZE

    entries: list[_FSTEntry] = []
    for i in range(total):
        base  = i * _ENTRY_SIZE
        word0 = struct.unpack_from(">I", fst_data, base)[0]
        is_dir   = (word0 >> 24) & 0xFF
        name_off = word0 & 0x00FFFFFF
        value1   = struct.unpack_from(">I", fst_data, base + 4)[0]
        value2   = struct.unpack_from(">I", fst_data, base + 8)[0]

        e = _FSTEntry(bool(is_dir), name_off, value1, value2)
        str_start = str_base + name_off
        str_end   = fst_data.index(b"\x00", str_start)
        e.name    = fst_data[str_start:str_end].decode("utf-8", errors="replace")
        entries.append(e)

    def _build(idx: int, parent: _FSTEntry):
        e = entries[idx]
        if e.is_dir:
            end = e.value2
            i   = idx + 1
            while i < end:
                child = entries[i]
                e.children.append(child)
                _build(i, e)
                i = child.value2 if child.is_dir else i + 1

    _build(0, None)
    return entries[0]


def _build_fst(files_root: Path, file_data_start: int,
               file_align: int = 4) -> tuple[bytes, dict]:
    """Walk *files_root* and build a GameCube FST."""
    entries      = []
    string_table = bytearray(b"\x00")
    seen_strings: dict[str, int] = {}
    entry_file_list: list[tuple[str, int, Path, int]] = []

    def _get_str_off(name: str) -> int:
        if name in seen_strings:
            return seen_strings[name]
        off = len(string_table)
        seen_strings[name] = off
        string_table.extend(name.encode("utf-8") + b"\x00")
        return off

    def _add_dir(dir_path: Path, virtual_path: str, parent_idx: int):
        dir_idx  = len(entries)
        name     = dir_path.name if virtual_path else ""
        name_off = _get_str_off(name) if name else 0
        entries.append([1, name_off, parent_idx, 0])

        children = sorted(dir_path.iterdir(), key=lambda p: p.name.lower())
        for child in children:
            cvpath = (virtual_path + "/" + child.name) if virtual_path else child.name
            if child.is_dir():
                _add_dir(child, cvpath, dir_idx)
            elif child.is_file():
                fidx = len(entries)
                foff = _get_str_off(child.name)
                size = child.stat().st_size
                entries.append([0, foff, 0, size])
                entry_file_list.append((cvpath, fidx, child, size))

        entries[dir_idx][3] = len(entries)

    _add_dir(files_root, "", 0)

    cur = file_data_start
    file_map: dict[str, tuple[int, Path, int]] = {}
    for vpath, fidx, local_path, size in sorted(entry_file_list, key=lambda x: x[0]):
        cur = align_up(cur, file_align)
        entries[fidx][2] = cur
        file_map[vpath] = (cur, local_path, size)
        cur += size

    fst = bytearray()
    for is_dir, name_off, v1, v2 in entries:
        word0 = (is_dir << 24) | (name_off & 0x00FFFFFF)
        fst += struct.pack(">III", word0, v1, v2)
    fst += bytes(string_table)
    return bytes(fst), file_map


# ---------------------------------------------------------------------------
# VFS-based FST builder
# ---------------------------------------------------------------------------

_DOL_ALIGN  = 0x100
_FST_ALIGN  = 0x20
_FILE_ALIGN = 0x20


class _TreeNode:
    __slots__ = ("name", "subdirs", "files")

    def __init__(self, name: str):
        self.name    = name
        self.subdirs: dict[str, "_TreeNode"] = {}
        self.files:   dict[str, str]         = {}


def _vfs_to_tree(virtual_files: dict[str, str]) -> _TreeNode:
    root = _TreeNode("")
    for vpath, local in virtual_files.items():
        parts = vpath.replace("\\", "/").strip("/").split("/")
        node  = root
        for part in parts[:-1]:
            node = node.subdirs.setdefault(part, _TreeNode(part))
        node.files[parts[-1]] = local
    return root


def _build_fst_from_tree(root: _TreeNode, file_data_start: int,
                          file_align: int = 4) -> tuple[bytes, dict]:
    entries      = []
    string_table = bytearray(b"\x00")
    seen_strings: dict[str, int] = {}
    file_entries: list[tuple[str, int, str]] = []

    def _str(name: str) -> int:
        if name in seen_strings:
            return seen_strings[name]
        off = len(string_table)
        seen_strings[name] = off
        string_table.extend(name.encode("utf-8") + b"\x00")
        return off

    def _add(node: _TreeNode, vpath: str, parent_idx: int):
        dir_idx  = len(entries)
        name_off = _str(node.name) if node.name else 0
        entries.append([1, name_off, parent_idx, 0])

        for dname in sorted(node.subdirs, key=str.lower):
            cvpath = (vpath + "/" + dname) if vpath else dname
            _add(node.subdirs[dname], cvpath, dir_idx)

        for fname in sorted(node.files, key=str.lower):
            fvpath = (vpath + "/" + fname) if vpath else fname
            fidx   = len(entries)
            local  = node.files[fname]
            fsize  = os.path.getsize(local)
            entries.append([0, _str(fname), 0, fsize])
            file_entries.append((fvpath, fidx, local))

        entries[dir_idx][3] = len(entries)

    _add(root, "", 0)

    cur      = file_data_start
    file_map: dict[str, tuple[int, Path, int]] = {}
    for vpath, fidx, local in sorted(file_entries, key=lambda x: x[0]):
        cur     = align_up(cur, file_align)
        size    = os.path.getsize(local)
        entries[fidx][2] = cur
        file_map[vpath]  = (cur, Path(local), size)
        cur += size

    fst = bytearray()
    for is_dir, name_off, v1, v2 in entries:
        word0 = (is_dir << 24) | (name_off & 0x00FFFFFF)
        fst  += struct.pack(">III", word0, v1, v2)
    fst += bytes(string_table)
    return bytes(fst), file_map


# ---------------------------------------------------------------------------
# ISO builders
# ---------------------------------------------------------------------------

def build_iso_from_vfs(sys_dir: str, virtual_files: dict[str, str],
                        output: str, file_align: int = _FILE_ALIGN,
                        verbose: bool = True):
    """Build a GC ISO where game files come from *virtual_files* dict."""
    sys_p = Path(sys_dir)
    header_data    = (sys_p / "boot.bin"     ).read_bytes()
    bi2_data       = (sys_p / "bi2.bin"      ).read_bytes()
    apploader_data = (sys_p / "apploader.img").read_bytes()
    dol_data       = (sys_p / "main.dol"     ).read_bytes()

    header = DiscHeader(header_data)

    appl_end   = APPLOADER_OFFSET + len(apploader_data)
    dol_offset = align_up(appl_end, _DOL_ALIGN)
    dol_end    = dol_offset + len(dol_data)
    fst_offset = align_up(dol_end, _FST_ALIGN)

    root_node = _vfs_to_tree(virtual_files)

    fst_tmp, _  = _build_fst_from_tree(root_node, fst_offset + 0x200000, file_align)
    fst_size    = len(fst_tmp)
    file_start  = align_up(fst_offset + fst_size, file_align)
    fst_data, file_map = _build_fst_from_tree(root_node, file_start, file_align)
    assert len(fst_data) == fst_size, "FST size changed between passes"

    header.update_offsets(dol_offset, fst_offset, fst_size)

    if verbose:
        safe_title = header.title.encode("ascii", errors="replace").decode("ascii")
        print(f"  Game    : {header.game_id} - {safe_title}")
        print(f"  DOL     : 0x{dol_offset:08X}  ({len(dol_data):,} B)")
        print(f"  FST     : 0x{fst_offset:08X}  ({fst_size:,} B, {len(virtual_files)} files)")
        print(f"  Files @ : 0x{file_start:08X}")

    total   = len(file_map)
    written = 0

    with open(output, "wb") as out:
        out.write(header.to_bytes())
        out.seek(BI2_OFFSET);       out.write(bi2_data[:BI2_SIZE])
        out.seek(APPLOADER_OFFSET); out.write(apploader_data)
        out.seek(dol_offset);       out.write(dol_data)
        out.seek(fst_offset);       out.write(fst_data)

        for _, (iso_off, local_path, size) in sorted(
                file_map.items(), key=lambda x: x[1][0]):
            out.seek(iso_off)
            with open(local_path, "rb") as f:
                out.write(f.read())
            written += 1
            if verbose:
                print(f"\r  Writing {written}/{total} files...", end="", flush=True)

    if verbose:
        iso_size = os.path.getsize(output)
        print(f"\n  ISO: {output}  ({iso_size:,} bytes)")


def build_iso(sys_dir: str, files_dir: str, output: str,
              file_align: int = _FILE_ALIGN, verbose: bool = True):
    """Build a GameCube ISO from *sys_dir* + *files_dir*."""
    vfs = scan_files_dir(files_dir)
    build_iso_from_vfs(sys_dir, vfs, output, file_align, verbose)


def scan_files_dir(files_dir: str) -> dict[str, str]:
    """Scan a directory -> {virtual_path: local_path_str}."""
    base   = Path(files_dir)
    result = {}
    for f in base.rglob("*"):
        if f.is_file():
            vpath = f.relative_to(base).as_posix()
            result[vpath] = str(f)
    return result


# ---------------------------------------------------------------------------
# GCDisc – main class
# ---------------------------------------------------------------------------

class GCDisc:
    """Opens a GameCube ISO image and provides read access."""

    def __init__(self, path: str):
        self.path = path
        self._f = open(path, "rb")
        self._parse()

    def _parse(self):
        f = self._f
        f.seek(0)
        self.header = DiscHeader(f.read(HEADER_SIZE))
        if not self.header.is_gc:
            raise ValueError(f"{self.path}: not a GameCube disc image")

        f.seek(BI2_OFFSET)
        self.bi2 = f.read(BI2_SIZE)

        f.seek(APPLOADER_OFFSET)
        al_hdr  = f.read(0x20)
        al_code = struct.unpack_from(">I", al_hdr, 0x14)[0]
        al_tail = struct.unpack_from(">I", al_hdr, 0x18)[0]
        f.seek(APPLOADER_OFFSET)
        self.apploader = f.read(0x20 + al_code + al_tail)

        f.seek(self.header.dol_offset)
        dol_hdr = f.read(0x100)
        dol_sz  = get_dol_size(dol_hdr)
        f.seek(self.header.dol_offset)
        self.dol = f.read(dol_sz)

        f.seek(self.header.fst_offset)
        self.fst_data = f.read(self.header.fst_size)
        self.fst_root = _parse_fst(self.fst_data)

    def close(self):
        self._f.close()

    def __enter__(self): return self
    def __exit__(self, *_): self.close()

    def list_files(self) -> list[str]:
        result = []
        def _walk(e: _FSTEntry, prefix: str):
            p = (prefix + "/" + e.name) if (prefix and e.name) else (e.name or prefix)
            if e.is_dir:
                for c in e.children:
                    _walk(c, p)
            else:
                result.append(p)
        _walk(self.fst_root, "")
        return result

    def read_file(self, virtual_path: str) -> bytes:
        parts = virtual_path.strip("/").split("/")
        e = self.fst_root
        for part in parts:
            matched = None
            for child in e.children:
                if child.name.lower() == part.lower():
                    matched = child
                    break
            if matched is None:
                raise FileNotFoundError(f"Not found in disc: {virtual_path}")
            e = matched
        self._f.seek(e.value1)
        return self._f.read(e.value2)

    def extract_all(self, output_dir: str, verbose: bool = True):
        out   = Path(output_dir)
        sys_d = out / "sys"
        fil_d = out / "files"
        sys_d.mkdir(parents=True, exist_ok=True)
        fil_d.mkdir(parents=True, exist_ok=True)

        (sys_d / "boot.bin"     ).write_bytes(self.header.to_bytes())
        (sys_d / "bi2.bin"      ).write_bytes(self.bi2)
        (sys_d / "apploader.img").write_bytes(self.apploader)
        (sys_d / "main.dol"     ).write_bytes(self.dol)
        (sys_d / "fst.bin"      ).write_bytes(self.fst_data)

        total = len(self.list_files())
        done  = 0

        def _extract(e: _FSTEntry, cur_dir: Path):
            nonlocal done
            if e.is_dir:
                sub = (cur_dir / e.name) if e.name else cur_dir
                sub.mkdir(exist_ok=True)
                for child in e.children:
                    _extract(child, sub)
            else:
                dest = cur_dir / e.name
                self._f.seek(e.value1)
                dest.write_bytes(self._f.read(e.value2))
                done += 1
                if verbose:
                    print(f"\r  {done}/{total}  {dest.relative_to(fil_d)}" + " " * 20,
                          end="", flush=True)

        _extract(self.fst_root, fil_d)
        if verbose:
            print()


def patch_iso(base_iso: str, replacements: dict[str, str], output: str,
              file_align: int = _FILE_ALIGN, verbose: bool = True):
    """Patch *base_iso* by replacing / adding files, then write *output*."""
    with tempfile.TemporaryDirectory(prefix="gc_patch_") as tmp:
        tmp_p = Path(tmp)
        if verbose:
            print(f"Extracting {base_iso} ...")
        with GCDisc(base_iso) as disc:
            disc.extract_all(tmp, verbose=False)

        files_p = tmp_p / "files"
        for vpath, src in replacements.items():
            dest = files_p / Path(vpath.replace("/", os.sep))
            dest.parent.mkdir(parents=True, exist_ok=True)
            src_size = os.path.getsize(src)
            if verbose:
                if dest.exists():
                    print(f"  replace {vpath}  ({dest.stat().st_size:,} -> {src_size:,} B)")
                else:
                    print(f"  add     {vpath}  ({src_size:,} B)")
            shutil.copy2(src, dest)

        if verbose:
            print(f"Building {output} ...")
        build_iso(str(tmp_p / "sys"), str(files_p), output, file_align, verbose)
