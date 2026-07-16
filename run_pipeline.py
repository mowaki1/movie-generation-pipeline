import subprocess
import sys
from pathlib import Path

args = sys.argv

if len(args) < 4:
    print(f"usage: python {Path(args[0]).name} <variant_id> <pipeline_no> <theme>")
    raise SystemExit(1)

variant_id = args[1]
pipeline_no = args[2]
theme = args[3]

SCRIPT_DIR = Path(__file__).resolve().parent

STEPS = [
    ["generate_story7.py", variant_id, pipeline_no, theme],
    ["generate_images2.py", pipeline_no],
    ["generate_voices3.py", pipeline_no],
    ["generate_movie4.py", pipeline_no],
    ["generate_description.py", pipeline_no],
    ["generate_thumbnail.py", pipeline_no],
    ["send_completion_email.py", pipeline_no],
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
