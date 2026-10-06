# 日本語ニュース動画(完成済みジョブ)の英語版を作る。画像・LTX動画クリップは
# 日本語版のものを再利用し、ナレーションの英訳・英語TTS・動画の再結合だけをやり直す。
#
# usage:
#   python run_news_pipeline_en.py <source_pipeline_no>
#       英語版のジャンルID・ジョブ番号を自動で決め、DB(t_movie_titles)にも記録する(手動実行向け)
#   python run_news_pipeline_en.py <en_genre_id> <en_pipeline_no> <source_pipeline_no>
#       番号を明示する(run_rotation_loop.pyが採番・DB記録を済ませた上で呼ぶ場合)

import json
import subprocess
import sys
from pathlib import Path

args = sys.argv

if len(args) not in (2, 4):
    print(f"usage: python {Path(args[0]).name} <source_pipeline_no>")
    print(f"       python {Path(args[0]).name} <en_genre_id> <en_pipeline_no> <source_pipeline_no>")
    raise SystemExit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
CREDENTIALS_DIR = Path.home() / "roujin_home_senka" / "credentials"

# 日本国内限定のニュースは英語版を作らない(news/check_global_relevance_en.pyが
# この終了コードで知らせる。run_rotation_loop.pyのENGLISH_SKIP_EXIT_CODEと一致させること)
SKIP_EXIT_CODE = 10

db = None
if len(args) == 2:
    from run_rotation_loop import (
        DB,
        DB_DSN,
        ENGLISH_GENRE_BY_SOURCE,
        delete_news_placeholder,
        insert_news_placeholder,
        mark_status,
        update_news_title,
    )

    source_pipeline_no = args[1]
    source_story_path = Path(f"jobs/story_pipeline{source_pipeline_no}/final_story.json")
    if not source_story_path.exists():
        print(f"ERROR: {source_story_path} がありません(日本語版ジョブが未完了)")
        raise SystemExit(1)

    source_genre_id = int(json.loads(source_story_path.read_text(encoding="utf-8"))["genre_id"])
    if source_genre_id not in ENGLISH_GENRE_BY_SOURCE:
        print(f"ERROR: genre_id={source_genre_id} には英語版が定義されていません")
        raise SystemExit(1)

    en_genre_id = str(ENGLISH_GENRE_BY_SOURCE[source_genre_id])
    db = DB(DB_DSN)
    en_pipeline_no = str(db.run(lambda conn: insert_news_placeholder(conn, int(en_genre_id))))
    print(f"english genre_id={en_genre_id} pipeline_no={en_pipeline_no} (source pipeline_no={source_pipeline_no})")
else:
    en_genre_id = args[1]
    en_pipeline_no = args[2]
    source_pipeline_no = args[3]

STEPS = [
    ["news/check_global_relevance_en.py", source_pipeline_no, en_pipeline_no],
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


def run_steps() -> int:
    for script, *script_args in STEPS:
        cmd = [sys.executable, str(SCRIPT_DIR / script), *script_args]
        print(f"=== {script} {' '.join(script_args)} ===")

        result = subprocess.run(cmd)
        if result.returncode == SKIP_EXIT_CODE:
            print("skip: 日本国内限定のニュースのため、英語版は作りません")
            return SKIP_EXIT_CODE
        if result.returncode != 0:
            print(f"ERROR: {script} failed (exit code {result.returncode})")
            print("再実行すると、完了済みの工程・シーンはスキップされて続きから進みます。")
            return result.returncode

    return 0


def main() -> None:
    code = run_steps()

    # 自動採番(DB記録あり)で起動した場合のみ、ここでステータスとタイトルを更新する
    if db is not None:
        if code == SKIP_EXIT_CODE:
            # 作らなかった英語版の行は、番号だけが残らないよう削除する
            db.run(lambda conn: delete_news_placeholder(conn, int(en_pipeline_no)))
            return
        if code == 0:
            final_story_path = Path(f"jobs/story_pipeline{en_pipeline_no}/final_story.json")
            title = json.loads(final_story_path.read_text(encoding="utf-8")).get("title", "")
            if title:
                db.run(lambda conn: update_news_title(conn, int(en_pipeline_no), title))
            db.run(lambda conn: mark_status(conn, int(en_pipeline_no), 3))
        else:
            db.run(lambda conn: mark_status(conn, int(en_pipeline_no), 2))

    if code != 0:
        raise SystemExit(code)
    print(f"done: jobs/story_pipeline{en_pipeline_no}/movie.mp4")


if __name__ == "__main__":
    main()
