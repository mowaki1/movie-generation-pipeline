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
#   python authorize_youtube.py <genre_id> <client_secret_pathへのパス> [--manual]
#   (--manual: 認証用URLを任意のブラウザ/端末で開き、認証後のURLを貼り付ける方式)
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

# 再生リスト作成・追加(ITニュースへのジャンル統合、2026-09-18)にはyoutube.uploadでは
# 権限不足(403)になるため、より広いyoutubeスコープを使う
SCOPES = ["https://www.googleapis.com/auth/youtube"]

args = [a for a in sys.argv if a != "--manual"]
manual = "--manual" in sys.argv
if len(args) < 3:
    print(f"usage: python {Path(args[0]).name} <genre_id> <client_secret_path> [--manual]")
    raise SystemExit(1)

genre_id = args[1]
client_secret_path = args[2]

flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)

if manual:
    # 既定のブラウザ(Chrome等)ではアカウント選択画面に目的のチャンネルが出ない場合や、
    # 別の端末のブラウザで認証したい場合向け。表示したURLを任意のブラウザで開いて認証し、
    # 最後に表示される(接続できないと出ても構わない)ページのURL全体を貼り付ける
    flow.redirect_uri = "http://localhost:8080/"
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    print("次のURLを、チャンネルが見えているブラウザで開いて認証してください:")
    print(auth_url)
    print()
    print("認証後、「このサイトにアクセスできません」等の画面になっても構いません。")
    print("そのときのアドレスバーのURL全体(http://localhost:8080/?state=...&code=...)をコピーして貼り付けてください。")
    response_url = input("URL> ").strip()
    # run_local_server()と同じく、oauthlibが要求するhttpsに置き換えて渡す
    flow.fetch_token(authorization_response=response_url.replace("http://", "https://", 1))
    credentials = flow.credentials
else:
    credentials = flow.run_local_server(port=0)

token_path = Path(f"token_{genre_id}.json")
token_path.write_text(credentials.to_json(), encoding="utf-8")

print(f"saved: {token_path.resolve()}")
print("このファイルをWinSCPで実機の ~/roujin_home_senka/credentials/ に転送してください。")
