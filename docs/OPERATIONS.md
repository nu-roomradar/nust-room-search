# RoomRadar 運営ハンドブック

RoomRadar を引き継ぐ人・一緒に運営する人のための1枚。**「何が・どこで・いつ・壊れたらどうする」** だけを書く。
コードの読み方や手順の詳細は README と `.claude/skills/` にあり、守るべきルールは `CLAUDE.md` にある。
`[要記入]` はこの文書を書いた時点で分からなかった箇所。引き継ぎ時に埋めること。

最終更新: 2026-09-23

初めて参加する人は先に [`ONBOARDING.md`](ONBOARDING.md) を読む。

---

## 1. サービスの全体像

| 部品 | 場所 | 更新のされ方 |
|---|---|---|
| 検索アプリ（`app.py`） | Render https://nust-room-search.onrender.com | `main` に push すると自動デプロイ（数分） |
| LP（`index.html`）・運営用ダッシュボード（`dashboard.html`） | GitHub Pages https://nu-roomradar.github.io/nust-room-search/ | `main` に push すると自動反映 |
| 時間割 DB（`schedule_final.db`） | リポジトリ内 | 2025・2026年度を同居（2026年度: 前期 6,437 行・後期 6,260 行・教室 180）。**`python scripts/build_schedule_db.py` で原本から再現できる**（6.） |
| 仮予約・使用中報告（`reservations.db` / `reports.db`） | Render の実行環境 | 実行時に自動生成。**再起動・再デプロイで消える**。環境変数 `DATA_DIR` を永続ディスクに向ければ残る（6. 参照） |
| Instagram @roomradar_nust | Meta | `instagram-post.yml` を手動起動して投稿 |
| ソースコード | GitHub Organization `nu-roomradar` / `nust-room-search` | 現状は `main` へ直接 push（ひとり運用のため） |

運営者は iPad から **Claude Code on the web**（claude.ai/code）でこのリポジトリを開いて作業する。ローカルの開発環境は無い。

## 2. アカウントと権限

引き継ぎでは **この表の全行に新しい担当者を追加** する。ひとつでも欠けると、その部分が誰にも触れなくなる。

| サービス | 何に使うか | 権限を持つ人 | 追加の仕方 |
|---|---|---|---|
| GitHub Organization `nu-roomradar` | コード・Actions・Secrets・Pages | `Kota0004`、`csko24143-droid`（いずれも現運営者） | Organization の Owner が Settings → People から招待 |
| Render | アプリのホスティング・プラン変更・ログ | [要記入] | Render ダッシュボード → Team → Invite |
| Meta for Developers（Instagram API） | 投稿用アクセストークンの発行 | [要記入] | アプリの「役割」に管理者として追加 |
| Google Analytics（GA4） | LP の計測（集計の自動取得は 2026-08 に終了） | [要記入] | GA4 の管理 → プロパティのアクセス管理 |
| Claude（Pro） | Claude Code on the web での開発・運用作業 | 現運営者の個人契約 | 個人ごとに契約。組織契約（Team）に上げるかは人数次第 |
| GitHub Secrets（`IG_ACCESS_TOKEN` / `IG_ACCOUNT_ID`） | Instagram 投稿ワークフロー | GitHub の Owner | リポジトリ Settings → Secrets and variables → Actions |

## 3. 定期作業カレンダー

| いつ | 何を | どうやって |
|---|---|---|
| **毎週月曜 09:00** | 運用ヘルスチェックの結果を見る | 自動で動く。異常があれば「【運用ヘルスチェック】異常を検知しました」という Issue が開く。復旧すると自動で閉じる。**Issue が開いたら中を読んで対応する**だけでよい |
| **毎月1日** | Instagram トークンの自動延長 | 自動。`ig-token-refresh.yml` が60日先まで延ばして Secret を書き換える。**人がやることは無い。失敗したときだけ対応**（下の「Instagram トークンの自動更新」参照） |
| **年1回程度** | `IG_REFRESH_PAT` の更新 | PAT に有効期限を付けた場合のみ。切れると上の自動延長が失敗し、ヘルスチェックが Issue で知らせる |
| **後期開始前（9/24 に Issue が自動で立つ）** | Render のプランを Starter に戻す | Render ダッシュボード → `nust-room-search` → Settings → Instance Type。**再起動で仮予約データが消える**ので利用の少ない時間帯に |
| **夏休み前（7月末）** | Render のプランを Free に落とす（費用節約） | 同上。戻し忘れ防止に `render-plan-reminder.yml` がある |
| **4/1 と 9/21** | 検索の学期が自動で前期／後期に切り替わる | 何もしなくてよい。ただし DB にその学期の時間割が入っている必要がある |
| **年1回（3〜4月）** | 翌年度の時間割を DB に入れる | 教務ページから時間割表をダウンロード → `data/source/` に置く → `python scripts/build_schedule_db.py --report` で差分を確認 → 問題なければ `--replace`。手順は 6. |
| **60日にいちど以上** | リポジトリに何かコミットする | public リポジトリは60日間コミットが無いと GitHub が定期実行（ヘルスチェック含む）を止める。止まると自分では検知できない |

## 4. 壊れたとき

| 症状 | まず見る場所 | 対応 |
|---|---|---|
| アプリが開かない・遅い | Render ダッシュボードの Events / Logs | Free プランならスリープ復帰に数十秒かかる（正常）。落ちていれば Manual Deploy → Deploy latest commit |
| 「テスト運用中・非公式」表記が本番から消えた | ヘルスチェックの Issue | 学生課・教務課と協議中のため即対応。`CLAUDE.md` ルール1。Claude Code なら hook が編集を止めるので、消えるとすれば手作業か外部要因 |
| Actions が失敗している | GitHub → Actions → 該当 run のログ | Instagram 系なら 9 割トークン失効。CI の失敗はテストが落ちている＝直すまで `main` に入れない |
| Instagram に投稿できない | Actions のログの `[ERROR]` 行 | `code=190` / `OAuthException` → トークン再発行。それ以外は `.claude/skills/instagram-post/SKILL.md` |
| 仮予約・報告が全部消えた | — | Render の再起動・デプロイで消える仕様。復旧不要。利用者への説明は「時限終了で自動リセット」の範囲内 |
| 検索結果がおかしい（授業中のはずの教室が空きで出る） | `schedule_final.db` の該当学期のデータ | DB が古い、または学期切替の境界（4/1・9/21）。時間割の更新が必要 |
| 何が壊れているか分からない | Claude Code on the web でリポジトリを開き、症状を説明する | `CLAUDE.md` と skills を読んだ状態で調査してくれる |

## 4.5 Instagram トークンの自動更新

`IG_ACCESS_TOKEN` は発行から **60日で失効**する。2026-08-13 に切れたときは気づくまで3週間かかり、その間まったく投稿できなかった。手で再発行し続けるのをやめるため、`.github/workflows/ig-token-refresh.yml` が**毎月1日に60日先まで延長**して Secret を書き換える。

**仕組み**: `refresh_access_token` で新トークンを取得 → 実際に使えるか確認 → 確認できてから Secret を更新。検証に失敗したら Secret は触らない（古いトークンが残るので投稿は続けられる）。

**必要な準備（一度だけ）**: GitHub Actions は `GITHUB_TOKEN` では Secret を書き換えられないので、専用の PAT が要る。

1. GitHub の自分のアイコン → **Settings** → 一番下の **Developer settings**
2. **Personal access tokens** → **Fine-grained tokens** → **Generate new token**
3. 設定:
   - **Resource owner**: `nu-roomradar`（個人アカウントではなく Organization。※ 組織の承認が要る場合がある）
   - **Repository access**: Only select repositories → `nust-room-search`
   - **Repository permissions** → **Secrets** を **Read and write** に
   - **Expiration**: 長め、または無期限
4. 生成されたトークンをコピー
5. https://github.com/nu-roomradar/nust-room-search/settings/secrets/actions → **New repository secret**
   - Name: `IG_REFRESH_PAT`
   - Secret: コピーしたトークン
6. Actions タブ → 「Instagramトークンの自動更新」→ **Run workflow**（`dry_run` を **true**）で疎通確認

**失敗したときは**: Actions が赤くなり、週次の運用ヘルスチェックが Issue で知らせる。ログを見て切り分ける。

| ログ | 意味 | 対応 |
|---|---|---|
| `既に失効しています` (code=190) | 延長できる期限を過ぎた | **自動では直せない。** Meta for Developers で手動再発行（`.claude/skills/instagram-post/SKILL.md`） |
| `Secret の公開鍵を取れません` | PAT の権限不足・期限切れ | PAT を作り直して `IG_REFRESH_PAT` を差し替える |
| `新しいトークンが使えません` | Meta 側でアプリ設定が変わった等 | Secret は無事。Meta のアプリ設定を確認 |

トークンはログに出ない（長さと末尾4文字だけ）。

## 5. 日常の作業のしかた

1. claude.ai/code でこのリポジトリを開き、やりたいことを日本語で伝える。
2. Instagram 投稿・ポスター・画面確認は `/instagram-post` `/make-poster` `/verify-ui` の手順書に沿って進む。**投稿と `git push` は必ず確認が入る**。
3. `main` に push すると Render と GitHub Pages が自動更新される。数分後に本番を自分のスマホで確認する（Claude の環境からは本番が見えない）。
   **アプリ（`app.py`・`templates/`・`static/`・`schedule_final.db`）の push は授業時間外（平日 20:30 以降・日曜など）に行う。** push すると Render が再デプロイし、その時点の仮予約・報告が消えるため（永続ディスクは付けない方針。2026-09 決定）。LP・ダッシュボードだけの変更はいつでもよい。
4. CI（`ci.yml`）が push ごとにテストを回す。赤くなったら直す。

## 6. 未整備・既知の課題（引き継ぎ時に必ず共有）

- ~~時間割 DB の作り方が失われている~~ → **2026-09-12 に解決。** 原本（教務ページ配布の時間割表 `.xls`）を回収し、`scripts/build_schedule_db.py` で現行 DB を**全7列・13,614行・教室マスタ・スキーマまで完全再現**できることを確認した。

  **翌年度の入れ替え手順**
  1. 教務ページ https://www.kyoumu.cst.nihon-u.ac.jp/timetable/ から時間割表をダウンロード（**理工学部・短期大学部・博士前期・博士後期の全学科**。ファイル名は変えない）
  2. `data/source/<年度>/` に置く（例 `data/source/2027/`。GitHub の Web 画面からアップロードでよい。翌年度用のフォルダは用意してある）
  3. `python scripts/build_schedule_db.py --report` … 現行 DB との差分が出る。行数・学科別一致率・占有スロット・教室マスタの差分を見る。新年度なら当然大きく差が出るので、**件数の桁と学科の顔ぶれ**が妥当かを見る
  4. `python -m unittest discover -s tests` でテストが通ることを確認
  5. 問題なければ `python scripts/build_schedule_db.py --replace`（`.bak` が自動で作られる）と `python scripts/export_classes.py`（授業の生データ一覧 `data/classes_<年度>.csv` を更新）、`python scripts/export_occupancy.py`（ダッシュボードの混み具合 `data/occupancy.json` を更新）
  6. コミットして push → Render が自動デプロイ。本番で数件検索して妥当性を確認

  既定では本番 DB を上書きしない（`schedule_final.new.db` に出る）。`--replace` を明示したときだけ差し替わる。
  本番 DB は全区分のビルド結果と完全に一致する（テストが検査）。原本を変えずに `--report` を走らせて差分が 0 なら、スクリプトは壊れていない。
  2026-09 に、教室名の全角・半角の統一（「階段教室（大）」＝「階段教室(大)」）と、合同教室の略記の分割（「1456/7/8」→ 1456・1457・1458）を入れた。どちらも「空き」と出るコマが減る（安全側の）変更。

- **短期大学部は船橋校舎を共用している。** 2026-09 に取り込むまで、短大の授業が入っている教室を「空き」と表示していた（既存181教室のうち20室・109スロット）。schedules には短大を入れるが、教室マスタ（検索結果に出る教室）は理工学部・大学院からだけ作る。短大専用教室は理工の学生が行っても使えるとは限らないため。
- **教室名が校舎をまたいで衝突している。** 「134」「143」「144」は船橋と駿河台の両方に存在し、「まち製図室1～5」はタワースコラと駿河台にあるが、DB は教室名だけで束ねている（`classrooms.name` が一意）。駿河台側の授業があると船橋の同名教室が「使用中」と出る。**空きを埋まって見せる方向の誤りなので実害は小さい**が、原本を回収したら (校舎, 教室) で管理するよう直す。それまでは `tests/test_schedule_db.py` の `KNOWN_NAME_COLLISIONS` に既知として登録してある。
- **仮予約・報告が再デプロイで消える。** Render の無料プランはディスクが揮発する。残したいときは Render の有料プラン（Starter 以上）で Disk を付け（例: マウント先 `/var/data`、1GB で足りる）、Environment に `DATA_DIR=/var/data` を追加する。コード側は対応済み。Disk を付けるとそのサービスはゼロダウンタイムデプロイができなくなる点に注意。
- ブランチ運用・PR レビューが無い（ひとり運用のため）。2人以上になったら PR 運用に切り替える。
- テストは最小限（運用スクリプト・hook・API・検索ページ）。UI の見た目は `/verify-ui` で目視。
- Instagram・GA4 の集計は 2026-08 に終了。ダッシュボードは最終取得時点のデータを表示したまま（凍結）。
- LP のスマホ幅ナビは横スワイプで動くが、スワイプできることを示す手がかりが無い。
- 「テスト運用中・非公式」の表記は学生課・教務課との協議次第で変わる可能性がある。変えるときは `.claude/hooks/guard-notices.py` の `GUARDED` も更新する。

## 7. 引き継ぎチェックリスト

- [ ] 2. の全サービスに新担当者を追加し、`[要記入]` を埋めた
- [ ] GitHub Secrets の中身（Instagram トークン・アカウント ID）を新担当者が再発行できる状態にした
- [ ] Render・Meta・GA4 のオーナー（請求先）を確認した
- [ ] 新担当者が Claude Code on the web でリポジトリを開けることを確認した
- [ ] 3. のカレンダーを新担当者の予定に入れた（特に 9/24 の Render、60日ごとのトークン、年1回の時間割）
- [ ] 翌年度の時間割入れ替え手順（6.）を新担当者と一度通しでやってみた
- [ ] 6. の未整備事項を口頭でも共有した
