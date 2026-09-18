# 実機側で実行する、YouTubeへの動画アップロードスクリプト。
# authorize_youtube.py(Windows側)で作成し、~/roujin_home_senka/credentials/ に
# 転送済みの token_<genre_id>.json を使って認証する。
#
# 公開設定は「公開」でアップロードする。以前は事実誤認等のリスクがある
# ニュース系動画を無人でいきなり一般公開しないため「限定公開」+手動確認と
# していた(2026-08-04合意)が、2026-09-18に全ジャンル即時公開へ方針変更。

import json
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# 再生リスト作成・追加にはyoutube.uploadでは権限不足(403)になるため、より広い
# youtubeスコープを使う(2026-09-18、ITニュース統合対応)。token_10002.jsonは
# このスコープで再認証済みであること
SCOPES = ["https://www.googleapis.com/auth/youtube"]
CREDENTIALS_DIR = Path.home() / "roujin_home_senka" / "credentials"
YOUTUBE_TITLE_MAX_CHARS = 100  # YouTube側の上限

DEFAULT_CATEGORY_ID = "25"  # News & Politics(ニュース系10001〜10009向け)
CATEGORY_ID_BY_GENRE = {
    "3003": "27",  # ITの教室 → Education
    "3004": "27",  # 資産運用系 → Education
}

# 9チャンネルに分散すると個々の登録者数・総再生時間(収益化条件)の伸びが遅く
# なるため、ITニュース(10002)にジャンルを統合する(地政学=10005のみ従来通り
# 独立維持、2026-09-18合意)。記事分類・脚本生成は従来通りジャンルごとに行い、
# アップロード先のチャンネルと再生リスト分けだけをここで統合する
MERGED_INTO_GENRE_ID = "10002"
MERGE_SOURCE_GENRE_IDS = {"10001", "10003", "10004", "10006", "10007", "10008", "10009"}
PLAYLIST_TITLE_BY_GENRE = {
    "10001": "AIニュース",
    "10003": "GPUニュース",
    "10004": "金融ニュース",
    "10006": "科学ニュース",
    "10007": "医療ニュース",
    "10008": "Linuxニュース",
    "10009": "セキュリティニュース",
}

args = sys.argv
if len(args) < 3:
    print(f"usage: python {Path(args[0]).name} <genre_id> <pipeline_no>")
    raise SystemExit(1)

genre_id = args[1]
pipeline_no = args[2]

OUTDIR = Path(f"jobs/story_pipeline{pipeline_no}")
upload_token_genre_id = MERGED_INTO_GENRE_ID if genre_id in MERGE_SOURCE_GENRE_IDS else genre_id
token_path = CREDENTIALS_DIR / f"token_{upload_token_genre_id}.json"

video_id_path = OUTDIR / "youtube_video_id.txt"
if video_id_path.exists():
    # 他の工程と同様、既にアップロード済みなら再実行しない
    # (後続工程の失敗でrun_news_pipeline.py全体がリトライされた際、
    # 同じ動画を重複投稿してしまうのを防ぐ)
    print(f"skip (cached): {video_id_path}")
    raise SystemExit(0)

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
        "categoryId": CATEGORY_ID_BY_GENRE.get(genre_id, DEFAULT_CATEGORY_ID),
        # defaultLanguage(タイトルと説明の言語)を設定すると、YouTube側の
        # 自動字幕が生成・表示されるようになることが実機での比較で確認された
        # ため外している。defaultAudioLanguageは音声言語の申告として残す
        "defaultAudioLanguage": "ja",
    },
    "status": {
        "privacyStatus": "public",
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
print(f"uploaded (public/公開): https://www.youtube.com/watch?v={video_id}")

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

playlist_title = PLAYLIST_TITLE_BY_GENRE.get(genre_id)
if playlist_title:
    try:
        playlist_id = None
        request = youtube.playlists().list(part="snippet", mine=True, maxResults=50)
        while request is not None and playlist_id is None:
            response = request.execute()
            for item in response.get("items", []):
                if item["snippet"]["title"] == playlist_title:
                    playlist_id = item["id"]
                    break
            request = youtube.playlists().list_next(request, response)

        if playlist_id is None:
            created = youtube.playlists().insert(
                part="snippet,status",
                body={
                    "snippet": {"title": playlist_title},
                    "status": {"privacyStatus": "unlisted"},
                },
            ).execute()
            playlist_id = created["id"]
            print(f"created playlist: {playlist_title} ({playlist_id})")

        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        ).execute()
        print(f"added to playlist: {playlist_title}")
    except HttpError as e:
        # 動画本体のアップロードは既に成功しているので、再生リスト追加の
        # 失敗(権限不足等)でジョブ全体を失敗させない
        print(f"WARNING: playlist add failed (video upload itself succeeded): {e}")

(OUTDIR / "youtube_video_id.txt").write_text(video_id, encoding="utf-8")
print(f"done: {OUTDIR / 'youtube_video_id.txt'}")
