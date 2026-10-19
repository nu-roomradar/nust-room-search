# CM2 用の静かなピアノ曲（自作・numpy 合成）。Apple の広告のような、間のある短いフレーズ
# 使い方: python3 piano.py out.wav [長さ秒]
import numpy as np, wave, sys
SR = 44100
TOTAL = float(sys.argv[2]) if len(sys.argv) > 2 else 26.0
N = int(TOTAL * SR); L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(3)
def hz(n): return 440.0 * 2 ** ((n - 69) / 12)

def piano(n, dur, vel=0.7):
    """ハンマーの当たり＋倍音ごとに減衰の違う、やわらかいピアノ風の音"""
    f = hz(n); T = int((dur + 1.6) * SR); t = np.arange(T) / SR
    B = 0.0004                                     # 弦の非調和性
    s = np.zeros(T)
    for k in range(1, 11):
        fk = f * k * np.sqrt(1 + B * k * k)
        if fk > 12000: break
        amp = (vel ** (1 + k * 0.12)) / (k ** 1.15)
        dec = 0.9 + 0.55 * k + f / 900
        s += amp * np.sin(2 * np.pi * fk * t + rng.uniform(0, 6.28)) * np.exp(-t * dec)
    s += 0.6 * np.sin(2 * np.pi * f * 1.002 * t) * np.exp(-t * 0.7) * vel   # 少しうなりを足す
    att = np.minimum(1, t / 0.006)
    rel = np.where(t > dur, np.exp(-(t - dur) * 4.5), 1)
    return s * att * rel

def add(sig, t0, gain=1.0, pan=0.0):
    i = int(t0 * SR); j = min(N, i + len(sig))
    if i >= N: return
    L[i:j] += sig[:j - i] * gain * (1 - pan) ; R[i:j] += sig[:j - i] * gain * (1 + pan)

BEAT = 60 / 68            # 68BPM
# 和音: Cmaj9 → Am7 → Fmaj7 → G6sus → (締め) Cmaj7add9
prog = [([48, 55, 64, 71, 74], 0), ([45, 52, 60, 67, 71], 4), ([41, 48, 57, 64, 67], 8), ([43, 50, 60, 64, 69], 12),
        ([48, 55, 64, 71, 74], 16), ([45, 52, 60, 67, 72], 20)]
for notes, beat in prog:
    t0 = 0.5 + beat * BEAT
    for i, n in enumerate(notes):                  # 下から少しずつずらして弾く
        add(piano(n, BEAT * 3.6, 0.42 if n < 55 else 0.34), t0 + i * 0.045, 0.55, pan=(-0.25 if n < 55 else 0.15))
# 上のメロディ（短い問いかけ → 答え）
mel = [(76, 0), (79, 1.5), (78, 2), (76, 3), (74, 4.5), (72, 6), (74, 7.5), (76, 8), (71, 10),
       (72, 12), (74, 13.5), (76, 14), (79, 16), (78, 17.5), (76, 18), (74, 19.5), (76, 20)]
for n, b in mel:
    add(piano(n, BEAT * 1.4, 0.5), 0.5 + b * BEAT, 0.42, pan=0.2)
# 最後（ロゴ）: 高い音の和音をそっと置く
end_t = 0.5 + 22 * BEAT
for i, n in enumerate([72, 76, 79, 83, 88]):
    add(piano(n, 3.0, 0.38), end_t + i * 0.06, 0.38, pan=0.1)

# 空気感: ごく薄いノイズのパッド
air = np.convolve(rng.standard_normal(N), np.ones(400) / 400, mode="same") * 0.004
L += air; R += air
# 残響: 減衰するノイズとの畳み込み（FFT）
ir_t = np.arange(int(2.6 * SR)) / SR
def ir(seed):
    r = np.random.default_rng(seed).standard_normal(len(ir_t)) * np.exp(-ir_t * 2.4)
    r[:int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR)); return r / np.sqrt(np.sum(r ** 2))
def conv(x, h):
    n = len(x) + len(h); F = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, F) * np.fft.rfft(h, F), F)[:len(x)]
wetL, wetR = conv(L, ir(11)), conv(R, ir(12))
L = L * 0.78 + wetL * 0.5; R = R * 0.78 + wetR * 0.5
fade = np.ones(N); k = int(2.5 * SR); fade[-k:] = np.linspace(1, 0, k) ** 2
L *= fade; R *= fade
peak = max(np.abs(L).max(), np.abs(R).max()); L /= peak / 0.85; R /= peak / 0.85
pcm = (np.stack([L, R], 1) * 32767).astype(np.int16)
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print("ok", TOTAL, "end chord at", round(end_t, 2))
