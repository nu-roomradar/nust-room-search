"""3D の背景に、キャッチコピー（明朝の縦書き）と小さな「RoomRadar」の文字を重ねて、1080×1350 の画像にする。
  python3 compose.py <背景.png> "<1行目>|<2行目>" <出力.png> [side=right|left] [mark=1|0] [size=76] [top=112] [shade=0.35]
書体は Noto Serif CJK JP（OFL）。大きいのでリポジトリには入れない（notofonts/noto-cjk の Serif/OTF/Japanese から取り、FONT の場所に置く）"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from _browser import find_chrome
from playwright.sync_api import sync_playwright
bg, copy, out = sys.argv[1], sys.argv[2], sys.argv[3]
opt = dict(a.split("=", 1) for a in sys.argv[4:])
side, mark, size, top, shade = opt.get("side", "right"), opt.get("mark", "1") == "1", int(opt.get("size", 76)), int(opt.get("top", 112)), float(opt.get("shade", 0.35))
FONT = os.environ.get("AD_FONT_DIR", "/tmp/claude-0/-home-user-nust-room-search/4884a853-579b-5cf7-8666-1d88092934b8/scratchpad/ad/fonts")
SYNE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "desk-3d", "fonts", "Syne-wght.ttf"))
lines = copy.split("|")
pos = "right:104px" if side == "right" else "left:104px"
markpos = "left:96px" if side == "right" else "right:96px"
html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:'Min';font-weight:600;src:url('file://{FONT}/NotoSerifCJKjp-SemiBold.otf')}}
@font-face{{font-family:'Syne';font-weight:400 800;src:url('file://{SYNE}')}}
*{{margin:0;padding:0}} html,body{{width:1080px;height:1350px;overflow:hidden;background:#000}}
.bg{{position:absolute;inset:0;width:1080px;height:1350px;object-fit:cover}}
.shade{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(3,6,16,{shade}) 0%,rgba(3,6,16,0) 42%)}}
.vig{{position:absolute;inset:0;background:radial-gradient(ellipse 75% 70% at 50% 55%,transparent 60%,rgba(0,0,0,.28) 100%)}}
.copy{{position:absolute;{pos};top:{top}px;writing-mode:vertical-rl;font-family:'Min';font-weight:600;font-size:{size}px;line-height:1.7;
       letter-spacing:.2em;color:#f5f2ea;text-shadow:0 2px 26px rgba(0,0,0,.45)}}
.copy span{{display:block}}
.copy span:nth-child(2){{padding-top:1.4em}}   /* 2行目を1字半さげて、段をつける */
.mark{{position:absolute;{markpos};top:118px;font-family:'Syne';font-weight:700;font-size:30px;letter-spacing:.32em;color:rgba(245,242,234,.86);text-shadow:0 1px 12px rgba(0,0,0,.4)}}
.mark i{{display:inline-block;width:10px;height:10px;border-radius:50%;background:#ffb070;margin-right:16px;vertical-align:4px;box-shadow:0 0 14px #ffb070}}
</style></head><body><img class="bg" src="file://{os.path.abspath(bg)}"><div class="shade"></div><div class="vig"></div>
{'<div class="mark"><i></i>RoomRadar</div>' if mark else ''}
<div class="copy">{''.join(f'<span>{l}</span>' for l in lines)}</div></body></html>"""
tmp = os.path.abspath(out) + ".html"; open(tmp, "w", encoding="utf-8").write(html)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=find_chrome()); pg = b.new_page(viewport={"width": 1080, "height": 1350})
    pg.goto("file://" + tmp); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(500)
    pg.screenshot(path=out); b.close()
os.remove(tmp); print(out)
