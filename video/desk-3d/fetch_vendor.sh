#!/usr/bin/env bash
# 3D の描画に使う three.js を vendor/ に入れる（MIT。npm から版を決めて取る。CDN はこの環境から届かない）
set -euo pipefail
cd "$(dirname "$0")"; mkdir -p vendor; cd vendor
V=0.170.0
[ -s three/three.module.js ] && { echo "three は取得済み"; exit 0; }
npm pack three@$V --silent >/dev/null && tar -xzf three-$V.tgz
mkdir -p three/addons && cp package/build/three.module.js three/ && cp package/LICENSE three/LICENSE
for d in postprocessing shaders geometries environments; do cp -r package/examples/jsm/$d three/addons/; done
rm -rf package three-$V.tgz; du -sh three
