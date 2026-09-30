#!/usr/bin/env python3
"""Prepare data/todo and link Garden's shared data directory to this checkout."""

import argparse
import os
from pathlib import Path
import sys

from link_codex_agents import LinkError, is_garden, repository_root


def shared_todo_paths(root):
    source = root / "data"
    for directory, boundary in ((source, root), (source / "todo", source.resolve())):
        if os.path.lexists(directory) and (
            not directory.is_dir() or not directory.resolve().is_relative_to(boundary)
        ):
            raise LinkError(f"Garden data paths are not a directory or are outside their storage: {directory}")
    destination = Path.home() / ".local/share/garden"
    if destination.is_symlink() and destination.resolve() == source.resolve():
        return source, destination
    if os.path.lexists(destination):
        raise LinkError(f"Destination already exists; left unchanged: {destination}")
    for parent in destination.parents:
        if os.path.lexists(parent) and not parent.is_dir():
            raise LinkError(f"Parent is not a directory; left unchanged: {parent}")
    return source, destination


def link_shared_todo(root, dry_run=False):
    source, destination = shared_todo_paths(root)
    if dry_run:
        for directory in (source, source / "todo"):
            if not directory.exists():
                print(f"Would create directory: {directory}")
    else:
        (source / "todo").mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        print(f"OK: Link already points to {source}")
    elif dry_run:
        print(f"Would link: {destination} -> {source}")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(source, target_is_directory=True)
        print(f"OK: {destination} -> {source}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        root = repository_root(args.repository)
        if not is_garden(root):
            raise LinkError("The repository's origin is not Olbbemi/Garden on GitHub.")
        link_shared_todo(root, dry_run=args.dry_run)
    except (LinkError, OSError, RuntimeError) as error:
        print(f"Garden todo link: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
