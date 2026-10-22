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
| 正式版 | `assets/posters/roomradar-poster-pro.png`、印刷用 `roomradar-poster.{pdf,pptx}`（A4・約392dpi）と `roomradar-poster-A3.pdf`（A3・約300dpi） |
| どこ行く？版（Claude Design で運営が作る） | `assets/posters/claude-design/RoomRadar_poster_{A4,A3}.pdf` と同じ画像の PNG（どちらも300dpi。2026-10-21 に学生課長の4点を入れた版に差し替え。古い塗り足し版は消した） |
| 静か版（**掲示しない**。2026-10-20 の学生課長の指示と合わないため。記録として残す） | `assets/posters/roomradar-poster-shizuka.{png,pdf,pptx}` |
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
   - `--print-files` を付けると、PNG と同じ場所に **A4縦・約392dpi** の PDF/PPTX（1080x1528 を dsf=3 で描画 → 3240x4584）と、**A3・約300dpi** の PDF（dsf=3.25 で描き直し → 3510x4966）も出力する。名前は正式版なら `roomradar-poster.{pdf,pptx}`・`roomradar-poster-A3.pdf`（PNG 名の `-pro` を外す）。PDF の中の画像は JPEG 画質95。
   - コンビニのマルチコピー機（セブン-イレブンのネットプリント、ローソン・ファミリーマートのネットワークプリント）で A4・A3 とも印刷できる。300dpi あれば十分で、ファイルも 1 つ 3MB 以下。コピー機はフチまで印刷できないので、上下の濃紺の帯のまわりに白い余白が出る（文字は端から離してあるので切れない）。
3. **生成した PNG を Read で目視する**。必須要素がすべて入っているか確認する: **ロゴ・LP QR・Instagram QR（ブランドQR）・「日本大学自主創造プロジェクト」・`#日大生プロジェクト`・下の帯の TEST 表記（2026-10-22 から学生課の提案の文言「本サービスは、学生が「自主創造プロジェクト」の一環として開発・運営している試験運用中のサービスです。大学が公式に提供するサービスではありません。」）**。一つでも欠けていたら成果物にしない。
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
- 仮予約は 2026-10 に廃止した。ポスターに「予約」「確保」と書かない。船橋校舎はテスト運用の対象外なので載せない（対象は駿河台キャンパスの65教室）。
- 静か版はネタ文言の仮版。正式版の代わりに掲示するかの判断はユーザーが行う。
- 正式版は 2026-10-21 から再び `scripts/make_poster.py` で作っている（Claude Design 版とほぼ同じ見た目で、見出し「「開けたら、空いてる」／を当たり前に。」（2行目の頭に「を」。2026-10-21 運営が採用）と学生課長の4点の枠「空き教室は、みんなで使う場所です。」を入れた。見出しは横幅いっぱいに置き、収まる大きさに自動で合わせる。2026-10-21 の運営の指示で、見出しとスマホを主役に大きくし、4点の枠は左の列に小さく入れた）。この環境では Google Fonts に届かないので、`video/cm-ai/fonts/`（`fetch_fonts.sh`）に Noto Sans CJK JP があれば自動で差し込む。どこ行く？版（`assets/posters/claude-design/`）は Claude Design で作っているので、直すときは運営者に Claude Design 用の指示文を渡す。ただし下の帯の表示文言だけなら `scripts/patch_poster_notice.py` で描き直せる（2026-10-22 に使用。強調の色はそのポスターのアクセント色にそろえる）。
- 周知物の言葉は `docs/OPERATIONS.md` 2.5 の方針（みんなで使う場所／自習専用ではない／静かに学習したいときは図書館・1号館CSTギャラリー／「静か」「集中」「自習室」を売りにしない／他の場所を下げない）に合わせる。
- `LP_URL` や Instagram QR 画像を変えたら、それは「QR を含む成果物の変更」なので手順 4 を必ず実施する。
- この環境から github.io / onrender.com 等の公開 URL には到達できない。QR の飛び先が実際に表示されるかの確認はユーザーに依頼する。
