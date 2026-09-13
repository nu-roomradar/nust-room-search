#!/usr/bin/env python3
"""
Instagram の長期アクセストークンを延長し、GitHub Secret を更新する。

背景: IG_ACCESS_TOKEN は発行から 60 日で失効する。2026-08-13 に切れたときは
気づくまで 3 週間かかり、その間まったく投稿できなかった。手で再発行し続けるのを
やめるため、月 1 回これを自動で回す。

仕組み:
  1. graph.instagram.com/refresh_access_token を叩いて 60 日先まで延長した新トークンを得る
     （元のトークンが「発行から 24 時間以上経過」かつ「まだ失効していない」ことが条件）
  2. 新トークンで実際に /me を引いて、使えることを確かめる
  3. 確かめてから GitHub Secret の IG_ACCESS_TOKEN を書き換える
     （libsodium の sealed box で暗号化して PUT する。GitHub API の仕様）

トークンそのものは絶対にログへ出さない。長さと末尾 4 文字だけ出す。

必要な環境変数:
  IG_ACCESS_TOKEN  現行のトークン（GitHub Secret）
  IG_REFRESH_PAT   Secrets への書き込み権限を持つ PAT。GITHUB_TOKEN では Secret を
                   書き換えられないため別途必要。作り方は docs/OPERATIONS.md
  GITHUB_REPOSITORY  "owner/repo"（Actions が自動で渡す）

使い方:
  python scripts/refresh_ig_token.py            # 延長して Secret を更新
  python scripts/refresh_ig_token.py --dry-run  # 延長の可否だけ確認し Secret は触らない
"""
import argparse
import base64
import os
import sys

import requests

GRAPH = "https://graph.instagram.com"
API_VERSION = "v21.0"
GITHUB_API = "https://api.github.com"
SECRET_NAME = "IG_ACCESS_TOKEN"
TIMEOUT = 30
# これを下回ったら警告する。月1回動く前提なので、通常は 55 日前後で回るはず
WARN_DAYS_LEFT = 14


class RefreshError(Exception):
    """処理を止めるべき失敗。メッセージは日本語でそのまま表示する"""


def mask(token):
    """ログ用。トークン本体は出さない"""
    return f"<{len(token)}文字 …{token[-4:]}>" if token and len(token) > 8 else "<不正な値>"


def api_error(resp, context):
    try:
        err = resp.json().get("error", {}) or {}
        detail = f"type={err.get('type')} code={err.get('code')} message={err.get('message')}"
    except ValueError:
        detail = resp.text[:200]
    return f"{context} -> HTTP {resp.status_code}: {detail}"


def refresh(token):
    """60 日延長した新しいトークンを返す"""
    resp = requests.get(f"{GRAPH}/refresh_access_token",
                        params={"grant_type": "ig_refresh_token", "access_token": token},
                        timeout=TIMEOUT)
    if not resp.ok:
        raise RefreshError(
            api_error(resp, "トークンの延長に失敗しました") + "\n"
            "  code=190 なら既に失効しています。この場合は自動では直せません。\n"
            "  Meta for Developers で手動で再発行してください（手順は .claude/skills/instagram-post/SKILL.md）")
    body = resp.json()
    new_token = body.get("access_token")
    expires_in = body.get("expires_in")
    if not new_token:
        raise RefreshError(f"延長のレスポンスに access_token がありません: {body}")
    return new_token, expires_in


def verify(token):
    """新しいトークンで実際にアカウントを引けるか。Secret を書き換える前に必ず通す"""
    resp = requests.get(f"{GRAPH}/{API_VERSION}/me", params={"fields": "id", "access_token": token},
                        timeout=TIMEOUT)
    if not resp.ok:
        raise RefreshError(api_error(resp, "新しいトークンが使えません。Secret は書き換えていません"))
    return resp.json().get("id")


def gh_headers(pat):
    return {"Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "roomradar-ig-token-refresh"}


def put_secret(repo, pat, name, value):
    """GitHub Secret を更新する。値は公開鍵で暗号化してから送る"""
    try:
        from nacl import encoding, public
    except ImportError as exc:                     # requirements-dev.txt に pynacl がある
        raise RefreshError(f"pynacl が入っていません（{exc}）。pip install -r requirements-dev.txt") from exc

    r = requests.get(f"{GITHUB_API}/repos/{repo}/actions/secrets/public-key",
                     headers=gh_headers(pat), timeout=TIMEOUT)
    if not r.ok:
        raise RefreshError(
            api_error(r, "Secret の公開鍵を取れません") + "\n"
            "  IG_REFRESH_PAT に、このリポジトリの Secrets への書き込み権限があるか確認してください")
    key = r.json()

    sealed = public.SealedBox(public.PublicKey(key["key"].encode(), encoding.Base64Encoder))
    encrypted = base64.b64encode(sealed.encrypt(value.encode())).decode()

    r = requests.put(f"{GITHUB_API}/repos/{repo}/actions/secrets/{name}",
                     headers=gh_headers(pat),
                     json={"encrypted_value": encrypted, "key_id": key["key_id"]},
                     timeout=TIMEOUT)
    if r.status_code not in (201, 204):
        raise RefreshError(api_error(r, f"Secret {name} の更新に失敗しました"))
    return r.status_code


def main(argv=None):
    ap = argparse.ArgumentParser(description="Instagram のアクセストークンを延長して Secret を更新する")
    ap.add_argument("--dry-run", action="store_true", help="延長の可否だけ確認し、Secret は書き換えない")
    args = ap.parse_args(argv)

    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not token:
        print("[ERROR] IG_ACCESS_TOKEN が設定されていません。", file=sys.stderr)
        return 2

    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    pat = os.environ.get("IG_REFRESH_PAT", "").strip()
    if not args.dry_run:
        if not pat:
            print("[ERROR] IG_REFRESH_PAT が設定されていません。", file=sys.stderr)
            print("        Secrets への書き込み権限を持つ PAT が要ります。"
                  "作り方は docs/OPERATIONS.md の「Instagram トークンの自動更新」。", file=sys.stderr)
            return 2
        if not repo:
            print("[ERROR] GITHUB_REPOSITORY が設定されていません（owner/repo）。", file=sys.stderr)
            return 2

    print(f"[INFO] 現行トークン: {mask(token)}")
    try:
        new_token, expires_in = refresh(token)
        days = round(expires_in / 86400) if isinstance(expires_in, int) else None
        print(f"[INFO] 延長しました: {mask(new_token)}"
              + (f" / 有効期間 約{days}日" if days is not None else ""))

        account_id = verify(new_token)
        print(f"[INFO] 新しいトークンで疎通確認できました（アカウントID {account_id}）")

        if args.dry_run:
            print("[INFO] --dry-run のため Secret は書き換えていません。")
        else:
            status = put_secret(repo, pat, SECRET_NAME, new_token)
            print(f"[INFO] Secret {SECRET_NAME} を更新しました（HTTP {status}）")

        if days is not None and days < WARN_DAYS_LEFT:
            print(f"[WARN] 延長後の残りが {days} 日しかありません。"
                  f"月1回の実行が止まっていないか確認してください。", file=sys.stderr)
    except RefreshError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f"[ERROR] 通信に失敗しました: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
