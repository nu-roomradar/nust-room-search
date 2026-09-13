#!/usr/bin/env python3
"""
時間割の原本（.xls）から schedule_final.db を組み立て直す。

背景: schedule_final.db は手作業で作られ、作成スクリプトが失われていた
（docs/OPERATIONS.md 6.）。原本が無いと翌年度の時間割を入れられないため、
2026年度（令和8年度）の原本を突き合わせて変換規則を復元し、スクリプト化したもの。
2026年度の原本からは現行 DB の 13,614 行を 7 列すべて完全に再現できる。

────────────────────────────────────────────────────────────────────────
原本の構造
────────────────────────────────────────────────────────────────────────
data/source/ に置かれた `<区分番号>_<区分名>_<学科番号>_<学科名>[_<コース>]_<年>年_時間割表N面_<timestamp>.xls`。
  区分番号 1=理工学部 / 2=短期大学部 / 3=博士前期 / 4=博士後期
  （2026年度は 16+3+15+15=49 ファイル）

短期大学部は船橋校舎を理工学部と共用している。短大の授業が入っている教室を「空き」と
出さないよう schedules には取り込むが、**教室マスタ（＝検索結果に出る教室の一覧）は
理工学部・大学院からだけ作る**。RoomRadar は理工学部の学生向けで、短大専用教室を
「空いています」と出しても行って使えるとは限らないため、安全側に倒している。
`--divisions 1,3,4` で短大を外すと、現行 schedule_final.db を全 7 列・13,614 行で完全再現する。
各ファイルはシート「前期」「後期」の 2 枚。中身は曜日×時限のグリッド（人が読む時間割表）。
  行1(0始まり)  B列に「2026年度」
  行2           B列に「理工学部 土木工学科」（大学院は「博士前期 土木工学専攻」）
  行4           曜日ラベル 月火水木金土
  行5           曜日ブロックごとの列見出し（時間割CD / 科目名 / 単位 / 対象学年 / 教員名 / 校舎 / 教室名）
  行6以降       データ
曜日ブロックの開始列 c0 からのオフセットは 時間割CD=+0, 科目名=+2, 単位=+3, 対象学年=+4,
教員名=+5, 校舎=+6, 教室名=+7。2026年度の実測では 月=2 火=10 水=18 木=35 金=43 土=51 だが、
年度で変わりうるので行4の曜日ラベルから毎回探す（列番号は決め打ちしない）。
時限ラベル（「1時限目」）はその時限の先頭行にだけ入るので前方補完する。ラベル列は
左半分（月火水）と右半分（木金土）で違う（2026年度は 列1 と 列34）ので、
「時限ラベルが実際に現れた列のうち、そのブロックの開始列より左で最も近い列」を使う。

────────────────────────────────────────────────────────────────────────
変換規則（2026年度の原本と現行 DB を突き合わせて確定したもの）
────────────────────────────────────────────────────────────────────────
[学科]   ファイル単位の定数。行2のセル（例「理工学部 土木工学科」）から区分と
         末尾の「(…コース)」を除いたもの。区分（学部/博士前期/博士後期）は DB に残らず、
         博士前期と博士後期の同名専攻は同じ「○○専攻」に単純連結される。
         ※ファイル名は NFD（macOS 書き出し）なので、そちらから取る場合は必ず NFC 正規化する
           （「まちづくり」が つ+濁点 になっていて DB と一致しない）。
[行の採否] 時間割CD と 科目名 がどちらも空の行は読み飛ばす。それ以外は教室名セルを採用。
[科目名] 原本の値をそのまま使う（注記込み。1,869 種すべて DB と一致）。
[教室名] 教室名セルは複数教室を含みうる。半角/全角スペースで分割する。ただし
         半角カッコ (...) の内側では分割しない。全角カッコ（）は保護しない
         （現行 DB が「スタジオ（S701」「S705）」という壊れ方で登録されており、
          素朴に分割されたことが確定しているため。下の「既知の未解決」参照）。
         分割した各トークンを次の優先順で正規化する。教室番号 = ^[A-Za-z]?\\d{3,4}$
           規則B  X(Y) で Y を分割した要素がすべて教室番号 → X を捨て Y を展開
                  例: 8号館実験室(819 826 829) → 819, 826, 829
           規則A  X(Y) で X が教室番号 → X だけ採用し (Y) は捨てる
                  例: 1201(PC演習室) → 1201 / S407(ｻﾃﾗｲﾄ時の主な相手:F1451) → S407
           規則C  上に当たらなければ無加工（階段教室(大) 等はこの綴りで DB に載っている）
         中黒「・」は教室名の一部なので分割しない（テクノ・工作技術センター）。
[教室 000/0000] "000"（教室未定）は捨てる。"0000" は schedules には残すが classrooms には入れない。
[例外表] 規則では説明できず、DB 作成者が黙って捨てた 2 トークンだけを破棄する
         （EXCEPTION_DROP。件数と理由は必ずレポートに出す）。
[校舎]   校舎列 F → 船橋校舎 ／ S かつ教室名が "S" 始まり → タワースコラ ／ S かつそれ以外 → 駿河台校舎。
         例外: 「まち製図室１～５」は S 始まりでないのにタワースコラにあり、DB では
         同じセルの先頭教室の校舎を引き継いでいる（BUILDING_INHERIT_ROOMS）。
[classrooms] schedules に出た教室名から作る（"0000" は除く）。building はその教室が
         schedules で最も多く取った校舎（最頻値）。

────────────────────────────────────────────────────────────────────────
既知の未解決（翌年度に向けて）
────────────────────────────────────────────────────────────────────────
* 例外表の 2 件は一般規則に還元できない。規則A〜Cのどれにも当たらずカッコを含んだまま
  採用したトークンは「要目視」として警告に出すので、翌年度は必ず目を通すこと。
* 全角カッコを保護しないのは現行 DB の壊れたデータ（スタジオ（S701 / S702 / S705））に
  合わせるため。本来は S701/S702/S705 の 3 教室。直すなら app.py と classrooms の整理も要る。
* 教室 134/143/144 は原本の校舎列で F と S の両方に現れる（原本側の品質問題の可能性）。
* 「まち製図室１～５」は現行 DB 内で 駿河台校舎4行 / タワースコラ7行 に割れている。
  上の継承規則はそれを再現するもので、classrooms（タワースコラ）とは 4 行食い違う。

────────────────────────────────────────────────────────────────────────
使い方
────────────────────────────────────────────────────────────────────────
  python scripts/build_schedule_db.py                      # schedule_final.new.db を作る
  python scripts/build_schedule_db.py --report             # 作った上で現行 DB との差分を出す
  python scripts/build_schedule_db.py --report --no-write  # 差分だけ見る（DB を書かない）
  python scripts/build_schedule_db.py --replace            # 本番を置き換える（.bak を残す）
  python scripts/build_schedule_db.py --src data/source/2027 --out /tmp/2027.db --report
既定では現行 schedule_final.db を絶対に上書きしない。--replace を付けたときだけ置き換える。
異常（入力が無い・シートが違う・列見出しが違う）は日本語で述べて終了コード 1 で止まる。
"""
import argparse
import collections
import os
import re
import shutil
import sqlite3
import sys
import unicodedata
from pathlib import Path

import xlrd

REPO = Path(__file__).resolve().parents[1]
DEFAULT_SRC = REPO / "data" / "source"
DEFAULT_REF = REPO / "schedule_final.db"
DEFAULT_OUT = REPO / "schedule_final.new.db"

# 原本ファイル名: <区分番号>_<区分名>_<学科番号>_<学科名>[_<コース>]_<年>年_時間割表N面_<timestamp>.xls
SRC_GLOB = "[0-9]_*.xls"
FILENAME_YEAR = re.compile(r"^(\d{4})年$")
SHEETS = ("前期", "後期")
DAYS = ("月", "火", "水", "木", "金", "土")
PERIOD_LABEL = re.compile(r"^(\d+)時限目")
SHEET_YEAR = re.compile(r"(\d{4})年度")

# 行5の列見出し（空白を除いて比較）→ 曜日ブロック開始列からのオフセット
COLUMN_OFFSETS = {"時間割CD": 0, "科目名": 2, "単位": 3, "対象学年": 4, "教員名": 5, "校舎": 6, "教室名": 7}
HEADER_ROW = 5          # 列見出しの行（0始まり）
DATA_ROW = 6            # データ開始行
TITLE_ROW = 1           # 「2026年度」がある行
DEPT_ROW, DEPT_COL = 2, 1   # 「理工学部 土木工学科」があるセル

ROOM_CODE = re.compile(r"^[A-Za-z]?\d{3,4}$")     # 641 / 819 / 1425 / S407
PAREN = re.compile(r"^([^()]*)\(([^()]*)\)$")     # 半角カッコのみ。全角は対象外
SPACES = re.compile(r"[ 　]+")

ROOM_UNDECIDED = "000"      # 教室未定。DB には入っていない
ROOM_PLACEHOLDER = "0000"   # schedules には残るが classrooms には入れない

# 規則A〜Cのどれでも説明できず、DB 作成者が黙って捨てたトークン。
# ここに足すのは「原本と DB を突き合わせて捨てられていると確認できた」ときだけにすること。
EXCEPTION_DROP = {
    "14製図室(1425～1429)": "範囲表記の注記。同じセルの 1325 だけが DB にある（1425〜1429 は展開されていない）",
    "階段(小)": "「階段教室(小)」の略記ゆれ。同じコマの DB 行は 1201/1202/1204 のみ",
    "他": "短期大学部の原本にある「他」。教室名ではないので捨てる",
}

# 短期大学部の区分番号。船橋校舎を理工学部と共用しているため占有判定には入れるが、
# 教室マスタ（＝検索結果に出る教室）は理工学部・大学院からだけ作る。
# RoomRadar は理工学部の学生向けで、短大専用教室を「空いています」と出しても
# 行って使えるとは限らないため、安全側に倒している。
TANDAI_DIVISION = "2"
TANDAI_PREFIX = "短大 "     # 学科名に付ける印（「一般教育」が理工と衝突するため）

# 中黒「・」の扱いは原本によって逆。理工では「テクノ・工作技術センター」という
# 1 つの教室名の一部なので割ってはいけない。短大では「1111・521」のように
# 教室番号の区切りとして使う。両側がどちらも教室コードの形のときだけ割る。
MIDDLE_DOTS = "・･"

# S 始まりでないのにタワースコラにある教室。DB では同じセルの先頭教室の校舎を引き継いでいる
BUILDING_INHERIT_ROOMS = {"まち製図室１～５"}
BUILDING_ORDER = ("タワースコラ", "駿河台校舎", "船橋校舎")

SCHEMA = """
CREATE TABLE schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    学科 TEXT, 履修期名 TEXT, 曜日 TEXT,
    時限 INTEGER, 教室 TEXT, 校舎 TEXT, 科目名 TEXT
);
CREATE TABLE classrooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE, building TEXT
);
CREATE INDEX idx_schedules ON schedules (曜日, 時限, 履修期名);
CREATE INDEX idx_classrooms ON classrooms (building);
"""


class SourceError(Exception):
    """原本が想定と違う。握りつぶさずここまで投げて、日本語で述べて止まる"""


# ------------------------------------------------------------------ 集計・警告

class Stats:
    """何をどれだけ捨て／変換したか。--report で全部出す（黙って落とさないため）"""

    def __init__(self):
        self.files = 0
        self.sheets = 0
        self.room_cells = 0        # 非空の教室名セル
        self.tokens = 0            # 分割直後のトークン数
        self.rows = 0              # schedules に入れた行数
        self.dropped_undecided = 0                  # "000"
        self.dropped_exception = collections.Counter()
        self.rule_a = collections.Counter()         # X(Y) → X
        self.rule_b = collections.Counter()         # X(Y) → Y を展開
        self.paren_kept = collections.Counter()     # 規則C だがカッコ付き = 要目視
        self.building_inherited = collections.Counter()
        self.tandai_rows = 0       # 短期大学部由来の行（教室マスタには入れない）
        self.warnings = []

    def warn(self, msg):
        self.warnings.append(msg)


# ------------------------------------------------------------------ 原本を読む

def cell_text(sheet, row, col):
    """セルを文字列で取る。数値セルは整数なら小数点を付けない"""
    if col >= sheet.ncols or row >= sheet.nrows:
        return ""
    v = sheet.cell_value(row, col)
    if isinstance(v, float):
        return str(int(v)) if v == int(v) else str(v)
    return str(v).strip()


def squeeze(s):
    """列見出し比較用。改行や空白を落とす（見出しは「時間割\\nCD」のように折り返されている）"""
    return re.sub(r"\s", "", str(s))


def parse_filename(path):
    """ファイル名から 区分番号 / 区分名 / 学科番号 / 学科名 / 年度 を取る（NFC 正規化込み）"""
    name = unicodedata.normalize("NFC", path.name)
    parts = name.split("_")
    if len(parts) < 6:
        raise SourceError(f"{path.name}: ファイル名の形が想定と違います"
                          f"（<区分番号>_<区分名>_<学科番号>_<学科名>_…_<年>年_時間割表N面_… を期待）")
    year = None
    for p in parts[4:]:
        m = FILENAME_YEAR.match(p)
        if m:
            year = int(m.group(1))
            break
    if year is None:
        raise SourceError(f"{path.name}: ファイル名に年度（「2026年」の形）が見つかりません")
    return {"division_no": parts[0], "division": parts[1], "dept_no": parts[2],
            "dept": parts[3], "year": year, "filename": name}


def find_blocks(sheet, where):
    """行4の曜日ラベルから曜日ブロックを見つけ、列見出しとオフセットを検証して返す

    戻り値: [(曜日, 開始列, 時限ラベル列), ...]（列の昇順 = 月火水木金土）

    時限ラベル列は左半分（月火水）と右半分（木金土）で違うので、曜日ブロックを
    「列が連続している塊」に分け、塊ごとにその直前にあるラベル列を割り当てる。
    列1だけを使うと木金土の時限がずれる（実測で確認済み）ため、塊ごとに必須とする。
    """
    day_cols = [(c, cell_text(sheet, 4, c)) for c in range(sheet.ncols)
                if cell_text(sheet, 4, c) in DAYS]
    seen = [v for _, v in day_cols]
    if seen != list(DAYS):
        raise SourceError(f"{where}: 行4の曜日ラベルが想定と違います（見つかったのは {seen or 'なし'}。"
                          f"月火水木金土 が左から順に並んでいることを期待）")

    # 列見出しが想定通りか（ここが崩れていると全部ずれる）
    for c0, day in day_cols:
        for label, off in COLUMN_OFFSETS.items():
            got = squeeze(cell_text(sheet, HEADER_ROW, c0 + off))
            if got != label:
                raise SourceError(
                    f"{where}: {day}曜ブロック（開始列 {c0}）の列見出しが想定と違います。"
                    f"列 {c0 + off} は「{label}」のはずですが「{got or '空'}」でした")

    # 時限ラベル（「1時限目」）が実際に現れる列
    label_cols = sorted({c for r in range(DATA_ROW, sheet.nrows) for c in range(sheet.ncols)
                         if PERIOD_LABEL.match(cell_text(sheet, r, c))})
    if not label_cols:
        raise SourceError(f"{where}: 「N時限目」の時限ラベルが 1 つも見つかりません")

    width = max(COLUMN_OFFSETS.values()) + 1      # 曜日ブロック 1 つ分の列幅
    groups, prev_end = [], None                   # 列が連続している曜日ブロックの塊
    for c0, day in day_cols:
        if prev_end is None or c0 > prev_end:
            groups.append([])
        groups[-1].append((c0, day))
        prev_end = c0 + width

    blocks, window_start = [], 0
    for group in groups:
        group_start = group[0][0]
        found = [c for c in label_cols if window_start <= c < group_start]
        if not found:
            names = "".join(d for _, d in group)
            raise SourceError(
                f"{where}: {names}曜のブロック（開始列 {group_start}）に対応する時限ラベル列が"
                f"列 {window_start}〜{group_start - 1} に見つかりません"
                f"（「N時限目」が見つかったのは列 {label_cols}）")
        label_col = max(found)
        blocks.extend((day, c0, label_col) for c0, day in group)
        window_start = group[-1][0] + width
    return blocks


def sheet_year(sheet):
    """シートの行1から年度を読む。読めなければ None"""
    for c in range(min(sheet.ncols, 8)):
        m = SHEET_YEAR.search(cell_text(sheet, TITLE_ROW, c))
        if m:
            return int(m.group(1))
    return None


def sheet_dept(sheet):
    """行2のセル（例「理工学部 土木工学科」）から学科名を取る。区分と (…コース) を落とす"""
    raw = unicodedata.normalize("NFC", cell_text(sheet, DEPT_ROW, DEPT_COL))
    if not raw:
        return None
    body = raw.split(" ", 1)[1] if " " in raw else raw
    body = re.sub(r"[(（][^()（）]*[)）]\s*$", "", body).strip()
    return body or None


def read_workbook(path, meta, stats):
    """1 ファイルを読んでセル単位のレコードにする（教室名セルが非空のものだけ）"""
    try:
        book = xlrd.open_workbook(str(path))
    except Exception as exc:  # 壊れたファイルもここで日本語にして止める
        raise SourceError(f"{path.name}: Excel として読めません（{exc}）") from exc

    missing = [s for s in SHEETS if s not in book.sheet_names()]
    if missing:
        raise SourceError(f"{path.name}: シート「{'」「'.join(missing)}」がありません"
                          f"（あるのは {book.sheet_names()}）")

    records = []
    for sheet_name in SHEETS:
        sheet = book.sheet_by_name(sheet_name)
        where = f"{path.name} / シート「{sheet_name}」"
        blocks = find_blocks(sheet, where)
        stats.sheets += 1

        year = sheet_year(sheet)
        if year is not None and year != meta["year"]:
            stats.warn(f"{where}: ファイル名の年度({meta['year']})とシートの年度({year})が違います")
        dept = sheet_dept(sheet)
        if dept is None:
            stats.warn(f"{where}: 行2から学科名を読めませんでした。ファイル名の「{meta['dept']}」を使います")
            dept = meta["dept"]
        elif dept != meta["dept"]:
            stats.warn(f"{where}: ファイル名の学科「{meta['dept']}」とシートの学科「{dept}」が違います。"
                       f"シート側を採用します")
        if meta["division_no"] == TANDAI_DIVISION:
            # 短大の「一般教育」は理工の「一般教育」と名前が衝突する。
            # 学科列は検索に使わないので実害は無いが、後から見て区別できるように印を付ける
            dept = f"{TANDAI_PREFIX}{dept}"

        for day, c0, label_col in blocks:
            period = None
            for r in range(DATA_ROW, sheet.nrows):
                m = PERIOD_LABEL.match(cell_text(sheet, r, label_col))
                if m:
                    period = int(m.group(1))      # 時限は先頭行にだけ入るので前方補完
                code = cell_text(sheet, r, c0 + COLUMN_OFFSETS["時間割CD"])
                subject = cell_text(sheet, r, c0 + COLUMN_OFFSETS["科目名"])
                if not code and not subject:
                    continue                       # 授業の無い行
                room_raw = cell_text(sheet, r, c0 + COLUMN_OFFSETS["教室名"])
                if not room_raw:
                    continue
                if period is None:
                    stats.warn(f"{where}: {day}曜 行{r} に時限ラベルより前の授業があります"
                               f"（科目「{subject}」）。読み飛ばしました")
                    continue
                records.append({
                    "dept": dept, "term": sheet_name, "day": day, "period": period,
                    "subject": subject, "room_raw": room_raw,
                    "building_col": cell_text(sheet, r, c0 + COLUMN_OFFSETS["校舎"]),
                    "source": f"{path.name} / {sheet_name} / {day}曜 行{r}",
                })
    return records


def collect_sources(src_dir, divisions=None):
    """原本ファイルを DB の登録順（区分番号 → 学科番号 → ファイル名）に並べて返す

    divisions に区分番号の集合を渡すとその区分だけ読む（例 {"1","3","4"} で理工＋大学院のみ）。
    """
    if not src_dir.is_dir():
        raise SourceError(f"原本のフォルダがありません: {src_dir}")
    paths = sorted(src_dir.glob(SRC_GLOB))
    if divisions:
        paths = [p for p in paths
                 if unicodedata.normalize("NFC", p.name).split("_", 1)[0] in divisions]
        if not paths:
            raise SourceError(f"--divisions {','.join(sorted(divisions))} に合う原本がありません: {src_dir}")
    if not paths:
        raise SourceError(
            f"原本が 1 つも見つかりません: {src_dir}/{SRC_GLOB}\n"
            f"  期待するファイル名: 1_理工学部_01_土木工学科_0_2026年_時間割表1面_<timestamp>.xls\n"
            f"  （同じフォルダの 1-01.xlsx や classroom_data.xlsx は別形式・集計結果なので使いません）")
    metas = [(parse_filename(p), p) for p in paths]
    metas.sort(key=lambda mp: (mp[0]["division_no"], mp[0]["dept_no"], mp[0]["filename"]))
    return metas


# ------------------------------------------------------------------ 教室名の正規化

def tokenize_rooms(cell):
    """教室名セルを教室トークンに割る。半角カッコの内側では割らない（全角カッコは保護しない）"""
    out, buf, depth = [], "", 0
    for ch in cell:
        if ch == "(":
            depth += 1
            buf += ch
        elif ch == ")":
            depth = max(0, depth - 1)
            buf += ch
        elif ch in " 　" and depth == 0:
            if buf:
                out.append(buf)
                buf = ""
        else:
            buf += ch
    if buf:
        out.append(buf)
    return [p for t in out for p in split_middle_dot(t)]


def split_middle_dot(token):
    """中黒で割るのは、割った結果が全部教室コードの形のときだけ

    「1111・521」→ ["1111", "521"]（短大の原本。どちらも実在する理工の教室）
    「テクノ・工作技術センター」→ そのまま（理工の教室名。割ると壊れる）
    """
    if not any(d in token for d in MIDDLE_DOTS):
        return [token]
    parts = [p for p in re.split(f"[{MIDDLE_DOTS}]", token) if p]
    if len(parts) > 1 and all(ROOM_CODE.match(p) for p in parts):
        return parts
    return [token]


def normalize_rooms(cell, stats, where):
    """教室名セル → 教室名のリスト。捨てたもの・変換したものは stats に記録する"""
    rooms = []
    for token in tokenize_rooms(cell):
        stats.tokens += 1
        if token == ROOM_UNDECIDED:
            stats.dropped_undecided += 1          # 教室未定
            continue
        if token in EXCEPTION_DROP:
            stats.dropped_exception[token] += 1   # 例外表（理由つきでレポートに出す）
            continue
        m = PAREN.match(token)
        if not m:
            rooms.append(token)
            continue
        head, inner = m.group(1), m.group(2)
        parts = [p for p in SPACES.split(inner) if p]
        if parts and all(ROOM_CODE.match(p) for p in parts):
            stats.rule_b[token] += 1              # 規則B: 括弧内が教室番号の並び → 展開
            rooms.extend(parts)
        elif ROOM_CODE.match(head):
            stats.rule_a[token] += 1              # 規則A: 括弧内は説明書き → 落とす
            rooms.append(head)
        else:
            stats.paren_kept[token] += 1          # 規則C: カッコごと教室名。要目視
            rooms.append(token)
    return rooms


def plain_building(room, building_col, stats, where):
    """校舎列（F/S）と教室名から校舎を決める"""
    col = (building_col or "").strip().upper()
    if col == "F":
        return "船橋校舎"
    if col == "S":
        return "タワースコラ" if room.startswith("S") else "駿河台校舎"
    stats.warn(f"{where}: 校舎列の値が F/S ではありません（「{building_col or '空'}」）。駿河台校舎として扱います")
    return "駿河台校舎"


def resolve_buildings(rooms, building_col, stats, where):
    """セル内の各教室の校舎を決める。BUILDING_INHERIT_ROOMS だけ先頭教室の校舎を引き継ぐ"""
    out, first = [], None
    for i, room in enumerate(rooms):
        building = plain_building(room, building_col, stats, where)
        if i == 0:
            first = building
        elif room in BUILDING_INHERIT_ROOMS:
            if building != first:
                stats.building_inherited[f"{room} → {first}"] += 1
            building = first
        if i == 0 and room in BUILDING_INHERIT_ROOMS:
            stats.warn(f"{where}: 「{room}」がセルの先頭にあり、引き継ぐ校舎がありません"
                       f"（{building} として扱います）")
        out.append(building)
    return out


# ------------------------------------------------------------------ 組み立て

def build_rows(metas, stats):
    """原本 → schedules の行（DB の登録順）

    戻り値は (全行, 教室マスタ用の行)。後者は短期大学部を除いたもので、
    短大が使っている教室は占有として残しつつ、検索対象の教室一覧は増やさない。
    """
    rows, master_rows = [], []
    for meta, path in metas:
        stats.files += 1
        is_tandai = meta["division_no"] == TANDAI_DIVISION
        for rec in read_workbook(path, meta, stats):
            stats.room_cells += 1
            rooms = normalize_rooms(rec["room_raw"], stats, rec["source"])
            buildings = resolve_buildings(rooms, rec["building_col"], stats, rec["source"])
            for room, building in zip(rooms, buildings):
                row = (rec["dept"], rec["term"], rec["day"], rec["period"],
                       room, building, rec["subject"])
                rows.append(row)
                if is_tandai:
                    stats.tandai_rows += 1
                else:
                    master_rows.append(row)
    stats.rows = len(rows)
    return rows, master_rows


def build_classrooms(rows, stats):
    """schedules の行から教室マスタを作る。building は最頻値、並びは初出順"""
    seen, counts = [], collections.defaultdict(collections.Counter)
    for _, _, _, _, room, building, _ in rows:
        if room == ROOM_PLACEHOLDER:      # 教室未定の仮名。マスタには入れない
            continue
        if room not in counts:
            seen.append(room)
        counts[room][building] += 1
    out = []
    for room in seen:
        tally = counts[room]
        building = sorted(tally.items(),
                          key=lambda kv: (-kv[1], BUILDING_ORDER.index(kv[0])
                                          if kv[0] in BUILDING_ORDER else len(BUILDING_ORDER)))[0][0]
        if len(tally) > 1:
            detail = " / ".join(f"{b}{n}行" for b, n in tally.most_common())
            stats.warn(f"教室「{room}」の校舎が schedules 内で割れています（{detail}）。"
                       f"マスタは最頻値の {building} にしました")
        out.append((room, building))
    return out


def write_db(path, rows, classrooms):
    """スキーマは現行 schedule_final.db と同一（列名・型・インデックス）"""
    path = Path(path)
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    try:
        con.executescript(SCHEMA)
        con.executemany(
            "INSERT INTO schedules (学科, 履修期名, 曜日, 時限, 教室, 校舎, 科目名) VALUES (?,?,?,?,?,?,?)", rows)
        con.executemany("INSERT INTO classrooms (name, building) VALUES (?,?)", classrooms)
        con.commit()
    finally:
        con.close()


def replace_db(new_path, target):
    """本番 DB を置き換える。置き換え前に .bak を作る"""
    target = Path(target)
    backup = None
    if target.exists():
        backup = target.with_suffix(target.suffix + ".bak")
        shutil.copy2(target, backup)
    shutil.copy2(new_path, target)
    return backup


# ------------------------------------------------------------------ レポート

def read_ref(ref_path):
    """現行 DB を読み取り専用で開いて中身を返す（絶対に書き換えない）"""
    con = sqlite3.connect(f"file:{ref_path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT 学科, 履修期名, 曜日, 時限, 教室, 校舎, 科目名 FROM schedules").fetchall()
        rooms = con.execute("SELECT name, building FROM classrooms").fetchall()
    finally:
        con.close()
    return rows, rooms


def section(title):
    print()
    print(title)
    print("-" * 68)


def report_build(stats):
    """何を読んで何を捨てたか。再現できなかった分は件数と理由を必ず出す"""
    section("■ 読み込み")
    print(f"原本ファイル            : {stats.files} ファイル / {stats.sheets} シート")
    print(f"教室名セル（非空）      : {stats.room_cells:,}")
    print(f"分割後トークン          : {stats.tokens:,}")
    print(f"schedules 行            : {stats.rows:,}")
    if stats.tandai_rows:
        print(f"  うち短期大学部        : {stats.tandai_rows:,}"
              f"（占有判定には入れるが、教室マスタ＝検索対象には加えない）")

    section("■ 再現できなかった分（捨てたトークン）")
    total = stats.dropped_undecided + sum(stats.dropped_exception.values())
    print(f"合計 {total:,} トークンを捨てました。内訳と理由:")
    print(f"  {stats.dropped_undecided:>6,} 件  「{ROOM_UNDECIDED}」= 教室未定。"
          f"現行 DB にも入っていないので欠落ではありません")
    for token, reason in EXCEPTION_DROP.items():
        n = stats.dropped_exception.get(token, 0)
        print(f"  {n:>6,} 件  「{token}」= 例外表。{reason}")
    unused = [t for t in EXCEPTION_DROP if not stats.dropped_exception.get(t)]
    if unused:
        print(f"  ※ 今回の原本に現れなかった例外表の項目: {', '.join(unused)}")

    section("■ 教室名の正規化")
    print(f"規則B（括弧内を展開）  : {sum(stats.rule_b.values()):,} 件 / {len(stats.rule_b)} 種")
    for token, n in sorted(stats.rule_b.items()):
        print(f"    {n:>4} 件  {token}")
    print(f"規則A（括弧を落とす）  : {sum(stats.rule_a.values()):,} 件 / {len(stats.rule_a)} 種")
    for token, n in sorted(stats.rule_a.items()):
        print(f"    {n:>4} 件  {token} → {PAREN.match(token).group(1)}")
    print(f"規則C（カッコ付きのまま採用・要目視）: "
          f"{sum(stats.paren_kept.values()):,} 件 / {len(stats.paren_kept)} 種")
    for token, n in sorted(stats.paren_kept.items()):
        print(f"    {n:>4} 件  {token}")
    if stats.building_inherited:
        print("校舎の継承補正（S 始まりでないタワースコラ教室）:")
        for key, n in sorted(stats.building_inherited.items()):
            print(f"    {n:>4} 件  {key}")


def report_diff(rows, classrooms, ref_path, ref_data=None):
    """現行 DB との差分。行数・学科別一致率・占有スロット・教室マスタ

    ref_data を渡すとそれを比較対象にする（--replace で上書きする前に取った
    スナップショットを渡すため。渡さなければ ref_path を読む）
    """
    ref_rows, ref_rooms = ref_data if ref_data is not None else read_ref(ref_path)
    new_c, ref_c = collections.Counter(rows), collections.Counter(ref_rows)

    section(f"■ 現行 DB との差分（{ref_path}）")
    both = sum((new_c & ref_c).values())
    print(f"行数  新 {len(rows):,} / 現行 {len(ref_rows):,}  （差 {len(rows) - len(ref_rows):+,}）")
    print(f"7列（学科,履修期名,曜日,時限,教室,校舎,科目名）の多重集合一致: "
          f"{both:,} / {len(ref_rows):,}  = {both / max(len(ref_rows), 1) * 100:.2f}%")
    print(f"  原本にだけある行: {sum((new_c - ref_c).values()):,}")
    print(f"  現行DBにだけある行: {sum((ref_c - new_c).values()):,}")

    section("■ 学科別の一致率")
    new_by, ref_by = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for r in rows:
        new_by[r[0]][r] += 1
    for r in ref_rows:
        ref_by[r[0]][r] += 1
    print(f"{'学科':<24}{'新':>8}{'現行':>8}{'一致':>8}{'一致率':>9}")
    bad = 0
    for dept in sorted(set(new_by) | set(ref_by)):
        n, d = new_by[dept], ref_by[dept]
        hit = sum((n & d).values())
        tot_n, tot_d = sum(n.values()), sum(d.values())
        rate = hit / tot_d * 100 if tot_d else (100.0 if not tot_n else 0.0)
        mark = "" if hit == tot_n == tot_d else "  ← 不一致"
        if mark:
            bad += 1
        pad = 24 - sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in dept)
        print(f"{dept}{' ' * max(pad, 1)}{tot_n:>8,}{tot_d:>8,}{hit:>8,}{rate:>8.2f}%{mark}")
    print(f"不一致の学科: {bad} / {len(set(new_by) | set(ref_by))}")

    section("■ 占有スロット（履修期名, 曜日, 時限, 教室）")
    new_slots = {(r[1], r[2], r[3], r[4]) for r in rows}
    ref_slots = {(r[1], r[2], r[3], r[4]) for r in ref_rows}
    print(f"一致        : {len(new_slots & ref_slots):,}")
    print(f"原本にだけ  : {len(new_slots - ref_slots):,}")
    for s in sorted(new_slots - ref_slots)[:20]:
        print(f"    {s}")
    print(f"現行DBにだけ: {len(ref_slots - new_slots):,}")
    for s in sorted(ref_slots - new_slots)[:20]:
        print(f"    {s}")

    section("■ 教室マスタ")
    new_map, ref_map = dict(classrooms), dict(ref_rooms)
    print(f"件数  新 {len(new_map):,} / 現行 {len(ref_map):,}")
    only_new = sorted(set(new_map) - set(ref_map))
    only_ref = sorted(set(ref_map) - set(new_map))
    diff_b = sorted(k for k in set(new_map) & set(ref_map) if new_map[k] != ref_map[k])
    print(f"原本にだけある教室  : {len(only_new)}" + (f"  {only_new}" if only_new else ""))
    print(f"現行DBにだけある教室: {len(only_ref)}" + (f"  {only_ref}" if only_ref else ""))
    print(f"校舎が違う教室      : {len(diff_b)}")
    for k in diff_b:
        print(f"    {k}: 新={new_map[k]} / 現行={ref_map[k]}")
    return len(rows) == len(ref_rows) and both == len(ref_rows)


def report_warnings(stats):
    section("■ 警告（黙って落とさないための一覧）")
    if not stats.warnings:
        print("なし")
        return
    counted = collections.Counter(stats.warnings)
    for msg, n in counted.most_common():
        print(f"  {n:>4} 件  {msg}" if n > 1 else f"         {msg}")


# ------------------------------------------------------------------ CLI

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="時間割の原本(.xls) から schedule_final.db を組み立てる",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=str(DEFAULT_SRC), help=f"原本のフォルダ（既定 {DEFAULT_SRC}）")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help=f"出力先 DB（既定 {DEFAULT_OUT}）")
    ap.add_argument("--ref", default=str(DEFAULT_REF), help=f"比較する現行 DB（既定 {DEFAULT_REF}）")
    ap.add_argument("--replace", action="store_true",
                    help="現行 DB（--ref）を置き換える。置き換え前に .bak を作る")
    ap.add_argument("--report", action="store_true", help="現行 DB との差分を出す")
    ap.add_argument("--no-write", action="store_true", help="DB を書かない（--report と組み合わせて確認だけ）")
    ap.add_argument("--divisions", default=None,
                    help="読む区分番号をカンマ区切りで絞る（1=理工学部 2=短期大学部 3=博士前期 4=博士後期）。"
                         "既定は全部。`--divisions 1,3,4` で短大を外すと現行DBを完全再現する")
    args = ap.parse_args(argv)

    divisions = None
    if args.divisions is not None:
        divisions = {d.strip() for d in args.divisions.split(",") if d.strip()}
        bad = {d for d in divisions if not d.isdigit()}
        if not divisions or bad:
            print(f"--divisions の指定が不正です: {args.divisions!r}"
                  f"（1〜9 の区分番号をカンマ区切りで。例: 1,3,4）", file=sys.stderr)
            return 1

    stats = Stats()
    try:
        metas = collect_sources(Path(args.src), divisions)
        years = sorted({m["year"] for m, _ in metas})
        print(f"原本: {len(metas)} ファイル（{args.src}）  年度: {'/'.join(str(y) for y in years)}")
        if len(years) > 1:
            print(f"  ※ 年度が混ざっています: {years}。意図した組み合わせか確認してください")
        rows, master_rows = build_rows(metas, stats)
        # 教室マスタは短大を除いた行から作る（短大専用教室を検索対象に増やさないため）
        classrooms = build_classrooms(master_rows, stats)
    except SourceError as exc:
        print("原本の読み取りに失敗しました。DB は作っていません。", file=sys.stderr)
        print(f"  {exc}", file=sys.stderr)
        return 1

    if not rows:
        print("原本から 1 行も取れませんでした。列見出しや曜日ブロックの想定が崩れている可能性があります。",
              file=sys.stderr)
        return 1

    # --replace で上書きすると比較対象が消えるので、先に中身を控えておく
    ref_before = None
    if args.replace and args.report and not args.no_write and Path(args.ref).exists():
        ref_before = read_ref(Path(args.ref))

    out_path = Path(args.out)
    if args.no_write:
        print("--no-write のため DB は書きません" + ("（--replace は無視します）" if args.replace else ""))
    else:
        if args.replace:
            out_path = Path(args.ref)
            tmp = out_path.with_suffix(out_path.suffix + ".tmp")
            try:
                # まるごと作ってから差し替える（途中で失敗しても現行 DB を壊さない）
                write_db(tmp, rows, classrooms)
                backup = replace_db(tmp, out_path)
            finally:
                if tmp.exists():
                    tmp.unlink()
            print(f"置き換えました: {out_path}" + (f"（旧 DB を {backup} に退避）" if backup else ""))
        else:
            write_db(out_path, rows, classrooms)
            print(f"書き出しました: {out_path}（schedules {len(rows):,} 行 / classrooms {len(classrooms):,} 件）")
            print(f"  現行 {args.ref} は触っていません。入れ替えるときは --replace を付けてください")

    report_build(stats)
    identical = None
    if args.report:
        ref = Path(args.ref)
        if not ref.exists():
            print(f"\n比較する現行 DB がありません: {ref}", file=sys.stderr)
            return 1
        if ref_before is not None:
            # --replace で上書きした後に現物と比べても「同じ」に決まっている。
            # 差し替え前に取っておいたスナップショットと比べて、何が変わったかを出す
            print("\n※ --replace で置き換えました。以下は「置き換え前の DB」との差分です")
        identical = report_diff(rows, classrooms, ref, ref_data=ref_before)
    report_warnings(stats)

    if identical is True:
        print("\n結果: 現行 DB を 7 列すべて完全に再現できました。")
    elif identical is False:
        print("\n結果: 現行 DB と差分があります。上の「占有スロット」「教室マスタ」を確認してください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
