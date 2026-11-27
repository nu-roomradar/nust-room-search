"""紹介ページ（index.html）と「このサービスについて」（about.html）の共有画像（assets/lp/og-image.png、1200×630）を作り直す。
2026-11-27 運営「お願い」：下の表記が古い言い方（「テスト運用中の非公式サービスです」）のままだったので、学生課の文言（ルール1）にそろえる。見た目はもとの画像に合わせる。
  python3 compose_og_lp.py <出力.png>"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
from _browser import find_chrome
from playwright.sync_api import sync_playwright
out = sys.argv[1]
F = os.path.abspath(os.path.join(HERE, "..", "desk-3d", "fonts"))
LOGO = os.path.abspath(os.path.join(HERE, "..", "cm-ai", "rr_logo_hd.png"))
html = f"""<!doctype html><html><head><meta charset='utf-8'><style>
@font-face{{font-family:'Sans';font-weight:400;src:url('file://{F}/NotoSansCJKjp-Regular.otf')}}
@font-face{{font-family:'Sans';font-weight:500;src:url('file://{F}/NotoSansCJKjp-Medium.otf')}}
@font-face{{font-family:'Sans';font-weight:900;src:url('file://{F}/NotoSansCJKjp-Black.otf')}}
@font-face{{font-family:'Syne';font-weight:400 800;src:url('file://{F}/Syne-wght.ttf')}}
*{{margin:0;padding:0;box-sizing:border-box}} html,body{{width:1200px;height:630px;overflow:hidden}}
body{{font-family:'Sans';color:#16181d;background:
  radial-gradient(520px 420px at 96% 12%,rgba(170,186,236,.62),transparent 70%),
  radial-gradient(460px 380px at 2% 98%,rgba(246,196,160,.6),transparent 70%),#f5f3ee}}
.grid{{position:absolute;inset:0;background-image:linear-gradient(rgba(60,70,100,.07) 1px,transparent 1px),linear-gradient(90deg,rgba(60,70,100,.07) 1px,transparent 1px);background-size:36px 36px}}
.brand{{position:absolute;left:74px;top:62px;display:flex;align-items:center;gap:34px}}
.brand img{{width:136px}} .brand b{{font-family:Syne;font-weight:800;font-size:64px;letter-spacing:-.01em}}
.brand b i{{font-style:normal;color:#2563eb}}
h1{{position:absolute;left:74px;top:196px;font-weight:900;font-size:66px;line-height:1.24;letter-spacing:.02em}} h1 i{{font-style:normal;color:#2563eb}}
.sub{{position:absolute;left:74px;top:366px;font-weight:400;font-size:27px;color:#555b66;letter-spacing:.02em}}
.note{{position:absolute;left:74px;right:70px;top:488px;display:flex;gap:18px;align-items:flex-start}}
.note span{{flex:none;margin-top:6px;font-family:Syne;font-weight:700;font-size:16px;letter-spacing:.14em;padding:5px 12px;border:1.5px solid #b9a595;border-radius:6px;color:#5b4c40;background:rgba(255,255,255,.5)}}
.note p{{font-weight:500;font-size:22.5px;line-height:1.62;color:#3d424c}}
</style></head><body><div class="grid"></div>
<div class="brand"><img src="file://{LOGO}"><b>Room<i>Radar</i></b></div>
<h1>日大理工の空き教室が、<br><i>開いた瞬間</i>わかる。</h1>
<div class="sub">時間割をもとに、いま使える教室を一覧表示（登録不要）</div>
<div class="note"><span>TEST</span><p>本サービスは、学生が「自主創造プロジェクト」の一環として開発・運営している<br>試験運用中のサービスです。大学が公式に提供するサービスではありません。</p></div>
</body></html>"""
tmp = os.path.abspath(out) + ".html"; open(tmp, "w", encoding="utf-8").write(html)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=find_chrome()); pg = b.new_page(viewport={"width": 1200, "height": 630})
    pg.goto("file://" + tmp); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(500); pg.screenshot(path=out); b.close()
os.remove(tmp); print(out)
