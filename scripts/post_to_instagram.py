"""
Instagram Graph APIへフィード・ストーリーズ・リールを投稿するスクリプト。

必要な環境変数:
  IG_ACCESS_TOKEN : アクセストークン
  IG_ACCOUNT_ID   : InstagramビジネスアカウントID

使い方:
  # フィード投稿
  python post_to_instagram.py --image-url <公開URL> --caption "<キャプション>"
  # ストーリーズ投稿（キャプションは任意・ストーリーズには表示されない）
  python post_to_instagram.py --image-url <公開URL> --story
  # リール投稿（--image-url はカバー画像。省略すると動画の先頭がカバーになる）
  python post_to_instagram.py --video-url <mp4の公開URL> --image-url <カバー画像の公開URL> --caption "<キャプション>"
"""
import argparse
import os
import sys
import time
import requests

API_VERSION = "v21.0"
HOSTS = ["https://graph.instagram.com", "https://graph.facebook.com"]
TIMEOUT = 30   # 1回の通信の待ち時間（秒）。動画の変換待ちは wait_until_ready のループで別に待つ
# 自主創造プロジェクトのレギュレーションで学外SNS発信時の使用が義務付けられた共通ハッシュタグ
REQUIRED_TAGS = ["#日大生プロジェクト"]


def ensure_required_tags(caption):
    missing = [tag for tag in REQUIRED_TAGS if tag not in caption]
    if not missing:
        return caption
    return caption.rstrip() + "\n" + " ".join(missing)


def show_error(resp, context):
    try:
        err = resp.json().get("error", {})
        print(f"[ERROR] {context} -> {resp.status_code}: "
              f"type={err.get('type')} code={err.get('code')} message={err.get('message')}",
              file=sys.stderr)
    except Exception:
        print(f"[ERROR] {context} -> {resp.status_code}（本文の解析に失敗）", file=sys.stderr)


def detect_host(account_id, access_token):
    """利用可能なAPIホストを判定する"""
    for host in HOSTS:
        resp = requests.get(f"{host}/{API_VERSION}/{account_id}", params={
            "fields": "id",
            "access_token": access_token,
        }, timeout=TIMEOUT)
        if resp.ok:
            print(f"[INFO] 使用エンドポイント: {host}")
            return host
        show_error(resp, f"ホスト判定 {host}")
    raise RuntimeError("どのAPIホストでもアカウントにアクセスできませんでした。")


def create_media_container(host, account_id, access_token, image_url, caption, story=False, video_url=None):
    data = {"access_token": access_token}
    if video_url:
        # リール。フィードにも表示する。image_url はカバー画像として使う
        data.update({"media_type": "REELS", "video_url": video_url, "caption": caption, "share_to_feed": "true"})
        if image_url:
            data["cover_url"] = image_url
    elif story:
        # ストーリーズはキャプション欄を持たないため caption は付けない
        data.update({"image_url": image_url, "media_type": "STORIES"})
    else:
        data.update({"image_url": image_url, "caption": caption})
    resp = requests.post(f"{host}/{API_VERSION}/{account_id}/media", data=data, timeout=TIMEOUT)
    if not resp.ok:
        show_error(resp, "コンテナ作成")
        resp.raise_for_status()
    return resp.json()["id"]


def check_public_url(url):
    """投稿前に、Instagram が取りに行く URL が公開されているかを見ておく（失敗時の切り分け用）"""
    try:
        resp = requests.head(url, allow_redirects=True, timeout=30)
        print(f"[INFO] {url} -> {resp.status_code} {resp.headers.get('Content-Type')} {resp.headers.get('Content-Length')} bytes")
    except requests.RequestException as e:
        print(f"[WARN] {url} を確認できませんでした: {e}", file=sys.stderr)


def wait_until_ready(host, container_id, access_token, timeout=120, interval=5):
    elapsed = 0
    while elapsed < timeout:
        resp = requests.get(f"{host}/{API_VERSION}/{container_id}", params={
            "fields": "status_code",
            "access_token": access_token,
        }, timeout=TIMEOUT)
        if not resp.ok:
            show_error(resp, "ステータス確認")
            resp.raise_for_status()
        status = resp.json().get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError("メディアコンテナの処理でエラーが発生しました。")
        time.sleep(interval)
        elapsed += interval
    raise TimeoutError("メディアコンテナの準備がタイムアウトしました。")


def publish_media(host, account_id, access_token, container_id):
    resp = requests.post(f"{host}/{API_VERSION}/{account_id}/media_publish", data={
        "creation_id": container_id,
        "access_token": access_token,
    }, timeout=TIMEOUT)
    if not resp.ok:
        show_error(resp, "公開")
        resp.raise_for_status()
    return resp.json()["id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-url", help="投稿する画像の公開URL（リールではカバー画像）")
    parser.add_argument("--video-url", help="リールとして投稿する動画（mp4）の公開URL")
    parser.add_argument("--caption", default="", help="投稿のキャプション（フィード・リール）")
    parser.add_argument("--story", action="store_true", help="ストーリーズとして投稿する")
    args = parser.parse_args()

    if args.video_url and args.story:
        print("--video-url と --story は同時に使えません。", file=sys.stderr)
        sys.exit(1)
    if not args.video_url and not args.image_url:
        print("--image-url（リールなら --video-url）が必要です。", file=sys.stderr)
        sys.exit(1)
    if not args.story and not args.caption:
        print("フィード・リールの投稿には --caption が必要です。", file=sys.stderr)
        sys.exit(1)

    access_token = os.environ.get("IG_ACCESS_TOKEN")
    account_id = os.environ.get("IG_ACCOUNT_ID")

    if not access_token or not account_id:
        print("環境変数 IG_ACCESS_TOKEN / IG_ACCOUNT_ID が設定されていません。", file=sys.stderr)
        sys.exit(1)

    try:
        post(args, account_id, access_token)
    except requests.RequestException as exc:
        # 例外の文面には URL ごとトークンが入る（GET の ?access_token=...）ので、種類と状態コードだけ出す
        status = getattr(getattr(exc, "response", None), "status_code", None)
        print(f"[ERROR] 通信に失敗しました: {type(exc).__name__}" + (f"（HTTP {status}）" if status else ""),
              file=sys.stderr)
        sys.exit(1)


def post(args, account_id, access_token):
    host = detect_host(account_id, access_token)

    caption = args.caption if args.story else ensure_required_tags(args.caption)

    kind = "リール" if args.video_url else "ストーリーズ" if args.story else "フィード"
    for url in (args.video_url, args.image_url):
        if url:
            check_public_url(url)
    print(f"メディアコンテナを作成しています...（{kind}）")
    container_id = create_media_container(
        host, account_id, access_token, args.image_url, caption, story=args.story, video_url=args.video_url)
    print(f"コンテナID: {container_id}")

    print("コンテナの準備完了を待機しています...")
    # 動画は Instagram 側の変換に数分かかることがある
    if args.video_url:
        wait_until_ready(host, container_id, access_token, timeout=600, interval=10)
    else:
        wait_until_ready(host, container_id, access_token)

    print("投稿を公開しています...")
    media_id = publish_media(host, account_id, access_token, container_id)
    print(f"投稿完了！ メディアID: {media_id}")


if __name__ == "__main__":
    main()
