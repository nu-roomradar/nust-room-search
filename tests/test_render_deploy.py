"""scripts/render_deploy.py（アプリの反映を授業のない時間にだけ行う判定）と、そのワークフローの検査"""
import datetime
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import render_deploy as rd  # noqa: E402

JST = rd.JST


def at(y, mo, d, h, mi):
    return datetime.datetime(y, mo, d, h, mi, tzinfo=JST)


MON_10 = at(2026, 10, 26, 10, 0)    # 月曜 10:00（授業中）
MON_2040 = at(2026, 10, 26, 20, 40)  # 月曜 20:40（6限のあと）
SUN_12 = at(2026, 11, 1, 12, 0)      # 日曜 12:00


class ClassHoursTests(unittest.TestCase):
    def test_class_hours_are_mon_to_sat_9_to_2030(self):
        self.assertTrue(rd.in_class_hours(MON_10))
        self.assertTrue(rd.in_class_hours(at(2026, 10, 26, 9, 0)))
        self.assertTrue(rd.in_class_hours(at(2026, 10, 26, 20, 29)))
        self.assertFalse(rd.in_class_hours(at(2026, 10, 26, 20, 30)))
        self.assertFalse(rd.in_class_hours(at(2026, 10, 26, 8, 59)))
        self.assertTrue(rd.in_class_hours(at(2026, 10, 31, 13, 0)))    # 土曜も授業がある
        self.assertFalse(rd.in_class_hours(SUN_12))

    def test_class_end_matches_the_last_period_of_the_app(self):
        src = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('1: ("09:00", "10:40")', src)
        self.assertIn('6: ("18:50", "20:30")', src)


class DecideTests(unittest.TestCase):
    def test_app_changes_are_held_until_after_class(self):
        deploy, reason = rd.decide(["static/app.js"], MON_10)
        self.assertFalse(deploy)
        self.assertIn("20:30 以降", reason)
        self.assertTrue(rd.decide(["static/app.js"], MON_2040)[0])
        self.assertTrue(rd.decide(["templates/index.html"], SUN_12)[0])

    def test_changes_that_do_not_touch_the_app_never_redeploy(self):
        for files in (["data/ga4_weekly.md", "data/ga4_weekly.json"], ["index.html", "dashboard.html"],
                      ["docs/OPERATIONS.md", "CLAUDE.md"], ["scripts/fetch_ga4_metrics.py"], []):
            self.assertFalse(rd.decide(files, MON_2040)[0], files)

    def test_files_render_runs(self):
        self.assertEqual(rd.app_changes(["app.py", "school_bookings.py", "requirements.txt", "schedule_final.db",
                                         "templates/room.html", "static/app.css", "requirements-dev.txt",
                                         "tests/test_app.py", "data/classes_2026.csv"]),
                         ["app.py", "school_bookings.py", "requirements.txt", "schedule_final.db",
                          "templates/room.html", "static/app.css"])

    def test_unknown_last_deploy_deploys_only_outside_class(self):
        self.assertTrue(rd.decide(None, MON_2040)[0])
        self.assertFalse(rd.decide(None, MON_10)[0])

    def test_force_deploys_even_in_class_and_without_changes(self):
        self.assertTrue(rd.decide(["static/app.js"], MON_10, force=True)[0])
        self.assertTrue(rd.decide([], MON_10, force=True)[0])


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / ".github/workflows/render-deploy.yml").read_text(encoding="utf-8")
        self.doc = yaml.safe_load(self.text)

    def test_runs_on_push_nightly_and_by_hand(self):
        on = self.doc[True]                  # YAML の on は True として読まれる
        self.assertEqual(on["push"]["branches"], ["main"])
        self.assertIn("force", on["workflow_dispatch"]["inputs"])
        self.assertTrue(on["schedule"])

    def scheduled_times_jst(self):
        """定期実行の予定時刻（日本時間）。毎日・「分 時,時,… * * *」の書き方だけを認める"""
        times = []
        for entry in self.doc[True]["schedule"]:
            minute, hours, dom, month, dow = entry["cron"].split()
            self.assertEqual((dom, month, dow), ("*", "*", "*"), entry["cron"])
            times += [datetime.time((int(h) + 9) % 24, int(minute)) for h in hours.split(",")]
        return sorted(times)

    def test_one_run_is_right_after_class_when_github_is_on_time(self):
        """定刻に届いたとき：授業が終わってすぐ（20:30〜21:00）に1回ある"""
        times = self.scheduled_times_jst()
        self.assertTrue(any(rd.CLASS_END <= t <= datetime.time(21, 0) for t in times), times)

    def test_some_run_lands_at_night_however_late_github_is(self):
        """GitHub の定期実行は遅れて届く（このリポジトリでは 5〜10 時間。20:40 の予定が 2:00〜6:30 に届いていた）。
        遅れが 0〜14 時間のどれでも、どれかの実行が「月曜の夜（20:30〜翌朝 9:00）」に、それも 20:30 から
        2 時間ほどのうちに届くこと。20:40 の1回だけだと、遅れが 12 時間を超えた日は反映されなかった"""
        mon = datetime.date(2026, 10, 26)
        night_start = datetime.datetime.combine(mon, rd.CLASS_END, tzinfo=JST)
        night_end = datetime.datetime.combine(mon + datetime.timedelta(days=1), rd.CLASS_START, tzinfo=JST)
        runs = [datetime.datetime.combine(mon + datetime.timedelta(days=d), t, tzinfo=JST)
                for d in (-1, 0) for t in self.scheduled_times_jst()]     # 前の日の分が遅れて届くこともある
        for late_min in range(0, 14 * 60 + 1, 10):
            late = datetime.timedelta(minutes=late_min)
            landed = [r + late for r in runs if night_start <= r + late < night_end]
            self.assertTrue(landed, f"{late_min} 分遅れのとき、夜のうちに届く実行が無い")
            for when in landed:
                self.assertFalse(rd.in_class_hours(when))
            # いちばん早く届く実行は、授業が終わってから 2 時間以内（その夜のうちに見られる）
            self.assertLess(min(landed) - night_start, datetime.timedelta(hours=2), late_min)

    def test_runs_scheduled_in_class_hours_are_refused_when_on_time(self):
        """早めに置いた分は、定刻に届いたら授業中。判定が見送ること（＝報告を消さない）"""
        early = [t for t in self.scheduled_times_jst() if rd.CLASS_START <= t < rd.CLASS_END]
        self.assertTrue(early)
        for t in early:
            when = datetime.datetime.combine(datetime.date(2026, 10, 26), t, tzinfo=JST)
            self.assertFalse(rd.decide(["static/app.js"], when)[0], t)

    def test_no_run_at_the_top_of_the_hour(self):
        """毎時0分は GitHub が混んでいて、遅れたり落とされたりしやすい"""
        self.assertTrue(all(t.minute not in (0, 30) for t in self.scheduled_times_jst()))

    def test_deploy_hook_call_retries_on_timeouts(self):
        steps = self.doc["jobs"]["deploy"]["steps"]
        hook = next(s for s in steps if "RENDER_DEPLOY_HOOK" in str(s.get("env", {})))
        self.assertIn("--retry 2", hook["run"])
        self.assertIn("--max-time", hook["run"])
        self.assertNotIn("--retry-all-errors", hook["run"])   # 401・404（Hook が無効）は、やり直しても直らない

    def test_deploy_hook_stays_in_env(self):
        """Deploy Hook の URL は知られると誰でも再デプロイ（＝報告を消す）できるので、run に埋め込まない"""
        steps = self.doc["jobs"]["deploy"]["steps"]
        for s in steps:
            self.assertNotIn("${{", str(s.get("run", "")))
        hook = next(s for s in steps if "RENDER_DEPLOY_HOOK" in str(s.get("env", {})))
        self.assertEqual(hook["env"]["RENDER_DEPLOY_HOOK"], "${{ secrets.RENDER_DEPLOY_HOOK }}")
        self.assertIn("-o /dev/null", hook["run"])

    def test_least_privilege(self):
        self.assertEqual(self.doc["permissions"], {"contents": "read", "deployments": "write"})


if __name__ == "__main__":
    unittest.main()
