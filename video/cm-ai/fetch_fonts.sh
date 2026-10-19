#!/usr/bin/env bash
# CM の書き出しに使うフォントを fonts/ に入れる（どれも SIL OFL。容量が大きいのでリポジトリには入れない）
set -euo pipefail
cd "$(dirname "$0")"; mkdir -p fonts; cd fonts
N=https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/Japanese
G=https://raw.githubusercontent.com/google/fonts/main/ofl
for w in Regular Medium Bold Black; do [ -s NotoSansCJKjp-$w.otf ] || curl -sSfL -o NotoSansCJKjp-$w.otf "$N/NotoSansCJKjp-$w.otf"; done
for w in Medium Bold ExtraBold Black; do [ -s MPLUSRounded1c-$w.ttf ] || curl -sSfL -o MPLUSRounded1c-$w.ttf "$G/mplusrounded1c/MPLUSRounded1c-$w.ttf"; done
[ -s YuseiMagic-Regular.ttf ] || curl -sSfL -o YuseiMagic-Regular.ttf "$G/yuseimagic/YuseiMagic-Regular.ttf"
ls -la
