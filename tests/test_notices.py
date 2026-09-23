"""
CLAUDE.md の「守るべきルール」1・2 を CI でも検査する。
.claude/hooks/guard-notices.py は Claude Code のセッション内でしか動かないため、
手作業のコミットや他のツールからの変更でも必須表記が消えていないことをここで保証する。
実行: python -m unittest discover -s tests -v
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ルール1: 「テスト運用中・非公式」表記（学生課/教務課と協議中のため誤認防止が必須）
NOTICE_FILES = {
    "templates/index.html": ["テスト運用中", "大学公式"],
    "index.html": ["テスト運用中", "大学公式"],
    "dashboard.html": ["テスト運用中", "大学公式"],
}
# ルール2: Instagram 投稿キャプションの必須タグとポスターの表記
REQUIRED_TAG = "#日大生プロジェクト"


class NoticeTests(unittest.TestCase):
    def test_unofficial_notice_present_in_every_public_page(self):
        for rel, phrases in NOTICE_FILES.items():
            text = (ROOT / rel).read_text(encoding="utf-8")
            for phrase in phrases:
                self.assertIn(phrase, text, f"{rel} に「{phrase}」が無い（CLAUDE.md ルール1）")

    def test_instagram_script_still_auto_adds_required_tag(self):
        src = (ROOT / "scripts" / "post_to_instagram.py").read_text(encoding="utf-8")
        m = re.search(r"REQUIRED_TAGS\s*=\s*\[([^\]]*)\]", src)
        self.assertIsNotNone(m, "REQUIRED_TAGS が見当たらない（CLAUDE.md ルール2）")
        self.assertIn(REQUIRED_TAG, m.group(1))
        self.assertIn("def ensure_required_tags", src)

    def test_poster_keeps_required_tag_and_test_notice(self):
        src = (ROOT / "scripts" / "make_poster.py").read_text(encoding="utf-8")
        self.assertIn(REQUIRED_TAG, src)
        self.assertIn("テスト運用中", src)


if __name__ == "__main__":
    unittest.main()
