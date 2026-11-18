"""リールを1コマずつ撮って mp4 にする（HTML の renderAt(t) を呼んで撮る。AI の映像は使わない）
  下書きのコマの一覧:  python3 render.py r1.html --sheet 0.8,3,6,9,12
  本番:              python3 render.py r1.html --out out-r1.mp4 [--audio r1.wav]
"""
import argparse, functools, http.server, os, subprocess, sys, threading
from PIL import Image
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from _browser import find_chrome
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))

def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    h = functools.partial(Quiet, directory=HERE)
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s

ap = argparse.ArgumentParser(); ap.add_argument("page"); ap.add_argument("--out"); ap.add_argument("--audio")
ap.add_argument("--sheet"); ap.add_argument("--fps", type=int, default=30); ap.add_argument("--scale", type=float, default=0.3)
a = ap.parse_args()
srv = serve()
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=find_chrome())
    pg = br.new_page(viewport={"width": 1080, "height": 1920})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{srv.server_port}/{a.page}", wait_until="load")
    pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(500)
    dur = pg.evaluate("window.DURATION")
    if errs: print("JS エラー:", errs); sys.exit(1)
    if a.sheet:
        ts = [float(x) for x in a.sheet.split(",")]; ims = []
        for t in ts:
            pg.evaluate(f"renderAt({t})"); f = f"/tmp/_sheet_{t}.png"; pg.screenshot(path=f)
            ims.append(Image.open(f).resize((int(1080 * a.scale), int(1920 * a.scale))))
        W = ims[0].width; sh = Image.new("RGB", (len(ims) * (W + 10), ims[0].height), "white")
        for i, im in enumerate(ims): sh.paste(im, (i * (W + 10), 0))
        out = os.path.join(HERE, "pv-" + a.page.replace(".html", ".png")); sh.save(out); print(out, "長さ", dur)
    if a.out:
        n = int(round(dur * a.fps)); tmp = os.path.join(HERE, "_video.mp4")
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(a.fps), "-i", "-",
                               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", tmp], stdin=subprocess.PIPE)
        for i in range(n):
            pg.evaluate(f"renderAt({i / a.fps})"); ff.stdin.write(pg.screenshot(type="png"))
            if i % 60 == 0: print(f"{i}/{n}", flush=True)
        ff.stdin.close(); ff.wait()
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", tmp]
        if a.audio: cmd += ["-i", a.audio, "-af", "alimiter=limit=0.89:level=false", "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-shortest"]
        cmd += ["-c:v", "copy", "-movflags", "+faststart", os.path.join(HERE, a.out)]
        subprocess.run(cmd, check=True); os.remove(tmp); print("書き出し:", a.out, f"{n}コマ")
    br.close()
srv.shutdown()
