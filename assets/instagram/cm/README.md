# Instagram 用 CM 動画（2026-10）

どれも 1080×1920・30fps・H.264＋AAC の縦型。リール投稿用。まだ投稿していない（2026-10-19 時点）。

| ファイル | 長さ | 中身 | 映像 | 音 |
|---|---|---|---|---|
| `cm3-vlog-v3.mp4` | 24秒 | **最新。** 学生の Vlog 風。画面録画風のアプリ操作＋手書きの書き込み＋Reels 風字幕 | AI 生成（運営が Gemini で作った6本）を色調整・粒子・手持ちの揺れで自然に | 自作BGM＋AI動画の生の音＋効果音 |
| `cm3-vlog-v3-nobgm.mp4` | 24秒 | 同上の BGM なし | 同上 | 生の音と効果音だけ。Instagram アプリで曲を付けて手動投稿する用 |
| `cm2-pixel-v2.mp4` | 25秒 | Google Pixel の広告風。パステル背景のアプリ画面と太字の字幕 | AI 生成（同上） | 自作BGM（120BPM）＋生の音＋効果音 |
| `cm1-photo-v1.mp4` | 24.5秒 | Apple 風の静かな構成。写真をゆっくり動かして撮影風に | Wikimedia Commons の CC0 写真6枚（下の表） | 自作ピアノ |

- 1本目のリール（アプリ画面のアニメ）は `../reel-daily-v1.mp4`。2026-10-17 に投稿済み。
- v2・v3 は `video/cm-ai/` から作り直せる（手順はそちらの README）。v1 の素材は残していない。
- 投稿手順は `/instagram-post` の手順D（リール）。BGM なし版に Instagram の曲を付けるときは API では付けられないので、アプリから手動で投稿する（`#日大生プロジェクト` を手で入れる）。

## キャプション（v3 の案）

```
空きコマを、もっと楽しく。

次の授業が休講になっても、RoomRadar を開けば、いま空いている教室がすぐ見つかります。
課題も、おしゃべりも。空きコマの居場所に。

駿河台キャンパス（タワー・スコラ／駿河台校舎）で、12月19日まで（予定）テスト運用中です。
プロフィールのリンクから使えます。

※テスト運用中の非公式サービスです（学生開発・大学公式ではありません）。時間割にない授業もあるので、使う前にドア越しに確認してください。
※映像はAIで生成したイメージです。

#RoomRadar #日本大学 #日大理工 #駿河台キャンパス #空きコマ #空き教室 #大学生の日常 #日大生プロジェクト
```

v1 を出すときは最後の注記を「※映像はイメージです（写真：Wikimedia Commons／CC0）」にする。

## 守ること

- **AI 生成の映像を使った版（v2・v3）は、キャプションに「AIで生成した映像」と必ず書く。** 実在の学生に見えるため。
- 船橋校舎を映さない・書かない。「予約」「確保」と書かない（CLAUDE.md ルール3）。
- 動画の最後に「テスト運用中・学生開発の非公式サービスです」を入れてある。消さない（ルール1）。

## v1 の写真の出典（すべて CC0。表記の義務はないが記録として）

| 場面 | ライセンス | 作者 | 出典 |
|---|---|---|---|
| 廊下 | CC0 | Ourlibrary | https://commons.wikimedia.org/wiki/File:UNIVERSITY_LIBRARY_CORRIDOR,_AUGUSTINE_UNIVERSITY,_EPE.jpg |
| スマホを持つ手 | CC0 | NeONBRAND | https://commons.wikimedia.org/wiki/File:Smartphone_in_Hand_(Unsplash).jpg |
| 空いた教室 | CC0 | Paul The Writer | https://commons.wikimedia.org/wiki/File:A_Sideview_of_an_Empty_Classroom.jpg |
| ノートと鉛筆 | CC0 | Thought Catalog | https://commons.wikimedia.org/wiki/File:Taking_notes_with_a_pencil_(Unsplash).jpg |
| ノートとPC | CC0 | JESHOOTS.COM | https://commons.wikimedia.org/wiki/File:Businessman_working_and_writing_notes_in_office_(Unsplash).jpg |
| 窓の外 | CC0 | Raichin | https://commons.wikimedia.org/wiki/File:Window_12.jpg |
