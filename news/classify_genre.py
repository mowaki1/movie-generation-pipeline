import re

import psycopg2
import requests

DB_DSN = "dbname=news_pipeline"

MODEL = "gemma4:31b-it-bf16"
API_URL = "http://localhost:11434/api/generate"

GENRES = {
    0: "未分類",
    1: "AIニュース",
    2: "ITニュース",
    3: "GPUニュース",
    4: "金融ニュース",
    5: "地政学ニュース",
    6: "科学ニュース",
    7: "医療ニュース",
    8: "Linuxニュース",
    9: "セキュリティニュース",
    9999: "その他のニュース",
}

BODY_CHARS_LIMIT = 2000

PROMPT_TEMPLATE = """以下はニュース記事のタイトルと本文です。
この記事が次のどのジャンルに最も当てはまるか、番号のみで答えてください。

{genre_list}

複数のジャンルに該当しそうな場合は、記事の中心的な話題に最も近いものを1つ選んでください。
どれにも当てはまらない場合は9999を選んでください。

タイトル:
{title}

本文:
{body}

出力形式: 番号のみを1つ出力してください(説明文は不要です)。
"""


def build_prompt(title, body):
    genre_list = "\n".join(f"{gid}: {name}" for gid, name in GENRES.items())
    return PROMPT_TEMPLATE.format(
        genre_list=genre_list,
        title=title,
        body=body[:BODY_CHARS_LIMIT],
    )


def ask_genre(title, body):
    payload = {
        "model": MODEL,
        "prompt": build_prompt(title, body),
        "stream": False,
        "options": {
            "temperature": 0.0,
            "top_p": 0.9,
            "num_ctx": 8192,
            "num_predict": 64,
        },
    }
    res = requests.post(API_URL, json=payload, timeout=300)
    res.raise_for_status()
    data = res.json()
    if "error" in data:
        print(f"  DEBUG: Ollama returned an error: {data['error']!r}")
        return None
    text = data.get("response", "").strip()

    match = re.search(r"\d+", text)
    if not match:
        print(
            f"  DEBUG: raw response was: {text!r}, "
            f"done_reason={data.get('done_reason')!r}, "
            f"eval_count={data.get('eval_count')}, "
            f"prompt_eval_count={data.get('prompt_eval_count')}"
        )
        return None

    genre_id = int(match.group())
    if genre_id not in GENRES:
        print(f"  DEBUG: parsed number {genre_id} is not a valid genre id, raw response was: {text!r}")
    return genre_id if genre_id in GENRES else None


def get_pending_articles(conn, limit):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, body FROM t_articles WHERE status_id = 2 ORDER BY id LIMIT %s",
            (limit,),
        )
        return cur.fetchall()


def update_genre(conn, article_id, genre_id):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE t_articles SET genre_id = %s, status_id = 6 WHERE id = %s",
            (genre_id, article_id),
        )
    conn.commit()


def main(limit=200):
    conn = psycopg2.connect(DB_DSN)
    articles = get_pending_articles(conn, limit)

    classified = 0
    for article_id, title, body in articles:
        print(f"classifying: id={article_id} {title[:60]}")
        try:
            genre_id = ask_genre(title, body or "")
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        if genre_id is None:
            print("  WARNING: could not parse genre from LLM response, skipping")
            continue

        update_genre(conn, article_id, genre_id)
        print(f"  -> {genre_id}: {GENRES[genre_id]}")
        classified += 1

    print(f"done: {classified} / {len(articles)} articles classified")
    conn.close()


if __name__ == "__main__":
    main()
