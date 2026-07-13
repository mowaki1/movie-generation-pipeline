import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import feedparser
import psycopg2
from googlenewsdecoder import new_decoderv1

DB_DSN = "dbname=news_pipeline"


def get_sources(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id, source, rss_url FROM m_sources WHERE id != 0")
        return cur.fetchall()


def get_existing_guids(conn, source_id):
    # Google Newsの検索RSSは前回取得分と大きく重複するので、
    # 既知のguidはデコードをスキップして無駄なGoogleへのリクエストを減らす
    # (これをしないと日次バッチのたびに同じ記事を再デコードし、429を誘発しやすくなる)
    with conn.cursor() as cur:
        cur.execute("SELECT rss_guid FROM t_articles WHERE source_id = %s", (source_id,))
        return {row[0] for row in cur.fetchall()}


_google_blocked = False


def resolve_url(url, max_retries=2):
    # Google News RSSの<link>はリダイレクトトークン付きの中間URLなので、
    # 実記事のURLに解決してから保存する(重複除去と後の本文取得を正しく機能させるため)。
    # 単純なHTTPリダイレクト追跡では解決できない(トークンはbase64エンコードされた
    # 内部IDでJS/専用エンドポイント経由のため)、専用ライブラリでデコードする。
    global _google_blocked

    if urlparse(url).hostname != "news.google.com":
        return url

    if _google_blocked:
        # 一度429(レート制限)を検知したら、このプロセス実行中は
        # Google側のブロックが解除されていないとみなし、以降は
        # 待機せず即座にスキップする(1件ごとに待っても無駄なため)
        return None

    for attempt in range(1, max_retries + 1):
        try:
            result = new_decoderv1(url, interval=2)
            if result.get("status"):
                return result["decoded_url"]
            message = result.get("message", "")
            if "429" in str(message):
                if attempt < max_retries:
                    wait = 10 * attempt
                    print(f"    WARNING: rate limited, retrying in {wait}s ({attempt}/{max_retries})")
                    time.sleep(wait)
                    continue
                print("    WARNING: still rate limited, skipping remaining Google News decodes for this run")
                _google_blocked = True
                return None
            print(f"    WARNING: failed to decode {url}: {message}")
            return None
        except Exception as e:
            if "429" in str(e):
                if attempt < max_retries:
                    wait = 10 * attempt
                    print(f"    WARNING: rate limited, retrying in {wait}s ({attempt}/{max_retries})")
                    time.sleep(wait)
                    continue
                print("    WARNING: still rate limited, skipping remaining Google News decodes for this run")
                _google_blocked = True
                return None
            print(f"    WARNING: failed to decode {url}: {e}")
            return None
    return None


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

    existing_guids = get_existing_guids(conn, source_id)

    inserted = 0
    skipped_decode_failures = 0
    with conn.cursor() as cur:
        for entry in feed.entries:
            guid = entry.get("id") or entry.get("guid") or entry.get("link")
            raw_url = entry.get("link")
            title = entry.get("title", "").strip()
            summary = entry.get("summary", "")
            published = parse_published(entry)
            category = entry.get("category")

            if not raw_url or not title:
                continue
            if guid in existing_guids:
                continue

            url = resolve_url(raw_url)
            if url is None:
                # デコードに失敗した記事はスキップする(未挿入のままにしておけば
                # 次回のバッチ実行時にあらためて解決を試みられる)
                skipped_decode_failures += 1
                continue

            cur.execute(
                """
                INSERT INTO t_articles
                    (source_id, rss_guid, title, url, published_at, rss_summary, category, status_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
                ON CONFLICT DO NOTHING
                """,
                (source_id, guid, title, url, published, summary, category),
            )
            if cur.rowcount > 0:
                inserted += 1

    conn.commit()
    print(f"  inserted: {inserted} / {len(feed.entries)} (decode failures skipped: {skipped_decode_failures})")
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
