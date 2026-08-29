import json
import time
import re
import wave
import subprocess
import subprocess

from urllib.parse import urlencode

import requests

import sys
from pathlib import Path

args = sys.argv

VOICEVOX_URL = "http://127.0.0.1:50021"
DEFAULT_SPEAKER_ID = 31  # No.7 読み聞かせ(final_story.jsonに指定が無い場合のフォールバック)

BASEDIR = Path(f"jobs/story_pipeline{args[1]}")
OUTDIR = BASEDIR / f"voices"
OUTDIR.mkdir(parents=True, exist_ok=True)

with open(BASEDIR / "final_story.json", encoding="utf-8") as f:
    story = json.load(f)

SPEAKER_ID = story.get("speaker_id", DEFAULT_SPEAKER_ID)

narrations = []
for scene in story["scenes"]:
    narrations.append(scene["narration"])

def escape_ass_text(text):
    return (
        text.replace("\\", "\\\\")
            .replace("{", "\\{")
            .replace("}", "\\}")
            .replace("\n", "\\N")
    )
def escape_ass_plain(text):
    return (
        text.replace("{", "\\{")
            .replace("}", "\\}")
    )

def wrap_ass(text, width=18):
    text = escape_ass_plain(text)

    lines = []
    while len(text) > width:
        pos = width
        while pos > 0 and text[pos] not in "、。！？":
            pos -= 1
        if pos < width // 2:
            pos = width

        lines.append(text[:pos + 1])
        text = text[pos + 1:].lstrip()

    if text:
        lines.append(text)

    return r"\N".join(lines)

def make_ass_header():
    return """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,BIZ UDPGothic,54,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,0,2,150,150,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def sec_to_ass(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int((sec - int(sec)) * 100)  # centisecond

    return f"{h}:{m:02}:{s:02}.{cs:02}"

def merge_wavs(files, outfile):
    list_file = OUTDIR / "merge_list.txt"

    with open(list_file, "w", encoding="utf-8") as f:
        for wavfile in files:
            f.write(f"file '{wavfile.resolve()}'\n")

    subprocess.run([
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-ar", "24000",
        "-ac", "1",
        str(outfile)
    ], check=True, stdin=subprocess.DEVNULL)

def sec_to_srt(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)

    return f"{h:02}:{m:02}:{s:02},{ms:03}"
    
def split_subtitles(text, max_chars=24):
    parts = re.split(r'(?<=[。！？])', text)
    result = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if len(part) <= max_chars:
            result.append(part)
            continue

        subparts = re.split(r'(?<=、)', part)
        buf = ""

        for sp in subparts:
            sp = sp.strip()
            if not sp:
                continue

            if len(buf) + len(sp) <= max_chars:
                buf += sp
            else:
                if buf:
                    result.append(buf)
                buf = sp

        if buf:
            result.append(buf)

    return result
    
# VOICEVOXは「方」を文脈判断できず「ホウ」と読んでしまうことが多いが、
# 実際のナレーションでは「この方/その方」のような指示語、または「興味のある方は」
# のような動詞・形容詞の連体形に続く「方」は、ほぼ必ず人を指す「カタ」読みになる
# (特に「興味のある方はチャンネル登録を」というCTAで頻出し、機械読み上げ感が
# 強く出て逆効果になっていた)。一方「〜した方がいい/よい」という比較表現は
# 正しく「ホウ」と読む必要があるため、後ろに「が」が続く場合は対象外にする。
# 字幕表示には影響させたくないため、音声合成に渡すテキストだけ「かた」に
# 置き換える
KATA_READING_LOOKAHEAD = r'(?=[はもにへを、。！？]|$)'

def fix_kata_reading(text: str) -> str:
    text = text.replace("方々", "かたがた")
    text = re.sub(rf'(この|その|あの|どの)方{KATA_READING_LOOKAHEAD}', r'\1かた', text)
    text = re.sub(rf'(ない|[るたい])方{KATA_READING_LOOKAHEAD}', r'\1かた', text)
    return text


def create_audio_query(text: str, speaker: int) -> dict:
    params = {
        "text": text,
        "speaker": speaker,
    }

    res = requests.post(
        f"{VOICEVOX_URL}/audio_query?{urlencode(params)}",
        timeout=60,
    )
    res.raise_for_status()
    return res.json()

def synthesize(query: dict, speaker: int) -> bytes:
    res = requests.post(
        f"{VOICEVOX_URL}/synthesis?speaker={speaker}",
        headers={"Content-Type": "application/json"},
        data=json.dumps(query, ensure_ascii=False).encode("utf-8"),
        timeout=120,
    )
    res.raise_for_status()
    return res.content

def main() -> None:
    current_time = 0.0
    ass_lines = [make_ass_header()]

    for i, text in enumerate(narrations, start=1):
        print(f"[scene {i}] {text}")
        subtitles = split_subtitles(text)
        wav_files = []
        for j, subtitle in enumerate(subtitles, start=1):
            out = OUTDIR / f"voice{i}_{j}.wav"

            if out.exists():
                print(f"skip (cached): {out}")
            else:
                query = create_audio_query(fix_kata_reading(subtitle), SPEAKER_ID)

                # 必要ならここで話速などを調整
                query["speedScale"] = 0.95
                query["intonationScale"] = 1.0
                query["volumeScale"] = 1.0
                query["prePhonemeLength"] = 0.2
                query["postPhonemeLength"] = 0.3

                wav = synthesize(query, SPEAKER_ID)
                out.write_bytes(wav)

                print(f"saved: {out} ({len(wav)} bytes)")
                time.sleep(0.2)

            with wave.open(str(out), "rb") as wf:
                duration = wf.getnframes() / wf.getframerate()

            start = current_time
            end = start + duration

            ass_text = wrap_ass(subtitle, 24)

            ass_lines.append(
                "Dialogue: 0,"
                f"{sec_to_ass(start)},"
                f"{sec_to_ass(end)},"
                "Default,,0,0,0,,"
                f"{ass_text}"
            )

            current_time = end

            wav_files.append(out)

        merged_out = OUTDIR / f"voice{i}.wav"
        if merged_out.exists():
            print(f"skip (cached): {merged_out}")
        else:
            merge_wavs(wav_files, merged_out)

    (OUTDIR / "subtitle.ass").write_text(
        "\n".join(ass_lines),
        encoding="utf-8"
    )

    print("saved subtitle.ass")

if __name__ == "__main__":
    main()
