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
    # colorフィルタのデフォルトフレームレートは25fpsだが、シーン動画
    # (LTX-2/ffmpegの出力)は全て24fpsで統一されている。ここが異なると、
    # 最後のシーンからアウトロへの継ぎ目でタイムスタンプの整合が取れず、
    # 結合後の映像に無音・静止画のまま数十秒フレームが重複する不具合があった
    "-f", "lavfi", "-i", f"color=c=0x1a1a2e:s=1920x1080:d={DURATION}:r=24",
    # シーン動画の音声(VOICEVOX出力)は24000Hz・モノラルで統一されている。
    # ここが異なる(以前は48000Hz・ステレオだった)と、動画結合時のconcat
    # デムクサーが音声セグメント間でフォーマットの不整合を起こし、結合後の
    # 音声トラックの尺が実際の約2倍に破損する不具合があった
    "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=24000",
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
