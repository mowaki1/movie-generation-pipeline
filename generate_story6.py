import requests
import json
import time
import re
import sys
import subprocess
import atexit
from pathlib import Path

args = sys.argv

if len(args) < 3:
    print(f"usage: python {Path(args[0]).name} <pipeline_no> <theme>")
    raise SystemExit(1)

MODEL = "gemma4:31b-it-bf16"
API_URL = "http://localhost:11434/api/generate"
MOVIE_THEME = args[2]

# 後続工程(FLUX/Wan2.2)がVRAMを使えるよう、終了時にOllamaのモデルを明示的にアンロードする
atexit.register(lambda: subprocess.run(["ollama", "stop", MODEL], check=False))

# ユーザー環境の実際のVOICEVOX話者IDに合わせて編集すること。
# characters配列の順番でこのプールから round-robin で割り当てる。
CHARACTER_SPEAKER_POOL = [31, 3, 8, 10]

OUTDIR = Path(f"jobs/story_pipeline{args[1]}")
OUTDIR.mkdir(parents=True, exist_ok=True)


def ask(prompt, filename=None, json_mode=False, num_predict=4096):
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "top_p": 0.9,
            "num_ctx": 32768,
            "num_predict": num_predict,
        },
    }

    if json_mode:
        payload["format"] = "json"

    for _ in range(3):
        res = requests.post(API_URL, json=payload, timeout=3000)
        res.raise_for_status()
        text = res.json().get("response", "").strip()

        if len(text) > 50:
            if filename:
                (OUTDIR / filename).write_text(text, encoding="utf-8")
            return text

        time.sleep(2)

    if filename:
        (OUTDIR / filename).write_text(text, encoding="utf-8")
    return text


def ask_cached(prompt, filename, json_mode=False, num_predict=4096):
    path = OUTDIR / filename
    if path.exists():
        print(f"skip (cached): {filename}")
        return path.read_text(encoding="utf-8")

    return ask(prompt, filename=filename, json_mode=json_mode, num_predict=num_predict)


def extract_json_array(text):
    text = repair_json_array(text)

    # そのままJSONとして読む
    try:
        data = json.loads(text)

        # 配列ならそのまま返す
        if isinstance(data, list):
            return data

        # {"scenes": [...]} 形式なら scenes を返す
        if isinstance(data, dict) and "scenes" in data:
            return data["scenes"]

        # {"scene_no": 1, "narration": "..."} 形式なら1件配列にする
        if isinstance(data, dict) and "scene_no" in data:
            return [data]

    except json.JSONDecodeError:
        pass

    # JSON配列だけ抜き出す
    m = re.search(r"\[\s*{.*}\s*\]", text, re.S)
    if m:
        return json.loads(m.group(0))

    # {"scenes":[...]} を抜き出す
    m = re.search(r"{\s*\"scenes\"\s*:\s*\[.*\]\s*}", text, re.S)
    if m:
        data = json.loads(m.group(0))
        return data["scenes"]

    raise ValueError("JSON配列またはscenesが見つかりません")

def safe_json_loads(text, fallback):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return fallback

def build_character_bible(design_json):
    characters = design_json.get("characters", [])

    lines = []
    for c in characters:
        name = c.get("name", "")
        role = c.get("role", "")
        age = c.get("age", "")
        appearance = c.get("appearance", "")

        if not name or not appearance:
            continue

        lines.append(
            f"{name} ({role}, {age}歳): {appearance}"
        )

    return "\n".join(lines)

def repair_json_array(text):
    text = text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    if text.startswith("["):
        if text.endswith('"\n]') or text.endswith('"\r\n]'):
            text = text[:-1] + "}\n]"

        if not text.endswith("]"):
            text += "\n]"

    return text

def find_characters(text, design_json):
    result = []

    for c in design_json["characters"]:
        if c["name"] in text:
            result.append(c)

    return result

def find_active_characters(text, design_json):
    active = []

    for c in design_json.get("characters", []):
        name = c.get("name", "")

        if not name:
            continue

        base_name = name.split("（")[0].strip()

        if name in text or base_name in text:
            active.append(c)

    return active

def build_active_character_text(active_characters):
    if not active_characters:
        return "No fixed character appears in this scene."

    lines = []

    for c in active_characters:
        lines.append(
            f'{c.get("name")}: {c.get("appearance")}'
        )

    return "\n".join(lines)

def build_image_prompt_by_python(narration_text, design_json):
    active = find_active_characters(narration_text, design_json)

    character_lines = []
    for c in active:
        character_lines.append(
            f'{c["name"]}: {c["appearance"]}'
        )

    if character_lines:
        characters_text = "\n".join(character_lines)
    else:
        characters_text = "elderly Japanese residents and care staff"

    return f"""
Japanese nursing home,
cinematic,
photorealistic,
realistic lighting,
high detail,

fixed characters:
{characters_text}

scene description:
{narration_text}
""".strip()

def safe_json_array(text):
    text = repair_json_array(text)

    m = re.search(r"\[\s*{.*}\s*\]", text, re.S)

    if not m:
        raise ValueError("json array not found")

    block = m.group(0)

    # 末尾カンマ除去
    block = re.sub(r',(\s*[}\]])', r'\1', block)

    # 生の制御文字を許容
    return json.loads(block, strict=False)

def build_character_json(active_characters):

    result = []

    for c in active_characters:

        result.append({
            "name": c["name"],
            "MUST_COPY_TO_IMAGE_PROMPT":
                c["appearance"]
        })

    return json.dumps(
        result,
        ensure_ascii=False,
        indent=2
    )

def parse_pipe_outline(text, start, end):
    scenes = []

    # まず 51|要約 形式を読む
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^(\d+)\s*[|｜]\s*(.+)$", line)
        if m:
            scene_no = int(m.group(1))
            summary = m.group(2).strip()
            if start <= scene_no <= end:
                scenes.append({"scene_no": scene_no, "summary": summary})

    # GemmaがJSON風で返した場合の救済
    if not scenes:
        for m in re.finditer(
            r'"scene_no"\s*:\s*(\d+)\s*,\s*"summary"\s*:\s*"([^"]+)"',
            text,
            re.S
        ):
            scene_no = int(m.group(1))
            summary = m.group(2).strip()
            if start <= scene_no <= end:
                scenes.append({"scene_no": scene_no, "summary": summary})

    # 重複除去
    unique = {}
    for s in scenes:
        unique[s["scene_no"]] = s
    scenes = [unique[i] for i in sorted(unique)]

    expected = list(range(start, end + 1))
    actual = [x["scene_no"] for x in scenes]

    if actual != expected:
        raise ValueError(f"outline番号不一致: expected={expected}, actual={actual}")

    return scenes

def parse_pipe_narration(text, start, end):
    scenes = []

    # 1|ナレーション 形式
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        m = re.match(r"^(\d+)\s*[|｜]\s*(.+)$", line)
        if m:
            scene_no = int(m.group(1))
            narration = m.group(2).strip()
            if start <= scene_no <= end:
                scenes.append({
                    "scene_no": scene_no,
                    "narration": narration
                })

    # GemmaがJSON風で返した場合の救済
    if not scenes:
        for m in re.finditer(
            r'"scene_no"\s*:\s*(\d+)\s*,\s*"narration"\s*:\s*"([^"]+)"',
            text,
            re.S
        ):
            scene_no = int(m.group(1))
            narration = m.group(2).strip()
            if start <= scene_no <= end:
                scenes.append({
                    "scene_no": scene_no,
                    "narration": narration
                })

    unique = {}
    for s in scenes:
        unique[s["scene_no"]] = s

    scenes = [unique[i] for i in sorted(unique)]

    expected = list(range(start, end + 1))
    actual = [x["scene_no"] for x in scenes]

    if actual != expected:
        raise ValueError(f"narration番号不一致: expected={expected}, actual={actual}")

    return scenes

BASE = f"""
あなたはYouTube向け短編ドラマ「老人ホーム専科」の脚本家です。

テーマ：
{MOVIE_THEME}

重要：
ナレーションだけ聞いてストーリーが追えるようにしてください。
登場人物の行動、会話、周囲の反応を明確にしてください。
心理描写だけで終わらせず、必ず出来事を進めてください。
高齢者向けYouTube朗読ドラマとして、分かりやすく感情移入できる物語にしてください。

これは心理小説ではなく、YouTube向けドラマです。
主人公以外にも重要人物を最低3人登場させてください。

必須人物：
・主人公：テーマの主人公にふさわしい人物
・主人公と相容れない人物
・主人公の味方となる人物
・主人公を評価しない職員または入居者

重要：
characters の name は自由に作ってよい。
ただし、一度作った name は以後の全工程で正式名称として扱う。

name には、後工程でそのまま使える短く一意な名前を入れること。
name にふりがなを入れないこと。
name を途中で短縮しないこと。
同姓だけの name は避けること。

良い例：
- 神崎健司
- 佐藤美咲
- 田中一郎
- 吉田主任
- アカリ

悪い例：
- 神崎健司（かんざき けんじ）
- 佐藤（さとう）
- 田中（たなか）
- 吉田（よしだ）

必須展開：

・起承転結を明確にする

【起】
主人公が抱える問題や状況を提示する

【承】
問題が深まり、人間関係や出来事が動き始める

【転】
主人公が大きな気づき・真実・転機を経験する

【結】
主人公が新しい価値観を得て、
視聴者に教訓や感動を残して締める

・物語は必ず前進させること
・一度得た気づきを失わせないこと
・同じ失敗を繰り返させないこと
・終盤は再生、成長、受容の方向へ向かわせること
・主人公は最終的に人生の大切な教訓を学ぶこと

・教訓は説教ではなく、
　主人公の行動や変化から自然に伝わるようにすること

・最後の1～3シーンは感情的な余韻を残すこと
・最後のシーンは教訓を含むオチで締めること

・視聴者が
「なるほど」
「そういうことか」
「考えさせられる」
のいずれかを感じる結末にすること
"""


# 1. 設計書作成
design_prompt = f"""
{BASE}

まず脚本の設計書だけをJSONで作ってください。

出力はJSONのみ。
説明文禁止。
Markdown禁止。

形式：

{{
  "title": "...",
  "synopsis": "...",
  "characters": [
    {{
      "name": "神崎健司",
      "role": "主人公",
      "age": 78,
      "appearance": "78-year-old Japanese man, short gray hair, deep wrinkles, sharp eyes, navy business suit, former bank vice president, dignified but lonely atmosphere"
    }}
  ],
  "story_structure": {{
    "act1": "...",
    "act2": "...",
    "act3": "...",
    "act4": "..."
  }}
}}

条件：
- characters には主要人物を3〜5人入れる
- 各characterには必ず name, role, age, appearance を入れる
- appearance はFlux向けの英語プロンプトにする
- appearance には年齢、性別、髪型、服装、表情、雰囲気を入れる
- まだ本文やシーン本文は書かない
- 起承転結を明確にしてください。
- 対立、孤立、転落、気づき、再生を必ず入れてください。

重要：
必ず story_structure を出力すること。
story_structure には必ず act1, act2, act3, act4 を入れること。
この4つのキーを省略してはいけない。
"""
design_text = ask_cached(
    design_prompt,
    filename="01_design.json",
    json_mode=True,
    num_predict=4096,
)

# その後Character Bible生成
# まずJSON化
design_json = safe_json_loads(design_text, {})
design_json["title"] = MOVIE_THEME

# 話者IDをキャラクターに機械的に割り当てる（LLMには生成させない）
for idx, c in enumerate(design_json.get("characters", [])):
    c["speaker_id"] = CHARACTER_SPEAKER_POOL[idx % len(CHARACTER_SPEAKER_POOL)]

print(json.dumps(design_json, ensure_ascii=False, indent=2))

if "story_structure" not in design_json:
    print("ERROR: story_structure がありません")
    print(design_text)
    raise SystemExit(1)
    
# Character Bible生成
character_bible = build_character_bible(design_json)

(OUTDIR / "character_bible.txt").write_text(
    character_bible,
    encoding="utf-8"
)

# 2. 100シーン骨子作成
outline_path = OUTDIR / "02_outline.json"

if outline_path.exists():
    outline = json.loads(outline_path.read_text(encoding="utf-8"))
    print(f"skip (cached): 02_outline.json ({len(outline)} scenes)")
else:
    outline = []
    act1 = design_json["story_structure"]["act1"]
    act2 = design_json["story_structure"]["act2"]
    act3 = design_json["story_structure"]["act3"]
    act4 = design_json["story_structure"]["act4"]

    for start in range(1, 101, 25):
        end = start + 24

        if start == 1:
            act_name = "起承転結の「起」"
            act_text = design_json["story_structure"]["act1"]
            extra_rule = f"""
この25シーンはAct1です。

まだ転落しない。
まだ改心しない。
まだ再生しない。
主人公は嫌な人物として描く。
"""
        elif start == 26:
            act_name = "起承転結の「承」"
            act_text = design_json["story_structure"]["act2"]
            extra_rule = f"""
この25シーンはAct2です。

対立と孤立を深める。
まだ再生しない。
まだ完全な気づきに到達しない。
"""
        elif start == 51:
            act_name = "起承転結の「転」"
            act_text = design_json["story_structure"]["act3"]
            extra_rule = f"""
この25シーンはAct3です。

転落と気づきを描く。
まだ完全再生しない。
"""
        else:
            act_name = "起承転結の「結」"
            act_text = design_json["story_structure"]["act4"]
            extra_rule = f"""
この25シーンはAct4です。

再生と教訓を描く。
物語を締める。
"""

        outline_prompt = f"""
{BASE}

以下の設計書に従い、scene_no {start} から {end} までの骨子だけを作ってください。

これは全100シーン中の {act_name} パートです。

今回使う展開：
{act_text}
{extra_rule}

出力は以下の形式のみ。
JSON禁止。
Markdown禁止。
説明文禁止。

形式：
51|夜。ユリは一人、病室の片付けをする。
52|高橋さんが静かに近づいてくる。
53|ユリはため息をつく。

条件：
- scene_no {start} から {end} までのみ出力
- 各summaryは30〜80文字
- narration, image_prompt, motion_prompt は書かない
- 起承転結が分かるようにする
- 同じ展開を繰り返さない

重要：
必ず次の形式だけで出力すること。

{start}|要約
{start + 1}|要約
{start + 2}|要約

JSONを書いてはいけない。
{{ }} を使ってはいけない。
"scene_no" や "summary" という文字を書いてはいけない。
番号を飛ばしてはいけない。
scene_no {start} から {end} まで、全番号を1行ずつ出力すること。

設計書：
{json.dumps(design_json, ensure_ascii=False, indent=2)}
"""

        predict = 16000

        outline_text = ask_cached(
            outline_prompt,
            filename=f"02_outline_{start:03d}_{end:03d}_raw.txt",
            json_mode=False,
            num_predict=4096,
        )

        try:
            part = parse_pipe_outline(outline_text, start, end)
        except Exception as e:
            print(f"ERROR: outline {start}-{end} parse failed: {e}")
            print(outline_text)
            raise SystemExit(1)

        print(f"outline {start}-{end}: {len(part)}")

        if len(part) != 25:
            print(f"ERROR: outline {start}-{end} が {len(part)} 件です")
            print(outline_text)
            raise SystemExit(1)

        for x in part:
            outline.append({
                "scene_no": int(x["scene_no"]),
                "summary": x["summary"]
            })

    outline = sorted(outline, key=lambda x: x["scene_no"])

    outline_path.write_text(
        json.dumps(outline, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

print(f"outline scenes: {len(outline)}")


# 3. 5シーンずつナレーション化
narration_path = OUTDIR / "03_scenes_narration.json"

character_names = "\n".join(
    f"- {c['name']}"
    for c in design_json["characters"]
)

if narration_path.exists():
    narration_scenes = json.loads(narration_path.read_text(encoding="utf-8"))["scenes"]
    print(f"skip (cached): 03_scenes_narration.json ({len(narration_scenes)} scenes)")
else:
    narration_scenes = []

    for start in range(1, 101, 5):
        end = start + 4
        chunk_outline = [
            x for x in outline
            if start <= int(x["scene_no"]) <= end
        ]

        if not chunk_outline:
            continue

        narration_prompt = f"""
{BASE}

以下のシーン骨子を、ナレーション本文に詳細化してください。

出力は以下の形式のみ。
JSON禁止。
Markdown禁止。
説明文禁止。

形式：
{start}|ナレーション本文
{start + 1}|ナレーション本文
{start + 2}|ナレーション本文

重要：
絶対に 1 から始めないこと。
今回の開始番号は {start} です。
必ず {start}| から始めて、{end}| で終えること。

設計書：

{design_text}

重要ルール：

ナレーション中の登場人物名は上記の設計書のnameから正確に引用すること。

条件：
- scene_no {start} から {end} までのみ出力
- 各narrationは120〜260文字
- ナレーションだけで状況が分かるようにする
- 登場人物の行動、会話、周囲の反応を入れる
- 心理描写だけで終わらせない
- 骨子の流れを守る
- 主人公名は固定する

シーン骨子：
{json.dumps(chunk_outline, ensure_ascii=False, indent=2)}
"""

        text = ask_cached(
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
            raise SystemExit(1)

        for item in part:
            if "scene_no" in item and "narration" in item:
                narration_scenes.append({
                    "scene_no": int(item["scene_no"]),
                    "narration": item["narration"].strip()
                })

        print(f"narration {start}-{end} done")

    narration_scenes = sorted(narration_scenes, key=lambda x: x["scene_no"])

    narration_path.write_text(
        json.dumps({
            "title": MOVIE_THEME,
            "synopsis": "",
            "scenes": narration_scenes
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

print(f"narration scenes: {len(narration_scenes)}")


# 4. 各シーンに映像プロンプト追加
final_story_path = OUTDIR / "final_story.json"

if final_story_path.exists():
    final_data = json.loads(final_story_path.read_text(encoding="utf-8"))
    print(f"skip (cached): final_story.json ({len(final_data['scenes'])} scenes)")
    print("完成:", final_story_path)
    print(f"final scenes: {len(final_data['scenes'])}")
    raise SystemExit(0)

final_scenes = []

for scene in narration_scenes:
    scene_no = scene["scene_no"]
    narration_text = scene["narration"]

    visual_prompt = f"""
Create image_prompt and motion_prompt.

Output JSON only.

Format:
{{
  "scene_no": {scene_no},
  "image_prompt": "...",
  "motion_prompt": "..."
}}

Design Document:
{design_text}

IMPORTANT:
- Use only character names from the design document.
- Do not translate names.
- Do not romanize names.
- Do not describe age.
- Do not describe gender.
- Do not describe clothing.
- Do not describe appearance.
- Do not create new characters.
- Character appearance will be injected automatically.

When referring to a character inside image_prompt or motion_prompt:

Use the exact character name from the design document.

Never use:
- English names
- Romanized names
- Nicknames
- Shortened names

Correct(example):
神崎健司

Incorrect(examples):
Kenji Kanzaki
Kanzaki
Kenji
Mr. Kanzaki

Do not create new characters.

Only characters defined in the design document may appear.

If a character is not defined in the design document,
do not mention that character.

Output rules:
- image_prompt: English
- motion_prompt: English

Narration:
{narration_text}
"""
    visual_text = ask_cached(
        visual_prompt,
        filename=f"visual_{scene_no:03d}.json",
        json_mode=True,
        num_predict=1024,
    )

    fallback = {
        "scene_no": scene_no,
        "image_prompt": "Japanese nursing home, cinematic, photorealistic, realistic lighting, high detail, elderly Japanese residents and care staff",
        "motion_prompt": "cinematic video scene, realistic human movement, natural facial expression, smooth camera movement, no fast action"
    }

    visual = safe_json_loads(visual_text, fallback)

    image_prompt = visual.get("image_prompt", fallback["image_prompt"])
    motion_prompt = visual.get("motion_prompt", fallback["motion_prompt"])

    active_characters = find_active_characters(narration_text + image_prompt + motion_prompt, design_json)
    print(scene["scene_no"])
    print(active_characters)

    appearance_lines = []

    appearance_prefix = []

    for c in active_characters:
        appearance_prefix.append(
            f'{c["name"]}, {c["appearance"]}'
        )

    if appearance_prefix:
        image_prompt = ", ".join(appearance_prefix) + ", " + image_prompt
    
    final_scenes.append({
        "scene_no": scene_no,
        "image_prompt": image_prompt,
        "motion_prompt": motion_prompt,
        "narration": narration_text
    })
    print(f"visual scene {scene_no} done")

# 5. 最終保存
final_data = {
    "title": MOVIE_THEME,
    "synopsis": "",
    "characters": design_json.get("characters", []),
    "scenes": final_scenes
}

final_story_path.write_text(
    json.dumps(final_data, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("完成:", final_story_path)
print(f"final scenes: {len(final_scenes)}")