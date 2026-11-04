"""Consistent SQLite backup. Run with the deployed virtualenv; no DB credentials printed."""

import argparse, sqlite3
from pathlib import Path
from datetime import datetime, timezone

p = argparse.ArgumentParser()
p.add_argument("database")
p.add_argument("directory")
p.add_argument("--keep", type=int, default=14)
a = p.parse_args()
source = Path(a.database).resolve()
if not source.is_file():
    p.error("source database does not exist")
folder = Path(a.directory).resolve()
folder.mkdir(parents=True, exist_ok=True)
if a.keep < 1:
    p.error("keep must be positive")
target = folder / (
    "subscription-"
    + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    + ".sqlite3"
)
with (
    sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True) as db,
    sqlite3.connect(target) as out,
):
    db.backup(out)
    if out.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RuntimeError("invalid backup")
for old in sorted(folder.glob("subscription-*.sqlite3"), reverse=True)[a.keep :]:
    if old.parent.resolve() != folder:
        raise RuntimeError("invalid backup path")
    old.unlink()
print(target.name)
