# 2. 100シーン骨子作成
outline = []
act1 = design_json["story_structure"]["act1"]
act2 = design_json["story_structure"]["act2"]
act3 = design_json["story_structure"]["act3"]
act4 = design_json["story_structure"]["act4"]
act5 = design_json["story_structure"]["act5"]
act6 = design_json["story_structure"]["act6"]
act7 = design_json["story_structure"]["act7"]
act8 = design_json["story_structure"]["act8"]
act9 = design_json["story_structure"]["act9"]
act10 = design_json["story_structure"]["act10"]

for start in range(1, VIDEO_LENGTH + 1, STEP):
    end = start + STEP - 1

    if start == 1:
        act_name = "第1段階"
        act_text = design_json["story_structure"]["act1"]
        extra_rule = f"""
この10シーンはAct1です。
主人公紹介・現状・問題提起
"""
    elif start == 11:
        act_name = "第2段階"
        act_text = design_json["story_structure"]["act2"]
        extra_rule = f"""
この10シーンはAct2です。
最初の失敗・視聴者を引き込む事件
"""
    elif start == 21:
        act_name = "第3段階"
        act_text = design_json["story_structure"]["act3"]
        extra_rule = f"""
この10シーンはAct3です。
問題が悪化・孤立・葛藤 
"""
    elif start == 31:
        act_name = "第4段階"
        act_text = design_json["story_structure"]["act4"]
        extra_rule = f"""
この10シーンはAct4です。
希望が見える・味方登場 
"""
    elif start == 41:
        act_name = "第5段階"
        act_text = design_json["story_structure"]["act5"]
        extra_rule = f"""
この10シーンはAct5です。
大きな挫折・絶望
"""
    elif start == 51:
        act_name = "第6段階"
        act_text = design_json["story_structure"]["act6"]
        extra_rule = f"""
この10シーンはAct6です。
師匠・入居者・同僚から学ぶ 
"""
    elif start == 61:
        act_name = "第7段階"
        act_text = design_json["story_structure"]["act7"]
        extra_rule = f"""
この10シーンはAct7です。
主人公が変わり始める
"""
    elif start == 71:
        act_name = "第8段階"
        act_text = design_json["story_structure"]["act8"]
        extra_rule = f"""
この10シーンはAct8です。
最大の試練・クライマックス前
"""
    elif start == 81:
        act_name = "第9段階"
        act_text = design_json["story_structure"]["act9"]
        extra_rule = f"""
この10シーンはAct9です。
大逆転・感動シーン
"""
    else:
        act_name = "第10段階"
        act_text = design_json["story_structure"]["act10"]
        extra_rule = f"""
この25シーンはAct10です。
エピローグ・教訓・余韻
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
