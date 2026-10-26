#!/usr/bin/env python3
"""検索アプリ（Render）に main の変更を反映するかどうかを決める（.github/workflows/render-deploy.yml から呼ぶ）。

Render の自動デプロイは切ってあり（2026-10-26 運営決定）、アプリの変更はこの判定を通って
Deploy Hook で反映される。再デプロイすると「実は使われていた」報告が消えるので、授業のある時間
（月〜土 9:00〜20:30）には出さず、その日の夜の定期実行（20:40）にまとめて出す。

判定（上から順に）:
  1. --force なら、時間に関係なく出す（急ぎの直し。報告は消える）
  2. 前回反映したコミットからアプリに関わるファイルが変わっていなければ、出さない
     （LP・ダッシュボード・docs・GA4 の記録だけの変更で Render を作り直さない）
  3. 授業のある時間なら、出さない（夜の定期実行に回す）
  4. それ以外は出す。前回反映したコミットが分からない（初回など）ときも出す

  python scripts/render_deploy.py --base <前回反映したコミット> [--force]
  結果は標準出力と、GitHub Actions では $GITHUB_OUTPUT の deploy=true/false に書く。
"""
import argparse
import datetime
import os
import subprocess
import sys

JST = datetime.timezone(datetime.timedelta(hours=9))
# Render が動かしているもの（ビルドは requirements.txt、起動は app.py。app.py は schedule_final.db・templates・static を読む）
APP_FILES = {"app.py", "school_bookings.py", "requirements.txt", "schedule_final.db"}
APP_DIRS = ("templates/", "static/")
# 授業のある時間。1限 9:00 〜 6限 20:30（app.py の PERIODS）。土曜にも授業がある。祝日は区別しない（夜に回るだけ）
CLASS_DAYS = range(0, 6)
CLASS_START, CLASS_END = datetime.time(9, 0), datetime.time(20, 30)


def in_class_hours(now):
    return now.weekday() in CLASS_DAYS and CLASS_START <= now.time() < CLASS_END


def app_changes(changed):
    """変わったファイルのうち、Render の反映が要るもの"""
    return [f for f in changed if f in APP_FILES or f.startswith(APP_DIRS)]


def decide(changed, now, force=False):
    """changed は前回反映したコミットから変わったファイル（前回が分からなければ None）。(出すか, 理由) を返す"""
    if force:
        return True, "手動で即時反映（force）。いまある報告は消えます"
    if changed is not None and not app_changes(changed):
        return False, "前回の反映からアプリに関わる変更はありません"
    if in_class_hours(now):
        return False, "授業のある時間（月〜土 9:00〜20:30）なので、今夜 20:40 の定期実行で反映します"
    if changed is None:
        return True, "前回反映したコミットが分からないので反映します"
    return True, "アプリの変更を反映します: " + ", ".join(app_changes(changed)[:10])


def changed_since(base):
    """base から HEAD までに変わったファイル。base が空・履歴に無いときは None"""
    if not base:
        return None
    r = subprocess.run(["git", "diff", "--name-only", base, "HEAD"], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[WARN] 前回反映したコミット {base[:7]} が履歴に見つかりません", file=sys.stderr)
        return None
    return [line for line in r.stdout.splitlines() if line]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="", help="前回 Render に反映したコミット（分からなければ空）")
    ap.add_argument("--force", action="store_true", help="授業時間中でもすぐ反映する")
    args = ap.parse_args(argv)

    now = datetime.datetime.now(JST)
    deploy, reason = decide(changed_since(args.base), now, args.force)
    print(f"[INFO] {now:%Y-%m-%d %H:%M} JST / 前回の反映 {args.base[:7] or '不明'} → "
          f"{'反映する' if deploy else '反映しない'}（{reason}）")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"deploy={'true' if deploy else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
