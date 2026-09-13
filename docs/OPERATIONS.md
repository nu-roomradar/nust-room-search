# RoomRadar 運営ハンドブック

RoomRadar を引き継ぐ人・一緒に運営する人のための1枚。**「何が・どこで・いつ・壊れたらどうする」** だけを書く。
コードの読み方や手順の詳細は README と `.claude/skills/` にあり、守るべきルールは `CLAUDE.md` にある。
`[要記入]` はこの文書を書いた時点で分からなかった箇所。引き継ぎ時に埋めること。

最終更新: 2026-09-11

---

## 1. サービスの全体像

| 部品 | 場所 | 更新のされ方 |
|---|---|---|
| 検索アプリ（`app.py`） | Render https://nust-room-search.onrender.com | `main` に push すると自動デプロイ（数分） |
| LP（`index.html`）・運営用ダッシュボード（`dashboard.html`） | GitHub Pages https://nu-roomradar.github.io/nust-room-search/ | `main` に push すると自動反映 |
| 時間割 DB（`schedule_final.db`） | リポジトリ内 | 2026年度（令和8年度）。前期 6,897 行・後期 6,717 行・教室 181。**`python scripts/build_schedule_db.py` で原本から再現できる**（6.） |
| 仮予約・使用中報告（`reservations.db` / `reports.db`） | Render の実行環境 | 実行時に自動生成。**再起動で消える**（仕様） |
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
| **約60日ごと** | Instagram トークンの再発行 | 失効するとヘルスチェックが Issue で知らせる。Meta for Developers → アプリ → Instagram → API設定 で長期トークンを再発行し、GitHub Secrets の `IG_ACCESS_TOKEN` を差し替える |
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

## 5. 日常の作業のしかた

1. claude.ai/code でこのリポジトリを開き、やりたいことを日本語で伝える。
2. Instagram 投稿・ポスター・画面確認は `/instagram-post` `/make-poster` `/verify-ui` の手順書に沿って進む。**投稿と `git push` は必ず確認が入る**。
3. `main` に push すると Render と GitHub Pages が自動更新される。数分後に本番を自分のスマホで確認する（Claude の環境からは本番が見えない）。
4. CI（`ci.yml`）が push ごとにテストを回す。赤くなったら直す。

## 6. 未整備・既知の課題（引き継ぎ時に必ず共有）

- ~~時間割 DB の作り方が失われている~~ → **2026-09-12 に解決。** 原本（教務ページ配布の時間割表 `.xls`）を回収し、`scripts/build_schedule_db.py` で現行 DB を**全7列・13,614行・教室マスタ・スキーマまで完全再現**できることを確認した。

  **翌年度の入れ替え手順**
  1. 教務ページ https://www.kyoumu.cst.nihon-u.ac.jp/timetable/ から時間割表をダウンロード（**理工学部・短期大学部・博士前期・博士後期の全学科**。ファイル名は変えない）
  2. `data/source/<年度>/` に置く（例 `data/source/2027/`。GitHub の Web 画面からアップロードでよい。翌年度用のフォルダは用意してある）
  3. `python scripts/build_schedule_db.py --report` … 現行 DB との差分が出る。行数・学科別一致率・占有スロット・教室マスタの差分を見る。新年度なら当然大きく差が出るので、**件数の桁と学科の顔ぶれ**が妥当かを見る
  4. `python -m unittest discover -s tests` でテストが通ることを確認
  5. 問題なければ `python scripts/build_schedule_db.py --replace`（`.bak` が自動で作られる）と `python scripts/export_classes.py`（授業の生データ一覧 `data/classes_<年度>.csv` を更新）
  6. コミットして push → Render が自動デプロイ。本番で数件検索して妥当性を確認

  既定では本番 DB を上書きしない（`schedule_final.new.db` に出る）。`--replace` を明示したときだけ差し替わる。
  `--divisions 1,3,4` で短大を外して走らせると現行 DB を完全再現するので、スクリプトが壊れていないかの確認に使える。

- **短期大学部は船橋校舎を共用している。** 2026-09 に取り込むまで、短大の授業が入っている教室を「空き」と表示していた（既存181教室のうち20室・109スロット）。schedules には短大を入れるが、教室マスタ（検索結果に出る教室）は理工学部・大学院からだけ作る。短大専用教室は理工の学生が行っても使えるとは限らないため。
- **教室名が校舎をまたいで衝突している。** 「134」「143」「144」は船橋と駿河台の両方に存在し、「まち製図室１～５」はタワースコラと駿河台にあるが、DB は教室名だけで束ねている（`classrooms.name` が一意）。駿河台側の授業があると船橋の同名教室が「使用中」と出る。**空きを埋まって見せる方向の誤りなので実害は小さい**が、原本を回収したら (校舎, 教室) で管理するよう直す。それまでは `tests/test_schedule_db.py` の `KNOWN_NAME_COLLISIONS` に既知として登録してある。
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
