#!/usr/bin/env python3
"""Scrape 菩提道次第廣論手抄稿（南普陀版） from amrtf.org into SQLite."""

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

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.amrtf.org/zh-hant"
INDEX_URL = f"{BASE_URL}/lamrim-transcripts-nanputuo/"
API_URL = f"{BASE_URL}/wp-json/wp/v2/posts"
CATEGORY_ID = 961
DEFAULT_DB = Path(__file__).resolve().parent / "lamrim_nanputuo.db"
USER_AGENT = (
    "lamrim-nanputuo-scraper/1.0 (+https://www.amrtf.org; educational archiving)"
)


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
        """
    )
    conn.commit()


def html_to_text(content_html: str) -> str:
    soup = BeautifulSoup(content_html, "html.parser")
    text = soup.get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text)


def parse_index_toc(index_html: str) -> dict[str, dict[str, Any]]:
    match = re.search(
        r'id="accordionIndex_toc"(.*?)id="accordionIndex_volume"',
        index_html,
        re.S,
    )
    if not match:
        raise RuntimeError("Could not find catalog TOC on index page")

    chunk = match.group(1)
    entries: list[dict[str, Any]] = []
    current_section: str | None = None
    current_subsection: str | None = None

    parts = re.split(
        r"(<button class=\"book-title[^>]*>.*?</button>|<div class=\"chapter-title\">.*?</div>)",
        chunk,
        flags=re.S,
    )
    item_pattern = re.compile(
        r'<li class="list-group-item" data-volume="(\d+)">.*?'
        r'href="(/zh-hant/lamrim-transcripts-nanputuo-\d+)[^"]*".*?'
        r'volume-item-title[^>]*>(.*?)</div>.*?'
        r'fa-headphones-alt[^>]*></i>([^<]*)',
        re.S,
    )

    for part in parts:
        if "book-title" in part:
            current_section = html.unescape(re.sub(r"<[^>]+>", "", part).strip()) or None
            current_subsection = None
            continue
        if "chapter-title" in part:
            current_subsection = html.unescape(re.sub(r"<[^>]+>", "", part).strip()) or None
            continue

        for volume, href, title, duration in item_pattern.findall(part):
            slug = href.rstrip("/").split("/")[-1]
            entries.append(
                {
                    "volume": int(volume),
                    "slug": slug,
                    "section": current_section,
                    "subsection": current_subsection,
                    "toc_title": html.unescape(re.sub(r"<[^>]+>", "", title).strip()),
                    "duration": duration.strip(),
                }
            )

    by_slug: dict[str, dict[str, Any]] = {}
    for entry in entries:
        slug = entry["slug"]
        existing = by_slug.get(slug)
        if existing is None:
            by_slug[slug] = entry
            continue
        # Prefer entries with subsection metadata, otherwise keep the latest one.
        if entry.get("subsection") and not existing.get("subsection"):
            by_slug[slug] = entry
        else:
            by_slug[slug] = entry

    return by_slug


def fetch_index_toc(session: requests.Session) -> dict[str, dict[str, Any]]:
    response = session.get(INDEX_URL, timeout=60)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return parse_index_toc(response.text)


def fetch_all_posts(session: requests.Session, delay: float) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    page = 1
    per_page = 100

    while True:
        response = session.get(
            API_URL,
            params={
                "categories": CATEGORY_ID,
                "per_page": per_page,
                "page": page,
                "_fields": "id,slug,title,content,link,date",
            },
            timeout=60,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        posts.extend(batch)

        total_pages = int(response.headers.get("X-WP-TotalPages", page))
        print(f"Fetched API page {page}/{total_pages} ({len(batch)} posts)")
        if page >= total_pages:
            break
        page += 1
        if delay:
            time.sleep(delay)

    posts.sort(key=lambda item: int(item["slug"].rsplit("-", 1)[-1]))
    return posts


def upsert_lecture(
    conn: sqlite3.Connection,
    *,
    volume: int,
    slug: str,
    wp_post_id: int,
    title: str,
    toc_title: str | None,
    section: str | None,
    subsection: str | None,
    duration: str | None,
    url: str,
    content_html: str,
    content_text: str,
    published_at: str | None,
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
            wp_post_id = excluded.wp_post_id,
            title = excluded.title,
            toc_title = excluded.toc_title,
            section = excluded.section,
            subsection = excluded.subsection,
            duration = excluded.duration,
            url = excluded.url,
            content_html = excluded.content_html,
            content_text = excluded.content_text,
            published_at = excluded.published_at,
            scraped_at = excluded.scraped_at
        """,
        (
            volume,
            slug,
            wp_post_id,
            title,
            toc_title,
            section,
            subsection,
            duration,
            url,
            content_html,
            content_text,
            published_at,
            scraped_at,
        ),
    )

def fetch_page_content(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=60)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")

    content = (
        soup.select_one(".entry-content")
        or soup.select_one("article")
        or soup.select_one("main")
    )

    return str(content) if content else ""


def scrape(db_path: Path, delay: float, limit: int | None) -> None:
    session = create_session()
    conn = sqlite3.connect(db_path)
    init_db(conn)

    print("Fetching index TOC metadata...")
    toc_by_slug = fetch_index_toc(session)

    print("Fetching lecture list from WordPress API...")
    posts = fetch_all_posts(session, delay=0.0)
    if limit is not None:
        posts = posts[:limit]

    scraped_at = datetime.now(timezone.utc).isoformat()
    saved = 0

    for index, post in enumerate(posts, start=1):
        slug = post["slug"]
        volume = int(slug.rsplit("-", 1)[-1])
        title = html.unescape(post["title"]["rendered"])
        content_html = fetch_page_content(session, post["link"])
        content_text = html_to_text(content_html)
        toc = toc_by_slug.get(slug, {})

        upsert_lecture(
            conn,
            volume=volume,
            slug=slug,
            wp_post_id=post["id"],
            title=title,
            toc_title=toc.get("toc_title"),
            section=toc.get("section"),
            subsection=toc.get("subsection"),
            duration=toc.get("duration"),
            url=post["link"],
            content_html=content_html,
            content_text=content_text,
            published_at=post.get("date"),
            scraped_at=scraped_at,
        )
        saved += 1
        print(f"[{index}/{len(posts)}] saved {slug} ({title})")

        if delay and index < len(posts):
            time.sleep(delay)

    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM lectures").fetchone()[0]
    conn.close()
    print(f"Done. {saved} lectures saved to {db_path} (total rows: {count}).")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape 南普陀版《菩提道次第廣論》手抄稿 into SQLite."
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
