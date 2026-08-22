fallback = {
    "scene_no": scene_no,
    "image_prompt": "sports history documentary,cinematic,photorealistic",
    "motion_prompt": "slow cinematic camera"
}

# LLMがJSON形式で応答できず解析に失敗すると、リトライ無しで即座に上記の
# 汎用フォールバックに差し替わり、そのシーン固有の人物・時代の手がかりが
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

HISTORY_PREFIX = """
historically accurate,
high-quality sports documentary,
photorealistic,
cinematic lighting,
culturally authentic,
avoid anachronisms,
""".strip()

appearance_prefix = []

for c in active_characters:
    appearance_prefix.append(
        f'({c["name"]}: {c["appearance"]})'
    )

for c in active_characters:
    motion_prompt = motion_prompt.replace(c["name"], f'{c["name"]} ({c["appearance"]})')

# CLIPテキストエンコーダーは77トークンまでしか読めず、それを超えた部分は
# 切り捨てられる(T5側は512トークンまで読めるが、FLUXはCLIPとT5の出力を
# 連結して使うため、CLIP側が見る内容も画像の構図に影響する)。人物の外見
# 描写を先頭に置くと、複数人物がいるシーンではそれだけで77トークンを超え、
# 肝心のシーン内容(場面・行動)がCLIP側から見て存在しないのと同じ扱いに
# なってしまう。シーン内容を先に、外見描写を後ろに回すことで、CLIPの
# 77トークン以内に実際の場面描写が収まりやすくする
image_prompt = HISTORY_PREFIX + ", " + image_prompt

if appearance_prefix:
    image_prompt += ", " + ", ".join(appearance_prefix)

final_scenes.append({
    "scene_no": scene_no,
    "image_prompt": image_prompt,
    "motion_prompt": motion_prompt,
    "narration": narration_text
})
print(f"visual scene {scene_no} done")
