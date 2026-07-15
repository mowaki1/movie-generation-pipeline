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

# 診断用: denoisingループ内のcallbackではVAEデコード処理そのものを監視できないため、
# vae.decode()自体をラップして入出力の異常値(NaN/Inf)を確認する
_original_vae_decode = pipe.vae.decode


def _instrumented_vae_decode(z, *args, **kwargs):
    in_has_nan = bool(torch.isnan(z).any() or torch.isinf(z).any())
    in_max_abs = z.abs().max().item()

    result = _original_vae_decode(z, *args, **kwargs)
    sample = result.sample if hasattr(result, "sample") else result[0]

    out_has_nan = bool(torch.isnan(sample).any() or torch.isinf(sample).any())
    out_max_abs = sample.abs().max().item()

    print(
        f"  DIAGNOSTIC: vae_decode input(has_nan={in_has_nan}, max_abs={in_max_abs:.4f}) "
        f"-> output(has_nan={out_has_nan}, max_abs={out_max_abs:.4f})"
    )

    return result


pipe.vae.decode = _instrumented_vae_decode


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


def make_diagnostic_callback():
    # 黒画像の原因(どのステップで潜在変数が異常な値になるか)を特定するための
    # 一時的な診断用コールバック。各denoisingステップ終了時に潜在変数を検査する。
    state = {"first_nan_step": None, "max_abs": 0.0}

    def callback(pipe, step_index, timestep, callback_kwargs):
        latents = callback_kwargs["latents"]
        abs_max = latents.abs().max().item()
        state["max_abs"] = max(state["max_abs"], abs_max)

        if state["first_nan_step"] is None and (
            torch.isnan(latents).any() or torch.isinf(latents).any()
        ):
            state["first_nan_step"] = step_index
            print(
                f"  DIAGNOSTIC: NaN/Inf first appeared at step={step_index} "
                f"timestep={timestep} max_abs_so_far={abs_max:.4f}"
            )

        return callback_kwargs

    return callback, state


def generate(prompt_embeds, pooled_prompt_embeds, use_negative_prompt: bool):
    kwargs = {}
    if use_negative_prompt:
        kwargs["negative_prompt_embeds"] = negative_prompt_embeds
        kwargs["negative_pooled_prompt_embeds"] = negative_pooled_prompt_embeds
        kwargs["true_cfg_scale"] = 3.5

    callback, state = make_diagnostic_callback()

    image = pipe(
        prompt_embeds=prompt_embeds,       # 結合した最終テキスト対応ベクトル
        pooled_prompt_embeds=pooled_prompt_embeds, # CLIP由来の768次元ベクトル
        height=1088,  # 16px単位制約のため1080ではなく1088で生成し、movie側で1080にクロップする
        width=1920,
        guidance_scale=3.5,
        num_inference_steps=50,
        max_sequence_length=512,
        callback_on_step_end=callback,
        callback_on_step_end_tensor_inputs=["latents"],
        **kwargs,
    ).images[0]

    print(
        f"  DIAGNOSTIC: max_abs_latent={state['max_abs']:.4f}, "
        f"first_nan_step={state['first_nan_step']}, use_negative_prompt={use_negative_prompt}"
    )

    return image


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
    # 暗いシーン等でtrue_cfg_scale使用時にbf16でNaNが起き、真っ黒な画像に
    # なることがある。これはシード(乱数)依存で起きるため、まずはネガティブ
    # プロンプトを保ったまま(=写実性を保ったまま)別のシードで数回リトライし、
    # それでも黒いままの場合のみネガティブプロンプト無しにフォールバックする
    # (ネガティブプロンプトにはillustration/anime等を弾く役割があるため、
    # 外すとアニメ調に振れやすくなる副作用がある)。
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