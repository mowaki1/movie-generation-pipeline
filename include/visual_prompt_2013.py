visual_prompt = f"""
Create image_prompt and motion_prompt.

Output JSON only.

Format:
{{
  "scene_no": {scene_no},
  "image_prompt": "...",
  "motion_prompt": "..."
}}

Design Document:
{design_text}

IMPORTANT:
- Use only character names from the design document.
- Do not translate names.
- Do not romanize names.
- Do not describe age.
- Do not describe gender.
- Do not describe clothing.
- Do not describe appearance.
- Do not create new characters.
- Character appearance will be injected automatically.

When referring to a character inside image_prompt or motion_prompt:

Use the exact character name from the design document.

Never use:
- English names
- Romanized names
- Nicknames
- Shortened names

Correct(example):
神崎健司

Incorrect(examples):
Kenji Kanzaki
Kanzaki
Kenji
Mr. Kanzaki

Do not create new characters.

Only characters defined in the design document may appear.

If a character is not defined in the design document,
do not mention that character.

Please describe the image in detailed English based on the narration.
The image must accurately reflect the historical scene, time period, location, people, architecture, clothing, weapons, technology, and atmosphere described in the narration.
Infer these details from the narration whenever they are not explicitly stated.
Maintain historical accuracy and cultural authenticity.
Avoid modern objects, anachronisms, or elements from unrelated countries or cultures.
The generated image should look like a high-quality historical documentary.
If the narration describes Japanese history, depict ethnically Japanese people with historically accurate Japanese architecture, clothing, weapons, landscapes, and cultural elements appropriate for that specific era.
Do not depict European people, Western architecture, or Western weapons unless they are explicitly mentioned in the narration.

Output rules:
- image_prompt: English
- motion_prompt: English

Narration:
{narration_text}
"""
