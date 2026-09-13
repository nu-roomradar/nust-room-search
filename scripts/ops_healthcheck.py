#!/usr/bin/env python3
"""
運用ヘルスチェック — 「静かに壊れている」状態を検知して GitHub Issue で知らせる。

背景: Instagram の長期アクセストークンが 2026-08-13 に失効し、以降の自動実行が全て
失敗していたことに 9/3 まで（3週間）気づかなかった。人が見に行かなくても異常が
Issue として届くようにする。LLM は使わない（決定論的・無料・API キー不要）。

チェック項目:
  1. 検索アプリ（Render）が応答し、「テスト運用中」表記が本番ページに残っているか
  2. LP（GitHub Pages）が応答し、同表記が残っているか
  3. 直近 N 日の GitHub Actions 実行に失敗がないか
  4. GitHub に自動無効化されたワークフローがないか（public リポジトリは60日間活動が無いと止まる）
  5. IG_ACCESS_TOKEN が有効か（設定されている場合のみ。失効なら再発行を促す）

結果の扱い:
  問題あり → 固定タイトルの Issue を作成（既にあれば本文を更新。検知内容が変わった時だけコメントも付ける）
  問題なし → 開いている同名 Issue があれば「復旧を確認」とコメントして閉じる
  スクリプト自体は正常に動けば常に終了コード 0（サイトが落ちていても Action は緑。通知は Issue で行う）

使い方:
  python scripts/ops_healthcheck.py --dry-run           # 結果を表示するだけ（Issue に触らない）
  python scripts/ops_healthcheck.py --dry-run --skip-urls  # 外部URLを叩かない（ローカル動作確認用）
  python scripts/ops_healthcheck.py                     # 本番（Actions から週1回）
環境変数: GITHUB_TOKEN, GITHUB_REPOSITORY（Actions が自動で渡す）, IG_ACCESS_TOKEN（任意）

注意: このワークフロー自身も60日ルールで止まりうる。止まると自分では検知できないので、
      リポジトリに何らかの活動（コミット）を保つこと。
"""
import argparse
import hashlib
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

APP_URL = "https://nust-room-search.onrender.com"
LP_URL = "https://nu-roomradar.github.io/nust-room-search/"
REQUIRED_NOTICE = "テスト運用中"  # CLAUDE.md ルール1。本番ページに残っているかを見る
RUN_LOOKBACK_DAYS = 14
ISSUE_TITLE = "【運用ヘルスチェック】異常を検知しました"
FINGERPRINT_TAG = "healthcheck-fingerprint"
GITHUB_API = "https://api.github.com"
IG_HOSTS = ["https://graph.instagram.com", "https://graph.facebook.com"]
IG_API_VERSION = "v21.0"
USER_AGENT = "roomradar-ops-healthcheck"
FAILED_CONCLUSIONS = {"failure", "timed_out", "startup_failure"}


@dataclass
class Result:
    ok: list = field(default_factory=list)        # 確認できたこと
    problems: list = field(default_factory=list)  # (見出し, 詳細) — 要対応
    notes: list = field(default_factory=list)     # 問題ではないが伝えたいこと

    def problem(self, title, detail=""):
        self.problems.append((title, detail))

    @property
    def fingerprint(self):
        """検知内容の同一性判定用。見出しの集合が同じなら同じ状態とみなす"""
        key = "\n".join(sorted(t for t, _ in self.problems))
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------- GitHub API

class GitHub:
    def __init__(self, token, repo, session=None):
        self.repo = repo
        self.s = session or requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        })

    def _req(self, method, path, **kw):
        r = self.s.request(method, f"{GITHUB_API}{path}", timeout=30, **kw)
        r.raise_for_status()
        return r.json() if r.content else None

    def get(self, path, **params):
        return self._req("GET", path, params=params)

    def post(self, path, payload):
        return self._req("POST", path, json=payload)

    def patch(self, path, payload):
        return self._req("PATCH", path, json=payload)


# ---------------------------------------------------------------- checks

def check_url(res, label, url, must_contain, attempts=3, wait=20, sleep=time.sleep):
    """200 かつ本文に must_contain を含めば OK。Render の無料プランはスリープ復帰に時間がかかるので再試行する"""
    last = None
    for i in range(attempts):
        try:
            r = requests.get(url, timeout=(10, 90), headers={"User-Agent": USER_AGENT})
            if r.status_code == 200:
                if must_contain in r.text:
                    res.ok.append(f"{label}: 200 OK、「{must_contain}」表記あり")
                else:
                    res.problem(f"{label}: 「{must_contain}」表記が本番ページに見当たりません",
                                f"{url} は 200 を返しましたが、必須表記（CLAUDE.md ルール1）が本文にありません。"
                                "直近のデプロイ内容を確認してください。")
                return
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = type(e).__name__
        if i < attempts - 1:
            sleep(wait)
    res.problem(f"{label}: 応答がありません（{last}）",
                f"{url} に {attempts} 回アクセスしましたが正常な応答が得られませんでした。"
                "Render のスリープ復帰が遅いだけの可能性もあるので、まず手動で開いて確認してください。")


_UNSET = object()      # 「省略」と「None を明示」を区別するための番兵


def existing_workflow_paths(root=None):
    """リポジトリに今ある .github/workflows のパス集合

    撤去したワークフローの古い失敗を報告し続けないために使う。
    ファイルが無ければ二度と実行されないので、報告しても直しようがない。
    """
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    d = root / ".github" / "workflows"
    if not d.is_dir():
        return None                      # 判定材料が無いときは絞り込まない
    return {f".github/workflows/{p.name}" for p in d.iterdir()
            if p.is_file() and p.suffix in (".yml", ".yaml")}


def check_recent_runs(res, gh, days=RUN_LOOKBACK_DAYS, now=None, known_paths=_UNSET):
    """known_paths: 省略ならリポジトリから読む。None を明示すると絞り込まない"""
    now = now or datetime.now(timezone.utc)
    if known_paths is _UNSET:
        known_paths = existing_workflow_paths()
    since = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    data = gh.get(f"/repos/{gh.repo}/actions/runs", per_page=100, created=f">={since}")

    # ワークフローごとに新しい順へ。判定に使うのは「いちばん新しい完了した実行」だけ。
    # 「直近N日に1回でも失敗したか」で見ると、直した後も N 日間ずっと報告し続けてしまい、
    # Issue が「もう直っているのに赤いまま」になる（2026-09 に実際そうなった）。
    by_workflow = {}
    removed = set()
    for run in data.get("workflow_runs", []):
        path = run.get("path")
        if known_paths is not None and path and path not in known_paths:
            removed.add(run.get("name") or path)      # 撤去済み。直しようがないので報告しない
            continue
        by_workflow.setdefault(run.get("name") or path or "?", []).append(run)
    if removed:
        res.notes.append("撤去済みのワークフローの古い実行は判定から除きました: "
                         + "、".join(sorted(removed)))

    broken = False
    for name, runs in sorted(by_workflow.items()):
        runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        done = [r for r in runs if r.get("status") == "completed" and r.get("conclusion")]
        if not done:
            continue                                    # まだ実行中のものしかない
        latest = done[0]
        if latest.get("conclusion") not in FAILED_CONCLUSIONS:
            continue                                    # 最新が通っている = いま壊れていない
        broken = True
        streak = 0
        for r in done:                                  # 直近で何回続けて失敗しているか
            if r.get("conclusion") not in FAILED_CONCLUSIONS:
                break
            streak += 1
        hint = ""
        if "instagram" in name.lower():
            hint = ("\nInstagram 系の失敗は IG_ACCESS_TOKEN の失効（約60日）をまず疑ってください。"
                    "自動更新については docs/OPERATIONS.md 4.5。")
        res.problem(f"Actions「{name}」が失敗しています（{streak} 回連続）",
                    f"最新の失敗: {latest.get('created_at', '')[:10]} {latest.get('html_url', '')}{hint}")

    if not broken:
        res.ok.append(f"GitHub Actions: 直近{days}日のワークフローはすべて最新の実行が成功しています")


def check_disabled_workflows(res, gh):
    data = gh.get(f"/repos/{gh.repo}/actions/workflows", per_page=100)
    auto_disabled = []
    for wf in data.get("workflows", []):
        state = wf.get("state")
        name = wf.get("name") or wf.get("path")
        if state == "disabled_inactivity":
            auto_disabled.append(name)
        elif state == "disabled_manually":
            res.notes.append(f"ワークフロー「{name}」は手動で無効化されています（意図したものなら対応不要）")
    if auto_disabled:
        res.problem("GitHub にワークフローが自動無効化されています: " + "、".join(auto_disabled),
                    "public リポジトリは60日間コミット等の活動が無いと schedule 実行が止められます。"
                    "Actions タブで該当ワークフローを開き「Enable workflow」を押すと復帰します。")
    else:
        res.ok.append("GitHub Actions: 自動無効化されたワークフローはありません")


def check_ig_token(res, token):
    if not token:
        res.notes.append("IG_ACCESS_TOKEN が未設定のため、Instagram トークンの確認はスキップしました")
        return
    last = None
    for host in IG_HOSTS:
        try:
            r = requests.get(f"{host}/{IG_API_VERSION}/me",
                             params={"fields": "id", "access_token": token},
                             timeout=30, headers={"User-Agent": USER_AGENT})
        except requests.RequestException as e:
            last = type(e).__name__
            continue
        if r.ok:
            res.ok.append("Instagram: アクセストークンは有効です")
            return
        try:
            err = r.json().get("error", {}) or {}
        except ValueError:
            err = {}
        code, msg = err.get("code"), str(err.get("message", ""))
        # 190 = OAuthException（失効・無効）。メッセージは伏せず載せてよい（トークン自体は含まれない）
        if code == 190 or "expired" in msg.lower():
            res.problem("Instagram のアクセストークンが失効しています",
                        "長期トークンは約60日で失効します。Meta for Developers のアプリ設定"
                        "（Instagram → API設定）で再発行し、GitHub Secrets の IG_ACCESS_TOKEN を更新してください。"
                        "更新するまで投稿ワークフローは失敗します。")
            return
        last = f"HTTP {r.status_code} code={code} {msg}".strip()
    res.problem("Instagram API に到達できません", last or "不明なエラー")


# ---------------------------------------------------------------- report / issue

def render_report(res, now, run_url=None):
    head = f"最終チェック: {now:%Y-%m-%d %H:%M} UTC"
    if run_url:
        head += f"（[実行ログ]({run_url})）"
    lines = [head, ""]
    if res.problems:
        lines += ["## 要対応", ""]
        for title, detail in res.problems:
            lines.append(f"- **{title}**")
            lines += [f"  {l}" for l in detail.splitlines() if l.strip()]
    else:
        lines += ["## 異常なし", ""]
    if res.ok:
        lines += ["", "## 確認済み", ""] + [f"- {x}" for x in res.ok]
    if res.notes:
        lines += ["", "## 補足", ""] + [f"- {x}" for x in res.notes]
    lines += ["", "---",
              "_この Issue は `.github/workflows/ops-healthcheck.yml`（`scripts/ops_healthcheck.py`）が"
              "自動で作成・更新し、復旧を検知すると自動で閉じます。_"]
    return "\n".join(lines)


def find_open_issue(gh):
    for it in gh.get(f"/repos/{gh.repo}/issues", state="open", per_page=100):
        if "pull_request" in it:
            continue
        if it.get("title") == ISSUE_TITLE:
            return it
    return None


def sync_issue(gh, res, body, dry_run=False, out=print):
    marker = f"<!-- {FINGERPRINT_TAG}: {res.fingerprint} -->"
    full = f"{body}\n{marker}"
    issue = find_open_issue(gh)
    num = issue["number"] if issue else None

    if res.problems:
        if issue is None:
            if dry_run:
                out(f"[dry-run] Issue「{ISSUE_TITLE}」を新規作成します")
                return "create"
            gh.post(f"/repos/{gh.repo}/issues", {"title": ISSUE_TITLE, "body": full})
            return "create"
        changed = marker not in (issue.get("body") or "")
        if dry_run:
            out(f"[dry-run] Issue #{num} を更新します（検知内容の変化: {'あり' if changed else 'なし'}）")
            return "update"
        gh.patch(f"/repos/{gh.repo}/issues/{num}", {"body": full})
        if changed:
            summary = "\n".join(f"- {t}" for t, _ in res.problems)
            gh.post(f"/repos/{gh.repo}/issues/{num}/comments",
                    {"body": f"検知内容が変わったため本文を更新しました。現在の要対応:\n\n{summary}"})
        return "update"

    if issue is not None:
        if dry_run:
            out(f"[dry-run] Issue #{num} を「復旧」として閉じます")
            return "close"
        gh.post(f"/repos/{gh.repo}/issues/{num}/comments",
                {"body": f"復旧を確認しました。自動で閉じます。\n\n{body}"})
        gh.patch(f"/repos/{gh.repo}/issues/{num}", {"state": "closed", "state_reason": "completed"})
        return "close"
    return "none"


# ---------------------------------------------------------------- main

def run_checks(gh, ig_token, skip_urls=False, now=None):
    res = Result()
    if not skip_urls:
        check_url(res, "検索アプリ（Render）", APP_URL, REQUIRED_NOTICE)
        check_url(res, "LP（GitHub Pages）", LP_URL, REQUIRED_NOTICE)
    check_recent_runs(res, gh, now=now)
    check_disabled_workflows(res, gh)
    check_ig_token(res, ig_token)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="RoomRadar 運用ヘルスチェック")
    ap.add_argument("--dry-run", action="store_true", help="結果を表示するだけで Issue に触らない")
    ap.add_argument("--skip-urls", action="store_true", help="外部URLのチェックを省略する（ローカル確認用）")
    args = ap.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("[ERROR] GITHUB_TOKEN と GITHUB_REPOSITORY が必要です", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc)
    gh = GitHub(token, repo)
    res = run_checks(gh, os.environ.get("IG_ACCESS_TOKEN"), skip_urls=args.skip_urls, now=now)

    run_url = None
    if os.environ.get("GITHUB_RUN_ID"):
        server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
        run_url = f"{server}/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"

    body = render_report(res, now, run_url)
    print(body)
    print()
    action = sync_issue(gh, res, body, dry_run=args.dry_run)
    print(f"[INFO] 要対応 {len(res.problems)} 件 / Issue 操作: {action}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
