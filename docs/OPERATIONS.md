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
| 時間割 DB（`schedule_final.db`） | リポジトリ内 | **手作業**。2026-06-10 にアップロードされたもの。前期 6,897 行・後期 6,717 行・教室 181 |
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
| **年1回（3月）** | 翌年度の時間割を DB に入れる | **手順が未整備**（下記 6.）。最重要の未整備事項 |
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

- **時間割の更新手順が無い。** `data/source/*.xlsx` が原本だが、xlsx から `schedule_final.db` を作るスクリプトは存在しない（DB は 2026-06-10 にアップロードされたもの）。翌年度（2027-04）までに変換スクリプトを整備するか、手順を文書化すること。
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
- [ ] 6. の未整備事項を口頭でも共有した
