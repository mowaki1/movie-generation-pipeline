import os
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
import json

import numpy as np
import torch
from diffusers import FluxPipeline

import sys
from pathlib import Path

args = sys.argv

OUTDIR = Path(f"jobs/story_pipeline{args[1]}")
OUTDIR.mkdir(parents=True, exist_ok=True)

model_id = "black-forest-labs/FLUX.1-dev"

prompt_suffix = "photojournalism,RAW photo,ultra realistic,DSLR,85mm lens,skin texture,natural lighting,real photograph,"

# "NOT illustration"のような否定文は拡散モデルに効きにくいため、
# true_cfg_scaleによる本物のネガティブプロンプトとして分離して与える。
negative_prompt = "illustration,anime,cartoon,3D render,CGI,digital painting,drawing,concept art,watermark,stock photo watermark,logo,text overlay,blurry,low quality"

pipe = FluxPipeline.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,
)
pipe.to("cuda")

pipe.vae.enable_slicing()
pipe.vae.enable_tiling()


def encode_prompt(text_prompt):
    # ========================================================
    # 1. CLIP側のエンコード & プーリングベクトルの抽出
    # ========================================================
    text_inputs = pipe.tokenizer(
        text_prompt,
        padding="max_length",
        max_length=77,
        truncation=True,
        return_tensors="pt",
    ).to("cuda")

    with torch.no_grad():
        # CLIPの通常の出力 (77トークン分)
        encoder_outputs = pipe.text_encoder(text_inputs.input_ids, output_hidden_states=True)
        prompt_embeds = encoder_outputs[0]
        # FLUXが要求する768次元pooledベクトルは、このCLIPのプーリングされた出力です
        pooled_prompt_embeds = encoder_outputs.pooler_output

    # ========================================================
    # 2. T5側のエンコード (256トークンまでの長さを保持)
    # ========================================================
    text_inputs_2 = pipe.tokenizer_2(
        text_prompt,
        padding="max_length",
        max_length=512, # 512まで拡張可能です
        truncation=True,
        return_tensors="pt",
    ).to("cuda")

    with torch.no_grad():
        # T5の出力ベクトル (長文用)
        text_embeds_2 = pipe.text_encoder_2(text_inputs_2.input_ids)[0]

    # ========================================================
    # 3. 2つのエンコーダーの出力をFLUXの仕様通りに結合 (4096次元)
    # ========================================================
    # FLUXは内部で CLIP(77x4096にパディング) と T5(256x4096) を結合して使用します
    # ここでCLIP側の次元をT5側に合わせてパディング処理を行います
    padding = torch.zeros(
        (prompt_embeds.shape[0], prompt_embeds.shape[1], text_embeds_2.shape[2] - prompt_embeds.shape[2]),
        device=prompt_embeds.device,
        dtype=prompt_embeds.dtype,
    )
    prompt_embeds = torch.cat([prompt_embeds, padding], dim=-1)

    # 最終的なプロンプト埋め込みベクトルの結合
    final_prompt_embeds = torch.cat([prompt_embeds, text_embeds_2], dim=1)

    return final_prompt_embeds, pooled_prompt_embeds


def is_black(image) -> bool:
    return np.array(image.convert("L")).mean() < 5


def generate(prompt_embeds, pooled_prompt_embeds, use_negative_prompt: bool):
    kwargs = {}
    if use_negative_prompt:
        kwargs["negative_prompt_embeds"] = negative_prompt_embeds
        kwargs["negative_pooled_prompt_embeds"] = negative_pooled_prompt_embeds
        kwargs["true_cfg_scale"] = 1.5

    return pipe(
        prompt_embeds=prompt_embeds,       # 結合した最終テキスト対応ベクトル
        pooled_prompt_embeds=pooled_prompt_embeds, # CLIP由来の768次元ベクトル
        height=1088,  # 16px単位制約のため1080ではなく1088で生成し、movie側で1080にクロップする
        width=1920,
        guidance_scale=3.5,
        num_inference_steps=50,
        max_sequence_length=512,
        **kwargs,
    ).images[0]


# ネガティブプロンプトは全シーン共通なので1回だけエンコードする
negative_prompt_embeds, negative_pooled_prompt_embeds = encode_prompt(negative_prompt)


with open(OUTDIR / "final_story.json", encoding="utf-8") as f:
    story = json.load(f)

prompts = []
for scene in story["scenes"]:
    prompts.append(scene["image_prompt"] + prompt_suffix)

for i, text_prompt in enumerate(prompts):
    file_name = f"image{i + 1}.png"

    if (OUTDIR / file_name).exists():
        print(f"skip (cached): {file_name}")
        continue

    final_prompt_embeds, pooled_prompt_embeds = encode_prompt(text_prompt)

    # 推論実行(true_cfg_scale>1でネガティブプロンプトが有効になる)。
    # 診断の結果、黒画像はNaN/数値誤差ではなく、FLUX.1-dev(guidance-distilled
    # モデル)にtrue_cfg_scaleで本物のCFG外挿をかけた際、特定のシードで
    # 潜在変数が学習分布から外れ、VAEデコード後に標準偏差ほぼ0の均一な黒へ
    # 縮退する現象と判明した(true_cfg_scaleを3.5→1.5に下げて緩和済み)。
    # それでも起き得るため、まずはネガティブプロンプトを保ったまま(=写実性を
    # 保ったまま)別のシードで数回リトライし、それでも黒いままの場合のみ
    # ネガティブプロンプト無しにフォールバックする(ネガティブプロンプトには
    # illustration/anime等を弾く役割があるため、外すとアニメ調に振れやすく
    # なる副作用がある)。
    image = generate(final_prompt_embeds, pooled_prompt_embeds, use_negative_prompt=True)

    retry = 0
    while is_black(image) and retry < 2:
        retry += 1
        print(f"WARNING: {file_name} was black, retrying with negative prompt (seed retry {retry}/2)")
        image = generate(final_prompt_embeds, pooled_prompt_embeds, use_negative_prompt=True)

    if is_black(image):
        print(f"WARNING: {file_name} still black after seed retries, retrying without negative prompt")
        image = generate(final_prompt_embeds, pooled_prompt_embeds, use_negative_prompt=False)

    image.save(OUTDIR / file_name)
    print(f"saved {file_name}")