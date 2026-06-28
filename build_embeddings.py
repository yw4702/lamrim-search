import os
import pickle
import sqlite3

import faiss
import numpy as np
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer

DB_SOURCES = {
    "南普陀版": "lamrim_nanputuo.db",
    "鳳山寺版": "lamrim_fengshan.db",
}

OUT_DIR = "embeddings"
MODEL_NAME = "BAAI/bge-m3"

WINDOW_SIZE = 3      # 每次合并 3 段
WINDOW_STEP = 1      # 每次往后滑 1 段
MIN_CHARS = 50       # 太短的段落不要
MAX_CHARS = 900      # 太长会影响 embedding 质量


def split_paragraphs(content_html: str) -> list[str]:
    soup = BeautifulSoup(content_html or "", "html.parser")

    paragraphs = []

    for el in soup.find_all(["p", "blockquote", "h4"]):
        if el.name == "p" and el.find_parent("blockquote"):
            continue

        text = el.get_text(" ", strip=True)
        text = " ".join(text.split())

        if len(text) >= MIN_CHARS:
            paragraphs.append(text)

    return paragraphs


def build_windows(paragraphs: list[str]) -> list[dict]:
    windows = []

    for start in range(0, len(paragraphs), WINDOW_STEP):
        chunk_parts = paragraphs[start : start + WINDOW_SIZE]

        if not chunk_parts:
            continue

        chunk_text = "\n".join(chunk_parts)

        if len(chunk_text) > MAX_CHARS:
            chunk_text = chunk_text[:MAX_CHARS]

        if len(chunk_text) < MIN_CHARS:
            continue

        windows.append(
            {
                "paragraph": chunk_parts[0],
                "context": chunk_text,
                "start_index": start,
            }
        )

    return windows


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    texts = []
    metadata = []

    for source_name, db_path in DB_SOURCES.items():
        if not os.path.exists(db_path):
            print(f"skip missing db: {db_path}")
            continue

        print(f"Reading {source_name}: {db_path}")

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT volume, title, toc_title, section, subsection, url, content_html
                FROM lectures
                WHERE content_html IS NOT NULL
                """
            ).fetchall()

        for row in rows:
            paragraphs = split_paragraphs(row["content_html"])
            windows = build_windows(paragraphs)

            for window in windows:
                texts.append(window["context"])

                metadata.append(
                    {
                        "source": source_name,
                        "volume": row["volume"],
                        "title": row["title"],
                        "toc_title": row["toc_title"],
                        "section": row["section"],
                        "subsection": row["subsection"],
                        "url": row["url"],
                        "paragraph": window["paragraph"],
                        "context": window["context"],
                        "start_index": window["start_index"],
                    }
                )

    print(f"Total semantic chunks: {len(texts)}")

    vectors = model.encode(
        texts,
        batch_size=16,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    vectors = np.array(vectors, dtype="float32")

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    faiss.write_index(index, f"{OUT_DIR}/lamrim.faiss")

    with open(f"{OUT_DIR}/metadata.pkl", "wb") as f:
        pickle.dump(metadata, f)

    print("Done.")
    print(f"Saved index: {OUT_DIR}/lamrim.faiss")
    print(f"Saved metadata: {OUT_DIR}/metadata.pkl")


if __name__ == "__main__":
    main()