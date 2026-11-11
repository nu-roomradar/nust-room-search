"""scripts/_browser.py（画像を書き出すスクリプトが使うブラウザの場所探し）の検査。

フォルダ名の番号を決め打ちにしていて、環境が作り直されたときにポスターやストーリーが作れなくなった（2026-11）。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import _browser  # noqa: E402


def make_exe(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)
    return str(path)


class FindChromeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_none_when_nothing_is_installed(self):
        """GitHub Actions など。None を渡せば Playwright が自分のブラウザを使う"""
        self.assertIsNone(_browser.find_chrome(root=str(self.root)))
        self.assertIsNone(_browser.find_chrome(root=str(self.root / "no-such-dir")))

    def test_prefers_the_unnumbered_name(self):
        make_exe(self.root / "chromium-1243" / "chrome-linux64" / "chrome")
        stable = make_exe(self.root / "chromium")
        self.assertEqual(_browser.find_chrome(root=str(self.root)), stable)

    def test_picks_the_newest_build_by_number_not_by_spelling(self):
        make_exe(self.root / "chromium-998" / "chrome-linux" / "chrome")
        make_exe(self.root / "chromium-1194" / "chrome-linux" / "chrome")
        newest = make_exe(self.root / "chromium-1243" / "chrome-linux64" / "chrome")
        self.assertEqual(_browser.find_chrome(root=str(self.root)), newest)

    def test_ignores_the_headless_shell_and_files_that_cannot_run(self):
        make_exe(self.root / "chromium_headless_shell-1243" / "chrome-linux" / "chrome")
        broken = self.root / "chromium-1243" / "chrome-linux64" / "chrome"
        make_exe(broken)
        broken.chmod(0o644)
        if os.access(str(broken), os.X_OK):     # root で動かすと実行できてしまうので、その場合は確かめられない
            self.skipTest("実行権限の無いファイルを作れない環境")
        self.assertIsNone(_browser.find_chrome(root=str(self.root)))

    def test_a_dangling_link_falls_back_to_a_numbered_build(self):
        os.symlink(str(self.root / "gone"), str(self.root / "chromium"))
        newest = make_exe(self.root / "chromium-1243" / "chrome-linux64" / "chrome")
        self.assertEqual(_browser.find_chrome(root=str(self.root)), newest)


class ScriptsUseItTests(unittest.TestCase):
    def test_no_script_or_guide_hard_codes_a_build_number(self):
        """番号入りの場所（chromium-1194 など）をまた書き込むと、次に環境が変わったときに同じことが起きる"""
        import re
        pat = re.compile(r"/opt/pw-browsers/chromium-\d+")
        files = [*ROOT.glob("scripts/*.py"), *ROOT.glob("video/**/*.py"), *ROOT.glob(".claude/skills/*/SKILL.md"),
                 ROOT / "CLAUDE.md"]
        bad = [str(f.relative_to(ROOT)) for f in files
               if f.name != "_browser.py" and pat.search(f.read_text(encoding="utf-8", errors="ignore"))]
        self.assertEqual(bad, [])

    def test_image_scripts_ask_the_helper(self):
        for name in ("make_poster.py", "make_story_promo.py", "make_condolence_story.py"):
            src = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            self.assertIn("from _browser import find_chrome", src, name)
            self.assertIn("CHROME = find_chrome()", src, name)


if __name__ == "__main__":
    unittest.main()
