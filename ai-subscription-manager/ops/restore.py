"""Restore to a NEW test path. Does not overwrite an existing production database."""

import argparse, sqlite3
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("backup")
p.add_argument("new_database")
a = p.parse_args()
source = Path(a.backup).resolve()
target = Path(a.new_database).resolve()
if not source.is_file():
    p.error("backup not found")
if target.exists():
    p.error("target exists; refusing to overwrite")
target.parent.mkdir(parents=True, exist_ok=True)
with (
    sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True) as original,
    sqlite3.connect(target) as out,
):
    original.backup(out)
    if out.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RuntimeError("invalid restore")
print("Restore verified at new target")
