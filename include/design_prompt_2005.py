
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
      "appearance": ""
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
- charactersには、視聴者に語りかける案内役を1人必ず含めること(現代的な服装で、appearanceに人種・民族的背景を明記する)
- 案内役に加えて、紹介する歴史上の人物がいれば必要な場合のみcharactersに追加してよい(その場合appearanceに時代考証を入れる)
- characterがいる場合、各characterには必ず name, role, age, appearance を入れる
- name はVOICEVOX(音声合成)が正しく読み上げられるよう、一般的で読み間違えられにくい
  氏名にすること。難読漢字やいわゆるキラキラネーム(独特な当て字・特殊な読み方)は避ける
  (実在の歴史上の人物名は除く)
- appearance は時代考証を入れる
- appearance はFlux向けの英語プロンプトにする
- appearance には年齢、性別、髪型、服装、表情、雰囲気を入れる
- まだ本文やシーン本文は書かない

重要：
必ず story_structure を出力すること。
story_structure には必ず chapter1, chapter2, chapter3, chapter4, chapter5, chapter6, chapter7, chapter8 を入れること。
この8個のキーを省略してはいけない。
"""
