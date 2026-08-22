
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
      "appearance": "age, gender, ethnicity appropriate to the era, hairstyle, clothing of that time (sportswear, uniform, or civilian clothing as appropriate), facial expression, atmosphere"
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
- charactersには、視聴者に語りかける現代の案内役を1人必ず含めること(現代的な服装で描写する)
- 案内役に加えて、紹介する実在の選手・監督・関係者がいれば必要な場合のみcharactersに追加してよい(その場合appearanceにその時代のユニフォーム・服装・髪型を入れる)
- characterがいる場合、各characterには必ず name, role, age, appearance を入れる
- name はVOICEVOX(音声合成)が正しく読み上げられるよう、一般的で読み間違えられにくい
  氏名にすること。難読漢字やいわゆるキラキラネーム(独特な当て字・特殊な読み方)は避ける
  (実在の選手・関係者名は除く)
- appearance は時代考証を入れる(その年代のユニフォーム・用具・髪型を反映する)
- appearance はFlux向けの英語プロンプトにする
- appearance には年齢、性別、髪型、服装、表情、雰囲気を入れる
- appearance には人種・民族的背景を必ず明記すること(空欄や省略は禁止)
- まだ本文やシーン本文は書かない

重要：
必ず story_structure を出力すること。
story_structure には必ず chapter1, chapter2, chapter3, chapter4, chapter5, chapter6, chapter7, chapter8 を入れること。
この8個のキーを省略してはいけない。
"""
