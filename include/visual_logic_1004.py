visual_text = ask(
    visual_prompt,
    filename=f"visual_{scene_no:03d}.json",
    num_predict=1024,
)

fallback = {
    "scene_no": scene_no,
    "image_prompt": "Japanese hospital, cinematic, photorealistic, realistic lighting, high detail, doctors, nurses and patients",
    "motion_prompt": "cinematic video scene, realistic human movement, natural facial expression, smooth camera movement, no fast action"
}

visual = safe_json_loads(visual_text, fallback)

image_prompt = visual.get("image_prompt", fallback["image_prompt"])
motion_prompt = visual.get("motion_prompt", fallback["motion_prompt"])

active_characters = find_active_characters(narration_text + image_prompt + motion_prompt, design_json)
print(scene["scene_no"])
print(active_characters)

appearance_lines = []

appearance_prefix = []

for c in active_characters:
    appearance_prefix.append(
        f'{c["name"]}, {c["appearance"]}'
    )

for c in active_characters:
    motion_prompt = motion_prompt.replace(c["name"], f'{c["name"]} ({c["appearance"]})')

if appearance_prefix:
    image_prompt = ", ".join(appearance_prefix) + ", " + image_prompt

final_scenes.append({
    "scene_no": scene_no,
    "image_prompt": image_prompt,
    "motion_prompt": motion_prompt,
    "narration": narration_text
})
print(f"visual scene {scene_no} done")
