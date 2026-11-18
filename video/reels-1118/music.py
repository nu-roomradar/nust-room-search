"""リール3本の音（numpy で合成。既存の曲は使わない）。場面の時刻は各 HTML のタイムラインと同じ。
  python3 music.py r1   → r1.wav（-14 LUFS にそろえる）
音程は倍音の足し算で作るので、ずれない（Karplus-Strong は使わない。make-video の手順書 6）。"""
import re, subprocess, sys, wave
import numpy as np

SR = 44100
rng = np.random.default_rng(7)          # 毎回同じ音になるよう、雑音の種を固定


def note(n):                             # 'A4' などを Hz に
    names = {'C': -9, 'D': -7, 'E': -5, 'F': -4, 'G': -2, 'A': 0, 'B': 2}
    m = re.match(r'([A-G])(#|b)?(\d)', n)
    k = names[m[1]] + (1 if m[2] == '#' else -1 if m[2] == 'b' else 0) + (int(m[3]) - 4) * 12
    return 440.0 * 2 ** (k / 12)


class Mix:
    def __init__(self, dur):
        self.n = int(dur * SR); self.L = np.zeros(self.n); self.R = np.zeros(self.n)

    def add(self, sig, t0, gain=1.0, pan=0.0):
        i = int(t0 * SR)
        if i >= self.n: return
        sig = sig[: self.n - i]
        self.L[i:i + len(sig)] += sig * gain * (1 - max(pan, 0))
        self.R[i:i + len(sig)] += sig * gain * (1 + min(pan, 0))


def env(n, a=0.004, d=0.4):
    t = np.arange(n) / SR
    return np.minimum(t / a, 1) * np.exp(-t / d)


def pluck(f, dur=0.6, bright=1.0):
    t = np.arange(int(dur * SR)) / SR
    s = sum((0.6 ** k) * bright ** k * np.sin(2 * np.pi * f * (k + 1) * t) * np.exp(-t * (3 + 2.5 * k)) for k in range(6))
    return s * np.minimum(t / 0.003, 1)


def pad(fs, dur):
    t = np.arange(int(dur * SR)) / SR
    s = sum(np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t) for f in fs) / len(fs)
    return s * np.minimum(t / 0.15, 1) * np.minimum((dur - t) / 0.3, 1).clip(0, 1)


def kick():
    t = np.arange(int(0.3 * SR)) / SR
    f = 45 + 80 * np.exp(-t / 0.04)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.12)


def noise(dur):
    return rng.standard_normal(int(dur * SR))


def onepole(x, a):                        # 簡単な低域通過（a が小さいほどこもる）
    y = np.zeros_like(x); acc = 0.0
    for i, v in enumerate(x):
        acc += a * (v - acc); y[i] = acc
    return y


def hat():
    x = noise(0.05); x = x - onepole(x, 0.3)
    return x * np.exp(-np.arange(len(x)) / SR / 0.012)


def clap():
    x = noise(0.14); x = onepole(x, 0.5) - onepole(x, 0.08)
    e = np.exp(-np.arange(len(x)) / SR / 0.05)
    return x * e * 1.6


def thud():                               # 「授業中」のはんこ
    t = np.arange(int(0.35 * SR)) / SR
    body = np.sin(2 * np.pi * (60 + 90 * np.exp(-t / 0.03)) * t) * np.exp(-t / 0.09)
    click = onepole(noise(0.35), 0.4) * np.exp(-t / 0.012)
    return body * 1.1 + click * 0.5


def whoosh(dur=0.35):
    x = noise(dur); n = len(x); out = np.zeros(n); acc = 0.0
    for i in range(n):
        a = 0.02 + 0.25 * (i / n); acc += a * (x[i] - acc); out[i] = acc
    return out * np.sin(np.pi * np.arange(n) / n) * 1.4


def tick(f=1900):
    t = np.arange(int(0.05 * SR)) / SR
    return np.sin(2 * np.pi * f * t) * np.exp(-t / 0.008)


def bell(f=1318.5):
    t = np.arange(int(1.6 * SR)) / SR
    parts = [(1, 1), (2.76, .5), (5.4, .25), (8.9, .12)]
    return sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * (1.6 + r)) for r, a in parts) * np.minimum(t / 0.002, 1)


def pop(f=880):
    t = np.arange(int(0.12 * SR)) / SR
    return np.sin(2 * np.pi * (f * (1 + 0.6 * np.exp(-t / 0.02))) * t) * np.exp(-t / 0.04)


CHORDS = {  # D の明るい進行（I–V–vi–IV）
    'D': ['D3', 'F#3', 'A3', 'D4'], 'A': ['A2', 'E3', 'A3', 'C#4'], 'Bm': ['B2', 'F#3', 'B3', 'D4'], 'G': ['G2', 'D3', 'G3', 'B3'],
}
PROG = ['D', 'A', 'Bm', 'G']


def groove(m, t0, t1, beat=0.5, drums=True, arp=True, start_bar=0):
    """t0〜t1 にリズムと和音の分散。1小節＝2拍（1秒）で和音が変わる"""
    k = 0; t = t0
    while t < t1 - 1e-6:
        ch = CHORDS[PROG[(start_bar + k // 2) % 4]]
        if drums:
            if k % 2 == 0: m.add(kick(), t, 0.9)
            else: m.add(clap(), t, 0.35, 0.1)
            m.add(hat(), t + beat / 2, 0.18, -0.3)
        if k % 2 == 0: m.add(pluck(note(ch[0]) / 2, 0.9, 0.6), t, 0.55)          # ベース
        if arp:
            for j, n in enumerate([ch[1], ch[2], ch[3], ch[2]]):
                m.add(pluck(note(n) * 2, 0.45), t + j * beat / 4, 0.16, (-0.4, 0.4)[j % 2])
        k += 1; t += beat


def master(m, name, fade_out):
    n = m.n; fo = int(fade_out * SR)
    g = np.ones(n); g[-fo:] = np.linspace(1, 0, fo)
    st = np.stack([m.L * g, m.R * g], 1)
    st /= max(1e-9, np.abs(st).max()) / 0.9
    raw = f"_{name}_raw.wav"; write(raw, st)
    def lufs_of(path):
        out = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
        return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", out)[-1])
    def limit(x):                         # 0.78 を超える分だけやわらかく抑える（最大 0.88。AAC にしてもはみ出さない）
        a = np.abs(x); over = a > 0.78
        y = x.copy(); y[over] = np.sign(x[over]) * (0.78 + 0.1 * np.tanh((a[over] - 0.78) / 0.1))
        return y
    first = lufs_of(raw); gain = 10 ** ((-14.0 - first) / 20)
    for _ in range(4):                    # はんこなどの大きな音を抑えると全体が下がるので、測り直して合わせる
        out_st = limit(st * gain); write(f"{name}.wav", out_st)
        got = lufs_of(f"{name}.wav")
        if abs(got + 14.0) < 0.3: break
        gain *= 10 ** ((-14.0 - got) / 20)
    print(f"{name}.wav  元 {first:.1f} LUFS → {got:.1f} LUFS（倍率 {gain:.2f}）")


def write(path, st):
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(st, -1, 1) * 32767).astype(np.int16).tobytes())


def r1():
    """空きコマあるある（13.2秒）"""
    m = Mix(13.2)
    m.add(pluck(note('D4'), 1.2) + pluck(note('F#4'), 1.2) + pluck(note('A4'), 1.2), 0.08, 0.5)   # 「空きコマ90分、」
    m.add(kick(), 0.08, 0.8); m.add(pop(988), 0.62, 0.5); m.add(kick(), 0.62, 0.6)               # 「どこ行く？」
    groove(m, 1.9, 5.9, arp=False)                                                              # ドアを回る（リズムだけ）
    for i in range(3):
        m.add(whoosh(), 1.95 + i * 1.3, 0.35, 0.3)
        m.add(thud(), 2.5 + i * 1.3, 0.9)
    for i in range(5): m.add(tick(1500 if i % 2 else 1900), 6.0 + i * 0.25, 0.35)               # 休み時間が終わる（止める）
    m.add(pad([note('D4'), note('F#4'), note('A4')], 3.3), 7.3, 0.18)                          # アプリ（明るく）
    groove(m, 7.3, 12.6, start_bar=0)
    m.add(bell(note('A5')), 8.7, 0.35); m.add(bell(note('D6')), 8.85, 0.2)                      # 輪
    m.add(pluck(note('D3'), 2.2) + pluck(note('A3'), 2.2) + pluck(note('F#4'), 2.2), 10.6, 0.5)  # 終わりの札
    m.add(bell(note('D6')), 10.65, 0.25)
    master(m, "r1", fade_out=0.8)


def r2():
    """クイズ（14.4秒）"""
    m = Mix(14.4)
    m.add(pop(1046.5), 0.0, 0.6); m.add(kick(), 0.0, 0.7)                                      # QUIZ
    m.add(pluck(note('D4'), 1.4) + pluck(note('A4'), 1.4) + pluck(note('E5'), 1.4), 0.35, 0.45)  # 問い
    for i in range(3): m.add(whoosh(0.3), 2.0 + i * 0.18, 0.28, (-0.3, 0, 0.3)[i])                # 選択肢
    m.add(pad([note('A3'), note('E4'), note('A4')], 3.0), 2.6, 0.16)                              # 考える間（同じ和音で待つ）
    for t in (2.6, 3.6, 4.6):
        m.add(tick(2100), t, 0.6); m.add(kick(), t, 0.5)
    for k in range(6): m.add(hat(), 2.6 + k * 0.5 + 0.25, 0.12)
    m.add(bell(note('A5')), 5.65, 0.4); m.add(thud(), 5.7, 0.7)                                 # 正解
    m.add(pluck(note('D4'), 1.6) + pluck(note('F#4'), 1.6) + pluck(note('A4'), 1.6) + pluck(note('D5'), 1.6), 5.65, 0.45)
    for k in range(7): m.add(pop(700 + k * 90), 5.9 + k * 0.1, 0.18)                             # 数が増える
    groove(m, 6.6, 13.6, start_bar=0)
    m.add(bell(note('E6')), 9.6, 0.22)                                                        # 5限・6限
    m.add(pluck(note('D3'), 2.2) + pluck(note('A3'), 2.2) + pluck(note('F#4'), 2.2), 11.8, 0.5)  # 終わりの札
    m.add(bell(note('D6')), 11.85, 0.25)
    master(m, "r2", fade_out=0.8)


def r3():
    """ランキング（13.6秒）"""
    m = Mix(13.6)
    m.add(kick(), 0.1, 0.8); m.add(pluck(note('D4'), 1.4) + pluck(note('F#4'), 1.4) + pluck(note('B4'), 1.4), 0.1, 0.5)   # つかみ
    m.add(pop(988), 0.5, 0.35)
    groove(m, 1.9, 5.5, arp=False)                                                   # 5位〜2位（リズム）
    for k, t in enumerate((2.2, 3.0, 3.8, 4.6)):
        m.add(whoosh(0.28), t, 0.25, (-0.3, 0.3)[k % 2]); m.add(pop(660 + k * 110), t + 0.1, 0.3)
    for k in range(8): m.add(tick(1700 + k * 60), 5.5 + k * 0.05, 0.12 + k * 0.03)   # 1位の前のため（細かく速く）
    m.add(kick(), 5.9, 1.0); m.add(bell(note('A5')), 5.95, 0.4); m.add(bell(note('D6')), 6.1, 0.25)   # 1位
    m.add(pluck(note('D4'), 1.8) + pluck(note('F#4'), 1.8) + pluck(note('A4'), 1.8) + pluck(note('D5'), 1.8), 5.9, 0.5)
    groove(m, 6.4, 13.0, start_bar=0)
    for k in range(3): m.add(pop(880 + k * 120), 9.2 + k * 0.15, 0.3)                 # マナーの札
    m.add(pluck(note('D3'), 2.2) + pluck(note('A3'), 2.2) + pluck(note('F#4'), 2.2), 11.0, 0.5)   # 終わりの札
    m.add(bell(note('D6')), 11.05, 0.25)
    master(m, "r3", fade_out=0.8)


if __name__ == "__main__":
    {"r1": r1, "r2": r2, "r3": r3}[sys.argv[1]]()
