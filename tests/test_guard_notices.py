"""
.claude/hooks/guard-notices.py（必須表記ガード）の挙動テスト。
一時ディレクトリに最小のリポジトリを作り、hook をサブプロセスとして本物の JSON で叩く。
実行: python -m unittest discover -s tests -v
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "guard-notices.py"

APP = "<p><strong>テスト運用中</strong>の非公式サービスです（大学公式ではありません）</p>\n<footer>現在テスト運用中です。大学公式のものではありません。</footer>\n"
INDEX = "<span>現在テスト運用中の非公式サービスです（学生開発・大学公式ではありません）。</span>\n<span>© RoomRadar — 大学公式のものではなく、現在テスト運用中です。</span>\n"
DASH = "<span>テスト運用中の非公式サービスです（学生開発・大学公式ではありません）。</span>\n"
POST = 'REQUIRED_TAGS = ["#日大生プロジェクト"]\n\ndef ensure_required_tags(caption):\n    return caption\n'
POSTER = '<span class="hash">#日大生プロジェクト</span>\n'


class GuardNoticesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="guard-"))
        (self.tmp / "scripts").mkdir()
        (self.tmp / ".claude").mkdir()
        (self.tmp / "templates").mkdir()
        self.write("templates/index.html", APP)
        self.write("templates/room.html", APP)          # 教室の1週間
        self.write("templates/room_search.html", APP)   # 教室から探す
        self.write("index.html", INDEX)
        self.write("dashboard.html", DASH)
        self.write("scripts/post_to_instagram.py", POST)
        self.write("scripts/make_poster.py", POSTER)
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, text):
        (self.tmp / rel).write_text(text, encoding="utf-8")

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.tmp), *args], check=True, capture_output=True)

    def hook(self, mode, payload=None, env=None):
        e = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.tmp)}
        e.pop("ROOMRADAR_GUARD_RELAX", None)
        if env:
            e.update(env)
        p = subprocess.run([sys.executable, str(HOOK), mode], input=json.dumps(payload or {}),
                           capture_output=True, text=True, env=e, cwd=str(self.tmp))
        return p.returncode, p.stderr

    def edit(self, path, old, new, replace_all=False):
        return {"tool_name": "Edit", "tool_input": {"file_path": path, "old_string": old,
                                                    "new_string": new, "replace_all": replace_all}}

    # --- tree / stop ---------------------------------------------------------

    def test_clean_tree_passes(self):
        self.assertEqual(self.hook("tree")[0], 0)

    def test_tree_blocks_when_notice_reduced(self):
        self.write("dashboard.html", DASH.replace("テスト運用中", "正式運用中"))
        rc, err = self.hook("tree", {"stop_hook_active": False})
        self.assertEqual(rc, 2)
        self.assertIn("dashboard.html", err)
        self.assertIn("'テスト運用中'", err)

    def test_tree_guards_room_pages_too(self):
        for rel in ("templates/room.html", "templates/room_search.html"):
            self.write(rel, APP.replace("大学公式", "公式"))
            rc, err = self.hook("tree", {"stop_hook_active": False})
            self.assertEqual(rc, 2, rel)
            self.assertIn(rel, err)
            self.write(rel, APP)

    def test_stop_does_not_reblock_when_already_continued(self):
        self.write("dashboard.html", "x")
        self.assertEqual(self.hook("tree", {"stop_hook_active": True})[0], 0)

    # --- bash ----------------------------------------------------------------

    def test_bash_ignores_unrelated_commands(self):
        self.write("dashboard.html", "x")
        self.assertEqual(self.hook("bash", {"tool_input": {"command": "ls -la && git status"}})[0], 0)

    def test_bash_blocks_commit_and_push_when_broken(self):
        self.write("dashboard.html", "x")
        for cmd in ("git commit -m x", "git config user.name a && git commit -m x", "git push -u origin main"):
            rc, _ = self.hook("bash", {"tool_input": {"command": cmd}})
            self.assertEqual(rc, 2, cmd)

    def test_bash_allows_commit_when_clean(self):
        self.assertEqual(self.hook("bash", {"tool_input": {"command": "git commit -m x"}})[0], 0)

    # --- edit ----------------------------------------------------------------

    def test_edit_reducing_count_is_blocked(self):
        rc, err = self.hook("edit", self.edit("templates/index.html", "<strong>テスト運用中</strong>の非公式サービスです",
                                              "<strong>正式公開</strong>の公式サービスです"))
        self.assertEqual(rc, 2)
        self.assertIn("1 箇所（必要 2）", err)

    def test_edit_keeping_count_passes(self):
        rc, _ = self.hook("edit", self.edit("templates/index.html", "<strong>テスト運用中</strong>の非公式サービスです",
                                            "<strong>テスト運用中</strong>の非公式サービスです（β）"))
        self.assertEqual(rc, 0)

    def test_edit_unrelated_file_passes(self):
        rc, _ = self.hook("edit", {"tool_name": "Write", "tool_input": {"file_path": "README.md", "content": "x"}})
        self.assertEqual(rc, 0)

    def test_write_removing_notice_is_blocked(self):
        rc, err = self.hook("edit", {"tool_name": "Write", "tool_input": {"file_path": "dashboard.html", "content": "<html/>"}})
        self.assertEqual(rc, 2)
        self.assertIn("ルール1", err)

    def test_edit_breaking_required_tags_is_blocked(self):
        rc, err = self.hook("edit", self.edit("scripts/post_to_instagram.py",
                                              'REQUIRED_TAGS = ["#日大生プロジェクト"]', "REQUIRED_TAGS = []"))
        self.assertEqual(rc, 2)
        self.assertIn("ルール2", err)

    def test_move_add_then_remove_passes(self):
        # 先に追加（作業ツリーは HEAD より多い）→ その後1箇所削除しても HEAD と同数なので通る
        self.write("index.html", INDEX + "<!-- 現在テスト運用中・大学公式ではありません -->\n")
        rc, _ = self.hook("edit", self.edit("index.html",
                                            "現在テスト運用中の非公式サービスです（学生開発・大学公式ではありません）。",
                                            "（移動済み）"))
        self.assertEqual(rc, 0)

    def test_edit_with_absolute_path(self):
        rc, _ = self.hook("edit", self.edit(str(self.tmp / "dashboard.html"), "テスト運用中", "正式運用中"))
        self.assertEqual(rc, 2)

    def test_edit_whose_old_string_is_absent_is_left_to_tool(self):
        rc, _ = self.hook("edit", self.edit("templates/index.html", "存在しない文字列", "x"))
        self.assertEqual(rc, 0)

    # --- relax ---------------------------------------------------------------

    def test_relax_marker_allows_reduction_but_not_removal(self):
        (self.tmp / ".claude" / "guard-relax").touch()
        rc, _ = self.hook("edit", self.edit("templates/index.html", "<strong>テスト運用中</strong>の非公式サービスです",
                                            "<strong>正式公開</strong>の公式サービスです"))
        self.assertEqual(rc, 0)
        rc, _ = self.hook("edit", {"tool_name": "Write", "tool_input": {"file_path": "dashboard.html", "content": "<html/>"}})
        self.assertEqual(rc, 2)

    def test_relax_env_allows_reduction(self):
        rc, _ = self.hook("edit", self.edit("templates/index.html", "<strong>テスト運用中</strong>の非公式サービスです",
                                            "<strong>正式公開</strong>の公式サービスです"),
                          env={"ROOMRADAR_GUARD_RELAX": "1"})
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
