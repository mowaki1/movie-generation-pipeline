import subprocess
import sys
from pathlib import Path

import psycopg2
from PIL import Image, ImageDraw, ImageFont

DB_DSN = "dbname=video_pipeline"

FONT_NAME = "BIZ UDPGothic"

ICON_SIZE = 800
BANNER_SIZE = (2560, 1440)

# ジャンル系統ごとの配色(背景色, 文字色)
FAMILY_COLORS = {
    "drama": ("#6B2737", "#F5E6C8"),   # 1000番台: ワインレッド
    "trivia": ("#4A2E6B", "#F5E6C8"),  # 3000番台: 紫
    "study": ("#1F4E79", "#F5E6C8"),   # 2000番台: 紺色
    "news": ("#2B2B2B", "#C0392B"),    # 10000番台: チャコールグレー+赤
}

TAGLINE = "AI自動生成チャンネル"


def get_family(genre_id):
    if 1000 <= genre_id < 2000:
        return "drama"
    if 2000 <= genre_id < 3000:
        return "study"
    if 3000 <= genre_id < 4000:
        return "trivia"
    if 10000 <= genre_id < 20000:
        return "news"
    raise ValueError(f"unknown genre_id {genre_id}")


def get_genre_name(conn, genre_id):
    with conn.cursor() as cur:
        cur.execute("SELECT genre FROM m_genres WHERE id = %s", (genre_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"genre_id {genre_id} not found in m_genres")
        return row[0]


def resolve_font_path(font_name=FONT_NAME):
    result = subprocess.run(
        ["fc-match", "-f", "%{file}", font_name],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def draw_centered_text(draw, text, font, center_x, center_y, fill):
    bbox = font.getbbox(text)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = center_x - w // 2 - bbox[0]
    y = center_y - h // 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=fill)


def make_icon(genre_name, bg_color, accent_color, font_path, out_path):
    img = Image.new("RGB", (ICON_SIZE, ICON_SIZE), bg_color)
    draw = ImageDraw.Draw(img)

    # 小さく円形表示されるため、先頭1文字のみをロゴ的に大きく配置する
    label = genre_name[0]
    font = ImageFont.truetype(font_path, 420)
    draw_centered_text(draw, label, font, ICON_SIZE // 2, ICON_SIZE // 2, accent_color)

    img.save(out_path)


def make_banner(genre_name, bg_color, accent_color, font_path, out_path):
    img = Image.new("RGB", BANNER_SIZE, bg_color)
    draw = ImageDraw.Draw(img)

    cx, cy = BANNER_SIZE[0] // 2, BANNER_SIZE[1] // 2

    # 中央のセーフエリア(約1546x423)内に収まるようフォントサイズを抑えている
    title_font = ImageFont.truetype(font_path, 110)
    tagline_font = ImageFont.truetype(font_path, 40)

    draw_centered_text(draw, genre_name, title_font, cx, cy - 90, accent_color)
    draw_centered_text(draw, TAGLINE, tagline_font, cx, cy + 60, accent_color)

    img.save(out_path)


def main():
    args = sys.argv
    if len(args) < 2:
        print(f"usage: python {Path(args[0]).name} <genre_id>")
        raise SystemExit(1)

    genre_id = int(args[1])
    family = get_family(genre_id)
    bg_color, accent_color = FAMILY_COLORS[family]

    conn = psycopg2.connect(DB_DSN)
    genre_name = get_genre_name(conn, genre_id)
    conn.close()

    font_path = resolve_font_path()

    outdir = Path(f"channel_art/{genre_id}")
    outdir.mkdir(parents=True, exist_ok=True)

    make_icon(genre_name, bg_color, accent_color, font_path, outdir / "icon.png")
    make_banner(genre_name, bg_color, accent_color, font_path, outdir / "banner.png")

    print(f"done: {outdir / 'icon.png'}, {outdir / 'banner.png'}")


if __name__ == "__main__":
    main()
