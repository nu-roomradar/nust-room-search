# BGM（music5.wav）に効果音を足して audio.wav を作る。時刻は index.html の場面に合わせる
import numpy as np, wave, subprocess, sys
SR = 44100; TOTAL = 15.0; N = int(TOTAL * SR)
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", "music5.wav", "-ac", "2", "-ar", str(SR), "-f", "s16le", "-"], capture_output=True, check=True).stdout
mix = np.frombuffer(raw, np.int16).reshape(-1, 2).astype(np.float32)[:N] / 32767
mix = np.pad(mix, ((0, N - len(mix)), (0, 0)))
rng = np.random.default_rng(5)
def tt(d): return np.arange(int(d * SR)) / SR
def ff(x, lo=None, hi=None):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); g = np.ones_like(f)
    if lo: g *= 1 / (1 + (lo / np.maximum(f, 1)) ** 4)
    if hi: g *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * g, len(x))
def pop(f0=520):
    t = tt(.16); f = f0 + 900 * np.exp(-t * 30); return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 22) * .4
def tick():
    t = tt(.04); return np.sin(2 * np.pi * 3200 * t) * np.exp(-t * 160) * .3
def swish(d=.35):
    t = tt(d); n = ff(rng.standard_normal(len(t)), lo=900, hi=5000); return n * np.sin(np.pi * t / d) ** 2 / np.abs(n).max() * .2
def thud():
    t = tt(.3); return np.sin(2 * np.pi * np.cumsum(90 + 60 * np.exp(-t * 25)) / SR) * np.exp(-t * 14) * .5
def bloom():
    t = tt(.6); f = 300 + 1500 * (t / .6) ** .5; return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / .6) * .18
def put(sig, t0, g=1.0, pan=0.0):
    i = int(t0 * SR); j = min(N, i + len(sig)); mix[i:j, 0] += sig[:j - i] * g * (1 - pan); mix[i:j, 1] += sig[:j - i] * g * (1 + pan)
for k, t in enumerate((.15, .35, .55, .75)): put(pop(520 + 80 * k), t, 1, (-.3, .3)[k % 2])
for t in (2.0, 3.5, 5.5, 8.0, 10.0, 12.0): put(swish(), t - .12, .9)
for k in range(5): put(pop(700 + 60 * k), 2.15 + k * .1, .7)
for t in (3.65, 4.1, 4.55): put(tick(), t)
put(thud(), 5.0)
put(swish(.5), 5.6, .6)      # 端末が上がる
put(tick(), 6.3)            # スクロール開始のタップ
put(bloom(), 6.9); put(pop(400), 7.35, .9)
put(pop(480), 8.15); put(thud(), 9.1, .7)
put(swish(.5), 10.1, .6)    # 端末が上がる
put(bloom(), 10.7); put(pop(440), 11.1, .8)   # 表のカードが飛び出す
put(tick(), 11.3)
pk = np.abs(mix).max(); mix = np.tanh(mix / pk * 1.2) / np.tanh(1.2) * .9
with wave.open("audio.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
print("ok")
