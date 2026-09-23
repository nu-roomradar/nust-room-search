import os
import re
import sqlite3
import datetime
import hashlib
import secrets
import string
import collections
import time
import logging
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

DB_NAME = "schedule_final.db"
JST = datetime.timezone(datetime.timedelta(hours=9))
PERIODS = {1: ("09:00", "10:40"), 2: ("10:50", "12:30"), 3: ("13:20", "15:00"),
           4: ("15:10", "16:50"), 5: ("17:00", "18:40"), 6: ("18:50", "20:30")}
# 仮予約・報告の置き場所。Render の通常ディスクは再デプロイ・再起動で消えるので、
# 永続ディスク（Render Disk）を付けたら環境変数 DATA_DIR にそのマウント先を入れる。未設定なら従来どおりカレント。
DATA_DIR    = os.environ.get("DATA_DIR", ".")
os.makedirs(DATA_DIR, exist_ok=True)
RESERVE_DB  = os.path.join(DATA_DIR, "reservations.db")
REPORTS_DB  = os.path.join(DATA_DIR, "reports.db")
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

def _asset_version():
    """static/ の中身のハッシュ。デプロイで CSS/JS が変わったらブラウザのキャッシュを捨てさせる"""
    h = hashlib.sha256()
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    for name in sorted(os.listdir(static_dir)):
        with open(os.path.join(static_dir, name), 'rb') as f:
            h.update(f.read())
    return h.hexdigest()[:10]

ASSET_VERSION = _asset_version()


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


def upcoming_period(now):
    """いまの授業時限。休み時間なら次の時限。1限の前も1限を返す。最終時限の後は None。"""
    c_time = now.strftime("%H:%M")
    for p, (s, e) in PERIODS.items():
        if c_time <= e:
            return p
    return None

@app.route('/', methods=['GET', 'POST'])
def index():
    now = datetime.datetime.now(JST)
    day = ["月", "火", "水", "木", "金", "土", "日"][now.weekday()]
    if day == "日": day = "月"

    # 開いた瞬間に「いま／このあと空いている教室」を出す。授業時間帯と休み時間なら自動で検索する
    auto_period = upcoming_period(now)
    period = auto_period or 1

    building = "all"
    empty_rooms = None
    error_message = None
    searched = False
    auto = request.method == 'GET' and auto_period is not None and now.weekday() != 6
    if auto:
        searched = True

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

    # static/app.js が読む設定。テンプレート内の JS に Jinja を埋め込まないための受け渡し口
    rr_config = {
        'day': day, 'period': period,
        'searched': searched, 'auto': auto, 'error': bool(error_message),
        'count': len(empty_rooms or []),
        'year': year, 'term': term,
        'periods': {p: [s, e] for p, (s, e) in PERIODS.items()},
    }

    return render_template(
        'index.html',
        rr_config=rr_config,
        auto=auto,
        asset_version=ASSET_VERSION,
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

WEEK_DAYS = ["月", "火", "水", "木", "金", "土"]

@app.route('/room/<path:name>')
def room_week(name):
    """教室ごとの1週間。どの曜日・時限が空いているかを一目で見る"""
    available_years = get_available_years()
    year = resolve_year(request.args.get('year'), available_years)
    term = resolve_term(request.args.get('term'))
    conn = sqlite3.connect(f"file:{DB_NAME}?mode=ro", uri=True)
    try:
        room_q, room_p = "SELECT building FROM classrooms WHERE name=?", [name]
        where, params = ["教室=?", "履修期名=?"], [name, term]
        if year is not None:
            room_q += " AND 年度=?"; room_p.append(year)
            where.append("年度=?"); params.append(year)
        row = conn.execute(room_q, room_p).fetchone()
        if row is None:
            return "教室が見つかりません", 404
        grid = collections.defaultdict(list)
        for d, p, subj in conn.execute(
                f"SELECT 曜日, 時限, 科目名 FROM schedules WHERE {' AND '.join(where)} ORDER BY id", params):
            subj = re.split(r"[↓{【]", subj or "")[0].strip()
            if subj and subj not in grid[(d, int(p))]:
                grid[(d, int(p))].append(subj)
    finally:
        conn.close()
    return render_template(
        'room.html', room=name, building=row[0], grid=grid,
        days=WEEK_DAYS, periods=PERIODS, year=year, term=term,
        asset_version=ASSET_VERSION,
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
