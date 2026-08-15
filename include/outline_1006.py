# 2. シーン骨子作成
outline = []

ACT_TEXTS = [design_json["story_structure"][f"act{i}"] for i in range(1, 11)]

ACT_DESCRIPTIONS = [
    "主人公紹介・現状・問題提起",
    "最初の失敗・視聴者を引き込む事件",
    "問題が悪化・孤立・葛藤",
    "希望が見える・味方登場",
    "大きな挫折・絶望",
    "師匠・入居者・同僚から学ぶ",
    "主人公が変わり始める",
    "最大の試練・クライマックス前",
    "大逆転・感動シーン",
    "エピローグ・教訓・余韻",
]

# YouTube視聴維持率の実測データで、Act1(静かな現状紹介)から入る構成だと
# 冒頭数分で視聴者の大半が離脱していることが判明した。そのため本編の前に、
# クライマックス(Act9)を断片的に見せる「コールドオープン」を挿入し、
# 「なぜこうなったのか」で本編に引き込む構成にする
TEASER_SCENES = 2
CLIMAX_TEXT = design_json["story_structure"]["act9"]

teaser_prompt = f"""
{BASE}

以下の設計書のクライマックス(第9段階)の展開を使い、動画の冒頭に置く
「コールドオープン(掴み)」の骨子を scene_no 1 から {TEASER_SCENES} までだけ作ってください。

クライマックスの展開：
{CLIMAX_TEXT}

これは本編ではなく、視聴者を引き込むための予告的な冒頭シーンです。

条件：
- 状況の全てを説明せず、断片的・示唆的な描写に留める(何が起きたのか気になる終わり方にする)
- 感情が最も動く一瞬(表情、セリフ、行動)を切り取る
- 「なぜこうなったのか」を視聴者が知りたくなるように終える
- 各summaryは30〜80文字
- narration, image_prompt, motion_prompt は書かない

出力は以下の形式のみ。
JSON禁止。
Markdown禁止。
説明文禁止。

形式：
1|要約
2|要約

重要：
必ず次の形式だけで出力すること。
JSONを書いてはいけない。
{{ }} を使ってはいけない。
"scene_no" や "summary" という文字を書いてはいけない。
scene_no 1 から {TEASER_SCENES} まで、全番号を1行ずつ出力すること。

設計書：
{json.dumps(design_json, ensure_ascii=False, indent=2)}
"""

TEASER_MAX_RETRIES = 3
teaser_part = None
for attempt in range(1, TEASER_MAX_RETRIES + 1):
    teaser_text = ask(
        teaser_prompt,
        filename="02_outline_teaser_raw.txt",
        num_predict=2048,
    )

    try:
        candidate = parse_pipe_outline(teaser_text, 1, TEASER_SCENES)
    except Exception as e:
        print(f"teaser outline parse failed (試行 {attempt}/{TEASER_MAX_RETRIES}): {e}")
        continue

    if len(candidate) != TEASER_SCENES:
        print(f"teaser outline が {len(candidate)} 件でした (試行 {attempt}/{TEASER_MAX_RETRIES})")
        continue

    teaser_part = candidate
    break

if teaser_part is None:
    print(f"ERROR: teaser outlineが{TEASER_MAX_RETRIES}回試行しても失敗しました")
    print(teaser_text)
    raise SystemExit(1)

for x in teaser_part:
    outline.append({
        "scene_no": int(x["scene_no"]),
        "summary": x["summary"]
    })

print(f"teaser outline: {len(teaser_part)}")

# 10段階(Act)を、コールドオープン分を除いた残りシーン数に応じて比例配分する。
# 固定10シーン刻み(STEP)だとVIDEO_LENGTHを短縮した際に、
# Act7以降(クライマックス・大逆転・エピローグ)が一度も生成されず
# 物語が完結しないまま終わる不具合があったため、動的に算出する
REMAINING_LENGTH = VIDEO_LENGTH - TEASER_SCENES
ACT_BOUNDARIES = [TEASER_SCENES + 1 + (REMAINING_LENGTH * i) // 10 for i in range(10)] + [VIDEO_LENGTH + 1]

for act_index in range(10):
    start = ACT_BOUNDARIES[act_index]
    end = ACT_BOUNDARIES[act_index + 1] - 1

    if start > VIDEO_LENGTH:
        break
    if end < start:
        continue

    act_name = f"第{act_index + 1}段階"
    act_text = ACT_TEXTS[act_index]
    extra_rule = f"""
このシーンは{act_name}です。
{ACT_DESCRIPTIONS[act_index]}
"""

    # Actごとに別々のLLM呼び出しでoutlineを生成しているため、後のActは前の
    # Actで実際にどんな骨子が書かれたか(design_jsonの抽象的な構成ではなく、
    # 具体的に設定された危機・課題そのもの)を知らない。そのため、序盤で
    # 大きく張った伏線(経済的損失、身体的な衰え等)が終盤で一切回収されずに
    # 放置される不具合があった。ここまでに実際に生成された骨子を渡し、
    # 伏線を意識して書けるようにする
    prior_outline_context = ""
    if outline:
        prior_lines = "\n".join(f"{x['scene_no']}|{x['summary']}" for x in outline)
        prior_outline_context = f"""
これまでに実際に作られたシーン骨子(続きとして書く際の参考。ここで設定された
危機・課題・障害は、放置せず、この後の段階のどこかで必ず結末をつけること):
{prior_lines}
"""

    outline_prompt = f"""
{BASE}

以下の設計書に従い、scene_no {start} から {end} までの骨子だけを作ってください。

これは全{VIDEO_LENGTH}シーン中の {act_name} パートです。

今回使う展開：
{act_text}
{extra_rule}
{prior_outline_context}

出力は以下の形式のみ。
JSON禁止。
Markdown禁止。
説明文禁止。

形式：
{start}|夜。ユリは一人、病室の片付けをする。
{start + 1}|高橋さんが静かに近づいてくる。
{start + 2}|ユリはため息をつく。

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
    part = generate_outline_with_continuation(outline_prompt, start, end)
    print(f"outline {start}-{end}: {len(part)}")

    for x in part:
        outline.append({
            "scene_no": int(x["scene_no"]),
            "summary": x["summary"]
        })
