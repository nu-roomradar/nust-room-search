# 人が出てこない Pixel 風（文字が主役）15秒

`assets/instagram/cm/cm4-pixel-type-v1.mp4` の素材。HyperFrames（`/make-video` の3）で作った最初の1本（2026-10-19）。
人の映像は使わず、文字・アプリの実画面・S305 の実際の空き（`schedule_final.db`）・ロゴだけで作っている。

| 秒 | 場面 |
|---|---|
| 0〜2 | 「空き／コマ」が1文字ずつ弾んで出る（青） |
| 2〜3.5 | 「どこ行く？」と大きな「？」（黄） |
| 3.5〜5.5 | 「どこも…」図書館→学食→ラウンジがスロットのように回り、「いっぱい。」のスタンプ（ピンク） |
| 5.5〜8 | 「開くだけで、」端末が上がって結果までスクロール、件数チップから大きな「14」が飛び出して「室、空いてる。」（緑） |
| 8〜10 | 「4限まで、ずっと空いてる。」S305 のカード（青） |
| 10〜12 | 「1週間も、ひと目で。」S305 の後期の空きが波のように並ぶ（火曜を枠で強調） |
| 12〜15 | ロゴ（レーダーの輪 → 一周して現れる → 波紋 → 光）と TEST 表記 |

## 作り直す手順

```bash
cd video/pixel-type
mkdir -p fonts && cp ../cm-ai/fonts/{MPLUSRounded1c-Black.ttf,MPLUSRounded1c-ExtraBold.ttf,NotoSansCJKjp-Bold.otf,NotoSansCJKjp-Medium.otf} fonts/   # 無ければ ../cm-ai/fetch_fonts.sh
mkdir -p vendor && (cd vendor && npm pack gsap@3.14.2 --silent && tar -xzf gsap-3.14.2.tgz package/dist/gsap.min.js && mv package/dist/gsap.min.js . && rm -rf package gsap-*.tgz)
python3 music5.py music5.wav && python3 mix5.py            # audio.wav（BGM＋効果音）
export HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_SKIP_SKILLS=1 CI=1
npx -y hyperframes@0.8.174 browser ensure
npx -y hyperframes@0.8.174 lint
npx -y hyperframes@0.8.174 snapshot --at 5.2,6,8.9,10.6     # 確認用のコマ（.hyperframes/artifacts/snapshots/）
npx -y hyperframes@0.8.174 render --quality delivery --output out-final.mp4
```

- 文字・色・タイミングはすべて `index.html` の CSS と GSAP のタイムライン（秒）。場面の長さを変えたら各 `<section>` の `data-start`/`data-duration`、`mix5.py` の効果音の時刻、`music5.py` の `END` も合わせる。
- 「14」はタワー・スコラの火曜2限の件数（撮影時の画面）。時間割が変わったら `../cm-ai/capture.py` で撮り直し、数字と注記を合わせる。
- lint の警告 `nested_structure_needs_subcomposition` は Studio での見え方の話で、書き出しには影響しない（1ファイルで作っているため）。
