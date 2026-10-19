# CM（AI 動画版）の編集素材

`assets/instagram/cm/cm2-pixel-v2.mp4`（Pixel 風）と `cm3-vlog-v3.mp4`（Vlog 風）を作り直すための一式。
HTML で1コマずつ描いて Playwright で撮り、ffmpeg で MP4 にする自前の仕組み（2026-10 作成）。
新しく動画を作るときは、まず `/make-video` スキルを読む（HyperFrames を使う手順もそこにある）。

## 中身

| ファイル | 役割 |
|---|---|
| `src/c0.mp4`〜`c5.mp4` | AI 動画の原本（運営が Gemini で生成、各8秒・720×1280）。c0 授業後〜「どこ行く？」／c1 スマホを見て笑顔／c2 空き教室のドア／c3 窓際で課題／c4 3人で笑う／c5 ハイタッチ |
| `cm4.html` | **v3（Vlog 風）**の台本。場面の切り替え・字幕・手書きの書き込み・画面録画・ロゴのアニメ |
| `cm3.html` | v2（Pixel 風）の台本 |
| `render4.py` / `render.py` | v3 / v2 の書き出し（`--preview 秒,秒,...` で確認用のコマだけ撮れる） |
| `extract_clips.py` | `src/` から使う部分をコマ画像に切り出す（v3 は色調整・粒子・手持ちの揺れ付き） |
| `music4.py` / `music3.py` | 自作 BGM（numpy で合成。既存の曲は使っていない） |
| `mix4.py` / `mix3.py` | BGM＋AI 動画の生の音＋効果音を混ぜる（`mix4.py out.wav nobgm` で BGM なし） |
| `cap-tower-full.png` / `cap-room-full.png` / `card-s305.png` / `rects.json` | アプリの実画面（火曜 10:52・タワースコラで撮影）と、その中の位置 |
| `capture.py` / `fakeapp.py` | 上の実画面を撮り直すとき用。時刻を固定してアプリを起動し、390px・3倍で撮る |
| `rr_logo_hd.png` / `logo_hd.py` | 高解像度化したロゴ（元は git 履歴の `rr_logo.png`、409×239 を4倍に） |
| `grain.png` | フィルムの粒子 |
| `fetch_fonts.sh` | フォント（Noto Sans CJK JP・M PLUS Rounded 1c・Yusei Magic。いずれも OFL）を `fonts/` に入れる |

## 作り直す手順（v3）

```bash
cd video/cm-ai
bash fetch_fonts.sh
python3 extract_clips.py v3
python3 music4.py music4.wav && python3 mix4.py cm4_audio.wav
python3 render4.py . --preview 1.0,8.2,21.5      # 確認用のコマ（pv-*.png）
python3 render4.py . --out out-v3.mp4            # 本番（2〜3分）
```

v2 は `extract_clips.py v2` → `music3.py music3.wav` → `mix3.py cm3_audio.wav` → `render.py . --out out-v2.mp4`。
作業ファイル（`fonts/`・`clips*/`・`*.wav`・`*_built.html`・`pv-*.png`・`out*.mp4`）は .gitignore 済み。

## 直すときのよくある場所（cm4.html）

- 字幕の言葉: `<div class="rc" id="c1">` など（`data-t` と中身の両方を同じにする。縁取りに使う）
- 場面の長さ: `const SCENES = [...]`（秒）。変えたら `extract_clips.py` の長さと `mix4.py` の `SEG`、`music4.py` の `END` も合わせる
- 手書きの書き込み: `wobbleEllipse` / `arrow` / `.note`。位置は `rects.json`（アプリの CSS px）から計算している
- ロゴのレーダーの中心: `LC`（ロゴ画像の同心円を当てはめた値。41.56%, 42.97%）
- Chromium のパスは `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`（この環境用）
