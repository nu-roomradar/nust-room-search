# 2027年度の時間割の原本を置く場所

まだ空。**2027年度の時間割表が教務ページで公開されたら、ここに入れる。**

## 手順

1. https://www.kyoumu.cst.nihon-u.ac.jp/timetable/ から、**全区分・全学科**の時間割表をダウンロードする
   - 理工学部（14学科＋一般教育。交通システム工学科はコース別に2つ）
   - **短期大学部**（船橋校舎を共用しているので必須。入れないと短大の授業が入った教室を「空き」と出す）
   - 博士前期・博士後期
   - 2026年度は合計49ファイルだった
2. ファイル名は**変えずに**このフォルダに置く（区分・学科・年度をファイル名から読んでいる）
3. 動かす:
   ```
   python scripts/build_schedule_db.py --report     # 2026年度との差分を確認
   python -m unittest discover -s tests             # テストが通るか
   python scripts/build_schedule_db.py --replace    # 差し替え（.bak が自動で作られる）
   python scripts/export_classes.py                 # 生データ一覧 data/classes_2027.csv
   ```
   `--year` を省略すると**中身のある最新の年度フォルダ**が自動で選ばれるので、
   ここにファイルを入れた時点で 2027年度に切り替わる。2026年度に戻したいときは `--year 2026`。
4. このファイル（README.md）は消してよい

詳しい手順と注意点は `docs/OPERATIONS.md` の 6.、原本の構造は `data/source/README.md`。

Claude Code に「2027年度の原本を置いた」と言えば、あとはやってくれる。
