"""広告ふうの画像 v3（2026-11-22、運営「全部にロゴ入れて、決めたキャッチコピー使って」）。
3D の背景に、核の言葉「「開けたら、空いてる」を当たり前に。」（明朝の縦書き）・ロゴ・注意の一言・必須の表記を重ねて、1080×1350 にする。
  python3 compose3.py <背景.png> <出力.png> [side=right|left] [size=66] [top=96] [shade=0.35] [copy="1行目|2行目"] [drop=3.2em] [right=96]
核の言葉は「時間割にない授業もある」の注意と必ず組で出す（docs/OPERATIONS.md の決定）。
書体：明朝は Noto Serif CJK JP（AD_FONT_DIR）、ゴシックは video/desk-3d/fonts の Noto Sans CJK JP（どちらも OFL）。"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
from _browser import find_chrome
from playwright.sync_api import sync_playwright

bg, out = sys.argv[1], sys.argv[2]
opt = dict(a.split("=", 1) for a in sys.argv[3:])
side, size, top, shade = opt.get("side", "right"), int(opt.get("size", 66)), int(opt.get("top", 96)), float(opt.get("shade", 0.35))
lines = opt.get("copy", "「開けたら、空いてる」を|当たり前に。").split("|")
drop, right = opt.get("drop", "3.2em"), int(opt.get("right", 96))
FONT = os.environ.get("AD_FONT_DIR", "/tmp/claude-0/-home-user-nust-room-search/4884a853-579b-5cf7-8666-1d88092934b8/scratchpad/ad/fonts")
SANS = os.path.abspath(os.path.join(HERE, "..", "desk-3d", "fonts"))
LOGO = os.path.abspath(os.path.join(HERE, "..", "cm-ai", "rr_logo_hd.png"))
NOTE = "本サービスは、学生が「自主創造プロジェクト」の一環として開発・運営している試験運用中のサービスです。大学が公式に提供するサービスではありません。"
pos = f"right:{right}px" if side == "right" else f"left:{right}px"
logopos = "left:84px" if side == "right" else "right:84px"
html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:'Min';font-weight:600;src:url('file://{FONT}/NotoSerifCJKjp-SemiBold.otf')}}
@font-face{{font-family:'Sans';font-weight:500;src:url('file://{SANS}/NotoSansCJKjp-Medium.otf')}}
@font-face{{font-family:'Sans';font-weight:700;src:url('file://{SANS}/NotoSansCJKjp-Bold.otf')}}
@font-face{{font-family:'Syne';font-weight:400 800;src:url('file://{SANS}/Syne-wght.ttf')}}
*{{margin:0;padding:0}} html,body{{width:1080px;height:1350px;overflow:hidden;background:#000}}
.bg{{position:absolute;inset:0;width:1080px;height:1350px;object-fit:cover}}
.shade{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(3,6,16,{shade}) 0%,rgba(3,6,16,0) 40%)}}
.foot{{position:absolute;left:0;right:0;bottom:0;height:250px;background:linear-gradient(0deg,rgba(3,6,16,.86) 0%,rgba(3,6,16,.6) 55%,rgba(3,6,16,0) 100%)}}
.vig{{position:absolute;inset:0;background:radial-gradient(ellipse 75% 70% at 50% 50%,transparent 60%,rgba(0,0,0,.26) 100%)}}
.copy{{position:absolute;{pos};top:{top}px;writing-mode:vertical-rl;font-family:'Min';font-weight:600;font-size:{size}px;line-height:1.75;
       letter-spacing:.14em;color:#f5f2ea;text-shadow:0 2px 26px rgba(0,0,0,.5)}}
.copy span{{display:block}}
.copy span:nth-child(2){{padding-top:{drop}}}
.brand{{position:absolute;{logopos};top:84px;display:flex;flex-direction:column;align-items:center;gap:6px}}
.brand img{{width:210px;filter:drop-shadow(0 6px 22px rgba(0,0,0,.45))}}
.brand b{{font-family:'Syne';font-weight:700;font-size:26px;letter-spacing:.22em;color:rgba(245,242,234,.92)}}
.brand small{{font-family:'Sans';font-weight:500;font-size:19px;letter-spacing:.3em;color:rgba(245,242,234,.72)}}
.caution{{position:absolute;left:0;right:0;bottom:92px;text-align:center;font-family:'Sans';font-weight:700;font-size:25px;letter-spacing:.06em;color:#ffd9b0}}
.note{{position:absolute;left:84px;right:84px;bottom:28px;text-align:center;font-family:'Sans';font-weight:500;font-size:17.5px;line-height:1.55;color:rgba(236,240,248,.82)}}
</style></head><body><img class="bg" src="file://{os.path.abspath(bg)}"><div class="shade"></div><div class="foot"></div><div class="vig"></div>
<div class="brand"><img src="file://{LOGO}" alt=""><b>RoomRadar</b><small>空き教室検索</small></div>
<div class="copy">{"".join(f"<span>{l}</span>" for l in lines)}</div>
<div class="caution">時間割にない授業もあります。入る前に、ドア越しに確認を。</div>
<div class="note">{NOTE}</div></body></html>"""
tmp = os.path.abspath(out) + ".html"; open(tmp, "w", encoding="utf-8").write(html)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=find_chrome()); pg = b.new_page(viewport={"width": 1080, "height": 1350})
    pg.goto("file://" + tmp); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(500)
    pg.screenshot(path=out); b.close()
os.remove(tmp); print(out)
