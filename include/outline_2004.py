# 2. シーン骨子作成
outline = []

CHAPTER_TEXTS = [design_json["story_structure"][f"chapter{i}"] for i in range(1, 9)]

CHAPTER_DESCRIPTIONS = [
    "導入・問題提起\n「なぜ○○なのか？」\n「○○とは何か？」",
    "背景・基礎知識\nテーマを理解するために必要な知識",
    "本題①\n最初の重要ポイント・出来事の経緯",
    "本題②\nさらに詳しく解説",
    "核心・仕組み・原因・因果関係",
    "テーマから導かれる結論・その後どうなったか",
    "他分野や現代との関係",
    "重要ポイントの整理",
]

# 8章をVIDEO_LENGTHに応じて比例配分する。
# 固定5シーン刻み(STEP)だとVIDEO_LENGTHを短縮した際に、
# chapter7・chapter8(他分野との関連・重要ポイントの整理)が
# 一度も生成されないまま終わる不具合があったため、動的に算出する
CHAPTER_BOUNDARIES = [1 + (VIDEO_LENGTH * i) // 8 for i in range(8)] + [VIDEO_LENGTH + 1]

for chapter_index in range(8):
    start = CHAPTER_BOUNDARIES[chapter_index]
    end = CHAPTER_BOUNDARIES[chapter_index + 1] - 1

    if start > VIDEO_LENGTH:
        break
    if end < start:
        continue

    act_name = f"第{chapter_index + 1}段階"
    act_text = CHAPTER_TEXTS[chapter_index]
    extra_rule = f"""
このシーンはchapter{chapter_index + 1}です。
{CHAPTER_DESCRIPTIONS[chapter_index]}
"""

    # 各chapterは設計書(抽象的な章立て)しか見ておらず、それ以前のchapterで
    # 実際にどこまで説明済みかを知らない。そのため後のchapterが既出の内容を
    # 重複して説明し直してしまうことがあったため、これまでに実際に作られた
    # 骨子を渡し、重複を避けさせる
    prior_outline_context = ""
    if outline:
        prior_lines = "\n".join(f"{x['scene_no']}|{x['summary']}" for x in outline)
        prior_outline_context = f"""
これまでに実際に作られたシーン骨子(続きとして書く際の参考。既にここで
説明済みの内容を重複して繰り返さないこと):
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
{start}|要約
{start + 1}|要約
{start + 2}|要約

条件：
- scene_no {start} から {end} までのみ出力
- 各summaryは30〜80文字
- narration, image_prompt, motion_prompt は書かない
- 時系列または因果関係の流れが分かるようにする
- 既に説明済みの内容を繰り返さない

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
