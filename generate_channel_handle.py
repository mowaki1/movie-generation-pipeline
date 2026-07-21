import sys
from pathlib import Path

import psycopg2
import pykakasi

DB_DSN = "dbname=video_pipeline"


def get_genre_name(conn, genre_id):
    with conn.cursor() as cur:
        cur.execute("SELECT genre FROM m_genres WHERE id = %s", (genre_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"genre_id {genre_id} not found in m_genres")
        return row[0]


def romanize(text):
    kks = pykakasi.kakasi()
    slug = "".join(item["hepburn"] for item in kks.convert(text))
    # ハンドルに使えない文字(記号・スペース等)を除去し、英数字のみに絞る
    slug = "".join(c for c in slug if c.isalnum())
    return slug.lower()


def build_candidates(genre_name, genre_id):
    base = romanize(genre_name)
    return [
        f"@{base}",
        f"@{base}{genre_id}",
        f"@{base}_channel",
    ]


def main():
    args = sys.argv
    if len(args) < 2:
        print(f"usage: python {Path(args[0]).name} <genre_id>")
        raise SystemExit(1)

    genre_id = int(args[1])

    outdir = Path(f"channel_art/{genre_id}")
    out_path = outdir / "handle_candidates.txt"
    if out_path.exists():
        print(f"skip (cached): {out_path}")
        return

    conn = psycopg2.connect(DB_DSN)
    genre_name = get_genre_name(conn, genre_id)
    conn.close()

    candidates = build_candidates(genre_name, genre_id)

    outdir.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(candidates), encoding="utf-8")

    print(f"candidates for {genre_name}:")
    for c in candidates:
        print(f"  {c}")
    print(f"done: {out_path}")
    print("NOTE: 実際の空き状況はYouTube側のハンドル設定画面で確認が必要です(重複はここでは検証できません)")


if __name__ == "__main__":
    main()
