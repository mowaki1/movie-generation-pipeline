# YouTube投稿用のOAuth初回認証スクリプト。
#
# 重要: これは実機(ヘッドレスサーバー)ではなく、ブラウザのあるこのWindows機で
# 実行すること。Googleは2022年にサーバー上だけで完結する認証方式(OOBフロー、
# コンソールに表示された確認コードを手入力する方式)を廃止したため、
# run_local_server()でこのマシン上に一時的なローカルサーバーを立て、
# ブラウザでの同意画面経由で認証を完了する必要がある。
#
# 使い方:
#   pip install google-auth-oauthlib google-api-python-client
#   python authorize_youtube.py <genre_id> <client_secret_pathへのパス>
#
# 完了すると token_<genre_id>.json がこのディレクトリに生成されるので、
# それをWinSCPで実機の ~/roujin_home_senka/credentials/ に転送すること。
#
# 認証時、同じGoogleアカウントに複数チャンネル(ブランドアカウント)が
# 紐づいている場合、「どのチャンネルとして許可するか」を選ぶ画面が
# 表示されるので、対象のニュースチャンネルを選ぶこと。

import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

args = sys.argv
if len(args) < 3:
    print(f"usage: python {Path(args[0]).name} <genre_id> <client_secret_path>")
    raise SystemExit(1)

genre_id = args[1]
client_secret_path = args[2]

flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
credentials = flow.run_local_server(port=0)

token_path = Path(f"token_{genre_id}.json")
token_path.write_text(credentials.to_json(), encoding="utf-8")

print(f"saved: {token_path.resolve()}")
print("このファイルをWinSCPで実機の ~/roujin_home_senka/credentials/ に転送してください。")
