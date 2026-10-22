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
- 時刻も時限も書かれていない行は、その日は終日使えないとみなす（「空き」に出さない側に倒す）

仮の形式（CSV。1行目は見出し。列の順番は問わない。UTF-8 か Shift_JIS）:
    日付,開始,終了,教室,（そのほかの列は無視）
    2026-10-23,10:50,12:30,S303,…
時刻の代わりに「時限」列（2、２限、2-3 など）でもよい。同じ見出しを持つ JSON の配列でもよい。
教室の合同の略記（1456/7/8）は 1456・1457・1458 に分ける（時間割 DB と同じ規則）。
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
MAX_BACKOFF = 1800                     # 失敗が続いたときの読み直し間隔の上限（秒）
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
COLUMNS = {
    "date": ("日付", "使用日", "利用日", "date"),
    "start": ("開始", "開始時刻", "開始時間", "使用開始", "start"),
    "end": ("終了", "終了時刻", "終了時間", "使用終了", "end"),
    "period": ("時限", "period"),
    "room": ("教室", "教室名", "施設", "施設名", "room"),
}

_fetch_lock = threading.Lock()
_worker_lock = threading.Lock()
_worker = {"pid": None, "ready": threading.Event()}
_state = {"data": {}, "loaded_at": None, "checked_at": None, "error": None,
          "bad_rows": 0, "unmatched": 0}


def room_key(name):
    """教室名の表記ゆれを吸収した照合用の鍵（app.normalize_room と同じ規則）"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(name or ""))).lower()


def room_keys(text):
    """1つの欄から教室の鍵を作る。合同の略記（1456/7/8・S303/4）は部屋ごとに分ける"""
    key = room_key(text)
    m = re.fullmatch(r"([a-z]*)(\d{3,4})((?:/\d{1,4})+)", key)
    if not m:
        return [key] if key else []
    prefix, base, rest = m.group(1), m.group(2), m.group(3)
    keys = [prefix + base]
    for tail in rest.split("/")[1:]:
        keys.append(prefix + (base[:len(base) - len(tail)] + tail if len(tail) < len(base) else tail))
    return keys


def enabled():
    return bool(os.environ.get(URL_ENV) or os.environ.get(FILE_ENV))


def _norm(text):
    return unicodedata.normalize("NFKC", str(text or "")).strip()


def _dashed(text):
    """日付・時限の範囲に使われるいろいろなダッシュ・波線を "-" にそろえる（教室名には使わない）"""
    return re.sub(r"[‐‑‒–—―−ー〜~]", "-", _norm(text))


def _parse_date(text):
    # 「2026/10/23(金)」「2026-10-23 0:00:00」のような書き方も読む
    m = re.match(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})日?", _dashed(text))
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
    found = {p for p in periods if min(a, b) <= p <= max(a, b)}
    return found or None


def periods_overlapping(start, end, periods):
    """時刻の範囲と重なる時限。授業と少しでも重なれば、その時限は使えないとみなす"""
    return {p for p, (s, e) in periods.items() if start < e and end > s}


def _field_of(header):
    h = _norm(header)
    h = h.lower() if h.isascii() else h
    for field, names in COLUMNS.items():
        if h in names:
            return field
    return None


def _pick(row, field):
    for key, value in row.items():
        if _field_of(key) == field and str(value or "").strip():
            return value
    return None


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
        if period_text is not None:
            slots = _parse_periods(period_text, periods)
        elif start_text is not None or end_text is not None:
            start, end = _parse_time(start_text), _parse_time(end_text)
            slots = periods_overlapping(start, end, periods) if start and end and start < end else None
            if slots == set():
                counts["ignored"] += 1       # 休み時間・夜間だけの予定。授業時間にはかからない
                continue
        else:
            slots = set(periods)             # 時刻も時限も無い行は、その日は終日使えないとみなす
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
        if not isinstance(rows, list):
            raise ValueError("JSON は配列で来る想定")
        rows = [r for r in rows if isinstance(r, dict)]
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
        chunk = resp.read(65536)
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


def refresh(periods, known_keys=None, force=False):
    """読み直しの時期なら読み直す。うまく読めたら True。ほかで読み直し中なら何もしない"""
    if not enabled():
        return False
    now = time.time()
    checked = _state["checked_at"]
    if not force and checked is not None and now - checked < REFRESH_SECONDS:
        return _state["error"] is None
    if not _fetch_lock.acquire(blocking=False):
        return _state["error"] is None
    try:
        _state["checked_at"] = now
        data, counts = parse_text(_read_source(), periods)
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
        # 例外の文面には読み取り先の URL や中身が入りうるので、種類だけ残す
        _state["error"] = type(e).__name__
        logging.warning(f"school_bookings: 読み取りに失敗（{type(e).__name__}）。前回の内容を使います")
        return False
    finally:
        _fetch_lock.release()


def _loop(periods, known_keys, ready):
    delay = REFRESH_SECONDS
    while True:
        ok = refresh(periods, known_keys, force=True)
        ready.set()
        delay = REFRESH_SECONDS if ok else min(delay * 2, MAX_BACKOFF)
        time.sleep(delay)


def _ensure_worker(periods, known_keys):
    """このプロセスの読み取り用スレッドを1本だけ起こす（gunicorn のワーカーごと）"""
    if _worker["pid"] == os.getpid():
        return
    with _worker_lock:
        if _worker["pid"] == os.getpid():
            return
        ready = threading.Event()
        _worker.update(pid=os.getpid(), ready=ready)
        threading.Thread(target=_loop, args=(periods, known_keys, ready),
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
            _worker["ready"].wait(FIRST_LOAD_WAIT)
    loaded = _state["loaded_at"]
    if loaded is None or time.time() - loaded > MAX_STALE:
        return {}
    return {p: frozenset(keys) for p, keys in _state["data"].get(date, {}).items()}


def status():
    """運用の確認用（件数と状態だけ。中身・読み取り先は出さない）"""
    return {"enabled": enabled(), "loaded_at": _state["loaded_at"], "error": _state["error"],
            "days": len(_state["data"]), "bad_rows": _state["bad_rows"], "unmatched": _state["unmatched"]}


def _reset_for_tests():
    _state.update(data={}, loaded_at=None, checked_at=None, error=None, bad_rows=0, unmatched=0)
