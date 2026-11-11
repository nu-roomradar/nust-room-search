"""この環境に入っているブラウザ（Chrome）の場所を探す。ポスター・ストーリーなど、画像を書き出すスクリプトが使う。

Claude Code on the web の環境には Playwright 用のブラウザが /opt/pw-browsers に入っているが、
フォルダ名の番号（chromium-1194 → chromium-1243 …）は環境が作り直されるたびに変わる。
番号を決め打ちにしていたら、環境が新しくなったとたんに画像が作れなくなった（2026-11）ので、ここで探す。

探す順:
  1. /opt/pw-browsers/chromium（いま入っているブラウザを指す、番号の付かない名前）
  2. /opt/pw-browsers/chromium-<番号>/chrome-linux*/chrome のうち番号がいちばん大きいもの

どちらも無いとき（GitHub Actions など）は None を返す。Playwright の launch(executable_path=None) は
`playwright install` で入れたブラウザを使うので、そのまま渡してよい。
環境変数 CHROME_PATH などは見ない（この環境が別の用途で入れていて、指す先が変わりうるため）。
"""
import glob
import os
import re

PW_BROWSERS = "/opt/pw-browsers"


def _build_number(path):
    m = re.search(r"chromium-(\d+)", path)
    return int(m.group(1)) if m else -1


def find_chrome(root=PW_BROWSERS):
    """使えるブラウザの実行ファイルの場所。無ければ None"""
    numbered = sorted(glob.glob(os.path.join(root, "chromium-*", "chrome-linux*", "chrome")),
                      key=_build_number, reverse=True)
    for path in [os.path.join(root, "chromium"), *numbered]:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


if __name__ == "__main__":
    print(find_chrome() or "（見つかりません。Playwright の既定のブラウザを使います）")
