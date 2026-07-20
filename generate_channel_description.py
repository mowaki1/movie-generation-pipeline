import subprocess
import sys
from pathlib import Path

import psycopg2
import requests

DB_DSN = "dbname=video_pipeline"

MODEL = "gemma4:31b-it-bf16"
OLLAMA_URL = "http://localhost:11434/api/generate"

FAMILY_LABELS = {
    "drama": "人間ドラマ",
    "study": "大人の学びなおし",
    "trivia": "雑学・ミステリー",
    "news": "ニュース解説",
}

CHANNEL_DESCRIPTION_PROMPT = """以下のYouTubeチャンネルの「チャンネル説明欄(概要)」を日本語で書いてください。

チャンネル名: {genre_name}
ジャンル系統: {family_label}

条件:
・200〜400字程度
・どんな動画が見られるチャンネルか、視聴者にとって魅力が伝わるように書くこと
・このチャンネルの動画はAIによって自動生成されていることを、誠実に一文だけ触れること
・登録を促す一言を含めること
・前置きや見出しは不要で、本文のみを出力すること
"""


def get_family(genre_id):
    if 1000 <= genre_id < 2000:
        return "drama"
    if 2000 <= genre_id < 3000:
        return "study"
    if 3000 <= genre_id < 4000:
        return "trivia"
    if 10000 <= genre_id < 20000:
        return "news"
    raise ValueError(f"unknown genre_id {genre_id}")


def get_genre_name(conn, genre_id):
    with conn.cursor() as cur:
        cur.execute("SELECT genre FROM m_genres WHERE id = %s", (genre_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"genre_id {genre_id} not found in m_genres")
        return row[0]


def ask_ollama(prompt, num_predict=800):
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.6,
            "top_p": 0.9,
            "num_ctx": 8192,
            "num_predict": num_predict,
        },
    }
    res = requests.post(OLLAMA_URL, json=payload, timeout=300)
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


def main():
    args = sys.argv
    if len(args) < 2:
        print(f"usage: python {Path(args[0]).name} <genre_id>")
        raise SystemExit(1)

    genre_id = int(args[1])
    family = get_family(genre_id)
    family_label = FAMILY_LABELS[family]

    outdir = Path(f"channel_art/{genre_id}")
    out_path = outdir / "channel_description.txt"
    if out_path.exists():
        print(f"skip (cached): {out_path}")
        return

    conn = psycopg2.connect(DB_DSN)
    genre_name = get_genre_name(conn, genre_id)
    conn.close()

    print(f"generating channel description for {genre_name}...")
    description = ask_ollama(
        CHANNEL_DESCRIPTION_PROMPT.format(genre_name=genre_name, family_label=family_label)
    )

    # 後続工程(画像/動画生成のFLUX等)がVRAMを使えるよう、終了時にOllamaのモデルをアンロードする
    subprocess.run(["ollama", "stop", MODEL], check=False)

    outdir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(description, encoding="utf-8")
    print(f"done: {out_path}")


if __name__ == "__main__":
    main()
