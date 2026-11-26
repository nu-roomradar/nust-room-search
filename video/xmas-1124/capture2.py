"""クリスマスモードの本編（リール⑤ v4）に使うアプリの実画面を撮る（12/1 火 13:40。4倍の解像度）。
  先に起動： python3 fakeapp.py 13:40 5071 &      → assets/s_<画面>_<n|x>.png（n：通常、x：クリスマス）
画面：main（いま・駿河台校舎）、next（次の時限）、room（教室 133 の1週間）、find（個別の教室を検索）。next は下まで流す用に縦長も撮る（s_nextlong_x.png）。
船橋校舎は映さない（タブと、教室さがしの船橋の欄を隠す）。報告は入れない。"""
import os, sys
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "assets")
FD = os.path.join(HERE, "..", "desk-3d", "fonts")
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
from _browser import find_chrome
FONTS = {"400": "Regular", "500": "Medium", "700": "Bold", "900": "Black"}
CSS = "".join(f"@font-face{{font-family:'{fam}';font-weight:{w};src:url('https://fonts.gstatic.com/local/{n}.otf') format('opentype');}}"
              for fam in ("Noto Sans JP", "M PLUS Rounded 1c", "Zen Kaku Gothic New") for w, n in FONTS.items())
CSS += "@font-face{font-family:'Syne';font-weight:400 800;src:url('https://fonts.gstatic.com/local/Syne.ttf') format('truetype');}"
HIDE = "a[href*='funabashi']{display:none!important} #toast,#a2hs,#purpose-bar{display:none!important}"
PAGES = {"main": "/?building=main", "next": "/?day=%E7%81%AB&period=4&building=main", "room": "/room/133", "find": "/room?year=2026&term=%E5%BE%8C%E6%9C%9F"}
def gs(route):
    name = route.request.url.rsplit("/", 1)[-1]
    path = f"{FD}/Syne-wght.ttf" if name == "Syne.ttf" else f"{FD}/NotoSansCJKjp-{name}"
    route.fulfill(status=200, content_type="font/otf", body=open(path, "rb").read(), headers={"Access-Control-Allow-Origin": "*"})
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=find_chrome())
    for tag, theme in (("n", "off"), ("x", None)):
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=4, timezone_id="Asia/Tokyo", locale="ja-JP")
        ctx.add_init_script("try{localStorage.setItem('rr_visits','1');localStorage.setItem('rr_a2hs','1');" + (f"localStorage.setItem('rr_theme','{theme}');" if theme else "localStorage.removeItem('rr_theme');") + "}catch(e){}")
        pg = ctx.new_page(); pg.clock.set_fixed_time("2026-12-01T13:40:00+09:00")
        pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(status=200, content_type="text/css", body=CSS))
        pg.route("**/fonts.gstatic.com/**", gs); pg.route("**/googletagmanager.com/**", lambda r: r.abort())
        for name, url in PAGES.items():
            pg.goto("http://127.0.0.1:5071" + url, wait_until="load"); pg.add_style_tag(content=HIDE); pg.wait_for_timeout(1800)
            pg.screenshot(path=f"{OUT}/s_{name}_{tag}.png", full_page=True, clip={"x": 0, "y": 0, "width": 390, "height": 844})
            vis = pg.evaluate("[...document.querySelectorAll('body *')].filter(e=>e.offsetParent&&e.children.length===0&&e.textContent.includes('船橋')&&e.getBoundingClientRect().top<1720).map(e=>[e.tagName,e.textContent.trim().slice(0,20),Math.round(e.getBoundingClientRect().top)])")
            print(tag, name, pg.evaluate("document.documentElement.className"), "船橋:", vis)
            if name == "next" and tag == "x":
                pg.screenshot(path=f"{OUT}/s_nextlong_x.png", full_page=True, clip={"x": 0, "y": 0, "width": 390, "height": 1700})
        ctx.close()
    b.close()
