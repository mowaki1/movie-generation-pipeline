

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
      "name": "桐生誠一",
      "role": "主人公",
      "age": 78,
      "appearance": "78-year-old Japanese man, short gray hair, deep wrinkles, sharp eyes, navy business suit, former bank vice president, dignified but lonely atmosphere"
    }}
  ],
  "story_structure": {{
    "act1": "...",
    "act2": "...",
    "act3": "...",
    "act4": "..."
  }}
}}

条件：
- characters には主要人物を3〜5人入れる
- 各characterには必ず name, role, age, appearance を入れる
- name はVOICEVOX(音声合成)が正しく読み上げられるよう、一般的で読み間違えられにくい
  氏名にすること。難読漢字やいわゆるキラキラネーム(独特な当て字・特殊な読み方)は避ける
- appearance はFlux向けの英語プロンプトにする
- appearance には年齢、性別、髪型、服装、表情、雰囲気を入れる
- まだ本文やシーン本文は書かない
- 10段階のストーリー構成。
- 対立、孤立、転落、気づき、再生を必ず入れてください。

重要：
必ず story_structure を出力すること。
story_structure には必ず act1, act2, act3, act4, act5, act6, act7, act8, act9, act10 を入れること。
この10個のキーを省略してはいけない。
"""
