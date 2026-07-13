
def ask(prompt, filename=None, num_predict=4096):
    # 注意: "format": "json" (文法制約付きデコーディング)はgemma4:31b-it-bf16で
    # 出力が"own own own..."のように壊れる不具合があるため使用しない。
    # プロンプト側の指示とrepair_json_array/safe_json_loadsのフェンス除去で代替する。
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

def strip_code_fence(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()

def safe_json_loads(text, fallback):
    try:
        return json.loads(strip_code_fence(text))
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
