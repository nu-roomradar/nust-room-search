# cm3.html をコマ撮りして MP4 にする。python3 render.py <dir> [--preview t1,t2,...] [--out name.mp4]
import sys, os, json, subprocess, http.server, threading, functools
from playwright.sync_api import sync_playwright
D = sys.argv[1]; FPS = 30; DUR = 24.0
args = sys.argv[2:]; preview = None; out = "roomradar-cm3.mp4"
if "--preview" in args: preview = [float(x) for x in args[args.index("--preview") + 1].split(",")]
if "--out" in args: out = args[args.index("--out") + 1]
clips = json.load(open(f"{D}/clips4.json")) if os.path.exists(f"{D}/clips4.json") else {}
html = open(f"{D}/cm4.html", encoding="utf-8").read().replace("__RECTS__", open(f"{D}/rects.json").read()).replace("__CLIPS__", json.dumps(clips))
open(f"{D}/cm4_built.html", "w", encoding="utf-8").write(html)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=D)); threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/cm4_built.html"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
    pg = b.new_page(viewport={"width": 1080, "height": 1920})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url, wait_until="load"); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(1500)
    print("fonts:", pg.evaluate("[document.fonts.check('900 60px JPB'), document.fonts.check('60px Hand')]"), errs)
    if preview:
        for t in preview:
            pg.evaluate(f"render({t})"); pg.screenshot(path=f"{D}/pv-{t:05.2f}.png")
    else:
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
                               "-i", f"{D}/cm4_audio.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-tune", "film", "-pix_fmt", "yuv420p",
                               "-profile:v", "high", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
                               "-shortest", "-movflags", "+faststart", f"{D}/{out}"], stdin=subprocess.PIPE)
        for i in range(int(DUR * FPS)):
            pg.evaluate(f"render({i / FPS})")
            ff.stdin.write(pg.screenshot(type="jpeg", quality=93))
        ff.stdin.close(); ff.wait(); print("ffmpeg rc", ff.returncode)
    print("errors:", errs[:3])
    b.close()
srv.shutdown()
