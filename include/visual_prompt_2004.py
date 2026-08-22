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
田中角栄

Incorrect(examples):
Kakuei Tanaka
Tanaka
Kakuei
Mr. Tanaka

Do not create new characters.

Only characters defined in the design document may appear.

If a character is not defined in the design document,
do not mention that character.

Please describe the image in detailed English based on the narration.
This is a documentary-style explainer video about real political and economic events or mechanisms.
If the narration describes a past historical event, depict the setting, clothing, and architecture accurately for that specific era (avoid anachronisms).
If the narration describes a present-day mechanism or current situation, depict present-day contemporary settings accurately.
Infer the correct time period from the narration content whenever it is not explicitly stated.
Maintain realism and cultural/historical authenticity.
Depict people with ethnic backgrounds accurate to the country/region being discussed in the narration (Japanese for Japan-related topics, the relevant nationality for foreign topics).

Diffusion models cannot reliably render legible text, especially long or complex text.
However, short well-known literal terms (roughly 4-6 characters, e.g. institution names, headlines) have a much higher chance of rendering correctly than free-form sentences or multi-item lists. If the narration mentions a specific short name, you may include that exact literal word as a label in the image_prompt (e.g., a newspaper headline, a signboard). Do NOT invent or write out longer text such as full articles, multiple labels, sentences, or paragraphs of on-screen text; describe those parts of the screen, document, or chart as blurred, abstract, or out-of-focus instead.

Output rules:
- image_prompt: English
- motion_prompt: English

Narration:
{narration_text}
"""
