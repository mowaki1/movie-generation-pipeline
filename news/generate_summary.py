import psycopg2
import requests

DB_DSN = "dbname=news_pipeline"

MODEL = "hf.co/mradermacher/Llama-3.3-Swallow-70B-Instruct-v0.4-GGUF:Q5_K_M"
API_URL = "http://localhost:11434/api/generate"

BODY_CHARS_LIMIT = 3000

# news/generate_news_script.pyのDUPLICATE_DISTANCE_THRESHOLDと同じ値。
# コサイン距離がこれ未満は「ほぼ同じ出来事の記事」とみなす
DUPLICATE_DISTANCE_THRESHOLD = 0.15

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


def already_covered_by_video(conn, article_id, max_distance=DUPLICATE_DISTANCE_THRESHOLD):
    # status_id=8への昇格はこの記事が動画生成の候補になることを意味するが、
    # 既に動画化済み(status_id=9)の記事とほぼ同じ出来事を報じているだけなら
    # 候補にする意味が無い(将来的に別記事として再度選ばれ、内容が重複した
    # 動画が生成されてしまう恐れがある)ため、要約前にチェックしてスキップする
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM t_embeddings e
            JOIN t_articles a ON a.id = e.article_id
            WHERE e.embedding_model_id = 1
              AND a.status_id = 9
              AND e.embedding <=> (
                SELECT embedding FROM t_embeddings
                WHERE article_id = %s AND embedding_model_id = 1
              ) < %s
            LIMIT 1
            """,
            (article_id, max_distance),
        )
        return cur.fetchone() is not None


def mark_already_covered(conn, article_id):
    with conn.cursor() as cur:
        cur.execute("UPDATE t_articles SET status_id = 9 WHERE id = %s", (article_id,))
    conn.commit()


def main(limit=200):
    conn = psycopg2.connect(DB_DSN)
    articles = get_pending_articles(conn, limit)

    summarized = 0
    skipped_duplicates = 0
    for article_id, title, body in articles:
        if already_covered_by_video(conn, article_id):
            print(f"skip (already covered by an existing video): id={article_id} {title[:60]}")
            mark_already_covered(conn, article_id)
            skipped_duplicates += 1
            continue

        print(f"summarizing: id={article_id} {title[:60]}")
        try:
            summary = ask_summary(title, body or "")
            save_summary(conn, article_id, summary)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        print(f"  ok: {len(summary)} chars")
        summarized += 1

    print(
        f"done: {summarized} summarized, {skipped_duplicates} skipped as duplicates "
        f"/ {len(articles)} articles"
    )
    conn.close()


if __name__ == "__main__":
    main()
