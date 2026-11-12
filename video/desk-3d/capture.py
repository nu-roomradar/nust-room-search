"""3D 広告のスマホに映すアプリの実画面を撮る（駿河台校舎・水曜）。出力は video/desk-3d/assets/。
  先に2つ起動しておく:  python3 fakeapp.py 14:40 5057 &   python3 fakeapp.py 15:10 5058 &
  撮るもの: 3限の一覧（page0）／教室を押したところ（modal0）／その教室の1週間（room0）／時限が変わったあとの一覧（pageN＝4限）
船橋校舎のタブは映さない（テスト運用の周知物の決まり）。報告は入れない（ふつうの使い方だけを見せる）。"""
import json, os, sys
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "assets"); FD = os.path.join(HERE, "fonts")
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
from _browser import find_chrome
ROOM, DSF = "705", 6
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
R = "sel => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.top + scrollY, r.width, r.height]; }"
RV = R.replace("r.top + scrollY", "r.top")
rects = {}
def page(b, clock, port):
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=DSF, timezone_id="Asia/Tokyo", locale="ja-JP")
    ctx.add_init_script("try{localStorage.setItem('rr_theme','off');localStorage.setItem('rr_visits','1');localStorage.setItem('rr_a2hs','1')}catch(e){}")
    pg = ctx.new_page(); pg.clock.set_fixed_time(f"2026-11-18T{clock}:00+09:00")
    pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(status=200, content_type="text/css", body=CSS))
    pg.route("**/fonts.gstatic.com/**", gs); pg.route("**/googletagmanager.com/**", lambda r: r.abort())
    pg.goto(f"http://127.0.0.1:{port}/?building=main", wait_until="load"); pg.add_style_tag(content=HIDE); pg.wait_for_timeout(1200)
    return pg
def tall(pg, name):
    h = pg.evaluate("document.documentElement.scrollHeight")
    pg.screenshot(path=f"{OUT}/{name}.png", full_page=True, clip={"x": 0, "y": 0, "width": 390, "height": min(TALL, h)})
    print(name, "高さ", h, "| 見えている船橋:", pg.evaluate("[...document.querySelectorAll('a,button,span,div,td,th,h1,h2,p')].filter(e => e.children.length === 0 && e.textContent.includes('船橋') && e.offsetParent !== null).length"))
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=find_chrome())
    pg = page(b, "14:40", 5057); tall(pg, "page0")
    for k, s in {"chips": ".slot-chips", "tabs": ".bldg-tabs", "meta": "#result-meta", "count": ".count-chip", "card": f".room-card[data-room='{ROOM}']",
                 "card701": ".room-card[data-room='701']", "span": f".room-card[data-room='{ROOM}'] .room-span", "span701": ".room-card[data-room='701'] .room-span",
                 "span751": ".room-card[data-room='751'] .room-span", "span752": ".room-card[data-room='752'] .room-span", "span805": ".room-card[data-room='805B'] .room-span",
                 "grid": ".room-grid"}.items(): rects[k] = pg.evaluate(R, s)
    y0 = int(rects["chips"][1] - 64); pg.evaluate(f"window.scrollTo(0,{y0})"); pg.wait_for_timeout(300)
    pg.click(f".room-card[data-room='{ROOM}']"); pg.wait_for_timeout(900)
    pg.screenshot(path=f"{OUT}/modal0.png")
    rects["modal"] = pg.evaluate(RV, "#modal .modal, .modal"); rects["link"] = pg.evaluate(RV, "#modal-week")
    pg.click("#modal-week"); pg.wait_for_load_state("load"); pg.add_style_tag(content=HIDE); pg.wait_for_timeout(1200)
    tall(pg, "room0")
    for k, s in {"rhead": ".room-head", "week": "table.week", "now": "td.now", "legend": ".legend", "rback": "a.back", "free": ".free-count"}.items(): rects[k] = pg.evaluate(R, s)
    print("教室のページ:", pg.inner_text(".room-head").replace("\n", " / "))
    pn = page(b, "15:10", 5058); tall(pn, "pageN")
    rects["chipsN"] = pn.evaluate(R, ".slot-chips"); rects["countN"] = pn.inner_text(".count-chip"); rects["nowN"] = pn.inner_text(".slot-chips a.on")
    json.dump(rects, open(f"{OUT}/rects.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in rects.items() if k in ("chips", "card", "span", "modal", "link", "week", "now", "rhead", "chipsN", "countN", "nowN")}, ensure_ascii=False))
