#!/usr/bin/env python3
"""
時間割の原本ファイルの構造を報告する。

`data/source/timetables/` に置かれた原本（学科ごとの時間割）が、どんな形をしているかを
実際に読んで調べるための道具。schedule_final.db の再現スクリプトを書く前に、
まずこれで形式を確認する（docs/OPERATIONS.md 6. 参照）。

対応形式: .xlsx / .xlsm / .xls / .csv / .tsv / .pdf / .html
未知の形式や壊れたファイルでも、そのことを報告して次のファイルへ進む。

使い方:
  python scripts/inspect_timetable.py data/source/timetables/2026/        # フォルダごと
  python scripts/inspect_timetable.py data/source/timetables/2026/1-01.xlsx
  python scripts/inspect_timetable.py <path> --rows 25                    # 表示行数を増やす
  python scripts/inspect_timetable.py <path> --full                       # 全シート・全列を表示
"""
import argparse
import sys
from pathlib import Path

# 時間割ファイルらしさを判定するための手がかり
HINT_WORDS = {
    "曜日": ["曜日", "曜", "day"],
    "時限": ["時限", "時間", "限", "period", "コマ"],
    "教室": ["教室", "講義室", "室", "room", "会場"],
    "科目": ["科目", "授業", "講義", "subject", "course"],
    "学科": ["学科", "専攻", "コース", "学年"],
    "学期": ["履修期", "学期", "前期", "後期", "通年", "term"],
    "時間割CD": ["時間割", "コード", "cd", "code"],
}
SUPPORTED = {".xlsx", ".xlsm", ".xls", ".csv", ".tsv", ".pdf", ".html", ".htm"}


def classify(text):
    """セル・列名に含まれる手がかり語を返す"""
    t = str(text).lower()
    return [label for label, words in HINT_WORDS.items() if any(w.lower() in t for w in words)]


def show_frame(df, rows, full, indent="    "):
    import pandas as pd
    with pd.option_context("display.max_columns", None if full else 20,
                           "display.width", 200, "display.max_colwidth", 16):
        print(indent + df.head(rows).to_string().replace("\n", "\n" + indent))


def guess_header_row(df, limit=12):
    """ヘッダーが先頭行にないことが多いので、手がかり語が一番多い行を探す"""
    best, best_n = None, 0
    for i in range(min(limit, len(df))):
        n = len({lab for v in df.iloc[i] for lab in classify(v)})
        if n > best_n:
            best, best_n = i, n
    return best, best_n


def inspect_excel(path, rows, full):
    import pandas as pd
    xl = pd.ExcelFile(path)
    print(f"  形式: Excel / シート {len(xl.sheet_names)}個: {xl.sheet_names}")
    sheets = xl.sheet_names if full else xl.sheet_names[:3]
    for sh in sheets:
        raw = xl.parse(sh, header=None)
        print(f"\n  ── シート「{sh}」 {raw.shape[0]}行 x {raw.shape[1]}列")
        if raw.empty:
            print("    （空）")
            continue
        hdr, n = guess_header_row(raw)
        if hdr is not None:
            labels = sorted({lab for v in raw.iloc[hdr] for lab in classify(v)})
            print(f"    ヘッダーらしき行: {hdr}行目（手がかり: {', '.join(labels)}）")
        else:
            print("    ヘッダーらしき行: 見つからない（表が縦横に展開された時間割の可能性）")
        show_frame(raw, rows, full)
    if not full and len(xl.sheet_names) > 3:
        print(f"\n  （残り {len(xl.sheet_names) - 3} シートは省略。--full で全部表示）")


def inspect_text_table(path, rows, full):
    import pandas as pd
    sep = "\t" if path.suffix.lower() == ".tsv" else ","
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            df = pd.read_csv(path, sep=sep, header=None, encoding=enc, dtype=str,
                             on_bad_lines="skip")
            print(f"  形式: 区切りテキスト / エンコーディング {enc} / {df.shape[0]}行 x {df.shape[1]}列")
            hdr, _ = guess_header_row(df)
            if hdr is not None:
                labels = sorted({lab for v in df.iloc[hdr] for lab in classify(v)})
                print(f"    ヘッダーらしき行: {hdr}行目（手がかり: {', '.join(labels)}）")
            show_frame(df, rows, full)
            return
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"  読めない: {type(e).__name__}: {e}")
            return
    print("  読めない: 文字コードを判定できなかった（utf-8 / cp932 のいずれでもない）")


def inspect_pdf(path, rows, full):
    try:
        import fitz  # pymupdf
    except ImportError:
        print("  形式: PDF — 解析には pymupdf が必要: pip install pymupdf")
        return
    doc = fitz.open(path)
    print(f"  形式: PDF / {doc.page_count}ページ")
    pages = range(doc.page_count) if full else range(min(2, doc.page_count))
    for i in pages:
        text = doc[i].get_text()
        labels = sorted({lab for lab in classify(text)})
        print(f"\n  ── {i + 1}ページ（手がかり: {', '.join(labels) or 'なし'}）")
        for line in text.splitlines()[:rows]:
            if line.strip():
                print("    " + line[:160])
        tables = doc[i].find_tables()
        print(f"    表として検出: {len(tables.tables)}個")
    doc.close()


def inspect_html(path, rows, full):
    import pandas as pd
    try:
        tables = pd.read_html(path)
    except Exception as e:
        print(f"  形式: HTML — 表を抽出できない: {type(e).__name__}: {e}")
        return
    print(f"  形式: HTML / 表 {len(tables)}個")
    for i, df in enumerate(tables if full else tables[:3]):
        print(f"\n  ── 表 {i} {df.shape[0]}行 x {df.shape[1]}列")
        show_frame(df, rows, full)


def inspect(path, rows, full):
    print(f"\n{'=' * 70}\n{path}  ({path.stat().st_size:,} bytes)")
    suffix = path.suffix.lower()
    try:
        if suffix in (".xlsx", ".xlsm", ".xls"):
            inspect_excel(path, rows, full)
        elif suffix in (".csv", ".tsv"):
            inspect_text_table(path, rows, full)
        elif suffix == ".pdf":
            inspect_pdf(path, rows, full)
        elif suffix in (".html", ".htm"):
            inspect_html(path, rows, full)
        else:
            print(f"  未対応の形式: {suffix}（対応: {', '.join(sorted(SUPPORTED))}）")
    except Exception as e:
        print(f"  解析に失敗: {type(e).__name__}: {e}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="時間割の原本ファイルの構造を報告する")
    ap.add_argument("path", help="ファイル、またはファイルを含むフォルダ")
    ap.add_argument("--rows", type=int, default=12, help="表示する行数（既定 12）")
    ap.add_argument("--full", action="store_true", help="全シート・全列・全ページを表示")
    args = ap.parse_args(argv)

    root = Path(args.path)
    if not root.exists():
        print(f"[ERROR] 見つかりません: {root}", file=sys.stderr)
        return 2

    if root.is_dir():
        found = [p for p in sorted(root.rglob("*")) if p.is_file() and p.name != "README.md"]
        files = [p for p in found if p.suffix.lower() in SUPPORTED]
        skipped = [p for p in found if p.suffix.lower() not in SUPPORTED]
        if skipped:
            # 黙って飛ばすと「全部見た」と誤解されるので必ず知らせる
            print(f"[WARN] 未対応の形式のため飛ばしたファイル {len(skipped)}件: "
                  + ", ".join(p.name for p in skipped[:10])
                  + (" …" if len(skipped) > 10 else "")
                  + f"\n       対応形式: {', '.join(sorted(SUPPORTED))}")
        if not files:
            print(f"[INFO] {root} に解析できるファイルがありません。"
                  f"\n       原本の置き方は data/source/timetables/README.md を参照。")
            return 0
        print(f"[INFO] {len(files)} ファイルを解析します")
    else:
        files = [root]

    for f in files:
        inspect(f, args.rows, args.full)

    print(f"\n{'=' * 70}\n[INFO] {len(files)} ファイルを解析しました。"
          f"\n       この出力を見て scripts/build_schedule_db.py を書きます。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
