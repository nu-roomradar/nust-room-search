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
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA_DIR = os.path.join(ROOT, "data")
WEEKLY_JSON = os.path.join(DATA_DIR, "ga4_weekly.json")
WEEKLY_MD = os.path.join(DATA_DIR, "ga4_weekly.md")
HISTORY_FILE = os.path.join(DATA_DIR, "ga4_history.json")
BREAKDOWN_FILE = os.path.join(DATA_DIR, "ga4_breakdown.json")

JST = datetime.timezone(datetime.timedelta(hours=9))
HOSTS = {"app": "nust-room-search.onrender.com", "lp": "nu-roomradar.github.io"}
EVENTS = ["search", "report_room", "reserve_room", "feedback_submit"]


# ── 純粋な関数（テスト対象。ネットワークを使わない） ──

def last_full_weeks(today, n=1):
    """today より前の、月曜始まりの完全な週を古い順に n 個返す [(月曜, 日曜), ...]"""
    this_monday = today - datetime.timedelta(days=today.weekday())
    return [(this_monday - datetime.timedelta(weeks=k), this_monday - datetime.timedelta(weeks=k, days=-6))
            for k in range(n, 0, -1)]


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


def to_markdown(weeks):
    lines = ["# GA4 週次の記録（自動更新・毎週月曜）", "",
             "アプリ＝検索アプリ（onrender.com）、LP＝紹介ページ（github.io）。ドメインが別なので合計しない。",
             "利用者数は端末・ブラウザの数で、人数ではない。前週比はアプリの訪問回数。", "",
             "| 週（月〜日） | アプリ 利用者 | アプリ 訪問 | 前週比 | 検索 | 「使われていた」報告 | LP 利用者 | LP 訪問 | 意見箱 |",
             "|---|---|---|---|---|---|---|---|---|"]
    prev = None
    for w in weeks:
        a, l, e = w["app"], w["lp"], w["events"]
        lines.append(f"| {w['week_start']}〜{w['week_end'][5:]} | {a['users']} | {a['sessions']} | "
                     f"{fmt_change(a['sessions'], prev)} | {e.get('search', 0)} | {e.get('report_room', 0)} | "
                     f"{l['users']} | {l['sessions']} | {e.get('feedback_submit', 0)} |")
        prev = a["sessions"]
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
    # 検索条件はカスタムディメンション。GA4 側で登録されていないと取れないので、失敗しても続ける
    for key, dim in [("search_building", "customEvent:search_building"),
                     ("search_period", "customEvent:search_period"),
                     ("search_day", "customEvent:search_day")]:
        try:
            rows = report(client, prop, [dim], ["eventCount"], start, end, limit=20)
            bd[key] = sorted([{"label": d[0], "count": int(m[0])} for d, m in rows
                              if d[0] not in ("(not set)", "")], key=lambda x: -x["count"])
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] {key} を取れません（GA4 でカスタムディメンション未登録の可能性）: {e}", file=sys.stderr)
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
        f.write(to_markdown(weeks))
    for w in new:
        print(f"[INFO] {w['week_start']}〜{w['week_end']}: アプリ 利用者{w['app']['users']}・訪問{w['app']['sessions']} / "
              f"LP 利用者{w['lp']['users']}・訪問{w['lp']['sessions']} / イベント {w['events']}")
    print(f"[INFO] 週次 {len(weeks)} 週・日次 {len(history)} 日を保存しました")


if __name__ == "__main__":
    main()
