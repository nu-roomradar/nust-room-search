"""scripts/post_to_instagram.py のリール対応（2026-10）"""
import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import post_to_instagram as ig  # noqa: E402


class FakeResp:
    ok = True
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class ContainerTests(unittest.TestCase):
    def sent(self, **kw):
        with mock.patch.object(ig.requests, "post", return_value=FakeResp({"id": "c1"})) as post:
            ig.create_media_container("https://h", "acc", "tok", **kw)
        return post.call_args.kwargs["data"]

    def test_reel_sends_video_cover_and_caption(self):
        data = self.sent(image_url="https://x/cover.jpg", caption="本文", video_url="https://x/v.mp4")
        self.assertEqual(data["media_type"], "REELS")
        self.assertEqual(data["video_url"], "https://x/v.mp4")
        self.assertEqual(data["cover_url"], "https://x/cover.jpg")
        self.assertEqual(data["caption"], "本文")
        self.assertNotIn("image_url", data)

    def test_feed_and_story_unchanged(self):
        feed = self.sent(image_url="https://x/a.png", caption="本文")
        self.assertEqual(feed, {"access_token": "tok", "image_url": "https://x/a.png", "caption": "本文"})
        story = self.sent(image_url="https://x/s.png", caption="", story=True)
        self.assertEqual(story["media_type"], "STORIES")
        self.assertNotIn("caption", story)


class MainTests(unittest.TestCase):
    def run_main(self, argv):
        calls = {}
        def fake_create(host, acc, tok, image_url, caption, story=False, video_url=None):
            calls.update(image_url=image_url, caption=caption, story=story, video_url=video_url)
            return "c1"
        with mock.patch.object(sys, "argv", ["post_to_instagram.py"] + argv), \
             mock.patch.dict("os.environ", {"IG_ACCESS_TOKEN": "t", "IG_ACCOUNT_ID": "a"}), \
             mock.patch.object(ig, "detect_host", return_value="https://h"), \
             mock.patch.object(ig, "check_public_url"), \
             mock.patch.object(ig, "create_media_container", side_effect=fake_create), \
             mock.patch.object(ig, "wait_until_ready") as wait, \
             mock.patch.object(ig, "publish_media", return_value="m1"):
            ig.main()
        return calls, wait

    def test_reel_caption_gets_required_tag(self):
        calls, wait = self.run_main(["--video-url", "https://x/v.mp4", "--image-url", "https://x/c.jpg", "--caption", "本文"])
        self.assertIn("#日大生プロジェクト", calls["caption"])
        self.assertEqual(calls["video_url"], "https://x/v.mp4")
        self.assertEqual(wait.call_args.kwargs.get("timeout"), 600)  # 動画は変換を長めに待つ

    def test_reel_and_story_together_is_rejected(self):
        with self.assertRaises(SystemExit):
            self.run_main(["--video-url", "https://x/v.mp4", "--story"])


class ErrorOutputTests(unittest.TestCase):
    def test_network_error_never_prints_the_token(self):
        # requests の例外の文面には URL（?access_token=...）がそのまま入る
        secret = "IGAA-secret-token-for-test-9876"

        def boom(*a, **kw):
            raise ig.requests.ConnectionError(f"Max retries exceeded with url: /v21.0/1?fields=id&access_token={secret}")

        err = io.StringIO()
        with mock.patch.object(sys, "argv", ["post_to_instagram.py", "--image-url", "https://x/a.png", "--caption", "本文"]), \
             mock.patch.dict("os.environ", {"IG_ACCESS_TOKEN": secret, "IG_ACCOUNT_ID": "1"}), \
             mock.patch.object(ig.requests, "get", side_effect=boom), \
             redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            ig.main()
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("ConnectionError", err.getvalue())
        self.assertNotIn(secret, err.getvalue())

    def test_every_api_call_has_a_timeout(self):
        seen = []

        def fake(url, **kw):
            seen.append(kw.get("timeout"))
            return FakeResp({"id": "c1", "status_code": "FINISHED"})

        with mock.patch.object(ig.requests, "get", side_effect=fake), \
             mock.patch.object(ig.requests, "post", side_effect=fake), \
             redirect_stdout(io.StringIO()):
            host = ig.detect_host("1", "t")
            cid = ig.create_media_container(host, "1", "t", "https://x/a.png", "本文 #日大生プロジェクト")
            ig.wait_until_ready(host, cid, "t")
            ig.publish_media(host, "1", "t", cid)
        self.assertTrue(seen)
        self.assertTrue(all(t for t in seen), seen)


if __name__ == "__main__":
    unittest.main()
