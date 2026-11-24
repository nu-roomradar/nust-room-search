"""クリスマスの動画に使うアプリの実画面を撮る（駿河台校舎・12/1 火 3限）。通常の見た目と、クリスマスの見た目の2枚。
  先に起動： python3 fakeapp.py 13:40 5071 &
船橋校舎のタブは映さない。報告は入れない。
  python3 capture.py hd   カミングスーンの動画で、机のスマホに重ねるくっきりした画面（クリスマスの見た目・1画面ぶん・8倍の解像度）→ assets/xmas_screen_hd.png"""
import os, sys
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "assets")
FD = os.path.join(HERE, "..", "desk-3d", "fonts")
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
from _browser import find_chrome
HD = len(sys.argv) > 1 and sys.argv[1] == "hd"
DSF, TALL = (8, 844) if HD else (3, 1100)
FONTS = {"400": "Regular", "500": "Medium", "700": "Bold", "900": "Black"}
CSS = "".join(f"@font-face{{font-family:'{fam}';font-weight:{w};src:url('https://fonts.gstatic.com/local/{n}.otf') format('opentype');}}"
              for fam in ("Noto Sans JP", "M PLUS Rounded 1c", "Zen Kaku Gothic New") for w, n in FONTS.items())
CSS += "@font-face{font-family:'Syne';font-weight:400 800;src:url('https://fonts.gstatic.com/local/Syne.ttf') format('truetype');}"
HIDE = ".bldg-tabs a[href*='funabashi']{display:none!important} #toast,#a2hs,#purpose-bar{display:none!important}"
def gs(route):
    name = route.request.url.rsplit("/", 1)[-1]
    path = f"{FD}/Syne-wght.ttf" if name == "Syne.ttf" else f"{FD}/NotoSansCJKjp-{name}"
    route.fulfill(status=200, content_type="font/otf", body=open(path, "rb").read(), headers={"Access-Control-Allow-Origin": "*"})
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=find_chrome())
    for name, theme in ((("xmas_screen_hd", None),) if HD else (("normal", "off"), ("xmas", None))):
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=DSF, timezone_id="Asia/Tokyo", locale="ja-JP")
        init = "try{localStorage.setItem('rr_visits','1');localStorage.setItem('rr_a2hs','1');" + (f"localStorage.setItem('rr_theme','{theme}');" if theme else "localStorage.removeItem('rr_theme');") + "}catch(e){}"
        ctx.add_init_script(init)
        pg = ctx.new_page(); pg.clock.set_fixed_time("2026-12-01T13:40:00+09:00")
        pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(status=200, content_type="text/css", body=CSS))
        pg.route("**/fonts.gstatic.com/**", gs); pg.route("**/googletagmanager.com/**", lambda r: r.abort())
        pg.goto("http://127.0.0.1:5071/?building=main", wait_until="load"); pg.add_style_tag(content=HIDE); pg.wait_for_timeout(2500)
        pg.screenshot(path=f"{OUT}/{name}.png", full_page=True, clip={"x": 0, "y": 0, "width": 390, "height": TALL})
        print(name, pg.evaluate("document.documentElement.className + ' | ' + document.body.className"),
              "| 船橋:", pg.evaluate("[...document.querySelectorAll('a,button,span')].filter(e=>e.offsetParent&&e.children.length===0&&e.textContent.includes('船橋')).length"))
        ctx.close()
    b.close()
