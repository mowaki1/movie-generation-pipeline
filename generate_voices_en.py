# 英語版ニュース動画用の音声・字幕生成。generate_voices3.py(VOICEVOX、日本語専用)の
# 英語版で、TTSにQwen3-TTSを使う。出力(voices/voice<N>.wav, voices/subtitle.ass)は
# generate_voices3.pyと同じ形式なので、generate_movie4.pyはそのまま使える。
#
# usage: python generate_voices_en.py <pipeline_no>

import json
import os
import re
import subprocess
import sys
import textwrap
import wave
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

args = sys.argv
if len(args) < 2:
    print(f"usage: python {Path(args[0]).name} <pipeline_no>")
    raise SystemExit(1)

BASEDIR = Path(f"jobs/story_pipeline{args[1]}")
OUTDIR = BASEDIR / "voices"
OUTDIR.mkdir(parents=True, exist_ok=True)

with open(BASEDIR / "final_story.json", encoding="utf-8") as f:
    story = json.load(f)

MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
SPEAKER = os.environ.get("TTS_EN_SPEAKER", "Ryan")
TRAILING_SILENCE_SEC = 0.25
SUBTITLE_MAX_CHARS = 80
SUBTITLE_WRAP_WIDTH = 50
SUBTITLE_FONT = "BIZ UDPGothic"

narrations = [scene["narration"] for scene in story["scenes"]]


def load_model():
    from qwen_tts import Qwen3TTSModel

    model = Qwen3TTSModel.from_pretrained(
        MODEL_ID,
        device_map="cuda:0",
        dtype=torch.bfloat16,
    )

    # 12Hzボコーダ(speech_tokenizer.decode)は初期状態が無いため、生成全体の最初の
    # 単語だけ発音が崩れる(例: "Hello"が"He"+"llo"に分断される)。無音コードを
    # 前置きしてデコードし、その分のサンプルを削ることで回避する
    # (QwenLM/Qwen3-TTS Issue #219)
    silence_wav = np.zeros(int(24000 * 0.25), dtype=np.float32)
    silence_enc = model.model.speech_tokenizer.encode(silence_wav, sr=24000)
    silence_codes = silence_enc.audio_codes[0].cpu()
    n_silence_frames = silence_codes.shape[0]
    orig_decode = model.model.speech_tokenizer.decode

    def patched_decode(encoded_list, **kw):
        patched = [
            {"audio_codes": torch.cat([silence_codes.to(c["audio_codes"].device), c["audio_codes"]], dim=0)}
            for c in encoded_list
        ]
        wavs_raw, fs = orig_decode(patched, **kw)
        trim = int(n_silence_frames * fs / 12)
        return [w[trim:] for w in wavs_raw], fs

    model.model.speech_tokenizer.decode = patched_decode
    return model


def split_subtitles(text, max_chars=SUBTITLE_MAX_CHARS):
    result = []
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) <= max_chars:
            result.append(sentence)
            continue

        buf = ""
        for part in re.split(r"(?<=[,;:])\s+", sentence):
            if buf and len(buf) + 1 + len(part) > max_chars:
                result.append(buf)
                buf = part
            else:
                buf = f"{buf} {part}".strip()
        if buf:
            result.append(buf)

    final = []
    for chunk in result:
        if len(chunk) <= max_chars * 1.5:
            final.append(chunk)
        else:
            final.extend(textwrap.wrap(chunk, max_chars))
    return final


def escape_ass_plain(text):
    return text.replace("{", "\\{").replace("}", "\\}")


def wrap_ass(text, width=SUBTITLE_WRAP_WIDTH):
    return r"\N".join(textwrap.wrap(escape_ass_plain(text), width))


def make_ass_header():
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{SUBTITLE_FONT},54,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,0,2,150,150,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def sec_to_ass(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int((sec - int(sec)) * 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def merge_wavs(files, outfile):
    list_file = OUTDIR / "merge_list.txt"

    with open(list_file, "w", encoding="utf-8") as f:
        for wavfile in files:
            f.write(f"file '{wavfile.resolve()}'\n")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-ar", "24000",
        "-ac", "1",
        str(outfile),
    ], check=True, stdin=subprocess.DEVNULL)


def synthesize(model, text):
    wavs, sr = model.generate_custom_voice(text=text, language="English", speaker=SPEAKER)
    wav = wavs[0]
    if hasattr(wav, "detach"):
        wav = wav.detach().cpu().numpy()
    wav = np.asarray(wav, dtype=np.float32)
    silence = np.zeros(int(sr * TRAILING_SILENCE_SEC), dtype=np.float32)
    return np.concatenate([wav, silence]), sr


def main():
    current_time = 0.0
    ass_lines = [make_ass_header()]
    model = None

    for i, text in enumerate(narrations, start=1):
        print(f"[scene {i}] {text}")
        wav_files = []
        for j, subtitle in enumerate(split_subtitles(text), start=1):
            out = OUTDIR / f"voice{i}_{j}.wav"

            if out.exists():
                print(f"skip (cached): {out}")
            else:
                if model is None:
                    model = load_model()
                wav, sr = synthesize(model, subtitle)
                sf.write(str(out), wav, sr, subtype="PCM_16")
                print(f"saved: {out}")

            with wave.open(str(out), "rb") as wf:
                duration = wf.getnframes() / wf.getframerate()

            start = current_time
            end = start + duration
            ass_lines.append(
                "Dialogue: 0,"
                f"{sec_to_ass(start)},"
                f"{sec_to_ass(end)},"
                "Default,,0,0,0,,"
                f"{wrap_ass(subtitle)}"
            )
            current_time = end
            wav_files.append(out)

        merged_out = OUTDIR / f"voice{i}.wav"
        if merged_out.exists():
            print(f"skip (cached): {merged_out}")
        else:
            merge_wavs(wav_files, merged_out)

    (OUTDIR / "subtitle.ass").write_text("\n".join(ass_lines), encoding="utf-8")
    print("saved subtitle.ass")


if __name__ == "__main__":
    main()
