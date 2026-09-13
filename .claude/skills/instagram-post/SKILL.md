---
name: instagram-post
description: RoomRadar公式Instagram（@roomradar_nust）へのフィード／ストーリー投稿を GitHub Actions（instagram-post.yml）経由で行う手順。投稿の実行、告知ストーリーの生成と目視確認、キャプション作成（#日大生プロジェクト自動付与）、story_headline の見出し決め、弔事ストーリー、IG_ACCESS_TOKEN 失効の相談で使う。ワークフロー起動前に必ずユーザー確認を取る。
disable-model-invocation: true
argument-hint: "[feed|story|condolence|token] 投稿内容や相談の要点"
---

# Instagram 投稿（GitHub Actions 経由）

## 前提
- リポジトリは Organization `nu-roomradar` の `nust-room-search`（既定ブランチ `main`）。GitHub 操作は GitHub MCP ツールで行う（ローカル端末・gh CLI は無い）。セッションの `origin` が旧個人アカウントを指していても、URL・MCP の owner は `nu-roomradar` を使う。
- 投稿はすべて `.github/workflows/instagram-post.yml` を workflow_dispatch で実行する。実体は `scripts/post_to_instagram.py`（Graph API v21.0。`graph.instagram.com` → `graph.facebook.com` の順にホスト判定）。詳細は各スクリプトの docstring を参照。
- secrets は `IG_ACCESS_TOKEN` / `IG_ACCOUNT_ID` の2つだけ。
- **投稿は外部公開される操作。ワークフローを起動する前に、入力値一式をユーザーに提示して承認を得る。承認前に起動しない。**
- 公開済み投稿のキャプションは API では編集・削除不可（Instagram アプリからの手動のみ）。起動前の確認が最後の砦。

## ワークフロー入力（instagram-post.yml）
| 入力 | 内容 |
|---|---|
| `post_type` | `feed` / `story`（既定 feed） |
| `image_url` | 投稿する画像の公開 URL（https://…）。必須 |
| `caption` | キャプション。フィードのみ。ストーリーでは無視される |
| `also_story` | フィード投稿時に告知ストーリー画像を生成する（既定 true。`post_type=feed` のときだけ有効） |
| `post_story` | 生成した告知ストーリーを同じ実行でそのまま投稿する（既定 false。true にすると**未確認の画像が公開される**。確認前は必ず false） |
| `story_headline` | 告知ストーリーの見出し。**毎回明示する**（未入力だとキャプションの1行目がそのまま入り、長すぎて不自然な位置で改行される）。全角14文字程度が収まりの目安 |

真偽値は文字列 `"true"` / `"false"` で渡す。`caption` はワークフロー内でシェルの `"…"` に展開されるので `"` `` ` `` `$` `\` を含めない。

## キャプションの規則（フィードのみ）
1. 1行目は見出し（ハウススタイル。`make_story_promo.py` もこの行を既定の見出しに使う）。
2. `#日大生プロジェクト` は自主創造プロジェクトの規定で必須。`scripts/post_to_instagram.py` の `REQUIRED_TAGS` / `ensure_required_tags()` が無ければ自動付与する。**この機構を壊さない**（スクリプトを迂回して API を直接叩かない・タグを消さない）。ストーリーズはキャプション自体が無いので対象外。
3. 公開文言では「予約」と言い切らない。仮予約は非公式で教室の使用権を保証しない旨を必ず併記する。
4. テスト運用中の非公式サービスである旨（学生課/教務課と協議中・誤認防止）を入れる。

## 手順A: フィード投稿（＋告知ストーリー生成）
1. 画像（正方形）を `assets/instagram/` に置き、ユーザー確認のうえコミット・push する（`git config user.email noreply@anthropic.com && git config user.name Claude`）。push 済みならブランチは問わない（SHA で参照するため）。
2. `image_url` は**ブランチ/コミットSHA固定の raw URL** `https://raw.githubusercontent.com/nu-roomradar/nust-room-search/<コミットSHA>/assets/instagram/<file>.png` を渡す。投稿前に `curl -sL "<URL>" | md5sum` と `md5sum <ローカルファイル>` を突き合わせ、キャッシュ齟齬がないか確認すると安全（raw.githubusercontent.com はこの環境から到達可。github.io / onrender.com は不可）。
3. キャプションを上記規則で作り、`story_headline`（全角14文字程度）を決める。
4. 入力値一式（post_type=feed, image_url, caption 全文, also_story=true, post_story=false, story_headline）をユーザーに提示し、承認を得る。
5. 承認後に起動: `mcp__github__actions_run_trigger`（method=run_workflow, owner=nu-roomradar, repo=nust-room-search, workflow_id=instagram-post.yml, ref=main, inputs={…}）。
6. 追跡: `mcp__github__actions_list`（list_workflow_runs, resource_id=instagram-post.yml）で run_id を得る → `mcp__github__actions_list`（list_workflow_jobs, resource_id=<run_id>）で job_id を得る → `mcp__github__get_job_logs`（job_id=<job_id>, return_content=true）。失敗時は `get_job_logs`（run_id=<run_id>, failed_only=true, return_content=true）。`get_job_logs` は job_id（単一ジョブ）か run_id+failed_only=true（失敗ジョブのみ）のどちらかが必須で、return_content=true だけでは成功ログを取れない。成功ログは `投稿完了！ メディアID: …`。
7. also_story=true のとき、ワークフローは `scripts/make_story_promo.py` で `assets/instagram/auto/latest-story.png`（1080x1920）を生成し、成果物 `promo-story-preview` にアップロードしたうえで github-actions[bot] がそのファイルを `main` にコミット・push する（`data/*.json` と同様、手元と競合したら pull して新しい方を採用）。→ 手順B へ。

## 手順B: 告知ストーリーの確認と投稿
1. **ストーリーは画像を目視確認してから投稿する。確認前に投稿しない。** github-actions[bot] は `main` にコミットするが、このセッションは `claude/…` 作業ブランチ上で動くため素の `git pull` では取得できないことがある。`main` の該当ファイルを明示的に取り込む: `git fetch origin main && git checkout FETCH_HEAD -- assets/instagram/auto/latest-story.png`、または `curl -sL https://raw.githubusercontent.com/nu-roomradar/nust-room-search/<botのコミットSHA>/assets/instagram/auto/latest-story.png -o assets/instagram/auto/latest-story.png`（bot のコミット SHA は `mcp__github__list_commits`（sha=main）や手順A 6 のログで確認。raw.githubusercontent.com は到達可）。取り込んだ `assets/instagram/auto/latest-story.png` を Read で確認し、ユーザーにも提示して（SendUserFile、または Actions の成果物 `promo-story-preview` / コミットされたファイルを GitHub で開いてもらう）承認を得る。見出しの改行位置・級数（88→54px で2行に収める。収まらなければ最小級数で3行）、埋め込み画像、`プロフィールでチェック` の導線を見る。API 経由のストーリーにはタップ可能なリンクスタンプを付けられないため、画像内文言で誘導する仕様。
2. 直したい場合はセッション内で再生成 → 再確認 → コミット・push。`scripts/make_story_promo.py` は preinstall 済みの Chrome（`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`）があればそれを使うので、そのまま実行できる（1080x1920 の PNG が出る）:
   ```
   python scripts/make_story_promo.py --feed-image-url <フィード画像の raw URL> --headline <見出し> --out assets/instagram/auto/latest-story.png
   ```
3. 承認が取れたら `post_type=story`、`image_url` = コミット済み `latest-story.png` の SHA 固定 raw URL で起動する（手順A 5〜6 と同じ。起動前に入力値を再提示）。
4. CLAUDE.md の「確認を取ってから `post_story` を有効にして投稿」は、**同一 run 内でフィードと一緒にストーリーまで投稿する場合**の指定（`post_story=true` を使ってよいのは、ユーザーが画像を事前確認済み＝手順B 2 でローカル生成して承認し、フィードと同じ実行でストーリーまで投稿する意図を明示した場合だけ）。`post_story` はワークフローの条件 `post_type == 'feed' && also_story && post_story` のとおり `post_type=feed` の run でしか動かず、確認後にフィード run を再実行するとフィードが二重投稿されるため、**確認後の別 run では `post_type=story` ＋ コミット済み `latest-story.png` の SHA 固定 raw URL で投稿する**（手順B 3）。CLAUDE.md と矛盾しているのではなく、確認後に別 run で投稿するときの手段を補っている。

## 手順C: 単体ストーリー投稿（既存画像・弔事など）
1. 画像（1080x1920）を `assets/instagram/` にコミット・push し、SHA 固定 raw URL を作る。
2. 画像をユーザーに提示して承認を得てから `post_type=story` で起動する。
3. **弔事（お見舞い・追悼）のストーリー**は、QR・LP リンク・CTA・ハッシュタグ・絵文字を一切入れない。ブランドカラー（青/ネイビー）も使わず明朝体（Noto Serif JP）で組む。実例は `scripts/make_condolence_story.py`（暖色グレージュ背景、ロゴ＋「RoomRadar 運営」の署名、上下の安全マージン 150px/240px、Playwright `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` で `assets/instagram/kumamoto-condolence-story.png` を出力）。新しい弔事は同スクリプトを雛形に文面だけ差し替え、文面もユーザーに確認してから生成する。

## トークン失効（投稿・集計が急に失敗し出したとき）

使っているのは **Instagram ビジネスログイン方式**（実行ログの `[INFO] 使用エンドポイント: https://graph.instagram.com` で確認済み。Facebookページ経由の古い方式ではない）。`IG_ACCESS_TOKEN` は**長期アクセストークンで有効期限は発行から60日**。

1. **まず期限を疑う。** `get_job_logs` の `[ERROR] … type= code= message=` を見る（`OAuthException` / code=190 なら期限切れ・無効）。週次の運用ヘルスチェックも同じ失効を Issue で知らせる。
2. **再発行**（ユーザーの作業。Claude 側からはできない）:
   1. https://developers.facebook.com/apps/ で RoomRadar のアプリを開く
   2. 左メニュー **Instagram** → **API setup with Instagram business login**（日本語UIなら「Instagramビジネスログインを使用したAPIセットアップ」）
   3. **「3. Generate access tokens」**の `@roomradar_nust` の横で **Generate token** → Instagram にログイン → 長いトークンが出る。**画面を閉じると二度と見られない**
   4. 同じ画面の **Instagram account ID** が `IG_ACCOUNT_ID` と一致しているか確認（変わっていなければ触らない）
3. **Secret の差し替え**（ユーザーの作業。MCP ではできない）:
   https://github.com/nu-roomradar/nust-room-search/settings/secrets/actions → `IG_ACCESS_TOKEN` を更新。
   iPad で編集ボタンが出ないときは Safari の「デスクトップ用Webサイトを表示」。
4. **確認**: `mcp__github__actions_run_trigger`（run_workflow, `ops-healthcheck.yml`, inputs `{"dry_run":"true"}`）を回し、
   ログの `Instagram: アクセストークンは有効です` を見る。本番実行（dry_run なし）なら Issue #23 系が自動で閉じる。
5. 失敗した run を `rerun_failed_jobs` で再実行するか、改めて起動する（再起動前にユーザー確認）。

**60日ごとの再発行をやめたい場合**: `GET https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=<現行>` で**失効前なら60日延長できる**。月1回これを叩くワークフローを置けば人手が要らなくなるが、Actions が自分の Secret を書き換えるには **Secrets の書き込み権限を持つ PAT** を1つ置く必要がある（60日ごとの手作業 ↔ 長期の PAT 1本、のトレードオフ）。未導入。導入するかはユーザーの判断。
