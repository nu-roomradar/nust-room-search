"""下書きのコマを並べた一覧を作る: python3 sheet.py 1.5,3,4.2 [--scale 0.4] [--cols 6] [--name sheet]"""
import subprocess, sys, os
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); times = sys.argv[1]
arg = lambda k, d: (sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d)
scale, cols, name, q = arg("--scale", "0.4"), int(arg("--cols", "6")), arg("--name", "sheet"), arg("--query", "")
subprocess.run([sys.executable, os.path.join(HERE, "render.py"), "--scale", scale, "--times", times, "--out", "renders/pv", "--query", q], check=True)
ims = [Image.open(os.path.join(HERE, "renders/pv", f"t{float(x):06.2f}".replace(".", "_") + ".jpg")) for x in times.split(",")]
w, h = ims[0].size; rows = (len(ims) + cols - 1) // cols
c = Image.new("RGB", (cols * (w + 6), rows * (h + 6)), "#222")
for i, im in enumerate(ims): c.paste(im, ((i % cols) * (w + 6), (i // cols) * (h + 6)))
c.save(os.path.join(HERE, "renders/pv", name + ".jpg"), quality=88); print(c.size)
