from pathlib import Path

import psycopg2

DB_DSN = "dbname=video_pipeline"
TITLES_DIR = Path("titles")


def genre_already_imported(conn, genre_id):
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM t_movie_titles WHERE genre_id = %s LIMIT 1", (genre_id,))
        return cur.fetchone() is not None


def main():
    conn = psycopg2.connect(DB_DSN)
    total_inserted = 0

    for path in sorted(TITLES_DIR.glob("*.txt")):
        genre_id = int(path.stem)

        if genre_already_imported(conn, genre_id):
            print(f"{path.name}: skip (already imported)")
            continue

        titles = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

        with conn.cursor() as cur:
            for title in titles:
                cur.execute(
                    "INSERT INTO t_movie_titles (genre_id, movie_title) VALUES (%s, %s)",
                    (genre_id, title),
                )
        conn.commit()

        print(f"{path.name}: inserted {len(titles)}")
        total_inserted += len(titles)

    conn.close()
    print(f"done: {total_inserted} titles inserted")


if __name__ == "__main__":
    main()
