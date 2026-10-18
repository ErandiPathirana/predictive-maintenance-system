"""Prints rows of the predictions table as JSON (used by the browser tests to read the database without any app code).
   python db_query.py <db file> [where-clause] -> JSON list"""
import json, sys
from harness import db_rows, decode_row
db = sys.argv[1]; where = sys.argv[2] if len(sys.argv) > 2 else "1=1"
print(json.dumps([decode_row(r) for r in db_rows(db, where)], default=str))
