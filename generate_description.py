import json
import re
import subprocess
import sys
from pathlib import Path

import requests

args = sys.argv
if len(args) < 2:
    print(f"usage: python {Path(args[0]).name} <pipeline_no>")
    raise SystemExit(1)

OUTDIR = Path(f"jobs/story_pipeline{args[1]}")

MODEL = "gemma4:31b-it-bf16"
OLLAMA_URL = "http://localhost:11434/api/generate"

# llama.cpp/Ollama側がUTF-8として正しく組み立てられなかったトークンを
# "<0xE6>"のようなバイト表記のまま出力してしまうことがある(特に日本語の
# 漢字生成時)。生成結果自体の破損なので検出したら失敗させる
GARBLED_BYTE_TOKEN_RE = re.compile(r"<0x[0-9A-Fa-f]{2}>")

NARRATION_CHARS_LIMIT = 6000

SYNOPSIS_PROMPT_TEMPLATE = """以下は動画のタイトルとナレーション全文です。
この動画のYouTube概要欄・タグ欄に載せる情報をJSON形式で作成してください。

条件:
・synopsis: 物語の核心的な結末までは明かしすぎず、視聴を促す紹介文(日本語200〜400字程度)。前置きや見出しは不要で本文のみ
・hashtags: 動画の内容に関連する日本語ハッシュタグを5個、"#"付き・半角スペース区切りの1つの文字列
・tags: YouTubeのタグ欄に登録する検索キーワードを10〜15個、日本語の配列

出力はJSON以外の文字列を一切出力しないこと。

出力形式:
{{
  "synopsis": "...",
  "hashtags": "#〇〇 #〇〇 #〇〇 #〇〇 #〇〇",
  "tags": ["...", "..."]
}}

タイトル: {title}

ナレーション全文:
{narration_full}
"""


def strip_code_fence(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def ask_ollama(prompt, num_predict=800):
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.5,
            "top_p": 0.9,
            "num_ctx": 16384,
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
    if GARBLED_BYTE_TOKEN_RE.search(text):
        raise RuntimeError(f"LLM output contains garbled byte tokens: {text!r}")
    return text


def main():
    out_path = OUTDIR / "description.txt"
    if out_path.exists():
        print(f"skip (cached): {out_path}")
        return

    with open(OUTDIR / "final_story.json", encoding="utf-8") as f:
        story = json.load(f)

    title = story.get("title", "")
    narration_full = "\n".join(scene["narration"] for scene in story["scenes"])

    print("generating synopsis/hashtags/tags...")
    response = ask_ollama(
        SYNOPSIS_PROMPT_TEMPLATE.format(
            title=title,
            narration_full=narration_full[:NARRATION_CHARS_LIMIT],
        ),
        num_predict=1500,
    )

    # 後続工程(サムネイル生成のFLUX等)がVRAMを使えるよう、終了時にOllamaのモデルをアンロードする
    subprocess.run(["ollama", "stop", MODEL], check=False)

    data = json.loads(strip_code_fence(response))
    synopsis = data["synopsis"].strip()
    hashtags = data["hashtags"].strip()
    tags = data["tags"]

    out_path.write_text(f"{synopsis}\n\n{hashtags}", encoding="utf-8")
    (OUTDIR / "tags.txt").write_text(", ".join(tags), encoding="utf-8")
    print(f"done: {out_path}")


if __name__ == "__main__":
    main()
