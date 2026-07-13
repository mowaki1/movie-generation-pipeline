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
The image must accurately reflect the historical scene, civilization, era, region, people, architecture, clothing, weapons, technology, and atmosphere described in the narration.
Infer these details from the narration whenever they are not explicitly stated.
Identify which civilization, country, or region the narration is set in (for example: ancient Egypt, ancient Greece, ancient Rome, medieval Europe, Han dynasty China, the Islamic Caliphate, the Mongol Empire, colonial America, etc.) and depict people, ethnicity, architecture, clothing, weapons, and cultural elements that are historically and geographically accurate for that specific civilization and era.
Maintain historical accuracy and cultural authenticity.
Avoid modern objects, anachronisms, or elements mixed in from an unrelated civilization, era, or region.
The generated image should look like a high-quality historical documentary.

Output rules:
- image_prompt: English
- motion_prompt: English

Narration:
{narration_text}
"""
