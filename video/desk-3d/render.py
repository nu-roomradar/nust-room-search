"""3D 広告を1コマずつ書き出す。index.html を開き、window.renderAt(t) を呼んでは画面を撮る。
  下書き（半分の大きさ・指定した時刻だけ）: python3 render.py --scale 0.5 --times 1,4,6.5,10 --out renders/pv
  本番（全コマ）:                         python3 render.py --out renders/frames            （続きから: --start 300）
  2つに分けて同時に:                     python3 render.py --out renders/frames --part 0/2 ＆ --part 1/2
撮ったコマは ffmpeg でつなぐ（README）。この環境に GPU は無いので、Chrome の中のソフトウェア描画（SwiftShader）で描く。"""
import argparse, functools, http.server, os, sys, threading, time
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
from _browser import find_chrome
ap = argparse.ArgumentParser()
ap.add_argument("--scale", type=float, default=1.0); ap.add_argument("--times", default=""); ap.add_argument("--out", default="renders/frames")
ap.add_argument("--start", type=int, default=0); ap.add_argument("--end", type=int, default=-1); ap.add_argument("--part", default="0/1")
ap.add_argument("--fps", type=int, default=30); ap.add_argument("--duration", type=float, default=30.0); ap.add_argument("--query", default="")
ap.add_argument("--page", default="index.html")       # door.html なら「ポスターとドア」の版（--duration 27）
a = ap.parse_args()
out = os.path.join(HERE, a.out); os.makedirs(out, exist_ok=True)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *x): pass
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))        # リポジトリの根から配る（ポスターの画像など assets/ も読むため）
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/video/desk-3d/{a.page}?{a.query}"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=find_chrome(), args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--disable-gpu-vsync"])
    pg = b.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=a.scale)
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type in ("error", "warning") else None)
    t0 = time.time(); pg.goto(url)
    for _ in range(360):                       # 文法の誤りなどでページが壊れていたら、待ち続けずにすぐ知らせる
        if pg.evaluate("window.__ready === true || !!window.__error"): break
        if any("SyntaxError" in e or "TypeError" in e or "ReferenceError" in e for e in errs): print("ページのエラー:", errs[:8]); sys.exit(1)
        time.sleep(0.5)
    else: print("読み込みに失敗（180秒）:", errs[:8]); sys.exit(1)
    if pg.evaluate("window.__error || ''"): print("エラー:", pg.evaluate("window.__error"), errs[:8]); sys.exit(1)
    print(f"準備 {time.time()-t0:.1f}s", "警告:" if errs else "", errs[:6], flush=True)
    stage = pg.locator("#stage")
    if a.times:
        jobs = [(f"t{float(x):06.2f}".replace(".", "_") + ".jpg", float(x)) for x in a.times.split(",")]
    else:
        n = int(round(a.duration * a.fps)); end = n if a.end < 0 else min(n, a.end); k, m = map(int, a.part.split("/"))
        jobs = [(f"{i:05d}.jpg", i / a.fps) for i in range(a.start, end) if i % m == k]
    t1 = time.time()
    for j, (name, t) in enumerate(jobs):
        path = os.path.join(out, name)
        if not a.times and os.path.exists(path) and os.path.getsize(path) > 0: continue
        pg.evaluate("t => window.renderAt(t)", t)
        stage.screenshot(path=path, type="jpeg", quality=95)
        if j % 20 == 0 or a.times: print(f"{name} t={t:.2f} ({(time.time()-t1)/(j+1):.2f}s/コマ)", flush=True)
    if errs: print("警告:", errs[:6])
    b.close()
print("完了", len(jobs), "コマ", f"{time.time()-t1:.0f}s")
