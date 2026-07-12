import subprocess
import json

import sys
from pathlib import Path

args = sys.argv

BASE = Path(f"jobs/story_pipeline{args[1]}")

IMAGE_DIR = BASE
VOICE_DIR = BASE / f"voices"
VIDEO_DIR = BASE

VIDEO_DIR.mkdir(parents=True, exist_ok=True)

with open(BASE / "final_story.json", encoding="utf-8") as f:
    story = json.load(f)

SCENES = []
IMAGE_PROMPTS = {}
for scene in story["scenes"]:
    SCENES.append(scene["scene_no"])
    IMAGE_PROMPTS[scene["scene_no"]] = scene["image_prompt"]

WAN22_DIR = Path("/home/mowaki/roujin_home_senka/Wan2.2")
WAN22_CKPT = Path("/data/models/wan2.2/Wan2.2-TI2V-5B")
WAN22_SIZE = "1280*704"
WAN22_FPS = 24
WAN22_MAX_SECONDS = 5.0
WAN22_SAMPLE_STEPS = 30

motion_prompt_suffix = ",subtle natural motion,gentle breathing,slight breeze,cinemagraph,photorealistic,slow movement,NOT illustration,NOT anime,"

def compute_frame_num(duration_sec: float) -> int:
    # Wan2.2のVAE時間方向ストライドが4のため、frame_numは 4k+1 でなければならない
    target = min(duration_sec, WAN22_MAX_SECONDS) * WAN22_FPS
    n = round((target - 1) / 4) * 4 + 1
    return max(25, min(121, n))

def run(cmd: list[str], cwd: Path | None = None) -> None:
    print(" ".join(cmd))
    # stdin=DEVNULL: バックグラウンド実行時にffmpeg等が標準入力待ちでSIGTTIN停止するのを防ぐ
    subprocess.run(cmd, check=True, cwd=str(cwd) if cwd else None, stdin=subprocess.DEVNULL)

def get_duration(path: Path) -> float:
    import subprocess
    r = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(r.stdout.strip())

def generate_motion_clip(scene_no: int, image: Path, out: Path, duration_sec: float) -> None:
    if out.exists():
        print(f"skip (cached): {out}")
        return

    prompt = IMAGE_PROMPTS[scene_no] + motion_prompt_suffix
    frame_num = compute_frame_num(duration_sec)

    run([
        sys.executable, "generate.py",
        "--task", "ti2v-5B",
        "--size", WAN22_SIZE,
        "--ckpt_dir", str(WAN22_CKPT),
        "--image", str(image.resolve()),
        "--prompt", prompt,
        "--frame_num", str(frame_num),
        "--sample_steps", str(WAN22_SAMPLE_STEPS),
        "--save_file", str(out.resolve()),
    ], cwd=WAN22_DIR)

def make_scene_video(scene_no: int) -> Path:
    image = IMAGE_DIR / f"image{scene_no}.png"
    voice = VOICE_DIR / f"voice{scene_no}.wav"
    out = VIDEO_DIR / f"video{scene_no}.mp4"

    if out.exists():
        print(f"skip (cached): {out}")
        return out

    if not image.exists():
        raise FileNotFoundError(image)
    if not voice.exists():
        raise FileNotFoundError(voice)

    duration = get_duration(voice)

    # 1. Wan2.2で先頭~5秒(ナレーションがそれより短ければその長さ)だけ動きをつける
    #    (1280x704で生成、ffmpegで1920x1088にアップスケール)
    motion_raw = VIDEO_DIR / f"motion{scene_no}_raw.mp4"
    generate_motion_clip(scene_no, image, motion_raw, duration)

    motion_scaled = VIDEO_DIR / f"motion{scene_no}_scaled.mp4"
    if not motion_scaled.exists():
        run([
            "ffmpeg", "-y",
            "-i", str(motion_raw),
            "-vf", "scale=1920:1088,format=yuv420p",
            "-c:v", "h264_nvenc",
            "-preset", "p4",
            "-cq", "23",
            str(motion_scaled),
        ])

    motion_duration = get_duration(motion_scaled)

    # 2. ナレーション尺に合わせる(短ければトリム、長ければ最終フレームを静止延長)
    silent = VIDEO_DIR / f"silent{scene_no}.mp4"

    if duration <= motion_duration:
        run([
            "ffmpeg", "-y",
            "-i", str(motion_scaled),
            "-t", f"{duration:.3f}",
            "-c", "copy",
            str(silent),
        ])
    else:
        freeze_frame = VIDEO_DIR / f"freeze{scene_no}.png"
        run([
            "ffmpeg", "-y",
            "-sseof", "-0.1",
            "-i", str(motion_scaled),
            "-update", "1",
            "-frames:v", "1",
            str(freeze_frame),
        ])

        freeze_clip = VIDEO_DIR / f"freeze{scene_no}.mp4"
        run([
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(freeze_frame),
            "-t", f"{duration - motion_duration:.3f}",
            "-vf", "format=yuv420p",
            "-c:v", "h264_nvenc",
            "-preset", "p4",
            "-cq", "23",
            str(freeze_clip),
        ])

        list_file = VIDEO_DIR / f"concat_motion{scene_no}.txt"
        list_file.write_text(
            "\n".join(f"file '{p.resolve()}'" for p in [motion_scaled, freeze_clip]),
            encoding="utf-8",
        )

        run([
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(silent),
        ])

    # 3. 音声を合成して最終出力(1080pにクロップ)
    run([
        "ffmpeg", "-y",
        "-i", str(silent),
        "-i", str(voice),
        "-vf", "crop=1920:1080:0:4",
        "-c:v", "h264_nvenc",
        "-preset", "p4",
        "-cq", "23",
        "-c:a", "aac",
        "-shortest",
        str(out),
    ])
    return out
    
def concat_videos(scene_videos: list[Path]) -> Path:
    list_file = VIDEO_DIR / "concat.txt"
    raw_episode = BASE / "movie_raw.mp4"
    episode = BASE / "movie.mp4"

    list_file.write_text(
        "\n".join(f"file '{v.resolve()}'" for v in scene_videos),
        encoding="utf-8",
    )

    # �܂����悾������
    run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(raw_episode),
    ])

    # ASS���Ă�����
    run([
        "ffmpeg", "-y",
        "-i", str(raw_episode),
        "-vf", f"ass={VOICE_DIR / 'subtitle.ass'}",
        "-c:v", "h264_nvenc",
        "-preset", "p4",
        "-cq", "23",
        "-c:a", "copy",
        str(episode),
    ])
    return episode

def main() -> None:
    scene_videos = [make_scene_video(n) for n in SCENES]
    episode = concat_videos(scene_videos)
    print(f"done: {episode}")

if __name__ == "__main__":
    main()
