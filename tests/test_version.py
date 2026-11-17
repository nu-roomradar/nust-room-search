"""
版番号（vX.Y.Z。docs/OPERATIONS.md 4.11）の表示がそろっているかの検査。

番号の元はリポジトリ直下の VERSION の1か所。検索アプリは app.py がそこから読み、
紹介ページ・about・dashboard（GitHub Pages の静的なページ）は同じ番号を直書きしている。
番号を上げるときは VERSION・3つのページの足元・about の「バージョン」の章を一緒に直す。
実行: python -m unittest tests.test_version -v
"""
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"\d+\.\d+\.\d+")


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def as_tuple(v):
    return tuple(int(x) for x in v.split("."))


VERSION = read("VERSION").strip()


class VersionSourceTest(unittest.TestCase):
    def test_version_file_is_semver(self):
        self.assertRegex(VERSION, r"^\d+\.\d+\.\d+$")

    def test_version_matches_changelog(self):
        """CHANGELOG の先頭の版と同じか、main に出す前の次の版（先頭より大きい）であること"""
        m = re.search(r"^## v(\d+\.\d+\.\d+) — (\d{4}-\d{2}-\d{2})", read("docs/CHANGELOG.md"), re.M)
        self.assertIsNotNone(m, "CHANGELOG に版の見出しが無い")
        top = m.group(1)
        self.assertGreaterEqual(as_tuple(VERSION), as_tuple(top),
                                f"VERSION {VERSION} が CHANGELOG の先頭 v{top} より古い")


class StaticPagesTest(unittest.TestCase):
    def test_lp_and_about_footer(self):
        for name, href in (("index.html", "about.html#version"), ("about.html", "#version")):
            with self.subTest(page=name):
                found = re.findall(r'<p class="foot-ver"><a href="([^"]+)">v([\d.]+)</a></p>', read(name))
                self.assertEqual(found, [(href, VERSION)])

    def test_dashboard_footer(self):
        self.assertEqual(re.findall(r'<span class="ver">v([\d.]+)</span>', read("dashboard.html")), [VERSION])

    def test_about_version_card(self):
        html = read("about.html")
        self.assertIn('id="version"', html)
        self.assertEqual(re.findall(r'<p class="ab-ver-v" data-version="([\d.]+)">v([\d.]+)</p>', html),
                         [(VERSION, VERSION)])
        digits = re.findall(r"<div><dt>(\d+)</dt>", html)
        self.assertEqual(".".join(digits), VERSION, "3つの数字の札が VERSION と違う")

    def test_about_current_row(self):
        """歩みの一覧で「いま」の印（is-key）が付くのは、いまの版の1行だけ"""
        html = read("about.html")
        rows = re.findall(r'<li class="is-key"><span class="ab-vl-k"><span class="ab-vl-v">v([\d.]+)</span>'
                          r'<time datetime="([\d-]+)">', html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], VERSION)
        card = re.search(r'<p class="ab-ver-d"><time datetime="([\d-]+)">', html)
        self.assertEqual(card.group(1), rows[0][1], "札の日付と一覧の日付が違う")
        m = re.search(r"^## v(\d+\.\d+\.\d+) — (\d{4}-\d{2}-\d{2})", read("docs/CHANGELOG.md"), re.M)
        if m.group(1) == VERSION:
            self.assertEqual(rows[0][1], m.group(2), "about の日付が CHANGELOG と違う")

    def test_about_list_versions_exist_in_changelog(self):
        """about に載せた版は、CHANGELOG に同じ日付で載っている（まだ出していない、いまの版を除く）"""
        log = dict(re.findall(r"^## v(\d+\.\d+\.\d+) — (\d{4}-\d{2}-\d{2})", read("docs/CHANGELOG.md"), re.M))
        rows = re.findall(r'<span class="ab-vl-v">v(\d+\.\d+\.\d+)</span><time datetime="([\d-]+)">', read("about.html"))
        self.assertGreater(len(rows), 10)
        for v, d in rows:
            if v == VERSION and v not in log:
                continue
            with self.subTest(version=v):
                self.assertEqual(log.get(v), d)


class AppPagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._cwd = os.getcwd()
        if "app" in sys.modules:
            cls.rr = sys.modules["app"]
        else:
            cls._tmp = tempfile.mkdtemp(prefix="rr-ver-")
            shutil.copy(ROOT / "schedule_final.db", cls._tmp)
            os.chdir(cls._tmp)
            sys.path.insert(0, str(ROOT))
            import app  # noqa: E402  揮発DBは一時ディレクトリに作る
            cls.rr = app
        cls.rr.app.config["TESTING"] = True
        cls.client = cls.rr.app.test_client()

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._cwd)

    def test_app_reads_version_file(self):
        self.assertEqual(self.rr.SERVICE_VERSION, VERSION)

    def test_every_app_page_shows_version(self):
        link = f'href="https://nu-roomradar.github.io/nust-room-search/about.html#version"'
        for path in ("/", "/room", "/room/" + "S101"):
            with self.subTest(path=path):
                res = self.client.get(path)
                self.assertEqual(res.status_code, 200)
                body = res.get_data(as_text=True)
                self.assertIn(f">v{VERSION}</a>", body)
                self.assertIn(link, body)


if __name__ == "__main__":
    unittest.main()
