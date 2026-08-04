# 実機側で実行する、YouTubeへの動画アップロードスクリプト。
# authorize_youtube.py(Windows側)で作成し、~/roujin_home_senka/credentials/ に
# 転送済みの token_<genre_id>.json を使って認証する。
#
# 公開設定は必ず「限定公開」でアップロードする。事実誤認等のリスクがある
# ニュース系動画をいきなり無人で一般公開しないための安全策(2026-08-04合意)。
# 最終確認後、手動で「公開」に切り替える運用とする。

import json
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CREDENTIALS_DIR = Path.home() / "roujin_home_senka" / "credentials"
YOUTUBE_TITLE_MAX_CHARS = 100  # YouTube側の上限

args = sys.argv
if len(args) < 3:
    print(f"usage: python {Path(args[0]).name} <genre_id> <pipeline_no>")
    raise SystemExit(1)

genre_id = args[1]
pipeline_no = args[2]

OUTDIR = Path(f"jobs/story_pipeline{pipeline_no}")
token_path = CREDENTIALS_DIR / f"token_{genre_id}.json"

if not token_path.exists():
    print(f"ERROR: {token_path} がありません。先にauthorize_youtube.py(Windows側)で認証してください。")
    raise SystemExit(1)

credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)

# アクセストークンが期限切れなら、リフレッシュトークンで更新して保存し直す
if credentials.expired and credentials.refresh_token:
    credentials.refresh(Request())
    token_path.write_text(credentials.to_json(), encoding="utf-8")

youtube = build("youtube", "v3", credentials=credentials)

with open(OUTDIR / "final_story.json", encoding="utf-8") as f:
    story = json.load(f)

title = story.get("title", "")[:YOUTUBE_TITLE_MAX_CHARS]

description = ""
description_path = OUTDIR / "description.txt"
if description_path.exists():
    description = description_path.read_text(encoding="utf-8")

tags = []
tags_path = OUTDIR / "tags.txt"
if tags_path.exists():
    tags = [t.strip() for t in tags_path.read_text(encoding="utf-8").split(",") if t.strip()]

body = {
    "snippet": {
        "title": title,
        "description": description,
        "tags": tags,
        "categoryId": "25",  # News & Politics
        "defaultLanguage": "ja",
        "defaultAudioLanguage": "ja",
    },
    "status": {
        "privacyStatus": "unlisted",
        "selfDeclaredMadeForKids": False,
        # 実在の出来事を写実的なAI生成画像で描いているため、YouTubeの
        # 「AIで改変・合成されたリアルなコンテンツ」開示対象に該当する
        "containsSyntheticMedia": True,
    },
}

print(f"uploading: {title}")
media = MediaFileUpload(str(OUTDIR / "movie.mp4"), chunksize=-1, resumable=True, mimetype="video/mp4")
request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

response = None
while response is None:
    status, response = request.next_chunk()
    if status:
        print(f"upload progress: {int(status.progress() * 100)}%")

video_id = response["id"]
print(f"uploaded (limited public/限定公開): https://www.youtube.com/watch?v={video_id}")

thumbnail_path = OUTDIR / "thumbnail.png"
if thumbnail_path.exists():
    # ニュース系チャンネルは電話番号確認が未完了で、カスタムサムネイルの
    # アップロード権限が無い(403 forbidden)。動画本体のアップロードは既に
    # 成功しているので、ここで失敗してもジョブ全体は失敗させない
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail_path)),
        ).execute()
        print("thumbnail set")
    except HttpError as e:
        print(f"WARNING: thumbnail set failed (video upload itself succeeded): {e}")

(OUTDIR / "youtube_video_id.txt").write_text(video_id, encoding="utf-8")
print(f"done: {OUTDIR / 'youtube_video_id.txt'}")
