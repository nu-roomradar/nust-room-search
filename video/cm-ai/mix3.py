# CM3 の音: BGM ＋ AI 動画の生の音（笑い声・ドア・キーボード）＋ 画面操作の小さな効果音
import numpy as np, wave, subprocess, sys
SR = 44100; TOTAL = 25.0; N = int(TOTAL * SR)
def load(path, ss=None, dur=None):
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", str(ss)] if ss is not None else []) + (["-t", str(dur)] if dur else []) + \
          ["-i", path, "-vn", "-ac", "2", "-ar", str(SR), "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).reshape(-1, 2).astype(np.float32) / 32767
music = load("music3.wav")[:N]; music = np.pad(music, ((0, N - len(music)), (0, 0)))
amb = np.zeros((N, 2), np.float32); duck = np.ones(N, np.float32)
def rms_db(x): return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)
# (元動画, 元の開始秒, 長さ, CM 上の開始秒, 目標の大きさ dBFS, 声があるか)
SEG = [("src/c0.mp4", 1.3, 2.0, 0.0, -24, True), ("src/c0.mp4", 4.6, 2.0, 2.0, -23, True),
       ("src/c1.mp4", 2.6, 2.0, 4.0, -34, False), ("src/c2.mp4", 1.0, 2.0, 12.0, -27, False),
       ("src/c3.mp4", 3.0, 1.5, 14.0, -30, False), ("src/c4.mp4", 4.4, 1.5, 15.5, -22, True),
       ("src/c5.mp4", 3.0, 2.0, 19.0, -21, True)]
for src, ss, d, t0, target, voice in SEG:
    x = load(src, ss, d)
    g = 10 ** ((target - rms_db(x)) / 20); g = min(g, 10 ** (14 / 20))      # 小さい環境音を上げすぎない
    x = x * g; k = int(.03 * SR)
    fade = np.ones(len(x), np.float32); fade[:k] = np.linspace(0, 1, k); fade[-k:] = np.linspace(1, 0, k)
    x = x * fade[:, None]; i = int(t0 * SR); j = min(N, i + len(x)); amb[i:j] += x[:j - i]
    if voice:                                       # 声のところだけ BGM を少し下げる
        a, b = int(t0 * SR), int((t0 + d) * SR); r = int(.08 * SR)
        duck[a:b] = np.minimum(duck[a:b], 10 ** (-4 / 20))
        duck[max(0, a - r):a] = np.minimum(duck[max(0, a - r):a], np.linspace(1, 10 ** (-4 / 20), a - max(0, a - r)))
        duck[b:b + r] = np.minimum(duck[b:b + r], np.linspace(10 ** (-4 / 20), 1, min(r, N - b)))
# 効果音（合成）
rng = np.random.default_rng(3)
def tt(d): return np.arange(int(d * SR)) / SR
def tap():
    t = tt(.05); return np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 120) * .5
def pop():
    t = tt(.16); f = 520 + 900 * np.exp(-t * 30); return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 22) * .45
def swish(d=.35):
    t = tt(d); n = rng.standard_normal(len(t)); X = np.fft.rfft(n); fr = np.fft.rfftfreq(len(t), 1 / SR)
    n = np.fft.irfft(X / (1 + (fr / 5000) ** 2) / (1 + (900 / np.maximum(fr, 1)) ** 2), len(t))
    env = np.sin(np.pi * t / d) ** 2; return n * env / np.abs(n).max() * .18
sfx = np.zeros(N, np.float32)
def put(sig, t0, g=1.0):
    i = int(t0 * SR); j = min(N, i + len(sig)); sfx[i:j] += sig[:j - i] * g
put(swish(), 5.85); put(tap(), 9.3); put(pop(), 10.0); put(swish(), 16.85); put(swish(.5), 20.7, .8)
mix = music * duck[:, None] + amb + sfx[:, None]
pk = np.abs(mix).max(); mix = np.tanh(mix / pk * 1.2) / np.tanh(1.2) * .9
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
print("ok")
