"""
scripts/build_schedule_db.py の回帰テスト。

このスクリプトは年1回しか使わないので、壊れていても気づきにくい。
最低限「現行 DB を再現できること」と「本番 DB を勝手に触らないこと」を固定する。
原本（data/source/*.xls）が揃っているときだけ本体の検査を走らせ、無ければスキップする。
実行: python -m unittest discover -s tests -v
"""
import hashlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_schedule_db.py"
PROD_DB = ROOT / "schedule_final.db"
SRC = ROOT / "data" / "source"

sys.path.insert(0, str(ROOT / "scripts"))
import build_schedule_db as bsd  # noqa: E402

HAVE_SOURCES = SRC.is_dir() and any(SRC.rglob("[0-9]_*.xls"))   # 年度フォルダの中を見る
needs_sources = unittest.skipUnless(HAVE_SOURCES, "原本 data/source/<年度>/*.xls が無い")


def run(*args):
    p = subprocess.run([sys.executable, str(SCRIPT), *args],
                       capture_output=True, text=True, cwd=str(ROOT), timeout=1800)
    return p.returncode, p.stdout + p.stderr


def rows_of(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        s = con.execute("SELECT 学科,履修期名,曜日,時限,教室,校舎,科目名 FROM schedules").fetchall()
        r = con.execute("SELECT name,building FROM classrooms").fetchall()
    finally:
        con.close()
    return s, r


class RoomTokenTests(unittest.TestCase):
    """教室名セルの割り方。中黒の扱いが理工と短大で逆なので、両方を固定する"""

    def test_splits_on_spaces_only(self):
        self.assertEqual(bsd.tokenize_rooms("633 635"), ["633", "635"])
        self.assertEqual(bsd.tokenize_rooms("819　826"), ["819", "826"])

    def test_does_not_split_inside_parentheses(self):
        self.assertEqual(bsd.tokenize_rooms("8号館実験室(819 826 829)"), ["8号館実験室(819 826 829)"])
        # 全角カッコも守る。守らないと「スタジオ（S701」「S705）」という壊れた教室名ができる
        self.assertEqual(bsd.tokenize_rooms("スタジオ（S701 S702 S705）"), ["スタジオ（S701 S702 S705）"])

    def test_expands_room_codes_in_full_width_parentheses(self):
        st = bsd.Stats()
        self.assertEqual(bsd.normalize_rooms("スタジオ（S701 S702 S705）", st, "t"),
                         ["S701", "S702", "S705"])

    def test_unifies_full_and_half_width(self):
        """全角・半角の違いは同じ教室として扱う（2026-09〜。以前は「階段教室（大）」が別の教室になっていた）"""
        st = bsd.Stats()
        self.assertEqual(bsd.normalize_rooms("階段教室（大）", st, "t"), ["階段教室(大)"])
        self.assertEqual(bsd.normalize_rooms("階段教室(大)", st, "t"), ["階段教室(大)"])
        self.assertEqual(bsd.normalize_rooms("CSTﾎｰﾙ", st, "t"), ["CSTホール"])
        self.assertEqual(bsd.normalize_rooms("ｓ３０３", st, "t"), ["s303"])
        # 波線は「~」にしない
        self.assertEqual(bsd.normalize_rooms("まち製図室１～５", st, "t"), ["まち製図室1～5"])

    def test_splits_joint_rooms(self):
        """規則D: 合同教室の略記は個別の教室に分ける"""
        cases = {
            "1456/7/8": ["1456", "1457", "1458"],
            "1457/58": ["1457", "1458"],
            "1042/43": ["1042", "1043"],
            "1231/32/33/34": ["1231", "1232", "1233", "1234"],
            "S1704/07/13/16": ["S1704", "S1707", "S1713", "S1716"],
            "521/2/3/4/5/7/8/9/10": ["521", "522", "523", "524", "525", "527", "528", "529", "5210"],
            "S401/2": ["S401", "S402"],
        }
        for token, expect in cases.items():
            st = bsd.Stats()
            self.assertEqual(bsd.normalize_rooms(token, st, "t"), expect, token)
            self.assertEqual(st.rule_d[token], 1)
        # 略記でないものは分けない
        self.assertIsNone(bsd.split_joint_rooms("1201"))
        self.assertIsNone(bsd.split_joint_rooms("101/102"))

    def test_fixes_known_typo_before_splitting(self):
        st = bsd.Stats()
        self.assertEqual(bsd.normalize_rooms("112/3", st, "t"), ["1122", "1123"])
        self.assertEqual(sum(st.room_fixes.values()), 1)

    def test_middle_dot_splits_only_between_room_codes(self):
        # 短大の原本: 教室番号の区切り
        self.assertEqual(bsd.split_middle_dot("1111・521"), ["1111", "521"])
        self.assertEqual(bsd.split_middle_dot("521・522"), ["521", "522"])
        # 理工の原本: 教室名そのもの。割ると壊れる
        self.assertEqual(bsd.split_middle_dot("テクノ・工作技術センター"), ["テクノ・工作技術センター"])
        self.assertEqual(bsd.split_middle_dot("1041"), ["1041"])
        # 半角の中黒・末尾に英字のある教室番号も、NFKC の後なら分ける
        self.assertEqual(bsd.normalize_rooms("812･805B・811C", bsd.Stats(), "t"), ["812", "805B", "811C"])

    def test_junk_token_is_listed_as_dropped(self):
        self.assertIn("他", bsd.EXCEPTION_DROP)


class CliTests(unittest.TestCase):
    def test_rejects_bad_divisions(self):
        for bad in ("x", "", "1,x"):
            rc, out = run("--divisions", bad, "--no-write")
            self.assertEqual(rc, 1, bad)
            self.assertIn("--divisions", out)

    def test_missing_source_dir_fails_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = run("--src", str(Path(tmp) / "nope"), "--no-write")
        self.assertEqual(rc, 1)
        self.assertIn("原本のフォルダがありません", out)

    @needs_sources
    def test_unknown_division_fails_clearly(self):
        rc, out = run("--divisions", "9", "--no-write")
        self.assertEqual(rc, 1)
        self.assertIn("合う原本がありません", out)


@needs_sources
class ReproductionTests(unittest.TestCase):
    """原本から現行 DB を再現できること。壊れたら年1回の入れ替えが成り立たない"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="bsd-"))
        cls.rikou = cls.tmp / "rikou.db"
        cls.allx = cls.tmp / "all.db"
        rc, out = run("--divisions", "1,3,4", "--out", str(cls.rikou))
        assert rc == 0, out
        rc, out = run("--out", str(cls.allx))
        assert rc == 0, out

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_full_build_reproduces_production_db_exactly(self):
        """全区分（短大込み）で本番 DB を再現できる。年1回の入れ替えが成り立つ前提"""
        prod_s, prod_r = rows_of(PROD_DB)
        new_s, new_r = rows_of(self.allx)
        self.assertEqual(Counter(new_s), Counter(prod_s), "schedules が現行 DB と一致しない")
        self.assertEqual(set(new_r), set(prod_r), "classrooms が現行 DB と一致しない")

    def test_excluding_tandai_drops_rows_but_keeps_classrooms(self):
        """--divisions 1,3,4 で短大が抜ける。教室マスタは元から理工のみなので変わらない"""
        all_s, all_r = rows_of(self.allx)
        rikou_s, rikou_r = rows_of(self.rikou)
        self.assertLess(len(rikou_s), len(all_s), "短大を外したのに行が減っていない")
        self.assertEqual(set(rikou_r), set(all_r),
                         "教室マスタは短大の有無で変わってはいけない（理工からだけ作るため）")

    def test_tandai_rows_are_labelled_and_on_funabashi(self):
        """短大の行は学科名で見分けがつき、船橋校舎に限られる"""
        all_s, _ = rows_of(self.allx)
        tandai = [x for x in all_s if x[0].startswith(bsd.TANDAI_PREFIX)]
        self.assertGreater(len(tandai), 0, "短大の行が1つも入っていない")
        self.assertEqual({x[5] for x in tandai}, {"船橋校舎"},
                         "短大は船橋校舎を共用している。他の校舎が出るのはおかしい")

    def test_tandai_marks_shared_rooms_as_occupied(self):
        """短大が理工の教室を使っている時間は使用中になる（これが取り込みの目的）"""
        all_s, all_r = rows_of(self.allx)
        rikou_s, _ = rows_of(self.rikou)
        names = {n for n, _ in all_r}
        without = {(x[1], x[2], x[3], x[4]) for x in rikou_s}
        with_t = {(x[1], x[2], x[3], x[4]) for x in all_s}
        added = {x for x in with_t - without if x[3] in names}
        self.assertGreater(len(added), 0, "短大を入れても共用教室の占有が増えていない")

    def test_no_junk_room_in_output(self):
        all_s, _ = rows_of(self.allx)
        self.assertNotIn("他", {x[4] for x in all_s})

    def test_production_db_is_untouched(self):
        digest = hashlib.md5(PROD_DB.read_bytes()).hexdigest()
        rc, out = run("--out", str(self.tmp / "again.db"), "--report")
        self.assertEqual(rc, 0, out)
        self.assertEqual(hashlib.md5(PROD_DB.read_bytes()).hexdigest(), digest,
                         "--replace なしで本番 DB が変わった")


if __name__ == "__main__":
    unittest.main()
