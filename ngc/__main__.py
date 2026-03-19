"""CLI entry point: python -m ngc <command> ..."""

import argparse
from .core import GCDisc, build_iso, patch_iso


def _cmd_list(args):
    with GCDisc(args.iso) as d:
        print(f"{d.header.game_id}  {d.header.title}")
        for f in d.list_files():
            print(f"  {f}")


def _cmd_extract(args):
    with GCDisc(args.iso) as d:
        print(f"Extracting {d.header.game_id} ...")
        d.extract_all(args.output, verbose=not args.quiet)
    print("Done.")


def _cmd_pack(args):
    build_iso(args.sys_dir, args.files_dir, args.output,
              file_align=int(args.align, 0), verbose=not args.quiet)
    print("Done.")


def _cmd_patch(args):
    reps: dict[str, str] = {}
    for r in (args.replace or []):
        iso_path, _, local_path = r.partition("=")
        reps[iso_path.strip()] = local_path.strip()
    patch_iso(args.iso, reps, args.output,
              file_align=int(args.align, 0), verbose=not args.quiet)
    print("Done.")


def main():
    p = argparse.ArgumentParser(prog="ngc",
                                description="GameCube ISO tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list", help="List files in a GC ISO")
    s.add_argument("iso")

    s = sub.add_parser("extract", help="Extract a GC ISO")
    s.add_argument("iso"); s.add_argument("output")
    s.add_argument("-q", "--quiet", action="store_true")

    s = sub.add_parser("pack", help="Build a GC ISO from sys/ + files/")
    s.add_argument("sys_dir"); s.add_argument("files_dir"); s.add_argument("output")
    s.add_argument("-a", "--align", default="0x20")
    s.add_argument("-q", "--quiet", action="store_true")

    s = sub.add_parser("patch", help="Patch specific files in a GC ISO")
    s.add_argument("iso"); s.add_argument("output")
    s.add_argument("-r", "--replace", action="append", metavar="ISO_PATH=LOCAL_PATH")
    s.add_argument("-a", "--align", default="0x20")
    s.add_argument("-q", "--quiet", action="store_true")

    args = p.parse_args()
    {"list": _cmd_list, "extract": _cmd_extract,
     "pack": _cmd_pack, "patch": _cmd_patch}[args.cmd](args)


if __name__ == "__main__":
    main()
