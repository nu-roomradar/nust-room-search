"""紹介ページ（intro.html）を共有したときに出る画像（OGP。1200×630）を、扉の 3D の背景で作る（2026-11-23）。
  python3 compose_og.py renders/door2_final.png ../../assets/lp/og-intro.png
左に扉の絵（4:5 で切り出し）、右にロゴ・核の言葉・注意の一言・必須の表記（学生課の文言）。"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
from _browser import find_chrome
from playwright.sync_api import sync_playwright

bg, out = os.path.abspath(sys.argv[1]), sys.argv[2]
FONT = os.environ.get("AD_FONT_DIR", "/tmp/claude-0/-home-user-nust-room-search/4884a853-579b-5cf7-8666-1d88092934b8/scratchpad/ad/fonts")
SANS = os.path.abspath(os.path.join(HERE, "..", "desk-3d", "fonts"))
LOGO = os.path.abspath(os.path.join(HERE, "..", "cm-ai", "rr_logo_hd.png"))
NOTE = "本サービスは、学生が「自主創造プロジェクト」の一環として開発・運営している試験運用中のサービスです。大学が公式に提供するサービスではありません。"
html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:'Min';font-weight:600;src:url('file://{FONT}/NotoSerifCJKjp-SemiBold.otf')}}
@font-face{{font-family:'Sans';font-weight:500;src:url('file://{SANS}/NotoSansCJKjp-Medium.otf')}}
@font-face{{font-family:'Sans';font-weight:700;src:url('file://{SANS}/NotoSansCJKjp-Bold.otf')}}
@font-face{{font-family:'Syne';font-weight:400 800;src:url('file://{SANS}/Syne-wght.ttf')}}
*{{margin:0;padding:0;box-sizing:border-box}} html,body{{width:1200px;height:630px;overflow:hidden;background:#0b1222}}
.pic{{position:absolute;left:0;top:0;width:504px;height:630px;object-fit:cover;object-position:52% 62%}}
.fade{{position:absolute;left:380px;top:0;width:140px;height:630px;background:linear-gradient(90deg,rgba(11,18,34,0),#0b1222)}}
.panel{{position:absolute;left:540px;right:56px;top:0;bottom:0;display:flex;flex-direction:column;justify-content:center}}
.brand{{display:flex;align-items:center;gap:18px;margin-bottom:30px}}
.brand img{{width:150px}}
.brand b{{font-family:'Syne';font-weight:700;font-size:40px;letter-spacing:.12em;color:#f5f2ea}}
.copy{{font-family:'Min';font-weight:600;font-size:43px;line-height:1.5;letter-spacing:.04em;color:#f5f2ea;white-space:nowrap}}
.sub{{margin-top:22px;font-family:'Sans';font-weight:700;font-size:23px;line-height:1.6;color:#cfd9ee}}
.caution{{margin-top:10px;font-family:'Sans';font-weight:700;font-size:20px;color:#ffd9b0}}
.note{{position:absolute;left:540px;right:56px;bottom:26px;font-family:'Sans';font-weight:500;font-size:14.5px;line-height:1.55;color:rgba(220,228,244,.78)}}
</style></head><body>
<img class="pic" src="file://{bg}"><div class="fade"></div>
<div class="panel">
  <div class="brand"><img src="file://{LOGO}" alt=""><b>RoomRadar</b></div>
  <div class="copy">「開けたら、空いてる」を<br>当たり前に。</div>
  <div class="sub">日大理工の空き教室を、時間割から一覧に。<br>いまは駿河台キャンパスで試験運用中です。</div>
  <div class="caution">時間割にない授業もあります。入る前に、ドア越しに確認を。</div>
</div>
<div class="note">{NOTE}</div></body></html>"""
tmp = os.path.abspath(out) + ".html"; open(tmp, "w", encoding="utf-8").write(html)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=find_chrome()); pg = b.new_page(viewport={"width": 1200, "height": 630})
    pg.goto("file://" + tmp); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(500)
    pg.screenshot(path=out); b.close()
os.remove(tmp); print(out)
