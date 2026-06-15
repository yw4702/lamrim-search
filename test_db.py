import sqlite3
import re

conn = sqlite3.connect("lamrim_nanputuo.db")
cur = conn.cursor()

row = cur.execute("""
SELECT content_html
FROM lectures
WHERE volume = 84
""").fetchone()

html = row[0]

print("blockquote count:", html.count("<blockquote"))

conn.close()
