import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OUTRO_DIR = SCRIPT_DIR / "assets"
OUTRO_DIR.mkdir(parents=True, exist_ok=True)
OUTRO_PATH = OUTRO_DIR / "outro.mp4"

DURATION = 5
FONT = "BIZ UDPGothic"

subprocess.run([
    "ffmpeg", "-y",
    "-f", "lavfi", "-i", f"color=c=0x1a1a2e:s=1920x1080:d={DURATION}",
    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
    "-vf",
    f"drawtext=font='{FONT}':text='ご視聴ありがとうございました':fontcolor=white:fontsize=64:x=(w-text_w)/2:y=(h/2)-80,"
    f"drawtext=font='{FONT}':text='チャンネル登録で次の動画もお見逃しなく':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h/2)+20",
    "-c:v", "h264_nvenc",
    "-preset", "p4",
    "-cq", "23",
    "-c:a", "aac",
    "-shortest",
    str(OUTRO_PATH),
], check=True)

print(f"done: {OUTRO_PATH}")
