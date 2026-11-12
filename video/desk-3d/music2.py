"""3D 広告その2「ポスターとドア」の音（自作。既存の曲は使わない）。door.js の T と同じ時刻に合わせてある。
  python3 music2.py  →  renders/audio2_raw.wav（48kHz・ステレオ・27秒）"""
import os, wave
import numpy as np
SR, DUR = 48000, 27.0
N = int(SR * DUR); rng = np.random.default_rng(11)
L = np.zeros(N); R = np.zeros(N)
def hz(note):
    names = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
    return 440.0 * 2 ** ((names[note[:-1]] + (int(note[-1]) - 4) * 12 - 9) / 12)
def add(sig, t0, pan=0.0, gain=1.0):
    i0 = int(t0 * SR); n = min(len(sig), N - i0)
    if n <= 0 or i0 < 0: return
    a = np.sqrt((1 - pan) / 2); b = np.sqrt((1 + pan) / 2)
    L[i0:i0 + n] += sig[:n] * gain * a; R[i0:i0 + n] += sig[:n] * gain * b
def env(n, a, r):
    e = np.ones(n); na, nr = int(a * SR), int(r * SR)
    e[:na] = 0.5 - 0.5 * np.cos(np.pi * np.arange(na) / na); e[n - nr:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(nr) / nr); return e
def pad(notes, t0, t1, gain=1.0):
    n = int((t1 - t0 + 1.6) * SR); tt = np.arange(n) / SR; s = np.zeros(n)
    for nt in notes:
        f = hz(nt)
        for det, g in ((-0.35, 0.5), (0.0, 0.7), (0.4, 0.5)):
            ff = f * 2 ** (det / 1200 * 8); ph = rng.uniform(0, 6.28)
            s += g * (np.sin(2 * np.pi * ff * tt + ph) + 0.22 * np.sin(2 * np.pi * 2 * ff * tt + ph * 1.7) + 0.06 * np.sin(2 * np.pi * 3 * ff * tt)) / len(notes)
    s *= env(n, 1.4, 1.6) * (1 + 0.06 * np.sin(2 * np.pi * 0.17 * tt)); add(s, max(0, t0 - 0.2), 0.0, 0.085 * gain)
def bell(note, t0, dur=2.4, gain=1.0, pan=0.0, bright=1.0):
    n = int(dur * SR); tt = np.arange(n) / SR; f = hz(note)
    s = (np.sin(2 * np.pi * f * tt) * np.exp(-tt / (dur * 0.30)) + 0.42 * bright * np.sin(2 * np.pi * 2.0 * f * tt) * np.exp(-tt / (dur * 0.16))
         + 0.16 * bright * np.sin(2 * np.pi * 3.01 * f * tt) * np.exp(-tt / (dur * 0.09)))
    s *= np.minimum(1, tt / 0.004); add(s, t0, pan, 0.10 * gain)
def piano(note, t0, dur=3.2, gain=1.0, pan=0.0):
    n = int(dur * SR); tt = np.arange(n) / SR; f = hz(note); s = np.zeros(n)
    for h in range(1, 9): s += np.sin(2 * np.pi * f * h * tt) * np.exp(-tt * (1.1 + 0.55 * h)) / (h ** 1.5)
    s *= np.minimum(1, tt / 0.006); add(s, t0, pan, 0.16 * gain)
def swell(t0, dur=0.9, gain=1.0, pan=0.0, lo=900, hi=5200):
    n = int(dur * SR); x = rng.standard_normal(n); X = np.fft.rfft(x); fr = np.fft.rfftfreq(n, 1 / SR)
    X *= np.exp(-((np.log(fr + 1) - np.log((lo * hi) ** 0.5)) / 0.7) ** 2); x = np.fft.irfft(X, n); x /= np.abs(x).max() + 1e-9
    tt = np.arange(n) / dur / SR; add(x * np.sin(np.pi * tt) ** 2, t0, pan, 0.028 * gain)
def tick(t0, gain=1.0, pan=0.0, f=2400, d=0.004):
    n = int(0.04 * SR); tt = np.arange(n) / SR; add(np.sin(2 * np.pi * f * tt) * np.exp(-tt / d), t0, pan, 0.05 * gain)
def thud(t0, gain=1.0, pan=0.0, f=70, d=0.09):                 # 足音・ドア（低い音。雑音を少し混ぜる）
    n = int(0.5 * SR); tt = np.arange(n) / SR
    s = np.sin(2 * np.pi * (f + 40 * np.exp(-tt / 0.02)) * tt) * np.exp(-tt / d) + 0.25 * rng.standard_normal(n) * np.exp(-tt / 0.012)
    add(s, t0, pan, 0.07 * gain)

pad(["D3", "A3", "E4", "F#4"], 0.0, 6.6); pad(["B2", "F#3", "A3", "D4"], 6.6, 13.2); pad(["G2", "D3", "F#3", "B3"], 13.2, 19.6, 1.05); pad(["D3", "A3", "D4", "F#4", "A4"], 19.6, 27.0, 1.15)
for nt, t0 in (("D2", 0.2), ("B1", 6.7), ("G1", 13.3), ("D2", 19.9)): piano(nt, t0, 5.0, 0.55)
bell("F#5", 0.8, 2.6, 0.5, -0.1); bell("A5", 2.2, 2.6, 0.45, 0.15)
swell(3.3, 1.0, 1.0, 0.0, 500, 3000)                                                              # スマホを構える
tick(5.0, 1.3, 0.0, 1976, 0.02); tick(5.09, 1.2, 0.0, 2637, 0.03); bell("B5", 5.0, 2.4, 0.9); swell(5.0, 1.2, 1.2)   # QR を読み取った
tick(6.05, 0.9, 0.1, 1500); swell(6.2, 0.6, 0.9, 0.0, 1200, 6000); bell("D5", 6.7, 2.6, 0.6)       # 開く → 一覧
bell("F#5", 10.0, 2.2, 0.9, 0.15); bell("A5", 10.0, 2.2, 0.55, 0.15); bell("D6", 10.95, 1.8, 0.5, 0.2)   # 空いてる教室、あった
swell(12.8, 0.9, 0.9, 0.0, 500, 3000)
k = 0
for t0 in np.arange(13.9, 18.3, 0.263):                                                           # 3人の足音（軽く）
    thud(float(t0) + rng.uniform(-0.03, 0.03), 0.30 + 0.10 * rng.random(), (-0.35, 0.3, 0.0)[k % 3], 95 + 12 * (k % 3), 0.035); k += 1
swell(18.55, 0.8, 0.9, 0.2, 300, 1800)                                                            # ドアが動く
thud(19.33, 2.2, 0.15, 62, 0.11); tick(19.36, 1.0, 0.2, 900, 0.01)                                # 閉まる
bell("D5", 20.45, 4.2, 1.1); bell("A5", 20.45, 4.2, 0.7, 0.2); bell("F#6", 20.6, 3.6, 0.35, -0.2); swell(20.45, 1.4, 1.4)   # ロゴ
piano("D3", 20.45, 5.0, 0.7); piano("A3", 20.51, 5.0, 0.5, 0.2); piano("F#4", 20.57, 5.0, 0.5, -0.2); bell("D6", 21.4, 3.4, 0.3, 0.1)

def reverb(x, seed):
    n = int(2.4 * SR); r = np.random.default_rng(seed); ir = r.standard_normal(n) * np.exp(-np.arange(n) / (0.55 * SR)); ir[: int(0.012 * SR)] = 0
    IR = np.fft.rfft(ir, N + n); IR *= 1 / (1 + (np.fft.rfftfreq(N + n, 1 / SR) / 5200) ** 2)
    return np.fft.irfft(np.fft.rfft(x, N + n) * IR, N + n)[:N] * 0.012
wl, wr = reverb(L, 1) + 0.3 * reverb(R, 3), reverb(R, 2) + 0.3 * reverb(L, 4)
L, R = L + wl, R + wr
fade = np.ones(N); nf = int(1.6 * SR); fade[-nf:] = 0.5 + 0.5 * np.cos(np.pi * np.arange(nf) / nf); fade[: int(0.05 * SR)] = np.linspace(0, 1, int(0.05 * SR))
st = np.stack([L, R], 1) * fade[:, None]; st = st / (np.abs(st).max() + 1e-9) * 0.7
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "renders", "audio2_raw.wav")
with wave.open(out, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype("<i2").tobytes())
print("書き出し", out)
