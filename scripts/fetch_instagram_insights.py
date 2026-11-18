"""
Instagram の投稿ごとの数字（閲覧・リーチ・いいね・保存・シェアなど）とアカウントの数字を集め、
data/ に記録する。投稿の傾向を分析して次の投稿に生かす「改善のサイクル」の材料（2026-11-18 再開）。
分析の手順は .claude/skills/instagram-review/SKILL.md、決まりは docs/OPERATIONS.md 4.12。

書き出すもの（どれも公開リポジトリに入るので、公開済みの投稿の数字と本文だけを入れる。個人の情報は入れない）:
  data/instagram_posts.json           いまの全投稿の数字と、分析用の項目（日本時間の曜日・時刻、枚数、見出し、反応率など）。
                                      dashboard.html もこれを読む（項目は 8 月までと同じ名前を残している）
  data/instagram_post_snapshots.json  取りに行くたびの投稿ごとの数字（投稿からの日数つき）。伸び方を見るため
  data/instagram_history.json         アカウントの数字（フォロワーなど）を取った日ごとに1行。直前7日の合計は *_7d
  data/instagram_posts.md             人と AI が読む表（新しい順・閲覧の多い順・まとめ）

必要な環境変数: IG_ACCESS_TOKEN（長期トークン）/ IG_ACCOUNT_ID
数字を読むにはトークンに instagram_business_manage_insights の権限が要る。無い・失効しているときは
投稿の一覧（いいね・コメント数）だけを書き、足りない理由を表の頭に書く（止まらない）。
ストーリーは対象外（運営の判断 2026-11-18。ストーリーの数字は出ている24時間しか取れない）。
"""
import datetime
import json
import os
import re
import sys

import requests

API_VERSION = "v21.0"
HOSTS = ["https://graph.instagram.com", "https://graph.facebook.com"]
TIMEOUT = 30
JST = datetime.timezone(datetime.timedelta(hours=9))
WEEKDAYS = "月火水木金土日"

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA_DIR = os.path.join(ROOT, "data")
POSTS_FILE = os.path.join(DATA_DIR, "instagram_posts.json")
SNAPSHOT_FILE = os.path.join(DATA_DIR, "instagram_post_snapshots.json")
HISTORY_FILE = os.path.join(DATA_DIR, "instagram_history.json")
REPORT_FILE = os.path.join(DATA_DIR, "instagram_posts.md")

ACCOUNT_FIELDS = "username,followers_count,follows_count,media_count"
MEDIA_FIELDS = ("id,caption,media_type,media_product_type,permalink,timestamp,"
                "like_count,comments_count,thumbnail_url,media_url,children{id}")
# 投稿の種類ごとに頼む数字。1回でまとめて頼み、断られたら1つずつ頼み直す（種類によって無い数字があるため）
FEED_METRICS = ["views", "reach", "likes", "comments", "saved", "shares", "total_interactions",
                "follows", "profile_visits", "profile_activity"]
REELS_METRICS = ["views", "reach", "likes", "comments", "saved", "shares", "total_interactions",
                 "ig_reels_avg_watch_time", "ig_reels_video_view_total_time"]
# アカウント全体（直前の7日間の合計）
ACCOUNT_METRICS = ["reach", "views", "accounts_engaged", "total_interactions", "profile_views",
                   "likes", "comments", "saves", "shares", "follows_and_unfollows"]
# 投稿・スナップショットに残す数字（無ければ None）
NUM_KEYS = ["views", "reach", "likes", "comments", "saved", "shares", "total_interactions",
            "follows", "profile_visits", "profile_activity", "ig_reels_avg_watch_time",
            "ig_reels_video_view_total_time"]


class Api:
    def __init__(self, host, token, session=None):
        self.host, self.token = host, token
        self.http = session or requests

    def get(self, path, params=None):
        p = dict(params or {}, access_token=self.token)
        return self.http.get(f"{self.host}/{API_VERSION}/{path}", params=p, timeout=TIMEOUT)


def error_message(resp):
    try:
        e = resp.json().get("error", {})
        return f"{resp.status_code} {e.get('type', '')} code={e.get('code', '')} {e.get('message', '')}".strip()
    except Exception:
        return str(resp.status_code)


def pick_host(account_id, token, session=None):
    """使えるホストを返す（Instagram ログイン方式なら graph.instagram.com）"""
    for host in HOSTS:
        resp = Api(host, token, session).get(account_id, {"fields": "id"})
        if resp.ok:
            print(f"[INFO] 使用エンドポイント: {host}")
            return host
        print(f"[WARN] {host} -> {error_message(resp)}", file=sys.stderr)
    return None


def get_all_media(api, account_id, limit=50, max_pages=20):
    """全投稿（新しい順）。paging.next をたどる"""
    out, params, path = [], {"fields": MEDIA_FIELDS, "limit": limit}, f"{account_id}/media"
    for _ in range(max_pages):
        resp = api.get(path, params)
        resp.raise_for_status()
        body = resp.json()
        out.extend(body.get("data", []))
        nxt = (body.get("paging") or {}).get("next")
        after = ((body.get("paging") or {}).get("cursors") or {}).get("after")
        if not nxt or not after:
            break
        params = {"fields": MEDIA_FIELDS, "limit": limit, "after": after}
    return out


def _parse_insights(body):
    out = {}
    for item in body.get("data", []):
        try:
            if "total_value" in item:
                out[item["name"]] = item["total_value"].get("value")
            else:
                out[item["name"]] = item["values"][0]["value"]
        except (KeyError, IndexError, TypeError):
            pass
    return out


def get_media_insights(api, media, notes, unsupported):
    """投稿1件の数字。まとめて断られたら1つずつ。どの種類で何が無いかは unsupported に覚えて次から頼まない"""
    kind = media_kind(media)
    metrics = [m for m in (REELS_METRICS if kind == "REELS" else FEED_METRICS)
               if m not in unsupported.setdefault(kind, set())]
    if not metrics:
        return {}
    resp = api.get(f"{media['id']}/insights", {"metric": ",".join(metrics)})
    if resp.ok:
        return _parse_insights(resp.json())
    first_error = error_message(resp)
    out = {}
    for m in metrics:
        r = api.get(f"{media['id']}/insights", {"metric": m})
        if r.ok:
            out.update(_parse_insights(r.json()))
        else:
            unsupported[kind].add(m)
    if not out:
        notes.add(f"投稿の数字を読めませんでした（{first_error}）。トークンに instagram_business_manage_insights の権限があるか確かめる")
    return out


def get_account_insights(api, account_id, end_date, notes):
    """アカウント全体の直前7日間（end_date の前日まで、日本時間）の合計。読めない数字は飛ばす"""
    until = datetime.datetime.combine(end_date, datetime.time(), JST)
    since = until - datetime.timedelta(days=7)
    out, failed = {}, []
    for metric in ACCOUNT_METRICS:
        params = {"metric": metric, "period": "day", "metric_type": "total_value",
                  "since": int(since.timestamp()), "until": int(until.timestamp())}
        resp = api.get(f"{account_id}/insights", params)
        if not resp.ok:
            failed.append(metric)
            continue
        value = _parse_insights(resp.json()).get(metric)
        if value is not None:
            out[f"{metric}_7d"] = value     # 8 月までの行（その日の値）と混ざらないよう、名前に _7d を付ける
    if failed:
        notes.add("アカウントの数字のうち読めなかったもの: " + ", ".join(failed))
    out["period"] = f"{since.date().isoformat()}〜{(until - datetime.timedelta(days=1)).date().isoformat()}"
    return out


def media_kind(m):
    if (m.get("media_product_type") or "").upper() == "REELS":
        return "REELS"
    if (m.get("media_product_type") or "").upper() == "STORY":
        return "STORY"
    return (m.get("media_type") or "IMAGE").upper()      # IMAGE / CAROUSEL_ALBUM / VIDEO


KIND_JA = {"IMAGE": "画像", "CAROUSEL_ALBUM": "カルーセル", "VIDEO": "動画", "REELS": "リール", "STORY": "ストーリー"}
HASHTAG = re.compile(r"#[^\s#]+")


def to_jst(ts):
    """'2026-11-17T11:59:23+0000' → 日本時間の datetime"""
    if not ts:
        return None
    try:
        return datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z").astimezone(JST)
    except ValueError:
        return None


def build_post(m, mi, now):
    """1件ぶんの記録。8 月までの項目名（dashboard.html が読む）も残す"""
    at = to_jst(m.get("timestamp"))
    cap = m.get("caption") or ""
    first = next((ln.strip() for ln in cap.splitlines() if ln.strip()), "")
    kind = media_kind(m)
    reach = mi.get("reach")
    inter = mi.get("total_interactions")
    post = {
        "id": m.get("id"),
        "permalink": m.get("permalink"),
        "media_type": m.get("media_type"),
        "media_product_type": m.get("media_product_type"),
        "kind": KIND_JA.get(kind, kind),
        "slides": len(((m.get("children") or {}).get("data")) or []) or (1 if kind != "CAROUSEL_ALBUM" else None),
        "thumbnail": m.get("thumbnail_url") or m.get("media_url"),
        "caption": cap,
        "headline": first[:80],
        "caption_length": len(cap),
        "hashtags": HASHTAG.findall(cap),
        "timestamp": m.get("timestamp"),
        "posted_jst": at.strftime("%Y-%m-%d %H:%M") if at else None,
        "weekday": WEEKDAYS[at.weekday()] if at else None,
        "hour": at.hour if at else None,
        "age_days": round((now - at).total_seconds() / 86400, 1) if at else None,
        "like_count": m.get("like_count"),
        "comments_count": m.get("comments_count"),
    }
    for k in NUM_KEYS:
        post[k] = mi.get(k)
    # 反応率＝反応の数 ÷ リーチ（見た人のうち、いいね・保存・シェア・コメントをした割合のめやす）
    post["engagement_rate"] = round(inter / reach, 4) if isinstance(reach, (int, float)) and reach and isinstance(inter, (int, float)) else None
    # 保存＋シェアの率（あとで役に立つ・人に教えたいと思われたかのめやす）
    keep = (mi.get("saved") or 0) + (mi.get("shares") or 0)
    post["save_share_rate"] = round(keep / reach, 4) if isinstance(reach, (int, float)) and reach else None
    return post


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def merge_snapshots(old, posts, today):
    """同じ日に取り直したら、その日の行を入れ替える"""
    keep = [s for s in old if s.get("date") != today]
    for p in posts:
        row = {"date": today, "id": p["id"], "age_days": p["age_days"]}
        row.update({k: p.get(k) for k in NUM_KEYS if p.get(k) is not None})
        row["like_count"], row["comments_count"] = p.get("like_count"), p.get("comments_count")
        keep.append(row)
    keep.sort(key=lambda s: (s.get("date", ""), s.get("id", "")))
    return keep


def merge_history(old, snapshot):
    keep = [h for h in old if h.get("date") != snapshot["date"]]
    keep.append(snapshot)
    keep.sort(key=lambda h: h.get("date", ""))
    return keep


def _n(v, pct=False):
    if v is None:
        return "–"
    if pct:
        return f"{v * 100:.1f}%"
    return f"{v:,}" if isinstance(v, int) else str(v)


def _cell(s):
    return (s or "").replace("|", "／").replace("\n", " ")


def render_report(posts, snapshot, notes, today):
    feed = [p for p in posts if p["kind"] != "ストーリー"]
    lines = [f"# Instagram の投稿の数字（{today} 取得）", "",
             "自動で書き出す表（scripts/fetch_instagram_insights.py）。手で書き換えない。",
             "読み方と分析の手順は `.claude/skills/instagram-review/SKILL.md`、決まりは `docs/OPERATIONS.md` 4.12。", ""]
    if notes:
        lines += ["> 取れなかったもの:"] + [f"> - {n}" for n in sorted(notes)] + [""]
    acc = [f"フォロワー {_n(snapshot.get('followers_count'))}", f"投稿 {_n(snapshot.get('media_count'))}"]
    for k, ja in (("reach_7d", "リーチ"), ("views_7d", "閲覧"), ("accounts_engaged_7d", "反応した人"), ("profile_views_7d", "プロフィール表示")):
        if snapshot.get(k) is not None:
            acc.append(f"{ja} {_n(snapshot[k])}")
    lines += ["## アカウント", "", f"- {snapshot.get('period', '')}（直前の7日間）: " + "・".join(acc), ""]
    head = "| 投稿日時（日本時間） | 曜 | 種類 | 枚 | 閲覧 | リーチ | いいね | 保存 | シェア | コメント | 反応率 | 保存＋シェア率 | 見出し |"
    sep = "|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|---|"

    def row(p):
        return (f"| [{p['posted_jst'] or '–'}]({p['permalink']}) | {p['weekday'] or '–'} | {p['kind']} | {_n(p['slides'])} | "
                f"{_n(p['views'])} | {_n(p['reach'])} | {_n(p['likes'] if p['likes'] is not None else p['like_count'])} | "
                f"{_n(p['saved'])} | {_n(p['shares'])} | {_n(p['comments'] if p['comments'] is not None else p['comments_count'])} | "
                f"{_n(p['engagement_rate'], True)} | {_n(p['save_share_rate'], True)} | {_cell(p['headline'])} |")

    ranked = sorted([p for p in feed if p.get("views") is not None], key=lambda p: -p["views"])
    if ranked:
        lines += ["## 閲覧の多い順（上位10）", "", head, sep] + [row(p) for p in ranked[:10]] + [""]
    lines += ["## 全投稿（新しい順）", "", head, sep] + [row(p) for p in feed] + [""]
    lines += ["## 数字の意味", "",
              "- 閲覧（views）: 表示された回数。同じ人が何度見ても数える",
              "- リーチ（reach）: 見た人の数（重複なし）",
              "- 反応率: いいね・コメント・保存・シェアなどの合計 ÷ リーチ",
              "- 保存＋シェア率: （保存＋シェア）÷ リーチ。あとで使える・人に教えたいと思われたかのめやす",
              "- 数字は取った日までの累計。投稿からの日数（age_days）が違う投稿を比べるときは data/instagram_post_snapshots.json で同じ日数どうしを比べる", ""]
    return "\n".join(lines)


def main():
    token = os.environ.get("IG_ACCESS_TOKEN")
    account_id = os.environ.get("IG_ACCOUNT_ID")
    if not token or not account_id:
        print("環境変数 IG_ACCESS_TOKEN / IG_ACCOUNT_ID が設定されていません。", file=sys.stderr)
        sys.exit(1)
    host = pick_host(account_id, token)
    if not host:
        print("[ERROR] 使えるエンドポイントがありません（トークンの失効を疑う。docs/OPERATIONS.md 4.5）", file=sys.stderr)
        sys.exit(1)
    api = Api(host, token)
    now = datetime.datetime.now(JST)
    today = now.date().isoformat()
    notes = set()

    acc = api.get(account_id, {"fields": ACCOUNT_FIELDS})
    acc.raise_for_status()
    account = acc.json()
    snapshot = {"date": today, "followers_count": account.get("followers_count"),
                "follows_count": account.get("follows_count"), "media_count": account.get("media_count")}
    snapshot.update(get_account_insights(api, account_id, now.date(), notes))

    unsupported = {}
    posts = []
    for m in get_all_media(api, account_id):
        if media_kind(m) == "STORY":
            continue
        posts.append(build_post(m, get_media_insights(api, m, notes, unsupported), now))
    for kind, ms in unsupported.items():
        if ms:
            print(f"[INFO] {KIND_JA.get(kind, kind)}では読めない数字: {', '.join(sorted(ms))}")

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(POSTS_FILE, "w", encoding="utf-8") as f:
        json.dump({"updated": today, "notes": sorted(notes), "posts": posts}, f, ensure_ascii=False, indent=2)
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(merge_snapshots(load_json(SNAPSHOT_FILE, []), posts, today), f, ensure_ascii=False, indent=1)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(merge_history(load_json(HISTORY_FILE, []), snapshot), f, ensure_ascii=False, indent=2)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(render_report(posts, snapshot, notes, today))

    print(f"[INFO] 投稿 {len(posts)} 件、アカウント: {json.dumps(snapshot, ensure_ascii=False)}")
    for n in sorted(notes):
        print(f"[WARN] {n}")
    # 実行の画面（Actions の Summary）にも表を出す
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(render_report(posts, snapshot, notes, today))


if __name__ == "__main__":
    main()
