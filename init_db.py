# init_db.py

import sqlite3, sys
DB = "hotchkiss_content.db"

schema = """
CREATE TABLE IF NOT EXISTS pages(
  url        TEXT PRIMARY KEY,
  title      TEXT,
  markdown   TEXT,
  url   TEXT,
  crawled_at INTEGER
);"""

conn = sqlite3.connect(DB)
conn.executescript(schema)
conn.close()
print(f"📚 SQLite DB ready → {DB}")