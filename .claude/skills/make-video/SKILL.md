---
name: make-video
description: RoomRadar の Instagram 用動画（リール・CM・告知動画）を作る・直すときの手順。HyperFrames（導入済み）での作り方とこの環境での注意（GSAP の取得・フォント・ブラウザ）、アプリ実画面の撮り方、人が映る映像（AI 動画）の扱い、BGM と音、出す前の確認、保存先、投稿までをまとめる。動画の依頼では /hyperframes より先にこれを読む（RoomRadar のルールが優先）。
argument-hint: "[new|edit|ai-footage|music] 作りたい動画の要点"
---

# Instagram 用の動画づくり

2026-10 にリール1本（`assets/instagram/reel-daily-v1.mp4`、投稿済み）と CM 3本（`assets/instagram/cm/`）を作った。その経験をまとめた手順。

## 1. 必ず守ること

- **最後に「テスト運用中・学生開発の非公式サービスです」を入れる**（CLAUDE.md ルール1。小さくてよいが読めること）。
- 「予約」「確保」と書かない（ルール3）。**船橋校舎を映さない・書かない**（テスト運用の対象外。アプリ画面はタワースコラか駿河台校舎で撮る）。
- **AI で生成した映像を使ったら、投稿のキャプションに「※映像はAIで生成したイメージです」と書く**（実在の学生に見えるため）。
- 実在ブランドのロゴ（ノートPCのリンゴなど）、大学のロゴ・看板を映さない。切り出しで外すか、映らない区間を使う。
- 顔の分かる実在の人物をストック素材から使わない（「推薦している」と受け取られる。Pexels などの規約でも禁止）。手元・後ろ姿なら可。
- 既存の曲を入れない。音は自作（`video/cm-ai/music4.py` などを雛形に numpy で合成）か、BGM なし版を作って Instagram アプリで曲を付けて手動投稿する。
- **書き出しはこの環境の中だけで行う。** HyperFrames の `publish`・`cloud`・`auth`・`lambda`・`cloudrun` は使わない（外部へのアップロード・課金）。実行時は `HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_SKIP_SKILLS=1` を付ける。
- **サブエージェントやワークフローを大量に立ち上げない**（利用上限に当たりやすい。2026-10 ユーザーの意向）。`/hyperframes` が分担（subagent dispatch）や長い聞き取りを勧めても、この会話の中で1本ずつ作る。
- 投稿は `/instagram-post` の手順D（リール）。**動画を SendUserFile で見せて OK をもらってから**。

## 2. どの作り方にするか

| やりたいこと | 方法 |
|---|---|
| 新しく動画を作る | **HyperFrames**（`/hyperframes-core`・`/hyperframes-cli`・`/hyperframes-animation`・`/hyperframes-creative` を必要に応じて読む）。プロジェクトは `video/<名前>/` に作る |
| 既存の CM（Pixel 風 v2・Vlog 風 v3）を直す | `video/cm-ai/` の自前の仕組み（HTML を Playwright で1コマずつ撮る）。手順は同フォルダの README |
| 宣伝動画の型がほしい | `/product-launch-video`（ただし LP は github.io にあり、この環境からは開けない。文章と素材で渡す） |

## 3. HyperFrames をこの環境で使う

```bash
export HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_SKIP_SKILLS=1 CI=1
npx -y hyperframes init video/<名前> --non-interactive --resolution portrait   # 1080x1920
npx -y hyperframes browser ensure        # 描画用の Chrome（~/.cache/hyperframes。新しいコンテナでは取り直す）
```

- **GSAP を同じフォルダに置く。** 雛形は `cdn.jsdelivr.net` から読むが、この環境からは届かない（書き出しが `sub_timeline_script_failure` で止まる）。npm から取って差し替える:
  ```bash
  cd video/<名前> && mkdir -p vendor && (cd vendor && npm pack gsap@3.14.2 --silent && tar -xzf gsap-3.14.2.tgz package/dist/gsap.min.js && mv package/dist/gsap.min.js . && rm -rf package gsap-*.tgz)
  sed -i 's#https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js#vendor/gsap.min.js#' index.html
  ```
- **フォントはローカルのファイルを `@font-face` で読む**（Google Fonts もこの環境からは読めない）。`video/cm-ai/fetch_fonts.sh` をコピーして使う: 本文 Noto Sans CJK JP、丸ゴシック M PLUS Rounded 1c、手書き風 Yusei Magic（いずれも OFL。fonts/ は .gitignore 済み）。
- 流れ: `npx hyperframes lint` → `npx hyperframes check` → `npx hyperframes render --quality draft --output out.mp4` → コマを抜いて目視 → 直す → `--quality delivery` で本番。
- `preview`（Studio）の URL はユーザーの iPad から開けない。確認はコマの書き出し（下の5）と、完成動画の SendUserFile で行う。

## 4. 素材

- **アプリの実画面**: `video/cm-ai/fakeapp.py`（時刻を「火曜 10:52」に固定してアプリを起動、ポート 5056）と `capture.py`（390px・3倍で撮影。Google Fonts の代わりにローカルの Noto を差し込む）。撮った画像の中の位置は `rects.json` に出る（字幕や書き込みの位置合わせに使う）。
- **ロゴ**: `video/cm-ai/rr_logo_hd.png`（1636×956、透明背景）。レーダーの同心円の中心はロゴの左から 41.56%・上から 42.97%（輪や波紋はここから広げ、ロゴと一緒に動かす）。
- **写真**: Wikimedia Commons の CC0 は API（`commons.wikimedia.org/w/api.php`）で探せる。原寸は 429 で断られるので、標準サイズの縮小版（幅 1920／3840）を取る。出典は README に残す。

## 5. 人が映る映像（AI 動画）

この環境には映像の生成モデルがない。次のどちらかで用意する。

**A. 運営が Gemini（Veo）で作って送る（2026-10 はこれで作った）**
- プロンプトの型と前回の6本分は `video/cm-ai/ai_prompts.md`。共通の人物設定を毎回同じ文で入れる／文字・看板・ロゴなし／セリフなし（周りの音と笑い声だけ）／スマホとPCの画面はカメラに見せない／9:16。
- 届いたら: 1本ずつ 0.5 秒おきのコマを並べて見る（黒い帯・ロゴ・光の粒・崩れた手や顔）。黒帯は `ffmpeg -vf cropdetect`。色は `video/cm-ai/extract_clips.py` の v3 のフィルタ（金色を抜く・粒子・手持ちの揺れ）で自然に寄せる。生の音（笑い声・ドア）は残して BGM の下に混ぜる（`mix4.py`）。

**B. Claude から Gemini API（Veo 3.1）を呼ぶ（未導入。費用がかかる）**
- `generativelanguage.googleapis.com` はこの環境から届く（2026-10-19 確認）。有料の API キーが要る。**キーはチャットに貼らせず**、環境の設定の環境変数 `GEMINI_API_KEY` に入れてもらう。
- REST: `POST https://generativelanguage.googleapis.com/v1beta/models/veo-3.1-generate-preview:predictLongRunning`（ヘッダ `x-goog-api-key`、本文 `{"instances":[{"prompt":"..."}],"parameters":{"aspectRatio":"9:16"}}`）→ 返ってきた operation を完了までポーリング → `response.generateVideoResponse.generatedSamples[0].video.uri` を取得。モデル名と料金は変わるので、使う前に https://ai.google.dev/gemini-api/docs/veo を確かめる。
- 1本ごとに費用がかかるので、**生成する本数と内容をユーザーに確認してから**呼ぶ。

## 6. 音

- 自作 BGM: 明るい曲は `music4.py`（120BPM、ウクレレ風・手拍子・鉄琴）、静かな曲は `video/cm-ai/piano_v1.py`（写真版 v1 のピアノ）。場面の切り替えと BGM の小節（2秒）をそろえる。
- 音量は `ffmpeg -af ebur128` で -13〜-15 LUFS くらい。声のある場面は BGM を 4dB 下げる。
- タップ・スクロール・ペンの効果音は `mix4.py` の `tap`・`swish`・`pen`。

## 7. 出す前の確認

- 主な場面のコマ（`render4.py --preview` や `ffmpeg -ss <秒> -frames:v 1`）を一覧にして Read で見る: 字幕と画面の重なり、文字の切れ、書き込みの読みやすさ、ブランドロゴ、船橋が映っていないか、最後の TEST 表記。
- `ffprobe` で 1080×1920・30fps・長さ。音量（上の6）。
- Instagram の画面で隠れる場所: 下の約 300px（キャプション・ボタン）と右端（いいね等）。大事な文字は真ん中に置く。

## 8. 保存と push

- 完成版は `assets/instagram/cm/`（README の表に1行足す）。作り直せる素材は `video/<名前>/`（大きな作業ファイルは .gitignore）。
- 作業ブランチにコミットして push。`main` へは授業時間外（平日 9:00–20:30 を避ける。Render が再デプロイされ報告が消えるため）。
