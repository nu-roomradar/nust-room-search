"""src/ の AI 動画から、CM で使う部分をコマ画像（JPEG 連番）に切り出す。

  python3 extract_clips.py v3   # Vlog 風（cm4.html）: clips4/ と clips4.json。自然な色・粒子・手持ちの揺れ
  python3 extract_clips.py v2   # Pixel 風（cm3.html）: clips/ と clips.json。拡大して輪郭補正だけ

切り出しの理由（どれも src の動画に合わせた値）
- c3・c4・c5 は上下に黒い帯があるので crop で落とす
- c3 はノートPCのふたのロゴが映らない区間、c4 は右端のPCのロゴを枠の外に出す
- c5 は緑の光の粒（レンズフレア）が出ない区間
"""
import glob
import json
import os
import shutil
import subprocess
import sys

# 枠: (元の動画, 開始秒, 長さ, 切り出し w:h:x:y)
V2 = {
    "A1": ("src/c0.mp4", 1.3, 2.0, None), "A2": ("src/c0.mp4", 4.6, 2.0, None),
    "A3": ("src/c1.mp4", 2.6, 2.0, None), "A4": ("src/c2.mp4", 1.0, 2.0, None),
    "A5a": ("src/c3.mp4", 3.0, 1.5, "593:1054:63:112"), "A5b": ("src/c4.mp4", 4.4, 1.5, "587:1044:48:118"),
    "A6": ("src/c5.mp4", 3.0, 2.0, "610:1084:55:98"),
}
V3 = {
    "A1": ("src/c0.mp4", 1.2, 2.0, None), "A2": ("src/c0.mp4", 4.6, 2.0, None),
    "A3": ("src/c1.mp4", 2.8, 1.5, None), "A4": ("src/c2.mp4", 1.0, 2.0, None),
    "A5a": ("src/c3.mp4", 2.9, 1.5, "593:1054:63:112"), "A5b": ("src/c4.mp4", 4.2, 2.0, "587:1044:48:118"),
    "A6": ("src/c5.mp4", 2.9, 3.0, "610:1084:55:98"),
}


def filters(version, crop, k):
    if version == "v2":
        return ",".join(filter(None, [f"crop={crop}" if crop else None,
                                      "scale=1080:1920:flags=lanczos", "unsharp=5:5:0.55:5:5:0", "fps=30"]))
    ph = k * 1.3  # 揺れの位相をカットごとに変える
    return ",".join(filter(None, [
        f"crop={crop}" if crop else None,
        "scale=1144:2034:flags=lanczos",
        # 手持ちの細かい揺れ（ゆっくりした揺れ＋小さな震え）
        f"crop=1080:1920:x='32+11*sin(2*PI*t*0.63+{ph})+4*sin(2*PI*t*1.9+{ph}*2)'"
        f":y='57+9*sin(2*PI*t*0.47+{ph}*1.7)+3*sin(2*PI*t*2.3+{ph})'",
        # AI 動画の金色の光を、ふつうの昼間の色へ
        "colorbalance=rs=-.07:bs=.05:rm=-.06:bm=.05:rh=-.05:bh=.03",
        "eq=saturation=0.84:contrast=1.03",
        "curves=all='0/0.025 0.5/0.49 1/0.93'",
        "gblur=sigma=0.55",          # つるつるの質感を少し丸める
        "noise=alls=9:allf=t+u",     # スマホ動画らしい粒子
        "vignette=PI/6",
        "fps=30"]))


def main(version):
    slots, out = (V2, "clips") if version == "v2" else (V3, "clips4")
    shutil.rmtree(out, ignore_errors=True)
    info = {}
    for k, (slot, (src, ss, dur, crop)) in enumerate(slots.items()):
        os.makedirs(f"{out}/{slot}", exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(ss), "-t", str(dur), "-i", src,
                        "-vf", filters(version, crop, k), "-q:v", "3", f"{out}/{slot}/%04d.jpg"], check=True)
        info[slot] = {"frames": len(glob.glob(f"{out}/{slot}/*.jpg")), "start": 0, "dir": slot}
    json.dump(info, open(f"{out}.json", "w"), indent=1)
    print(info)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main(sys.argv[1] if len(sys.argv) > 1 else "v3")
