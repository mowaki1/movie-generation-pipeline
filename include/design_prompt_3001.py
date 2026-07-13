

# 1. 設計書作成
design_prompt = f"""
{BASE}

まず構成の設計書だけをJSONで作ってください。

出力はJSONのみ。
説明文禁止。
Markdown禁止。

形式：

{{
  "title": "...",
  "synopsis": "...",
  "characters": [],
  "story_structure": {{
    "chapter1": "...",
    "chapter2": "...",
    "chapter3": "...",
    "chapter4": "...",
    "chapter5": "...",
    "chapter6": "...",
    "chapter7": "...",
    "chapter8": "..."
  }}
}}

条件：
- charactersは空配列のままでよい(雑学には固定の登場人物は不要)
- story_structureの各chapterには、独立した1つの雑学ネタの概要を入れる
- 8個は互いに異なるネタにする
- まだ本文やシーン本文は書かない

重要：
必ず story_structure を出力すること。
story_structure には必ず chapter1, chapter2, chapter3, chapter4, chapter5, chapter6, chapter7, chapter8 を入れること。
この8個のキーを省略してはいけない。
"""
