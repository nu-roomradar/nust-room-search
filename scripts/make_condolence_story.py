#!/usr/bin/env python3
"""令和8年熊本地震のお見舞いストーリー 1080x1920。
宣伝要素（QR/LPリンク/CTA/ハッシュタグ/絵文字）は一切入れない。"""
import base64, pathlib
from playwright.sync_api import sync_playwright

from _browser import find_chrome

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHROME = find_chrome()

logo = base64.b64encode((ROOT / "rr_logo.png").read_bytes()).decode()

HTML = f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@400;500;600&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1920px; overflow:hidden;
  font-family:"Noto Serif JP", serif; color:#ffffff;
  background:#b9ad9c; }}
/* 目にやさしい暖色のグレージュ。ブランドの青/ネイビーは使わない */
.bg {{ position:absolute; inset:0;
  background:linear-gradient(180deg,#bcb1a0 0%,#c1b6a6 18%,#b8ac99 58%,#ada190 100%); }}

/* 上端のユーザー名バー/下端の返信バーに隠れない安全マージン */
.wrap {{ position:absolute; inset:0; padding:150px 96px 240px;
  display:flex; flex-direction:column; align-items:center;
  justify-content:center; text-align:center; }}

.lead {{ font-size:47px; font-weight:600; line-height:2.05; letter-spacing:.06em;
  text-shadow:0 1px 3px rgba(80,66,50,.22); }}

.rule {{ width:96px; height:1px; background:rgba(255,255,255,.55); margin:74px 0; }}

.body {{ font-size:38px; font-weight:500; line-height:2.15;
  letter-spacing:.04em; color:rgba(255,255,255,.94);
  text-shadow:0 1px 3px rgba(80,66,50,.20); }}

.sign {{ margin-top:96px; display:flex; flex-direction:column; align-items:center; gap:22px; }}
.sign img {{ width:104px; filter:brightness(0) invert(1) opacity(.72); }}
.sign .name {{ font-size:31px; font-weight:500; letter-spacing:.12em; color:rgba(255,255,255,.82); }}
</style></head>
<body>
<div class="bg"></div>
<div class="wrap">
  <div class="lead">
    このたびの熊本県での地震により<br>
    被害を受けられた皆さまに<br>
    心よりお見舞い申し上げます
  </div>

  <div class="rule"></div>

  <div class="body">
    ご家族やご友人が被災された学生の方も<br>
    いらっしゃると思います。<br>
    どうかご無理をなさらず、<br>
    まずはご自身の安全を優先してください。
  </div>

  <div class="sign">
    <img src="data:image/png;base64,{logo}">
    <div class="name">RoomRadar 運営</div>
  </div>
</div>
</body></html>"""

out = str(ROOT / "assets/instagram/kumamoto-condolence-story.png")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME)
    pg = b.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=2)
    pg.set_content(HTML, wait_until="networkidle")
    pg.wait_for_timeout(600)
    pg.screenshot(path=out, clip={"x": 0, "y": 0, "width": 1080, "height": 1920})
    b.close()
print("saved", out)
