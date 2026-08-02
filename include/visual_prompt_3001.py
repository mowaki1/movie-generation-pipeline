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

Please describe the image in detailed English based on the narration.
The image must accurately and clearly depict the specific object, animal, food, place, body part, or phenomenon described in the narration.
Use a clean, appealing, photorealistic style suitable for a modern educational YouTube video, similar to a high-quality stock photograph or short documentary clip.
Avoid unrelated or fantastical elements not mentioned in the narration.
If the narration mentions a specific animal, food, everyday object, or natural phenomenon, depict it clearly and accurately, ideally in close-up or well-composed shots that make the subject easy to understand at a glance.
If ordinary people are shown, depict modern ordinary Japanese people in everyday settings unless otherwise specified.
Do not invent named characters; this is a factual trivia video, not a drama.

Diffusion models cannot reliably render legible text, so requesting it produces garbled,
unreadable characters. Do NOT describe readable text, numbers, labels, chart axis labels,
graph data labels, or on-screen UI text in the image_prompt. If the narration mentions a
chart, graph, whiteboard, document, sign, book, or screen, describe it as a blurred, abstract,
or out-of-focus visual element without legible text or data labels.

Output rules:
- image_prompt: English
- motion_prompt: English

Narration:
{narration_text}
"""
