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
        """ヒーローの教室数は、DB のいちばん新しい年度の教室マスタの件数（年度を足したら直す）"""
        con = sqlite3.connect(f"file:{ROOT / 'schedule_final.db'}?mode=ro", uri=True)
        try:
            year, n = con.execute(
                "SELECT 年度, COUNT(*) FROM classrooms WHERE 年度=(SELECT MAX(年度) FROM classrooms)").fetchone()
        finally:
            con.close()
        m = re.search(r'data-count="(\d+)" id="stat-rooms"><span class="num">(\d+)</span>', LP)
        self.assertIsNotNone(m)
        self.assertEqual((int(m.group(1)), int(m.group(2))), (n, n), f"{year}年度の教室は {n} 室")
        self.assertIn(f"教室（{year}年度）", LP)

    def test_tentative_hold_never_reads_as_a_real_reservation(self):
        """CLAUDE.md ルール3: 仮予約に触れる文には、公式でない・使用権を保証しない旨を併記する"""
        # 仮予約で「何ができるか」を説明する文（「予約」と「できます」を含むもの）が対象
        described = [t for t in lang_spans("ja") if "予約" in t and "できます" in t]
        self.assertGreaterEqual(len(described), 2)
        for text in described:
            self.assertIn("使用権", text, text)
            self.assertIn("大学公式", text, text)
        # 英語も同じ: 仮予約で何ができるかを説明する文には「公式の予約ではない」を入れる
        described_en = [t for t in lang_spans("en") if "let others know you plan" in t or "add a tentative hold" in t]
        self.assertGreaterEqual(len(described_en), 2)
        for text in described_en:
            self.assertIn("not an official", text, text)
        for bad in ("Room Reservation", "reserve it", "it's taken", "已被占用"):
            self.assertNotIn(bad, LP)

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
