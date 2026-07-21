import subprocess
import sys
from pathlib import Path

from run_rotation_loop import DRAMA_TRIVIA_GENRES, NEWS_GENRES, STUDY_GENRES

SCRIPT_DIR = Path(__file__).resolve().parent

ALL_GENRES = DRAMA_TRIVIA_GENRES + STUDY_GENRES + NEWS_GENRES

STEPS = [
    "generate_channel_art.py",
    "generate_channel_description.py",
    "generate_channel_handle.py",
]


def main():
    for genre_id in ALL_GENRES:
        print(f"=== genre_id={genre_id} ===")
        for script in STEPS:
            cmd = [sys.executable, str(SCRIPT_DIR / script), str(genre_id)]
            result = subprocess.run(cmd)
            if result.returncode != 0:
                print(f"ERROR: {script} failed for genre_id={genre_id} (exit code {result.returncode})")
                print("再実行すると、生成済みのチャンネル・工程はスキップされて続きから進みます。")
                raise SystemExit(result.returncode)

    print(f"done: {len(ALL_GENRES)} channels processed")


if __name__ == "__main__":
    main()
