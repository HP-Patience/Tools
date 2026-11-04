"""Atomically replace the release symlink, without deleting directories."""

from pathlib import Path
import os, re, sys

root = Path(sys.argv[1]).resolve()
sha = sys.argv[2]
if not re.fullmatch(r"[a-f0-9]{40}", sha):
    raise ValueError("invalid SHA")
release = (root / "releases" / sha).resolve()
if release.parent != (root / "releases").resolve() or not release.is_dir():
    raise ValueError("invalid release path")
current = root / "current"
temporary = root / "current.next"
if current.exists() and not current.is_symlink():
    raise ValueError("current must be a symlink")
if temporary.is_symlink():
    temporary.unlink()
elif temporary.exists():
    raise ValueError("temporary link path is occupied")
temporary.symlink_to(release, target_is_directory=True)
os.replace(temporary, current)
