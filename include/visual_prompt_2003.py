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
- Use only character names from the design document, if any are defined.
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

Do not create new characters.

Only characters defined in the design document may appear.

Please describe the image in detailed English based on the narration.
This is a contemporary geography documentary, not a historical reenactment.
The image must accurately reflect the specific country, region, city, landscape, environmental phenomenon, or social situation described in the narration, as it exists today.
Infer the specific real-world location and context from the narration whenever they are not explicitly stated.
Depict the people, clothing, architecture, and setting appropriate to that specific real country or region in the present day.
Avoid generic or stereotypical depictions; aim for a realistic, journalistic, documentary-style depiction similar to a high-quality news or documentary photograph.
Avoid historical costumes or anachronistic elements unless the narration specifically refers to the past.

Output rules:
- image_prompt: English
- motion_prompt: English

Narration:
{narration_text}
"""
