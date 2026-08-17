fallback = {
    "scene_no": scene_no,
    "image_prompt": "Japanese traditional house interior, cinematic, photorealistic, realistic lighting, high detail, family members",
    "motion_prompt": "cinematic video scene, realistic human movement, natural facial expression, smooth camera movement, no fast action"
}

# LLMがJSON形式で応答できず解析に失敗すると、リトライ無しで即座に上記の
# 汎用フォールバックに差し替わり、そのシーン固有の人物・文化的な手がかりが
# 完全に失われていた(重要人物が登場するシーンでも人物描写が一切無くなり、
# FLUXが無関係な人物を描いてしまう不具合があった)。数回リトライしてから
# 初めてフォールバックするようにする
VISUAL_MAX_RETRIES = 3
visual = None
for attempt in range(1, VISUAL_MAX_RETRIES + 1):
    visual_text = ask(
        visual_prompt,
        filename=f"visual_{scene_no:03d}.json",
        num_predict=1024,
    )
    candidate = safe_json_loads(visual_text, None)
    if isinstance(candidate, dict) and candidate.get("image_prompt") and candidate.get("motion_prompt"):
        visual = candidate
        break
    print(f"visual scene {scene_no} のJSON解析に失敗しました (試行 {attempt}/{VISUAL_MAX_RETRIES})")

if visual is None:
    print(f"WARNING: visual scene {scene_no} が{VISUAL_MAX_RETRIES}回試行しても解析できず、フォールバックを使用します")
    visual = fallback

image_prompt = visual.get("image_prompt", fallback["image_prompt"])
motion_prompt = visual.get("motion_prompt", fallback["motion_prompt"])

active_characters = find_active_characters(narration_text + image_prompt + motion_prompt, design_json)
print(scene["scene_no"])
print(active_characters)

appearance_lines = []

appearance_prefix = []

for c in active_characters:
    appearance_prefix.append(
        f'({c["name"]}: {c["appearance"]})'
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
