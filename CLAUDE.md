# RoomRadar — プロジェクト指示

日本大学理工学部の空き教室検索サービス。学生開発・**テスト運用中の非公式サービス**（自主創造プロジェクトの一環）。ユーザーとのやり取りは日本語で行う。運営者は iPad から Claude Code on the web だけを使う（ローカル端末・gh CLI は無い。GitHub の操作は GitHub MCP ツールで行う）。

## 構成と配信先

- リポジトリは Organization **`nu-roomradar`** 所有（2026-08、個人アカウント名がLPのURLに露出していたため移管）。セッションの `origin` が旧個人アカウントを指していてもリダイレクトされる。
- `app.py` — Flask検索アプリ本体。**Render**（https://nust-room-search.onrender.com ）でホスティング。mainへのpushで自動デプロイ。Renderの参照元は `nu-roomradar/nust-room-search` の `main`。
- `index.html` / `dashboard.html` — LPと運営用アナリティクス。**GitHub Pages**（https://nu-roomradar.github.io/nust-room-search/ ）で配信。
- `schedule_final.db` — 時間割DB（検索の元データ、前期・後期とも収録）。原本は `data/source/<年度>/` の `<区分>_<学部>_<学科>_..._時間割表N面_*.xls`（教務ページ配布の時間割表。区分 1=理工学部 2=短期大学部 3=博士前期 4=博士後期）。年度フォルダは原本が入っている最新のものが自動で選ばれる（`--year` で明示も可）。`python scripts/build_schedule_db.py --report` で原本から作り直せる。既定では本番DBを上書きせず `schedule_final.new.db` に出す。`--divisions 1,3,4`（短大を外す）で現行DBを全7列完全再現することを確認済み。差し替え時は `tests/test_schedule_db.py` と `tests/test_build_schedule_db.py` が検査する。手順は `docs/OPERATIONS.md`。
- **短期大学部は船橋校舎を理工学部と共用している。** 短大の授業が入った教室を「空き」と出さないよう schedules には取り込むが、**教室マスタ（検索結果に出る教室）は理工学部・大学院からだけ作る**（短大専用教室は行っても使えるとは限らないため安全側に倒す）。この方針を変えると空き判定の意味が変わるので、変更前にユーザーに確認する。
- `data/source/archive/` は令和7年度の**古い別形式のエクスポートと集計**。原本ではないので変換には使わない。`data/source/README.md` 参照。
- `data/classes_2026.csv` — 授業の生データ一覧（`python scripts/export_classes.py` で生成）。DB が捨てている **時間割CD・単位・対象学年・教員名** も入っている。アプリは読まない（検索が使うのは `schedule_final.db` だけ）。
- `reservations.db` / `reports.db` — 実行時に自動生成される揮発データ。**コミットしない**（.gitignore済み）。
- `data/*.json` — Instagram/GA4 の集計。**2026-08 で収集を終了**し、ダッシュボード表示用に凍結（更新しない。収集用のワークフロー・スクリプトは撤去済み）。

## 守るべきルール

1. **「テスト運用中・非公式」表記を消さない**: app.py・index.html・dashboard.html・ポスターに常設。学生課/教務課と協議中のため誤認防止が必須。
2. **Instagram投稿キャプションには `#日大生プロジェクト` が必須**（自主創造プロジェクトの規定）。`scripts/post_to_instagram.py` が自動付与するので、この機構を壊さない。ストーリーズにはキャプション自体が無いので対象外。
3. **公開文言では「予約」と言い切らない**: アプリの仮予約は非公式であり教室の使用権を保証しない旨を必ず併記。
4. コミットは `git config user.email noreply@anthropic.com && git config user.name Claude` で行う（Verified表示のため）。

ルール1・2は `.claude/hooks/guard-notices.py` が機械的に検査する（編集前・`git commit`/`push` 前・応答終了前）。CLAUDE.md の指示だけでは強制力がないため。判定は「コミット済みより出現数を減らさない」。表記を意図的に減らす・変えるときは、ユーザーの指示のもとで空ファイル `.claude/guard-relax` を置き（作業後に削除）、フレーズ自体を変えるなら同ファイルの `GUARDED` も更新する。
`.claude/settings.json` の permissions で、秘匿ファイルの読み取りは拒否、`git push` と Instagram 投稿は毎回確認になる。

## 手順書（skills）

手順の詳細は `.claude/skills/` にあり、CLAUDE.md には書かない。該当する作業では必ず読む。

- `/instagram-post` — フィード／ストーリー投稿、告知ストーリーの目視確認フロー、キャプション規則、弔事ストーリー、トークン失効時の対処
- `/make-poster` — ポスター生成（正式版／静か版、PDF/PPTX）、必須要素、QR の実物デコード確認
- `/verify-ui` — 画面変更後の Playwright スクショ（PC幅・390px）と表記の目視確認

## 環境の癖

- この環境から github.io・onrender.com 等の公開URLへの到達はプロキシに阻まれる。公開URLの表示確認はユーザーに依頼する。raw.githubusercontent.com は到達可。
- `pip install -r requirements.txt` が debian 製 blinker と衝突する場合は `--ignore-installed blinker` を付ける。
- Playwright のブラウザは preinstall 済み（`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`）。`playwright install` は不要。
- Instagram の長期アクセストークンは約60日で失効する。`ig-token-refresh.yml` が毎月1日に自動延長するので通常は人の作業は不要。投稿が急に失敗し出したらまず自動更新が止まっていないかを見る（`docs/OPERATIONS.md` 4.5）。

## 運用の自動化

- `.github/workflows/ops-healthcheck.yml` が毎週月曜に本番URLの応答と必須表記・Actions の失敗・トークンの有効性を検査し、異常なら Issue を開く（復旧で自動クローズ）。`ci.yml` が push/PR で構文チェックと `tests/` を回す。
- public リポジトリは60日間コミットが無いと GitHub が schedule 実行（ヘルスチェック含む）を止める。止まると自分では検知できない。
