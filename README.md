# RoomRadar 📡

日本大学理工学部の**空き教室リアルタイム検索サービス**。
曜日・時限・校舎を選ぶだけで、時間割データをもとに授業が入っていない教室を表示します。

> ⚠️ 本サービスは**テスト運用中の非公式サービス**です。日本大学「自主創造プロジェクト」の一環として学生が開発・運営しており、大学公式のものではありません。

## リンク

| | URL |
|---|---|
| 検索アプリ | https://nust-room-search.onrender.com |
| ランディングページ | https://nu-roomradar.github.io/nust-room-search/ |
| Instagram | https://www.instagram.com/roomradar_nust/ |

## 構成

```
├── app.py                  # 検索アプリ本体（Flask・Render でホスティング）
├── index.html              # ランディングページ（GitHub Pages）
├── dashboard.html          # 運営チーム用アナリティクス画面（GitHub Pages）
├── schedule_final.db       # 時間割データベース（検索の元データ）
├── rr_logo.png             # ロゴ（LP から参照）
├── requirements.txt
│
├── data/
│   ├── source/             # 時間割の元データ（xlsx）
│   ├── instagram_*.json    # Instagram インサイト集計（ワークフローが自動更新）
│   └── ga4_*.json          # GA4 サイト分析集計（ワークフローが自動更新）
│
├── assets/
│   ├── instagram/          # Instagram 投稿・ストーリーズ用画像
│   │   └── auto/           # 自動生成されたプロモストーリー画像
│   ├── posters/            # 学内掲示用ポスター（PNG / PDF / PPTX）
│   │   └── handoff/        # 外部デザインツール用素材（ロゴ・QR）
│   └── instagram-qr.png    # LP に表示する Instagram QR
│
├── scripts/
│   ├── post_to_instagram.py        # フィード / ストーリーズ投稿（必須タグ自動付与）
│   ├── make_poster.py              # 学内掲示ポスター生成（PNG/PDF/PPTX・variant切替）
│   ├── make_story_promo.py         # 新規投稿の告知ストーリー画像生成
│   ├── ops_healthcheck.py          # 運用ヘルスチェック（本番URL・Actions・トークン → Issue）
│   ├── fetch_instagram_insights.py # インサイト取得 → data/ へ記録
│   ├── fetch_instagram_posts.py    # 投稿一覧取得
│   └── fetch_ga4_metrics.py        # GA4 指標取得 → data/ へ記録
│
├── tests/                      # 運用スクリプト・hook・アプリの単体テスト（CI で実行）
├── .claude/                    # Claude Code 用の設定（必須表記を守る hook / permissions / 手順書 skills）
│
└── .github/workflows/
    ├── ci.yml                  # push / PR で構文チェックとテスト
    ├── ops-healthcheck.yml     # 毎週月曜 運用ヘルスチェック（異常なら Issue、復旧で自動クローズ）
    ├── instagram-post.yml      # 手動トリガーで投稿（feed / story 選択・同時ストーリー可）
    ├── instagram-insights.yml  # インサイト記録（手動のみ。自動実行は停止中）
    ├── instagram-fetch.yml     # 投稿データ取得（手動のみ）
    ├── ga4-fetch.yml           # GA4 記録（手動のみ）
    └── render-plan-reminder.yml # 9/24 に Render プランを戻すリマインド Issue を作成
```

## 運用メモ

- `reservations.db` / `reports.db`（仮予約・使用中報告）は実行時に自動生成される揮発データで、リポジトリには含めません。
- Instagram 投稿キャプションには規定の共通ハッシュタグ `#日大生プロジェクト` がスクリプトで自動付与されます。
- ポスターは `python scripts/make_poster.py --print-files` で再生成できます（A4縦・約392dpi、PDF/PPTX同時出力）。
- Claude Code on the web では `.claude/hooks/session-start.sh` がセッション開始時に依存パッケージを自動インストールします。
- テストは `python -m unittest discover -s tests -v`（`pip install -r requirements.txt requests` が必要）。push / PR ごとに CI が同じものを回します。
- 運用ヘルスチェックは毎週月曜 09:00 JST に動き、本番 URL の応答と必須表記・Actions の失敗・Instagram トークンの有効性を検査します。異常があると「【運用ヘルスチェック】異常を検知しました」という Issue が開き、復旧すると自動で閉じます。
- Instagram 投稿・ポスター生成・画面検証の手順書は `.claude/skills/` にあります（Claude Code から `/instagram-post` `/make-poster` `/verify-ui`）。

---
日本大学自主創造プロジェクト ／ #日大生プロジェクト
