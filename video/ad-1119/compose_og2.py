"""紹介ページ（intro.html）の共有画像（1200×630）の構成案を作る（2026-11-24、運営「画像はいい感じだから構成をもうちょっと考えて」）。
OK をもらった広告ふうの画像（文字入り。assets/instagram/ad/ad3-*.png）には手を入れず、そのまま置く。
  python3 compose_og2.py <a|b|c> <出力.png>
  a：左に扉の画像、右に案内（はじめての人へ・2分で読める・何のサービスか）
  b：扉の画像を真ん中に大きく、左右に残りの2枚を少しのぞかせる（3枚ひと組に見せる）
  c：3枚を横に並べ、下に細い帯で案内
  d：左に扉の画像、右に大きな字で「RoomRadar／日大理工の空き教室検索」（紹介ページ・about 用）"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
from _browser import find_chrome
from playwright.sync_api import sync_playwright

kind, out = sys.argv[1], sys.argv[2]
AD = os.path.abspath(os.path.join(HERE, "..", "..", "assets", "instagram", "ad"))
SANS = os.path.abspath(os.path.join(HERE, "..", "desk-3d", "fonts"))
LOGO = os.path.abspath(os.path.join(HERE, "..", "cm-ai", "rr_logo_hd.png"))
door, hero, room = (f"file://{AD}/ad3-{n}.png" for n in ("door", "hero", "room"))
CSS = f"""
@font-face{{font-family:'Sans';font-weight:500;src:url('file://{SANS}/NotoSansCJKjp-Medium.otf')}}
@font-face{{font-family:'Sans';font-weight:700;src:url('file://{SANS}/NotoSansCJKjp-Bold.otf')}}
@font-face{{font-family:'Sans';font-weight:900;src:url('file://{SANS}/NotoSansCJKjp-Black.otf')}}
@font-face{{font-family:'Syne';font-weight:400 800;src:url('file://{SANS}/Syne-wght.ttf')}}
*{{margin:0;padding:0;box-sizing:border-box}} html,body{{width:1200px;height:630px;overflow:hidden}}
body{{background:radial-gradient(900px 600px at 70% 40%,#1a2742,#0b1222 70%);font-family:'Sans';color:#f5f2ea}}
img.ad{{position:absolute;display:block;box-shadow:0 18px 50px rgba(0,0,0,.55)}}
"""
if kind == "a":
    # 2026-11-24 運営「表示がちょっと小さくて見づらい」→ LINE のカード（幅 500px ほど）でも読めるよう、字を大きく・数を減らす
    body = f"""<img class="ad" src="{door}" style="left:0;top:0;width:504px;height:630px;box-shadow:none">
<div style="position:absolute;left:504px;top:0;width:60px;height:630px;background:linear-gradient(90deg,rgba(0,0,0,.35),rgba(0,0,0,0))"></div>
<div style="position:absolute;left:566px;right:40px;top:0;bottom:0;display:flex;flex-direction:column;justify-content:center">
  <div style="font-weight:900;font-size:34px;letter-spacing:.14em;color:#ffd9b0">はじめての人へ</div>
  <div style="margin-top:10px;font-weight:900;font-size:92px;line-height:1.12;letter-spacing:-.01em">2分でわかる</div>
  <div style="margin-top:6px;font-family:Syne;font-weight:800;font-size:60px;line-height:1.1">RoomRadar</div>
  <div style="margin-top:26px;font-weight:900;font-size:34px;line-height:1.45;color:#dfe7f6">日大理工の空き教室を、<br>時間割から探せる。</div>
</div>"""
elif kind == "d":
    # 2026-11-27 運営「（LINE のカードで）見た感じ分かりづらいかも」→ 紹介ページ・about 用。左に扉の画像、右に大きな字で「何のサービスか」だけ
    body = f"""<img class="ad" src="{door}" style="left:0;top:0;width:504px;height:630px;box-shadow:none">
<div style="position:absolute;left:504px;top:0;width:60px;height:630px;background:linear-gradient(90deg,rgba(0,0,0,.35),rgba(0,0,0,0))"></div>
<div style="position:absolute;left:566px;right:36px;top:0;bottom:0;display:flex;flex-direction:column;justify-content:center">
  <div style="font-family:Syne;font-weight:800;font-size:62px;line-height:1.05;letter-spacing:-.01em">RoomRadar</div>
  <div style="margin-top:22px;font-weight:900;font-size:60px;line-height:1.25">日大理工の<br>空き教室検索</div>
  <div style="margin-top:26px;font-weight:700;font-size:30px;line-height:1.5;color:#dfe7f6">時間割から、いま授業のない<br>教室がすぐ分かる。</div>
  <div style="margin-top:22px;font-weight:700;font-size:23px;line-height:1.5;color:#ffd9b0">学生開発・試験運用中<br>（大学公式のサービスではありません）</div>
</div>"""
elif kind == "b":
    body = f"""<img class="ad" src="{hero}" style="left:-150px;top:70px;width:392px;height:490px;opacity:.55;filter:saturate(.8)">
<img class="ad" src="{room}" style="right:-150px;top:70px;width:392px;height:490px;opacity:.55;filter:saturate(.8)">
<div style="position:absolute;left:0;top:0;width:330px;height:630px;background:linear-gradient(90deg,rgba(11,18,34,.85),rgba(11,18,34,0))"></div>
<div style="position:absolute;right:0;top:0;width:330px;height:630px;background:linear-gradient(270deg,rgba(11,18,34,.85),rgba(11,18,34,0))"></div>
<img class="ad" src="{door}" style="left:348px;top:0;width:504px;height:630px">"""
else:
    body = f"""<img class="ad" src="{door}" style="left:24px;top:24px;width:376px;height:470px">
<img class="ad" src="{hero}" style="left:412px;top:24px;width:376px;height:470px">
<img class="ad" src="{room}" style="left:800px;top:24px;width:376px;height:470px">
<div style="position:absolute;left:24px;right:24px;top:510px;bottom:20px;display:flex;align-items:center;justify-content:space-between">
  <div style="display:flex;align-items:center;gap:16px"><img src="file://{LOGO}" style="width:92px"><span style="font-family:Syne;font-weight:800;font-size:38px;letter-spacing:.04em">RoomRadar</span></div>
  <div style="text-align:right"><div style="font-weight:900;font-size:30px">はじめての人へ：2分でわかる紹介</div><div style="font-weight:700;font-size:19px;color:#cfd9ee;margin-top:4px">日大理工の空き教室検索（駿河台キャンパスで試験運用中）</div></div>
</div>"""
html = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
tmp = os.path.abspath(out) + ".html"; open(tmp, "w", encoding="utf-8").write(html)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=find_chrome()); pg = b.new_page(viewport={"width": 1200, "height": 630})
    pg.goto("file://" + tmp); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(500)
    pg.screenshot(path=out); b.close()
os.remove(tmp); print(out)
