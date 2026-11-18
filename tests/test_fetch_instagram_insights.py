"""
scripts/fetch_instagram_insights.py（Instagram 週次の記録）のテスト。Instagram には実際にはつながず、応答を作って渡す。
実行: python -m unittest tests.test_fetch_instagram_insights -v
"""
import datetime
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_instagram_insights as fi  # noqa: E402

JST = fi.JST
NOW = datetime.datetime(2026, 11, 18, 9, 0, tzinfo=JST)


class Resp:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status
        self.ok = status < 400

    def json(self):
        return self.body

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(self.status_code)


def err(msg="unsupported metric", code=100):
    return Resp({"error": {"message": msg, "type": "OAuthException", "code": code}}, 400)


class FakeGraph:
    """パスと metric で応答を決める。呼ばれた (path, params) を記録する"""

    def __init__(self, media_pages, insights=None, reject=(), account_metrics=None, deny_all=False):
        self.media_pages = media_pages       # [[media, ...], [media, ...]]
        self.insights = insights or {}       # media_id -> {metric: value}
        self.reject = set(reject)            # この metric を含む依頼は断る
        self.account_metrics = account_metrics or {}
        self.deny_all = deny_all             # 数字を読む権限が無い
        self.calls = []

    def get(self, url, params=None, timeout=None):
        path = urlparse(url).path.split("/", 2)[2]    # "/v21.0/<path>"
        p = dict(params or {})
        self.calls.append((path, p))
        if path == "acc":
            return Resp({"id": "acc", "username": "roomradar_nust", "followers_count": 120,
                         "follows_count": 3, "media_count": 40})
        if path == "acc/media":
            i = 0 if "after" not in p else int(p["after"])
            body = {"data": self.media_pages[i]}
            if i + 1 < len(self.media_pages):
                body["paging"] = {"cursors": {"after": str(i + 1)}, "next": "https://graph.instagram.com/next"}
            return Resp(body)
        if path == "acc/insights":
            m = p["metric"]
            if self.deny_all or m not in self.account_metrics:
                return err()
            return Resp({"data": [{"name": m, "total_value": {"value": self.account_metrics[m]}}]})
        if path.endswith("/insights"):
            mid = path.split("/")[0]
            ms = p["metric"].split(",")
            if self.deny_all:
                return err("(#10) Application does not have permission for this action", 10)
            if self.reject & set(ms):
                return err()
            have = self.insights.get(mid, {})
            return Resp({"data": [{"name": m, "values": [{"value": have[m]}]} for m in ms if m in have]})
        return err("unknown", 1)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def media(mid, ts, mtype="IMAGE", product="FEED", caption="見出し\n本文 #RoomRadar #日大生プロジェクト", children=0):
    m = {"id": mid, "timestamp": ts, "media_type": mtype, "media_product_type": product,
         "permalink": f"https://www.instagram.com/p/{mid}/", "caption": caption,
         "like_count": 5, "comments_count": 1, "media_url": f"https://cdn/{mid}.jpg"}
    if children:
        m["children"] = {"data": [{"id": f"{mid}-{i}"} for i in range(children)]}
    return m


class FetchTest(unittest.TestCase):
    def api(self, fake):
        return fi.Api("https://graph.instagram.com", "TOKEN", session=fake)

    def test_get_all_media_follows_paging(self):
        fake = FakeGraph([[media("a", "2026-11-17T11:59:23+0000")], [media("b", "2026-11-10T03:00:00+0000")]])
        got = fi.get_all_media(self.api(fake), "acc")
        self.assertEqual([m["id"] for m in got], ["a", "b"])
        self.assertEqual(fake.calls[1][1]["after"], "1")

    def test_batch_insights(self):
        fake = FakeGraph([[]], insights={"a": {"views": 300, "reach": 120, "saved": 4}})
        notes, unsupported = set(), {}
        got = fi.get_media_insights(self.api(fake), media("a", "2026-11-17T11:59:23+0000"), notes, unsupported)
        self.assertEqual(got, {"views": 300, "reach": 120, "saved": 4})
        self.assertEqual(len([c for c in fake.calls if c[0] == "a/insights"]), 1)   # まとめて1回
        self.assertEqual(notes, set())

    def test_falls_back_to_one_metric_at_a_time_and_remembers(self):
        fake = FakeGraph([[]], insights={"a": {"views": 300, "reach": 120}, "b": {"views": 50, "reach": 40}},
                         reject={"profile_activity"})
        notes, unsupported = set(), {}
        api = self.api(fake)
        got = fi.get_media_insights(api, media("a", "2026-11-17T11:59:23+0000"), notes, unsupported)
        self.assertEqual(got, {"views": 300, "reach": 120})
        self.assertIn("profile_activity", unsupported["IMAGE"])
        fake.calls.clear()
        got = fi.get_media_insights(api, media("b", "2026-11-10T03:00:00+0000"), notes, unsupported)
        self.assertEqual(got, {"views": 50, "reach": 40})
        self.assertNotIn("profile_activity", fake.calls[0][1]["metric"])     # 2件目からは頼まない
        self.assertEqual(len(fake.calls), 1)

    def test_reels_ask_for_reels_metrics(self):
        fake = FakeGraph([[]], insights={"r": {"views": 900, "ig_reels_avg_watch_time": 4100}})
        got = fi.get_media_insights(self.api(fake), media("r", "2026-10-30T10:00:00+0000", "VIDEO", "REELS"), set(), {})
        self.assertEqual(got["ig_reels_avg_watch_time"], 4100)
        self.assertIn("ig_reels_avg_watch_time", fake.calls[0][1]["metric"])
        self.assertNotIn("profile_visits", fake.calls[0][1]["metric"])

    def test_no_permission_leaves_a_note(self):
        fake = FakeGraph([[]], deny_all=True)
        notes = set()
        got = fi.get_media_insights(self.api(fake), media("a", "2026-11-17T11:59:23+0000"), notes, {})
        self.assertEqual(got, {})
        self.assertTrue(any("instagram_business_manage_insights" in n for n in notes))

    def test_account_insights_skip_unreadable(self):
        fake = FakeGraph([[]], account_metrics={"reach": 800, "views": 2400})
        notes = set()
        got = fi.get_account_insights(self.api(fake), "acc", NOW.date(), notes)
        self.assertEqual((got["reach_7d"], got["views_7d"]), (800, 2400))
        self.assertNotIn("reach", got)      # 8 月までの「その日の値」と混ぜない
        self.assertEqual(got["period"], "2026-11-11〜2026-11-17")
        self.assertTrue(any("accounts_engaged" in n for n in notes))
        p = [c for c in fake.calls if c[1].get("metric") == "reach"][0][1]
        self.assertEqual(p["metric_type"], "total_value")
        self.assertEqual(p["until"] - p["since"], 7 * 86400)


class BuildTest(unittest.TestCase):
    def test_build_post_derived_fields(self):
        m = media("c", "2026-11-17T11:59:23+0000", "CAROUSEL_ALBUM", "FEED",
                  caption="🆕 RoomRadar v2.8 にアップデートしました！\n\n本文 #RoomRadar #空き教室", children=3)
        p = fi.build_post(m, {"views": 200, "reach": 100, "total_interactions": 12, "saved": 3, "shares": 2}, NOW)
        self.assertEqual(p["posted_jst"], "2026-11-17 20:59")
        self.assertEqual((p["weekday"], p["hour"]), ("火", 20))
        self.assertEqual(p["kind"], "カルーセル")
        self.assertEqual(p["slides"], 3)
        self.assertEqual(p["headline"], "🆕 RoomRadar v2.8 にアップデートしました！")
        self.assertEqual(p["hashtags"], ["#RoomRadar", "#空き教室"])
        self.assertEqual(p["engagement_rate"], 0.12)
        self.assertEqual(p["save_share_rate"], 0.05)
        self.assertEqual(p["age_days"], 0.5)
        # dashboard.html が読む項目名（8 月まで）を残す
        for k in ("id", "permalink", "media_type", "thumbnail", "caption", "timestamp", "like_count",
                  "comments_count", "saved", "shares", "reach", "views", "total_interactions"):
            self.assertIn(k, p)

    def test_rates_are_none_without_reach(self):
        p = fi.build_post(media("a", "2026-11-17T11:59:23+0000"), {}, NOW)
        self.assertIsNone(p["engagement_rate"])
        self.assertIsNone(p["save_share_rate"])
        self.assertEqual(p["slides"], 1)

    def test_merges_replace_the_same_day(self):
        posts = [fi.build_post(media("a", "2026-11-17T11:59:23+0000"), {"views": 10}, NOW)]
        old = [{"date": "2026-11-18", "id": "a", "views": 1}, {"date": "2026-11-11", "id": "z", "views": 5}]
        got = fi.merge_snapshots(old, posts, "2026-11-18")
        self.assertEqual([(s["date"], s["id"], s.get("views")) for s in got],
                         [("2026-11-11", "z", 5), ("2026-11-18", "a", 10)])
        hist = fi.merge_history([{"date": "2026-11-18", "followers_count": 1}], {"date": "2026-11-18", "followers_count": 2})
        self.assertEqual(hist, [{"date": "2026-11-18", "followers_count": 2}])

    def test_report_escapes_and_lists_notes(self):
        p = fi.build_post(media("a", "2026-11-17T11:59:23+0000", caption="A|B の見出し"), {"views": 10, "reach": 5}, NOW)
        md = fi.render_report([p], {"followers_count": 120, "media_count": 40, "reach_7d": 800, "period": "2026-11-11〜2026-11-17"},
                              {"アカウントの数字のうち読めなかったもの: views"}, "2026-11-18")
        self.assertIn("A／B の見出し", md)
        self.assertIn("> - アカウントの数字のうち読めなかったもの: views", md)
        self.assertIn("## 閲覧の多い順（上位10）", md)
        self.assertIn("フォロワー 120", md)
        self.assertIn("リーチ 800", md)


class MainTest(unittest.TestCase):
    def test_main_writes_four_files_and_skips_stories(self):
        fake = FakeGraph(
            [[media("c", "2026-11-17T11:59:23+0000", "CAROUSEL_ALBUM", children=3),
              media("s", "2026-11-17T13:08:25+0000", "IMAGE", "STORY")],
             [media("r", "2026-10-30T10:00:00+0000", "VIDEO", "REELS")]],
            insights={"c": {"views": 200, "reach": 100, "total_interactions": 9},
                      "r": {"views": 900, "reach": 500, "ig_reels_avg_watch_time": 4100}},
            account_metrics={"reach": 800})
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.multiple(fi, DATA_DIR=d, POSTS_FILE=os.path.join(d, "p.json"),
                                    SNAPSHOT_FILE=os.path.join(d, "s.json"), HISTORY_FILE=os.path.join(d, "h.json"),
                                    REPORT_FILE=os.path.join(d, "r.md")), \
                mock.patch.object(fi, "requests", fake), \
                mock.patch.dict(os.environ, {"IG_ACCESS_TOKEN": "T", "IG_ACCOUNT_ID": "acc", "GITHUB_STEP_SUMMARY": ""}):
            fi.main()
            posts = json.loads(read(os.path.join(d, "p.json")))
            self.assertEqual([p["id"] for p in posts["posts"]], ["c", "r"])        # ストーリーは入れない
            self.assertEqual(len(json.loads(read(os.path.join(d, "s.json")))), 2)
            hist = json.loads(read(os.path.join(d, "h.json")))
            self.assertEqual((hist[-1]["followers_count"], hist[-1]["reach_7d"]), (120, 800))
            self.assertIn("| 火 | カルーセル | 3 |", read(os.path.join(d, "r.md")))
        # トークンは URL の外（params）で渡し、ログに出さない
        self.assertTrue(all("TOKEN" not in c[0] and "T" == c[1]["access_token"] for c in fake.calls))

    def test_main_needs_secrets(self):
        with mock.patch.dict(os.environ, {"IG_ACCESS_TOKEN": "", "IG_ACCOUNT_ID": ""}), \
                self.assertRaises(SystemExit):
            fi.main()


if __name__ == "__main__":
    unittest.main()
