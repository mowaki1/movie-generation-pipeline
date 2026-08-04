visual_text = ask(
    visual_prompt,
    filename=f"visual_{scene_no:03d}.json",
    num_predict=1024,
)

fallback = {
    "scene_no": scene_no,
    "image_prompt": "modern educational documentary,cinematic,photorealistic",
    "motion_prompt": "slow cinematic camera"
}

visual = safe_json_loads(visual_text, fallback)

image_prompt = visual.get("image_prompt", fallback["image_prompt"])
motion_prompt = visual.get("motion_prompt", fallback["motion_prompt"])

active_characters = find_active_characters(narration_text + image_prompt + motion_prompt, design_json)
print(scene["scene_no"])
print(active_characters)

appearance_lines = []

MODERN_PREFIX = """
photorealistic,
high-quality modern educational documentary,
cinematic lighting,
present-day contemporary Japan,
culturally authentic,
avoid historical costumes and period settings,
""".strip()

appearance_prefix = []

for c in active_characters:
    appearance_prefix.append(
        f'({c["name"]}: {c["appearance"]})'
    )

for c in active_characters:
    motion_prompt = motion_prompt.replace(c["name"], f'{c["name"]} ({c["appearance"]})')

prefix = MODERN_PREFIX

if appearance_prefix:
    prefix += ", " + ", ".join(appearance_prefix)

image_prompt = prefix + ", " + image_prompt

final_scenes.append({
    "scene_no": scene_no,
    "image_prompt": image_prompt,
    "motion_prompt": motion_prompt,
    "narration": narration_text
})
print(f"visual scene {scene_no} done")
