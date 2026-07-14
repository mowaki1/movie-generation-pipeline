import psycopg2
import requests

DB_DSN = "dbname=news_pipeline"

MODEL = "gemma4:31b-it-bf16"
API_URL = "http://localhost:11434/api/generate"

BODY_CHARS_LIMIT = 3000

PROMPT_TEMPLATE = """以下はニュース記事のタイトルと本文です。
この記事の要点を日本語で200〜400字程度に要約してください。

固有名詞・数値・日付など具体的な事実は省略せず残してください。
前置きや見出し(「要約:」等)は不要です。要約文のみを出力してください。

タイトル:
{title}

本文:
{body}
"""


def build_prompt(title, body):
    return PROMPT_TEMPLATE.format(title=title, body=body[:BODY_CHARS_LIMIT])


def ask_summary(title, body):
    payload = {
        "model": MODEL,
        "prompt": build_prompt(title, body),
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.3,
            "top_p": 0.9,
            "num_ctx": 8192,
            "num_predict": 800,
        },
    }
    res = requests.post(API_URL, json=payload, timeout=300)
    res.raise_for_status()
    data = res.json()
    if "error" in data:
        raise RuntimeError(data["error"])

    text = data.get("response", "").strip()
    if not text:
        raise RuntimeError(
            f"empty response, done_reason={data.get('done_reason')!r}, "
            f"eval_count={data.get('eval_count')}"
        )
    return text


def get_pending_articles(conn, limit):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, body FROM t_articles WHERE status_id = 7 ORDER BY id LIMIT %s",
            (limit,),
        )
        return cur.fetchall()


def save_summary(conn, article_id, summary):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE t_articles SET summary = %s, status_id = 8 WHERE id = %s",
            (summary, article_id),
        )
    conn.commit()


def main(limit=200):
    conn = psycopg2.connect(DB_DSN)
    articles = get_pending_articles(conn, limit)

    summarized = 0
    for article_id, title, body in articles:
        print(f"summarizing: id={article_id} {title[:60]}")
        try:
            summary = ask_summary(title, body or "")
            save_summary(conn, article_id, summary)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        print(f"  ok: {len(summary)} chars")
        summarized += 1

    print(f"done: {summarized} / {len(articles)} articles summarized")
    conn.close()


if __name__ == "__main__":
    main()
