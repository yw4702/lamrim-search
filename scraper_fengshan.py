#!/usr/bin/env python3
"""Scrape 菩提道次第廣論手抄稿（凤山寺版） from amrtf.org into SQLite."""

from __future__ import annotations

import argparse
import html
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.blisswisdom.org"
INDEX_URL = "https://www.blisswisdom.org/teachings/lamrim2"
DEFAULT_DB = Path(__file__).resolve().parent / "lamrim_fengshan.db"

USER_AGENT = (
    "lamrim-fengshan-scraper/1.0 "
    "(+https://www.blisswisdom.org; educational archiving)"
)

SECTION_MAP = {
    "要旨總說": "道前基礎",
    "皈敬頌": "道前基礎",
    "本論所說法與講說傳規": "道前基礎",
    "造者殊勝": "道前基礎",
    "教授殊勝": "道前基礎",
    "聽聞軌理": "道前基礎",
    "說法軌理": "道前基礎",
    "完結軌理": "道前基礎",
    "親近善士": "道前基礎",
    "修習軌理": "道前基礎",
    "暇滿": "道前基礎",
    "道次引導": "道前基礎",
    "念死無常": "下士道",
    "三惡趣苦": "下士道",
    "皈依三寶": "下士道",
    "深信業果": "下士道",
    "希求解脫": "中士道",
    "思惟苦諦": "中士道",
    "思惟集諦": "中士道",
    "十二緣起": "中士道",
    "中士道之量": "中士道",
    "除邪分別": "中士道",
    "解脫正道": "中士道",
}

def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS lectures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            volume INTEGER NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            wp_post_id INTEGER,
            title TEXT NOT NULL,
            toc_title TEXT,
            section TEXT,
            subsection TEXT,
            duration TEXT,
            url TEXT NOT NULL,
            content_html TEXT,
            content_text TEXT,
            published_at TEXT,
            scraped_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_lectures_volume ON lectures(volume);
        CREATE INDEX IF NOT EXISTS idx_lectures_section ON lectures(section);
        CREATE INDEX IF NOT EXISTS idx_lectures_subsection ON lectures(subsection);
        """
    )
    conn.commit()

def clean_text(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def html_to_text(content_html: str) -> str:
    soup = BeautifulSoup(content_html, "html.parser")
    text = soup.get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text)



def parse_index(index_html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(index_html, "html.parser")

    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]

        if not re.search(r"/teachings/lamrim2/\d+-\d+$", href):
            continue

        url = urljoin(BASE_URL, href)
        slug = url.rstrip("/").split("/")[-1]

        if slug in seen:
            continue

        seen.add(slug)

        title = clean_text(link.get_text(" ", strip=True))
        title = re.sub(r"^[一二三四五六七八九十百\d、.\s]+", "", title).strip()

        number_match = re.search(r"-(\d+)$", slug)
        volume = int(number_match.group(1)) if number_match else len(items) + 1

        section = SECTION_MAP.get(title)

        items.append(
            {
                "volume": volume,
                "slug": slug,
                "title": title or slug,
                "toc_title": title or slug,
                "section": section,
                "subsection": title or None,
                "url": url,
            }
        )

    items.sort(key=lambda item: item["volume"])
    return items


def fetch_index_toc(session: requests.Session) -> dict[str, dict[str, Any]]:
    response = session.get(INDEX_URL, timeout=60)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return parse_index(response.text)


def extract_page_title(soup: BeautifulSoup, fallback: str) -> str:
    h1 = soup.find("h1")
    if h1:
        return clean_text(h1.get_text(" ", strip=True))

    title = soup.find("title")
    if title:
        return clean_text(title.get_text(" ", strip=True)).split("|")[0].strip()

    return fallback


def extract_transcript_html(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")

    content = soup.select_one("section.article-content.lamrimcontent")

    if content is None:
        content = (
            soup.select_one("main")
            or soup.select_one("article")
            or soup.body
        )

    blocks = []

    for element in content.find_all(["p", "h4"], recursive=True):
        text = clean_text(element.get_text(" ", strip=True))

        if not text:
            continue

        time_label = None

        time_span = element.find("span")
        if time_span:
            time_text = clean_text(time_span.get_text(" ", strip=True))
            match = re.search(r"\d{1,2}:\d{2}(?::\d{2})?", time_text)

            if match:
                time_label = match.group(0)

        for span in element.find_all("span"):
            span.decompose()

        inner_text = clean_text(element.get_text(" ", strip=True))

        if not inner_text:
            continue

        time_html = (
            f'<span class="seek-to" data-label="{time_label}"></span>'
            if time_label
            else ""
        )

        if element.name == "h4":
            blocks.append(
                f"<blockquote><p>{time_html}{html.escape(inner_text)}</p></blockquote>"
            )
        else:
            blocks.append(
                f"<p>{time_html}{html.escape(inner_text)}</p>"
            )

    return "\n".join(blocks)


def fetch_page(session: requests.Session, item: dict[str, Any]) -> dict[str, Any]:
    response = session.get(item["url"], timeout=60)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")

    title = extract_page_title(soup, item["title"])
    content_html = extract_transcript_html(response.text)
    content_text = html_to_text(content_html)

    return {
        **item,
        "title": title,
        "content_html": content_html,
        "content_text": content_text,
    }


def upsert_lecture(
    conn: sqlite3.Connection,
    *,
    volume: int,
    slug: str,
    title: str,
    toc_title: str | None,
    section: str | None,
    subsection: str | None,
    url: str,
    content_html: str,
    content_text: str,
    scraped_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO lectures (
            volume, slug, wp_post_id, title, toc_title, section, subsection,
            duration, url, content_html, content_text, published_at, scraped_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            volume = excluded.volume,
            title = excluded.title,
            toc_title = excluded.toc_title,
            section = excluded.section,
            subsection = excluded.subsection,
            url = excluded.url,
            content_html = excluded.content_html,
            content_text = excluded.content_text,
            scraped_at = excluded.scraped_at
        """,
        (
            volume,
            slug,
            None,
            title,
            toc_title,
            section,
            subsection,
            None,
            url,
            content_html,
            content_text,
            None,
            scraped_at,
        ),
    )


def scrape(db_path: Path, delay: float, limit: int | None) -> None:
    session = create_session()
    conn = sqlite3.connect(db_path)
    init_db(conn)

    print("Fetching Fengshan index...")
    posts = fetch_index_toc(session)

    if limit is not None:
        posts = posts[:limit]
    
    print(f"Found {len(posts)} Fengshan sections.")

    scraped_at = datetime.now(timezone.utc).isoformat()
    saved = 0

    for index, post in enumerate(posts, start=1):
        page = fetch_page(session, post)

        upsert_lecture(
            conn,
            volume=page["volume"],
            slug=page["slug"],
            title=page["title"],
            toc_title=page["toc_title"],
            section=page["section"],
            subsection=page["subsection"],
            url=page["url"],
            content_html=page["content_html"],
            content_text=page["content_text"],
            scraped_at=scraped_at,
        )

        conn.commit()
        saved += 1

        print(
            f"[{index}/{len(posts)}] saved "
            f"{page['slug']} | {page['toc_title']} | {len(page['content_text'])} chars"
        )


        if delay and index < len(posts):
            time.sleep(delay)

    count = conn.execute("SELECT COUNT(*) FROM lectures").fetchone()[0]
    conn.close()
    print(f"Done. {saved} lectures saved to {db_path} (total rows: {count}).")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape 凤山寺版《菩提道次第廣論》手抄稿 into SQLite."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"SQLite database path (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay in seconds between requests (default: 0.5)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only scrape the first N lectures (for testing)",
    )
    args = parser.parse_args()

    try:
        scrape(args.db, delay=args.delay, limit=args.limit)
    except requests.RequestException as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - CLI entrypoint
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
