"""
GA4 Data API から利用状況を取り、週ごとの記録を残す（毎週月曜の朝に GitHub Actions で実行）。

書き出すもの:
  data/ga4_weekly.json  … 週ごとの記録（月〜日）。実行のたびに直前の1週を追記・上書きする
  data/ga4_weekly.md    … 同じ内容の表（GitHub 上でそのまま読める）
  data/ga4_history.json … 直近28日の日次推移（dashboard.html が読む）
  data/ga4_breakdown.json … 直近28日のイベント数・検索条件・流入元（dashboard.html が読む）

LP（nu-roomradar.github.io）とアプリ（nust-room-search.onrender.com）はドメインが別で、
同じ人でも別々に数えられる。合計は意味がないので、ホスト名で分けて記録する。

必要な環境変数（GitHub の Secrets）:
  GA4_PROPERTY_ID : GA4 のプロパティID（数字だけ）
  GA4_SA_KEY      : サービスアカウントの JSON 鍵（中身そのもの）。GA4 側で「閲覧者」に追加しておく
設定手順は docs/OPERATIONS.md の 4.6。
以前（〜2026-08）の取得が毎回失敗していたのは、この2つの Secrets が未設定だったため。

  python scripts/fetch_ga4_metrics.py            # 直前の1週（月〜日）
  python scripts/fetch_ga4_metrics.py --weeks 4  # 直前の4週を取り直す（初回に使う）
"""
import argparse
import datetime
import json
import os
import sqlite3
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA_DIR = os.path.join(ROOT, "data")
WEEKLY_JSON = os.path.join(DATA_DIR, "ga4_weekly.json")
WEEKLY_MD = os.path.join(DATA_DIR, "ga4_weekly.md")
HISTORY_FILE = os.path.join(DATA_DIR, "ga4_history.json")
BREAKDOWN_FILE = os.path.join(DATA_DIR, "ga4_breakdown.json")
SCHEDULE_DB = os.path.join(ROOT, "schedule_final.db")
REPORT_ROOMS_TOP = 10

JST = datetime.timezone(datetime.timedelta(hours=9))
HOSTS = {"app": "nust-room-search.onrender.com", "lp": "nu-roomradar.github.io"}
# 使った目的のワンタップ調査（2026-10-25〜）。目的ごとにイベント名を分けて送るので、GA4 側の設定なしで数えられる
PURPOSES = [("study", "個人学習"), ("group", "グループワーク"),
            ("meeting", "学生同士の打合せ"), ("break", "授業の合間の休憩"), ("other", "その他")]
PURPOSE_EVENTS = [f"purpose_{code}" for code, _ in PURPOSES]
EVENTS = (["search", "report_room", "report_cancel", "reserve_room", "feedback_submit"]
          + PURPOSE_EVENTS + ["purpose_skip"])
# 「実は使われていた」報告は、報告（report_room）から取り消し（report_cancel）を引いて数える。
# 取り消しと、報告の曜日・時限（search_day・search_period）は 2026-10-26 から送っている
REPORT_SIGN = {"report_room": 1, "report_cancel": -1}
# 検索条件として記録してよい値。GA4 には測定IDさえ分かれば外部の誰でも記録を送れるので、
# アプリが送る値（static/app.js）以外は取り込まない（ダッシュボードへの蓄積型XSSを防ぐ）
ORDERED = {"search_period": ["1", "2", "3", "4", "5", "6"], "search_day": ["月", "火", "水", "木", "金", "土"]}
ALLOWED_SEARCH_VALUES = {
    "search_building": {"all", "tower", "main", "funabashi"},
    "search_period": set(ORDERED["search_period"]),
    "search_day": set(ORDERED["search_day"]),
}


# ── 純粋な関数（テスト対象。ネットワークを使わない） ──

def last_full_weeks(today, n=1):
    """today より前の、月曜始まりの完全な週を古い順に n 個返す [(月曜, 日曜), ...]"""
    this_monday = today - datetime.timedelta(days=today.weekday())
    return [(this_monday - datetime.timedelta(weeks=k), this_monday - datetime.timedelta(weeks=k, days=-6))
            for k in range(n, 0, -1)]


def keep_known(key, items):
    """検索条件の内訳から、アプリが送らない値（偽の記録など）を落とす。落とした件数も返す"""
    allowed = ALLOWED_SEARCH_VALUES[key]
    kept = [i for i in items if i["label"] in allowed]
    return kept, len(items) - len(kept)


def net_reports(events):
    """週・期間のイベント数から、取り消しを引いた「実は使われていた」報告の数"""
    return max(0, events.get("report_room", 0) - events.get("report_cancel", 0))


def top_report_rooms(rows, known, top=REPORT_ROOMS_TOP):
    """「実は使われていた」報告を教室ごとに数える（取り消しは引く）。rows = [([イベント名, 教室, 校舎], [件数]), ...]

    GA4 の room・building は 2026-06-18 にカスタムディメンション登録済み（「予約/報告-教室」）。
    仮予約（reserve_room。2026-10 廃止）などほかのイベントの行も来るので報告と取り消しだけを数え、
    教室マスタに無い名前（偽の記録）は落とす。期間より前の報告の取り消しで負にならないよう、0件以下は出さない
    """
    counts, bldg = {}, {}
    for (event, room, building), (n,) in rows:
        if event not in REPORT_SIGN or room not in known:
            continue
        counts[room] = counts.get(room, 0) + REPORT_SIGN[event] * int(n)
        bldg.setdefault(room, building)
    ranked = sorted(((r, n) for r, n in counts.items() if n > 0), key=lambda kv: (-kv[1], kv[0]))[:top]
    return [{"label": r, "building": bldg[r], "count": n} for r, n in ranked]


def report_slots(rows):
    """「実は使われていた」報告を曜日×時限ごとに数える（取り消しは引く）。rows = [([イベント名, 曜日, 時限], [件数]), ...]

    返り値は {曜日: [1限の件数, …, 6限の件数]}。曜日・時限の無い行（2026-10-25 までの報告は (not set)）や、
    アプリが送らない値（偽の記録）は数えない"""
    days, periods = ORDERED["search_day"], ORDERED["search_period"]
    grid = {d: [0] * len(periods) for d in days}
    for (event, day, period), (n,) in rows:
        if event not in REPORT_SIGN or day not in grid or period not in periods:
            continue
        grid[day][periods.index(period)] += REPORT_SIGN[event] * int(n)
    return {d: [max(0, n) for n in v] for d, v in grid.items()}


def search_breakdown(key, rows):
    """検索条件の内訳。rows = [([イベント名, 値], [件数]), ...]。同じ名前の値を送るほかのイベント
    （使った目的の調査・報告）が混ざらないよう、検索（search）の行だけを数える"""
    counts = {}
    for (event, value), (n,) in rows:
        if event == "search":
            counts[value] = counts.get(value, 0) + int(n)
    return keep_known(key, [{"label": v, "count": n} for v, n in counts.items()])


def known_rooms(db=SCHEDULE_DB):
    """全年度の教室マスタの教室名。時間割 DB が無ければ空（＝何も取り込まない）"""
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            return {r[0] for r in con.execute("SELECT DISTINCT name FROM classrooms")}
        finally:
            con.close()
    except sqlite3.Error:
        return set()


def merge_weeks(old, new):
    """週の記録を week_start で上書きマージし、古い順に並べる"""
    by = {w["week_start"]: w for w in old}
    for w in new:
        by[w["week_start"]] = w
    return [by[k] for k in sorted(by)]


def fmt_change(cur, prev):
    if not prev:
        return "—"
    return f"{(cur - prev) / prev * 100:+.0f}%"


def to_markdown(weeks, report_rooms=None, slots=None):
    lines = ["# GA4 週次の記録（自動更新・毎週月曜）", "",
             "アプリ＝検索アプリ（onrender.com）、LP＝紹介ページ（github.io）。ドメインが別なので合計しない。",
             "利用者数は端末・ブラウザの数で、人数ではない。前週比はアプリの訪問回数。",
             "「使われていた」報告は、取り消された分を引いた数（取り消しは 2026-10-26 から数えている）。", "",
             "| 週（月〜日） | アプリ 利用者 | アプリ 訪問 | 前週比 | 検索 | 「使われていた」報告 | LP 利用者 | LP 訪問 | 意見箱 |",
             "|---|---|---|---|---|---|---|---|---|"]
    prev = None
    for w in weeks:
        a, l, e = w["app"], w["lp"], w["events"]
        lines.append(f"| {w['week_start']}〜{w['week_end'][5:]} | {a['users']} | {a['sessions']} | "
                     f"{fmt_change(a['sessions'], prev)} | {e.get('search', 0)} | {net_reports(e)} | "
                     f"{l['users']} | {l['sessions']} | {e.get('feedback_submit', 0)} |")
        prev = a["sessions"]
    asked = [w for w in weeks if any(w["events"].get(k, 0) for k in PURPOSE_EVENTS + ["purpose_skip"])]
    if asked:
        lines += ["", "## 空きコマに何に使う？（使った目的のワンタップ調査・回答数）", "",
                  "任意・匿名。今日のいまの時限か次の時限を検索したときだけ、1台1日1回まで聞く。「閉じた」は答えずに閉じた数。", "",
                  "| 週（月〜日） | " + " | ".join(label for _, label in PURPOSES) + " | 回答計 | 閉じた |",
                  "|---|" + "---|" * (len(PURPOSES) + 2)]
        for w in asked:
            e = w["events"]
            counts = [e.get(k, 0) for k in PURPOSE_EVENTS]
            lines.append(f"| {w['week_start']}〜{w['week_end'][5:]} | " + " | ".join(str(c) for c in counts)
                         + f" | {sum(counts)} | {e.get('purpose_skip', 0)} |")
    if report_rooms:
        lines += ["", "## 「実は使われていた」報告の多い教室（直近28日）", "",
                  "報告は時限が終わるとアプリからは消えるので、残るのはこの件数だけ。", "",
                  "| 教室 | 校舎 | 報告 |", "|---|---|---|"]
        lines += [f"| {r['label']} | {r['building']} | {r['count']} |" for r in report_rooms]
    if slots and any(any(v) for v in slots.values()):
        days, periods = ORDERED["search_day"], ORDERED["search_period"]
        lines += ["", "## 「実は使われていた」報告の曜日・時限（直近28日）", "",
                  "時間割にない使われ方が多い時間帯の目安。曜日・時限は 2026-10-26 からの報告だけ。", "",
                  "| 時限 | " + " | ".join(days) + " |", "|---|" + "---|" * len(days)]
        lines += [f"| {p}限 | " + " | ".join(str(slots[d][i]) if slots[d][i] else "·" for d in days) + " |"
                  for i, p in enumerate(periods)]
    return "\n".join(lines) + "\n"


# ── GA4 への問い合わせ ──

def get_client():
    raw, prop = os.environ.get("GA4_SA_KEY"), os.environ.get("GA4_PROPERTY_ID")
    missing = [k for k, v in (("GA4_PROPERTY_ID", prop), ("GA4_SA_KEY", raw)) if not v]
    if missing:
        sys.exit(f"[ERROR] Secrets {' と '.join(missing)} が設定されていません（docs/OPERATIONS.md 4.6）")
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.oauth2 import service_account
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit("[ERROR] GA4_SA_KEY が JSON として読めません。鍵ファイルの中身を丸ごと貼ってください")
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/analytics.readonly"])
    return BetaAnalyticsDataClient(credentials=creds), prop.strip()


def report(client, prop, dims, mets, start, end, limit=None):
    from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
    req = RunReportRequest(property=f"properties/{prop}",
                           dimensions=[Dimension(name=d) for d in dims],
                           metrics=[Metric(name=m) for m in mets],
                           date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
                           limit=limit)
    resp = client.run_report(req)
    return [([d.value for d in r.dimension_values], [m.value for m in r.metric_values]) for r in resp.rows]


def fetch_week(client, prop, start, end):
    w = {"week_start": str(start), "week_end": str(end)}
    zero = {"users": 0, "sessions": 0, "page_views": 0}
    hosts = {d[0]: m for d, m in report(client, prop, ["hostName"],
                                         ["activeUsers", "sessions", "screenPageViews"], start, end)}
    for key, host in HOSTS.items():
        m = hosts.get(host)
        w[key] = {"users": int(m[0]), "sessions": int(m[1]), "page_views": int(m[2])} if m else dict(zero)
    ev = {d[0]: int(m[0]) for d, m in report(client, prop, ["eventName"], ["eventCount"], start, end)}
    w["events"] = {k: ev.get(k, 0) for k in EVENTS}
    return w


def fetch_dashboard(client, prop, today):
    start, end = today - datetime.timedelta(days=28), today - datetime.timedelta(days=1)
    history = []
    for d, m in report(client, prop, ["date"], ["activeUsers", "newUsers", "screenPageViews", "sessions"], start, end):
        history.append({"date": f"{d[0][:4]}-{d[0][4:6]}-{d[0][6:]}", "active_users": int(m[0]),
                        "new_users": int(m[1]), "page_views": int(m[2]), "sessions": int(m[3])})
    history.sort(key=lambda h: h["date"])
    bd = {"updated": str(today)}
    ev = {d[0]: int(m[0]) for d, m in report(client, prop, ["eventName"], ["eventCount"], start, end)}
    bd["events"] = {k: ev[k] for k in EVENTS if k in ev}
    bd["purposes"] = [{"label": code, "count": ev.get(f"purpose_{code}", 0)} for code, _ in PURPOSES]
    bd["purpose_skip"] = ev.get("purpose_skip", 0)
    # 検索条件はカスタムディメンション。GA4 側で登録されていないと取れないので、失敗しても続ける
    for key, dim in [("search_building", "customEvent:search_building"),
                     ("search_period", "customEvent:search_period"),
                     ("search_day", "customEvent:search_day")]:
        try:
            rows = report(client, prop, ["eventName", dim], ["eventCount"], start, end, limit=500)
            items, dropped = search_breakdown(key, rows)
            if dropped:
                print(f"[WARN] {key}: 想定外の値 {dropped} 件を取り込みませんでした（偽の記録の可能性）", file=sys.stderr)
            bd[key] = sorted(items, key=lambda x: -x["count"])
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] {key} を取れません（GA4 でカスタムディメンション未登録の可能性）: {e}", file=sys.stderr)
    try:
        rows = report(client, prop, ["eventName", "customEvent:room", "customEvent:building"], ["eventCount"],
                      start, end, limit=500)
        bd["report_rooms"] = top_report_rooms(rows, known_rooms())
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] 報告の教室別の件数を取れません: {e}", file=sys.stderr)
    try:
        rows = report(client, prop, ["eventName", "customEvent:search_day", "customEvent:search_period"],
                      ["eventCount"], start, end, limit=2000)
        bd["report_slots"] = report_slots(rows)
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] 報告の曜日・時限別の件数を取れません: {e}", file=sys.stderr)
    rows = report(client, prop, ["sessionDefaultChannelGroup"], ["sessions"], start, end, limit=10)
    bd["channels"] = sorted([{"label": d[0], "sessions": int(m[0])} for d, m in rows], key=lambda x: -x["sessions"])
    return history, bd


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--weeks", type=int, default=1, help="直前の何週ぶんを取り直すか（既定 1）")
    args = ap.parse_args(argv)

    client, prop = get_client()
    today = datetime.datetime.now(JST).date()
    new = [fetch_week(client, prop, s, e) for s, e in last_full_weeks(today, args.weeks)]
    try:
        old = json.load(open(WEEKLY_JSON, encoding="utf-8"))
    except FileNotFoundError:
        old = []
    weeks = merge_weeks(old, new)
    history, breakdown = fetch_dashboard(client, prop, today)

    os.makedirs(DATA_DIR, exist_ok=True)
    for path, obj in ((WEEKLY_JSON, weeks), (HISTORY_FILE, history), (BREAKDOWN_FILE, breakdown)):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
            f.write("\n")
    with open(WEEKLY_MD, "w", encoding="utf-8") as f:
        f.write(to_markdown(weeks, breakdown.get("report_rooms"), breakdown.get("report_slots")))
    for w in new:
        print(f"[INFO] {w['week_start']}〜{w['week_end']}: アプリ 利用者{w['app']['users']}・訪問{w['app']['sessions']} / "
              f"LP 利用者{w['lp']['users']}・訪問{w['lp']['sessions']} / イベント {w['events']}")
    print(f"[INFO] 週次 {len(weeks)} 週・日次 {len(history)} 日を保存しました")


if __name__ == "__main__":
    main()
