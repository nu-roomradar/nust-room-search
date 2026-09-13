"""
scripts/ops_healthcheck.py の単体テスト。外部 API は全てフェイクに差し替える。
実行: python -m unittest discover -s tests -v
"""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ops_healthcheck as hc  # noqa: E402

NOW = datetime(2026, 9, 8, 0, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, status=200, text="", json_data=None, raise_exc=None):
        self.status_code = status
        self.text = text
        self._json = json_data
        self.ok = 200 <= status < 300
        self._raise = raise_exc

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


class FakeGitHub:
    """GitHub クラスと同じ get/post/patch を持つ記録用フェイク"""

    def __init__(self, runs=None, workflows=None, issues=None):
        self.repo = "nu-roomradar/nust-room-search"
        self.runs = runs or []
        self.workflows = workflows or []
        self.issues = issues or []
        self.calls = []

    def get(self, path, **params):
        self.calls.append(("GET", path, params))
        if path.endswith("/actions/runs"):
            return {"workflow_runs": self.runs}
        if path.endswith("/actions/workflows"):
            return {"workflows": self.workflows}
        if path.endswith("/issues"):
            return self.issues
        raise AssertionError(f"unexpected GET {path}")

    def post(self, path, payload):
        self.calls.append(("POST", path, payload))
        return {"number": 99}

    def patch(self, path, payload):
        self.calls.append(("PATCH", path, payload))
        return {}


def run(name, conclusion, created, url="https://github.com/x/y/actions/runs/1", status=None):
    return {"name": name, "conclusion": conclusion, "created_at": created, "html_url": url,
            "status": status or ("completed" if conclusion else "in_progress")}


class UrlCheckTests(unittest.TestCase):
    def test_ok_when_200_and_notice_present(self):
        res = hc.Result()
        with mock.patch("ops_healthcheck.requests.get", return_value=FakeResponse(200, "…テスト運用中の非公式…")):
            hc.check_url(res, "App", "https://example", "テスト運用中", sleep=lambda s: None)
        self.assertEqual(res.problems, [])
        self.assertTrue(any("App" in x for x in res.ok))

    def test_problem_when_notice_missing(self):
        res = hc.Result()
        with mock.patch("ops_healthcheck.requests.get", return_value=FakeResponse(200, "<html>正式版</html>")):
            hc.check_url(res, "App", "https://example", "テスト運用中", sleep=lambda s: None)
        self.assertEqual(len(res.problems), 1)
        self.assertIn("表記が本番ページに見当たりません", res.problems[0][0])

    def test_retries_then_reports_down(self):
        res = hc.Result()
        sleeps = []
        with mock.patch("ops_healthcheck.requests.get", return_value=FakeResponse(503, "")) as g:
            hc.check_url(res, "App", "https://example", "x", attempts=3, wait=7, sleep=sleeps.append)
        self.assertEqual(g.call_count, 3)
        self.assertEqual(sleeps, [7, 7])  # 最後の試行後は待たない
        self.assertIn("応答がありません（HTTP 503）", res.problems[0][0])

    def test_recovers_on_second_attempt(self):
        res = hc.Result()
        seq = [hc.requests.ConnectionError(), FakeResponse(200, "テスト運用中")]
        with mock.patch("ops_healthcheck.requests.get", side_effect=seq):
            hc.check_url(res, "App", "https://example", "テスト運用中", sleep=lambda s: None)
        self.assertEqual(res.problems, [])


class ActionsCheckTests(unittest.TestCase):
    def test_no_failures(self):
        gh = FakeGitHub(runs=[run("CI", "success", "2026-09-07T00:00:00Z")])
        res = hc.Result()
        hc.check_recent_runs(res, gh, now=NOW)
        self.assertEqual(res.problems, [])
        self.assertEqual(gh.calls[0][2]["created"], ">=2026-08-25")

    def test_groups_failures_by_workflow_and_picks_latest(self):
        gh = FakeGitHub(runs=[
            run("Instagramへ投稿", "failure", "2026-09-01T00:00:00Z", "https://gh/old"),
            run("Instagramへ投稿", "failure", "2026-09-06T00:00:00Z", "https://gh/new"),
            run("CI", "success", "2026-09-06T00:00:00Z"),
            run("CI", None, "2026-09-07T00:00:00Z"),  # 実行中は判定に使わない
        ])
        res = hc.Result()
        hc.check_recent_runs(res, gh, now=NOW)
        self.assertEqual(len(res.problems), 1)
        title, detail = res.problems[0]
        self.assertIn("Instagramへ投稿", title)
        self.assertIn("2 回連続", title)
        self.assertIn("https://gh/new", detail)
        self.assertIn("IG_ACCESS_TOKEN", detail)  # Instagram 系にはトークン失効のヒント

    def test_fixed_workflow_stops_being_reported(self):
        """直したら次の実行が通った時点で報告をやめる（直近N日に失敗があっても蒸し返さない）"""
        gh = FakeGitHub(runs=[
            run("CI", "failure", "2026-09-01T00:00:00Z"),
            run("CI", "failure", "2026-09-02T00:00:00Z"),
            run("CI", "success", "2026-09-07T00:00:00Z"),   # 最新が成功 = もう壊れていない
        ])
        res = hc.Result()
        hc.check_recent_runs(res, gh, now=NOW)
        self.assertEqual(res.problems, [])
        self.assertTrue(any("最新の実行が成功" in x for x in res.ok))

    def test_counts_only_the_current_failure_streak(self):
        """「連続何回」は直近の連続分だけ。間に成功があればそこで切れる"""
        gh = FakeGitHub(runs=[
            run("CI", "failure", "2026-09-01T00:00:00Z"),
            run("CI", "success", "2026-09-02T00:00:00Z"),
            run("CI", "failure", "2026-09-05T00:00:00Z"),
            run("CI", "failure", "2026-09-07T00:00:00Z"),
        ])
        res = hc.Result()
        hc.check_recent_runs(res, gh, now=NOW)
        self.assertEqual(len(res.problems), 1)
        self.assertIn("2 回連続", res.problems[0][0])

    def test_in_progress_only_workflow_is_not_judged(self):
        gh = FakeGitHub(runs=[run("CI", None, "2026-09-07T00:00:00Z")])
        res = hc.Result()
        hc.check_recent_runs(res, gh, now=NOW)
        self.assertEqual(res.problems, [])

    def test_timed_out_counts_as_failure(self):
        gh = FakeGitHub(runs=[run("CI", "timed_out", "2026-09-07T00:00:00Z")])
        res = hc.Result()
        hc.check_recent_runs(res, gh, now=NOW)
        self.assertEqual(len(res.problems), 1)

    def test_disabled_inactivity_is_problem_manual_is_note(self):
        gh = FakeGitHub(workflows=[
            {"name": "A", "state": "active"},
            {"name": "B", "state": "disabled_inactivity"},
            {"name": "C", "state": "disabled_manually"},
        ])
        res = hc.Result()
        hc.check_disabled_workflows(res, gh)
        self.assertEqual(len(res.problems), 1)
        self.assertIn("B", res.problems[0][0])
        self.assertTrue(any("C" in n for n in res.notes))


class InstagramTokenTests(unittest.TestCase):
    def test_skip_when_unset(self):
        res = hc.Result()
        hc.check_ig_token(res, "")
        self.assertEqual(res.problems, [])
        self.assertTrue(any("スキップ" in n for n in res.notes))

    def test_valid(self):
        res = hc.Result()
        with mock.patch("ops_healthcheck.requests.get", return_value=FakeResponse(200, json_data={"id": "1"})):
            hc.check_ig_token(res, "tok")
        self.assertEqual(res.problems, [])

    def test_expired_code_190(self):
        res = hc.Result()
        body = {"error": {"code": 190, "type": "OAuthException", "message": "Session has expired"}}
        with mock.patch("ops_healthcheck.requests.get", return_value=FakeResponse(400, json_data=body)):
            hc.check_ig_token(res, "tok")
        self.assertEqual(len(res.problems), 1)
        self.assertIn("失効", res.problems[0][0])
        # トークン文字列を出力に含めない
        self.assertNotIn("tok", res.problems[0][0] + res.problems[0][1])

    def test_falls_back_to_second_host(self):
        res = hc.Result()
        seq = [hc.requests.ConnectionError(), FakeResponse(200, json_data={"id": "1"})]
        with mock.patch("ops_healthcheck.requests.get", side_effect=seq):
            hc.check_ig_token(res, "tok")
        self.assertEqual(res.problems, [])


class IssueSyncTests(unittest.TestCase):
    def _res(self, problems):
        res = hc.Result()
        for p in problems:
            res.problem(p, "detail")
        return res

    def test_creates_issue_when_problems_and_none_open(self):
        gh = FakeGitHub(issues=[])
        res = self._res(["X"])
        action = hc.sync_issue(gh, res, "body", out=lambda *_: None)
        self.assertEqual(action, "create")
        post = [c for c in gh.calls if c[0] == "POST"][0]
        self.assertEqual(post[2]["title"], hc.ISSUE_TITLE)
        self.assertIn(hc.FINGERPRINT_TAG, post[2]["body"])

    def test_updates_without_comment_when_unchanged(self):
        res = self._res(["X"])
        existing = {"number": 5, "title": hc.ISSUE_TITLE,
                    "body": f"old\n<!-- {hc.FINGERPRINT_TAG}: {res.fingerprint} -->"}
        gh = FakeGitHub(issues=[existing])
        action = hc.sync_issue(gh, res, "body", out=lambda *_: None)
        self.assertEqual(action, "update")
        self.assertTrue(any(c[0] == "PATCH" for c in gh.calls))
        self.assertFalse(any(c[0] == "POST" for c in gh.calls))  # コメントは付けない

    def test_updates_with_comment_when_changed(self):
        existing = {"number": 5, "title": hc.ISSUE_TITLE, "body": f"old\n<!-- {hc.FINGERPRINT_TAG}: 000 -->"}
        gh = FakeGitHub(issues=[existing])
        action = hc.sync_issue(gh, self._res(["X", "Y"]), "body", out=lambda *_: None)
        self.assertEqual(action, "update")
        comment = [c for c in gh.calls if c[0] == "POST" and c[1].endswith("/comments")]
        self.assertEqual(len(comment), 1)
        self.assertIn("- X", comment[0][2]["body"])

    def test_closes_when_recovered(self):
        existing = {"number": 5, "title": hc.ISSUE_TITLE, "body": "x"}
        gh = FakeGitHub(issues=[existing])
        action = hc.sync_issue(gh, self._res([]), "body", out=lambda *_: None)
        self.assertEqual(action, "close")
        patch = [c for c in gh.calls if c[0] == "PATCH"][0]
        self.assertEqual(patch[2]["state"], "closed")

    def test_ignores_pull_requests_and_other_titles(self):
        gh = FakeGitHub(issues=[
            {"number": 1, "title": hc.ISSUE_TITLE, "pull_request": {}},
            {"number": 2, "title": "別の Issue"},
        ])
        self.assertIsNone(hc.find_open_issue(gh))

    def test_dry_run_touches_nothing(self):
        gh = FakeGitHub(issues=[])
        hc.sync_issue(gh, self._res(["X"]), "body", dry_run=True, out=lambda *_: None)
        self.assertFalse(any(c[0] in ("POST", "PATCH") for c in gh.calls))

    def test_noop_when_healthy_and_no_issue(self):
        gh = FakeGitHub(issues=[])
        self.assertEqual(hc.sync_issue(gh, self._res([]), "body", out=lambda *_: None), "none")


class ReportTests(unittest.TestCase):
    def test_render_lists_problems_ok_notes(self):
        res = hc.Result()
        res.problem("見出し", "1行目\n2行目")
        res.ok.append("確認A")
        res.notes.append("補足B")
        text = hc.render_report(res, NOW, "https://run")
        self.assertIn("## 要対応", text)
        self.assertIn("- **見出し**", text)
        self.assertIn("  2行目", text)
        self.assertIn("- 確認A", text)
        self.assertIn("- 補足B", text)
        self.assertIn("[実行ログ](https://run)", text)

    def test_fingerprint_ignores_order_and_detail(self):
        a, b = hc.Result(), hc.Result()
        a.problem("X", "d1"); a.problem("Y", "d2")
        b.problem("Y", "other"); b.problem("X", "other")
        self.assertEqual(a.fingerprint, b.fingerprint)


if __name__ == "__main__":
    unittest.main()
