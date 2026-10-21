# GitHub Actions 用の依存（版とハッシュを固定）

Secrets や書き込み権限を持つワークフローは、ここのファイルで依存を入れる。

```
pip install --require-hashes --only-binary :all: -r .github/requirements/<名前>.txt
```

| ファイル | 使うワークフロー | 中身 |
|---|---|---|
| `requests.txt` | instagram-post・ops-healthcheck | requests |
| `ig-token-refresh.txt` | ig-token-refresh | requests・pynacl |
| `ga4.txt` | ga4-weekly | google-analytics-data |
| `story-promo.txt` | instagram-post（告知ストーリーの画像） | requests・playwright |

- `.in` が「入れたいもの」、`.txt` が版とハッシュまで固定した結果。`.txt` は手で書き換えない。
- 版なしで入れると、PyPI のパッケージ（やその依存）が乗っ取られて悪い版が出たとき、次の定期実行でそのまま入り、
  Secrets（Instagram のトークン・GA4 の鍵・Secrets を書き換えられる PAT）を盗まれる。ハッシュで固定すれば、
  固定した版と中身が1バイトでも違えば入らない（2026-10-22 点検）。
- **作り直し方**（版を上げるとき。半年に1回くらい、または脆弱性の知らせが来たとき）:
  ```
  cd .github/requirements && for f in *.in; do python3 ../../scripts/lock_workflow_requirements.py "$f"; done
  ```
  Actions と同じ Python 3.11・Linux で動かす。「!!」が出たら、その版に既知の脆弱性がある。
  作り直したら `tests/test_workflows.py` を通し、ワークフローを手動（dry_run）で1回動かして確かめる。
