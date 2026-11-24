#!/usr/bin/env bash
# 3D 広告の書き出しに使うフォントを fonts/ に入れる（どれも SIL OFL。容量が大きいのでリポジトリには入れない）
set -euo pipefail
cd "$(dirname "$0")"; mkdir -p fonts; cd fonts
N=https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/Japanese
G=https://raw.githubusercontent.com/google/fonts/main/ofl
M=https://raw.githubusercontent.com/notofonts/noto-cjk/main/Serif/OTF/Japanese
for w in Regular Medium Bold Black; do [ -s NotoSansCJKjp-$w.otf ] || curl -sSfL -o NotoSansCJKjp-$w.otf "$N/NotoSansCJKjp-$w.otf"; done
for w in Medium SemiBold Bold Black; do [ -s NotoSerifCJKjp-$w.otf ] || curl -sSfL -o NotoSerifCJKjp-$w.otf "$M/NotoSerifCJKjp-$w.otf"; done   # 明朝（広告・予告の字）
for w in Medium Bold ExtraBold Black; do [ -s MPLUSRounded1c-$w.ttf ] || curl -sSfL -o MPLUSRounded1c-$w.ttf "$G/mplusrounded1c/MPLUSRounded1c-$w.ttf"; done
[ -s YuseiMagic-Regular.ttf ] || curl -sSfL -o YuseiMagic-Regular.ttf "$G/yuseimagic/YuseiMagic-Regular.ttf"
[ -s Syne-wght.ttf ] || curl -sSfL -o Syne-wght.ttf "$G/syne/Syne%5Bwght%5D.ttf"   # アプリのロゴ・教室名の書体
ls -la
