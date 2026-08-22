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
王貞治

Incorrect(examples):
Sadaharu Oh
Oh
Sadaharu
Mr. Oh

Do not create new characters.

Only characters defined in the design document may appear.

If a character is not defined in the design document,
do not mention that character.

Please describe the image in detailed English based on the narration.
This is a documentary about the history of a specific sport in Japan.
The image must accurately reflect the era described in the narration: the correct sport, uniforms, equipment, stadium or venue architecture, spectator style, and general atmosphere for that specific decade.
Infer the correct era and sport from the narration whenever they are not explicitly stated.
Maintain historical accuracy for sports equipment, uniforms, and venues (for example, do not depict modern stadium screens or modern uniform designs in a scene set in the 1950s).
Depict Japanese people and settings unless the narration explicitly describes a different country.
The generated image should look like a high-quality sports documentary.

Diffusion models cannot reliably render legible text, so requesting it produces garbled,
unreadable characters. Do NOT describe readable text, numbers, scoreboards, uniform numbers,
labels, or on-screen UI text in the image_prompt. If the narration mentions a scoreboard,
sign, newspaper, or screen, describe it as a blurred, abstract, or out-of-focus visual element
without legible text or data labels.

Output rules:
- image_prompt: English
- motion_prompt: English

Narration:
{narration_text}
"""
