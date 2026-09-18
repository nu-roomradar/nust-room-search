---
name: make-poster
description: RoomRadar の学内掲示ポスターを生成・更新する手順。正式版／静か版のPNG生成、--print-files でのA4縦 PDF/PPTX 出力、必須要素（ロゴ・LP QR・Instagram QR・自主創造プロジェクト表記・#日大生プロジェクト・TEST表記）の確認、アプリ画面スクショの差し替え、QRの実物デコード確認まで。ポスターを作る・作り直す・スクショやQRを差し替える・掲示用ファイルを出力するときに使う。
argument-hint: "[official|shizuka] [--print-files] [スクショ更新あり]"
---

# 学内掲示ポスターの生成・更新

生成は `scripts/make_poster.py` 一本（詳細はファイル先頭の docstring と `main()` の引数）。生成自体は副作用なし。
Claude Code on the web のセッション内（Bash）で完結する。ポスター用の GitHub Actions は無い。

## 成果物と素材（すべてリポジトリ内）

| 種別 | パス |
|---|---|
| 正式版 | `assets/posters/roomradar-poster-pro.png`、印刷用 `roomradar-poster.{pdf,pptx}` |
| 静か版（ネタ文言の仮版。掲示運用のためコミット済み） | `assets/posters/roomradar-poster-shizuka.{png,pdf,pptx}` |
| ロゴ | `rr_logo.png`（リポジトリ直下） |
| アプリ画面スクショ | `assets/posters/handoff/app-phone-screenshot.png` |
| Instagram QR（ブランドQR・静的画像を埋め込み） | `assets/posters/handoff/qr-instagram-branded.png` |
| LP QR | 静的画像は無い。`make_poster.py` の `LP_URL`（`https://nu-roomradar.github.io/nust-room-search/`）から実行時に動的生成 |

成果物は必ず `assets/posters/` に置く。

## 手順

1. **依存を確認する**。必要パッケージは `qrcode` / `pillow` / `playwright` / `python-pptx`（`--print-files` 時）。web セッションでは `.claude/hooks/session-start.sh` が自動インストール済み。QR 確認用の `cv2` は別途 `pip install opencv-python-headless`。ブラウザは preinstall 済みの `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`（スクリプトの `CHROME` 定数）を使うので `playwright install` は不要。
   - 確認コマンド: `python -c "import qrcode, PIL, playwright, pptx"`（エラーが出なければ OK）。
   - 失敗したら（SessionStart hook は `CLAUDE_CODE_REMOTE=true` のときだけ走るため、走っていないことがある）: `pip install qrcode pillow playwright python-pptx` を実行してから再確認する。
2. **どのバリアントを、どこまで出力するかをユーザーに確認してから**生成する。
   - 正式版: `python scripts/make_poster.py`（`--out` 省略時 → `assets/posters/roomradar-poster-pro.png`）
   - 静か版: `python scripts/make_poster.py --variant shizuka --out assets/posters/roomradar-poster-shizuka.png`
     （`--out` を省略すると `/tmp/roomradar-poster-shizuka.png` に出るので、成果物にするなら必ず指定）
   - `--print-files` を付けると PNG と同じ場所・同名で **A4縦・約392dpi** の PDF/PPTX も出力（1080x1528 を dsf=3 で描画 → 3240x4584）。
   - 注意: 正式版の印刷用ファイルはリポジトリ上 `roomradar-poster.{pdf,pptx}` だが、`--print-files` は `roomradar-poster-pro.{pdf,pptx}` を書き出す。旧ファイルが残って二重にならないよう、どちらの名前に揃えるかをユーザーに確認してから置き換える。
3. **生成した PNG を Read で目視する**。必須要素がすべて入っているか確認する: **ロゴ・LP QR・Instagram QR（ブランドQR）・「日本大学自主創造プロジェクト」・`#日大生プロジェクト`・TEST表記（「テスト運用中の非公式サービス」）**。一つでも欠けていたら成果物にしない。
   - HTML は Google Fonts を読み込む。プロキシで取得できず代替フォントで崩れることがあるので、文字の詰まり・改行位置も見る。
   - ユーザー（iPad）にも PNG を見せて確認を取る。手段: SendUserFile（`display=render`）で `assets/posters/roomradar-poster-pro.png`（静か版なら `roomradar-poster-shizuka.png`）を送る。送れない環境なら作業ブランチに push し、GitHub 上の画像プレビューで確認してもらう。
4. **QR を実物からデコードして飛び先を確認する**（QR を含む成果物を変更したら必ず。省略不可）。
   - PNG: `cv2.QRCodeDetector().detectAndDecodeMulti(cv2.imread(path))` で全 QR を読む。大きすぎて検出できなければ幅 1600px 程度に縮小して再試行。
   - PDF: `pdfimages -png <pdf> <prefix>` で埋め込み画像を取り出してから同様にデコード（`pdfimages` が無ければ `pip install pymupdf` で抽出）。
   - PPTX: zip 展開（`unzip -o <pptx> 'ppt/media/*' -d <dir>`）で埋め込み画像を取り出してからデコード。
   - 期待値: LP QR = `LP_URL` と完全一致。Instagram QR = `assets/posters/handoff/qr-instagram-branded.png` を単体でデコードした値と一致。どちらか一つでも違えば成果物にせず、ユーザーに報告する。
5. **アプリ画面スクショを更新する場合のみ**（画面変更があったときなど。更新するかはユーザーに確認）:
   1. `pip install -r requirements.txt`（debian 製 blinker と衝突する場合は `--ignore-installed blinker`）→ `PORT=5055 python app.py` でローカル起動（DB は自動生成）。
   2. Playwright（上記 chrome）で **390x844, device_scale_factor=3** で撮影し、`assets/posters/handoff/app-phone-screenshot.png` を差し替える。
   3. スクショは正式版・静か版の両方に埋め込まれるので、両バリアントを再生成し、手順 3・4 をやり直す。
6. **コミット**: `git config user.email noreply@anthropic.com && git config user.name Claude` を設定してからコミットする。push・PR 作成はユーザーに確認してから。

## 禁止事項・注意

- ポスターから TEST 表記（テスト運用中・非公式）と `#日大生プロジェクト` を消さない・減らさない。`.claude/hooks/guard-notices.py` が `scripts/make_poster.py` の `#日大生プロジェクト` 出現数を HEAD と比較してブロックする。文言変更が必要なときはユーザーに確認し、hook の説明に従う。
- 文言を足すときも「予約」と言い切らない。仮予約に触れるなら、非公式で教室の使用権を保証しない旨を併記する。
- 静か版はネタ文言の仮版。正式版の代わりに掲示するかの判断はユーザーが行う。
- `LP_URL` や Instagram QR 画像を変えたら、それは「QR を含む成果物の変更」なので手順 4 を必ず実施する。
- この環境から github.io / onrender.com 等の公開 URL には到達できない。QR の飛び先が実際に表示されるかの確認はユーザーに依頼する。
