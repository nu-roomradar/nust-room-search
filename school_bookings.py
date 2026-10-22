"""教務課の教室使用予定（授業以外の予約）を取り込み、その時間帯の教室を「空き」に出さないための部品。

**仮の実装（2026-10-22）。** 理工学部学生課から「教務課の教室予約データが提供されたら、リアルタイムで
反映できるか」と聞かれ、教務課のシステムから自動で読み取る形を想定して先に作っておく。
データの形式と受け取り方が決まったら、`parse_text`（形式）と `_read_source`（受け取り方）を合わせて最終調整する。

方針（docs/OPERATIONS.md 4.9）:
- 予約が入っている時間帯の教室は「空き」として出さない。画面で「予約」とは書かない（CLAUDE.md ルール3）
- 使うのは 日付・時間帯・教室 だけ。予約者名など、ほかの列は読み込んだその場で捨て、どこにも保存しない（メモリだけ）
- 予約データはリポジトリ（公開）に置かない。読み取り先と鍵は Render の環境変数に入れる
- 環境変数 SCHOOL_BOOKINGS_URL か SCHOOL_BOOKINGS_FILE が無ければ何もしない（いまの本番と同じ動き）
- 読み取りに失敗したら、前回うまく読めた内容を使い続ける。ただし MAX_STALE を過ぎたら使わない
  （古い予定で「空き」を隠し続けるより、時間割だけの表示に戻すほうが安全）

仮の形式（CSV。1行目は見出し。列の順番は問わない。UTF-8 か Shift_JIS）:
    日付,開始,終了,教室,（そのほかの列は無視）
    2026-10-23,10:50,12:30,S303,…
時刻の代わりに「時限」列（2、２限、2-3 など）でもよい。同じ見出しを持つ JSON の配列でもよい。
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

URL_ENV = "SCHOOL_BOOKINGS_URL"        # 教務課のシステムの読み取り先（決まったら Render の環境変数に入れる）
TOKEN_ENV = "SCHOOL_BOOKINGS_TOKEN"    # 読み取りに鍵が要るなら。Authorization: Bearer で送る（形は決まったら合わせる）
FILE_ENV = "SCHOOL_BOOKINGS_FILE"      # ファイルで受け取る場合・手元での確認用
REFRESH_SECONDS = int(os.environ.get("SCHOOL_BOOKINGS_INTERVAL", "300"))   # 何秒おきに読み直すか
MAX_STALE = 6 * 3600                   # 最後にうまく読めてからこれを過ぎたら、予定を使わない
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT = 5

# 見出しの言い方の揺れ（形式が決まったらここを合わせる）
COLUMNS = {
    "date": ("日付", "使用日", "date"),
    "start": ("開始", "開始時刻", "start"),
    "end": ("終了", "終了時刻", "end"),
    "period": ("時限", "period"),
    "room": ("教室", "教室名", "room"),
}

_lock = threading.Lock()
_state = {"data": {}, "loaded_at": None, "checked_at": None, "error": None, "skipped": 0}


def room_key(name):
    """教室名の表記ゆれを吸収した照合用の鍵（app.normalize_room と同じ規則）"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(name or ""))).lower()


def enabled():
    return bool(os.environ.get(URL_ENV) or os.environ.get(FILE_ENV))


def _norm(text):
    return unicodedata.normalize("NFKC", str(text or "")).strip()


def _parse_date(text):
    t = _norm(text)
    m = re.fullmatch(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})日?", t)
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _parse_time(text):
    m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::\d{2})?", _norm(text))
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        return None
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def _parse_periods(text, periods):
    m = re.fullmatch(r"(\d)(?:限)?(?:[-~〜](\d)(?:限)?)?", _norm(text).replace(" ", ""))
    if not m:
        return set()
    a, b = int(m.group(1)), int(m.group(2) or m.group(1))
    return {p for p in periods if min(a, b) <= p <= max(a, b)}


def periods_overlapping(start, end, periods):
    """時刻の範囲と重なる時限。授業と少しでも重なれば、その時限は使えないとみなす"""
    return {p for p, (s, e) in periods.items() if start < e and end > s}


def _pick(row, field):
    for name in COLUMNS[field]:
        if name in row and str(row[name]).strip():
            return row[name]
    return None


def parse_rows(rows, periods):
    """見出し付きの行（dict）から {日付: {時限: {教室の鍵}}} を作る。ほかの列はここで捨てる"""
    data, skipped = {}, 0
    for raw in rows:
        row = {_norm(k).lower() if _norm(k).isascii() else _norm(k): v for k, v in (raw or {}).items() if k is not None}
        date = _parse_date(_pick(row, "date"))
        room = room_key(_pick(row, "room"))
        slots = set()
        if _pick(row, "period") is not None:
            slots = _parse_periods(_pick(row, "period"), periods)
        else:
            start, end = _parse_time(_pick(row, "start")), _parse_time(_pick(row, "end"))
            if start and end and start < end:
                slots = periods_overlapping(start, end, periods)
        if not (date and room and slots):
            skipped += 1
            continue
        day = data.setdefault(date, {})
        for p in slots:
            day.setdefault(p, set()).add(room)
    return data, skipped


def parse_text(text, periods):
    """CSV か JSON（同じ見出しを持つオブジェクトの配列）を読む"""
    stripped = text.lstrip("﻿").lstrip()
    if stripped.startswith("["):
        rows = json.loads(stripped)
        if not isinstance(rows, list):
            raise ValueError("JSON は配列で来る想定")
        rows = [r for r in rows if isinstance(r, dict)]
    else:
        rows = list(csv.DictReader(io.StringIO(stripped)))
    return parse_rows(rows, periods)


def _decode(raw):
    for enc in ("utf-8-sig", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("文字コードが読めない（UTF-8 か Shift_JIS の想定）")


def _read_source():
    """読み取り先から中身を取る。URL が優先。形が決まったら、ここを教務課のシステムに合わせる"""
    url = os.environ.get(URL_ENV)
    if url:
        if not url.startswith("https://"):
            raise ValueError("読み取り先は https に限る")
        req = urllib.request.Request(url, headers={"User-Agent": "RoomRadar-school-bookings"})
        token = os.environ.get(TOKEN_ENV)
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read(MAX_BYTES + 1)
    else:
        with open(os.environ[FILE_ENV], "rb") as f:
            raw = f.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("大きすぎる")
    return _decode(raw)


def refresh(periods, force=False):
    """読み直しの時期なら読み直す。ほかの人が読み直し中なら待たずに前回の内容を使う"""
    if not enabled():
        return
    now = time.time()
    checked = _state["checked_at"]
    if not force and checked is not None and now - checked < REFRESH_SECONDS:
        return
    if not _lock.acquire(blocking=False):
        return
    try:
        _state["checked_at"] = now
        data, skipped = parse_text(_read_source(), periods)
        _state.update(data=data, loaded_at=now, error=None, skipped=skipped)
        if skipped:
            logging.warning(f"school_bookings: 読めなかった行 {skipped} 件（形式を確認）")
    except Exception as e:   # 何が起きても検索は止めない。前回の内容を使い続ける
        # 例外の文面には読み取り先の URL が入りうるので、種類だけ残す
        _state["error"] = type(e).__name__
        logging.warning(f"school_bookings: 読み取りに失敗（{type(e).__name__}）。前回の内容を使います")
    finally:
        _lock.release()


def booked_rooms(date, periods):
    """その日の {時限: {教室の鍵}}。使えない（無効・一度も読めていない・古すぎる）ときは空"""
    if not enabled():
        return {}
    refresh(periods)
    loaded = _state["loaded_at"]
    if loaded is None or time.time() - loaded > MAX_STALE:
        return {}
    return {p: frozenset(keys) for p, keys in _state["data"].get(date, {}).items()}


def status():
    """運用の確認用（件数と状態だけ。中身は出さない）"""
    return {"enabled": enabled(), "loaded_at": _state["loaded_at"], "error": _state["error"],
            "days": len(_state["data"]), "skipped_rows": _state["skipped"]}


def _reset_for_tests():
    _state.update(data={}, loaded_at=None, checked_at=None, error=None, skipped=0)
