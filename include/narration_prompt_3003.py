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
- 各narrationは100〜160文字
- ナレーションだけで状況が分かるようにする
- 登場人物の行動、会話、周囲の反応を入れる
- 心理描写だけで終わらせない
- 骨子の流れを守る
- 主人公名は固定する

シーン骨子：
{json.dumps(chunk_outline, ensure_ascii=False, indent=2)}
"""
