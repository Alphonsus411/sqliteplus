import os
import sys
import sqlite3
import tempfile
import shutil
from pathlib import Path

# Prefer installed package over local sources
cwd = os.getcwd()
if cwd in sys.path:
    sys.path.remove(cwd)

from sqliteplus.utils.replication_sync import SQLiteReplication

tmpdir = tempfile.mkdtemp(prefix="sqliteplus_repl_")
src_db = Path(tmpdir) / "src.db"
target_db = Path(tmpdir) / "copy.db"
backups_dir = Path(tmpdir) / "backups"

try:
    # Create a small source database
    with sqlite3.connect(src_db) as conn:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        conn.executemany("INSERT INTO t (name) VALUES (?)", [("alice",), ("bob",), ("carol",)])
        conn.commit()

    # Run accelerated replication helpers
    repl = SQLiteReplication(db_path=str(src_db), backup_dir=str(backups_dir))
    backup_path = repl.backup_database()
    if not Path(backup_path).exists():
        print("[ERR] backup file not found:", backup_path)
        raise SystemExit(2)

    result_target = repl.replicate_database(str(target_db))
    if not Path(result_target).exists():
        print("[ERR] replicate target not found:", result_target)
        raise SystemExit(2)

    # Check data equality
    with sqlite3.connect(src_db) as c1, sqlite3.connect(target_db) as c2:
        n1 = c1.execute("SELECT COUNT(*) FROM t").fetchone()[0]
        n2 = c2.execute("SELECT COUNT(*) FROM t").fetchone()[0]

    print("rows src:", n1, "rows dst:", n2)
    if n1 != n2 or n1 == 0:
        print("[ERR] row count mismatch")
        raise SystemExit(2)

    print("REPL_OK")
finally:
    # Cleanup
    shutil.rmtree(tmpdir, ignore_errors=True)
