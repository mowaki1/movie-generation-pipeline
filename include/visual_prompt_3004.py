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
桐生誠一

Incorrect(examples):
Seiichi Kiryu
Kiryu
Seiichi
Mr. Kiryu

Do not create new characters.

Only characters defined in the design document may appear.

If a character is not defined in the design document,
do not mention that character.

Please describe the image in detailed English based on the narration.
This is a present-day, contemporary Japan educational/practical show, not a historical piece.
The image must accurately reflect modern-day Japanese settings, people, smartphones, computers, apps, home/office interiors, and everyday objects described in the narration.
Infer these details from the narration whenever they are not explicitly stated.
Maintain realism and cultural authenticity for present-day Japan.
Avoid historical costumes, period architecture, or anachronistic elements unless explicitly mentioned in the narration.
The generated image should look like a high-quality modern educational documentary or explainer video.
Depict ethnically Japanese people in a contemporary Japanese setting (modern homes, offices, cafes, streets) unless the narration explicitly describes a different country.
Do not depict European people or Western settings unless they are explicitly mentioned in the narration.

Diffusion models cannot reliably render legible text, especially long or complex text.
However, short well-known literal terms (roughly 4-6 characters, e.g. "NISA", "iDeCo")
have a much higher chance of rendering correctly than free-form sentences or multi-item
lists. If the narration mentions a specific short term, product name, or service name,
you may include that exact literal word as a label in the image_prompt (e.g., a chart
labeled "NISA" or "iDeCo"). Do NOT invent or write out longer text such as full legends,
axis labels, multiple data labels, sentences, or on-screen UI text; describe those parts
of the chart, graph, whiteboard, document, or screen as blurred, abstract, or out-of-focus
instead.

Output rules:
- image_prompt: English
- motion_prompt: English

Narration:
{narration_text}
"""
