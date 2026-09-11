"""
scripts/inspect_timetable.py のテスト。
原本が届いたときに最初に走らせる道具なので、未知の形式や壊れたファイルで
落ちないこと・黙って飛ばさないことを保証する。
実行: python -m unittest discover -s tests -v
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import inspect_timetable as it  # noqa: E402


def run(*argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = it.main(list(argv))
    return rc, buf.getvalue()


class ClassifyTests(unittest.TestCase):
    def test_recognizes_timetable_column_names(self):
        self.assertIn("曜日", it.classify("曜日"))
        self.assertIn("教室", it.classify("講義室"))
        self.assertIn("学期", it.classify("履修期名"))
        self.assertIn("時間割CD", it.classify("時間割CD"))
        self.assertEqual(it.classify("なまえ"), [])

    def test_classify_survives_non_string_cells(self):
        for v in (None, 1, 3.5, float("nan")):
            self.assertEqual(it.classify(v), [])


class DirectoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tt-"))

    def test_empty_dir_points_at_the_readme(self):
        rc, out = run(str(self.tmp))
        self.assertEqual(rc, 0)
        self.assertIn("解析できるファイルがありません", out)
        self.assertIn("README.md", out)

    def test_readme_is_not_treated_as_data(self):
        (self.tmp / "README.md").write_text("# 置き場", encoding="utf-8")
        rc, out = run(str(self.tmp))
        self.assertEqual(rc, 0)
        self.assertIn("解析できるファイルがありません", out)

    def test_unsupported_files_are_reported_not_silently_dropped(self):
        (self.tmp / "timetable.docx").write_bytes(b"x")
        (self.tmp / "notes.txt").write_text("x", encoding="utf-8")
        rc, out = run(str(self.tmp))
        self.assertEqual(rc, 0)
        self.assertIn("[WARN]", out)
        self.assertIn("timetable.docx", out)
        self.assertIn("notes.txt", out)

    def test_missing_path_returns_error_code(self):
        rc, _ = run(str(self.tmp / "nope"))
        self.assertEqual(rc, 2)


class FileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tt-"))

    def test_csv_header_row_and_hints(self):
        p = self.tmp / "1-01.csv"
        p.write_text("学科,曜日,時限,教室,科目名\n土木工学科,月,1,1041,構造力学\n", encoding="utf-8-sig")
        rc, out = run(str(p), "--rows", "3")
        self.assertEqual(rc, 0)
        self.assertIn("区切りテキスト", out)
        self.assertIn("ヘッダーらしき行: 0行目", out)
        for hint in ("曜日", "時限", "教室"):
            self.assertIn(hint, out)

    def test_cp932_csv_is_read(self):
        p = self.tmp / "sjis.csv"
        p.write_bytes("曜日,教室\n月,1041\n".encode("cp932"))
        rc, out = run(str(p))
        self.assertEqual(rc, 0)
        self.assertIn("cp932", out)

    def test_excel_reports_sheets_and_shape(self):
        import pandas as pd
        p = self.tmp / "1-02.xlsx"
        with pd.ExcelWriter(p) as w:
            pd.DataFrame({"曜日": ["月"], "時限": [1], "教室": ["S101"]}).to_excel(w, sheet_name="前期", index=False)
            pd.DataFrame({"曜日": ["火"], "時限": [2], "教室": ["1041"]}).to_excel(w, sheet_name="後期", index=False)
        rc, out = run(str(p), "--rows", "3")
        self.assertEqual(rc, 0)
        self.assertIn("シート 2個", out)
        self.assertIn("前期", out)
        self.assertIn("後期", out)

    def test_corrupt_file_is_reported_without_crashing(self):
        p = self.tmp / "broken.xlsx"
        p.write_bytes(b"not really a workbook")
        rc, out = run(str(p))
        self.assertEqual(rc, 0)          # 1ファイル壊れても全体は止めない
        self.assertIn("解析に失敗", out)

    def test_unsupported_single_file_says_so(self):
        p = self.tmp / "x.docx"
        p.write_bytes(b"x")
        rc, out = run(str(p))
        self.assertEqual(rc, 0)
        self.assertIn("未対応の形式", out)


if __name__ == "__main__":
    unittest.main()
