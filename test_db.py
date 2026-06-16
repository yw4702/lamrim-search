import sqlite3
import re

conn = sqlite3.connect("lamrim_fengshan.db")
cur = conn.cursor()

row = cur.execute("""
SELECT content_html
FROM lectures
WHERE volume = 5
""").fetchone()

print(row[0][0:10000])
