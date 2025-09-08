#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified CLI for "rename" (flatten with underscores) and "repack" (restore paths)
Refactored from the original rename.py and repack.py without changing core logic.

- Subcommands:
  * rename: replicate original rename.py behavior (using .rename_lib)
  * repack: replicate original repack.py behavior (classic or using .rename_lib)

Notes on behavior preservation:
- The core renaming/restoring algorithms are kept intact, including the quirky path handling.
- For "rename", the head offset logic defaults to 2 when root is ".", matching original behavior.
- For "repack", if .rename_lib is missing, fallback to classic underscore-based restore.
- We removed interactive pauses by default; optional flags are provided to preserve cleanup behaviors.
"""

import argparse
import json
import os
import sys
from typing import Dict, Optional

from loguru import logger


def setup_logging():
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{message}")


def _rename_walk(dir_path: str, head: int, floor: int, library: Dict[str, str]) -> None:
    entries = os.scandir(dir_path)
    for entry in entries:
        if entry.is_file():
            new_name = entry.path[:head] + entry.path[head:].replace("\\", "_").replace(
                "/", "_"
            )
            if new_name != entry.path:
                if not os.path.exists(new_name):
                    if entry.path in library:
                        logger.info("File %s has been renamed. Skipped." % (entry.path))
                    else:
                        logger.info("Rename %s to %s." % (entry.path, new_name))
                        os.rename(entry.path, new_name)
                        library[new_name] = entry.path
                else:
                    logger.info("File %s has existed. Skipped." % new_name)
        else:
            # Preserve original recursion and path concatenation with backslash
            subdir = dir_path + "\\" + entry.name
            _rename_walk(
                subdir,
                head + (len(entry.name) + 1 if floor > 0 else 0),
                floor - 1,
                library,
            )
            if floor <= 0:
                try:
                    os.rmdir(entry.path)
                except Exception:
                    pass


def cmd_rename(root: str, floor: int, lib_path: str) -> None:
    root_abs = os.path.abspath(root)
    lib_abs = os.path.abspath(lib_path)

    try:
        with open(lib_abs, "r", encoding="utf-8") as f:
            library = json.load(f)
        logger.info("Found rename library.")
    except Exception:
        logger.info("Create a new rename library.")
        library = dict()

    old_cwd = os.getcwd()
    try:
        os.chdir(root_abs)
        head = 2
        _rename_walk(".", head, floor, library)
    finally:
        os.chdir(old_cwd)

    with open(lib_abs, "w", encoding="utf-8") as f:
        json.dump(library, f, ensure_ascii=False)


def cmd_repack(root: str, lib_path: str, keep_lib: bool) -> None:
    root_abs = os.path.abspath(root)
    lib_abs = os.path.abspath(lib_path)

    old_cwd = os.getcwd()
    try:
        os.chdir(root_abs)

        library: Optional[Dict[str, str]] = None
        try:
            with open(lib_abs, "r", encoding="utf-8") as f:
                library = json.load(f)
            logger.info("Found rename library.")
        except Exception:
            library = None
            logger.info("Library not found. Fallback to classic methods.")

        entries = os.scandir(".")
        for entry in entries:
            if entry.is_file():
                new_path = entry.path

                if library is None:
                    nlist = list(new_path)
                    if new_path.rfind("_") == -1 and new_path.rfind("-U") == -1:
                        continue
                    if new_path.rfind("_") != -1:
                        nlist[new_path.rfind("_")] = "\\"
                    new_path = "".join(nlist)
                    new_path = new_path.replace("_", "/").replace("-U", "_")
                else:
                    if entry.path in library:
                        new_path = library[entry.path]
                    else:
                        logger.info(f"{entry.path} not in library file. Skip.")

                logger.info("Rename %s to %s" % (entry.path, new_path))

                if entry.path.rfind("_") != -1:
                    if not os.path.exists(new_path[0 : new_path.rfind("\\")]):
                        os.makedirs(new_path[0 : new_path.rfind("\\")])

                if not os.path.exists(new_path):
                    os.rename(entry.path, new_path)
                else:
                    logger.info("File %s has existed. Skip." % new_path)
    finally:
        os.chdir(old_cwd)

    if not keep_lib:
        try:
            os.remove(lib_abs)
        except Exception:
            pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Image unfolder script: rename (flatten) and repack (restore) utilities."
    )
    sub = p.add_subparsers(dest="command", required=True)

    pr = sub.add_parser(
        "rename",
        help="Flatten file paths into underscores; records mapping in .rename_lib.",
    )
    pr.add_argument(
        "--dir",
        default=".",
        help="Root directory to process. Default: current directory (.)",
    )
    pr.add_argument(
        "--floor",
        type=int,
        default=0,
        help="Number of top levels to keep before flattening. Default: 0",
    )
    pr.add_argument(
        "--lib",
        default=None,
        help="Path to rename library file. Default: <dir>/.rename_lib",
    )

    pp = sub.add_parser(
        "repack",
        help="Restore file paths using .rename_lib or classic underscore-based method.",
    )
    pp.add_argument(
        "--dir",
        default=".",
        help="Root directory to process. Default: current directory (.)",
    )
    pp.add_argument(
        "--lib",
        default=None,
        help="Path to rename library file. Default: <dir>/.rename_lib",
    )
    pp.add_argument(
        "--keep-lib",
        action="store_true",
        help="Keep the rename library after repack (original repack.py removed it). Default: remove.",
    )

    return p


def main(argv=None):
    setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "rename":
        lib_path = args.lib if args.lib else os.path.join(args.dir, ".rename_lib")
        cmd_rename(root=args.dir, floor=args.floor, lib_path=lib_path)
    elif args.command == "repack":
        lib_path = args.lib if args.lib else os.path.join(args.dir, ".rename_lib")
        cmd_repack(root=args.dir, lib_path=lib_path, keep_lib=args.keep_lib)
    else:
        parser.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
