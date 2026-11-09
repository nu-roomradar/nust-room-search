"""教務課の教室使用予定（授業以外の予約）を取り込み、その時間帯の教室を「空き」に出さないための部品。

**仮の実装（2026-10-22）。** 理工学部学生課から「教務課の教室予約データが提供されたら、リアルタイムで
反映できるか」と聞かれ、教務課のシステムから自動で読み取る形を想定して先に作っておく。
データの形式と受け取り方が決まったら、`COLUMNS`・`parse_text`（形式）と `_read_source`（受け取り方）を
合わせて最終調整する（docs/OPERATIONS.md 4.9）。

方針:
- 予約が入っている時間帯の教室は「空き」として出さない。画面で「予約」とは書かない（CLAUDE.md ルール3）
- 使うのは 日付・時間帯・教室 だけ。予約者名など、ほかの列は読み込んだその場で捨て、どこにも保存しない（メモリだけ）。
  ログ・status() にも中身（教室名・予約者・読み取り先の URL・鍵）は出さない
- 予約データはリポジトリ（公開）に置かない。読み取り先と鍵は Render の環境変数に入れる
- 環境変数 SCHOOL_BOOKINGS_URL か SCHOOL_BOOKINGS_FILE が無ければ何もしない（いまの本番と同じ動き）
- 読み取りは検索の応答とは別のスレッドで行う（プロセスごとに1本）。上流が遅くても検索は待たされない
- 読めない応答（ログイン画面の HTML・空・見出し違い）は失敗として扱い、前回の内容を使い続ける。
  ただし最後にうまく読めてから MAX_STALE を過ぎたら使わない（古い予定で「空き」を隠し続けるより、
  時間割だけの表示に戻すほうが安全）
- 時刻も時限も書かれていない行（「終日」「全日」も）は、その日は終日使えないとみなす（「空き」に出さない側に倒す）

仮の形式（CSV。1行目は見出し。列の順番は問わない。UTF-8 か Shift_JIS）:
    日付,開始,終了,教室,（そのほかの列は無視）
    2026-10-23,10:50,12:30,S303,…
時刻の代わりに「時限」列（2、２限、2-3 など）でもよい。同じ見出しを持つ JSON の配列でもよい。
教室の合同の略記（1456/7/8、521/2/…/10）は時間割 DB（scripts/build_schedule_db.py の規則D）と同じ規則で分ける。
"""
import csv
import datetime
import io
import json
import logging
import os
import re
import threading
import time
import unicodedata
import urllib.request

URL_ENV = "SCHOOL_BOOKINGS_URL"        # 教務課のシステムの読み取り先（https。決まったら Render の環境変数に入れる）
TOKEN_ENV = "SCHOOL_BOOKINGS_TOKEN"    # 読み取りに鍵が要るなら。Authorization: Bearer で送る（形は決まったら合わせる）
FILE_ENV = "SCHOOL_BOOKINGS_FILE"      # ファイルで受け取る場合・手元での確認用
INTERVAL_ENV = "SCHOOL_BOOKINGS_INTERVAL"
MAX_STALE = 6 * 3600                   # 最後にうまく読めてからこれを過ぎたら、予定を使わない
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT = 5                            # 1回の通信操作の待ち時間（秒）
READ_DEADLINE = 15                     # 読み取り全体の締め切り（秒）。少しずつしか返さない相手で詰まらないように
FIRST_LOAD_WAIT = 1.0                  # 起動直後、最初の読み取りを検索が待つ上限（秒）
RETRY_SECONDS = 60                     # 失敗したら、まずこの間隔で読み直し、続けば倍にしていく
MAX_BACKOFF = 1800                     # 失敗が続いたときの読み直し間隔の上限（秒。通常の間隔より長ければそちら）
SYNC = False                           # True なら検索の中で読み直す（テスト用）


def _interval_from_env(default=300, lo=60, hi=MAX_STALE // 2):
    """読み直しの間隔（秒）。書き間違い（"5m" など）でもアプリが起動しなくならないよう、既定値に戻す"""
    raw = (os.environ.get(INTERVAL_ENV) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logging.warning(f"school_bookings: {INTERVAL_ENV} は秒数（整数）で書く。既定の {default} 秒を使います")
        return default
    return min(max(value, lo), hi)


REFRESH_SECONDS = _interval_from_env()

# 見出しの言い方の揺れ（形式が決まったらここを合わせる）
# 見出しの言い方の揺れ（形式が決まったらここを合わせる）。同じ項目に当たる列が複数あるときは、ここに書いた順で選ぶ
COLUMNS = {
    "date": ("日付", "使用日", "利用日", "date"),
    "start": ("開始", "開始時刻", "開始時間", "使用開始", "start"),
    "end": ("終了", "終了時刻", "終了時間", "使用終了", "end"),
    "period": ("時限", "period"),
    "room": ("教室", "教室名", "room", "施設名", "施設"),
}
ALL_DAY_WORDS = {"終日", "全日", "-"}    # 時刻・時限の欄にこう書いてあれば終日
ROOM_CODE = re.compile(r"[a-z]?\d{3,4}[a-z]?")             # 641 / 1425 / s407 / 805b（照合用の小文字）
JOINT = re.compile(r"([a-z]?\d{3,4})((?:/\d{1,4})+)")      # 1456/7/8・521/2/…/10・s1704/07/13
MIDDLE_DOTS = "・･·"

_fetch_lock = threading.Lock()
_worker_lock = threading.Lock()
_worker = {"pid": None, "ready": threading.Event(), "started": 0.0, "gen": 0}   # gen: 古い読み取りスレッドを止める目印
_state = {"data": {}, "loaded_at": None, "checked_at": None, "error": None,
          "bad_rows": 0, "unmatched": 0}


def room_key(name):
    """教室名の表記ゆれを吸収した照合用の鍵（app.normalize_room と同じ規則）"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(name or ""))).lower()


def _split_joint(key):
    """規則D（scripts/build_schedule_db.py の split_joint_rooms と同じ）。当てはまらなければ None。
    2つ目の片の桁数 w ぶん、先頭の番号の末尾を置き換える。w より長い片は置き換える前の部分に付ける。
    片が先頭と同じ桁（101/102）なら略記ではないので、片をそれぞれ1室として扱う"""
    m = JOINT.fullmatch(key)
    if not m:
        return None
    first, pieces = m.group(1), m.group(2).split("/")[1:]
    w = len(pieces[0])
    digits = len(re.match(r"[a-z]?(\d+)", first).group(1))
    prefix = re.match(r"[a-z]?", first).group(0)
    if w >= digits:
        return [first] + [prefix + p for p in pieces]
    base = first[:-w]
    return [first] + [base + p if len(p) >= w else first[:-len(p)] + p for p in pieces]


def room_keys(text):
    """1つの欄から教室の鍵を作る。合同の略記（1456/7/8）や、教室コードの並び（S303/S304・1111・521）は部屋ごとに分ける"""
    key = room_key(text)
    if not key:
        return []
    parts = [p for p in re.split(f"[{MIDDLE_DOTS}]", key) if p]
    if len(parts) > 1 and all(ROOM_CODE.fullmatch(p) for p in parts):
        return parts
    joint = _split_joint(key)
    if joint:
        return joint
    parts = key.split("/")
    if len(parts) > 1 and all(ROOM_CODE.fullmatch(p) for p in parts):
        return parts
    return [key]


def enabled():
    return bool(os.environ.get(URL_ENV) or os.environ.get(FILE_ENV))


def _norm(text):
    return unicodedata.normalize("NFKC", str(text or "")).strip()


def _dashed(text):
    """日付・時限の範囲に使われるいろいろなダッシュ・波線を "-" にそろえる（教室名には使わない）"""
    return re.sub(r"[‐‑‒–—―−ー〜~]", "-", _norm(text))


def _parse_date(text):
    # 「2026/10/23(金)」「2026-10-23 0:00:00」のような書き方も読む。期間（～10/30）は読めない行にする
    m = re.fullmatch(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})日?(?:\s*[(（][^)）]{1,3}[)）])?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?",
                     _dashed(text))
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _parse_time(text):
    m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::\d{2})?", _norm(text))
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if mi > 59 or h > 24 or (h == 24 and mi):
        return None
    return f"{h:02d}:{mi:02d}"


def _parse_periods(text, periods):
    m = re.fullmatch(r"(\d)(?:限)?(?:-(\d)(?:限)?)?", _dashed(text).replace(" ", ""))
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2) or m.group(1))
    return {p for p in periods if min(a, b) <= p <= max(a, b)}   # 7限など授業の無い時限だけなら空


def periods_overlapping(start, end, periods):
    """時刻の範囲と重なる時限。授業と少しでも重なれば、その時限は使えないとみなす"""
    return {p for p, (s, e) in periods.items() if start < e and end > s}


def _header(name):
    h = _norm(name)
    return h.lower() if h.isascii() else h


def _field_of(header):
    h = _header(header)
    for field, names in COLUMNS.items():
        if h in names:
            return field
    return None


def _blank(value):
    return value is None or str(value).strip() == ""


def _pick(row, field):
    """その項目の値。列が複数あれば COLUMNS に書いた順で選ぶ（「教室」があれば「施設」より優先）"""
    by_name = {_header(k): v for k, v in row.items()}
    for name in COLUMNS[field]:
        if name in by_name and not _blank(by_name[name]):
            return by_name[name]
    return None


def _all_day(value):
    return value is not None and _dashed(value) in ALL_DAY_WORDS


def parse_rows(rows, periods):
    """見出し付きの行（dict）から {日付: {時限: {教室の鍵}}} を作る。ほかの列はここで捨てる。

    返す counts: rows=行数、used=使った行、ignored=空行・授業時間にかからない行、bad=読めなかった行"""
    data = {}
    counts = {"rows": 0, "used": 0, "ignored": 0, "bad": 0}
    for raw in rows:
        counts["rows"] += 1
        row = {k: v for k, v in (raw or {}).items() if k is not None}
        if not any(str(v or "").strip() for v in row.values()):
            counts["ignored"] += 1           # Excel の末尾の空行など
            continue
        date = _parse_date(_pick(row, "date"))
        keys = room_keys(_pick(row, "room"))
        period_text = _pick(row, "period")
        start_text, end_text = _pick(row, "start"), _pick(row, "end")
        slots = None
        if _all_day(period_text) or _all_day(start_text):
            slots = set(periods)                 # 「終日」「全日」
        elif period_text is not None and _parse_periods(period_text, periods) is not None:
            slots = _parse_periods(period_text, periods)
        elif start_text is not None or end_text is not None:
            start, end = _parse_time(start_text), _parse_time(end_text)
            if start and end == "00:00":
                end = "24:00"                    # 夜中の0時まで
            slots = periods_overlapping(start, end, periods) if start and end and start < end else None
        elif period_text is None:
            slots = set(periods)                 # 時刻も時限も無い行は、その日は終日使えないとみなす
        if slots == set():
            counts["ignored"] += 1               # 休み時間・夜間・授業の無い時限だけの予定
            continue
        if not (date and keys and slots):
            counts["bad"] += 1
            continue
        counts["used"] += 1
        day = data.setdefault(date, {})
        for p in slots:
            day.setdefault(p, set()).update(keys)
    return data, counts


def parse_text(text, periods):
    """CSV か JSON（同じ見出しを持つオブジェクトの配列）を読む。

    中身が読めない（見出しに日付・教室が無い、JSON が配列でない、行はあるのに1行も使えない）ときは
    ValueError にする。ログイン画面の HTML などを「予定0件」と取り違えて、前回の予定を消さないため。
    見出しだけの CSV や [] は「予定なし」として正しく読む。"""
    stripped = text.lstrip("﻿").lstrip()
    if stripped.startswith(("[", "{")):
        rows = json.loads(stripped)
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise ValueError("JSON はオブジェクトの配列で来る想定")
        fields = {_field_of(k) for r in rows for k in r}
        if rows and not {"date", "room"} <= fields:
            raise ValueError("JSON に日付と教室の項目が無い")
    else:
        reader = csv.DictReader(io.StringIO(stripped))
        fields = {_field_of(h) for h in (reader.fieldnames or [])}
        if not {"date", "room"} <= fields:
            raise ValueError("見出しに日付と教室が無い（形式が違うか、ログイン画面などが返ってきた）")
        rows = list(reader)
    data, counts = parse_rows(rows, periods)
    if counts["rows"] - counts["ignored"] > 0 and counts["used"] == 0:
        raise ValueError("使える行が1行も無い")
    return data, counts


def _decode(raw):
    for enc in ("utf-8-sig", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("文字コードが読めない（UTF-8 か Shift_JIS の想定）")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """転送を追わない（HTTPError になる）。転送先のホストや http に鍵を送らないため"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _build_request(url, token=None):
    req = urllib.request.Request(url, headers={"User-Agent": "RoomRadar-school-bookings"})
    if token:
        req.add_unredirected_header("Authorization", f"Bearer {token}")
    return req


def _read_all(resp, deadline):
    chunks, total = [], 0
    while True:
        if time.monotonic() > deadline:
            raise TimeoutError("読み取りに時間がかかりすぎる")
        chunk = resp.read1(65536)       # read() は 64KiB たまるまで戻らず、締め切りを確かめられない
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_BYTES:
            raise ValueError("大きすぎる")


def _read_source():
    """読み取り先から中身を取る。URL が優先。形が決まったら、ここを教務課のシステムに合わせる"""
    url = os.environ.get(URL_ENV)
    if url:
        if not url.startswith("https://"):
            raise ValueError("読み取り先は https に限る")
        deadline = time.monotonic() + READ_DEADLINE
        with _OPENER.open(_build_request(url, os.environ.get(TOKEN_ENV)), timeout=TIMEOUT) as resp:
            if "html" in (resp.headers.get("Content-Type") or "").lower():
                raise ValueError("HTML が返ってきた（ログイン画面など）")
            raw = _read_all(resp, deadline)
    else:
        with open(os.environ[FILE_ENV], "rb") as f:
            raw = f.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("大きすぎる")
    return _decode(raw)


def refresh(periods, known_keys=None, force=False, gen=None):
    """読み直しの時期なら読み直す。読めたら True、失敗したら False。読み直さなかったら None"""
    if not enabled():
        return False
    now = time.time()
    checked = _state["checked_at"]
    if not force and checked is not None and now - checked < REFRESH_SECONDS:
        return None
    if not _fetch_lock.acquire(blocking=False):
        return None
    try:
        _state["checked_at"] = now
        data, counts = parse_text(_read_source(), periods)
        if gen is not None and gen != _worker["gen"]:
            return None                          # 止められた古いスレッドの結果は使わない
        unmatched = 0
        if known_keys:
            unmatched = len({k for day in data.values() for keys in day.values() for k in keys} - set(known_keys))
        _state.update(data=data, loaded_at=now, error=None, bad_rows=counts["bad"], unmatched=unmatched)
        if counts["bad"]:
            logging.warning(f"school_bookings: 読めなかった行 {counts['bad']} 件（形式を確認）")
        if unmatched:
            logging.warning(f"school_bookings: 時間割の教室と照合できなかった教室 {unmatched} 室（教室名の書き方を確認）")
        return True
    except Exception as e:   # 何が起きても検索は止めない。前回の内容を使い続ける
        if gen is not None and gen != _worker["gen"]:
            return None
        # 例外の文面には読み取り先の URL や中身が入りうるので、種類だけ残す
        _state["error"] = type(e).__name__
        logging.warning(f"school_bookings: 読み取りに失敗（{type(e).__name__}）。前回の内容を使います")
        return False
    finally:
        _fetch_lock.release()


def next_delay(ok, failures):
    """次に読み直すまでの秒数。失敗したら短い間隔から倍にしていく"""
    if ok:
        return REFRESH_SECONDS
    return min(RETRY_SECONDS * 2 ** max(failures - 1, 0), max(REFRESH_SECONDS, MAX_BACKOFF))


def _loop(periods, known_keys, ready, gen):
    failures = 0
    while _worker["gen"] == gen:
        ok = refresh(periods, known_keys, force=True, gen=gen) is True
        ready.set()
        failures = 0 if ok else failures + 1
        time.sleep(next_delay(ok, failures))


def _ensure_worker(periods, known_keys):
    """このプロセスの読み取り用スレッドを1本だけ起こす（gunicorn のワーカーごと）"""
    if _worker["pid"] == os.getpid():
        return
    with _worker_lock:
        if _worker["pid"] == os.getpid():
            return
        ready = threading.Event()
        _worker.update(pid=os.getpid(), ready=ready, started=time.monotonic())
        threading.Thread(target=_loop, args=(periods, known_keys, ready, _worker["gen"]),
                         name="school-bookings", daemon=True).start()


def booked_rooms(date, periods, known_keys=None):
    """その日の {時限: {教室の鍵}}。使えない（無効・まだ読めていない・古すぎる）ときは空。
    検索の応答の中では読み取りをしない（SYNC のときだけ）"""
    if not enabled():
        return {}
    if SYNC:
        refresh(periods, known_keys)
    else:
        _ensure_worker(periods, known_keys)
        if _state["loaded_at"] is None:
            # 待つのはワーカーの起動から FIRST_LOAD_WAIT のあいだだけ。読み取りが詰まっていても検索を遅くしない
            remaining = _worker["started"] + FIRST_LOAD_WAIT - time.monotonic()
            if remaining > 0:
                _worker["ready"].wait(remaining)
    loaded = _state["loaded_at"]
    if loaded is None or time.time() - loaded > MAX_STALE:
        return {}
    return {p: frozenset(keys) for p, keys in _state["data"].get(date, {}).items()}


def status():
    """運用の確認用（件数と状態だけ。中身・読み取り先は出さない）"""
    return {"enabled": enabled(), "loaded_at": _state["loaded_at"], "error": _state["error"],
            "days": len(_state["data"]), "bad_rows": _state["bad_rows"], "unmatched": _state["unmatched"]}


def _after_fork_in_child():
    """fork した子（gunicorn のワーカー）では、親のロックやスレッドの状態を引き継がない"""
    global _fetch_lock, _worker_lock
    _fetch_lock, _worker_lock = threading.Lock(), threading.Lock()
    _worker.update(pid=None, ready=threading.Event(), started=0.0, gen=_worker["gen"] + 1)


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_after_fork_in_child)


def _reset_for_tests():
    _state.update(data={}, loaded_at=None, checked_at=None, error=None, bad_rows=0, unmatched=0)
