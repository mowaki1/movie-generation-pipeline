import zipfile
from pathlib import Path

import psycopg2

DB_DSN = "dbname=video_pipeline"
OUTPUT_ZIP = "all_final_stories.zip"


def get_latest_completed_per_genre(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (genre_id) genre_id, id
            FROM t_movie_titles
            WHERE status_id = 3
            ORDER BY genre_id, id DESC
            """
        )
        return cur.fetchall()


def main():
    conn = psycopg2.connect(DB_DSN)
    rows = get_latest_completed_per_genre(conn)
    conn.close()

    if not rows:
        print("完了済み(status_id=3)のジョブが見つかりませんでした")
        raise SystemExit(1)

    missing = []
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for genre_id, pipeline_no in rows:
            story_path = Path(f"jobs/story_pipeline{pipeline_no}/final_story.json")
            if not story_path.exists():
                missing.append((genre_id, pipeline_no))
                continue
            zf.write(story_path, arcname=f"genre_{genre_id}_pipeline_{pipeline_no}.json")

    if missing:
        print("WARNING: final_story.jsonが見つからなかったジョブ:")
        for genre_id, pipeline_no in missing:
            print(f"  genre_id={genre_id} pipeline_no={pipeline_no}")

    print(f"done: {OUTPUT_ZIP} ({len(rows) - len(missing)}/{len(rows)} genres)")


if __name__ == "__main__":
    main()
