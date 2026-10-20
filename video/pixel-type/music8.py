"""cm4（文字が主役）用の BGM v4。なめらかなギターが主役（120BPM のハーフタイム＝ゆったり感じる）。
既存の曲・音源は使わず numpy だけで合成する。
v3（music7.py）の Karplus-Strong は音程が低めにずれ、弾き始めがノイズっぽかったので、
ギターを倍音の足し算（加算合成）で作り直した: 音程は正確、指で弾いたような柔らかい立ち上がり、高い倍音ほど早く消える。
メロディはスライド（音の間を滑らせる）とゆるいビブラートでつなぐ。

展開（index.html の秒数と同じ。1小節＝2秒）
  0–2   Cmaj7  指弾きだけで始まる
  2–4   Fmaj7  シェイカーと柔らかいベースが入る
  4–6   Am7    5.0 のスタンプでいったん間をあけ、5.5 で上へのかき鳴らし
  6–8   Fmaj7  かき鳴らしのギターと、軽いキック・リムが入る。6.0 からギターのメロディ
  8–10  G6
  10–12 Em7 → Am7
  12–   Cmaj9  ゆっくりかき鳴らして、ハーモニクスで余韻

使い方: python3 music8.py music5.wav   （mix5.py が music5.wav を読んで効果音を足し、-14 LUFS にそろえる）
"""
import sys
import wave

import numpy as np

SR = 44100
TOTAL = 15.0
N = int(TOTAL * SR)
B = 0.5
rng = np.random.default_rng(8)

gtr = np.zeros((N, 2))     # ギター（あとで胴鳴りを付ける）
dry = np.zeros((N, 2))     # ベース・打楽器
rev = np.zeros((N, 2))     # 残響に送る


def hz(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def tt(d):
    return np.arange(int(d * SR)) / SR


def fft_filter(x, lo=None, hi=None, order=2):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    g = np.ones_like(f)
    if lo:
        g *= 1 / (1 + (lo / np.maximum(f, 1)) ** (2 * order))
    if hi:
        g *= 1 / (1 + (f / hi) ** (2 * order))
    return np.fft.irfft(X * g, len(x))


def place(buf, sig, t, g=1.0, pan=0.0):
    i = int(round(t * SR))
    if i >= N or i < 0:
        return
    j = min(N, i + len(sig))
    s = sig[:j - i] * g
    buf[i:j, 0] += s * np.sqrt((1 - pan) / 2) * 1.41
    buf[i:j, 1] += s * np.sqrt((1 + pan) / 2) * 1.41


def add(buf, sig, t, g=1.0, pan=0.0, send=0.0, human=True):
    if human:                                   # 人が弾いたように、タイミングと強さを少しずらす
        t = max(0.0, t + rng.normal(0, 0.003))
        g *= 1 + rng.normal(0, 0.05)
    place(buf, sig, t, g, pan)
    if send:
        place(rev, sig, t, g * send, pan)


# ── ギター ───────────────────────────────────────────
def string(n, dur=2.0, bright=0.45, decay=None, pick_pos=0.14, slide_from=None, vibrato=0.0):
    """倍音を足して作るギターの1音。
    pick_pos: 弾く位置（ブリッジからの比率。小さいほど硬い音）／bright: 高い倍音の残り方
    slide_from: そのノートから滑らせて入る（半音単位、60ms）／vibrato: ビブラートの深さ（セント）"""
    t = tt(dur)
    f0 = hz(n)
    if slide_from is not None or vibrato:
        f = np.full_like(t, f0)
        if slide_from is not None:
            g = np.clip(t / 0.06, 0, 1)
            g = g * g * (3 - 2 * g)
            f = hz(slide_from) * (f0 / hz(slide_from)) ** g
        if vibrato:
            depth = np.clip((t - 0.25) / 0.3, 0, 1) * vibrato
            f = f * 2 ** (depth * np.sin(2 * np.pi * 5.2 * t) / 1200)
        base_phase = 2 * np.pi * np.cumsum(f) / SR
    else:
        base_phase = None
    s = np.zeros_like(t)
    roll = 1.75 - 0.6 * bright
    k = 1
    while k * f0 < 7500 and k <= 36:
        a = abs(np.sin(np.pi * k * pick_pos)) / k ** roll
        fk = k * f0 * np.sqrt(1 + 0.00004 * k * k)
        dk = 0.9 + 1.1 * (fk / 1000) ** 1.15          # 高い倍音ほど早く消える
        ph = rng.uniform(0, 2 * np.pi)
        if base_phase is None:
            p = 2 * np.pi * fk * t + ph
        else:
            p = base_phase * k * np.sqrt(1 + 0.00004 * k * k) + ph
        part = np.sin(p)
        if k <= 5:                                     # ほんの少しうなりを入れて温かく
            part = 0.75 * part + 0.25 * np.sin(p + 2 * np.pi * fk * 0.0009 * t)
        s += a * part * np.exp(-t * dk)
        k += 1
    att = 1 - np.exp(-t / 0.0025)                      # 指で弾いたような柔らかい立ち上がり
    s *= att
    nz = tt(0.03)                                      # 指が弦に当たる小さな音
    finger = fft_filter(rng.standard_normal(len(nz)), lo=300, hi=2500) * np.exp(-nz * 120) * 0.012
    s[:len(nz)] += finger[:len(s)]
    r = int(0.06 * SR)
    s[-r:] *= np.linspace(1, 0, r)
    return s / (np.abs(s).max() + 1e-9)


def strum(notes, t, down=True, g=0.5, spread=0.022, pan=0.0, dur=2.2, bright=0.5, send=0.25):
    order = notes if down else notes[::-1][:4]      # アップは高い弦だけ
    for i, n in enumerate(order):
        vel = g * (1.0 if down else 0.6) * (1 - 0.06 * i if down else 1)
        add(gtr, string(n, dur, bright + (0.1 if not down else 0), pick_pos=0.16), t + i * spread, vel, pan, send)


def mute_chk(t, g=0.18, pan=0.0):
    """ミュートしたかき鳴らし（チャッ）"""
    d = tt(0.05)
    s = fft_filter(rng.standard_normal(len(d)), lo=600, hi=3500) * np.exp(-d * 70)
    add(gtr, s, t, g, pan, 0.1)


def squeak(t, g=0.05):
    """コードを変えるときに指が弦をこする音"""
    d = tt(0.12)
    n = rng.standard_normal(len(d))
    s = np.zeros_like(n)
    for k in range(4):
        a, b = int(k * len(d) / 4), int((k + 1) * len(d) / 4)
        s[a:b] = fft_filter(n[a:b], lo=1400 + 500 * k, hi=3000 + 900 * k)
    add(gtr, s * np.sin(np.pi * d / 0.12), t, g, -0.2, 0.15)


def harmonic(n, dur=2.5):
    d = tt(dur)
    f = hz(n)
    s = np.sin(2 * np.pi * f * d) * np.exp(-d * 1.6) + 0.2 * np.sin(2 * np.pi * 2 * f * d) * np.exp(-d * 3)
    return s * np.minimum(1, d / 0.002)


# ── ベース・打楽器 ─────────────────────────────────────
def bass(n, dur, att=0.012):
    d = tt(dur)
    f = hz(n)
    s = np.sin(2 * np.pi * f * d) + 0.3 * np.sin(2 * np.pi * 2 * f * d) + 0.08 * np.sin(2 * np.pi * 3 * f * d)
    env = np.minimum(1, d / att) * np.exp(-d * 1.4) * np.minimum(1, (dur - d) / 0.05)
    return s * env


def kick():
    d = tt(0.35)
    ph = 2 * np.pi * np.cumsum(48 + 80 * np.exp(-d * 28)) / SR
    return np.sin(ph) * np.exp(-d * 9)


def rim():
    d = tt(0.12)
    tone = np.sin(2 * np.pi * 1700 * d) * np.exp(-d * 60) + 0.5 * np.sin(2 * np.pi * 820 * d) * np.exp(-d * 45)
    click = fft_filter(rng.standard_normal(len(d)), lo=2500) * np.exp(-d * 200) * 0.4
    return tone + click


def shaker(acc=1.0):
    d = tt(0.09)
    env = np.minimum(1, d / 0.012) * np.exp(-d * 45)
    return fft_filter(rng.standard_normal(len(d)), lo=5000, order=2) * env * acc


def swell(dur=0.9):
    d = tt(dur)
    s = fft_filter(rng.standard_normal(len(d)), lo=2500, hi=11000)
    return s * (d / dur) ** 3


# ── 和音（ギターの押さえ方に近い並び。低い弦から）──────────────
CH = {
    "Cmaj7": [48, 52, 55, 59, 64],         # C3 E3 G3 B3 E4
    "Fmaj7": [41, 48, 52, 57, 64],         # F2 C3 E3 A3 E4
    "Am7":   [45, 52, 55, 60, 64],         # A2 E3 G3 C4 E4
    "G6":    [43, 47, 50, 55, 59, 64],     # G2 B2 D3 G3 B3 E4
    "Em7":   [40, 47, 50, 55, 59, 64],     # E2 B2 D3 G3 B3 E4
    "Cmaj9": [48, 52, 55, 59, 62, 64],     # C3 E3 G3 B3 D4 E4
}
ROOT = {"Cmaj7": 36, "Fmaj7": 41, "Am7": 45, "G6": 43, "Em7": 40, "Cmaj9": 36}
BARS = [(0, "Cmaj7"), (2, "Fmaj7"), (4, "Am7"), (6, "Fmaj7"), (8, "G6"), (10, "Em7"), (11, "Am7")]

# 指弾き（3連のゆれ: 1拍を3つに分けて、低い弦→高い弦→真ん中）
TRIP = B / 3
for bi, (t0, name) in enumerate(BARS):
    d = 1.0 if name in ("Em7", "Am7") and t0 >= 10 else 2.0
    ch = CH[name]
    for beat in range(int(d / B)):
        tb = t0 + beat * B
        if 5.0 <= tb < 5.5:                     # スタンプの間はあける
            continue
        bass_note = ch[0] if beat % 2 == 0 else ch[1]
        add(gtr, string(bass_note, 1.8, 0.3, pick_pos=0.2), tb, 0.42, -0.25, 0.2)
        add(gtr, string(ch[-1], 1.4, 0.4, pick_pos=0.18), tb + TRIP, 0.22, -0.1, 0.25)
        add(gtr, string(ch[-2], 1.2, 0.4, pick_pos=0.18), tb + 2 * TRIP, 0.18, -0.15, 0.25)

# 5.5: 上へのかき鳴らしで、ふわっと持ち上げる
strum(CH["Fmaj7"], 5.5, down=False, g=0.28, spread=0.03, pan=0.3, dur=1.4, send=0.45)
add(dry, swell(0.6), 4.95, 0.10, 0.0, 0.3, human=False)

# 6.0–12.0: かき鳴らしのギター（右）。ゆったり（1・3拍のダウン、ゴーストのアップ）
for t0, name in BARS[3:]:
    d = 1.0 if t0 >= 10 else 2.0
    ch = CH[name]
    pattern = [(0.0, True, 0.34), (1.5, False, 0.16), (2.0, True, 0.28), (2.75, False, 0.14), (3.5, False, 0.18)]
    for b_, down, g in pattern:
        if b_ * B < d - 0.01:
            strum(ch, t0 + b_ * B, down, g, pan=0.45, dur=1.6, bright=0.55, send=0.2)

# ギターのメロディ（6.0 から）。スライドの代わりに半音下から素早く入る音を時々入れる
MEL = [  # (6.0 からの拍, ノート, 長さ, 半音下から入るか)
    (0, 76, 1.0, True), (1, 79, .5, False), (1.5, 81, 1.0, False), (3, 79, .75, False),
    (4, 74, 1.0, True), (5, 76, .5, False), (5.5, 79, 1.0, False), (7, 76, .75, False),
    (8, 79, .75, True), (8.75, 76, .75, False), (9.5, 74, .5, False), (10, 72, 1.5, True)]
for b_, n, ln, slide in MEL:
    t = 6.0 + b_ * B
    add(gtr, string(n, ln * B + 1.0, 0.55, pick_pos=0.2, slide_from=(n - 2 if slide else None),
                    vibrato=(14 if ln >= 1.0 else 0)), t - (0.03 if slide else 0), 0.34, 0.05, 0.42)

# ベース（2.0 から柔らかく、5.5 からはっきり）
for t0, name in BARS[1:]:
    d = 1.0 if t0 >= 10 else 2.0
    r = ROOT[name]
    if t0 < 5.5:
        add(dry, bass(r, 1.2, att=0.04), t0, 0.24, 0.0, 0.02)
    else:
        for b_, iv, ln in ((0, 0, 0.9), (1.5, 7, 0.4), (2, 0, 0.8), (3.5, 12, 0.3)):
            if b_ * B < d - 0.01:
                add(dry, bass(r + iv, ln), t0 + b_ * B, 0.32, 0.0, 0.02)

# 打楽器: シェイカー（2.0 から）、軽いキックとリム（6.0 から、ハーフタイム）
q = 4
while q * B < 12.0 - 1e-6:
    tq = q * B
    if not (5.0 <= tq < 5.5):
        add(dry, shaker(1.0), tq, 0.07, 0.4, 0.1)
        add(dry, shaker(0.6), tq + B / 2 + 0.015, 0.05, 0.4, 0.1)
    if tq >= 6.0:
        bar_beat = round((tq - 6.0) / B) % 4
        if bar_beat == 0:
            add(dry, kick(), tq, 0.55)
        if bar_beat == 2:
            add(dry, rim(), tq, 0.22, -0.1, 0.25)
        if bar_beat == 3:
            add(dry, kick(), tq + B / 2, 0.30)
    q += 1

# 12.0: Cmaj9 をゆっくりかき鳴らして、ハーモニクスで余韻
strum(CH["Cmaj9"], 12.0, down=True, g=0.40, spread=0.045, pan=0.0, dur=3.0, bright=0.5, send=0.5)
add(dry, bass(36, 2.5, att=0.02), 12.0, 0.42, 0.0, 0.05)
add(dry, kick(), 12.0, 0.45)
for i, n in enumerate([76, 79, 83, 88]):
    add(gtr, harmonic(n, 2.4), 12.35 + i * 0.22, 0.12, (-0.3, 0.3)[i % 2], 0.6)

# ── ミックス ─────────────────────────────────────────
def conv(x, h):
    n = len(x) + len(h)
    F = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, F) * np.fft.rfft(h, F), F)[:len(x)]


# ギターの胴鳴り（低めの共鳴をいくつか足した短い応答）
bt = tt(0.08)
body = np.zeros_like(bt)
body[0] = 1.0
for f, a, dk in ((105, 0.010, 45), (205, 0.008, 60), (410, 0.004, 80), (1250, 0.002, 140)):
    body += a * np.sin(2 * np.pi * f * bt) * np.exp(-bt * dk)
for c in range(2):
    gtr[:, c] = conv(gtr[:, c], body)
    gtr[:, c] = fft_filter(gtr[:, c], lo=75, hi=9000, order=1)
mix = gtr + dry

ir_t = tt(1.6)
for c in range(2):
    ir = fft_filter(np.random.default_rng(60 + c).standard_normal(len(ir_t)), lo=300, hi=6000) * np.exp(-ir_t * 3.6)
    ir[:int(0.018 * SR)] = 0
    ir /= np.sqrt(np.sum(ir ** 2))
    mix[:, c] += conv(rev[:, c], ir) * 0.5

env = np.sqrt(np.convolve((mix ** 2).mean(1), np.ones(4410) / 4410, mode="same")) + 1e-6
mix *= np.minimum(1, (0.2 / env) ** 0.18)[:, None]
fade = np.ones(N)
k = int(1.5 * SR)
fade[-k:] = np.linspace(1, 0, k) ** 1.4
mix *= fade[:, None]
mix /= np.abs(mix).max()
mix = np.tanh(mix * 1.05) / np.tanh(1.05) * 0.9

with wave.open(sys.argv[1] if len(sys.argv) > 1 else "music5.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype(np.int16).tobytes())
print("ok")
