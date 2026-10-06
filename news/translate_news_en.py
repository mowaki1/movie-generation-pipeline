# 日本語ニュース動画(完成済みジョブ)を英語版チャンネル用に再ローカライズする第1段階。
# 画像・LTX動画クリップは言語に依存しないため、日本語版のものをシンボリックリンクで
# 再利用し、ナレーションとタイトルだけを英訳した英語版ジョブ(final_story.json)を作る。
#
# usage: python translate_news_en.py <source_pipeline_no> <en_pipeline_no> <en_genre_id>

import json
import re
import subprocess
import sys
from pathlib import Path

import requests

MODEL = "gemma4:31b-it-bf16"
OLLAMA_URL = "http://localhost:11434/api/generate"

BATCH_SIZE = 8
MAX_RETRIES = 3

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTRO_EN_FILENAME = "outro_en.mp4"

JAPANESE_CHAR_RE = re.compile(r"[぀-ヿ㐀-䶿一-鿿]")

TRANSLATE_PROMPT = """You are a professional news translator and voice-over scriptwriter.
Translate the following Japanese news video narration into natural, fluent spoken English for a news voice-over.

Rules:
- Keep every fact, number, name and nuance. Do not add or omit information.
- Write for the ear: clear, concise sentences in a neutral news-anchor tone. Roughly the same length as the original or slightly shorter.
- Do not translate word for word. Rephrase so that it sounds like a native English-speaking news anchor talking. Avoid vague or literal phrasing that only makes sense in Japanese.
- The audience is a global English-speaking audience, not a Japanese one. Do not frame the news from a Japanese-market perspective: no emotional commentary such as "unfortunately" or "we look forward to" about Japan. State facts about Japan neutrally (e.g. "Japan is not part of the initial launch").
- If the source gives a price in its original currency (e.g. US dollars) together with a yen conversion, keep only the original currency. Keep yen only when the amount is natively in yen (e.g. a Japanese company's revenue).
- If the narration ends with a call to subscribe, write a short, natural call to subscribe to the channel.
- Use the standard English spelling for company, product and person names (romanize Japanese names).
- Convert Japanese-style dates and units to natural English (e.g. 2026年9月11日 -> September 11, 2026; 5億円 -> 500 million yen).
- The output must contain no Japanese characters at all.
- Keep scene_no unchanged and output exactly one entry per input scene, in the same order.

Output JSON only (no commentary), in this format:
[{{"scene_no": 1, "narration": "..."}}]

Input:
{scenes_json}
"""

TITLE_PROMPT = """Translate this Japanese YouTube news video title into a natural, engaging English title of at most 90 characters.
If the title starts with a Japanese date such as 2026年9月11日, write it as "Sep 11, 2026:" at the start.
The output must contain no Japanese characters. Output the title only, with no quotes or commentary.

Title: {title}
"""


def ask_ollama(prompt, num_predict=4096):
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.3,
            "top_p": 0.9,
            "num_ctx": 16384,
            "num_predict": num_predict,
            # Swallowのチャットテンプレート終了トークンが/api/generateで正しく
            # 解釈されず可視文字として漏れ、生成が早期打ち切りになる不具合対策
            "stop": ["<|im_end|>", "<|eot_id|>", "<|end_of_text|>", "<|im_start|>"],
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


def parse_json_array(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return json.loads(text[text.index("["):text.rindex("]") + 1])


def translate_batch(batch):
    payload = [{"scene_no": s["scene_no"], "narration": s["narration"]} for s in batch]
    prompt = TRANSLATE_PROMPT.format(
        scenes_json=json.dumps(payload, ensure_ascii=False, indent=2)
    )
    expected = {s["scene_no"] for s in batch}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = parse_json_array(ask_ollama(prompt))
            by_no = {int(r["scene_no"]): r["narration"].strip() for r in result}
            if set(by_no) != expected:
                raise ValueError(f"scene_no mismatch: got {sorted(by_no)}, expected {sorted(expected)}")
            for no, narration in by_no.items():
                if not narration or JAPANESE_CHAR_RE.search(narration):
                    raise ValueError(f"scene {no}: empty or contains Japanese characters: {narration!r}")
            return by_no
        except Exception as e:
            print(f"translate batch failed (試行 {attempt}/{MAX_RETRIES}): {e}")

    print(f"ERROR: 翻訳が{MAX_RETRIES}回試行しても失敗しました (scene_no {sorted(expected)})")
    raise SystemExit(1)


def translate_title(title):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            translated = ask_ollama(TITLE_PROMPT.format(title=title), num_predict=200)
            translated = translated.strip().strip('"').strip()
            if translated and not JAPANESE_CHAR_RE.search(translated):
                return translated
            raise ValueError(f"empty or contains Japanese characters: {translated!r}")
        except Exception as e:
            print(f"translate title failed (試行 {attempt}/{MAX_RETRIES}): {e}")

    print(f"ERROR: タイトル翻訳が{MAX_RETRIES}回試行しても失敗しました")
    raise SystemExit(1)


def link_assets(src_dir, dst_dir):
    # 画像とLTXの動画クリップは高コストかつ言語非依存なので、コピーせずリンクで再利用する。
    # generate_movie4.pyは出力ファイルが既に存在すれば生成をスキップする
    for pattern in ("image*.png", "motion*_raw.mp4", "motion*_scaled.mp4"):
        for src in src_dir.glob(pattern):
            dst = dst_dir / src.name
            if dst.exists() or dst.is_symlink():
                continue
            dst.symlink_to(src.resolve())


def main():
    args = sys.argv
    if len(args) < 4:
        print(f"usage: python {Path(args[0]).name} <source_pipeline_no> <en_pipeline_no> <en_genre_id>")
        raise SystemExit(1)

    source_no = args[1]
    src_dir = Path(f"jobs/story_pipeline{source_no}")
    en_dir = Path(f"jobs/story_pipeline{args[2]}")
    en_genre_id = int(args[3])

    out_path = en_dir / "final_story.json"
    if out_path.exists():
        print(f"skip (cached): {out_path}")
        return

    src_story_path = src_dir / "final_story.json"
    if not src_story_path.exists():
        print(f"ERROR: {src_story_path} がありません(日本語版ジョブが未完了)")
        raise SystemExit(1)

    with open(src_story_path, encoding="utf-8") as f:
        src_story = json.load(f)

    en_dir.mkdir(parents=True, exist_ok=True)
    link_assets(src_dir, en_dir)

    # 途中で失敗しても、翻訳済みのバッチをやり直さずに済むよう都度保存する
    partial_path = en_dir / "04_translation_partial.json"
    translated = {}
    if partial_path.exists():
        translated = {int(k): v for k, v in json.loads(partial_path.read_text(encoding="utf-8")).items()}

    scenes = src_story["scenes"]
    for i in range(0, len(scenes), BATCH_SIZE):
        batch = [s for s in scenes[i:i + BATCH_SIZE] if s["scene_no"] not in translated]
        if not batch:
            continue
        print(f"translating scenes {batch[0]['scene_no']}-{batch[-1]['scene_no']}...")
        translated.update(translate_batch(batch))
        partial_path.write_text(json.dumps(translated, ensure_ascii=False), encoding="utf-8")

    print("translating title...")
    title_en = translate_title(src_story.get("title", ""))
    print(f"title: {title_en}")

    # 後続のFLUX/LTX等がVRAMを使えるよう、終了時にOllamaのモデルをアンロードする
    subprocess.run(["ollama", "stop", MODEL], check=False)

    outro_file = OUTRO_EN_FILENAME if (REPO_ROOT / "assets" / OUTRO_EN_FILENAME).exists() else None

    out_path.write_text(
        json.dumps(
            {
                "genre_id": en_genre_id,
                "language": "en",
                "source_genre_id": src_story.get("genre_id"),
                "source_pipeline_no": int(source_no),
                "title": title_en,
                "outro_file": outro_file,
                "scenes": [
                    {
                        "scene_no": s["scene_no"],
                        "image_prompt": s["image_prompt"],
                        "motion_prompt": s["motion_prompt"],
                        "narration": translated[s["scene_no"]],
                    }
                    for s in scenes
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"done: {out_path}")


if __name__ == "__main__":
    main()
