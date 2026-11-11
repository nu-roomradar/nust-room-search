# 3D 広告「机の上」（縦 1080×1920・30秒・7場面）

2026-11-12、運営の企画文をもとに作成。夕方の空き教室の机の上だけで、時間割の紙 → 空きコマが光る → スマホ（アプリの実画面）→ 報告 → 時限の終わりで消える → 決めの言葉 → ロゴと必須の表記、と進む。
完成版は `assets/instagram/cm/cm5-desk-3d-v1.mp4`。

## 作り方（この環境でそのまま作り直せる）

```bash
cd video/desk-3d
bash fetch_fonts.sh          # 書体（Noto Sans CJK JP・Syne。OFL）を fonts/ に
bash fetch_vendor.sh         # three.js 0.170.0（MIT）を npm から vendor/ に（CDN はこの環境から届かない）
# アプリの実画面を撮り直すとき（時刻を 水曜 14:40 に固定して起動 → 撮影）
python3 fakeapp.py &  ;  python3 capture.py  ;  kill %1  ;  rm -f ../../reports.db
python3 sheet.py 1.5,6.5,10.8,13.6,15.6,18.5,22.8,27 --scale 0.4 --cols 8   # 下書きのコマの一覧（renders/pv/sheet.jpg）
python3 render.py --out renders/frames                                       # 本番（全900コマ。途中で止めても続きから）
python3 music.py                                                             # 音（自作）
bash encode.sh                                                               # コマと音をつないで mp4 に
```

- **HyperFrames ではなく自前の書き出し（`render.py`）にした理由**：3D（WebGL）をこの環境で描くと、GPU が無いので Chrome の中のソフトウェア描画（SwiftShader）になり、1コマに数秒かかる。途中で止めて続きから撮れる・コマごとに時間を測れる形が要ったので、`video/cm-ai` と同じ「1コマずつ撮る」方式にした。`index.html` は `hf-seek` も受けるので、HyperFrames から時刻を送ることもできる。
- 時刻 `t` だけで絵が決まる（`window.renderAt(t)`）。場面の切れ目は `scene.js` の先頭の `T` に集めてある。音（`music.py`）も同じ時刻に合わせている。
- 描いているもの：机（木の写真を貼った板）、紙（canvas で描いた時間割。架空の時間割）、光る札、レーダーの輪（机の面のシェーダー）、スマホ（アプリの実画面の写真を canvas に描いて貼る）、置き時計、鉛筆、ぼけて見える教室。光は「窓の形のスポットライト（桟の影つき）」。後処理は 浅いピント（自作）→ 光のにじみ → 色 → 粒子。

## 中身で確かめたこと

- **「水曜3限でも、24室が空き」**：`schedule_final.db` の 2026年度・後期。駿河台キャンパス（タワー・スコラ 38室＋駿河台校舎 26室＝64室）のうち、水曜3限に時間割上の授業が無いのは 24室（タワー・スコラ 12・駿河台校舎 12）。全曜日・全時限で最も少ないコマ。
- **スマホの画面**は本物のアプリ（駿河台校舎のタブ・水曜3限）。「実は使われていた」→ 1件（⚠1件報告）→ 2件（使用中の可能性）は、実際に報告を2件入れて撮った。報告は時限が終わると消える（アプリの仕様どおり）。
- 船橋校舎のタブは撮影時に隠した（`capture.py` の `HIDE`。学生課の依頼で近く外す予定の表示でもある）。画面はすべて駿河台校舎。7階以上の教室（学生課の依頼で外す予定）も映していない。
- 「予約」「確保」は使っていない。最後に必須の表記（学生課の文言）を約4.8秒出す。人の顔・大学のロゴ・看板・校舎の名前の看板は無い。

## 素材の出どころ

| 素材 | 出どころ | 許諾 |
|---|---|---|
| 机の木目 `assets/wood_src.jpg` | Wikimedia Commons「Pressed pine wood grain and texture close up.jpg」（幅1920の縮小版） | CC0 |
| ロゴ `assets/logo.png` | `video/cm-ai/rr_logo_hd.png` | 自前 |
| アプリの画面 `assets/page*.png`・`modal*.png`・`view0.png` | `capture.py` で撮影（作り直せるのでリポジトリには入れない） | 自前 |
| 書体 | Noto Sans CJK JP・Syne | SIL OFL |
| three.js | npm `three@0.170.0` | MIT |
| 音 | `music.py`（numpy で合成。既存の曲は不使用） | 自前 |

AI で生成した映像は使っていない（全部この環境で描いた 3D）。キャプションの「※映像はAIで生成したイメージです」は不要。入れるなら「※映像は3DCGのイメージです」。
