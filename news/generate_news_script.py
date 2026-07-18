import atexit
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import psycopg2
import requests

DB_DSN = "dbname=news_pipeline"

MODEL = "gemma4:31b-it-bf16"
OLLAMA_URL = "http://localhost:11434/api/generate"

# 後続工程(FLUX/LTX)がVRAMを使えるよう、終了時にOllamaのモデルを明示的にアンロードする
atexit.register(lambda: subprocess.run(["ollama", "stop", MODEL], check=False))

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
TAVILY_URL = "https://api.tavily.com/search"

# variant_id(10001-10009) -> m_genres.id(1-9)
VARIANT_TO_GENRE = {
    10001: 1,  # AIニュース
    10002: 2,  # ITニュース
    10003: 3,  # GPUニュース
    10004: 4,  # 金融ニュース
    10005: 5,  # 地政学ニュース
    10006: 6,  # 科学ニュース
    10007: 7,  # 医療ニュース
    10008: 8,  # Linuxニュース
    10009: 9,  # セキュリティニュース
}

CANDIDATE_LIMIT = 30
RELATED_ARTICLES_LIMIT = 5
WEB_SEARCH_RESULTS = 5
TARGET_SCENES = 12
BODY_CHARS_LIMIT = 2000
DUPLICATE_DISTANCE_THRESHOLD = 0.15  # コサイン距離。これ未満は「ほぼ同じ出来事の記事」とみなす


def ask_ollama(prompt, num_predict=4096, temperature=0.3):
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": temperature,
            "top_p": 0.9,
            "num_ctx": 16384,
            "num_predict": num_predict,
        },
    }
    res = requests.post(OLLAMA_URL, json=payload, timeout=600)
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


def strip_code_fence(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


SELECT_PROMPT_TEMPLATE = """以下は直近のニュース記事一覧です(ID: タイトル / 要約)。
この中から、動画で取り上げるべき最も重要・興味深い記事を1つ選び、そのIDの数字だけを出力してください。

{listing}

出力形式: IDの数字のみ(説明文は不要です)。
"""


def select_article(conn, genre_id):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, title, summary FROM t_articles
            WHERE genre_id = %s AND status_id = 8
            ORDER BY published_at DESC
            LIMIT %s
            """,
            (genre_id, CANDIDATE_LIMIT),
        )
        candidates = cur.fetchall()

    if not candidates:
        raise RuntimeError(f"no candidate articles for genre_id={genre_id}")

    listing = "\n".join(f"{aid}: {title}\n  {summary}" for aid, title, summary in candidates)
    response = ask_ollama(SELECT_PROMPT_TEMPLATE.format(listing=listing), num_predict=64)

    match = re.search(r"\d+", response)
    valid_ids = {c[0] for c in candidates}
    if not match or int(match.group()) not in valid_ids:
        raise RuntimeError(f"could not parse a valid article id from: {response!r}")

    return int(match.group())


def get_article(conn, article_id):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, body, summary FROM t_articles WHERE id = %s",
            (article_id,),
        )
        return cur.fetchone()


def mark_video_generated(conn, article_id):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE t_articles SET status_id = 9 WHERE id = %s",
            (article_id,),
        )
    conn.commit()


def mark_duplicate_articles(conn, article_id, max_distance=DUPLICATE_DISTANCE_THRESHOLD):
    # 別ソースが同じ出来事を報じているだけの記事(コサイン距離が極めて小さい)を
    # 「この動画でカバー済み」として一緒にstatus_id=9にし、将来再選定されるのを防ぐ
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE t_articles
            SET status_id = 9
            WHERE status_id = 8
              AND id != %s
              AND id IN (
                SELECT e.article_id
                FROM t_embeddings e
                WHERE e.embedding_model_id = 1
                  AND e.embedding <=> (
                    SELECT embedding FROM t_embeddings
                    WHERE article_id = %s AND embedding_model_id = 1
                  ) < %s
              )
            RETURNING id, title
            """,
            (article_id, article_id, max_distance),
        )
        return cur.fetchall()


def find_related_articles(conn, article_id, limit=RELATED_ARTICLES_LIMIT):
    # コサイン距離がDUPLICATE_DISTANCE_THRESHOLD未満の記事は、別ソースが同じ出来事を
    # 報じているだけの重複である可能性が高く、深掘り材料として意味が薄いため除外する
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.id, a.title, a.summary
            FROM t_embeddings e
            JOIN t_articles a ON a.id = e.article_id
            WHERE e.embedding_model_id = 1
              AND e.article_id != %s
              AND e.embedding <=> (
                SELECT embedding FROM t_embeddings
                WHERE article_id = %s AND embedding_model_id = 1
              ) >= %s
            ORDER BY e.embedding <=> (
                SELECT embedding FROM t_embeddings
                WHERE article_id = %s AND embedding_model_id = 1
            )
            LIMIT %s
            """,
            (article_id, article_id, DUPLICATE_DISTANCE_THRESHOLD, article_id, limit),
        )
        return cur.fetchall()


def tavily_search(query, max_results=WEB_SEARCH_RESULTS):
    if not TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY is not set")

    res = requests.post(
        TAVILY_URL,
        json={
            "api_key": TAVILY_API_KEY,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        },
        timeout=30,
    )
    res.raise_for_status()
    return res.json().get("results", [])


SCRIPT_PROMPT_TEMPLATE = """あなたはニュース解説動画の脚本家です。
以下の「軸となる記事」と「関連材料」だけを根拠に、日本語のニュース解説動画の台本をJSON形式で作成してください。

重要な制約:
・軸となる記事および関連材料に書かれていない事実を創作しないこと(ハルシネーション禁止)
・登場人物(キャラクター)は設定しないこと。ナレーターが視聴者に語りかける構成にすること
・image_promptは、ニュースの内容を象徴する報道写真・図解・関連する場所や物のクローズアップなど、具体的で写実的な英語の画像生成プロンプトにすること(架空の人物の外見描写は不要)
・{target_scenes}シーン程度で構成すること
・各シーンのnarrationは2〜4文程度の日本語
・titleは、元記事のタイトルを直訳するのではなく、YouTube向けに再構成した日本語の動画タイトル(30字程度、内容を的確に表し興味を引くもの)にすること

軸となる記事:
タイトル: {main_title}
本文: {main_body}

関連材料(社内DB類似記事):
{related_articles}

関連材料(Web検索結果):
{web_results}

出力形式(JSON以外の文字列は一切出力しないこと):
{{
  "title": "...(日本語の動画タイトル)",
  "scenes": [
    {{
      "scene_no": 1,
      "image_prompt": "...(英語)",
      "motion_prompt": "...(英語、カメラワークや被写体の動き)",
      "narration": "...(日本語)"
    }}
  ]
}}
"""


def build_script_prompt(main_article, related_articles, web_results):
    _, main_title, main_body, _ = main_article

    related_text = "\n".join(
        f"- {title}: {summary}" for _, title, summary in related_articles
    ) or "(該当なし)"

    web_text = "\n".join(
        f"- {r.get('title', '')}: {r.get('content', '')[:500]}" for r in web_results
    ) or "(該当なし)"

    return SCRIPT_PROMPT_TEMPLATE.format(
        target_scenes=TARGET_SCENES,
        main_title=main_title,
        main_body=(main_body or "")[:BODY_CHARS_LIMIT],
        related_articles=related_text,
        web_results=web_text,
    )


def generate_script(main_article, related_articles, web_results):
    prompt = build_script_prompt(main_article, related_articles, web_results)
    response = ask_ollama(prompt, num_predict=6000)

    text = strip_code_fence(response)
    data = json.loads(text)

    title = data.get("title", "").strip()
    scenes = data["scenes"]
    if not title:
        raise RuntimeError("LLM did not return a title")
    if not scenes:
        raise RuntimeError("LLM returned an empty scenes list")

    # scene_noを1始まりの連番に振り直す(欠番/重複対策)
    for i, scene in enumerate(scenes, start=1):
        scene["scene_no"] = i

    return title, scenes


def main():
    args = sys.argv
    if len(args) < 3:
        print(f"usage: python {Path(args[0]).name} <genre_id> <pipeline_no>")
        raise SystemExit(1)

    genre_variant_id = int(args[1])
    pipeline_no = args[2]

    outdir = Path(f"jobs/story_pipeline{pipeline_no}")
    if (outdir / "final_story.json").exists():
        # 既に台本が完成している場合は再生成しない(記事の再選定やTavilyクエリの
        # 無駄遣いを避け、後続工程の画像/音声キャッシュとのミスマッチも防ぐ)
        print(f"skip (cached): {outdir / 'final_story.json'}")
        return

    genre_id = VARIANT_TO_GENRE.get(genre_variant_id)
    if genre_id is None:
        print(f"ERROR: unknown genre_id {genre_variant_id} (expected 10001-10009)")
        raise SystemExit(1)

    conn = psycopg2.connect(DB_DSN)

    print(f"selecting article for genre_id={genre_id}...")
    article_id = select_article(conn, genre_id)
    main_article = get_article(conn, article_id)
    print(f"selected: id={article_id} {main_article[1]}")

    print("searching related articles (embedding similarity)...")
    related_articles = find_related_articles(conn, article_id)
    for _, title, _ in related_articles:
        print(f"  related: {title}")

    print("searching web (Tavily)...")
    web_results = tavily_search(main_article[1])
    for r in web_results:
        print(f"  web: {r.get('title', '')}")

    print("generating script...")
    title, scenes = generate_script(main_article, related_articles, web_results)
    print(f"title: {title}")
    print(f"generated {len(scenes)} scenes")

    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "final_story.json").write_text(
        json.dumps(
            {"title": title, "speaker_id": 30, "scenes": scenes},  # No.7 アナウンス(ニュース系)
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    mark_video_generated(conn, article_id)
    duplicates = mark_duplicate_articles(conn, article_id)
    for dup_id, dup_title in duplicates:
        print(f"  duplicate covered: id={dup_id} {dup_title}")

    conn.close()
    print(
        f"done: {outdir / 'final_story.json'} "
        f"(article id={article_id} + {len(duplicates)} duplicates marked status_id=9)"
    )


if __name__ == "__main__":
    main()
