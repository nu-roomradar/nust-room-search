"""3D 広告の音（自作。既存の曲は使わない）。静かなパッドと、レーダーの輪に合わせた小さな鐘の音。
  python3 music.py  →  renders/audio.wav（48kHz・ステレオ・30秒）。時刻は scene.js の T に合わせてある。
音程は平均律の周波数をそのまま足し算で鳴らす（弦の物理モデルは使わない。音程がずれるため）。"""
import os, wave
import numpy as np
SR, DUR = 48000, 30.0
N = int(SR * DUR); t = np.arange(N) / SR
rng = np.random.default_rng(7)
L = np.zeros(N); R = np.zeros(N)
def hz(note):                      # 例 "D4" "F#5"
    names = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
    return 440.0 * 2 ** ((names[note[:-1]] + (int(note[-1]) - 4) * 12 - 9) / 12)
def add(sig, t0, pan=0.0, gain=1.0):
    i0 = int(t0 * SR); n = min(len(sig), N - i0)
    if n <= 0: return
    a = np.sqrt((1 - pan) / 2); b = np.sqrt((1 + pan) / 2)
    L[i0:i0 + n] += sig[:n] * gain * a; R[i0:i0 + n] += sig[:n] * gain * b
def env(n, a, r):                  # ゆっくり立ち上がり、ゆっくり消える
    e = np.ones(n); na, nr = int(a * SR), int(r * SR)
    e[:na] = 0.5 - 0.5 * np.cos(np.pi * np.arange(na) / na); e[n - nr:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(nr) / nr); return e
def pad(notes, t0, t1, gain=1.0):  # やわらかい和音
    n = int((t1 - t0 + 1.6) * SR); tt = np.arange(n) / SR; s = np.zeros(n)
    for k, nt in enumerate(notes):
        f = hz(nt)
        for det, g in ((-0.35, 0.5), (0.0, 0.7), (0.4, 0.5)):
            ff = f * 2 ** (det / 1200 * 8); ph = rng.uniform(0, 6.28)
            s += g * (np.sin(2 * np.pi * ff * tt + ph) + 0.22 * np.sin(2 * np.pi * 2 * ff * tt + ph * 1.7) + 0.06 * np.sin(2 * np.pi * 3 * ff * tt)) / len(notes)
    s *= env(n, 1.4, 1.6) * (1 + 0.06 * np.sin(2 * np.pi * 0.17 * tt))
    add(s, max(0, t0 - 0.2), 0.0, 0.085 * gain)
def bell(note, t0, dur=2.4, gain=1.0, pan=0.0, bright=1.0):   # 輪に合わせる小さな鐘
    n = int(dur * SR); tt = np.arange(n) / SR; f = hz(note)
    s = (np.sin(2 * np.pi * f * tt) * np.exp(-tt / (dur * 0.30)) + 0.42 * bright * np.sin(2 * np.pi * 2.0 * f * tt) * np.exp(-tt / (dur * 0.16))
         + 0.16 * bright * np.sin(2 * np.pi * 3.01 * f * tt) * np.exp(-tt / (dur * 0.09)) + 0.07 * np.sin(2 * np.pi * 4.2 * f * tt) * np.exp(-tt / (dur * 0.05)))
    s *= np.minimum(1, tt / 0.004)
    add(s, t0, pan, 0.10 * gain)
def piano(note, t0, dur=3.2, gain=1.0, pan=0.0):              # 低いやわらかい音
    n = int(dur * SR); tt = np.arange(n) / SR; f = hz(note); s = np.zeros(n)
    for h in range(1, 9): s += np.sin(2 * np.pi * f * h * tt) * np.exp(-tt * (1.1 + 0.55 * h)) / (h ** 1.5)
    s *= np.minimum(1, tt / 0.006); add(s, t0, pan, 0.16 * gain)
def swell(t0, dur=0.9, gain=1.0, pan=0.0, lo=900, hi=5200):   # 輪が広がる気配（絞った雑音）
    n = int(dur * SR); x = rng.standard_normal(n); X = np.fft.rfft(x); fr = np.fft.rfftfreq(n, 1 / SR)
    X *= np.exp(-((np.log(fr + 1) - np.log((lo * hi) ** 0.5)) / 0.7) ** 2); x = np.fft.irfft(X, n); x /= np.abs(x).max() + 1e-9
    tt = np.arange(n) / dur / SR; add(x * np.sin(np.pi * tt) ** 2, t0, pan, 0.028 * gain)
def tick(t0, gain=1.0, pan=0.2, f=2400):
    n = int(0.03 * SR); tt = np.arange(n) / SR; add(np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.004), t0, pan, 0.05 * gain)

# 和音（場面に合わせてゆっくり変わる。ニ長調）
pad(["D3", "A3", "E4", "F#4"], 0.0, 8.0); pad(["B2", "F#3", "A3", "D4"], 8.0, 16.4); pad(["G2", "D3", "F#3", "B3"], 16.4, 20.4)
pad(["A2", "E3", "A3", "C#4"], 20.4, 24.4, 1.05); pad(["D3", "A3", "D4", "F#4", "A4"], 24.4, 30.0, 1.15)
for nt, t0 in (("D2", 0.2), ("B1", 8.1), ("G1", 16.5), ("A1", 20.5), ("D2", 24.5)): piano(nt, t0, 5.0, 0.55)

# レーダーの輪（scene.js の T と同じ時刻）
for nt, t0, g in (("F#5", 0.6, 0.9), ("A5", 1.5, 0.75), ("E5", 2.4, 0.75)): bell(nt, t0, 2.6, g, -0.15); swell(t0, 1.0, 0.9)
bell("D5", 3.3, 3.0, 1.0); bell("A5", 3.3, 3.0, 0.6, 0.2); swell(3.3, 1.3, 1.3)
for k, dt in enumerate((0.25, 0.5, 0.72, 0.95, 1.15)): bell(("F#6", "A6", "E6", "D6", "B5")[k], 3.3 + dt, 1.2, 0.22, (-0.5, 0.4, -0.2, 0.5, 0.0)[k], 0.6)   # 空きコマが順に光る
bell("B5", 8.0, 2.6, 0.9); swell(8.0, 1.0, 1.1); piano("D4", 9.15, 2.4, 0.35, -0.1)                                                                     # スマホへ
tick(12.5, 0.9, -0.1, 1800); tick(13.75, 1.0, 0.0, 1500)                                                                                               # 押す
bell("A5", 15.05, 1.6, 0.6, 0.15); bell("F#5", 15.95, 2.0, 0.7, 0.15); bell("D5", 15.95, 2.0, 0.45, 0.15)                                              # 印が1つ、2つ
bell("E5", 16.5, 2.4, 0.8, 0.2); swell(16.5, 1.0, 1.0, 0.2)                                                                                            # 時計へ
for k in range(20): tick(17.2 + (18.75 - 17.2) * (k / 20) ** 0.85, 0.5 + 0.02 * k, 0.3, 2600)                                                          # 針が進む
bell("A5", 18.8, 2.8, 0.95, 0.25); bell("D6", 19.0, 2.8, 0.8, 0.1)                                                                                     # 時限の終わり
for k in range(14): bell(("D6", "F#6", "A6", "E6", "B6")[k % 5], 19.05 + rng.uniform(0, 1.1), 0.9, 0.16, rng.uniform(-0.6, 0.4), 0.5)                  # 光の粒
bell("E5", 20.25, 2.4, 0.8); swell(20.4, 1.5, 1.6, 0.0, 500, 3000)                                                                                     # 紙が起き上がる
piano("A3", 21.5, 3.4, 0.6); piano("C#4", 21.56, 3.4, 0.45, 0.2); piano("E4", 21.62, 3.4, 0.45, -0.2); bell("A5", 21.6, 2.6, 0.5)                      # 決めの言葉
bell("D5", 25.3, 4.2, 1.1); bell("A5", 25.3, 4.2, 0.7, 0.2); bell("F#6", 25.45, 3.6, 0.35, -0.2); swell(25.3, 1.4, 1.4)                                # ロゴ
piano("D3", 25.3, 5.0, 0.7); piano("A3", 25.36, 5.0, 0.5, 0.2); piano("F#4", 25.42, 5.0, 0.5, -0.2); bell("D6", 26.2, 3.4, 0.3, 0.1)

# 残響（減っていく雑音をたたみ込む）
def reverb(x, seed):
    n = int(2.4 * SR); r = np.random.default_rng(seed); ir = r.standard_normal(n) * np.exp(-np.arange(n) / (0.55 * SR)); ir[: int(0.012 * SR)] = 0
    IR = np.fft.rfft(ir, N + n); IR *= 1 / (1 + (np.fft.rfftfreq(N + n, 1 / SR) / 5200) ** 2)
    return np.fft.irfft(np.fft.rfft(x, N + n) * IR, N + n)[:N] * 0.012
wl, wr = reverb(L, 1) + 0.3 * reverb(R, 3), reverb(R, 2) + 0.3 * reverb(L, 4)
L, R = L + wl, R + wr
fade = np.ones(N); nf = int(1.6 * SR); fade[-nf:] = 0.5 + 0.5 * np.cos(np.pi * np.arange(nf) / nf); fade[: int(0.05 * SR)] = np.linspace(0, 1, int(0.05 * SR))
st = np.stack([L, R], 1) * fade[:, None]
st = st / (np.abs(st).max() + 1e-9) * 0.7
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "renders"), exist_ok=True)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "renders", "audio_raw.wav")
with wave.open(out, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype("<i2").tobytes())
print("書き出し", out, "peak", float(np.abs(st).max()))
