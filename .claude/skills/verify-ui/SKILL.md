---
name: verify-ui
description: app.py / index.html / dashboard.html の画面変更後に、ローカルでアプリを起動し Playwright で PC 幅とスマホ幅（390px）の両方のスクショを撮り、Read で目視してレイアウト崩れ・横はみ出し・「テスト運用中・非公式」表記の有無を確認する手順。画面系の変更をしたとき、見た目の確認を頼まれたとき、コミット前の最終確認に使う。公開 URL はこの環境から見えないので確認はユーザーに依頼する。
argument-hint: "[app|lp|dashboard|all] [変更点の要約]"
---

# 画面変更の検証（Playwright スクショ目視）

## 前提（CLAUDE.md「検証」より）
- 画面系の変更は Playwright（`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`）で **PC 幅とスマホ幅（390px）の両方**のスクショを撮って目視確認する。片方だけで済ませない。
- アプリ起動は `PORT=5055 python app.py`（PORT 未指定だと 10000）。依存は `pip install -r requirements.txt`。debian 製 blinker と衝突して `Cannot uninstall blinker ... installed by debian` で止まる場合は `pip install -r requirements.txt --ignore-installed blinker`。DB（`reservations.db` / `reports.db`）は起動時に自動生成される揮発データで .gitignore 済み。コミットしない。
- web セッションでは `.claude/hooks/session-start.sh`（`CLAUDE_CODE_REMOTE=true` のときだけ動く）が `requirements.txt` と `requests qrcode pillow python-pptx playwright` を自動インストールする。ただし上記の blinker 衝突で hook が途中で失敗し flask が無いことがあるので、`python -c "import flask, playwright"` で確認してから始める。ブラウザは preinstall 済み（`/opt/pw-browsers`）なので `playwright install` は不要。
- この環境から github.io / onrender.com 等の公開 URL にはプロキシに阻まれて到達できない。**公開 URL での表示確認（Render / GitHub Pages に反映されたか）は必ずユーザーに依頼する。**「公開 URL で確認した」とは書かない。

## 対象とローカルでの開き方
| 対象 | 配信先 | ローカル | 「テスト運用中・非公式」表記の場所 |
|---|---|---|---|
| `app.py`（検索アプリ） | Render https://nust-room-search.onrender.com | `PORT=5055 python app.py` → `http://127.0.0.1:5055/`。GET が検索フォーム、`#search-form button` を押した POST が結果一覧（両方撮る） | ヘッダー下の TEST 帯「テスト運用中の非公式サービスです（学生開発・大学公式ではありません）」＋フッター |
| `index.html`（LP） | GitHub Pages https://nu-roomradar.github.io/nust-room-search/ | `python -m http.server 8088 --bind 127.0.0.1 --directory <リポジトリ直下>` → `http://127.0.0.1:8088/index.html` | ヒーロー直下の TEST 帯＋フッター |
| `dashboard.html`（運営用） | 同上 `/dashboard.html` | 同上 `http://127.0.0.1:8088/dashboard.html`。`./data/*.json` を fetch するので **file:// では開かない**（データ無し表示になる） | 見出し直下の TEST 帯 |

## 手順
1. 何を変えたか（対象ファイル・意図）と、撮るべき画面状態（検索結果あり／エラー表示／モーダル等）を整理する。どの状態まで撮るか迷う場合はユーザーに確認してから進める。
2. 依存確認 → サーバをバックグラウンド起動（`(PORT=5055 python app.py > <scratch>/app.log 2>&1 &)`）。起動待ちは curl だと権限確認が出るので `python -c "import urllib.request as u; print(u.urlopen('http://127.0.0.1:5055/').status)"` が 200 を返すまで待つ。
3. スクショ撮影。PC 幅 **1280x800（dsf=1）** とスマホ幅 **390x844（dsf=3。LP/ダッシュボードは 2 で十分）**、`full_page=True` の全体像を撮る。出力先はスクラッチパッド（システムプロンプトに示されるディレクトリ）で、リポジトリには置かない。雛形:
   ```python
   from playwright.sync_api import sync_playwright
   CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
   URL, OUT, PAGE = "http://127.0.0.1:5055/", "<scratch>", "app"   # LP は 8088/index.html など
   with sync_playwright() as p:
       b = p.chromium.launch(executable_path=CHROME)
       for name, vp, dsf in [("pc", {"width": 1280, "height": 800}, 1), ("sp", {"width": 390, "height": 844}, 3)]:
           pg = b.new_page(viewport=vp, device_scale_factor=dsf)
           pg.goto(URL, wait_until="load", timeout=60000)
           pg.evaluate("document.querySelectorAll('.reveal').forEach(e => e.classList.add('visible'))")  # LP のスクロール出現を強制（無いと空白になる）
           pg.wait_for_timeout(1000)
           pg.screenshot(path=f"{OUT}/{PAGE}-{name}.png", full_page=True)
           print(name, pg.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]"),
                 "テスト運用中" in pg.content(), "大学公式" in pg.content())
           # app の結果一覧: pg.click("#search-form button"); pg.wait_for_load_state("load"); 再度 screenshot
       b.close()
   ```
   - Read は縦長画像を縮小するので細部が潰れる。注目箇所は `full_page=False` でスクロール位置ごとに撮る（`pg.evaluate("window.scrollTo(0, 1200)")` → screenshot）か、`pg.locator(...).screenshot()` で要素単位に撮る。
4. **Read で開いて目視する**。チェック項目:
   - レイアウト崩れ: 要素の重なり・はみ出し・不自然な改行・ボタンやカードの整列・文字の切れ。
   - 横はみ出し: `scrollWidth > clientWidth` なら 390px で横スクロールが発生している。原因要素は `[...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1)` で特定する。**既知の問題**: HEAD 時点で app.py の教室カード（`.room-card` のグリッド）が 390px で右にはみ出す（実測 `[scrollWidth, clientWidth]` = [434, 390]、船橋校舎の3列目カードが右端で切れる）。無関係の変更でも初回から「横はみ出しあり」と出るので、自分の変更で悪化していないか（数値・原因要素が増えていないか）を見て、この既知分を直すかどうかはユーザーに確認してから決める。
   - **「テスト運用中・非公式」表記が両幅で見えているか**（ルール1）。文字列として残っているだけでなく、折りたたみ・重なり・色で読めなくなっていないかを見る。`.claude/hooks/guard-notices.py` が `テスト運用中` / `大学公式` の出現数を HEAD と比較して減る編集・commit をブロックするが、hook は表示崩れまでは見ない。
   - 仮予約（2026-10 廃止）の文言・ボタンが残っていないか、LP に船橋校舎が出ていないか（ルール3・テスト運用の範囲）。
   - 変更点が意図どおりに反映されているか。app は検索フォーム（GET）と結果一覧（POST）の両方。
5. 環境由来の見え方（バグではない）: Google Fonts（fonts.googleapis.com）・GA4（googletagmanager.com）・Chart.js（cdn.jsdelivr.net）・Instagram サムネ（cdninstagram.com）はプロキシで取得に失敗する。→ 代替フォントでの字詰め・改行ずれ、dashboard のグラフ枠が空・投稿サムネが壊れて見えるのは仕様。本来の見え方は公開 URL でユーザーに確認してもらう。
6. 結果を報告し、必要ならユーザーにもスクショを見せる（SendUserFile）。崩れがあれば直して**両幅を再撮影**する。直すか、そのまま進めるか（意図的なデザインか）はユーザーに確認してから決める。
7. 後片付け: `pkill -f "[p]ython app.py"; pkill -f "[h]ttp.server 8088"`（**ブラケット記法必須**。素の `pkill -f "python app.py"` は Bash ツール自身のコマンドライン `bash -c 'pkill -f "python app.py"'` にもパターンが一致して呼び出し元シェルごと殺され、exit code 144 で後続コマンドが実行されない。同じ Bash 呼び出しに `python app.py` を含む起動コマンドを同居させないこと。単独実行で rc=0・停止を確認済み）。代替として起動時に PID を控える方式でもよい: 手順2を `PORT=5055 python app.py > <scratch>/app.log 2>&1 & echo $! > <scratch>/app.pid` にして `kill $(cat <scratch>/app.pid)` で止める。コミットするなら `git config user.email noreply@anthropic.com && git config user.name Claude` を設定してから。push はユーザー確認後（`main` への push で Render が自動デプロイ、GitHub Pages も更新される）。

## 禁止事項・注意
- 表記を消す・隠す・小さくして読めなくする変更は通さない。「合格」と報告する前に両幅で表記を目視したことを明記する。
- スクショをリポジトリ（`assets/` 等）に入れない。ポスター用のアプリ画面スクショ（`assets/posters/handoff/app-phone-screenshot.png`、390x844・dsf=3）の差し替えは make-poster スキルの手順で行う。
- `index.html` の Instagram QR（`assets/instagram-qr.png`）を差し替えたら「QR を含む成果物の変更」なので、実物をデコードして飛び先を確認する（`cv2.QRCodeDetector().detectAndDecodeMulti()`。make-poster スキル参照）。
- 起動時に生成される `reports.db`、`__pycache__/` はコミットしない（.gitignore 済み）。`git status` で成果物以外が混ざっていないか確認する。
