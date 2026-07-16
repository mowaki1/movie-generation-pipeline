import json
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

NARRATION_CHARS_LIMIT = 6000

SYNOPSIS_PROMPT_TEMPLATE = """以下は動画のタイトルとナレーション全文です。
この動画のYouTube概要欄に載せるあらすじを、日本語で200〜400字程度で書いてください。

条件:
・物語の核心的な結末までは明かしすぎず、視聴を促す紹介文にすること
・前置きや見出し(「あらすじ:」等)は不要で、本文のみを出力すること

タイトル: {title}

ナレーション全文:
{narration_full}
"""


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

    print("generating synopsis...")
    synopsis = ask_ollama(
        SYNOPSIS_PROMPT_TEMPLATE.format(
            title=title,
            narration_full=narration_full[:NARRATION_CHARS_LIMIT],
        )
    )

    # 後続工程(サムネイル生成のFLUX等)がVRAMを使えるよう、終了時にOllamaのモデルをアンロードする
    subprocess.run(["ollama", "stop", MODEL], check=False)

    out_path.write_text(synopsis, encoding="utf-8")
    print(f"done: {out_path}")


if __name__ == "__main__":
    main()
