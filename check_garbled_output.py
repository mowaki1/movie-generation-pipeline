import re
from pathlib import Path

import psycopg2

JOBS_DIR = Path("jobs")
GARBLED_BYTE_TOKEN_RE = re.compile(r"<0x[0-9A-Fa-f]{2}>")


def find_affected_jobs():
    affected = []
    for story_path in sorted(JOBS_DIR.glob("story_pipeline*/final_story.json")):
        text = story_path.read_text(encoding="utf-8")
        if GARBLED_BYTE_TOKEN_RE.search(text):
            affected.append(story_path)
    return affected


def find_matching_row(conn, pipeline_no):
    # pipeline_noが手動テスト等でt_movie_titles.idと無関係な値のこともあるため、
    # 数値でなければDBには触れない
    if not pipeline_no.isdigit():
        return None
    with conn.cursor() as cur:
        cur.execute(
            "SELECT genre_id, status_id FROM t_movie_titles WHERE id = %s",
            (int(pipeline_no),),
        )
        return cur.fetchone()


def main():
    affected = find_affected_jobs()
    if not affected:
        print("no garbled byte tokens found")
        return

    print(f"found {len(affected)} affected job(s):")

    conn = psycopg2.connect("dbname=video_pipeline")
    for story_path in affected:
        pipeline_no = story_path.parent.name.removeprefix("story_pipeline")
        row = find_matching_row(conn, pipeline_no)

        print(f"  {story_path}")
        print(f"    rm -rf {story_path.parent}")
        if row is None:
            print("    (t_movie_titlesに対応する行なし、DB操作不要)")
        else:
            genre_id, status_id = row
            print(
                f"    UPDATE t_movie_titles SET status_id = 0 WHERE id = {pipeline_no}; "
                f"-- genre_id={genre_id}, 現status_id={status_id}"
            )
    conn.close()

    print()
    print("上記のrm -rfとUPDATE文(該当ある分のみ)を実行してから、再度生成してください。")


if __name__ == "__main__":
    main()
