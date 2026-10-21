"""
GitHub Actions のサプライチェーン対策が崩れていないか（2026-10-22 点検）。

- Action は乗っ取られたタグの付け替えに備えて、コミット SHA で固定する
- Secrets や書き込み権限を持つワークフローの pip は、版とハッシュで固定したファイルから入れる
- push しないジョブは、checkout のトークンをディスクに残さない
実行: python -m unittest discover -s tests -v
"""
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github/workflows").glob("*.yml"))
LOCKS = ROOT / ".github/requirements"


def steps(doc):
    for job in doc["jobs"].values():
        yield from job.get("steps", [])


class WorkflowSupplyChainTests(unittest.TestCase):
    def test_actions_are_pinned_to_a_commit_sha(self):
        for wf in WORKFLOWS:
            for step in steps(yaml.safe_load(wf.read_text(encoding="utf-8"))):
                if "uses" in step:
                    self.assertRegex(step["uses"], r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$", f"{wf.name}: {step['uses']}")

    def test_sensitive_workflows_install_only_hash_locked_packages(self):
        for wf in WORKFLOWS:
            text = wf.read_text(encoding="utf-8")
            if "secrets." not in text and "contents: write" not in text:
                continue                    # ci.yml など、Secrets も書き込み権限も無いもの
            for step in steps(yaml.safe_load(text)):
                for line in str(step.get("run", "")).splitlines():
                    if not re.search(r"\bpip install\b", line):
                        continue
                    m = re.search(r"--require-hashes --only-binary :all: -r (\.github/requirements/[\w-]+\.txt)$", line.strip())
                    self.assertIsNotNone(m, f"{wf.name}: {line.strip()}")
                    self.assertTrue((ROOT / m.group(1)).exists(), m.group(1))

    def test_every_lock_entry_has_a_version_and_hashes(self):
        for lock in LOCKS.glob("*.txt"):
            self.assertTrue(lock.with_suffix(".in").exists(), lock.name)
            entries = re.findall(r"^([A-Za-z0-9_.-]+)==(\S+) \\\n((?:    --hash=sha256:[0-9a-f]{64}(?: \\)?\n)+)",
                                 lock.read_text(encoding="utf-8"), flags=re.M)
            self.assertTrue(entries, lock.name)
            names = {n.lower().replace("_", "-") for n, _, _ in entries}
            for want in lock.with_suffix(".in").read_text(encoding="utf-8").split():
                self.assertIn(want.lower(), names, f"{lock.name} に {want} が無い")

    def test_jobs_that_do_not_push_drop_the_checkout_token(self):
        for wf in WORKFLOWS:
            text = wf.read_text(encoding="utf-8")
            if "git push" in text:
                continue
            for step in steps(yaml.safe_load(text)):
                if str(step.get("uses", "")).startswith("actions/checkout@"):
                    self.assertIs(step.get("with", {}).get("persist-credentials"), False, wf.name)


if __name__ == "__main__":
    unittest.main()
