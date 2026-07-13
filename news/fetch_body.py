import psycopg2
import requests
import trafilatura
from charset_normalizer import from_bytes

DB_DSN = "dbname=news_pipeline"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 15


def get_pending_articles(conn, limit):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, url FROM t_articles WHERE status_id = 1 ORDER BY id LIMIT %s",
            (limit,),
        )
        return cur.fetchall()


def fetch_html(url):
    # requestsで取得し、charset_normalizerで文字化けを防ぐ(サイトが宣言する
    # エンコーディングが実際のバイト列と一致しないケースがあるため)。
    # requestsが失敗した場合はtrafilatura自身の取得ロジックにフォールバックする。
    res = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    res.raise_for_status()
    return str(from_bytes(res.content).best())


def update_status(conn, article_id, status_id, body=None):
    with conn.cursor() as cur:
        if body is not None:
            cur.execute(
                "UPDATE t_articles SET status_id = %s, body = %s WHERE id = %s",
                (status_id, body, article_id),
            )
        else:
            cur.execute(
                "UPDATE t_articles SET status_id = %s WHERE id = %s",
                (status_id, article_id),
            )
    conn.commit()


def process_article(conn, article_id, url):
    print(f"fetching body: id={article_id} {url}")

    html = None
    try:
        html = fetch_html(url)
    except requests.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else None
        if status_code in (401, 403):
            print(f"  ACCESS DENIED ({status_code})")
            update_status(conn, article_id, 4)
            return
        print(f"  WARNING: requests failed ({e}), falling back to trafilatura fetch")
    except requests.RequestException as e:
        print(f"  WARNING: requests failed ({e}), falling back to trafilatura fetch")

    if html is None:
        html = trafilatura.fetch_url(url)

    if html is None:
        print("  ERROR: could not fetch page (connection error/timeout)")
        update_status(conn, article_id, 5)
        return

    body = trafilatura.extract(html, include_comments=False, include_tables=False)

    if not body:
        print("  WARNING: no article text extracted")
        update_status(conn, article_id, 3)
        return

    update_status(conn, article_id, 2, body=body)
    print(f"  ok: {len(body)} chars")


def main(limit=200):
    conn = psycopg2.connect(DB_DSN)
    articles = get_pending_articles(conn, limit)

    for article_id, url in articles:
        try:
            process_article(conn, article_id, url)
        except Exception as e:
            print(f"  ERROR processing id={article_id}: {e}")
            update_status(conn, article_id, 5)

    print(f"done: {len(articles)} articles processed")
    conn.close()


if __name__ == "__main__":
    main()
