
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
      "name": "...",
      "role": "主人公",
      "age": 60,
      "appearance": "age, gender, ethnicity appropriate to the era/region, hairstyle, clothing of that time and place, facial expression, atmosphere"
    }}
  ],
  "story_structure": {{
    "chapter1": "...",
    "chapter2": "...",
    "chapter3": "...",
    "chapter4": "...",
    "chapter5": "...",
    "chapter6": "...",
    "chapter7": "...",
    "chapter8": "...",
  }}
}}

条件：
- charactersは必要な場合のみ
- characterがいる場合、各characterには必ず name, role, age, appearance を入れる
- appearance は時代考証を入れる
- appearance はFlux向けの英語プロンプトにする
- appearance には年齢、性別、髪型、服装、表情、雰囲気を入れる
- appearance には人種・民族的背景を必ず明記すること(その時代・地域に実在した人々の人種を正確に反映させる。テーマが日本の歴史なら日本人、古代エジプトならエジプト人、ヨーロッパならヨーロッパ人など、空欄や省略は禁止)
- まだ本文やシーン本文は書かない

重要：
必ず story_structure を出力すること。
story_structure には必ず chapter1, chapter2, chapter3, chapter4, chapter5, chapter6, chapter7, chapter8 を入れること。
この8個のキーを省略してはいけない。
"""
