#!/usr/bin/env python3
"""Link a Garden checkout's global/AGENTS.md into Codex home."""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys


GARDEN_URL = re.compile(
    r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
    r"Olbbemi/Garden(?:\.git)?/?", re.IGNORECASE
)


class LinkError(Exception):
    pass


def git(*args, cwd=None, optional=False):
    result = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True)
    if optional and result.returncode == 1:
        return None
    if result.returncode:
        raise LinkError(result.stderr.strip() or "Git command failed.")
    return result.stdout.rstrip("\n")


def repository_root(directory):
    return Path(git("rev-parse", "--show-toplevel", cwd=directory)).resolve()


def is_garden(root):
    # Read the configured URL, before Git's insteadOf transport rewriting.
    url = git("config", "--local", "--get", "remote.origin.url", cwd=root, optional=True)
    return url is not None and GARDEN_URL.fullmatch(url) is not None


def codex_directory():
    value = os.environ.get("CODEX_HOME")
    if value is None:
        return Path.home() / ".codex"
    path = Path(value)
    if not value or not path.is_absolute():
        raise LinkError("CODEX_HOME must be a nonempty absolute path.")
    return path


def link_instructions(root):
    source = root / "global/AGENTS.md"
    if not source.is_file() or not source.resolve().is_relative_to(root):
        raise LinkError(f"Garden instructions are missing or outside the repository: {source}")
    destination = codex_directory() / "AGENTS.md"
    if destination.is_symlink() and destination.resolve() == source.resolve():
        print(f"OK: Link already points to {source}")
    elif os.path.lexists(destination):
        raise LinkError(f"Destination already exists; left unchanged: {destination}")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        # symlink() fails if another process creates the destination in the meantime.
        destination.symlink_to(source)
        print(f"OK: {destination} -> {source}")
    override = destination.parent / "AGENTS.override.md"
    if override.is_file() and override.stat().st_size:
        print(f"NOTE: Codex uses {override} before AGENTS.md.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    args = parser.parse_args()
    try:
        root = repository_root(args.repository)
        if not is_garden(root):
            raise LinkError("The repository's origin is not Olbbemi/Garden on GitHub.")
        link_instructions(root)
    except (LinkError, OSError, RuntimeError) as error:
        print(f"Garden Codex link: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
