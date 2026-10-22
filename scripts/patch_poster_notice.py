#!/usr/bin/env python3
"""どこ行く？版ポスター（Claude Design 製・assets/posters/claude-design/）の下の帯の表示文言を差し替える。

Claude Design で作り直さずに、帯の中の文字だけを描き直す。2026-10-22 に、理工学部学生課の提案で
表示を「本サービスは、学生が「自主創造プロジェクト」の一環として開発・運営している試験運用中の
サービスです。大学が公式に提供するサービスではありません。」に変えたときに作った。

帯の中の四角（塗り色 FILL）を探して、TEST の札より右を塗りつぶし、2行で書き直す。
強調の色はこのポスターのアクセント（テラコッタ）の明るい色にそろえる。
A4（2480x3508）でも A3（3508x4961）でも、幅に合わせて大きさを変える。

使い方:
  python scripts/patch_poster_notice.py <元のPNG> <出力PNG>
  元の PNG は git の履歴（2026-10-21 版）から取り出す。PDF は出力 PNG を 300dpi で PDF にする。
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT = str(ROOT / "video/cm-ai/fonts/NotoSansCJKjp-{}.otf")   # video/cm-ai/fetch_fonts.sh で入る
FILL = (40, 50, 77)            # 帯の中の四角の塗り
WHITE = (226, 233, 247)        # 元の本文の色
ACCENT = (242, 167, 132)       # テラコッタ（ポスターの「？」・付箋の矢印）の明るい色。紺の上で読める
LINE1 = [("本サービスは、学生が「自主創造プロジェクト」の一環として開発・運営している", WHITE, "Medium"),
         ("試験運用中のサービス", ACCENT, "Bold"), ("です。", WHITE, "Medium")]
LINE2 = [("大学が公式に提供するサービスではありません。", WHITE, "Medium")]


def near(px, color, tol=2):
    return all(abs(a - b) <= tol for a, b in zip(px, color))


def find_box(im):
    """帯の中の四角の上端・下端・右端（塗り色 FILL の範囲）"""
    W, H = im.size
    px = im.load()
    f = W / 2480
    xs = int(1500 * f)
    rows = [y for y in range(int(H * 0.85), H) if near(px[xs, y], FILL)]
    if not rows:
        raise SystemExit("帯の四角が見つかりません（元の画像か確認してください）")
    ymid = (rows[0] + rows[-1]) // 2
    xr = max(x for x in range(W) if near(px[x, ymid], FILL))
    return rows[0], rows[-1], xr


def patch(src, out):
    im = Image.open(src).convert("RGB")
    W, _ = im.size
    f = W / 2480
    y0, y1, xr = find_box(im)
    x0 = int(400 * f)              # TEST の札の右
    d = ImageDraw.Draw(im)
    d.rectangle([x0, y0 + int(4 * f), xr - int(12 * f), y1 - int(4 * f)], fill=FILL)
    size = round(37 * f)
    fonts = {w: ImageFont.truetype(FONT.format(w), size) for w in ("Medium", "Bold")}
    line_h = round(54 * f)
    top = (y0 + y1) / 2 - (size + line_h) / 2 - size * 0.12
    for i, line in enumerate((LINE1, LINE2)):
        x = x0 + int(14 * f)
        for text, color, weight in line:
            d.text((x, top + i * line_h), text, font=fonts[weight], fill=color)
            x += d.textlength(text, font=fonts[weight])
        if x >= xr - 20 * f:
            raise SystemExit(f"文字が四角からはみ出します（{x:.0f} >= {xr}）")
    im.save(out, optimize=True)
    return out


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    print("saved", patch(sys.argv[1], sys.argv[2]))
