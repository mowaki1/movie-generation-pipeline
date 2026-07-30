import json
import os
import sys
import time
from pathlib import Path

import psycopg2

# サブプロセス(run_pipeline.py/run_news_pipeline.py以下、全ての子プロセスに継承される)の
# 標準出力バッファリングを無効化する。ファイルへのリダイレクト時はデフォルトで
# ブロックバッファリングされ、クラッシュ時にバッファ内容がフラッシュされず
# ログから失われることがあったため
os.environ["PYTHONUNBUFFERED"] = "1"

DB_DSN = "dbname=video_pipeline"

# 1000番台(ドラマ)+3000番台(雑学・ミステリー)
DRAMA_TRIVIA_GENRES = [
    1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010, 1011, 1012, 1013,
    3001, 3002,
]
# 2004, 2006〜2010はinclude/variables_*.py・base_*.pyが未作成のため一時除外
# (作成でき次第、このリストに戻すこと)
STUDY_GENRES = [
    2001, 2002, 2003, 2005, 2011, 2012, 2013, 2014, 2015,
]
NEWS_GENRES = [10001, 10002, 10003, 10004, 10005, 10006, 10007, 10008, 10009]

ALL_GENRES = DRAMA_TRIVIA_GENRES + STUDY_GENRES + NEWS_GENRES

# この本数だけ各ジャンルで成功(status_id=3)すれば、そのジャンルは
# 手動アップロードでの目視確認が一巡したとみなす
AUTO_UPLOAD_REVIEW_THRESHOLD = 2

REST_SECONDS = 1.5 * 3600

SCRIPT_DIR = Path(__file__).resolve().parent


def get_next_title(conn, genre_id):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, movie_title FROM t_movie_titles
            WHERE genre_id = %s AND status_id = 0
            ORDER BY id LIMIT 1
            """,
            (genre_id,),
        )
        return cur.fetchone()


def mark_status(conn, row_id, status_id):
    with conn.cursor() as cur:
        cur.execute("UPDATE t_movie_titles SET status_id = %s WHERE id = %s", (status_id, row_id))
    conn.commit()


def insert_news_placeholder(conn, genre_id):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO t_movie_titles (genre_id, status_id) VALUES (%s, 1) RETURNING id",
            (genre_id,),
        )
        row_id = cur.fetchone()[0]
    conn.commit()
    return row_id


def update_news_title(conn, row_id, title):
    with conn.cursor() as cur:
        cur.execute("UPDATE t_movie_titles SET movie_title = %s WHERE id = %s", (title, row_id))
    conn.commit()


def run_script(script, script_args):
    import subprocess
    return subprocess.run([sys.executable, str(SCRIPT_DIR / script), *script_args])


def run_drama_or_study(conn, genre_id):
    row = get_next_title(conn, genre_id)
    if row is None:
        print(f"  no pending titles left for genre_id={genre_id}, skipping")
        return

    row_id, title = row
    mark_status(conn, row_id, 1)
    print(f"=== genre_id={genre_id} pipeline_no={row_id} title={title!r} ===")

    result = run_script("run_pipeline.py", [str(genre_id), str(row_id), title])
    mark_status(conn, row_id, 3 if result.returncode == 0 else 2)


def run_news(conn, genre_id):
    row_id = insert_news_placeholder(conn, genre_id)
    print(f"=== news genre_id={genre_id} pipeline_no={row_id} ===")

    result = run_script("run_news_pipeline.py", [str(genre_id), str(row_id)])

    if result.returncode == 0:
        final_story_path = Path(f"jobs/story_pipeline{row_id}/final_story.json")
        if final_story_path.exists():
            with open(final_story_path, encoding="utf-8") as f:
                title = json.load(f).get("title", "")
            if title:
                update_news_title(conn, row_id, title)
        mark_status(conn, row_id, 3)
    else:
        mark_status(conn, row_id, 2)


def get_completed_counts(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT genre_id, COUNT(*) FROM t_movie_titles WHERE status_id = 3 GROUP BY genre_id"
        )
        return dict(cur.fetchall())


def all_genres_reviewed_twice(conn):
    counts = get_completed_counts(conn)
    return all(counts.get(g, 0) >= AUTO_UPLOAD_REVIEW_THRESHOLD for g in ALL_GENRES)


def rest():
    print(f"resting for {REST_SECONDS / 3600:.1f} hours (GPU cooldown)...")
    time.sleep(REST_SECONDS)
    print("rest done, resuming")


def main():
    conn = psycopg2.connect(DB_DSN)

    drama_idx = 0
    study_idx = 0
    auto_upload_announced = False

    while True:
        # 1000/3000番台 x1
        genre_id = DRAMA_TRIVIA_GENRES[drama_idx % len(DRAMA_TRIVIA_GENRES)]
        drama_idx += 1
        run_drama_or_study(conn, genre_id)
        rest()

        # 2000番台 x2
        for _ in range(2):
            genre_id = STUDY_GENRES[study_idx % len(STUDY_GENRES)]
            study_idx += 1
            run_drama_or_study(conn, genre_id)
        rest()

        # 10000番台 全て
        for genre_id in NEWS_GENRES:
            run_news(conn, genre_id)
        rest()

        if not auto_upload_announced and all_genres_reviewed_twice(conn):
            auto_upload_announced = True
            print("=== 全ジャンルで手動アップロードが2周完了しました。自動アップロードへの移行タイミングです ===")


if __name__ == "__main__":
    main()
