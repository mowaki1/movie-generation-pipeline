# 2. 100シーン骨子作成
outline = []
chapter1 = design_json["story_structure"]["chapter1"]
chapter2 = design_json["story_structure"]["chapter2"]
chapter3 = design_json["story_structure"]["chapter3"]
chapter4 = design_json["story_structure"]["chapter4"]
chapter5 = design_json["story_structure"]["chapter5"]
chapter6 = design_json["story_structure"]["chapter6"]
chapter7 = design_json["story_structure"]["chapter7"]
chapter8 = design_json["story_structure"]["chapter8"]

for start in range(1, VIDEO_LENGTH + 1, STEP):
    end = start + STEP - 1

    if start == 1:
        act_name = "第1段階"
        act_text = design_json["story_structure"]["chapter1"]
        extra_rule = f"""
この5シーンはchapter1です。
導入・問題提起
「なぜ○○なのか？」
「○○とは何か？」
"""
    if start == 6:
        act_name = "第2段階"
        act_text = design_json["story_structure"]["chapter2"]
        extra_rule = f"""
この5シーンはchapter2です。
背景・基礎知識
テーマを理解するために必要な知識
"""
    elif start == 11:
        act_name = "第3段階"
        act_text = design_json["story_structure"]["chapter3"]
        extra_rule = f"""
この5シーンはchapter3です。
本題①
最初の重要ポイント
"""
    elif start == 16:
        act_name = "第4段階"
        act_text = design_json["story_structure"]["chapter4"]
        extra_rule = f"""
この5シーンはchapter4です。
本題②
さらに詳しく解説
"""
    elif start == 21:
        act_name = "第5段階"
        act_text = design_json["story_structure"]["chapter5"]
        extra_rule = f"""
この5シーンはchapter5です。
核心・仕組み・原因・流れなど
"""
    elif start == 26:
        act_name = "第6段階"
        act_text = design_json["story_structure"]["chapter6"]
        extra_rule = f"""
この5シーンはchapter6です。
テーマから導かれる結論
"""
    elif start ==31:
        act_name = "第7段階"
        act_text = design_json["story_structure"]["chapter7"]
        extra_rule = f"""
この5シーンはchapter7です。
他分野や現代との関係
"""
    elif start == 36:
        act_name = "第8段階"
        act_text = design_json["story_structure"]["chapter8"]
        extra_rule = f"""
この5シーンはchapter8です。
重要ポイントの整理
"""
    outline_prompt = f"""
{BASE}

以下の設計書に従い、scene_no {start} から {end} までの骨子だけを作ってください。

これは全{VIDEO_LENGTH}シーン中の {act_name} パートです。

今回使う展開：
{act_text}
{extra_rule}

出力は以下の形式のみ。
JSON禁止。
Markdown禁止。
説明文禁止。

形式：
{start}|要約
{start + 1}|要約
{start + 2}|要約
{start + 3}|要約
{start + 4}|要約

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

    outline_text = ask(
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
        raise SystemExit

    print(f"outline {start}-{end}: {len(part)}")

    if len(part) != STEP:
        print(f"ERROR: outline {start}-{end} が {len(part)} 件です")
        print(outline_text)
        raise SystemExit
    
    for x in part:
        outline.append({
            "scene_no": int(x["scene_no"]),
            "summary": x["summary"]
        })
