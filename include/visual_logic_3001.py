visual_text = ask(
    visual_prompt,
    filename=f"visual_{scene_no:03d}.json",
    num_predict=1024,
)

fallback = {
    "scene_no": scene_no,
    "image_prompt": "everyday life scene, modern Japan, cinematic, photorealistic, realistic lighting, high detail",
    "motion_prompt": "cinematic video scene, natural movement, smooth camera movement, no fast action"
}

visual = safe_json_loads(visual_text, fallback)

image_prompt = visual.get("image_prompt", fallback["image_prompt"])
motion_prompt = visual.get("motion_prompt", fallback["motion_prompt"])

TRIVIA_PREFIX = "clean modern photography style, photorealistic, high detail, natural lighting,"

image_prompt = TRIVIA_PREFIX + " " + image_prompt

print(scene["scene_no"])

final_scenes.append({
    "scene_no": scene_no,
    "image_prompt": image_prompt,
    "motion_prompt": motion_prompt,
    "narration": narration_text
})
print(f"visual scene {scene_no} done")
