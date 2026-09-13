#!/usr/bin/env python3
"""
時間割の原本(.xls)から、授業の生データを 1 枚の CSV にまとめる。

schedule_final.db は空き教室を判定するのに必要な列しか持っていない（学科・学期・曜日・
時限・教室・校舎・科目名）。原本にはほかに **時間割CD・単位・対象学年・教員名** が
入っているが、DB には残らない。この CSV はそれも含めた「授業の生データの一覧」で、
Excel も 49 個の .xls も開かずに中身を確かめたり、年度どうしを比べたりするためのもの。

アプリはこの CSV を読まない。検索が使うのは schedule_final.db だけ。

出力する列:
  年度, 区分, 学科, 時間割CD, 履修期名, 曜日, 時限, 科目名, 単位, 対象学年, 教員名,
  校舎記号, 校舎, 教室名（原本の表記）, 教室（正規化後）, 原本ファイル

1 行 = 1 コマ × 1 教室。原本の 1 セルに複数教室が書かれている授業は教室ごとに行が割れる
（schedule_final.db と同じ数え方）。教室未定の "000" は原本にあるが除く。

使い方:
  python scripts/export_classes.py                       # data/classes_2026.csv に書く
  python scripts/export_classes.py --out /tmp/x.csv      # 出力先を変える
  python scripts/export_classes.py --divisions 1,3,4     # 区分を絞る（短大を外す等）
  python scripts/export_classes.py --stdout              # 画面に出す
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_schedule_db as bsd  # noqa: E402  パーサは本体と共有する（二重管理を避ける）

REPO = Path(__file__).resolve().parents[1]
FIELDS = ["年度", "区分", "学科", "時間割CD", "履修期名", "曜日", "時限", "科目名",
          "単位", "対象学年", "教員名", "校舎記号", "校舎", "教室名", "教室", "原本ファイル"]


def collect(src_dir, divisions, stats):
    """原本 → CSV の行。教室ごとに 1 行（schedule_final.db と同じ数え方）"""
    rows = []
    for meta, path in bsd.collect_sources(src_dir, divisions):
        stats.files += 1
        for rec in bsd.read_workbook(path, meta, stats):
            stats.room_cells += 1
            rooms = bsd.normalize_rooms(rec["room_raw"], stats, rec["source"])
            buildings = bsd.resolve_buildings(rooms, rec["building_col"], stats, rec["source"])
            dept = rec["dept"]
            for room, building in zip(rooms, buildings):
                rows.append({
                    "年度": rec["year"], "区分": rec["division"], "学科": dept,
                    "時間割CD": rec["code"], "履修期名": rec["term"], "曜日": rec["day"],
                    "時限": rec["period"], "科目名": rec["subject"], "単位": rec["credits"],
                    "対象学年": rec["grade"], "教員名": rec["teacher"],
                    "校舎記号": rec["building_col"], "校舎": building,
                    "教室名": rec["room_raw"], "教室": room, "原本ファイル": rec["file"],
                })
    return rows


def summarize(rows, out):
    """中身の要約。CSV を開かなくても規模と内訳が分かるように"""
    def tally(key):
        c = {}
        for r in rows:
            c[r[key]] = c.get(r[key], 0) + 1
        return c

    print(f"  行数            : {len(rows):,}（1行 = 1コマ × 1教室）", file=out)
    print(f"  年度            : {'/'.join(str(y) for y in sorted(tally('年度')))}", file=out)
    for key in ("区分", "履修期名", "校舎"):
        items = sorted(tally(key).items(), key=lambda kv: -kv[1])
        print(f"  {key:<15}: " + " / ".join(f"{k} {v:,}" for k, v in items), file=out)
    print(f"  学科            : {len(tally('学科'))} 種", file=out)
    print(f"  教室            : {len(tally('教室'))} 種", file=out)
    print(f"  科目名          : {len(tally('科目名'))} 種", file=out)
    teachers = {t for r in rows for t in (r["教員名"],) if t}
    print(f"  教員名（原本の表記のまま）: {len(teachers)} 種", file=out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="授業の生データを CSV にまとめる")
    ap.add_argument("--src", default=str(REPO / "data" / "source"), help="原本のフォルダ")
    ap.add_argument("--out", default=None, help="出力先 CSV（既定 data/classes_<年度>.csv）")
    ap.add_argument("--divisions", default=None,
                    help="区分番号をカンマ区切りで絞る（1=理工学部 2=短期大学部 3=博士前期 4=博士後期）")
    ap.add_argument("--stdout", action="store_true", help="ファイルに書かず画面に出す")
    args = ap.parse_args(argv)

    divisions = None
    if args.divisions is not None:
        divisions = {d.strip() for d in args.divisions.split(",") if d.strip()}
        if not divisions or any(not d.isdigit() for d in divisions):
            print(f"--divisions の指定が不正です: {args.divisions!r}"
                  f"（1〜9 の区分番号をカンマ区切りで。例: 1,3,4）", file=sys.stderr)
            return 1

    stats = bsd.Stats()
    try:
        rows = collect(Path(args.src), divisions, stats)
    except bsd.SourceError as exc:
        print("原本の読み取りに失敗しました。CSV は作っていません。", file=sys.stderr)
        print(f"  {exc}", file=sys.stderr)
        return 1

    if not rows:
        print("原本から 1 行も取れませんでした。列見出しや曜日ブロックの想定が崩れている可能性があります。",
              file=sys.stderr)
        return 1

    if args.stdout:
        w = csv.DictWriter(sys.stdout, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
        return 0

    years = sorted({r["年度"] for r in rows})
    out_path = Path(args.out) if args.out else REPO / "data" / f"classes_{years[0]}.csv"
    if len(years) > 1:
        print(f"※ 年度が混ざっています: {years}。意図した組み合わせか確認してください")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Excel で開いたときに文字化けしないよう BOM 付き UTF-8
    with out_path.open("w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f"書き出しました: {out_path}（{out_path.stat().st_size:,} bytes）")
    summarize(rows, sys.stdout)
    if stats.warnings:
        print(f"\n  ※ 読み取り時の警告 {len(stats.warnings)} 件"
              f"（内訳は scripts/build_schedule_db.py --report で確認できます）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
