# CM3（Pixel 風）の陽気な BGM。120BPM・D メジャー。ウクレレ風のストローク、手拍子、グロッケンのメロディ
# 自作の合成音だけで作る（既存の曲・音源は使わない）。使い方: python3 music3.py out.wav
import numpy as np, wave, sys
SR = 44100; BPM = 120; B = 60 / BPM; BAR = 4 * B
TOTAL = 25.0; N = int(TOTAL * SR)
L = np.zeros(N); R = np.zeros(N); rng = np.random.default_rng(21)
def hz(n): return 440.0 * 2 ** ((n - 69) / 12)
def add(sig, t, g=1.0, pan=0.0):
    i = int(round(t * SR)); j = min(N, i + len(sig))
    if 0 <= i < N: L[i:j] += sig[:j-i] * g * (1 - pan); R[i:j] += sig[:j-i] * g * (1 + pan)
def ff(x, lo=None, hi=None):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); gg = np.ones_like(f)
    if lo: gg *= 1 / (1 + (lo / np.maximum(f, 1)) ** 4)
    if hi: gg *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * gg, len(x))
def tt(d): return np.arange(int(d * SR)) / SR

def uke(n, d=0.5, bright=1.0):          # ナイロン弦の短い減衰
    t = tt(d + .3); f = hz(n); s = np.zeros_like(t)
    for k in range(1, 9):
        s += (1 / k ** 1.4) * np.sin(2 * np.pi * f * k * t) * np.exp(-t * (6 + k * 4.5 / bright))
    return s * np.minimum(1, t / .003)
def strum(notes, t0, down=True, g=1.0):
    order = notes if down else notes[::-1]
    for i, n in enumerate(order): add(uke(n, .45, 1.1 if down else .8), t0 + i * .012, g * (1 if down else .7), pan=-.2)
def glock(n, d=1.2):
    t = tt(d); f = hz(n)
    s = np.sin(2*np.pi*f*t)*np.exp(-t*3.2) + .35*np.sin(2*np.pi*2.76*f*t)*np.exp(-t*7) + .15*np.sin(2*np.pi*5.4*f*t)*np.exp(-t*12)
    return s * np.minimum(1, t / .002)
def bass(n, d):
    t = tt(d); f = hz(n)
    s = np.sin(2*np.pi*f*t) + .35*np.sin(2*np.pi*2*f*t) + .1*np.sin(2*np.pi*3*f*t)
    return s * np.minimum(1, t/.008) * np.exp(-t * 3) * np.minimum(1, (d - t) / .02)
def kick():
    t = tt(.32); ph = 2*np.pi*np.cumsum(50 + 120*np.exp(-t*30)) / SR
    return np.sin(ph) * np.exp(-t * 9)
def clap():
    Ls = int(.22 * SR); s = np.zeros(Ls)
    for k, off in enumerate((0, .009, .018, .03)):
        t = tt(.22 - off); i = int(off * SR); s[i:i+len(t)] += rng.standard_normal(len(t)) * np.exp(-t * (70 if k < 3 else 14))
    return ff(s, lo=1000, hi=6000)
def shaker(acc=1.0):
    t = tt(.07); return ff(rng.standard_normal(len(t)), lo=6000) * np.exp(-t * 55) * acc
def snap():
    t = tt(.05); return ff(rng.standard_normal(len(t)), lo=2500, hi=9000) * np.exp(-t * 120)
def ping(f=1760):
    t = tt(.8); return np.sin(2*np.pi*f*t) * np.exp(-t * 6) * np.minimum(1, t/.002)
def crash():
    t = tt(2.0); return ff(rng.standard_normal(len(t)), lo=4000) * np.exp(-t * 2.2)
def riser(d):
    t = tt(d); return ff(rng.standard_normal(len(t)), lo=1500, hi=9000) * (t / d) ** 2.5

# D メジャーの I–V–vi–IV（1小節＝2秒）
CH = {"D": (38, [62, 66, 69, 74]), "A": (33, [61, 64, 69, 73]), "Bm": (35, [62, 66, 71, 74]), "G": (31, [62, 67, 71, 74])}
prog = ["D", "A", "Bm", "G"]
STRUM = [(0, True), (1, True), (1.5, False), (2.5, False), (3, True), (3.5, False)]   # 島っぽいストローク
mel = [  # (拍, ノート, 長さ) 2小節で1フレーズ
    (0, 78, .5), (.5, 81, .5), (1, 83, .5), (2, 81, .5), (2.5, 78, .5), (3, 76, 1),
    (4, 74, .5), (4.5, 76, .5), (5, 78, .5), (6, 81, .5), (6.5, 78, .5), (7, 76, 1)]
mel2 = [(0, 83, .5), (.5, 86, .5), (1, 85, .5), (1.5, 83, .5), (2, 81, 1), (3, 78, .5), (3.5, 81, .5),
        (4, 83, .5), (5, 81, .5), (5.5, 78, .5), (6, 76, .5), (6.5, 78, .5), (7, 74, 1)]
END = 21.0
bars = int(END / BAR)                       # 0〜21秒: 10.5小節
for b in range(bars + 1):
    t0 = b * BAR
    if t0 >= END: break
    name = prog[b % 4]; root, notes = CH[name]
    for beat, down in STRUM:
        if t0 + beat * B < END: strum(notes, t0 + beat * B, down, .32 if b > 0 else .26)
    if b >= 1:                                # 2秒から全部入る
        for q in range(4):
            tq = t0 + q * B
            if tq >= END: break
            if q in (0, 2): add(kick(), tq, .9)
            if q == 2 and b % 2 == 1: add(kick(), tq + B / 2, .55)
            if q in (1, 3): add(clap(), tq, .38, pan=.1)
            for s16 in range(4): add(shaker(1 if s16 % 2 else .6), tq + s16 * B / 4, .09, pan=.35)
        for bt, ln in ((0, .45), (1.5, .4), (2, .45), (3.5, .4)):
            if t0 + bt * B < END: add(bass(root + (12 if bt == 1.5 else 0), ln), t0 + bt * B, .5)
    else:
        for q in range(4): add(snap(), t0 + q * B + B, .25, pan=-.3)   # 0〜2秒: 指パッチンだけ
    if b >= 3:                                # 6秒からメロディ
        phrase = mel if (b // 2) % 2 == 1 else mel2
        off = (b % 2) * 4
        for bt, n, ln in phrase:
            if off <= bt < off + 4 and t0 + (bt - off) * B < END - .05:
                add(glock(n, 1.0), t0 + (bt - off) * B, .2, pan=.25)
add(riser(1.5), END - 1.5, .22)
for k in range(8): add(snap(), END - 1.0 + k * B / 4, .12 + k * .02)        # 盛り上げの細かい手拍子
# 締め: ジャーン → グロッケンの上昇 → 和音を伸ばす。ロゴの「ピン」に合わせて音を置く
add(kick(), END, 1.0); add(crash(), END, .2); add(bass(38, 1.8), END, .6)
for n in [62, 66, 69, 74, 78]: add(uke(n, 2.0, 1.4), END + .01 * (n - 62) / 4, .3)
for i, n in enumerate([74, 78, 81, 86, 90]): add(glock(n, 1.6), END + .25 + i * .09, .22, pan=.2)
t = tt(3.6)
pad = sum(np.sin(2*np.pi*hz(n)*t) for n in (62, 66, 69, 74)) * np.minimum(1, t/.3) * np.exp(-t * .7) / 4
add(pad, END, .22)
for tp, f in ((21.75, 1760), (22.55, 2093)): add(ping(f), tp, .12, pan=-.1); add(ping(f), tp + .18, .05, pan=.3)
# 軽いサイドチェイン、フェードアウト、ノーマライズ
fade = np.ones(N); k = int(1.6 * SR); fade[-k:] = np.linspace(1, 0, k) ** 1.6
L *= fade; R *= fade
pk = max(np.abs(L).max(), np.abs(R).max())
L = np.tanh(L / pk * 1.3) / np.tanh(1.3) * .89; R = np.tanh(R / pk * 1.3) / np.tanh(1.3) * .89
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.stack([L, R], 1) * 32767).astype(np.int16).tobytes())
print("ok")
