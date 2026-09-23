"""dashboard.html が読む data/occupancy.json が時間割 DB とずれていないこと"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import export_occupancy as eo  # noqa: E402


class OccupancyTests(unittest.TestCase):
    def test_committed_json_is_up_to_date(self):
        committed = json.loads((ROOT / "data" / "occupancy.json").read_text(encoding="utf-8"))
        self.assertEqual(committed, json.loads(json.dumps(eo.build(), ensure_ascii=False)),
                         "時間割 DB を差し替えたら python scripts/export_occupancy.py を走らせる")

    def test_counts_never_exceed_rooms(self):
        for v in eo.build()["views"]:
            for row in v["busy"]:
                self.assertTrue(all(0 <= n <= v["rooms"] for n in row))


if __name__ == "__main__":
    unittest.main()
