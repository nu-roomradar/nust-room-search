#!/usr/bin/env python3
"""
必須表記ガード — CLAUDE.md の「守るべきルール」1・2を機械的に守る hook。

  ルール1: 「テスト運用中・非公式」表記を app.py / index.html / dashboard.html から消さない
          （学生課・教務課と協議中のため、誤認防止に必須）
  ルール2: Instagram 投稿への #日大生プロジェクト 自動付与（scripts/post_to_instagram.py）を壊さない
          ポスター（scripts/make_poster.py）にも #日大生プロジェクト が必須

CLAUDE.md の指示は Claude への「お願い」でしかなく強制力がない。ここで検査して初めて保証になる。

判定の基準:
  各フレーズの出現数が「コミット済み（git HEAD）の出現数」を下回ったらブロック（最低でも1つ）。
  → 表記を別の場所へ移す（先に追加してから削除）のは通る。2箇所を1箇所に統合する編集は止まる。
  → 意図的に減らす／文言を変えるセッションでは、空ファイル .claude/guard-relax を置く（gitignore 済み。
    ウェブセッションでは Claude に作らせる。.claude/ 配下なので権限確認が出る）か、ターミナルなら
    ROOMRADAR_GUARD_RELAX=1 を付けて起動すると「最低1つ残っていればよい」判定に緩む。
    フレーズ自体を変えるときは下の GUARDED も更新する。

使い方（.claude/settings.json から呼ばれる）:
  guard-notices.py edit   PreToolUse(Edit|Write) : 編集を適用した後の内容を再現して検査
  guard-notices.py bash   PreToolUse(Bash)       : git commit / git push を含むコマンドの前に作業ツリーを検査
  guard-notices.py tree   Stop                   : Claude が応答を終える前に作業ツリーを検査。欠けていれば続行させる

終了コード: 0 = 問題なし / 2 = ブロック（stderr の内容が Claude に理由として渡る）
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ファイル（リポジトリルート基準）→ 必ず含まれていなければならない文字列
GUARDED = {
    # 検索アプリの画面は templates/index.html にある（2026-09 に app.py から分割）
    "templates/index.html":         ["テスト運用中", "大学公式"],
    "index.html":                   ["テスト運用中", "大学公式"],
    "dashboard.html":               ["テスト運用中", "大学公式"],
    "scripts/post_to_instagram.py": ["#日大生プロジェクト", "REQUIRED_TAGS", "ensure_required_tags"],
    "scripts/make_poster.py":       ["#日大生プロジェクト"],
}

RULE_OF = {
    "templates/index.html": "ルール1（テスト運用中・非公式表記）",
    "index.html": "ルール1（テスト運用中・非公式表記）",
    "dashboard.html": "ルール1（テスト運用中・非公式表記）",
    "scripts/post_to_instagram.py": "ルール2（#日大生プロジェクト の自動付与）",
    "scripts/make_poster.py": "ポスターの必須要素（#日大生プロジェクト）",
}

RELAX_MARKER = Path(".claude") / "guard-relax"

HOW_TO_CHANGE = (
    "意図的に減らす・文言を変える場合: ユーザーの明示的な指示のもとで空ファイル .claude/guard-relax を作ると"
    "（gitignore 済み・作業後に削除）、そのセッションは「最低1つ残っていればよい」判定になります。"
    "フレーズ自体を変えるときは .claude/hooks/guard-notices.py の GUARDED も更新してください。"
)


def relaxed(root):
    """逃げ道: マーカーファイル（ウェブセッション向け）または環境変数（ターミナル起動時）"""
    return (root / RELAX_MARKER).exists() or os.environ.get("ROOMRADAR_GUARD_RELAX") == "1"


def project_dir(payload):
    root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    return Path(root).resolve()


def guarded_key(file_path, root):
    """file_path が GUARDED のいずれかならそのキーを返す。対象外なら None。"""
    if not file_path:
        return None
    p = Path(file_path)
    if not p.is_absolute():
        p = root / p
    try:
        rel = p.resolve().relative_to(root).as_posix()
    except (ValueError, OSError):
        return None
    return rel if rel in GUARDED else None


def read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def head_text(root, key):
    """コミット済み（HEAD）の内容。取れなければ None。"""
    try:
        r = subprocess.run(["git", "-C", str(root), "show", f"HEAD:{key}"],
                           capture_output=True, timeout=10)
        if r.returncode == 0:
            return r.stdout.decode("utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def required_counts(root, key):
    """各フレーズに必要な最低出現数。HEAD にある数（最低1）。RELAX 時や HEAD が無いときは1。"""
    base = None if relaxed(root) else head_text(root, key)
    return {ph: (max(1, base.count(ph)) if base is not None else 1) for ph in GUARDED[key]}


def shortfalls(text, req):
    """(フレーズ, 実際の数, 必要な数) のうち足りないもの"""
    return [(ph, text.count(ph), n) for ph, n in req.items() if text.count(ph) < n]


def describe(short):
    return "、".join(f"{ph!r} が {have} 箇所（必要 {need}）" for ph, have, need in short)


def block(lines):
    print("\n".join(lines), file=sys.stderr)
    sys.exit(2)


def check_tree(root):
    problems = []
    for key in GUARDED:
        f = root / key
        if not f.exists():
            problems.append(f"  - {key}: ファイルが存在しません")
            continue
        short = shortfalls(read_text(f), required_counts(root, key))
        if short:
            problems.append(f"  - {key}: {describe(short)} — {RULE_OF[key]}")
    return problems


def cmd_tree(payload, context):
    problems = check_tree(project_dir(payload))
    if problems:
        block([f"必須表記ガード: {context}。CLAUDE.md で保護された表記がコミット済みの状態より減っています。",
               *problems,
               "対処: 該当の表記を復元してください。",
               HOW_TO_CHANGE])


def cmd_bash(payload):
    command = (payload.get("tool_input") or {}).get("command", "") or ""
    # 「git … commit」「git … push」を含むコマンドだけを対象にする（git -c … commit のような形も拾う）
    if not re.search(r"\bgit\b[^|;&\n]*\b(commit|push)\b", command):
        return
    cmd_tree(payload, "git commit / push を実行できません")


def cmd_edit(payload):
    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input") or {}
    root = project_dir(payload)
    key = guarded_key(ti.get("file_path", ""), root)
    if not key:
        return

    current = read_text(root / key)

    if tool == "Write":
        after = ti.get("content", "") or ""
    elif tool == "Edit":
        old, new = ti.get("old_string", "") or "", ti.get("new_string", "") or ""
        if old not in current:
            return  # Edit 自体が失敗するので、判断はツールに任せる
        after = current.replace(old, new) if ti.get("replace_all") else current.replace(old, new, 1)
    elif tool == "MultiEdit":
        after = current
        for e in ti.get("edits") or []:
            old, new = e.get("old_string", "") or "", e.get("new_string", "") or ""
            if old not in after:
                return
            after = after.replace(old, new) if e.get("replace_all") else after.replace(old, new, 1)
    else:
        return

    short = shortfalls(after, required_counts(root, key))
    if short:
        block([f"必須表記ガード: この編集で {key} の {describe(short)} になるためブロックしました。",
               f"理由: CLAUDE.md {RULE_OF[key]} で保護されており、コミット済みの状態より減らす編集は通しません。",
               "対処: その表記を残す形で編集し直してください。別の場所へ移す場合は、先に追加してから元を削除してください。",
               HOW_TO_CHANGE])


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "tree"
    payload = {}
    if not sys.stdin.isatty():
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            payload = {}

    if mode == "edit":
        cmd_edit(payload)
    elif mode == "bash":
        cmd_bash(payload)
    else:
        # Stop hook が一度「続行」を返した直後は再ブロックしない（ループ防止）
        if payload.get("stop_hook_active"):
            return
        cmd_tree(payload, "作業を終了できません")


if __name__ == "__main__":
    main()
