# 日本語ニュース動画(完成済みジョブ)の英語版を作る。画像・LTX動画クリップは
# 日本語版のものを再利用し、ナレーションの英訳・英語TTS・動画の再結合だけをやり直す。
#
# usage: python run_news_pipeline_en.py <en_genre_id> <en_pipeline_no> <source_pipeline_no>

import subprocess
import sys
from pathlib import Path

args = sys.argv

if len(args) < 4:
    print(f"usage: python {Path(args[0]).name} <en_genre_id> <en_pipeline_no> <source_pipeline_no>")
    raise SystemExit(1)

en_genre_id = args[1]
en_pipeline_no = args[2]
source_pipeline_no = args[3]

SCRIPT_DIR = Path(__file__).resolve().parent

CREDENTIALS_DIR = Path.home() / "roujin_home_senka" / "credentials"

STEPS = [
    ["news/translate_news_en.py", source_pipeline_no, en_pipeline_no, en_genre_id],
    ["generate_voices_en.py", en_pipeline_no],
    ["generate_movie4.py", en_pipeline_no],
    ["generate_description.py", en_pipeline_no],
    ["generate_thumbnail.py", en_pipeline_no],
]

# 英語版チャンネルのOAuth認証(authorize_youtube.py)が済んでtokenが置かれるまでは、
# 動画の生成だけ行ってアップロードは見送る(限定公開で自動アップロードされる)
if (CREDENTIALS_DIR / f"token_{en_genre_id}.json").exists():
    STEPS.append(["upload_youtube.py", en_genre_id, en_pipeline_no])
else:
    print(f"note: token_{en_genre_id}.json が無いためYouTube自動アップロードは行いません")

STEPS.append(["send_completion_email.py", en_pipeline_no])


def main() -> None:
    for script, *script_args in STEPS:
        cmd = [sys.executable, str(SCRIPT_DIR / script), *script_args]
        print(f"=== {script} {' '.join(script_args)} ===")

        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"ERROR: {script} failed (exit code {result.returncode})")
            print("再実行すると、完了済みの工程・シーンはスキップされて続きから進みます。")
            raise SystemExit(result.returncode)

    print(f"done: jobs/story_pipeline{en_pipeline_no}/movie.mp4")


if __name__ == "__main__":
    main()
