
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
      "age": 45,
      "appearance": "age, gender, Japanese ethnicity, hairstyle, modern contemporary clothing, facial expression, atmosphere"
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
- charactersには、視聴者に語りかける案内役の講師を1人必ず含める
- characterには必ず name, role, age, appearance を入れる
- appearance はFlux向けの英語プロンプトにする
- appearance には年齢、性別、髪型、服装、表情、雰囲気を入れる
- appearance には人種を必ず明記すること(現代の日本人講師として描写するため、基本的に"Japanese"を明記する。空欄や省略は禁止)
- appearance は現代日本の一般的なビジネスカジュアルな服装にする(歴史考証は不要)
- まだ本文やシーン本文は書かない

重要：
必ず story_structure を出力すること。
story_structure には必ず chapter1, chapter2, chapter3, chapter4, chapter5, chapter6, chapter7, chapter8 を入れること。
この8個のキーを省略してはいけない。
"""
