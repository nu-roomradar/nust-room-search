#!/usr/bin/env python3
"""時間割 DB から「曜日×時限ごとに、検索対象の教室の何割が授業で埋まっているか」を集計し
data/occupancy.json に書き出す。dashboard.html の「教室の混み具合」が読む。

時間割 DB（schedule_final.db）を差し替えたら走らせ直す:
    python scripts/export_occupancy.py
"""
import collections
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "schedule_final.db"
OUT = ROOT / "data" / "occupancy.json"
DAYS = ["月", "火", "水", "木", "金", "土"]
PERIODS = [1, 2, 3, 4, 5, 6]
BUILDINGS = ["タワースコラ", "駿河台校舎", "船橋校舎"]


def build(db_path=DB):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rooms = collections.defaultdict(dict)  # 年度 -> 教室 -> 校舎
        for y, name, b in con.execute("SELECT 年度, name, building FROM classrooms"):
            rooms[y][name] = b
        busy = collections.defaultdict(set)    # (年度, 学期, 曜日, 時限) -> 教室（教室マスタにあるものだけ）
        for y, t, d, p, r in con.execute("SELECT DISTINCT 年度, 履修期名, 曜日, 時限, 教室 FROM schedules"):
            if r in rooms[y]:
                busy[(y, t, d, int(p))].add(r)
        terms = sorted({(y, t) for y, t, _, _ in busy}, reverse=True)
    finally:
        con.close()

    out = {"days": DAYS, "periods": PERIODS, "views": []}
    for y, t in terms:
        for b in ["all"] + BUILDINGS:
            members = {n for n, bb in rooms[y].items() if b == "all" or bb == b}
            if not members:
                continue
            grid = [[len(busy[(y, t, d, p)] & members) for p in PERIODS] for d in DAYS]
            out["views"].append({"year": y, "term": t, "building": b, "rooms": len(members), "busy": grid})
    return out


def main():
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"書き出しました: {OUT.relative_to(ROOT)}（{len(data['views'])} 通り）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
