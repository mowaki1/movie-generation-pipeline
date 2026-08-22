
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
- charactersには、視聴者に語りかける現代の案内役の講師を1人必ず含める(現代的な服装で描写する)
- テーマが実在の歴史的出来事(政治スキャンダル、戦後経済史など)である場合、必要な範囲で
  その出来事の関係者(実在の政治家・経営者等)をcharactersに追加してよい。その場合、
  appearanceには当時の年代に応じた時代考証(服装・髪型)を入れること
- テーマが現代の仕組み・現象の解説(特定の歴史上の人物が主役でないもの)である場合、
  案内役の講師以外のcharactersは追加しなくてよい
- characterには必ず name, role, age, appearance を入れる
- name はVOICEVOX(音声合成)が正しく読み上げられるよう、一般的で読み間違えられにくい
  氏名にすること。難読漢字やいわゆるキラキラネーム(独特な当て字・特殊な読み方)は避ける
  (実在の人物名は除く)
- appearance はFlux向けの英語プロンプトにする
- appearance には年齢、性別、髪型、服装、表情、雰囲気を入れる
- appearance には人種・民族的背景を必ず明記すること(日本の政治経済がテーマの場合は基本的に"Japanese"、海外の出来事の場合はその国・地域の人種を正確に反映させる。空欄や省略は禁止)
- まだ本文やシーン本文は書かない

重要：
必ず story_structure を出力すること。
story_structure には必ず chapter1, chapter2, chapter3, chapter4, chapter5, chapter6, chapter7, chapter8 を入れること。
この8個のキーを省略してはいけない。
"""
