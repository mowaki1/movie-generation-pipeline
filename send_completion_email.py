import json
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

args = sys.argv
if len(args) < 2:
    print(f"usage: python {Path(args[0]).name} <pipeline_no>")
    raise SystemExit(1)

OUTDIR = Path(f"jobs/story_pipeline{args[1]}")

GMAIL_ADDRESS = "asuneet1966@gmail.com"
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
NOTIFY_EMAIL_TO = "asuneet1966@gmail.com"

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def main():
    if not GMAIL_APP_PASSWORD:
        print("ERROR: GMAIL_APP_PASSWORD environment variable is not set")
        raise SystemExit(1)

    with open(OUTDIR / "final_story.json", encoding="utf-8") as f:
        story = json.load(f)
    title = story.get("title") or f"story_pipeline{args[1]}"

    description_path = OUTDIR / "description.txt"
    description = (
        description_path.read_text(encoding="utf-8")
        if description_path.exists()
        else "(概要欄は生成されていません)"
    )

    movie_path = (OUTDIR / "movie.mp4").resolve()

    msg = EmailMessage()
    msg["Subject"] = f"動画生成完了: {title}"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = NOTIFY_EMAIL_TO
    msg.set_content(
        f"動画の生成が完了しました。\n\n"
        f"タイトル: {title}\n"
        f"保存先: {movie_path}\n\n"
        f"あらすじ:\n{description}\n"
    )

    thumbnail_path = OUTDIR / "thumbnail.png"
    if thumbnail_path.exists():
        msg.add_attachment(
            thumbnail_path.read_bytes(),
            maintype="image",
            subtype="png",
            filename="thumbnail.png",
        )

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)

    print(f"done: notification email sent to {NOTIFY_EMAIL_TO}")


if __name__ == "__main__":
    main()
