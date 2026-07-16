import json
import re
import subprocess
import sys
from pathlib import Path

import requests
import torch
from diffusers import FluxPipeline
from PIL import Image, ImageDraw, ImageFont

args = sys.argv
if len(args) < 2:
    print(f"usage: python {Path(args[0]).name} <pipeline_no>")
    raise SystemExit(1)

OUTDIR = Path(f"jobs/story_pipeline{args[1]}")

MODEL = "gemma4:31b-it-bf16"
OLLAMA_URL = "http://localhost:11434/api/generate"
FONT_NAME = "BIZ UDPGothic"  # 字幕と同じフォントで統一

THUMBNAIL_WIDTH = 1280
THUMBNAIL_HEIGHT = 720

FLUX_MODEL_ID = "black-forest-labs/FLUX.1-dev"
NEGATIVE_PROMPT = "illustration,anime,cartoon,3D render,CGI,digital painting,drawing,concept art,watermark,stock photo watermark,logo,text overlay,blurry,low quality"


def ask_ollama(prompt, num_predict=1024):
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "num_ctx": 8192,
            "num_predict": num_predict,
        },
    }
    res = requests.post(OLLAMA_URL, json=payload, timeout=300)
    res.raise_for_status()
    data = res.json()
    if "error" in data:
        raise RuntimeError(data["error"])

    text = data.get("response", "").strip()
    if not text:
        raise RuntimeError(
            f"empty response, done_reason={data.get('done_reason')!r}, "
            f"eval_count={data.get('eval_count')}"
        )
    return text


def strip_code_fence(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


CATCHPHRASE_PROMPT_TEMPLATE = """以下は動画のタイトルとあらすじです。
YouTubeサムネイルに載せる、短く強いキャッチコピーと、サムネイル用の画像生成プロンプトをJSON形式で作成してください。

タイトル: {title}
あらすじ: {synopsis}

条件:
・catchphraseは日本語で10〜15字程度、感情を煽る短い言葉にすること
・image_promptは英語で、クローズアップの感情的な構図にすること
・image_promptでは、画面の左右どちらか半分程度に文字を載せる余白ができるような構図を意識すること(人物やモノを片側に寄せる等)
・写実的(写真調)な描写にすること

出力形式(JSON以外の文字列は一切出力しないこと):
{{
  "catchphrase": "...",
  "image_prompt": "..."
}}
"""


def resolve_font_path(font_name=FONT_NAME):
    result = subprocess.run(
        ["fc-match", "-f", "%{file}", font_name],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def wrap_catchphrase(text, font, max_width):
    if font.getbbox(text)[2] <= max_width:
        return [text]

    # 中央付近で2行に分割する(句読点があればそこを優先)
    mid = len(text) // 2
    split_at = mid
    for offset in range(0, mid):
        for pos in (mid - offset, mid + offset):
            if 0 < pos < len(text) and text[pos - 1] in "、。！？":
                split_at = pos
                break
        else:
            continue
        break

    return [text[:split_at], text[split_at:]]


def draw_catchphrase(image, text, font_path):
    img = image.convert("RGB").resize((THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))
    draw = ImageDraw.Draw(img)

    font_size = 100
    font = ImageFont.truetype(font_path, font_size)
    max_width = THUMBNAIL_WIDTH - 80

    lines = wrap_catchphrase(text, font, max_width)
    line_height = font.getbbox("あ")[3] + 20
    total_height = line_height * len(lines)
    y = THUMBNAIL_HEIGHT - total_height - 50

    for line in lines:
        bbox = font.getbbox(line)
        line_width = bbox[2] - bbox[0]
        x = (THUMBNAIL_WIDTH - line_width) // 2
        draw.text(
            (x, y), line, font=font, fill="white",
            stroke_width=8, stroke_fill="black",
        )
        y += line_height

    return img


def generate_thumbnail_image(image_prompt):
    pipe = FluxPipeline.from_pretrained(FLUX_MODEL_ID, torch_dtype=torch.bfloat16)
    pipe.to("cuda")

    full_prompt = image_prompt + ",photojournalism,RAW photo,ultra realistic,DSLR,85mm lens,natural lighting,real photograph,"

    return pipe(
        prompt=full_prompt,
        negative_prompt=NEGATIVE_PROMPT,
        true_cfg_scale=1.5,
        height=736,
        width=1280,
        guidance_scale=3.5,
        num_inference_steps=50,
        max_sequence_length=512,
    ).images[0]


def main():
    out_path = OUTDIR / "thumbnail.png"
    if out_path.exists():
        print(f"skip (cached): {out_path}")
        return

    with open(OUTDIR / "final_story.json", encoding="utf-8") as f:
        story = json.load(f)

    title = story.get("title", "")
    synopsis = story.get("synopsis") or ""
    if not synopsis:
        # synopsisが空の場合、先頭シーンのナレーションで代用する
        synopsis = " ".join(scene["narration"] for scene in story["scenes"][:3])

    print("generating catchphrase and thumbnail prompt...")
    response = ask_ollama(
        CATCHPHRASE_PROMPT_TEMPLATE.format(title=title, synopsis=synopsis[:1000])
    )
    data = json.loads(strip_code_fence(response))
    catchphrase = data["catchphrase"]
    image_prompt = data["image_prompt"]
    print(f"catchphrase: {catchphrase}")

    # 後続のFLUX生成がVRAMを使えるよう、ここでOllamaモデルを明示的にアンロードする
    subprocess.run(["ollama", "stop", MODEL], check=False)

    print("generating thumbnail image...")
    image = generate_thumbnail_image(image_prompt)

    font_path = resolve_font_path()
    final_image = draw_catchphrase(image, catchphrase, font_path)

    final_image.save(out_path)
    print(f"done: {out_path}")


if __name__ == "__main__":
    main()
