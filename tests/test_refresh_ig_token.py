"""
scripts/refresh_ig_token.py のテスト。外部 API は全てフェイクに差し替える。

このスクリプトは月1回しか動かないうえ、失敗すると 60 日後に投稿できなくなる。
「Secret を壊さない」「トークンをログに出さない」「失効時に黙って成功しない」を固定する。
実行: python -m unittest discover -s tests -v
"""
import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import refresh_ig_token as rt  # noqa: E402

TOKEN = "IGAA-old-token-value-abcdefgh1234"
NEW = "IGAA-new-token-value-zyxwvu987654"
ENV = {"IG_ACCESS_TOKEN": TOKEN, "IG_REFRESH_PAT": "ghp_fake", "GITHUB_REPOSITORY": "nu-roomradar/nust-room-search"}


class FakeResponse:
    def __init__(self, status=200, json_data=None):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._json = json_data if json_data is not None else {}
        self.text = str(self._json)

    def json(self):
        return self._json


def run(argv=(), env=None, get=None, put=None):
    out, err = io.StringIO(), io.StringIO()
    patches = [mock.patch.dict("os.environ", env if env is not None else ENV, clear=True)]
    if get is not None:
        patches.append(mock.patch("refresh_ig_token.requests.get", side_effect=get))
    if put is not None:
        patches.append(mock.patch("refresh_ig_token.requests.put", side_effect=put))
    for p in patches:
        p.start()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = rt.main(list(argv))
    finally:
        for p in reversed(patches):
            p.stop()
    return rc, out.getvalue() + err.getvalue()


def happy_get(url, **kw):
    if "refresh_access_token" in url:
        return FakeResponse(200, {"access_token": NEW, "expires_in": 5184000})   # 60日
    if url.endswith("/me"):
        return FakeResponse(200, {"id": "17841400000000000"})
    if "public-key" in url:
        # libsodium の鍵として妥当な 32 バイトの base64
        return FakeResponse(200, {"key_id": "568250167715943520",
                                  "key": "u+n1Wz0ZGDGxLA+1KeXlCtLOaVh1Kg5YJQ1ldBVKpVQ="})
    raise AssertionError(f"想定外の GET: {url}")


class MaskTests(unittest.TestCase):
    def test_mask_hides_the_token_body(self):
        masked = rt.mask(TOKEN)
        self.assertNotIn(TOKEN, masked)
        self.assertIn(TOKEN[-4:], masked)
        self.assertIn(str(len(TOKEN)), masked)

    def test_mask_handles_short_or_empty(self):
        self.assertEqual(rt.mask(""), "<不正な値>")
        self.assertEqual(rt.mask("abc"), "<不正な値>")


class DryRunTests(unittest.TestCase):
    def test_dry_run_never_writes_the_secret(self):
        put = mock.Mock(side_effect=AssertionError("--dry-run で PUT してはいけない"))
        rc, out = run(["--dry-run"], get=happy_get, put=put)
        self.assertEqual(rc, 0, out)
        self.assertIn("Secret は書き換えていません", out)
        put.assert_not_called()

    def test_dry_run_works_without_a_pat(self):
        env = {"IG_ACCESS_TOKEN": TOKEN}
        rc, out = run(["--dry-run"], env=env, get=happy_get)
        self.assertEqual(rc, 0, out)


class GuardTests(unittest.TestCase):
    def test_missing_token_is_an_error(self):
        rc, out = run(env={}, get=happy_get)
        self.assertEqual(rc, 2)
        self.assertIn("IG_ACCESS_TOKEN", out)

    def test_missing_pat_is_an_error_and_does_not_call_the_api(self):
        get = mock.Mock(side_effect=AssertionError("PAT が無いのに API を叩いてはいけない"))
        rc, out = run(env={"IG_ACCESS_TOKEN": TOKEN}, get=get)
        self.assertEqual(rc, 2)
        self.assertIn("IG_REFRESH_PAT", out)
        get.assert_not_called()


class FailureTests(unittest.TestCase):
    def test_expired_token_fails_loudly_with_manual_steps(self):
        def get(url, **kw):
            return FakeResponse(400, {"error": {"code": 190, "type": "OAuthException",
                                                "message": "Session has expired"}})
        put = mock.Mock(side_effect=AssertionError("失敗時に PUT してはいけない"))
        rc, out = run(get=get, put=put)
        self.assertEqual(rc, 1)
        self.assertIn("既に失効", out)
        self.assertIn("手動で再発行", out)
        put.assert_not_called()

    def test_unusable_new_token_does_not_overwrite_the_secret(self):
        """延長できても新トークンが使えないなら Secret を壊してはいけない"""
        def get(url, **kw):
            if "refresh_access_token" in url:
                return FakeResponse(200, {"access_token": NEW, "expires_in": 5184000})
            if url.endswith("/me"):
                return FakeResponse(400, {"error": {"code": 190, "message": "Invalid token"}})
            raise AssertionError(url)
        put = mock.Mock(side_effect=AssertionError("検証に失敗したら PUT してはいけない"))
        rc, out = run(get=get, put=put)
        self.assertEqual(rc, 1)
        self.assertIn("Secret は書き換えていません", out)
        put.assert_not_called()

    def test_response_without_token_fails(self):
        def get(url, **kw):
            return FakeResponse(200, {"expires_in": 5184000})
        rc, out = run(get=get)
        self.assertEqual(rc, 1)
        self.assertIn("access_token がありません", out)

    def test_network_error_is_reported_not_swallowed(self):
        def get(url, **kw):
            raise rt.requests.ConnectionError("boom")
        rc, out = run(get=get)
        self.assertEqual(rc, 1)
        self.assertIn("通信に失敗", out)

    def test_secret_write_failure_is_reported(self):
        put = mock.Mock(return_value=FakeResponse(403, {"message": "Resource not accessible"}))
        rc, out = run(get=happy_get, put=put)
        self.assertEqual(rc, 1)
        self.assertIn("更新に失敗", out)


class SuccessTests(unittest.TestCase):
    def test_updates_secret_with_encrypted_value_and_never_logs_the_token(self):
        captured = {}

        def put(url, **kw):
            captured["url"] = url
            captured["json"] = kw.get("json")
            captured["auth"] = kw.get("headers", {}).get("Authorization")
            return FakeResponse(204)

        rc, out = run(get=happy_get, put=put)
        self.assertEqual(rc, 0, out)
        self.assertTrue(captured["url"].endswith("/actions/secrets/IG_ACCESS_TOKEN"))
        self.assertEqual(captured["auth"], "Bearer ghp_fake")
        body = captured["json"]
        self.assertIn("encrypted_value", body)
        self.assertIn("key_id", body)
        # 暗号化されていること = 平文が混ざっていないこと
        self.assertNotIn(NEW, body["encrypted_value"])
        # ログにトークンが出ていないこと
        for secret in (TOKEN, NEW, "ghp_fake"):
            self.assertNotIn(secret, out)
        self.assertIn("約60日", out)

    def test_warns_when_the_extension_is_unexpectedly_short(self):
        def get(url, **kw):
            if "refresh_access_token" in url:
                return FakeResponse(200, {"access_token": NEW, "expires_in": 5 * 86400})
            return happy_get(url, **kw)
        rc, out = run(get=get, put=lambda *a, **k: FakeResponse(204))
        self.assertEqual(rc, 0, out)
        self.assertIn("[WARN]", out)


if __name__ == "__main__":
    unittest.main()
