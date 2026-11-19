# リール3本「あるある・クイズ・ランキング」（2026-11-18）

運営の依頼「伸びそうなリール動画を2〜3本」。追加の課金なし（AI の映像なし）で、この環境の中だけで作った。どれも 1080×1920・30fps・H.264＋AAC、-14 LUFS。

| 完成版（`assets/instagram/cm/`） | 長さ | 中身 | ねらい |
|---|---|---|---|
| `reel7-aruaru-v1.mp4` | 13.2秒 | 「空きコマ90分、どこ行く？」→ 教室を回るたびに「授業中」（S503・S602・142）→「そして、休み時間が終わる。」→ 開けた瞬間、いま使える教室（アプリの実画面・駿河台校舎・水曜3限、705 に印）→ 終わりの札 | 学生の「あるある」で共感 → 解決。シェアされやすい |
| `reel8-quiz-v1.mp4` | 14.4秒 | QUIZ「駿河台キャンパスで空き教室がいちばん少ないのは？」→ 3択（月曜1限／水曜3限／金曜5限）と3秒のカウントダウン → 正解 水曜3限（24室。ほかは49室・52室）→ 曜日×時限の空き教室の表「ねらい目は5限・6限」「月曜6限は64室中61室が空き」→ 終わりの札 | 考えさせて最後まで見てもらう。数字の表は保存されやすい |
| `reel9-ranking-v1.mp4` | 13.6秒 | 「空きコマ、みんな何してる？」→ 5位から順に（その他4%・打合せ9%・グループワーク11%・休憩19%・1位 個人学習57%）→「空き教室で、それぞれの空きコマを。」と使い方の札（授業が優先・静かに・ゴミは持ち帰る）→ 終わりの札 | ランキングは最後まで見られやすい。使い方の約束も伝える |

カバーは同じ名前の `-cover.jpg`（つかみの文字が出そろったコマ）。

## v2（2026-11-18、運営の意見「2・3本目のクオリティをもうちょっと上げたら投稿できそう。Blender と連携してよりリアルに」）

- `reel8-quiz-v2.mp4`・`reel9-ranking-v2.mp4`。3D の場面を Blender 4.5（Cycles）で描き、文字はこれまでどおり HTML で重ねた（`r2b.html`・`r3b.html`）。
- 3D：`blender/r2_scene.py`（曜日×時限の空き教室の数を柱の高さにした街）、`blender/r3_scene.py`（使い方の小物を載せた棒が床の下からせり上がるランキング）。どちらも時刻 t＝フレーム t×30 で、HTML と同じ時刻表で動く。
- 文字を 3D に合わせる：Blender で棒・柱の画面の位置を `frames*/anchors.json` に書き出し、HTML がそこへ文字を置く（端で切れないよう、大きな札は画面の内側に寄せる）。
- この環境に GPU は無いので、Cycles は CPU で 720×1280・16サンプル＋ノイズ除去（約9秒/コマ）。HTML 側で 1080×1920 に広げて重ねる。EEVEE はソフトウェアの OpenGL だと遅い（約67秒/コマ）ので使わない。
- Blender は Python のモジュール `bpy==4.5.16`（PyPI。Python 3.11 用）。作業用の仮想環境に入れて使った（約1GB。リポジトリには入れない）:
  ```bash
  python3 -m venv /tmp/blendervenv && /tmp/blendervenv/bin/pip install bpy==4.5.16
  cd video/reels-1118/blender
  /tmp/blendervenv/bin/python r3_scene.py preview 2.6,6.4,8.5     # 下書き（小さく）
  /tmp/blendervenv/bin/python r3_scene.py render                   # 本番（frames3/。止めても続きから。約30分）
  /tmp/blendervenv/bin/python r2_scene.py render                   # 本番（frames2/。約55分）
  cd .. && python3 render.py r3b.html --out out-r3b.mp4 --audio r3.wav
  python3 render.py r2b.html --out out-r2b.mp4 --audio r2.wav
  ```

## 数字の根拠

- **クイズ**：`schedule_final.db` の 2026年度・後期。駿河台キャンパス（タワー・スコラ 38室＋駿河台校舎 26室＝64室）で、その曜日・時限に時間割上の授業が入っていない教室の数（隔週の授業も「入っている」に数える）。月〜金×1〜6限の表は `r2.html` の `GRID`。水曜3限の24室は全コマで最少で、3D 広告（cm5）の数字と同じ。
- **ランキング**：アプリの任意・匿名の質問「何に使う？」の回答 140件（`data/ga4_breakdown.json` の `purposes`。2026-11-15 まで）。個人学習 80・休憩 27・グループワーク 15・打合せ 12・その他 6 を割合にした（57・19・11・9・4、計100）。
- **あるある**の教室名（S503・S602・142）は実在する教室だが、「授業中」は演出（特定の日の事実ではない）。

## 決まりの確認

- 最後に必須の表記（学生課の文言）を約2.6秒出す。船橋校舎は映さない・書かない。「予約」「確保」は使っていない。
- アプリの画面は本物（駿河台校舎のタブ。船橋のタブは撮影時に隠してある）。7階以上の教室は映していない。
- 人の顔・大学や実在の会社のロゴ・既存の曲は使っていない。AI の映像は使っていないので、キャプションの AI の注記は不要。
- 音は `music.py`（numpy で合成。倍音の足し算なので音程はずれない）。効果音（はんこ・カチッ・鐘など）も合成。

## 作り直し方

```bash
cd video/reels-1118
bash fetch_fonts.sh                                    # 書体（Noto Sans CJK JP・M PLUS Rounded 1c・Syne。OFL）
mkdir -p vendor && (cd vendor && npm pack gsap@3.14.2 --silent && tar -xzf gsap-3.14.2.tgz package/dist/gsap.min.js && mv package/dist/gsap.min.js . && rm -rf package gsap-*.tgz)   # GSAP（CDN は届かない）
cp ../desk-3d/assets/logo.png assets/logo.png          # ロゴ
cp ../desk-3d/assets/page0.png assets/page0.png        # アプリの実画面（無ければ desk-3d の capture.py で撮る）
python3 render.py r1.html --sheet 0.9,2.9,6.5,9.6,12.6 # 下書きのコマの一覧（pv-r1.png）
python3 music.py r1                                    # 音（r1.wav）
python3 render.py r1.html --out out-r1.mp4 --audio r1.wav   # 本番（約2.5分）
```

- 1本の HTML が1本の動画。GSAP のタイムラインを止めたまま持ち、`render.py` が `renderAt(t)` で1コマずつ進めて撮り、ffmpeg でつなぐ（3D が無いので速い。1コマ約0.35秒）。
- 共通の見た目は `common.css`、終わりの札は `common.js` の `addEnd()`。GSAP は `vendor/gsap.min.js`（npm の gsap@3.14.2 を上の手順で取る。リポジトリには入れない）。

## 2本目 v4（黒板。2026-11-19、運営の意見「3本目と雰囲気が被ってるから全く違うものに」）

- `reel8-quiz-v4.mp4`。背景は `blender/r2_board.py` で描いた昼間の教室の黒板（`assets/board.png`、窓枠の影つき）と黒板消し（`assets/eraser.png`、背景透明）の静止画2枚だけ（Cycles 96サンプル、約2分）。
- 動きはすべて `r2d.html`：手書き風の書体（Yusei Magic）に SVG のフィルタでチョークのかすれを付け、左から書いていくように見せる。丸・下線・表の線は SVG の線を描き足していく。黒板全体をゆっくり寄せる。
- 音は `python3 music.py r2d`（木琴・手拍子・チョークで書く音・黒板消し）。チョークの音は高い音が多く、AAC にすると瞬間の値がはみ出しやすいので、まとめるときに `lowpass=f=15000,alimiter=limit=0.79` をかけた。
