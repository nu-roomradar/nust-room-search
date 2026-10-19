# 409x239 のロゴを 4 倍の解像度に起こし直す。輪郭は potrace でなめらかな曲線にし、中の色は高品質に拡大する
import sys, numpy as np, potrace
from PIL import Image, ImageDraw, ImageFilter
S = sys.argv[1]; F = 4; SS = 4      # 出力倍率、輪郭のアンチエイリアス用の内部倍率
src = Image.open(f"{S}/rr_logo.png").convert("RGBA")
w, h = src.size
a = np.asarray(src).astype(np.float32) / 255
alpha = a[..., 3]
# 色: ふちの暗いにじみ（元画像のアンチエイリアス）を使わず、内側のしっかり不透明な色を外へ広げてから拡大する
lum = a[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
art = alpha * np.clip((lum - 0.18) / 0.12, 0, 1)        # 元画像の暗いふち線は使わない
solid = art > 0.92
col = a[..., :3].copy()
def blur(x, r):
    return np.asarray(Image.fromarray((np.clip(x, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))).astype(np.float32) / 255
filled = col * solid[..., None]; got = solid.copy()
for r in (1, 2, 3, 5, 8, 12):
    wgt = blur(solid.astype(np.float32), r)
    est = np.dstack([blur(col[..., i] * solid, r) for i in range(3)]) / np.maximum(wgt[..., None], 1e-3)
    take = (~got) & (wgt > 0.02)
    filled[take] = est[take]; got |= take
col = np.where(solid[..., None], col, filled)
pre = np.dstack([col, np.ones_like(alpha)])
up = Image.fromarray((pre * 255).astype(np.uint8), "RGBA").resize((w * F, h * F), Image.LANCZOS)
u = np.asarray(up).astype(np.float32) / 255
rgb = np.clip(u[..., :3], 0, 1)
rgb_img = Image.fromarray((rgb * 255).astype(np.uint8), "RGB").filter(ImageFilter.UnsharpMask(radius=3, percent=60, threshold=2))
# 輪郭: アルファを 2 倍に拡大してから二値化してトレース（細い部分を潰さない）
a2 = np.asarray(Image.fromarray((art * 255).astype(np.uint8)).resize((w * 2, h * 2), Image.BICUBIC)) > 127
path = potrace.Bitmap(a2).trace(turdsize=4, alphamax=1.0, opticurve=True, opttolerance=0.2)
k = F * SS / 2
mask = np.zeros((h * F * SS, w * F * SS), bool)
def P(p):
    return np.array([p.x, p.y], float) if hasattr(p, "x") else np.array(p, float)
def bez(p0, c1, c2, p1, n=24):
    t = np.linspace(0, 1, n)[:, None]
    return ((1-t)**3)*p0 + 3*((1-t)**2)*t*c1 + 3*(1-t)*t*t*c2 + t**3*p1
for curve in path:
    pts = [P(curve.start_point)]
    cur = P(curve.start_point)
    for seg in curve.segments:
        if seg.is_corner:
            pts += [P(seg.c), P(seg.end_point)]
        else:
            pts += list(bez(cur, P(seg.c1), P(seg.c2), P(seg.end_point))[1:])
        cur = P(seg.end_point)
    poly = Image.new("1", (w * F * SS, h * F * SS), 0)
    ImageDraw.Draw(poly).polygon([(float(x) * k, float(y) * k) for x, y in pts], fill=1)
    mask ^= np.asarray(poly)                                     # 偶奇規則で穴を抜く
ref = np.asarray(Image.fromarray(a2.astype(np.uint8) * 255).resize(mask.shape[::-1], Image.NEAREST)) > 127
if (mask == ref).mean() < (~mask == ref).mean():   # トレースの向きが逆なら反転する
    mask = ~mask
print("match", (mask == ref).mean())
m = Image.fromarray((mask * 255).astype(np.uint8)).resize((w * F, h * F), Image.LANCZOS)
out = rgb_img.convert("RGBA"); out.putalpha(m)
out.save(f"{S}/rr_logo_hd.png"); print(out.size, len(path))
# 確認用: 黒・白の背景に並べる（左: 元を単純拡大、右: 起こし直し）
crop = (int(w*F*0.18), int(h*F*0.05), int(w*F*0.58), int(h*F*0.55))
naive = src.resize((w * F, h * F), Image.BICUBIC)
for bg, name in (((8, 10, 16, 255), "dark"), ((250, 250, 248, 255), "light")):
    sheet = Image.new("RGBA", ((crop[2]-crop[0]) * 2 + 20, crop[3]-crop[1]), bg)
    for i, im in enumerate((naive, out)):
        tile = Image.new("RGBA", im.size, bg); tile.alpha_composite(im)
        sheet.paste(tile.crop(crop), (i * ((crop[2]-crop[0]) + 20), 0))
    sheet.save(f"{S}/logo_cmp_{name}.png")
