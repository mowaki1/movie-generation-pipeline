import subprocess
import sys
from pathlib import Path

args = sys.argv

if len(args) < 3:
    print(f"usage: python {Path(args[0]).name} <genre_id> <pipeline_no>")
    raise SystemExit(1)

genre_id = args[1]
pipeline_no = args[2]

SCRIPT_DIR = Path(__file__).resolve().parent

STEPS = [
    ["news/generate_news_script.py", genre_id, pipeline_no],
    ["generate_images2.py", pipeline_no],
    ["generate_voices3.py", pipeline_no],
    ["generate_movie4.py", pipeline_no],
]


def main() -> None:
    for script, *script_args in STEPS:
        cmd = [sys.executable, str(SCRIPT_DIR / script), *script_args]
        print(f"=== {script} {' '.join(script_args)} ===")

        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"ERROR: {script} failed (exit code {result.returncode})")
            print("再実行すると、完了済みの工程・シーンはスキップされて続きから進みます。")
            raise SystemExit(result.returncode)

    print(f"done: jobs/story_pipeline{pipeline_no}/movie.mp4")


if __name__ == "__main__":
    main()
