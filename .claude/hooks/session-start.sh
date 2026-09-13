#!/bin/bash
set -uo pipefail

# Claude Code on the web のセッション開始時に依存関係を揃える。
# ローカル実行時は何もしない（webのみ）。
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# requirements.txt には flask が入っており、その依存の blinker が debian 製と衝突して
# 「Cannot uninstall blinker ... installed by debian」で pip が失敗する。
# set -e のままだとここでフックごと落ち、pandas や xlrd が入らないまま
# セッションが始まってしまう（2026-09 に実際そうなった）。
# --ignore-installed blinker で回避し、失敗しても後続は続ける。
install() {
  pip install -q --ignore-installed blinker "$@" \
    || pip install -q "$@" \
    || { echo "session-start: 依存のインストールに失敗: $*" >&2; return 1; }
}

ok=0
#   requirements.txt     : アプリ本体（Renderと同じ）
#   requirements-dev.txt : 開発・運用スクリプト用（xlrd / playwright / pillow など）
# Playwright本体はpreinstall済みブラウザ(/opt/pw-browsers)を使うためinstall不要
install -r requirements.txt -r requirements-dev.txt || ok=1

# 入ったかどうかを実際に確かめる。黙って欠けたまま始めるのが一番困る
missing=$(python3 - <<'PY'
import importlib.util
need = ["flask", "pandas", "openpyxl", "requests", "xlrd"]
print(" ".join(m for m in need if importlib.util.find_spec(m) is None))
PY
) || missing="(確認スクリプトが動きませんでした)"
if [ -n "$missing" ]; then
  echo "session-start: 次のパッケージが入っていません: $missing" >&2
  echo "session-start: 手動で復旧するには pip install --ignore-installed blinker -r requirements.txt -r requirements-dev.txt" >&2
  exit 0   # セッション自体は始められるようにする（止めても直らないため）
fi

[ "$ok" -eq 0 ] && echo "session-start: dependencies ready" \
                || echo "session-start: dependencies ready（一部の install で警告あり）"
