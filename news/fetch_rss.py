import time
from datetime import datetime, timezone

import feedparser
import psycopg2

DB_DSN = "dbname=news_pipeline"


def get_sources(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id, source, rss_url FROM m_sources WHERE id != 0")
        return cur.fetchall()


def parse_published(entry):
    if getattr(entry, "published_parsed", None):
        return datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
    return None


def fetch_source(conn, source_id, source_name, rss_url):
    print(f"fetching: {source_name} ({rss_url})")
    feed = feedparser.parse(rss_url)

    if feed.bozo and not feed.entries:
        print(f"  ERROR: failed to parse feed: {feed.bozo_exception}")
        return 0

    inserted = 0
    with conn.cursor() as cur:
        for entry in feed.entries:
            guid = entry.get("id") or entry.get("guid") or entry.get("link")
            url = entry.get("link")
            title = entry.get("title", "").strip()
            summary = entry.get("summary", "")
            published = parse_published(entry)

            if not url or not title:
                continue

            cur.execute(
                """
                INSERT INTO t_articles
                    (source_id, rss_guid, title, url, published_at, rss_summary, status_id)
                VALUES (%s, %s, %s, %s, %s, %s, 1)
                ON CONFLICT (url) DO NOTHING
                """,
                (source_id, guid, title, url, published, summary),
            )
            if cur.rowcount > 0:
                inserted += 1

    conn.commit()
    print(f"  inserted: {inserted} / {len(feed.entries)}")
    return inserted


def main():
    conn = psycopg2.connect(DB_DSN)
    sources = get_sources(conn)

    total = 0
    for source_id, source_name, rss_url in sources:
        try:
            total += fetch_source(conn, source_id, source_name, rss_url)
        except Exception as e:
            print(f"  ERROR fetching {source_name}: {e}")

    print(f"done: {total} new articles inserted")
    conn.close()


if __name__ == "__main__":
    main()
