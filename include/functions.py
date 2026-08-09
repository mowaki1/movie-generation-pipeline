
GARBLED_BYTE_TOKEN_RE = re.compile(r"<0x[0-9A-Fa-f]{2}>")

LEAKED_SPECIAL_TOKENS = ["<|im_end|>", "<|eot_id|>", "<|end_of_text|>", "<|im_start|>"]
# stopオプションに渡す厳密な文字列とは別に、実際にはトークンの区切り記号が
# "<\|im_end|>"のようにバックスラッシュを挟む形で崩れて漏れることがあった。
# 装飾記号のブレを吸収するため、トークン名の部分一致で検出する
LEAKED_TOKEN_MARKERS = ["im_end", "im_start", "eot_id", "end_of_text"]


def has_garbled_byte_tokens(text):
    # llama.cpp/Ollama側がUTF-8として正しく組み立てられなかったトークンを
    # "<0xE6>"のようなバイト表記のまま出力してしまうことがある(特に日本語の
    # 漢字生成時)。これはPython側の文字化けではなく生成結果自体の破損なので、
    # 検出したら再試行する
    return bool(GARBLED_BYTE_TOKEN_RE.search(text))


def strip_leaked_special_tokens(text):
    # optionsのstopで指定していても、Ollamaがstop文字列を完全には
    # response から除去しきれず、地の文と同じ行に混入することがある
    # (実測: 骨子/ナレーションの最終行末尾に"<\|im_end|>"のような崩れた
    # 形で可視文字として残る)。stopによる一次防御に加え、万一混入した
    # 場合の二次防御として、トークン名が最初に現れた箇所(装飾記号ごと)
    # 以降を切り捨てる
    earliest = None
    for marker in LEAKED_TOKEN_MARKERS:
        idx = text.find(marker)
        if idx == -1:
            continue
        cut_start = idx
        while cut_start > 0 and text[cut_start - 1] in "<|\\":
            cut_start -= 1
        if earliest is None or cut_start < earliest:
            earliest = cut_start
    return text[:earliest] if earliest is not None else text


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
            # 同じ短いフレーズを延々と繰り返す劣化出力(repetition loop)が
            # 稀に発生した(例: "<br>"が数百回続く)ことへの緩和策
            "repeat_penalty": 1.15,
            # Swallow(hf.co経由のGGUF)へ切り替えた際、チャットテンプレートの
            # 終了トークンがOllamaの/api/generate(生の補完API)で正しく解釈
            # されず、"<|im_end|>"等が可視文字として出力され、そこで生成が
            # 早期に打ち切られる不具合が見つかった(outlineの最終シーンが
            # 欠落する形で発覚)。明示的にstopとして指定し、混入・早期打ち切り
            # 両方を防ぐ
            "stop": LEAKED_SPECIAL_TOKENS,
        },
    }

    for _ in range(3):
        res = requests.post(API_URL, json=payload, timeout=3000)
        res.raise_for_status()
        text = res.json().get("response", "").strip()
        text = strip_leaked_special_tokens(text).strip()

        if len(text) > 50 and not has_garbled_byte_tokens(text):
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

def extract_first_json_object(text):
    # モデル(Swallow)がJSON出力の後に余計な説明文を続けて出力することがあり、
    # json.loadsが"Extra data"で失敗する原因になっていた。ネストしたJSON内の
    # {}と衝突しないよう、波かっこの対応関係を実際に追跡して最初の完全な
    # JSONオブジェクトだけを抜き出す
    start = text.index("{")
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    raise ValueError("complete JSON object not found")

def safe_json_loads(text, fallback):
    cleaned = strip_code_fence(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(extract_first_json_object(cleaned))
    except (json.JSONDecodeError, ValueError):
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

def normalize_name(name):
    # LLMがキャラクター名を出力する際、design_json通りの表記("如月 冴子"のように
    # 姓名間にスペースあり)と、スペース無し("如月冴子")の両方が混在して出力される
    # ことがあり、単純な文字列一致だと後者を見逃して外見情報の注入に失敗する
    # (→ 民族・性別等の指定が無いまま画像生成され、西洋人として描画されてしまう)
    # ため、比較前に半角/全角スペースを除去して揺れを吸収する
    return name.replace(" ", "").replace("　", "")

def find_characters(text, design_json):
    result = []
    normalized_text = normalize_name(text)

    for c in design_json["characters"]:
        if normalize_name(c["name"]) in normalized_text:
            result.append(c)

    return result

def find_active_characters(text, design_json):
    active = []
    normalized_text = normalize_name(text)

    for c in design_json.get("characters", []):
        name = c.get("name", "")

        if not name:
            continue

        base_name = name.split("（")[0].strip()

        if normalize_name(name) in normalized_text or normalize_name(base_name) in normalized_text:
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

def _extract_pipe_scenes(text, start, end):
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
    return [unique[i] for i in sorted(unique)]

def parse_pipe_outline(text, start, end):
    scenes = _extract_pipe_scenes(text, start, end)

    expected = list(range(start, end + 1))
    actual = [x["scene_no"] for x in scenes]

    if actual != expected:
        raise ValueError(f"outline番号不一致: expected={expected}, actual={actual}")

    return scenes

def generate_outline_with_continuation(outline_prompt, start, end, max_retries=3, num_predict=4096, filename_prefix="02_outline"):
    # 骨子生成の最終盤で、モデルが要求件数の途中(例:4件中3件目)で
    # 自ら応答を終えてしまい、フルリトライしても毎回同じ箇所で
    # 打ち切られる不具合があった。ゼロからやり直す代わりに、生成できた
    # 分はそのまま採用し、不足分だけを追加生成することで回収する
    expected_count = end - start + 1
    outline_text = ""
    for attempt in range(1, max_retries + 1):
        outline_text = ask(
            outline_prompt,
            filename=f"{filename_prefix}_{start:03d}_{end:03d}_raw.txt",
            num_predict=num_predict,
        )

        candidate = _extract_pipe_scenes(outline_text, start, end)

        if len(candidate) == expected_count:
            return candidate

        got = {x["scene_no"] for x in candidate}
        missing = [n for n in range(start, end + 1) if n not in got]
        if candidate and missing and missing[-1] - missing[0] + 1 == len(missing):
            continued = _continue_outline(outline_prompt, candidate, missing, num_predict)
            if continued is not None:
                merged = sorted(candidate + continued, key=lambda x: x["scene_no"])
                if len(merged) == expected_count:
                    return merged

        print(f"outline {start}-{end} が {len(candidate)} 件でした (試行 {attempt}/{max_retries})")

    print(f"ERROR: outline {start}-{end} が{max_retries}回試行しても失敗しました")
    print(outline_text)
    raise SystemExit(1)

def _continue_outline(outline_prompt, candidate, missing, num_predict):
    written = "\n".join(f"{x['scene_no']}|{x['summary']}" for x in candidate)
    continuation_prompt = f"""
{outline_prompt}

ここまで、以下のscene_noまで骨子を書きました。これらは書き直さないでください。
{written}

続きとして、scene_no {missing[0]} から {missing[-1]} までの骨子だけを追加で書いてください。

出力は以下の形式のみ。
{missing[0]}|要約
"""
    text = ask(continuation_prompt, num_predict=num_predict)
    continued = _extract_pipe_scenes(text, missing[0], missing[-1])
    return continued if len(continued) == len(missing) else None

def is_repetition_garbage(text):
    # モデルが同じ短いフレーズ("<br>"等)を延々と繰り返すループに陥り、
    # num_predict上限まで埋め尽くす劣化出力が稀に発生した。先頭の短い
    # 断片が全体の過半を占める場合、正常な文章ではなく壊れた出力とみなす
    stripped = text.strip()
    if len(stripped) < 100:
        return False
    for chunk_len in (4, 6, 8, 10, 12):
        if len(stripped) < chunk_len * 5:
            continue
        chunk = stripped[:chunk_len]
        if chunk.strip() and stripped.count(chunk) * chunk_len > len(stripped) * 0.5:
            return True
    return False

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
            if start <= scene_no <= end and not is_repetition_garbage(narration):
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
            if start <= scene_no <= end and not is_repetition_garbage(narration):
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
