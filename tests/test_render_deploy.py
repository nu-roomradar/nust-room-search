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
        self.assertIn("20:40", reason)
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
        cron = on["schedule"][0]["cron"]
        minute, hour = map(int, cron.split()[:2])
        jst = datetime.time((hour + 9) % 24, minute)
        self.assertGreaterEqual(jst, rd.CLASS_END)     # 夜の定期実行は授業が終わってから
        self.assertIn("force", on["workflow_dispatch"]["inputs"])

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
