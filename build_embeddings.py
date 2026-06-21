import json
import sqlite3
import time
from openai import OpenAI

DB_PATHS = {
    "南普陀版": "lamrim_nanputuo.db",
    "鳳山寺版": "lamrim_fengshan.db",
}

MODEL = "text-embedding-3-small"
client = OpenAI()

def embed(text: str) -> list[float]:
    response = client.embeddings.create(
        model=MODEL,
        input=text[:3000],
    )
    return response.data[0].embedding

for source, db_path in DB_PATHS.items():
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS paragraph_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                volume INTEGER,
                title TEXT,
                toc_title TEXT,
                section TEXT,
                subsection TEXT,
                url TEXT,
                paragraph TEXT,
                embedding TEXT
            )
        """)

        existing = conn.execute(
            "SELECT COUNT(*) FROM paragraph_embeddings"
        ).fetchone()[0]

        if existing > 0:
            print(f"{source} already has {existing} embeddings, skip.")
            continue

        rows = conn.execute("""
            SELECT volume, title, toc_title, section, subsection, url, content_text
            FROM lectures
            WHERE content_text IS NOT NULL
        """).fetchall()

        for row in rows:
            volume, title, toc_title, section, subsection, url, content_text = row
            paragraphs = [
                p.strip()
                for p in content_text.split("\n")
                if len(p.strip()) >= 30
            ]

            for p in paragraphs:
                vector = embed(p)
                conn.execute("""
                    INSERT INTO paragraph_embeddings
                    (source, volume, title, toc_title, section, subsection, url, paragraph, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    source,
                    volume,
                    title,
                    toc_title,
                    section,
                    subsection,
                    url,
                    p,
                    json.dumps(vector),
                ))

                conn.commit()
                time.sleep(0.05)

        print(f"{source} done.")