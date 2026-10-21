#!/usr/bin/env python3
"""GitHub Actions 用の依存ロックファイル（.github/requirements/*.txt）を作る。

Secrets や書き込み権限を持つワークフローで `pip install requests` のように版なしで入れると、
PyPI のパッケージ（や、その依存）が乗っ取られて悪い版が出たとき、次の定期実行でそのまま入り、
Secrets を盗まれる（2026-10-22 点検）。そこで版とハッシュを固定し、ワークフローでは
`pip install --require-hashes --only-binary :all: -r .github/requirements/<名前>.txt` で入れる。

仕組み: pip の --report で版を解決し、PyPI の JSON から、その版の全ファイルの sha256 を集めて書く。
GitHub Actions と同じ Python 3.11・Linux で動かすこと（この環境の python3 は 3.11）。

使い方（版を上げるとき）:
  cd .github/requirements && for f in *.in; do python3 ../../scripts/lock_workflow_requirements.py "$f"; done
既知の脆弱性がある版を選んだときは「!!」を出す。
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import urllib.request

src = pathlib.Path(sys.argv[1])
out = src.with_suffix(".txt")
with tempfile.TemporaryDirectory() as td:
    rep = pathlib.Path(td) / "r.json"
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--dry-run", "--ignore-installed",
                    "--only-binary", ":all:", "--report", str(rep), "-r", str(src)], check=True)
    items = json.loads(rep.read_text())["install"]
lines = [f"# {src.name} から生成（作り直し方は .github/requirements/README.md）。手で書き換えない", ""]
for it in sorted(items, key=lambda i: i["metadata"]["name"].lower()):
    name, ver = it["metadata"]["name"], it["metadata"]["version"]
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{ver}/json", timeout=60) as r:
        data = json.load(r)
    digests = sorted({u["digests"]["sha256"] for u in data["urls"]})
    vulns = data.get("vulnerabilities") or []
    if vulns:
        print(f"!! {name}=={ver} has {len(vulns)} known vulnerabilities", file=sys.stderr)
    lines.append(f"{name}=={ver} \\")
    lines += [f"    --hash=sha256:{d}" + (" \\" if i < len(digests) - 1 else "") for i, d in enumerate(digests)]
out.write_text("\n".join(lines) + "\n")
print(out.name, len(items), "packages")
