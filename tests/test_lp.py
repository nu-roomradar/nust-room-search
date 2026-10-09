"""LP（index.html）の中身が、アプリ・時間割 DB・CLAUDE.md のルールとずれていないこと"""
import re
import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LP = (ROOT / "index.html").read_text(encoding="utf-8")


def lang_spans(cls):
    return re.findall(rf'<span class="{cls}">(.*?)</span>', LP, re.S)


class LandingPageTests(unittest.TestCase):
    def test_room_count_matches_latest_year_in_db(self):
        """ヒーローの教室数は、DB のいちばん新しい年度の駿河台キャンパス（タワースコラ・駿河台校舎）の教室数。
        テスト運用は駿河台キャンパスのみが対象なので、船橋校舎は数えない（2026-10 学生課と協議）"""
        con = sqlite3.connect(f"file:{ROOT / 'schedule_final.db'}?mode=ro", uri=True)
        try:
            year, n = con.execute(
                "SELECT 年度, COUNT(*) FROM classrooms WHERE 年度=(SELECT MAX(年度) FROM classrooms) "
                "AND building IN ('タワースコラ', '駿河台校舎')").fetchone()
        finally:
            con.close()
        m = re.search(r'data-count="(\d+)" id="stat-rooms"><span class="num">(\d+)</span>', LP)
        self.assertIsNotNone(m)
        self.assertEqual((int(m.group(1)), int(m.group(2))), (n, n), f"{year}年度の駿河台キャンパスの教室は {n} 室")
        self.assertIn(f"駿河台の教室（{year}年度）", LP)

    def test_no_tentative_hold_and_no_funabashi(self):
        """仮予約は廃止。船橋校舎はテスト運用の対象外なので LP に載せない（2026-10 学生課と協議）。
        検索アプリでは船橋校舎も選べるが、周知物（LP・ポスター）では扱わない"""
        visible = " ".join(lang_spans("ja") + lang_spans("en") + lang_spans("zh"))
        for bad in ("仮予約", "Tentative hold", "tentative hold", "临时占用", "船橋", "Funabashi", "船桥"):
            self.assertNotIn(bad, visible, bad)
        for bad in ("Room Reservation", "reserve it", "it's taken", "已被占用", "仮予約"):
            self.assertNotIn(bad, LP)
        self.assertIn("campuses', 'tower ichi'", LP)   # 3D 模型も駿河台の2校舎だけ

    def test_no_overclaiming_real_time_or_official_data(self):
        for bad in ("リアルタイム", "real-time", "in real time", "实时", "大学公式の時間割", "official timetable"):
            self.assertNotIn(bad, LP)

    def test_share_preview_and_icons_exist(self):
        for rel in re.findall(r'(?:href|src|content)="(?:https://nu-roomradar\.github\.io/nust-room-search/)?(assets/lp/[^"]+)"', LP):
            self.assertTrue((ROOT / rel).exists(), rel)
        for tag in ('property="og:image"', 'property="og:description"', 'name="description"', 'rel="apple-touch-icon"'):
            self.assertIn(tag, LP)
        og = re.search(r'property="og:description" content="([^"]+)"', LP).group(1)
        self.assertIn("非公式", og)

    def test_feedback_form_labels_are_linked(self):
        for fid in ("fbCategory", "fbOpinion", "fbContact"):
            self.assertIn(f'<label for="{fid}">', LP)
            self.assertIn(f'id="{fid}"', LP)


if __name__ == "__main__":
    unittest.main()
