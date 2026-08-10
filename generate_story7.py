import requests
import json
import os
import time
import re
import sys
import subprocess
import atexit
from pathlib import Path

args = sys.argv

MODEL = "hf.co/mradermacher/Llama-3.3-Swallow-70B-Instruct-v0.4-GGUF:Q5_K_M"
API_URL = "http://localhost:11434/api/generate"
#MOVIE_THEME = "面会ゼロだった老人に起きた大逆転"
MOVIE_THEME = args[3]

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
TAVILY_URL = "https://api.tavily.com/search"


def tavily_search(query, max_results=5):
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

# 後続工程(FLUX/Wan2.2/LTX)がVRAMを使えるよう、終了時にOllamaのモデルを明示的にアンロードする
atexit.register(lambda: subprocess.run(["ollama", "stop", MODEL], check=False))

INCLUDE_PATH = Path("include")

# 変数群のpy
with open(INCLUDE_PATH / f"variables_{args[1]}.py", "r", encoding="utf-8-sig") as f:
    exec(f.read())

OUTDIR = Path(f"jobs/story_pipeline{args[2]}")
OUTDIR.mkdir(parents=True, exist_ok=True)

if (OUTDIR / "final_story.json").exists():
    # 既に台本が完成している場合は再生成しない(後続工程の画像/音声キャッシュと
    # 内容がミスマッチするのを防ぐため、他の工程と同じ「既存ならスキップ」に揃える)
    print(f"skip (cached): {OUTDIR / 'final_story.json'}")
    raise SystemExit(0)

# 関数群のpy
with open(INCLUDE_PATH / "functions.py", "r", encoding="utf-8-sig") as f:
    exec(f.read())

# LLMの学習データが古いジャンル(variables_*.pyでUSE_TAVILY_SEARCH = Trueを
# 指定したもの)では、テーマ名でWeb検索し最新情報をBASEに埋め込む。
# MOVIE_THEMEは「第7章 バッテリーを長持ちさせる設定」のような内部的な
# 章タイトル表記を含むため、そのまま検索クエリに使うと実際のWeb検索に
# 適さない(章番号込みの文言は現実の検索クエリとして使われないため、
# 有効なヒットが得にくい)。機械的に章番号を取り除くのではなく、LLMに
# 自然な検索キーワードを考えさせてから検索する
web_context = ""
if globals().get("USE_TAVILY_SEARCH", False):
    search_query = ask(
        f"""次のテーマについて、Web検索で有益な情報を得るための、
自然な検索キーワードを1つ考えてください。
「第◯章」のような内部的な体裁は含めず、検索エンジンで実際に使われそうな
簡潔なキーワードにすること。

テーマ：{MOVIE_THEME}

出力は検索キーワードのみ。説明文や記号は禁止。""",
        filename="00_search_query.txt",
        num_predict=64,
    ).strip()
    print(f"search query: {search_query!r}")

    print("searching web (Tavily)...")
    web_results = tavily_search(search_query)
    web_text = "\n".join(
        f"- {r.get('title', '')}: {r.get('content', '')[:500]}" for r in web_results
    )
    if web_text:
        web_context = f"""
参考情報(Web検索結果。LLMの学習データより新しい情報の可能性があるため、
内容が矛盾する場合はこちらを優先すること):
{web_text}
"""

# BASEのpy
with open(INCLUDE_PATH / f"base_{args[1]}.py", "r", encoding="utf-8-sig") as f:
    exec(f.read())

# design_promptのpy
with open(INCLUDE_PATH / f"design_prompt_{args[1]}.py", "r", encoding="utf-8-sig") as f:
    exec(f.read())

# LLMがJSON構文を1箇所でも崩す(クォート抜け等)とdesign全体のパースが失敗し、
# 後続のoutline/narrationと違ってここだけリトライが無く即座にジョブ全体が
# 失敗していたため、他の工程と同様に数回re試行してから諦めるようにする
DESIGN_MAX_RETRIES = 3
design_json = None
for attempt in range(1, DESIGN_MAX_RETRIES + 1):
    design_text = ask(
        design_prompt,
        filename="01_design.json",
        num_predict=4096,
    )

    # その後Character Bible生成
    # まずJSON化
    candidate_json = safe_json_loads(design_text, {})
    candidate_json["title"] = MOVIE_THEME

    if "story_structure" in candidate_json:
        design_json = candidate_json
        break

    print(f"design生成が壊れたJSONを返しました (試行 {attempt}/{DESIGN_MAX_RETRIES})")

if design_json is None:
    print(f"ERROR: design生成が{DESIGN_MAX_RETRIES}回試行しても story_structure を含みませんでした")
    print(design_text)
    raise SystemExit(1)

print(json.dumps(design_json, ensure_ascii=False, indent=2))
    
# Character Bible生成
character_bible = build_character_bible(design_json)

(OUTDIR / "character_bible.txt").write_text(
    character_bible,
    encoding="utf-8"
)

# outline_logicのpy
with open(INCLUDE_PATH / f"outline_{args[1]}.py", "r", encoding="utf-8-sig") as f:
    exec(f.read())

outline = sorted(outline, key=lambda x: x["scene_no"])

(OUTDIR / "02_outline.json").write_text(
    json.dumps(outline, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print(f"outline scenes: {len(outline)}")


# 3. 5シーンずつナレーション化
narration_scenes = []

character_names = "\n".join(
    f"- {c['name']}"
    for c in design_json["characters"]
)

for start in range(1, VIDEO_LENGTH + 1, 5):
    end = start + 4
    chunk_outline = [
        x for x in outline
        if start <= int(x["scene_no"]) <= end
    ]

    if not chunk_outline:
        continue

    # narration_promptのpy
    with open(INCLUDE_PATH / f"narration_prompt_{args[1]}.py", "r", encoding="utf-8-sig") as f:
        exec(f.read())

    # チャンネル登録を促す一言は動画全体で最後のシーンにのみ入れたい。
    # 以前はbase_*.py側に無条件で「最後のシーンには〜」と書いていたため、
    # 5シーンごとのチャンクそれぞれが「最後のシーン」だと誤解され、
    # 動画の途中(各チャンクの末尾)に何度もCTAが挿入されてしまっていた。
    # ここで本当に動画全体の最終チャンクの場合だけ明示的に指示を追加する
    if end >= VIDEO_LENGTH:
        narration_prompt += (
            f"\n\n重要: scene_no {min(end, VIDEO_LENGTH)}はこの動画全体の最後の"
            "シーンです。そのnarrationには、物語の余韻を保ったまま、"
            "チャンネル登録を促す一言を自然に添えること。"
        )

    # LLMが一部のシーン番号を生成せず打ち切ることがある(構文的には正常だが
    # 内容が不完全)。ask()側のリトライ(壊れたバイト列/短すぎる応答)とは
    # 別の失敗パターンなので、ここでも数回re試行してから諦める
    NARRATION_MAX_RETRIES = 3
    part = None
    for attempt in range(1, NARRATION_MAX_RETRIES + 1):
        text = ask(
            narration_prompt,
            filename=f"03_narration_{start:03d}_{end:03d}_raw.json",
            num_predict=4096,
        )
        try:
            part = parse_pipe_narration(text, start, end)
            break
        except Exception as e:
            print(f"narration parse failed {start}-{end} (試行 {attempt}/{NARRATION_MAX_RETRIES}): {e}")
            print(text)

    if part is None:
        print(f"ERROR: narration {start}-{end} が{NARRATION_MAX_RETRIES}回試行しても失敗しました")
        raise SystemExit(1)

    for item in part:
        if "scene_no" in item and "narration" in item:
            narration_scenes.append({
                "scene_no": int(item["scene_no"]),
                "narration": item["narration"].strip()
            })

    print(f"narration {start}-{end} done")


narration_scenes = sorted(narration_scenes, key=lambda x: x["scene_no"])

(OUTDIR / "03_scenes_narration.json").write_text(
    json.dumps({
        "title": MOVIE_THEME,
        "synopsis": "",
        "scenes": narration_scenes
    }, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print(f"narration scenes: {len(narration_scenes)}")


# 4. 各シーンに映像プロンプト追加
final_scenes = []

for scene in narration_scenes:
    scene_no = scene["scene_no"]
    narration_text = scene["narration"]

    # visual_promptのpy
    with open(INCLUDE_PATH / f"visual_prompt_{args[1]}.py", "r", encoding="utf-8-sig") as f:
        exec(f.read())

    # visual_logicのpy
    with open(INCLUDE_PATH / f"visual_logic_{args[1]}.py", "r", encoding="utf-8-sig") as f:
        exec(f.read())



def speaker_id_for_variant(variant_id: int) -> int:
    # VOICEVOX「No.7」のスタイル違いで、ジャンル系統ごとにトーンを変える
    if 1000 <= variant_id < 2000:
        return 31  # 読み聞かせ(ドラマ系)
    if 2000 <= variant_id < 4000:
        return 29  # ノーマル(学びなおし系)
    return 31  # フォールバック


# 5. 最終保存
final_data = {
    "genre_id": int(args[1]),
    "title": MOVIE_THEME,
    "synopsis": "",
    "speaker_id": speaker_id_for_variant(int(args[1])),
    "scenes": final_scenes
}

(OUTDIR / "final_story.json").write_text(
    json.dumps(final_data, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("完成:", OUTDIR / "final_story.json")
print(f"final scenes: {len(final_scenes)}")