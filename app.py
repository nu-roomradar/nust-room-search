import os
import sqlite3
import datetime
import hashlib
import secrets
import string
import collections
import time
import logging
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

DB_NAME = "schedule_final.db"
JST = datetime.timezone(datetime.timedelta(hours=9))
PERIODS = {1: ("09:00", "10:40"), 2: ("10:50", "12:30"), 3: ("13:20", "15:00"),
           4: ("15:10", "16:50"), 5: ("17:00", "18:40"), 6: ("18:50", "20:30")}
RESERVE_DB  = "reservations.db"
REPORTS_DB  = "reports.db"
REPORT_THRESHOLD = 2  # 何人報告でグレーアウトするか

def init_reports_db():
    conn = sqlite3.connect(REPORTS_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            room        TEXT NOT NULL,
            day         TEXT NOT NULL,
            period      INTEGER NOT NULL,
            cancel_code TEXT NOT NULL,
            expires_at  TEXT NOT NULL,
            reporter    TEXT
        )
    """)
    # 既存の DB（reporter 列が無い頃のもの）にも列を足す
    if "reporter" not in {r[1] for r in conn.execute("PRAGMA table_info(reports)")}:
        conn.execute("ALTER TABLE reports ADD COLUMN reporter TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rep ON reports (room, day, period)")
    # 1人が同じコマの同じ教室を2回報告できないようにする（しきい値は「人数」で数える）
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_rep_once ON reports (room, day, period, reporter)")
    conn.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL)")
    conn.commit(); conn.close()

def cleanup_reports():
    now = datetime.datetime.now(JST).isoformat()
    conn = sqlite3.connect(REPORTS_DB)
    conn.execute("DELETE FROM reports WHERE expires_at < ?", (now,))
    conn.commit(); conn.close()

def get_report_counts(day, period):
    """指定曜日・時限の教室ごとの報告**人数**を返す {room: count}

    以前は行数を数えていたため、1人が2回押すだけでしきい値（2件）に達して
    「使用中の可能性」にできた。reporter ごとに1人と数える。
    reporter が無い古い行は1行1人として数える。
    """
    conn = sqlite3.connect(REPORTS_DB)
    rows = conn.execute(
        "SELECT room, COUNT(DISTINCT COALESCE(reporter, 'legacy:' || id)) "
        "FROM reports WHERE day=? AND period=? GROUP BY room",
        (day, period)
    ).fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}

def reporter_id(ip):
    """報告者の識別子。IP をそのまま保存しないよう、DB ごとの秘密の塩でハッシュ化する

    塩は reports.db 自体に置く（gunicorn のワーカーが複数でも同じ値になるように）。
    報告は時限終了で消えるので、識別子もそれ以上は残らない。
    """
    conn = sqlite3.connect(REPORTS_DB)
    try:
        conn.execute("INSERT OR IGNORE INTO meta (k, v) VALUES ('reporter_salt', ?)",
                     (secrets.token_hex(16),))
        conn.commit()
        salt = conn.execute("SELECT v FROM meta WHERE k='reporter_salt'").fetchone()[0]
    finally:
        conn.close()
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:16]

init_reports_db()

# セキュリティ設定
VALID_DAYS      = {'月','火','水','木','金','土'}
VALID_PERIODS   = {1,2,3,4,5,6}
VALID_BUILDINGS = {'all','tower','main','funabashi'}
VALID_TERMS     = ('前期','後期')
_rate_store = collections.defaultdict(list)
RATE_LIMIT, RATE_WINDOW = 30, 60

# 手前にいる信頼できるプロキシの段数。Render は1段（ロードバランサ）が
# X-Forwarded-For の末尾に接続元 IP を付け足す。段数が違う環境では環境変数で変える。
TRUSTED_PROXY_HOPS = int(os.environ.get("TRUSTED_PROXY_HOPS", "1"))

def client_ip():
    """レート制限・報告者識別に使う接続元 IP

    X-Forwarded-For は「利用者が自分で書いた値, …, プロキシが付け足した値」の順に並ぶ。
    以前は**先頭**を使っていたため、利用者がヘッダを自分で付ければ好きな IP を名乗れ、
    レート制限をすり抜けられた。信頼できるプロキシが付け足した**末尾側**を使う。
    """
    hops = [h.strip() for h in request.headers.get("X-Forwarded-For", "").split(",") if h.strip()]
    if TRUSTED_PROXY_HOPS > 0 and len(hops) >= TRUSTED_PROXY_HOPS:
        return hops[-TRUSTED_PROXY_HOPS]
    return request.remote_addr or ""

def is_rate_limited(ip):
    now = time.time()
    _rate_store[ip] = [t for t in _rate_store[ip] if now - t < RATE_WINDOW]
    if len(_rate_store[ip]) >= RATE_LIMIT: return True
    _rate_store[ip].append(now)
    return False

def get_current_term_label():
    """いまの学期。4/1〜9/20 が前期、それ以外は後期

    DB の履修期名は前期/後期の2種に正規化済み（通年の授業は両方に展開されている）。
    """
    now = datetime.datetime.now(JST)
    return '前期' if (4, 1) <= (now.month, now.day) <= (9, 20) else '後期'

def get_current_year():
    """いまの年度。日本の年度は 4/1 始まりなので 1〜3月は前年扱い"""
    now = datetime.datetime.now(JST)
    return now.year if now.month >= 4 else now.year - 1

def get_available_years():
    """DB に入っている年度（新しい順）。年度列が無い古い DB でも落ちないようにする"""
    try:
        conn = sqlite3.connect(f"file:{DB_NAME}?mode=ro", uri=True)
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(schedules)")}
            if "年度" not in cols:
                return []
            return [r[0] for r in conn.execute(
                "SELECT DISTINCT 年度 FROM schedules WHERE 年度 IS NOT NULL ORDER BY 年度 DESC")]
        finally:
            conn.close()
    except Exception:
        return []

def resolve_year(requested, available):
    """選ばれた年度を決める。未指定・不正なら「いまの年度」、無ければいちばん新しい年度"""
    if not available:
        return None
    try:
        if requested is not None and int(requested) in available:
            return int(requested)
    except (TypeError, ValueError):
        pass
    current = get_current_year()
    return current if current in available else available[0]

def resolve_term(requested):
    return requested if requested in VALID_TERMS else get_current_term_label()

MAX_PERIOD = max(PERIODS)

def resolve_span(requested):
    """「続けて使う」コマ数。1〜3。不正な値は1（絞り込みなし）"""
    try:
        n = int(requested)
    except (TypeError, ValueError):
        return 1
    return n if n in (1, 2, 3) else 1

def free_until(room, period, occupied_at):
    """room が period から続けて空いている最後の時限。period 自体が埋まっていれば period - 1"""
    last = period - 1
    for p in range(period, MAX_PERIOD + 1):
        if room in occupied_at.get(p, ()):
            break
        last = p
    return last

def period_end_dt(day_str, period_num):
    """指定の曜日・時限の終了日時（今週分）を返す"""
    day_map = {'月':0,'火':1,'水':2,'木':3,'金':4,'土':5}
    now = datetime.datetime.now(JST)
    target_wd = day_map.get(day_str, 0)
    delta = (target_wd - now.weekday()) % 7
    target_date = (now + datetime.timedelta(days=delta)).date()
    end_str = PERIODS[period_num][1]
    h, m = map(int, end_str.split(':'))
    return datetime.datetime(target_date.year, target_date.month, target_date.day,
                             h, m, tzinfo=JST)

def init_reserve_db():
    conn = sqlite3.connect(RESERVE_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            room        TEXT NOT NULL,
            building    TEXT NOT NULL,
            day         TEXT NOT NULL,
            period      INTEGER NOT NULL,
            name        TEXT NOT NULL,
            purpose     TEXT,
            cancel_code TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            expires_at  TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_res_room ON reservations (room, day, period)")
    conn.commit(); conn.close()

def cleanup_expired():
    """時限終了済みの予約を自動削除"""
    now = datetime.datetime.now(JST).isoformat()
    conn = sqlite3.connect(RESERVE_DB)
    conn.execute("DELETE FROM reservations WHERE expires_at < ?", (now,))
    conn.commit(); conn.close()

CANCEL_CODE_ALPHABET = string.ascii_uppercase + string.digits

def make_cancel_code():
    """仮予約・報告を取り消すための6文字のコード

    random は疑似乱数で、出力を観察すると続きを予測できる。他人の仮予約を勝手に
    取り消せないよう、暗号論的に安全な secrets を使う（36^6 ≒ 21億通り）。
    """
    return ''.join(secrets.choice(CANCEL_CODE_ALPHABET) for _ in range(6))

def get_reservations(day, period):
    """指定曜日・時限の予約一覧を返す"""
    conn = sqlite3.connect(RESERVE_DB)
    rows = conn.execute(
        "SELECT id, room, building, name, purpose, created_at FROM reservations WHERE day=? AND period=?",
        (day, period)
    ).fetchall()
    conn.close()
    return [{'id':r[0],'room':r[1],'building':r[2],'name':r[3],'purpose':r[4],'created_at':r[5]} for r in rows]

init_reserve_db()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-L1T1CDZ05N"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());
      gtag('config', 'G-L1T1CDZ05N');
    </script>
    <title>RoomRadar — 日大理工 空き教室</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0a0a0f;
            --surface: #13131a;
            --surface2: #1c1c26;
            --border: rgba(255,255,255,0.07);
            --text: #f0f0f5;
            --muted: #6b6b80;
            --tower-color: #6c8fff;
            --tower-bg: rgba(108,143,255,0.08);
            --tower-border: rgba(108,143,255,0.3);
            --surugadai-color: #4dd9a0;
            --surugadai-bg: rgba(77,217,160,0.08);
            --surugadai-border: rgba(77,217,160,0.3);
            --funabashi-color: #ff8c5a;
            --funabashi-bg: rgba(255,140,90,0.08);
            --funabashi-border: rgba(255,140,90,0.3);
            --accent: #6c8fff;
            --radius: 14px;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Noto Sans JP', sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            padding: 0 0 env(safe-area-inset-bottom) 0;
        }

        /* ── ノイズ背景 ── */
        body::before {
            content: '';
            position: fixed; inset: 0;
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.03'/%3E%3C/svg%3E");
            pointer-events: none; z-index: 0;
        }

        .wrap { max-width: 480px; margin: 0 auto; padding: 24px 16px; position: relative; z-index: 1; }

        /* ── レスポンシブ ── */
        @media (min-width: 768px) {
            .wrap { max-width: 760px; padding: 40px 32px; }
            .logo { font-size: 2.6rem; }
            .subtitle { font-size: 0.92rem; }
            .card { padding: 28px; }
            .form-grid { grid-template-columns: 1fr 1fr 2fr; }
            .form-full { grid-column: auto; }
            /* .room-grid の列数は「教室カード」節の末尾で定義（基本ルールより後に置かないと負ける） */
        }
        @media (min-width: 1100px) {
            .wrap { max-width: 1100px; padding: 48px 40px; }
            .page-cols { display: grid; grid-template-columns: 320px 1fr; gap: 32px; align-items: start; }
            .sidebar { position: sticky; top: 28px; }
            .logo { font-size: 2.8rem; }
            /* .room-grid の列数は「教室カード」節の末尾で定義 */
            .modal { border-radius: 20px; max-width: 460px; margin: auto; }
            .modal-overlay { align-items: center; }
        }

        /* ── ヘッダー ── */
        header { margin-bottom: 28px; }
        .logo {
            font-family: 'Syne', sans-serif;
            font-size: 2rem; font-weight: 800;
            letter-spacing: -0.03em;
            background: linear-gradient(135deg, #fff 0%, var(--accent) 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            background-clip: text;
            user-select: none;
            -webkit-user-select: none;
        }
        .logo span { font-weight: 700; opacity: 0.5; font-size: 1.1rem; }
        .logo-link { text-decoration: none; display: inline-block; }
        .subtitle { color: var(--muted); font-size: 0.82rem; margin-top: 4px; letter-spacing: 0.03em; }

        /* ── 現在時刻バッジ ── */
        .now-badge {
            display: inline-flex; align-items: center; gap: 6px;
            background: var(--surface2); border: 1px solid var(--border);
            border-radius: 99px; padding: 5px 12px; font-size: 0.78rem;
            color: var(--muted); margin-top: 10px;
        }
        .now-badge .dot { width: 6px; height: 6px; border-radius: 50%; background: #4dd9a0; animation: pulse 2s infinite; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

        /* ── 検索フォーム ── */
        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 20px;
            margin-bottom: 16px;
        }

        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }
        .form-full { grid-column: 1 / -1; }

        label { display: block; font-size: 0.72rem; font-weight: 700; color: var(--muted); letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 6px; }

        select {
            width: 100%; padding: 12px 14px;
            background: var(--surface2); border: 1px solid var(--border);
            border-radius: 10px; color: var(--text); font-size: 0.95rem;
            font-family: 'Noto Sans JP', sans-serif;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%236b6b80' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
            background-repeat: no-repeat; background-position: right 12px center;
            cursor: pointer; transition: border-color 0.2s;
        }
        select:focus { outline: none; border-color: var(--accent); }

        .btn-search {
            width: 100%; padding: 15px;
            background: var(--accent);
            border: none; border-radius: 10px;
            color: #fff; font-size: 1rem; font-weight: 700;
            font-family: 'Noto Sans JP', sans-serif;
            cursor: pointer; letter-spacing: 0.04em;
            transition: opacity 0.2s, transform 0.1s;
            position: relative; overflow: hidden;
        }
        .btn-search:active { transform: scale(0.98); }
        .btn-search:hover { opacity: 0.88; }

        /* ── 報告済み教室スタイル ── */
        .room-card.reported {
            opacity: 0.45;
            filter: grayscale(0.6);
            cursor: not-allowed;
        }
        .room-card.reported .room-number { text-decoration: line-through; }
        .reported-badge {
            position: absolute; top: 6px; right: 6px;
            font-size: 0.52rem; font-weight: 700; padding: 2px 5px;
            border-radius: 4px; background: rgba(255,80,80,0.15);
            color: #ff6060; border: 1px solid rgba(255,80,80,0.3);
            line-height: 1.4;
        }
        .btn-report {
            width: 100%; margin-top: 12px; padding: 11px;
            background: rgba(255,80,80,0.08); border: 1px solid rgba(255,80,80,0.25);
            border-radius: 10px; color: #ff6060; font-size: 0.85rem; font-weight: 700;
            font-family: 'Noto Sans JP', sans-serif; cursor: pointer;
            transition: background 0.2s;
        }
        .btn-report:hover { background: rgba(255,80,80,0.15); }
        .report-count-note {
            font-size: 0.72rem; color: var(--muted); text-align: center;
            margin-top: 8px;
        }

        /* ── 免責事項バナー ── */
        .disclaimer {
            display: flex; align-items: flex-start; gap: 10px;
            background: rgba(255,200,60,0.06);
            border: 1px solid rgba(255,200,60,0.2);
            border-radius: 10px; padding: 12px 14px;
            font-size: 0.78rem; color: #b8a060;
            line-height: 1.6; margin-bottom: 14px;
        }
        .disclaimer-icon { font-size: 1rem; flex-shrink: 0; margin-top: 1px; }
        /* いま以外の年度・学期を見ているときの注意。危険ではないので青系にする */
        .disclaimer.past-view {
            background: rgba(108,143,255,0.07);
            border-color: rgba(108,143,255,0.28);
            color: #8ea6ff;
        }
        .disclaimer.past-view strong { color: var(--text); }

        /* ── 結果ヘッダー ── */
        .result-meta {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 14px;
        }
        .result-label { font-size: 0.78rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }
        .count-chip {
            font-family: 'Syne', sans-serif; font-size: 0.9rem; font-weight: 700;
            background: var(--surface2); border: 1px solid var(--border);
            padding: 4px 12px; border-radius: 99px; color: var(--text);
        }
        .count-chip em { color: var(--accent); font-style: normal; }

        /* ── 検索フィードバック（更新が分かるように） ── */
        .btn-search.loading { pointer-events: none; }
        .btn-search .btn-in { display: inline-flex; align-items: center; justify-content: center; gap: 9px; }
        .btn-search .spinner {
            width: 15px; height: 15px; border-radius: 50%;
            border: 2px solid rgba(255,255,255,0.45); border-top-color: #fff;
            display: none; animation: btnspin 0.7s linear infinite;
        }
        .btn-search.loading .spinner { display: inline-block; }
        @keyframes btnspin { to { transform: rotate(360deg); } }

        .result-meta { scroll-margin-top: 18px; border-radius: 12px; }
        @keyframes resultFlash {
            0%   { box-shadow: 0 0 0 0 rgba(108,143,255,0); background: rgba(108,143,255,0); }
            18%  { box-shadow: 0 0 0 3px rgba(108,143,255,0.45); background: rgba(108,143,255,0.14); }
            100% { box-shadow: 0 0 0 0 rgba(108,143,255,0); background: rgba(108,143,255,0); }
        }
        .result-meta.flash { padding: 8px 12px; margin: -8px -12px 6px; animation: resultFlash 1.8s ease-out; }
        @keyframes chipPop {
            0%   { transform: scale(1);    box-shadow: 0 0 0 0 rgba(108,143,255,0); }
            30%  { transform: scale(1.2);  box-shadow: 0 0 0 5px rgba(108,143,255,0.35); }
            100% { transform: scale(1);    box-shadow: 0 0 0 0 rgba(108,143,255,0); }
        }
        .count-chip.pop { animation: chipPop 0.8s ease-out; }

        /* ── 校舎セクション ── */
        .building-section { margin-bottom: 20px; }
        .building-label {
            display: flex; align-items: center; gap: 8px;
            font-size: 0.72rem; font-weight: 700; letter-spacing: 0.1em;
            text-transform: uppercase; margin-bottom: 10px;
            padding-bottom: 8px; border-bottom: 1px solid var(--border);
        }
        .building-label .badge {
            font-size: 0.68rem; padding: 2px 8px; border-radius: 99px; font-weight: 700;
        }
        .badge-tower    { background: var(--tower-bg);     color: var(--tower-color);     border: 1px solid var(--tower-border); }
        .badge-surugadai{ background: var(--surugadai-bg); color: var(--surugadai-color); border: 1px solid var(--surugadai-border); }
        .badge-funabashi{ background: var(--funabashi-bg); color: var(--funabashi-color); border: 1px solid var(--funabashi-border); }

        /* ── 教室カード ── */
        /* 列は minmax(0, 1fr)。1fr だけだと「S1704/07/13/16」「521/2/3/4/5/7/8/9/10」のような
           折り返し位置のない教室名が列を押し広げ、スマホ幅で右にはみ出す */
        .room-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
        @media (max-width: 340px)  { .room-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
        @media (min-width: 768px)  { .room-grid { grid-template-columns: repeat(5, minmax(0, 1fr)); } }
        @media (min-width: 1100px) { .room-grid { grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 10px; } }

        .room-card {
            border-radius: 10px; padding: 12px 8px;
            text-align: center; cursor: pointer;
            transition: transform 0.15s, opacity 0.15s;
            border: 1px solid transparent;
            position: relative;
            min-width: 0;
        }
        .room-card:active { transform: scale(0.96); }

        .room-card.tower     { background: var(--tower-bg);     border-color: var(--tower-border); }
        .room-card.surugadai { background: var(--surugadai-bg); border-color: var(--surugadai-border); }
        .room-card.funabashi { background: var(--funabashi-bg); border-color: var(--funabashi-border); }

        .room-number {
            font-family: 'Syne', sans-serif; font-size: 1.15rem; font-weight: 700;
            display: block; line-height: 1.2;
            overflow-wrap: anywhere;  /* 長い教室名はカード内で折り返す */
        }
        .room-card.tower     .room-number { color: var(--tower-color); }
        .room-card.surugadai .room-number { color: var(--surugadai-color); }
        .room-card.funabashi .room-number { color: var(--funabashi-color); }

        .room-bldg { font-size: 0.65rem; color: var(--muted); margin-top: 3px; display: block; overflow-wrap: anywhere; }
        /* 何限まで続けて空いているか。空き時間が長い教室ほど使いやすいので目に入る位置に */
        .room-span {
            display: inline-block; margin-top: 4px;
            font-size: 0.62rem; font-weight: 700; letter-spacing: 0.02em;
            padding: 1px 7px; border-radius: 99px;
            background: rgba(255,255,255,0.08); color: var(--text);
        }

        /* 予約中バッジ */
        .room-card.reserved::after {
            content: '予約中';
            position: absolute; top: 5px; right: 5px;
            font-size: 0.55rem; font-weight: 700;
            background: rgba(255,255,255,0.1); color: var(--muted);
            padding: 1px 5px; border-radius: 4px;
        }

        /* ── モーダル（仮予約） ── */
        .modal-overlay {
            display: none; position: fixed; inset: 0;
            background: rgba(0,0,0,0.7); backdrop-filter: blur(6px);
            z-index: 100; align-items: flex-end; justify-content: center;
        }
        .modal-overlay.open { display: flex; }

        .modal {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 20px 20px 0 0;
            padding: 28px 24px 36px;
            width: 100%; max-width: 480px;
            animation: slideUp 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        @keyframes slideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }

        .modal-handle { width: 40px; height: 4px; background: var(--border); border-radius: 2px; margin: 0 auto 20px; }
        .modal-title { font-family: 'Syne', sans-serif; font-size: 1.3rem; font-weight: 800; margin-bottom: 6px; }
        .modal-room-info { color: var(--muted); font-size: 0.85rem; margin-bottom: 20px; }

        .modal-notice {
            background: rgba(255,200,60,0.08); border: 1px solid rgba(255,200,60,0.2);
            border-radius: 10px; padding: 12px 14px; font-size: 0.78rem;
            color: #ffc83c; line-height: 1.6; margin-bottom: 20px;
        }
        .modal-notice strong { display: block; margin-bottom: 2px; }

        .modal-form label { color: var(--muted); font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; display: block; margin-bottom: 6px; margin-top: 14px; }
        .modal-form input, .modal-form textarea {
            width: 100%; padding: 12px 14px;
            background: var(--surface2); border: 1px solid var(--border);
            border-radius: 10px; color: var(--text); font-size: 0.9rem;
            font-family: 'Noto Sans JP', sans-serif;
        }
        .modal-form input:focus, .modal-form textarea:focus { outline: none; border-color: var(--accent); }
        .modal-form textarea { resize: none; height: 72px; }

        .modal-actions { display: grid; grid-template-columns: 1fr 2fr; gap: 10px; margin-top: 18px; }
        .btn-cancel {
            padding: 13px; background: var(--surface2); border: 1px solid var(--border);
            border-radius: 10px; color: var(--muted); font-size: 0.9rem; font-weight: 700;
            font-family: 'Noto Sans JP', sans-serif; cursor: pointer;
        }
        .btn-reserve {
            padding: 13px; background: var(--accent); border: none;
            border-radius: 10px; color: #fff; font-size: 0.9rem; font-weight: 700;
            font-family: 'Noto Sans JP', sans-serif; cursor: pointer;
        }

        /* ── 予約済みバッジ ── */
        .room-card.has-reserve { position: relative; }
        .reserve-badge {
            position: absolute; top: 6px; right: 6px;
            font-size: 0.55rem; font-weight: 700; padding: 2px 6px;
            border-radius: 4px; background: rgba(255,200,60,0.15);
            color: #ffc83c; border: 1px solid rgba(255,200,60,0.3);
            line-height: 1.4;
        }

        /* ── 予約一覧パネル ── */
        .reserve-panel {
            background: var(--surface2); border: 1px solid var(--border);
            border-radius: 10px; padding: 14px; margin-top: 10px;
            font-size: 0.82rem;
        }
        .reserve-panel-title {
            font-size: 0.72rem; font-weight: 700; color: var(--muted);
            text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 10px;
        }
        .reserve-item {
            display: flex; justify-content: space-between; align-items: center;
            padding: 8px 0; border-bottom: 1px solid var(--border);
        }
        .reserve-item:last-child { border-bottom: none; }
        .reserve-item-name { font-weight: 700; color: var(--text); }
        .reserve-item-purpose { color: var(--muted); font-size: 0.75rem; margin-top: 2px; }
        .reserve-item-room {
            font-size: 0.72rem; padding: 2px 8px; border-radius: 4px;
            background: var(--surface); color: var(--muted);
        }

        /* ── キャンセルコード表示 ── */
        .cancel-code-box {
            background: rgba(108,143,255,0.08); border: 1px solid rgba(108,143,255,0.3);
            border-radius: 10px; padding: 14px; margin-top: 14px; text-align: center;
        }
        .cancel-code-label { font-size: 0.72rem; color: var(--muted); margin-bottom: 6px; }
        .cancel-code-value {
            font-family: 'Syne', sans-serif; font-size: 1.8rem; font-weight: 800;
            color: var(--tower-color); letter-spacing: 0.15em;
        }
        .cancel-code-note { font-size: 0.72rem; color: var(--muted); margin-top: 6px; }

        /* ── トースト ── */
        .toast {
            display: none; position: fixed; bottom: 32px; left: 50%; transform: translateX(-50%);
            background: var(--surface); border: 1px solid var(--border);
            border-radius: 99px; padding: 10px 20px; font-size: 0.85rem;
            color: var(--text); z-index: 200; white-space: nowrap;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        }
        .toast.show { display: block; animation: fadeInOut 2.5s ease forwards; }
        @keyframes fadeInOut {
            0%{opacity:0;transform:translateX(-50%) translateY(10px)}
            15%{opacity:1;transform:translateX(-50%) translateY(0)}
            75%{opacity:1}
            100%{opacity:0}
        }

        /* ── 空き無し ── */
        .empty-state { text-align: center; padding: 40px 20px; color: var(--muted); font-size: 0.9rem; }
        .empty-state .icon { font-size: 2.5rem; display: block; margin-bottom: 10px; }

        /* ── 公式サービスとの誤認防止のための常設表記 ── */
        .compliance-footer {
            margin-top: 24px; padding: 16px 0 32px;
            font-size: 0.7rem; color: var(--muted); text-align: center; line-height: 1.6;
        }

        /* ── テスト運用・非公式の控えめ表記 ── */
        .test-banner {
            display: flex; align-items: center; gap: 8px;
            margin-bottom: 20px;
            font-size: 0.72rem; color: var(--muted); line-height: 1.5;
        }
        .test-tag {
            flex-shrink: 0; font-family: 'Syne', sans-serif; font-weight: 700;
            font-size: 0.56rem; letter-spacing: 0.1em;
            background: var(--surface2); color: var(--muted);
            border: 1px solid var(--border);
            padding: 3px 7px; border-radius: 5px;
        }
        .test-banner strong { color: #9a9ab0; font-weight: 600; }

        /* ── 使い方フッター ── */
        .help-footer {
            margin-top: 40px; padding-top: 24px;
            border-top: 1px solid var(--border);
        }
        .help-title {
            font-size: 0.72rem; font-weight: 700; color: var(--muted);
            text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 14px;
        }
        .help-item {
            display: flex; gap: 12px; align-items: flex-start;
            padding: 12px 0; border-bottom: 1px solid var(--border);
        }
        .help-item:last-child { border-bottom: none; }
        .help-icon {
            width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0;
            display: flex; align-items: center; justify-content: center;
            font-size: 1rem;
        }
        .help-icon.blue  { background: var(--tower-bg);     border: 1px solid var(--tower-border); }
        .help-icon.green { background: var(--surugadai-bg); border: 1px solid var(--surugadai-border); }
        .help-icon.red   { background: rgba(255,80,80,0.08); border: 1px solid rgba(255,80,80,0.25); }
        .help-icon.yellow{ background: rgba(255,200,60,0.08); border: 1px solid rgba(255,200,60,0.2); }
        .help-text-title { font-size: 0.85rem; font-weight: 700; color: var(--text); margin-bottom: 3px; }
        .help-text-desc  { font-size: 0.75rem; color: var(--muted); line-height: 1.6; }

        /* ── エラー ── */
        .error-card { background: rgba(255,80,80,0.08); border: 1px solid rgba(255,80,80,0.2); border-radius: var(--radius); padding: 16px; color: #ff6060; font-size: 0.85rem; }
    </style>
</head>
<body>
<div class="wrap">

    <!-- テスト運用・非公式の明示（誤認防止・控えめ表記） -->
    <div class="test-banner">
        <span class="test-tag">TEST</span>
        <span><strong>テスト運用中</strong>の非公式サービスです（学生開発・大学公式ではありません）。</span>
    </div>

    <!-- ヘッダー -->
    <header>
        <a href="https://nu-roomradar.github.io/nust-room-search/" class="logo-link"><div class="logo">RoomRadar <span>β</span></div></a>
        <div class="subtitle">日大理工学部 · 空き教室リアルタイム検索</div>
        <div class="now-badge">
            <span class="dot"></span>
            <span id="clock">--:--</span>
            <span>·</span>
            <span id="now-period">現在時限 検出中…</span>
        </div>
    </header>

    <!-- PC: 2カラム / スマホ・タブレット: 1カラム -->
    <div class="page-cols">

        <!-- 左サイドバー（PC）/ 上部（スマホ） -->
        <div class="sidebar">
            <div class="card">
                <form method="POST" id="search-form">
                    <div class="form-grid">
                        <div>
                            <label>年度</label>
                            <select name="year" id="sel-year">
                                {% for y in available_years %}
                                <option value="{{ y }}" {% if selected_year == y %}selected{% endif %}>{{ y }}年度</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div>
                            <label>学期</label>
                            <select name="term" id="sel-term">
                                {% for t in available_terms %}
                                <option value="{{ t }}" {% if selected_term == t %}selected{% endif %}>{{ t }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div>
                            <label>曜日</label>
                            <select name="day" id="sel-day">
                                {% for d in ["月", "火", "水", "木", "金", "土"] %}
                                <option value="{{ d }}" {% if selected_day == d %}selected{% endif %}>{{ d }}曜日</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div>
                            <label>時限</label>
                            <select name="period" id="sel-period">
                                {% for p in range(1, 7) %}
                                <option value="{{ p }}" {% if selected_period == p %}selected{% endif %}>{{ p }}限 ({{ period_times[p] }})</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div>
                            <label>校舎</label>
                            <select name="building">
                                <option value="all">すべての校舎</option>
                                <option value="tower"     {% if selected_building == 'tower'     %}selected{% endif %}>🏢 タワースコラ</option>
                                <option value="main"      {% if selected_building == 'main'      %}selected{% endif %}>🏫 駿河台校舎</option>
                                <option value="funabashi" {% if selected_building == 'funabashi' %}selected{% endif %}>🏛 船橋校舎</option>
                            </select>
                        </div>
                        <div>
                            <label>続けて使う</label>
                            <select name="span" id="sel-span">
                                <option value="1" {% if selected_span == 1 %}selected{% endif %}>1コマ</option>
                                <option value="2" {% if selected_span == 2 %}selected{% endif %}>2コマ以上</option>
                                <option value="3" {% if selected_span == 3 %}selected{% endif %}>3コマ以上</option>
                            </select>
                        </div>
                    </div>
                    <button type="submit" class="btn-search" id="btn-search"><span class="btn-in"><span class="spinner"></span><span class="btn-text">空き教室を検索</span></span></button>
                </form>
            </div>
        </div><!-- /sidebar -->

        <!-- 右: 結果エリア（PC）/ 下部（スマホ） -->
        <div class="results-area">

            <!-- エラー -->
            {% if error_message %}
            <div class="error-card">⚠ {{ error_message }}</div>
            {% endif %}

            <!-- 結果 -->
            {% if empty_rooms is not none and not error_message %}
            {% if not is_current_view %}
            <div class="disclaimer past-view">
                <span class="disclaimer-icon">🗓</span>
                <span><strong>{% if selected_year %}{{ selected_year }}年度 {% endif %}{{ selected_term }}</strong>の時間割を表示しています（現在は{{ current_year }}年度 {{ current_term }}）。いま空いている教室を探す場合は、年度と学期を戻してください。</span>
            </div>
            {% endif %}
            <div class="disclaimer">
                <span class="disclaimer-icon">⚠</span>
                <span>時間割に登録されていないゲリラ授業・急遽変更が行われている場合があります。実際に教室を使用する前に、ドア越しに確認することをおすすめします。</span>
            </div>
            <div class="result-meta" id="result-meta">
                <span class="result-label">{% if selected_year %}{{ selected_year }}年度 {% endif %}{{ selected_term }} {{ selected_day }}曜 {{ selected_period }}限{% if selected_span > 1 %}から{{ selected_span }}コマ続けて{% endif %} の空き教室</span>
                <span class="count-chip" id="count-chip"><em>{{ empty_rooms|length }}</em> 室</span>
            </div>

            {% if empty_rooms %}
                {% set tower_rooms     = empty_rooms | selectattr('building', 'equalto', 'タワースコラ') | list %}
                {% set surugadai_rooms = empty_rooms | selectattr('building', 'equalto', '駿河台校舎') | list %}
                {% set funabashi_rooms = empty_rooms | selectattr('building', 'equalto', '船橋校舎') | list %}

                {% if tower_rooms %}
                <div class="building-section">
                    <div class="building-label">
                        <span class="badge badge-tower">タワースコラ</span>
                        {{ tower_rooms|length }}室
                    </div>
                    <div class="room-grid">
                    {% for room in tower_rooms %}
                        {% set cnt = report_counts.get(room.name, 0) %}
                        {% set is_reported = cnt >= report_threshold %}
                        <div class="room-card tower {% if is_reported %}reported{% endif %} has-report"
                             onclick="{% if not is_reported %}openModal('{{ room.name }}', 'タワースコラ'){% endif %}">
                            {% if is_reported %}<span class="reported-badge">使用中の可能性</span>{% endif %}
                            <span class="room-number">{{ room.name }}</span>
                            {% if room.free_until > selected_period %}<span class="room-span">〜{{ room.free_until }}限</span>{% endif %}
                            <span class="room-bldg">
                                {%- set rcnt = reserve_counts.get(room.name, 0) -%}
                                {%- if rcnt > 0 -%}📋{{ rcnt }}件予約中　{%- endif -%}
                                {%- if cnt > 0 -%}⚠{{ cnt }}件報告{%- endif -%}
                                {%- if rcnt == 0 and cnt == 0 -%}タワースコラ{%- endif -%}
                            </span>
                        </div>
                    {% endfor %}
                    </div>
                </div>
                {% endif %}

                {% if surugadai_rooms %}
                <div class="building-section">
                    <div class="building-label">
                        <span class="badge badge-surugadai">駿河台校舎</span>
                        {{ surugadai_rooms|length }}室
                    </div>
                    <div class="room-grid">
                    {% for room in surugadai_rooms %}
                        {% set cnt = report_counts.get(room.name, 0) %}
                        {% set is_reported = cnt >= report_threshold %}
                        <div class="room-card surugadai {% if is_reported %}reported{% endif %} has-report"
                             onclick="{% if not is_reported %}openModal('{{ room.name }}', '駿河台校舎'){% endif %}">
                            {% if is_reported %}<span class="reported-badge">使用中の可能性</span>{% endif %}
                            <span class="room-number">{{ room.name }}</span>
                            {% if room.free_until > selected_period %}<span class="room-span">〜{{ room.free_until }}限</span>{% endif %}
                            <span class="room-bldg">
                                {%- set rcnt = reserve_counts.get(room.name, 0) -%}
                                {%- if rcnt > 0 -%}📋{{ rcnt }}件予約中　{%- endif -%}
                                {%- if cnt > 0 -%}⚠{{ cnt }}件報告{%- endif -%}
                                {%- if rcnt == 0 and cnt == 0 -%}駿河台校舎{%- endif -%}
                            </span>
                        </div>
                    {% endfor %}
                    </div>
                </div>
                {% endif %}

                {% if funabashi_rooms %}
                <div class="building-section">
                    <div class="building-label">
                        <span class="badge badge-funabashi">船橋校舎</span>
                        {{ funabashi_rooms|length }}室
                    </div>
                    <div class="room-grid">
                    {% for room in funabashi_rooms %}
                        {% set cnt = report_counts.get(room.name, 0) %}
                        {% set is_reported = cnt >= report_threshold %}
                        <div class="room-card funabashi {% if is_reported %}reported{% endif %} has-report"
                             onclick="{% if not is_reported %}openModal('{{ room.name }}', '船橋校舎'){% endif %}">
                            {% if is_reported %}<span class="reported-badge">使用中の可能性</span>{% endif %}
                            <span class="room-number">{{ room.name }}</span>
                            {% if room.free_until > selected_period %}<span class="room-span">〜{{ room.free_until }}限</span>{% endif %}
                            <span class="room-bldg">
                                {%- set rcnt = reserve_counts.get(room.name, 0) -%}
                                {%- if rcnt > 0 -%}📋{{ rcnt }}件予約中　{%- endif -%}
                                {%- if cnt > 0 -%}⚠{{ cnt }}件報告{%- endif -%}
                                {%- if rcnt == 0 and cnt == 0 -%}船橋校舎{%- endif -%}
                            </span>
                        </div>
                    {% endfor %}
                    </div>
                </div>
                {% endif %}

            {% else %}
            <div class="empty-state">
                <span class="icon">🔍</span>
                条件に合う空き教室はありませんでした。
            </div>
            {% endif %}
            {% endif %}

        </div><!-- /results-area -->
    </div><!-- /page-cols -->

    <!-- 使い方フッター -->
    <div class="wrap">
        <div class="help-footer">
            <div class="help-title">💡 使い方・機能説明</div>

            <div class="help-item">
                <div class="help-icon blue">🔍</div>
                <div>
                    <div class="help-text-title">空き教室を検索する</div>
                    <div class="help-text-desc">曜日・時限・校舎を選んで「空き教室を検索」を押すと、授業が入っていない教室を一覧表示します。現在の曜日・時限は自動で選択されます。</div>
                </div>
            </div>

            <div class="help-item">
                <div class="help-icon green">📋</div>
                <div>
                    <div class="help-text-title">仮予約する（RoomRadar上のみ）</div>
                    <div class="help-text-desc">教室カードをタップするとモーダルが開きます。お名前と利用目的を入力して「仮予約する」を押すと、他のユーザーに共有されます。<br>⚠ 大学公式の予約ではなく、使用権を保証するものではありません。</div>
                </div>
            </div>

            <div class="help-item">
                <div class="help-icon red">⚠</div>
                <div>
                    <div class="help-text-title">「実は使われていた」を報告する</div>
                    <div class="help-text-desc">教室カードをタップして「⚠ 実は使われていた」ボタンを押すと報告できます。<strong style="color:var(--text)">2件以上</strong>の報告が集まった教室はグレーアウトされ「使用中の可能性」と表示されます。報告は本人がいつでも取り消せます。また、時限終了後に自動でリセットされます。</div>
                </div>
            </div>

            <div class="help-item">
                <div class="help-icon yellow">🏢</div>
                <div>
                    <div class="help-text-title">校舎の色分けについて</div>
                    <div class="help-text-desc">
                        <span style="color:var(--tower-color)">■ 青：タワースコラ</span>　
                        <span style="color:var(--surugadai-color)">■ 緑：駿河台校舎</span>　
                        <span style="color:var(--funabashi-color)">■ オレンジ：船橋校舎</span>
                    </div>
                </div>
            </div>

            <div class="help-item">
                <div class="help-icon yellow">⚡</div>
                <div>
                    <div class="help-text-title">注意事項</div>
                    <div class="help-text-desc">時間割に登録されていないゲリラ授業や急遽変更が行われている場合があります。実際に入室する前に、ドア越しに確認することをおすすめします。本システムは日大理工学部の学生が自主的に開発・運営しています。</div>
                </div>
            </div>
        </div>
    </div>

    <!-- 公式サービスとの誤認防止のための常設表記 -->
    <div class="wrap">
        <div class="compliance-footer">
            © 2026 RoomRadar — 日本大学「自主創造プロジェクト」の一環として理工学部の学生が開発・運営しています。本サービスは大学公式のものではなく、現在テスト運用中です。学内での正式な提供については調整中です。
        </div>
    </div>

</div><!-- /wrap -->

<!-- 仮予約モーダル -->
<div class="modal-overlay" id="modal" onclick="handleOverlayClick(event)">
    <div class="modal">
        <div class="modal-handle"></div>
        <div class="modal-title" id="modal-title">教室名</div>
        <div class="modal-room-info" id="modal-info">校舎 · 現在検索中の時間帯</div>

        <div class="modal-notice">
            <strong>⚠ これはRoomRadar上の仮予約です</strong>
            大学公式の予約システムではありません。教室の使用権を保証するものではなく、
            他の利用者への情報共有を目的としています。
        </div>

        <div class="modal-form">
            <label>お名前 / グループ名</label>
            <input type="text" id="reserve-name" placeholder="例: 二川・物理学科" maxlength="30">
            <label>利用目的（任意）</label>
            <textarea id="reserve-note" placeholder="例: グループ課題の打ち合わせ"></textarea>
        </div>

        <button class="btn-report" onclick="submitReport()">⚠ 実は使われていた</button>
        <div class="report-count-note" id="report-note"></div>
        <div class="modal-actions">
            <button class="btn-cancel" onclick="closeModal()">キャンセル</button>
            <button class="btn-reserve" onclick="submitReserve()">仮予約する</button>
        </div>
    </div>
</div>

<!-- トースト -->
<div class="toast" id="toast"></div>

<script>
// ── 時計 & 現在時限の自動検出 ──
const PERIODS = {
    1: ["09:00","10:30"], 2: ["10:40","12:10"], 3: ["13:00","14:30"],
    4: ["14:40","16:10"], 5: ["16:20","17:50"], 6: ["18:00","19:30"]
};
const DAYS = ["日","月","火","水","木","金","土"];

function toMin(t) { const [h,m] = t.split(':').map(Number); return h*60+m; }

function updateClock() {
    const now = new Date();
    const jst = new Date(now.toLocaleString('en', {timeZone:'Asia/Tokyo'}));
    const h = String(jst.getHours()).padStart(2,'0');
    const m = String(jst.getMinutes()).padStart(2,'0');
    document.getElementById('clock').textContent = h + ':' + m;

    const cur = h*60 + jst.getMinutes();
    let found = null;
    for (const [p, [s,e]] of Object.entries(PERIODS)) {
        if (cur >= toMin(s) && cur <= toMin(e)) { found = p; break; }
    }
    document.getElementById('now-period').textContent = found ? found + '限 授業中' : '授業時間外';
}
setInterval(updateClock, 1000);
updateClock();

// ── ページ読み込み時に現在の曜日・時限をセット（GETのみ） ──
{% if not searched %}
(function() {
    const now = new Date();
    const jst = new Date(now.toLocaleString('en', {timeZone:'Asia/Tokyo'}));
    const dayIdx = jst.getDay(); // 0=日
    const dayName = DAYS[dayIdx === 0 ? 1 : dayIdx]; // 日曜は月に
    const sel = document.getElementById('sel-day');
    for (let i = 0; i < sel.options.length; i++) {
        if (sel.options[i].value === dayName) { sel.selectedIndex = i; break; }
    }
    const cur = jst.getHours()*60 + jst.getMinutes();
    let period = 1;
    for (const [p, [s,e]] of Object.entries(PERIODS)) {
        if (cur >= toMin(s) && cur <= toMin(e)) { period = parseInt(p); break; }
        if (cur < toMin(s)) { period = Math.max(1, parseInt(p)-1); break; }
    }
    document.getElementById('sel-period').value = period;
})();
{% endif %}

// ── GA4: 検索イベント計測 ──
(function() {
    const form = document.getElementById('search-form');
    if (!form) return;
    form.addEventListener('submit', function() {
        if (typeof gtag === 'function') {
            gtag('event', 'search', {
                search_day:      document.getElementById('sel-day').value,
                search_period:   document.getElementById('sel-period').value,
                search_building: form.building.value
            });
        }
        // 押した瞬間のローディング表示（更新されることを明示）
        const btn = document.getElementById('btn-search');
        if (btn) {
            btn.classList.add('loading');
            const tx = btn.querySelector('.btn-text');
            if (tx) tx.textContent = '検索中…';
        }
    });
})();

// ── 検索後：結果へスクロール＋強調＋トースト（更新に気づけるように） ──
{% if searched and not error_message %}
window.addEventListener('load', function() {
    const meta = document.getElementById('result-meta');
    if (meta) {
        meta.scrollIntoView({ behavior: 'smooth', block: 'center' });
        setTimeout(function() {
            meta.classList.add('flash');
            const chip = document.getElementById('count-chip');
            if (chip) chip.classList.add('pop');
        }, 380);
    }
    showToast('✓ 検索しました — {{ empty_rooms|length }}室');
});
{% endif %}

// ── 仮予約モーダル ──
let currentRoom = '', currentBuilding = '';

function openModal(room, building) {
    currentRoom = room;
    currentBuilding = building;
    document.getElementById('modal-title').textContent = room;
    document.getElementById('modal-info').textContent =
        building + ' · {{ selected_day }}曜 {{ selected_period }}限';
    document.getElementById('reserve-name').value = '';
    document.getElementById('reserve-note').value = '';
    document.getElementById('modal').classList.add('open');
    updateReserveButton();
    updateReportButton();
}

function closeModal() {
    document.getElementById('modal').classList.remove('open');
}

function handleOverlayClick(e) {
    if (e.target === document.getElementById('modal')) closeModal();
}

async function submitReserve() {
    const name    = document.getElementById('reserve-name').value.trim();
    const purpose = document.getElementById('reserve-note').value.trim();
    if (!name) { showToast('⚠ お名前を入力してください'); return; }

    // すでに予約済みなら取り消し
    const storedCode = localStorage.getItem(`reserve_${currentRoom}_{{ selected_day }}_{{ selected_period }}`);
    if (storedCode) {
        const res = await fetch('/api/reserve/cancel', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({room: currentRoom, day: '{{ selected_day }}', period: {{ selected_period }}, cancel_code: storedCode})
        });
        const data = await res.json();
        if (data.ok) {
            localStorage.removeItem(`reserve_${currentRoom}_{{ selected_day }}_{{ selected_period }}`);
            closeModal();
            showToast('✓ 仮予約を取り消しました');
            setTimeout(() => location.reload(), 1000);
        }
        return;
    }

    // 新規予約
    const res = await fetch('/api/reserve', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            room: currentRoom, building: currentBuilding,
            day: '{{ selected_day }}', period: {{ selected_period }},
            name, purpose
        })
    });
    const data = await res.json();
    if (data.ok) {
        localStorage.setItem(`reserve_${currentRoom}_{{ selected_day }}_{{ selected_period }}`, data.cancel_code);
        if (typeof gtag === 'function') {
            gtag('event', 'reserve_room', { building: currentBuilding, room: currentRoom });
        }
        closeModal();
        showToast('✓ ' + currentRoom + ' を仮予約しました（RoomRadar上のみ）');
        setTimeout(() => location.reload(), 1000);
    } else if (data.error === 'rate_limited') {
        showToast('⚠ しばらく時間をおいて再試行してください');
    }
}

// ── 使用中報告 ──
async function submitReport() {
    const cancelCode = localStorage.getItem(`report_${currentRoom}_{{ selected_day }}_{{ selected_period }}`);
    
    // すでに報告済みなら取り消し
    if (cancelCode) {
        const res = await fetch('/api/report/cancel', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({room: currentRoom, day: '{{ selected_day }}', period: {{ selected_period }}, cancel_code: cancelCode})
        });
        const data = await res.json();
        if (data.ok) {
            localStorage.removeItem(`report_${currentRoom}_{{ selected_day }}_{{ selected_period }}`);
            closeModal();
            showToast('✓ 報告を取り消しました');
            setTimeout(() => location.reload(), 1000);
        }
        return;
    }

    // 新規報告
    const res = await fetch('/api/report', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({room: currentRoom, day: '{{ selected_day }}', period: {{ selected_period }}})
    });
    const data = await res.json();
    if (!data.ok) {
        showToast(data.error === 'already_reported' ? 'この教室はすでに報告済みです'
                : data.error === 'rate_limited' ? '操作が続いたため少し待ってからお試しください'
                : '報告できませんでした');
        return;
    }
    if (data.ok) {
        localStorage.setItem(`report_${currentRoom}_{{ selected_day }}_{{ selected_period }}`, data.cancel_code);
        if (typeof gtag === 'function') {
            gtag('event', 'report_room', { building: currentBuilding, room: currentRoom });
        }
        closeModal();
        showToast('⚠ 報告しました。ありがとうございます！');
        setTimeout(() => location.reload(), 1000);
    }
}

function updateReserveButton() {
    const btn  = document.querySelector('.btn-reserve');
    const code = localStorage.getItem(`reserve_${currentRoom}_{{ selected_day }}_{{ selected_period }}`);
    if (!btn) return;
    if (code) {
        btn.textContent = '✓ 予約済み（タップで取り消し）';
        btn.style.background = 'rgba(77,217,160,0.3)';
    } else {
        btn.textContent = '仮予約する';
        btn.style.background = '';
    }
}

function updateReportButton() {
    const btn = document.querySelector('.btn-report');
    const note = document.getElementById('report-note');
    if (!btn || !currentRoom) return;
    const cancelCode = localStorage.getItem(`report_${currentRoom}_{{ selected_day }}_{{ selected_period }}`);
    if (cancelCode) {
        btn.textContent = '✓ 報告済み（タップで取り消し）';
        btn.style.background = 'rgba(255,80,80,0.2)';
        if (note) note.textContent = '時限終了後に自動でリセットされます';
    } else {
        btn.textContent = '⚠ 実は使われていた';
        btn.style.background = '';
        if (note) note.textContent = '2件以上の報告で「使用中の可能性」と表示されます';
    }
}

function showToast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.remove('show');
    void t.offsetWidth;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2600);
}
</script>
</body>
</html>
"""

@app.route('/api/reserve', methods=['POST'])
def api_reserve():
    data = request.get_json(silent=True) or {}
    room    = str(data.get('room', '')).strip()[:20]
    building= str(data.get('building', '')).strip()[:20]
    day     = data.get('day', '')
    period  = data.get('period', 0)
    name    = str(data.get('name', '')).strip()[:30]
    purpose = str(data.get('purpose', '')).strip()[:60]

    if not room or not name or day not in VALID_DAYS or period not in VALID_PERIODS:
        return jsonify({'ok': False, 'error': 'invalid'}), 400

    ip = client_ip()
    if is_rate_limited(ip):
        return jsonify({'ok': False, 'error': 'rate_limited'}), 429

    cleanup_expired()
    expires     = period_end_dt(day, period).isoformat()
    cancel_code = make_cancel_code()
    created_at  = datetime.datetime.now(JST).isoformat()

    conn = sqlite3.connect(RESERVE_DB)
    conn.execute(
        "INSERT INTO reservations (room, building, day, period, name, purpose, cancel_code, created_at, expires_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (room, building, day, period, name, purpose, cancel_code, created_at, expires)
    )
    conn.commit()
    count = conn.execute(
        "SELECT COUNT(*) FROM reservations WHERE room=? AND day=? AND period=?",
        (room, day, period)
    ).fetchone()[0]
    conn.close()
    return jsonify({'ok': True, 'cancel_code': cancel_code, 'count': count})


@app.route('/api/reserve/cancel', methods=['POST'])
def api_reserve_cancel():
    data = request.get_json(silent=True) or {}
    room        = str(data.get('room', '')).strip()[:20]
    day         = data.get('day', '')
    period      = data.get('period', 0)
    cancel_code = str(data.get('cancel_code', '')).strip()[:10]
    if not room or not cancel_code:
        return jsonify({'ok': False}), 400
    # キャンセルコードの総当たりを防ぐため、取り消しにもレート制限をかける
    if is_rate_limited(client_ip()):
        return jsonify({'ok': False, 'error': 'rate_limited'}), 429

    conn = sqlite3.connect(RESERVE_DB)
    cur  = conn.cursor()
    cur.execute(
        "DELETE FROM reservations WHERE room=? AND day=? AND period=? AND cancel_code=?",
        (room, day, period, cancel_code)
    )
    deleted = cur.rowcount
    conn.commit(); conn.close()
    return jsonify({'ok': deleted > 0})


@app.route('/api/reserve/list', methods=['GET'])
def api_reserve_list():
    day    = request.args.get('day', '')
    period = request.args.get('period', 0, type=int)
    if day not in VALID_DAYS or period not in VALID_PERIODS:
        return jsonify({'ok': False}), 400
    cleanup_expired()
    return jsonify({'ok': True, 'reservations': get_reservations(day, period)})


@app.route('/api/report', methods=['POST'])
def api_report():
    data = request.get_json(silent=True) or {}
    room   = str(data.get('room', '')).strip()[:20]
    day    = data.get('day', '')
    period = data.get('period', 0)
    if not room or day not in VALID_DAYS or period not in VALID_PERIODS:
        return jsonify({'ok': False, 'error': 'invalid'}), 400

    ip = client_ip()
    if is_rate_limited(ip):
        return jsonify({'ok': False, 'error': 'rate_limited'}), 429

    cleanup_reports()
    expires = period_end_dt(day, period).isoformat()
    cancel_code = make_cancel_code()
    reporter = reporter_id(ip)

    conn = sqlite3.connect(REPORTS_DB)
    try:
        conn.execute(
            "INSERT INTO reports (room, day, period, cancel_code, expires_at, reporter) VALUES (?,?,?,?,?,?)",
            (room, day, period, cancel_code, expires, reporter)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # 同じ人が同じコマの同じ教室をもう報告している。1人で「使用中の可能性」にさせない
        conn.close()
        return jsonify({'ok': False, 'error': 'already_reported'}), 409
    conn.close()
    count = get_report_counts(day, period).get(room, 0)

    return jsonify({'ok': True, 'cancel_code': cancel_code, 'count': count})


@app.route('/api/report/cancel', methods=['POST'])
def api_report_cancel():
    data = request.get_json(silent=True) or {}
    room        = str(data.get('room', '')).strip()[:20]
    day         = data.get('day', '')
    period      = data.get('period', 0)
    cancel_code = str(data.get('cancel_code', '')).strip()[:10]
    if not room or not cancel_code:
        return jsonify({'ok': False}), 400
    # キャンセルコードの総当たりを防ぐため、取り消しにもレート制限をかける
    if is_rate_limited(client_ip()):
        return jsonify({'ok': False, 'error': 'rate_limited'}), 429

    conn = sqlite3.connect(REPORTS_DB)
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM reports WHERE room=? AND day=? AND period=? AND cancel_code=?",
        (room, day, period, cancel_code)
    )
    deleted = cur.rowcount
    conn.commit(); conn.close()
    return jsonify({'ok': deleted > 0})


@app.route('/', methods=['GET', 'POST'])
def index():
    now = datetime.datetime.now(JST)
    day = ["月", "火", "水", "木", "金", "土", "日"][now.weekday()]
    if day == "日": day = "月"

    c_time = now.strftime("%H:%M")
    period = 1
    for p, (s, e) in PERIODS.items():
        if s <= c_time <= e:
            period = p
            break

    building = "all"
    empty_rooms = None
    error_message = None
    searched = False

    period_times = {p: f"{s}–{e}" for p, (s, e) in PERIODS.items()}

    # 年度・学期は選べる。未指定なら「いまの年度・いまの学期」を既定にする
    available_years = get_available_years()
    year = resolve_year(None, available_years)
    term = get_current_term_label()
    span = 1

    if request.method == 'POST':
        searched = True
        day = request.form.get('day')
        period = int(request.form.get('period'))
        building = request.form.get('building')
        year = resolve_year(request.form.get('year'), available_years)
        term = resolve_term(request.form.get('term'))
        span = resolve_span(request.form.get('span'))

    try:
        if not os.path.exists(DB_NAME):
            raise FileNotFoundError(f"データベースファイル '{DB_NAME}' が見つかりません。")

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()

        # 年度と学期は利用者が選ぶ。既定は「いまの年度・いまの学期」。
        # 以前は日付から決め打ちしていて、他の学期・年度を見る手段が無かった。
        # その日の全時限の占有をまとめて引く。「何限まで続けて空いているか」を出すため
        where, params = ["曜日=?", "履修期名=?"], [day, term]
        room_where, room_params = [], []
        if year is not None:
            where.append("年度=?"); params.append(year)
            room_where.append("年度=?"); room_params.append(year)
        cur.execute(f"SELECT 時限, 教室 FROM schedules WHERE {' AND '.join(where)}", params)
        occupied_at = collections.defaultdict(set)
        for p_, room_ in cur.fetchall():
            occupied_at[int(p_)].add(str(room_))
        occupied = occupied_at[period]

        building_name = {"tower": "タワースコラ", "main": "駿河台校舎",
                         "funabashi": "船橋校舎"}.get(building)
        if building_name:
            room_where.append("building = ?"); room_params.append(building_name)
        q_all = "SELECT name, building FROM classrooms"
        if room_where:
            q_all += " WHERE " + " AND ".join(room_where)

        cur.execute(q_all, room_params)
        all_rooms = cur.fetchall()
        conn.close()

        empty_rooms = sorted(
            [{"name": r[0], "building": r[1],
              "free_until": free_until(str(r[0]), period, occupied_at)}
             for r in all_rooms if str(r[0]) not in occupied],
            key=lambda x: (x['building'] != 'タワースコラ', x['building'] != '駿河台校舎', x['name'])
        )
        # 「続けて使う」で絞る。span=2 なら、この時限と次の時限の両方が空いている教室だけ
        empty_rooms = [r for r in empty_rooms if r["free_until"] - period + 1 >= span]

    except Exception as e:
        logging.error(f"RoomRadar error: {e}")
        error_message = "検索中にエラーが発生しました。時間をおいて再試行してください。"
        empty_rooms = []

    # 報告数・予約数を取得（検索済みの場合のみ）
    cleanup_reports()
    cleanup_expired()
    report_counts   = get_report_counts(day, period) if searched else {}
    reserve_counts  = {}
    if searched:
        conn = sqlite3.connect(RESERVE_DB)
        for row in conn.execute(
            "SELECT room, COUNT(*) FROM reservations WHERE day=? AND period=? GROUP BY room",
            (day, period)
        ):
            reserve_counts[row[0]] = row[1]
        conn.close()

    return render_template_string(
        HTML_TEMPLATE,
        empty_rooms=empty_rooms,
        selected_day=day, selected_period=period,
        selected_building=building,
        error_message=error_message,
        period_times=period_times,
        searched=searched,
        report_counts=report_counts,
        report_threshold=REPORT_THRESHOLD,
        reserve_counts=reserve_counts,
        current_term=get_current_term_label(),
        selected_year=year, selected_term=term, selected_span=span,
        max_period=MAX_PERIOD,
        available_years=available_years,
        available_terms=VALID_TERMS,
        # いま（実時間）と違う年度・学期を見ているときに注意を出すための材料
        is_current_view=(year in (None, get_current_year()) and term == get_current_term_label()),
        current_year=get_current_year(),
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
