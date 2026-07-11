import requests
import json
import time
import re
import sys
from pathlib import Path

args = sys.argv

MODEL = "gemma4:e4b"
API_URL = "http://localhost:11434/api/generate"
#MOVIE_THEME = "面会ゼロだった老人に起きた大逆転"
MOVIE_THEME = args[3]

INCLUDE_PATH = Path("include")

# 変数群のpy
with open(INCLUDE_PATH / f"variables_{args[1]}.py", "r", encoding="utf-8") as f:
    exec(f.read())

OUTDIR = Path(f"jobs/story_pipeline{args[2]}")
OUTDIR.mkdir(parents=True, exist_ok=True)

# 関数群のpy
with open(INCLUDE_PATH / "functions.py", "r", encoding="utf-8") as f:
    exec(f.read())

# BASEのpy
with open(INCLUDE_PATH / f"base_{args[1]}.py", "r", encoding="utf-8") as f:
    exec(f.read())

# design_promptのpy
with open(INCLUDE_PATH / f"design_prompt_{args[1]}.py", "r", encoding="utf-8") as f:
    exec(f.read())

design_text = ask(
    design_prompt,
    filename="01_design.json",
    json_mode=True,
    num_predict=4096,
)

# その後Character Bible生成
# まずJSON化
design_json = safe_json_loads(design_text, {})
design_json["title"] = MOVIE_THEME

print(json.dumps(design_json, ensure_ascii=False, indent=2))

if "story_structure" not in design_json:
    print("ERROR: story_structure がありません")
    print(design_text)
    raise SystemExit
    
# Character Bible生成
character_bible = build_character_bible(design_json)

(OUTDIR / "character_bible.txt").write_text(
    character_bible,
    encoding="utf-8"
)

# outline_logicのpy
with open(INCLUDE_PATH / f"outline_{args[1]}.py", "r", encoding="utf-8") as f:
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
    with open(INCLUDE_PATH / f"narration_prompt_{args[1]}.py", "r", encoding="utf-8") as f:
        exec(f.read())


    text = ask(
        narration_prompt,
        filename=f"03_narration_{start:03d}_{end:03d}_raw.json",
        json_mode=False,
        num_predict=4096,
    )
    try:
        part = parse_pipe_narration(text, start, end)
    except Exception as e:
        print(f"narration parse failed {start}-{end}: {e}")
        print(text)
        raise SystemExit

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
    with open(INCLUDE_PATH / f"visual_prompt_{args[1]}.py", "r", encoding="utf-8") as f:
        exec(f.read())

    # visual_logicのpy
    with open(INCLUDE_PATH / f"visual_logic_{args[1]}.py", "r", encoding="utf-8") as f:
        exec(f.read())



# 5. 最終保存
final_data = {
    "title": MOVIE_THEME,
    "synopsis": "",
    "scenes": final_scenes
}

(OUTDIR / "final_story.json").write_text(
    json.dumps(final_data, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("完成:", OUTDIR / "final_story.json")
print(f"final scenes: {len(final_scenes)}")