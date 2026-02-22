import os
import sys

cwd = os.getcwd()
if cwd in sys.path:
    sys.path.remove(cwd)

import sqliteplus
from sqliteplus.core import schemas
import sqliteplus.core.schemas_cy as scy
from sqliteplus.utils import replication_sync as repl

print("schemas module:", schemas.__name__, getattr(schemas, "__file__", None))
print("schemas_cy file:", getattr(scy, "__file__", None))
print("replication_sync file:", getattr(repl, "__file__", None))
print("OK")
