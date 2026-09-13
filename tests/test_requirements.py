"""
スクリプトが import しているパッケージが、ちゃんと requirements に書いてあるか。

2026-09 に xlrd をローカルで入れただけで requirements に足さず、CI が 4 回続けて
失敗していた（気づいたのは週次の運用ヘルスチェック）。同じ取りこぼしを防ぐ。

対象は「モジュールの先頭で import しているもの」だけ。関数の中で import して
ImportError を捕まえているもの（inspect_timetable.py の pymupdf など）は任意扱い。
実行: python -m unittest discover -s tests -v
"""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REQ = ROOT / "requirements.txt"
REQ_DEV = ROOT / "requirements-dev.txt"

# import 名 → パッケージ名（違うものだけ書く）
DISTRIBUTION = {
    "PIL": "pillow",
    "pptx": "python-pptx",
    "fitz": "pymupdf",
    "cv2": "opencv-python-headless",
    "yaml": "pyyaml",
    "dateutil": "python-dateutil",
}
# リポジトリ内のモジュール（scripts/ 直下を sys.path に足して import している）
LOCAL = {p.stem for p in SCRIPTS.glob("*.py")}


def declared():
    names = set()
    for path in (REQ, REQ_DEV):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            # 「flask」「requests>=2」「pillow==11.0」など
            for sep in ("==", ">=", "<=", "~=", ">", "<", "[", ";"):
                line = line.split(sep, 1)[0]
            names.add(line.strip().lower().replace("_", "-"))
    return names


def top_level_imports(path):
    """モジュール直下（関数・try の外）の import だけを返す"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out = set()
    for node in tree.body:                      # body だけ見る = ネストは対象外
        if isinstance(node, ast.Import):
            out.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.add(node.module.split(".")[0])
    return out


class RequirementsTests(unittest.TestCase):
    def test_dev_requirements_file_exists(self):
        self.assertTrue(REQ_DEV.exists(), "requirements-dev.txt が無い")
        self.assertTrue(declared(), "requirements に 1 つも書かれていない")

    def test_every_script_import_is_declared(self):
        missing = {}
        for path in sorted(SCRIPTS.glob("*.py")):
            for mod in sorted(top_level_imports(path)):
                if mod in sys.stdlib_module_names or mod in LOCAL:
                    continue
                dist = DISTRIBUTION.get(mod, mod).lower().replace("_", "-")
                if dist not in declared():
                    missing.setdefault(path.name, []).append(f"{mod}（{dist}）")
        self.assertEqual(
            missing, {},
            "requirements に書かれていない import がある。requirements-dev.txt に足すこと:\n"
            + "\n".join(f"  {f}: {', '.join(m)}" for f, m in missing.items()))

    def test_ci_and_session_hook_install_dev_requirements(self):
        """CI とセッション初期化が requirements-dev.txt を読んでいること（二重管理を防ぐ）"""
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        hook = (ROOT / ".claude" / "hooks" / "session-start.sh").read_text(encoding="utf-8")
        self.assertIn("requirements-dev.txt", ci, "ci.yml が requirements-dev.txt を入れていない")
        self.assertIn("requirements-dev.txt", hook,
                      "session-start.sh が requirements-dev.txt を入れていない")

    def test_app_requirements_stay_lean(self):
        """Render が入れる requirements.txt に開発用の重い依存を混ぜない"""
        app = {line.split("#", 1)[0].strip().lower()
               for line in REQ.read_text(encoding="utf-8").splitlines()}
        for heavy in ("playwright", "python-pptx", "xlrd"):
            self.assertNotIn(heavy, app, f"{heavy} は requirements-dev.txt に書く")


if __name__ == "__main__":
    unittest.main()
