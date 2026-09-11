# 時間割の原本置き場

`schedule_final.db` を作り直すための**原本ファイル**をここに置く。
（`data/source/classroom_data.xlsx` などは原本ではなく集計結果で、DB の 48% しか再現できない。詳細は `docs/OPERATIONS.md` 6.）

## 何を置くか

- 学科・一般教養ごとの時間割ファイル（DB 作成時に使ったもの。`1-07.xlsx` `1-12.xlsx` のような名前だったはず）
- 教務の時間割ページ（ https://www.kyoumu.cst.nihon-u.ac.jp/timetable/ ）からダウンロードしたファイル
- 形式は xlsx / csv / pdf / html いずれでも可。**ファイル名は変えずに**置く（DB の `元ファイル` 列と突き合わせるため）

年度・学期ごとにサブフォルダを切る:

```
data/source/timetables/
├── README.md          ← このファイル
├── 2026/              ← 2026年度（現行 DB の元）
│   ├── 1-07.xlsx
│   └── ...
└── 2027/              ← 翌年度分はここに
```

## iPad からのアップロード手順（GitHub の Web 画面）

1. Safari で https://github.com/nu-roomradar/nust-room-search/tree/main/data/source/timetables を開く
2. 右上の **Add file → Upload files**（表示されない場合は Safari の「デスクトップ用 Web サイトを表示」を有効にする）
3. **choose your files** から「ファイル」アプリの該当ファイルを選ぶ（複数選択可。1ファイル 25MB まで、1回に 100 ファイルまで）
4. 下の Commit changes は **Commit directly to the main branch** のまま **Commit changes**
5. アップロード後、Claude Code のチャットで「原本を置いた」と伝えれば、DB の再現スクリプト作成に進める

年度フォルダ（`2026/` など）は、アップロード画面のファイル名欄で `2026/1-07.xlsx` のようにスラッシュ付きで入力すると自動で作られる。
