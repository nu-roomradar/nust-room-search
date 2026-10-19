import os, sys
from playwright.sync_api import sync_playwright
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
S = sys.argv[1]; BASE = "http://127.0.0.1:5056"
FONTS = {"400": "Regular", "500": "Medium", "700": "Bold", "900": "Black"}
CSS = "".join(f"@font-face{{font-family:'{fam}';font-weight:{w};src:url('https://fonts.gstatic.com/local/{n}.otf') format('opentype');}}"
              for fam in ("Noto Sans JP", "M PLUS Rounded 1c", "Zen Kaku Gothic New") for w, n in FONTS.items())
FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")   # fetch_fonts.sh で入れる
def gs(route):
    name = route.request.url.rsplit("/", 1)[-1]
    route.fulfill(status=200, content_type="font/otf", body=open(f"{FD}/NotoSansCJKjp-{name}", "rb").read(), headers={"Access-Control-Allow-Origin": "*"})
import json
rects = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME)
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, timezone_id="Asia/Tokyo", locale="ja-JP")
    pg = ctx.new_page()
    pg.clock.set_fixed_time("2026-10-20T10:52:00+09:00")
    pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(status=200, content_type="text/css", body=CSS))
    pg.route("**/fonts.gstatic.com/**", gs)
    pg.route("**/googletagmanager.com/**", lambda r: r.abort())
    pg.goto(BASE + "/", wait_until="load"); pg.wait_for_timeout(800)
    pg.screenshot(path=f"{S}/cap-home.png")                      # 開いた直後（上から1画面）
    print("home fonts:", pg.evaluate("getComputedStyle(document.body).fontFamily"))
    def search(building, span, name):
        pg.goto(BASE + "/", wait_until="load")
        pg.select_option("select[name=building]", building)
        pg.select_option("select[name=span]", span)
        pg.click("#btn-search"); pg.wait_for_load_state("load"); pg.wait_for_timeout(3500); pg.add_style_tag(content="#toast{display:none!important}")
        pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(300)
        pg.screenshot(path=f"{S}/cap-{name}-full.png", full_page=True)
        R = "sel => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.top + scrollY, r.width, r.height]; }"
        rects[name] = {k: pg.evaluate(R, s) for k, s in {"clockchip": ".status-pill, #now-period", "btn": "#btn-search", "meta": "#result-meta",
                       "count": "#count-chip", "s305": ".room-card[data-room='S305']", "card1": ".room-card[data-room]"}.items()}
        rects[name]["clockchip"] = pg.evaluate("(() => { const r = document.getElementById('now-period').parentElement.getBoundingClientRect(); return [r.left, r.top + scrollY, r.width, r.height]; })()")
        y = rects[name]["meta"][1]
        print(name, "result-meta y:", y, "height:", pg.evaluate("document.documentElement.scrollHeight"),
              "funabashi?", "船橋" in pg.inner_text("main") if pg.query_selector("main") else "船橋" in pg.inner_text("body"))
    search("tower", "1", "tower")
    search("main", "1", "main")
    pg.goto(BASE + "/room/S305?year=2026&term=後期", wait_until="load"); pg.wait_for_timeout(800)
    pg.screenshot(path=f"{S}/cap-room-full.png", full_page=True)
    rects["room"] = {"now": pg.evaluate("""(() => { const e = [...document.querySelectorAll('*')].filter(x => x.children.length === 0 && x.textContent.trim() === 'いま')[0];
       const c = e.closest('td,div,button'); const r = c.getBoundingClientRect(); return [r.left, r.top + scrollY, r.width, r.height]; })()""")}
    json.dump(rects, open(S + "/rects.json", "w"), indent=1)
    print("card y:", pg.evaluate("[...document.querySelectorAll('*')].length"), "room height:", pg.evaluate("document.documentElement.scrollHeight"))
    b.close()
