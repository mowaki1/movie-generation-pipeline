# 英語版チャンネルは世界の視聴者向けなので、日本国内でしか意味を持たないニュースは
# 英語版を作らない。日本語版ナレーションを読ませて、英語版にする価値があるかを判定する。
# 迷う場合は「作る」側に倒す(国内限定と明らかなものだけ外す)。
#
# 終了コード: 0=英語版を作る / 10=国内限定のためスキップ(run_news_pipeline_en.py側の
# SKIP_EXIT_CODEと一致させること) / その他=エラー
#
# usage: python check_global_relevance_en.py <source_pipeline_no> <en_pipeline_no>

import json
import subprocess
import sys
from pathlib import Path

import requests

MODEL = "gemma4:31b-it-bf16"
OLLAMA_URL = "http://localhost:11434/api/generate"

SKIP_EXIT_CODE = 10
NARRATION_CHARS_LIMIT = 4000
MAX_RETRIES = 3

PROMPT = """You are the editor of an English-language news channel for a worldwide audience, covering science, technology and geopolitics.
Below is the title and narration of a Japanese news video. Decide whether it is worth producing an English version for non-Japanese viewers.

Answer "domestic" only if the story is clearly of no use or interest to people outside Japan, for example:
- campaigns, prices or promotions that apply only in Japan
- Japanese domestic regulations or politics with no international relevance
- services or products that can only be used or bought in Japan

Answer "global" for anything else, including:
- stories about Japanese companies or technologies that matter globally (semiconductors, EVs, games, robotics, etc.)
- international relations or security involving Japan
- global products or services that merely mention their availability in Japan

When in doubt, answer "global".

Output JSON only, in this format:
{{"verdict": "global" or "domestic", "reason": "one short sentence in English"}}

Title: {title}

Narration:
{narration}
"""


def ask_ollama(prompt):
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "top_p": 0.9,
            "num_ctx": 8192,
            "num_predict": 300,
            # Swallowのチャットテンプレート終了トークンが/api/generateで正しく
            # 解釈されず可視文字として漏れ、生成が早期打ち切りになる不具合対策
            "stop": ["<|im_end|>", "<|eot_id|>", "<|end_of_text|>", "<|im_start|>"],
        },
    }
    res = requests.post(OLLAMA_URL, json=payload, timeout=300)
    res.raise_for_status()
    data = res.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    text = data.get("response", "").strip()
    if not text:
        raise RuntimeError(f"empty response, done_reason={data.get('done_reason')!r}")
    return text


def classify(title, narration):
    prompt = PROMPT.format(title=title, narration=narration[:NARRATION_CHARS_LIMIT])
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            text = ask_ollama(prompt)
            data = json.loads(text[text.index("{"):text.rindex("}") + 1])
            verdict = data["verdict"].strip().lower()
            if verdict not in ("global", "domestic"):
                raise ValueError(f"unexpected verdict: {verdict!r}")
            return verdict, str(data.get("reason", "")).strip()
        except Exception as e:
            print(f"relevance check failed (試行 {attempt}/{MAX_RETRIES}): {e}")

    # 判定できない場合は、ニュースを取りこぼさないよう英語版を作る側に倒す
    print("WARNING: 判定に失敗したため、英語版を作る(global)扱いにします")
    return "global", "classification failed"


def main():
    args = sys.argv
    if len(args) < 3:
        print(f"usage: python {Path(args[0]).name} <source_pipeline_no> <en_pipeline_no>")
        raise SystemExit(1)

    src_story_path = Path(f"jobs/story_pipeline{args[1]}/final_story.json")
    en_dir = Path(f"jobs/story_pipeline{args[2]}")
    result_path = en_dir / "00_relevance.json"

    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
        print(f"skip (cached): {result_path}")
    else:
        if not src_story_path.exists():
            print(f"ERROR: {src_story_path} がありません(日本語版ジョブが未完了)")
            raise SystemExit(1)

        story = json.loads(src_story_path.read_text(encoding="utf-8"))
        narration = "\n".join(scene["narration"] for scene in story["scenes"])
        verdict, reason = classify(story.get("title", ""), narration)
        result = {"verdict": verdict, "reason": reason}

        en_dir.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"relevance: {result['verdict']} ({result['reason']})")

    if result["verdict"] == "domestic":
        # このあと英語版の工程に進まないので、後続のFLUX/LTX等がVRAMを使えるよう
        # Ollamaのモデルをアンロードしておく(globalの場合は次の翻訳工程で同じモデルを使う)
        subprocess.run(["ollama", "stop", MODEL], check=False)
        raise SystemExit(SKIP_EXIT_CODE)


if __name__ == "__main__":
    main()
