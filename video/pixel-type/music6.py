"""cm4（文字が主役）用の BGM v2。明るいポップ（120BPM・C メジャー）。既存の曲・音源は使わず numpy だけで合成する。

場面に合わせた展開（index.html の秒数と同じ）
  0.0–2.0  イントロ: はじいた弦のアルペジオ＋パッドが少しずつ開く（Fmaj9）
  2.0–5.0  「どこ行く？」でドラムが軽く入る（G6 → Em7 → Am7）
  5.0–5.5  「いっぱい。」のスタンプで止める（ブレイク＋上昇音）
  5.5–12.0 「開くだけで、」で盛り上がる。ベルのメロディ・ベース・4つ打ち（F → G → Em7 → Am7）
  12.0–    ロゴ: Cadd9 に着地して、ベルが上がって余韻

使い方: python3 music6.py music5.wav   （mix5.py が music5.wav を読んで効果音を足す）
"""
import sys
import wave

import numpy as np

SR = 44100
TOTAL = 15.0
N = int(TOTAL * SR)
B = 0.5                      # 1拍（120BPM）
rng = np.random.default_rng(11)

dry = np.zeros((N, 2))       # そのまま
rev = np.zeros((N, 2))       # 残響に送る
duckable = np.zeros((N, 2))  # キックでへこませる（パッド・ベース・弦）


def hz(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def tt(d):
    return np.arange(int(d * SR)) / SR


def place(buf, sig, t, g=1.0, pan=0.0):
    i = int(round(t * SR))
    if i >= N or i < 0:
        return
    j = min(N, i + len(sig))
    s = sig[:j - i] * g
    buf[i:j, 0] += s * np.sqrt((1 - pan) / 2) * 1.41
    buf[i:j, 1] += s * np.sqrt((1 + pan) / 2) * 1.41


def add(sig, t, g=1.0, pan=0.0, send=0.0, duck=False):
    place(duckable if duck else dry, sig, t, g, pan)
    if send:
        place(rev, sig, t, g * send, pan)


def fft_filter(x, lo=None, hi=None, order=2):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    g = np.ones_like(f)
    if lo:
        g *= 1 / (1 + (lo / np.maximum(f, 1)) ** (2 * order))
    if hi:
        g *= 1 / (1 + (f / hi) ** (2 * order))
    return np.fft.irfft(X * g, len(x))


# ── 楽器 ─────────────────────────────────────────────
def pluck(n, dur=0.9, bright=0.55, decay=0.996):
    """Karplus-Strong（はじいた弦）。ブロック単位で計算して速くする"""
    f = hz(n)
    D = max(2, int(round(SR / f)))
    L = int(dur * SR)
    y = np.zeros(L + D + 1)
    burst = fft_filter(rng.uniform(-1, 1, D), hi=2000 + 9000 * bright, order=1)
    y[:D] = burst
    k = D
    while k < L:
        m = min(D, L - k)
        y[k:k + m] = decay * 0.5 * (y[k - D:k - D + m] + y[k - D + 1:k - D + 1 + m])
        k += m
    y = y[:L]
    env = np.minimum(1, np.arange(L) / (0.002 * SR))
    tail = np.ones(L)
    r = int(0.08 * SR)
    tail[-r:] = np.linspace(1, 0, r)
    return y * env * tail / (np.abs(y).max() + 1e-9)


def bell(n, dur=1.6):
    """マリンバ寄りのベル（モード合成）"""
    t = tt(dur)
    f = hz(n)
    s = (np.sin(2 * np.pi * f * t) * np.exp(-t * 3.0)
         + 0.42 * np.sin(2 * np.pi * f * 3.93 * t) * np.exp(-t * 9)
         + 0.16 * np.sin(2 * np.pi * f * 9.2 * t) * np.exp(-t * 22)
         + 0.25 * np.sin(2 * np.pi * f * 2.0 * t) * np.exp(-t * 5))
    return s * np.minimum(1, t / 0.0015)


def saw_voice(f, t, fc):
    s = np.zeros_like(t)
    k = 1
    while f * k < min(9000, SR / 2 - 500) and k < 60:
        a = (1 / k) / (1 + (f * k / fc) ** 2)
        s += a * np.sin(2 * np.pi * f * k * t + rng.uniform(0, 2 * np.pi))
        k += 1
    return s


def pad(notes, dur, fc=1800, att=0.25, rel=0.5):
    t = tt(dur + rel)
    s = np.zeros_like(t)
    for n in notes:
        for det in (-0.12, 0.0, 0.11):
            s += saw_voice(hz(n) * 2 ** (det / 12), t, fc)
    env = np.minimum(1, t / att) * np.where(t > dur, np.exp(-(t - dur) * 6), 1)
    return fft_filter(s * env / (len(notes) * 3), lo=170)   # 低音はベースに任せる


def bass(n, dur):
    t = tt(dur)
    f = hz(n)
    s = np.sin(2 * np.pi * f * t) + 0.45 * np.sin(2 * np.pi * 2 * f * t) + 0.15 * np.sin(2 * np.pi * 3 * f * t)
    s = np.tanh(1.6 * s) / np.tanh(1.6)
    env = np.minimum(1, t / 0.005) * np.exp(-t * 2.2) * np.minimum(1, (dur - t) / 0.02)
    return s * env


def kick():
    t = tt(0.42)
    ph = 2 * np.pi * np.cumsum(46 + 125 * np.exp(-t * 32)) / SR
    body = np.sin(ph) * np.exp(-t * 7.5)
    click = fft_filter(rng.standard_normal(len(t)), lo=1500, hi=6000) * np.exp(-t * 250) * 0.35
    return np.tanh(1.4 * (body + click))


def clap():
    L = int(0.35 * SR)
    s = np.zeros(L)
    for k, off in enumerate((0, 0.008, 0.017, 0.027)):
        t = tt(0.35 - off)
        i = int(off * SR)
        s[i:i + len(t)] += rng.standard_normal(len(t)) * np.exp(-t * (90 if k < 3 else 11))
    t = tt(0.35)
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * 0.4
    return fft_filter(s, lo=900, hi=7000) * 0.8 + body


def hat(open_=False):
    t = tt(0.22 if open_ else 0.05)
    return fft_filter(rng.standard_normal(len(t)), lo=7500, order=3) * np.exp(-t * (14 if open_ else 85))


def snap():
    t = tt(0.06)
    return fft_filter(rng.standard_normal(len(t)), lo=1800, hi=5500) * np.exp(-t * 110)


def crash():
    t = tt(2.4)
    return fft_filter(rng.standard_normal(len(t)), lo=3500, order=2) * np.exp(-t * 1.9)


def riser(d):
    t = tt(d)
    n = rng.standard_normal(len(t))
    out = np.zeros_like(n)
    seg = 8
    for k in range(seg):                       # 帯域を少しずつ上げる
        a, b = int(k * len(t) / seg), int((k + 1) * len(t) / seg)
        out[a:b] = fft_filter(n[a:b], lo=400 * 1.35 ** k, hi=2500 * 1.3 ** k)
    return out * (t / d) ** 2.2


def snare_roll(t0, d, n=12):
    for k in range(n):
        x = k / n
        add(clap(), t0 + x * d, 0.12 + 0.35 * x, pan=0.1, send=0.2)


# ── 和音とメロディ ─────────────────────────────────────
CH = {
    "Fmaj9": (41, [53, 57, 60, 64, 67]), "G6": (43, [55, 59, 62, 64]), "Em7": (40, [52, 55, 59, 62]),
    "Am7": (45, [57, 60, 64, 67]), "F": (41, [53, 57, 60, 65]), "G": (43, [55, 59, 62, 67]),
    "Cadd9": (36, [60, 64, 67, 74]),
}
# (開始秒, 長さ, 和音)
PROG = [(0.0, 2.0, "Fmaj9"), (2.0, 1.5, "G6"), (3.5, 0.75, "Em7"), (4.25, 0.75, "Am7"),
        (5.5, 2.5, "F"), (8.0, 2.0, "G"), (10.0, 1.0, "Em7"), (11.0, 1.0, "Am7")]

# イントロ: パッドの明るさを少しずつ上げる（4つに分けて重ねる）
for k in range(4):
    p = pad(CH["Fmaj9"][1], 0.5, fc=500 + 450 * k, att=0.08 if k else 0.4, rel=0.25)
    add(p, k * 0.5, 0.42, send=0.35, duck=True)
for t0, d, name in PROG[1:]:
    add(pad(CH[name][1], d, fc=2200 if t0 >= 5.5 else 1500, att=0.06), t0, 0.40 if t0 >= 5.5 else 0.34, send=0.3, duck=True)

# はじいた弦: イントロのアルペジオと、前半の跳ねるリズム
arp = [65, 69, 72, 79, 76, 72, 69, 72]
for i, n in enumerate(arp):
    add(pluck(n, 0.8, 0.45), 0.0 + i * B / 2, 0.34, pan=-0.35 if i % 2 else 0.35, send=0.35, duck=True)
for t0, d, name in PROG[1:4]:
    tones = CH[name][1]
    steps = int(round(d / (B / 2)))
    for i in range(steps):
        n = tones[[0, 2, 1, 3, 2, 3, 1, 2][i % 8] % len(tones)] + 12
        add(pluck(n, 0.5, 0.6), t0 + i * B / 2, 0.30 if i % 2 == 0 else 0.20, pan=(-0.3, 0.3)[i % 2], send=0.3, duck=True)
for t0, d, name in PROG[4:]:
    tones = CH[name][1]
    for i in range(int(round(d / (B / 2)))):
        if i % 4 in (1, 3):                    # 裏拍だけ軽く
            add(pluck(tones[(i // 2) % len(tones)] + 12, 0.35, 0.7), t0 + i * B / 2, 0.16, pan=(-0.45, 0.45)[(i // 2) % 2], send=0.25, duck=True)

# ベル（メロディ）。5.5 秒からの盛り上がりで鳴らす。拍は 6.0 秒から
MEL = [  # (6.0 からの拍, ノート, 長さ拍)
    (0, 81, .5), (.5, 79, .5), (1, 76, .5), (1.5, 79, .5), (2.5, 81, .5), (3, 84, 1),
    (4, 86, .5), (4.5, 83, .5), (5, 79, .5), (6, 81, .5), (6.5, 83, .5), (7, 86, 1),
    (8, 83, .5), (8.5, 79, .5), (9, 76, .5), (9.5, 79, .5), (10, 84, .5), (10.5, 81, .5), (11, 76, .5), (11.5, 79, .5)]
add(bell(76, 1.0), 5.5, 0.30, pan=0.15, send=0.4)          # 盛り上がりの頭
for b_, n, ln in MEL:
    add(bell(n, 0.4 + ln), 6.0 + b_ * B, 0.30, pan=0.15, send=0.35)
    add(bell(n + 12, 0.35), 6.0 + b_ * B + 0.012, 0.06, pan=-0.3, send=0.4)   # 1オクターブ上をほんの少し
# 前半のちょっとした合いの手
for b_, n in ((0.5, 79), (1, 83), (1.5, 86)):
    add(bell(n, 0.8), 2.5 + b_ * B, 0.14, pan=0.3, send=0.45)

# ベース
for t0, d, name in PROG[1:]:
    root = CH[name][0]
    if t0 < 5.5:
        pat = [(0, .45, 0), (1.5, .4, 0)]
    else:
        pat = [(0, .4, 0), (.75, .2, 12), (1.5, .4, 0), (2, .4, 0), (2.75, .2, 12), (3.5, .4, 7)]
    for b_, ln, iv in pat:
        if b_ * B < d - 0.01:
            add(bass(root + iv, ln * B * 2), t0 + b_ * B, 0.40, send=0.02, duck=True)

# ドラム
kicks = []
for q in range(4, 10):                         # 2.0–5.0: 軽く（1・3拍のキック、2・4拍の指パッチン）
    tq = q * B
    if q % 2 == 0:
        add(kick(), tq, 0.65); kicks.append(tq)
    else:
        add(snap(), tq, 0.35, pan=-0.2, send=0.3)
    add(hat(), tq + B / 2, 0.08, pan=0.4)
for k in range(4):                             # 0〜2秒: 指パッチンだけ
    add(snap(), 0.5 + k * B, 0.22, pan=-0.25, send=0.35)
add(riser(0.9), 4.6, 0.20, send=0.3)           # ブレイクに向けて
q = 11
while q * B < 12.0 - 1e-6:                     # 5.5–12.0: 4つ打ち
    tq = q * B
    add(kick(), tq, 0.95); kicks.append(tq)
    if q % 2 == 0 and tq < 11.5:
        add(clap(), tq, 0.42, pan=0.05, send=0.25)
    for s16 in range(4):
        sw = 0.018 if s16 % 2 else 0.0         # 少し跳ねさせる
        add(hat(open_=(s16 == 2)), tq + s16 * B / 4 + sw, 0.10 if s16 == 2 else 0.06, pan=0.35)
    q += 1
add(crash(), 5.5, 0.26, send=0.3)
snare_roll(11.5, 0.5)

# 締め（12秒）: Cadd9 に着地 → ベルが上がる → 余韻
add(kick(), 12.0, 1.0); kicks.append(12.0)
add(crash(), 12.0, 0.22, send=0.35)
add(pad(CH["Cadd9"][1], 2.2, fc=2600, att=0.02, rel=1.2), 12.0, 0.46, send=0.5)
add(bass(36, 1.6), 12.0, 0.6)
for i, n in enumerate([72, 76, 79, 84, 86, 88]):
    add(bell(n, 1.8), 12.12 + i * 0.085, 0.22, pan=(-0.3, 0.3)[i % 2], send=0.5)
for i, n in enumerate([84, 79, 76, 72]):
    add(pluck(n, 1.4, 0.4), 13.0 + i * 0.25, 0.14, pan=(-0.4, 0.4)[i % 2], send=0.5)

# ── ミックス ───────────────────────────────────────────
duck = np.ones(N)
for k in kicks:                                # キックのたびにパッド・ベース・弦を少し下げる
    i = int(k * SR)
    L_ = min(N - i, int(0.32 * SR))
    t = np.arange(L_) / SR
    duck[i:i + L_] = np.minimum(duck[i:i + L_], 1 - 0.38 * np.exp(-t * 11))
mix = dry + duckable * duck[:, None]


def conv(x, h):
    n = len(x) + len(h)
    F = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, F) * np.fft.rfft(h, F), F)[:len(x)]


ir_t = tt(1.9)
for c in range(2):                             # 左右で少し違う残響
    ir = fft_filter(np.random.default_rng(40 + c).standard_normal(len(ir_t)), lo=250, hi=7000) * np.exp(-ir_t * 3.2)
    ir[:int(0.012 * SR)] = 0                   # 少し遅らせて奥行きを出す
    ir /= np.sqrt(np.sum(ir ** 2))
    mix[:, c] += conv(rev[:, c] + 0.15 * duckable[:, c] * duck, ir) * 0.55

# 低域を少し締め、高域を少し上げる
for c in range(2):
    x = mix[:, c]
    low = fft_filter(x, hi=120, order=2)
    high = fft_filter(x, lo=6000, order=1)
    mix[:, c] = x - 0.3 * low + 0.15 * high

# コンプ（ゆっくり）＋リミッター
env = np.sqrt(np.convolve((mix ** 2).mean(1), np.ones(2205) / 2205, mode="same")) + 1e-6
gain = np.minimum(1, (0.22 / env) ** 0.22)
mix *= gain[:, None]
fade = np.ones(N)
k = int(1.4 * SR)
fade[-k:] = np.linspace(1, 0, k) ** 1.5
mix *= fade[:, None]
mix /= np.abs(mix).max()
mix = np.tanh(mix * 1.1) / np.tanh(1.1) * 0.9

with wave.open(sys.argv[1] if len(sys.argv) > 1 else "music5.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype(np.int16).tobytes())
print("ok")
