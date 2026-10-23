#!/usr/bin/env python3
"""どこ行く？版ポスター（Claude Design 製・assets/posters/claude-design/）の「空き教室は、みんなで使う場所です。」の枠を、
横幅いっぱいに組み直す。

2026-10-23、運営から「枠の右端が空いているのが気になる」と言われて作った。Claude Design で作り直さずに、
枠の中の古い文字を消して（背景は周りから補う。左上に QR のシールの影が落ちているので、
平らな色で塗りつぶさない）、HTML で描き直した文字を重ねる（文言は学生課長の指示どおりで変えない）。
- 見出しを少し大きくし、本文（2行）が枠の右端まで届くようにする
- 「使い方の例」の5つのラベルを横幅いっぱいに広げる
- 注記を横幅いっぱいに割り付ける
枠の位置は塗り色（FILL）から探す。A4（2480x3508）でも A3（3508x4961）でも、幅に合わせて大きさを変える。

使い方:
  python scripts/patch_poster_rules_box.py <元のPNG> <出力PNG>
"""
import sys
import tempfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from make_poster import CHROME, _route_local_fonts  # noqa: E402  ローカルの Noto Sans JP を差し込む

FILL = (250, 247, 240)          # 枠の塗り
INSET = 20                      # 枠の線と角の丸みを残すため、塗りの内側だけを描き直す（A4 の px）

HTML = """<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap" rel="stylesheet">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ width:{w}px; height:{h}px; background:transparent; overflow:hidden; }}
  body {{ font-family:'Noto Sans JP', sans-serif; padding:2px 25px 0; display:flex; flex-direction:column; }}
  .top {{ display:flex; align-items:center; height:98px; }}
  .rh {{ font-weight:900; font-size:60px; color:#111; letter-spacing:0.01em; white-space:nowrap; font-feature-settings:'palt'; }}
  .div {{ width:3px; align-self:stretch; margin:6px 40px; background:rgb(219,212,194); }}
  .rb {{ flex:1; font-size:33px; line-height:1.48; color:rgb(72,64,56); white-space:nowrap;
        text-align:justify; text-align-last:justify; }}
  .chips {{ display:flex; align-items:center; gap:18px; margin-top:12px; height:56px; }}
  .lbl {{ font-weight:700; font-size:31px; color:rgb(180,96,64); white-space:nowrap; margin-right:6px; }}
  .chip {{ flex:1 1 auto; text-align:center; font-weight:500; font-size:31px; color:#222; white-space:nowrap;
          background:rgb(242,236,224); border:3px solid rgb(216,208,192); border-radius:999px; padding:4px 18px; }}
  .rn {{ margin-top:14px; font-size:29px; color:rgb(104,96,88); white-space:nowrap;
        text-align:justify; text-align-last:justify; }}
</style></head><body>
  <div class="top">
    <div class="rh">空き教室は、みんなで使う場所です。</div>
    <div class="div"></div>
    <div class="rb">使う目的は人それぞれ。静かさを求めすぎず、大きな声で騒がず、<br>お互いの利用目的を尊重し、周囲に配慮して利用しましょう。</div>
  </div>
  <div class="chips"><span class="lbl">使い方の例</span><span class="chip">個人学習</span><span class="chip">グループワーク</span><span class="chip">課題についての相談</span><span class="chip">学生同士の打合せ</span><span class="chip">授業の合間の休憩</span></div>
  <div class="rn">※ 空き教室は自習専用のスペースではありません。静かな環境で学習したい場合は、図書館または1号館のCSTギャラリーをご利用ください。</div>
</body></html>"""


def find_fill(im):
    """枠の塗りの範囲（左・上・右・下）。縦は枠の左の余白（文字の無い列）、横は枠の上の余白（文字の無い行）で測る"""
    W, H = im.size
    px = im.load()
    near = lambda p: all(abs(a - b) <= 2 for a, b in zip(p, FILL))
    xs = round(W * 0.075)                       # 枠の左の余白（文字は 0.079W から）
    shaded = lambda p: all(abs(a - b) <= 12 for a, b in zip(p, FILL))   # 左上は影で少し暗い
    rows = [y for y in range(int(H * 0.72), int(H * 0.9)) if shaded(px[xs, y])]
    if not rows:
        raise SystemExit("枠が見つかりません（元の画像か確認してください）")
    runs, start, prev = [], rows[0], rows[0]
    for y in rows[1:]:
        if y != prev + 1:
            runs.append((start, prev))
            start = y
        prev = y
    runs.append((start, prev))
    y0, y1 = max(runs, key=lambda r: r[1] - r[0])   # いちばん長く続く区間が枠
    # 横は、文字の無い行（行と行のすき間）で、塗りが途切れずに続くいちばん広い区間
    best = (0, -1)
    for y in range(y0 + 8, y1 - 8, 3):
        x = W // 2
        if not shaded(px[x, y]):
            continue
        lo, hi = x, x
        while lo > 0 and shaded(px[lo - 1, y]):
            lo -= 1
        while hi < W - 1 and shaded(px[hi + 1, y]):
            hi += 1
        if hi - lo > best[1] - best[0]:
            best = (lo, hi)
    return best[0], y0, best[1], y1


def render_box(w_css, h_css, scale):
    with tempfile.TemporaryDirectory() as td:
        html = Path(td) / "box.html"
        html.write_text(HTML.format(w=w_css, h=h_css, fill=FILL), encoding="utf-8")
        out = Path(td) / "box.png"
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=CHROME)
            page = b.new_page(viewport={"width": w_css, "height": h_css}, device_scale_factor=scale)
            _route_local_fonts(page)
            page.goto(html.as_uri(), wait_until="networkidle")
            page.wait_for_timeout(500)
            overflow = page.evaluate("""() => [...document.querySelectorAll('.rh,.rb,.chips,.rn')]
                .filter(e => e.scrollWidth > e.clientWidth + 1).map(e => e.className)""")
            if overflow:
                raise SystemExit(f"枠からはみ出す要素があります: {overflow}")
            page.screenshot(path=str(out), omit_background=True)
            b.close()
        return Image.open(out).convert("RGBA")


def erase_text(im, region):
    """region（左・上・右・下）の中の文字・ラベル・区切り線を消し、周りの背景で補う。影のなだらかな濃淡は残す"""
    try:
        import cv2                  # 文字を消したあとの背景を補う（任意の依存。ポスターを直すときだけ使う）
        import numpy as np
    except ImportError as exc:
        raise SystemExit("opencv-python-headless が要ります: pip install opencv-python-headless") from exc
    left, top, right, bottom = region
    a = np.array(im)[top:bottom, left:right].astype(int)
    dev = np.abs(a - np.array(FILL)).max(axis=2)
    mask = (dev > 12).astype(np.uint8) * 255          # 影は 11 以下、文字・ラベル・線はそれより濃い
    mask = cv2.dilate(mask, np.ones((9, 9), np.uint8))  # 文字のふちのにじみも消す
    bgr = cv2.cvtColor(a.astype(np.uint8), cv2.COLOR_RGB2BGR)
    fixed = cv2.inpaint(bgr, mask, 7, cv2.INPAINT_TELEA)
    im.paste(Image.fromarray(cv2.cvtColor(fixed, cv2.COLOR_BGR2RGB)), (left, top))


def patch(src, out):
    im = Image.open(src).convert("RGB")
    f = im.size[0] / 2480
    x0, y0, x1, y1 = find_fill(im)
    inset = round(INSET * f)
    erase_text(im, (x0 + inset, y0 + round(4 * f), x1 - inset, y1 - round(4 * f)))
    left, top, right, bottom = x0 + inset, y0 + round(12 * f), x1 - inset, y1 - round(12 * f)
    w_css, h_css = round((right - left) / f), round((bottom - top) / f)
    box = render_box(w_css, h_css, f).resize((right - left, bottom - top))
    im.paste(box, (left, top), box)
    im.save(out, optimize=True)
    return out, (x0, y0, x1, y1)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    print("saved", *patch(sys.argv[1], sys.argv[2]))
