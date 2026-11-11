"""3D 広告のスマホに映すアプリの実画面を撮る（駿河台校舎・水曜3限。報告の前・1件・2件）。
先に `python3 video/desk-3d/fakeapp.py &` でアプリを起動しておく。出力は video/desk-3d/assets/。
船橋校舎のタブは映さない（テスト運用の周知物の決まり）。"""
import json, os, sys, urllib.request
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "assets"); FD = os.path.join(HERE, "fonts")
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
from _browser import find_chrome
BASE, ROOM, DSF = "http://127.0.0.1:5057", "705", 6
TALL = 1365                                   # 縦に撮る範囲（CSS px）。×6 で 8190px（テクスチャの上限 8192 に収める）
FONTS = {"400": "Regular", "500": "Medium", "700": "Bold", "900": "Black"}
CSS = "".join(f"@font-face{{font-family:'{fam}';font-weight:{w};src:url('https://fonts.gstatic.com/local/{n}.otf') format('opentype');}}"
              for fam in ("Noto Sans JP", "M PLUS Rounded 1c", "Zen Kaku Gothic New") for w, n in FONTS.items())
CSS += "@font-face{font-family:'Syne';font-weight:400 800;src:url('https://fonts.gstatic.com/local/Syne.ttf') format('truetype');}"   # アプリのロゴ・教室名
HIDE = ".bldg-tabs a[href*='funabashi']{display:none!important} #toast,#a2hs,.season-deco{display:none!important}"
def gs(route):
    name = route.request.url.rsplit("/", 1)[-1]
    path = f"{FD}/Syne-wght.ttf" if name == "Syne.ttf" else f"{FD}/NotoSansCJKjp-{name}"
    route.fulfill(status=200, content_type="font/otf", body=open(path, "rb").read(), headers={"Access-Control-Allow-Origin": "*"})
def report_as(ip):
    req = urllib.request.Request(BASE + "/api/report", data=json.dumps({"room": ROOM, "day": "水", "period": 3}).encode(),
                                 headers={"Content-Type": "application/json", "X-Forwarded-For": ip}, method="POST")
    return json.load(urllib.request.urlopen(req))
R = "sel => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.top + scrollY, r.width, r.height]; }"
rects = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=find_chrome())
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=DSF, timezone_id="Asia/Tokyo", locale="ja-JP")
    ctx.add_init_script("try{localStorage.setItem('rr_theme','off');localStorage.setItem('rr_visits','1');localStorage.setItem('rr_a2hs','1')}catch(e){}")
    pg = ctx.new_page(); pg.clock.set_fixed_time("2026-11-18T14:40:00+09:00")
    pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(status=200, content_type="text/css", body=CSS))
    pg.route("**/fonts.gstatic.com/**", gs)
    pg.route("**/googletagmanager.com/**", lambda r: r.abort())
    def load(name):
        pg.goto(BASE + "/?building=main", wait_until="load"); pg.add_style_tag(content=HIDE); pg.wait_for_timeout(1200)
        h = pg.evaluate("document.documentElement.scrollHeight")
        pg.screenshot(path=f"{OUT}/{name}.png", full_page=True, clip={"x": 0, "y": 0, "width": 390, "height": min(TALL, h)})
        print(name, "height", h, "船橋?", "船橋" in pg.inner_text("body"), "font:", pg.evaluate("getComputedStyle(document.body).fontFamily")[:40])
    load("page0")
    for k, s in {"chips": ".slot-chips", "tabs": ".bldg-tabs", "meta": "#result-meta", "count": ".count-chip", "card": f".room-card[data-room='{ROOM}']",
                 "grid": ".room-grid", "badge": ".now-badge", "ribbon": ".season-ribbon.s-normal", "fold": "#form-fold", "purpose": ".purpose-bar, #purpose-bar"}.items():
        rects[k] = pg.evaluate(R, s)
    # スマホの画面に出す位置（時限の切り替えが上に来るところ）までスクロールし、教室を押す
    y0 = int(rects["chips"][1] - 64); rects["scrollY"] = y0
    pg.evaluate(f"window.scrollTo(0,{y0})"); pg.wait_for_timeout(300)
    pg.screenshot(path=f"{OUT}/view0.png")
    pg.click(f".room-card[data-room='{ROOM}']"); pg.wait_for_timeout(900)
    pg.screenshot(path=f"{OUT}/modal0.png")
    rects["modal"] = pg.evaluate(R.replace("r.top + scrollY", "r.top"), "#modal .modal, .modal")
    rects["btn"] = pg.evaluate(R.replace("r.top + scrollY", "r.top"), ".btn-report")
    pg.click(".btn-report"); pg.wait_for_timeout(900)
    pg.screenshot(path=f"{OUT}/modal1.png")
    rects["modal1"] = pg.evaluate(R.replace("r.top + scrollY", "r.top"), "#modal .modal, .modal")
    load("page1")                                 # 1件（この端末から）
    print("2人目:", report_as("203.0.113.7"))
    load("page2")                                 # 2件 →「使用中の可能性」
    rects["card2"] = pg.evaluate(R, f".room-card[data-room='{ROOM}'], .room-card.reported")
    json.dump(rects, open(f"{OUT}/rects.json", "w"), indent=1, ensure_ascii=False)
