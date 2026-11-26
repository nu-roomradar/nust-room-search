"""リール3本の音（numpy で合成。既存の曲は使わない）。場面の時刻は各 HTML のタイムラインと同じ。
  python3 music.py r1   → r1.wav（TARGET_LUFS＝-22 LUFS にそろえる。2026-11-24 までは -14、11-25 に -17 → -20 → -22）
音程は倍音の足し算で作るので、ずれない（Karplus-Strong は使わない。make-video の手順書 6）。"""
import re, subprocess, sys, wave
import numpy as np

SR = 44100
TARGET_LUFS = -22.0                     # 音の大きさのめあて。2026-11-24 運営「若干音が大きい」で -14 → -17、11-25「まだ結構大きい」で -20、同日「もうちょいだけ下げて」で -22
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
    first = lufs_of(raw); gain = 10 ** ((TARGET_LUFS - first) / 20)
    for _ in range(4):                    # はんこなどの大きな音を抑えると全体が下がるので、測り直して合わせる
        out_st = limit(st * gain); write(f"{name}.wav", out_st)
        got = lufs_of(f"{name}.wav")
        if abs(got - TARGET_LUFS) < 0.3: break
        gain *= 10 ** ((TARGET_LUFS - got) / 20)
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


def mallet(f, dur=0.9):                  # 木琴のような音（基音＋高い倍音がすぐ消える）
    t = np.arange(int(dur * SR)) / SR
    s = (np.sin(2 * np.pi * f * t) * np.exp(-t * 5) + 0.35 * np.sin(2 * np.pi * f * 3.98 * t) * np.exp(-t * 18)
         + 0.12 * np.sin(2 * np.pi * f * 9.9 * t) * np.exp(-t * 40))
    return s * np.minimum(t / 0.002, 1)


def chalk(t0, t1, m, gain=0.32):         # チョークで書く音：短いこすれを、すき間をあけて並べる
    t = t0
    while t < t1:
        d = rng.uniform(0.045, 0.11); x = noise(d)
        x = onepole(x, 0.55) - onepole(x, 0.12)                     # 高めの帯域だけ
        e = np.sin(np.pi * np.arange(len(x)) / len(x)) ** 0.7
        m.add(x * e * rng.uniform(0.6, 1.0), t, gain, rng.uniform(-0.2, 0.2))
        t += d + rng.uniform(0.015, 0.05)


def tap():                               # チョークで点を打つ・黒板をたたく音
    t = np.arange(int(0.06 * SR)) / SR
    return (np.sin(2 * np.pi * 900 * t) * 0.5 + onepole(noise(0.06), 0.5)) * np.exp(-t / 0.01)


def r2d():
    """クイズ（黒板の版・14.4秒）。木琴と手拍子の明るい音（3本目の紺のスタジオとは別の雰囲気）"""
    S = 1.5                               # v6：答えを 1.5 秒長く見せる。黒板消しから後はすべて S 秒ずらす
    m = Mix(14.4 + S)
    F = {"F": ["F3", "A3", "C4", "F4"], "Dm": ["D3", "F3", "A3", "D4"], "Bb": ["Bb2", "D3", "F3", "Bb3"], "C": ["C3", "E3", "G3", "C4"]}
    prog = ["F", "Dm", "Bb", "C"]; beat = 0.6
    def bed(t0, t1, bar0=0, lively=True):
        k = 0; t = t0
        while t < t1 - 1e-6:
            ch = F[prog[(bar0 + k // 4) % 4]]
            m.add(mallet(note(ch[0]) / 2, 1.0), t, 0.30) if k % 4 == 0 else None
            for j, n in enumerate((ch[1], ch[3], ch[2], ch[3]) if lively else (ch[1], ch[2])):
                tt = t + j * beat / (4 if lively else 2)
                if tt < t1: m.add(mallet(note(n) * 2, 0.6), tt, 0.12, (-0.3, 0.3)[j % 2])
            if lively and k % 2 == 1: m.add(clap(), t, 0.16, 0.15)
            if lively: m.add(hat(), t + beat / 2, 0.08, -0.2)
            k += 1; t += beat
    # 1. 問題を書く
    chalk(0.02, 0.24, m, 0.38); chalk(0.2, 0.52, m); chalk(0.5, 0.92, m); chalk(0.95, 1.5, m); chalk(1.5, 1.78, m, 0.25)
    m.add(mallet(note("F5"), 1.2), 0.05, 0.35); m.add(mallet(note("A5"), 1.2), 0.25, 0.25)
    bed(1.8, 5.6, lively=False)
    # 2. 選択肢とカウントダウン
    for t in (2.0, 2.4, 2.8): chalk(t, t + 0.34, m)
    for t in (3.4, 4.2, 5.0): m.add(tap(), t, 0.7); chalk(t, t + 0.18, m, 0.3)
    # 3. 正解（赤い丸・正解！・数字）
    chalk(5.65, 6.05, m, 0.42); m.add(bell(note("C6")), 5.7, 0.35); m.add(bell(note("F6")), 5.85, 0.22)
    m.add(mallet(note("F4"), 1.4) + mallet(note("A4"), 1.4) + mallet(note("C5"), 1.4), 5.65, 0.35)
    chalk(6.05, 6.3, m); chalk(6.35, 6.88, m, 0.25); chalk(6.75, 7.2, m)
    bed(6.0, 7.3 + S, bar0=0)
    chalk(7.5, 7.8, m, 0.3); m.add(pop(988), 7.9, 0.35)                 # 「24室」の下線と、数字がはねる
    # 4. 黒板消し
    m.add(whoosh(0.36), 7.3 + S, 0.55, 0.3); m.add(whoosh(0.36), 7.66 + S, 0.55, -0.3)
    # 5. 表を書く
    chalk(8.1 + S, 8.42 + S, m); chalk(8.42 + S, 8.72 + S, m)
    for i in range(13): chalk(8.75 + S + i * 0.03, 8.75 + S + i * 0.03 + 0.12, m, 0.12)
    chalk(9.05 + S, 10.1 + S, m, 0.14)
    chalk(10.25 + S, 10.65 + S, m, 0.32); m.add(bell(note("A5")), 10.3 + S, 0.22)
    chalk(10.7 + S, 11.12 + S, m); chalk(11.0 + S, 11.35 + S, m, 0.18)
    bed(8.1 + S, 11.7 + S, bar0=1)
    # 6. 消して、紙を貼る
    m.add(whoosh(0.34), 11.7 + S, 0.5); chalk(12.05 + S, 12.4 + S, m); chalk(12.38 + S, 12.66 + S, m)
    m.add(tap(), 12.5 + S, 0.5); m.add(tap(), 12.56 + S, 0.4)
    m.add(mallet(note("F3"), 2.0) + mallet(note("C4"), 2.0) + mallet(note("A4"), 2.0) + mallet(note("F5"), 2.0), 12.1 + S, 0.4)
    bed(12.1 + S, 13.8 + S, bar0=0, lively=False)
    master(m, "r2d", fade_out=0.8)


def soft(f, dur=2.6, d=1.1):               # やわらかい鍵盤のような音（倍音を少なく、ゆっくり消える）
    t = np.arange(int(dur * SR)) / SR
    s = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t / (d / k ** 0.6)) for k, a in ((1, 1.0), (2, 0.32), (3, 0.12), (4, 0.05)))
    return s * np.minimum(t / 0.012, 1)


def r4():
    """「開けたら、空いてる」（11.0秒）。静かな和音と、ゆっくりした分散。場面の切り替え（3.3・5.7・8.1秒）で和音が変わる"""
    m = Mix(11.0)
    CH = {"D": ["D3", "A3", "E4", "F#4"], "Bm": ["B2", "F#3", "D4", "A4"], "G": ["G2", "D3", "B3", "A4"], "Dend": ["D3", "A3", "F#4", "D5"]}
    plan = [(0.0, 3.3, "D"), (3.3, 5.7, "Bm"), (5.7, 8.1, "G"), (8.1, 11.0, "Dend")]
    for t0, t1, name in plan:
        ch = [note(n) for n in CH[name]]
        m.add(pad(ch[:3], t1 - t0 + 0.4), max(0, t0 - 0.2), 0.20)                # 下に薄く敷く和音
        m.add(soft(ch[0] / 2, 3.0, 1.6), t0, 0.34)                               # 低い音
        seq = [ch[1], ch[2], ch[3], ch[2]] if name != "Dend" else [ch[1], ch[2], ch[3]]
        for j, f in enumerate(seq):                                              # ゆっくりした分散（0.6秒おき）
            tt = t0 + 0.3 + j * 0.6
            if tt < t1 - 0.2 or name == "Dend": m.add(soft(f, 2.4), tt, 0.26, (-0.25, 0.25)[j % 2])
    for t, f, g in ((0.15, "A5", 0.10), (3.3, "F#5", 0.09), (5.7, "D5", 0.09), (8.1, "D6", 0.11)):
        m.add(bell(note(f)), t, g, 0.1)                                          # 切り替えの合図（小さく）
    master(m, "r4", fade_out=1.6)


def drone(f, dur, swell=True):              # 低くうなる音（予告動画の暗い出だし）。だんだん大きくなる
    t = np.arange(int(dur * SR)) / SR
    s = np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.003 * t) + 0.25 * np.sin(2 * np.pi * f * 3.01 * t)
    g = (t / dur) ** 1.6 if swell else np.ones_like(t)
    return s * g * np.minimum((dur - t) / 0.05, 1).clip(0, 1)


def impact():                              # 切り替わる一瞬の「どん」（低い音＋きらっとした高い音）
    t = np.arange(int(2.2 * SR)) / SR
    low = np.sin(2 * np.pi * np.cumsum(38 + 70 * np.exp(-t / 0.08)) / SR) * np.exp(-t / 0.7)
    air = onepole(noise(2.2), 0.08) * np.exp(-t / 0.35) * 0.35
    return low + air


def r5():
    """クリスマスモードの本編（15.4秒）。2026-11-26 に作り直し（その前は、暗いうなり → 鈴の分散）。
    カミングスーン（r6）と同じ楽器（チェレスタ・鈴・弦・声・鐘・ハープ）と同じ出だしの旋律で、続きの動画だと分かるようにした（イ長調・3拍子・1拍 0.5 秒。オリジナル）。
    机のスマホに寄る（旋律と弦、鈴がだんだん、ハープのかけ上がり）→ 🎄 を押す「こつ」→ 切り替わる一瞬に「しゃらん」と鐘ときらきら →
    ずん・ちゃっ・ちゃっのワルツと鈴 → 問いかけ → 日付で温かい和音と声（A → D/A → A）。場面の時刻は r5.html と同じ"""
    m = Mix(15.4); B = 0.5
    J = jingles(13)
    def cel(n, t, g, pan=0.0): m.add(celesta(note(n)), t, g, pan); m.add(bell(note(n) * 2), t, g * 0.12, -pan)
    bar = lambda k: 0.55 + 3 * B * k                     # 小節の頭（3小節目の頭 3.55 秒が切り替わり）
    # 1. 机のスマホに寄る（0〜3.55秒）
    m.add(wind(2.6), 0.0, 0.1)
    for n, t in (("E5", bar(0)), ("A5", bar(0) + B), ("C#6", bar(0) + 2 * B), ("B5", bar(1)), ("A5", bar(1) + 1.5 * B), ("F#5", bar(1) + 2 * B)):
        cel(n, t, 0.3, 0.1)
    m.add(strings(("A2", "E3", "A3", "C#4"), 1.6, att=1.0, rel=0.4), bar(0), 0.13)
    m.add(strings(("F#2", "C#3", "F#3", "A3"), 1.55, att=0.5, rel=0.1), bar(1), 0.17)
    sleigh_run(m, J, bar(1), bar(2) - 0.05, B / 2, 0.04, 0.13)
    for i, n in enumerate(("A4", "B4", "C#5", "D5", "E5", "F#5", "G#5", "A5", "B5", "C#6")):   # ハープのかけ上がり
        m.add(pluck(note(n), 1.2, 0.8), 3.05 + 0.45 * i / 10, 0.09, -0.4 + 0.8 * i / 10)
    m.add(pop(1300), 3.33, 0.18)                                                       # 🎄 を押す「こつ」
    # 2. 切り替わる（3.55秒）：「しゃらん」・鐘・きらきら・弦と声
    S = bar(2)
    m.add(sleigh_crash(), S, 0.3, 0.1); m.add(toll(note("A2")), S, 0.3); m.add(timp(note("A1")), S, 0.3)
    for n in ("A6", "C#7", "E7"): m.add(bell(note(n)), S + 0.01, 0.06)
    m.add(strings(("A2", "E3", "A3", "C#4", "E4", "A4"), 1.5, att=0.03, rel=0.4, cutoff=3200), S, 0.22)
    m.add(choir(("A3", "C#4", "E4"), 1.5, att=0.3, rel=0.5), S, 0.1)
    # 3. ワルツ（3.55〜9.55秒）：A → D → Bm → E
    prog = (("A2", ("C#5", "E5", "A5"), ("A2", "E3", "A3", "C#4")), ("D3", ("D5", "F#5", "A5"), ("D3", "F#3", "A3", "D4")),
            ("B2", ("D5", "F#5", "B5"), ("B2", "F#3", "B3", "D4")), ("E3", ("D5", "G#5", "B5"), ("E3", "G#3", "B3", "D4")))
    for k, (bass, ch, pad_) in enumerate(prog):
        t = bar(2 + k)
        m.add(pluck(note(bass), 0.9, 0.5), t, 0.42)
        for jb in (1, 2):
            for n in ch: m.add(celesta(note(n)), t + jb * B, 0.05, (-0.3, 0.3)[jb - 1])
        if k: m.add(strings(pad_, 3 * B, att=0.2, rel=0.2), t, 0.15)
    for n, t, d in (("A5", bar(2), 0), ("C#6", bar(2) + B, 0), ("E6", bar(2) + 2 * B, 0), ("F#6", bar(3), 0), ("E6", bar(3) + B, 0), ("D6", bar(3) + 2 * B, 0),
                    ("C#6", bar(4), 0), ("B5", bar(4) + 1.5 * B, 0), ("A5", bar(4) + 2 * B, 0), ("B5", bar(5), 0), ("G#5", bar(5) + 2 * B, 0)):
        cel(n, t, 0.24)
    sleigh_run(m, J, S, bar(4), B / 2, 0.14, 0.15)
    sleigh_run(m, J, bar(4), bar(6) - 0.05, B / 2, 0.12, 0.08)                         # 問いかけの間は少し静かに
    # 4. 日付（9.55秒〜）：A → D/A → A。弦と声、チェレスタ、鈴をひと振りずつ
    E = bar(6)
    m.add(toll(note("A2")), E, 0.16)
    for names, t0, d, a, r in ((("A2", "E3", "A3", "C#4", "E4"), E, 1.6, 0.6, 0.4), (("A2", "D3", "F#3", "A3", "D4"), E + 1.5, 1.6, 0.4, 0.4), (("A2", "E3", "A3", "C#4", "E4"), E + 3.0, 2.85, 0.4, 1.8)):
        m.add(strings(names, d, att=a, rel=r), t0, 0.19)
        m.add(choir(names[2:], d, att=a + 0.3, rel=r), t0 + 0.05, 0.15)
    for n, t, gg in (("E6", E + 0.05, 0.22), ("C#6", E + 0.55, 0.2), ("A5", E + 1.05, 0.2), ("B5", E + 1.55, 0.2), ("A5", E + 2.05, 0.18), ("C#6", E + 3.0, 0.18), ("A5", E + 3.02, 0.12)):
        cel(n, t, gg)
    for t, gg in ((E, 0.11), (E + 1.5, 0.08), (E + 3.0, 0.07), (E + 4.3, 0.05)): shake_once(m, J, t, gg)
    master(m, "r5", fade_out=1.8)


def wind(dur):                             # 夜の風（こもった雑音が、ゆっくり強くなったり弱くなったり）
    t = np.arange(int(dur * SR)) / SR
    x = onepole(noise(dur), 0.02)
    return x * (0.6 + 0.4 * np.sin(2 * np.pi * 0.23 * t) * np.sin(2 * np.pi * 0.11 * t + 1)) * np.minimum(t / 1.0, 1)


def sleigh_crash():                        # たくさんの鈴が一度に鳴る「しゃらん」
    m = np.zeros(int(2.0 * SR))
    for k in range(18):
        f = 2400 + 1600 * rng.random(); i = int(rng.random() * 0.12 * SR)
        b = bell(f)[: len(m) - i] * (0.5 + 0.5 * rng.random())
        m[i:i + len(b)] += b
    return m


def fft_filter(x, gain):                    # 周波数ごとに大きさを変える（gain は周波数 Hz の配列を受けて倍率を返す関数）
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X * gain(f), len(x))


def _saws(fs, t, detunes, vib):
    s = np.zeros_like(t)
    for f in fs:
        for d in detunes:
            ph = np.cumsum(f * (1 + d) * (1 + vib * (1 + 40 * d))) / SR
            s += 2 * (ph % 1.0) - 1
    return s / (len(fs) * len(detunes))


def strings(names, dur, att=0.6, rel=0.8, cutoff=2200):   # 弦の和音（少しずつずらした のこぎり波を重ね、高い音を丸める）
    t = np.arange(int(dur * SR)) / SR
    s = _saws([note(n) for n in names], t, (-0.004, 0.0, 0.0045), 0.0022 * np.sin(2 * np.pi * 5.1 * t))
    s = fft_filter(s, lambda f: (f > 45) / np.sqrt(1 + (f / cutoff) ** 4))
    return s * np.minimum(t / att, 1) * np.minimum((dur - t) / rel, 1).clip(0, 1)


def choir(names, dur, att=1.0, rel=1.0):    # 聖歌隊のような「あー」（声の響きの山を3つ作る）
    t = np.arange(int(dur * SR)) / SR
    s = _saws([note(n) for n in names], t, (-0.003, 0.003), 0.004 * np.sin(2 * np.pi * 5.6 * t))
    fm = lambda f: (f > 60) * (0.06 + sum(a * np.exp(-((f - F) / w) ** 2) for F, a, w in ((730, 1.0, 140), (1090, 0.55, 160), (2440, 0.28, 240)))) / np.sqrt(1 + (f / 3600) ** 6)
    return fft_filter(s, fm) * 2.2 * np.minimum(t / att, 1) * np.minimum((dur - t) / rel, 1).clip(0, 1)


def celesta(f, dur=1.6):                    # チェレスタ（オルゴールのような、やわらかい金属の鍵盤）
    t = np.arange(int(dur * SR)) / SR
    s = (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.9) + 0.25 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / 0.35)
         + 0.16 * np.sin(2 * np.pi * 4 * f * t) * np.exp(-t / 0.16) + 0.1 * np.sin(2 * np.pi * 2.76 * f * t) * np.exp(-t / 0.05))
    return s * np.minimum(t / 0.0015, 1)


def toll(f, dur=5.0):                       # 教会の鐘（低いうなりと、ずれた倍音が長く残る）
    t = np.arange(int(dur * SR)) / SR
    parts = ((0.5, 0.3, 2.4), (1.0, 1.0, 2.4), (1.19, 0.42, 1.7), (1.5, 0.32, 1.3), (2.0, 0.45, 1.1), (2.51, 0.22, 0.7), (3.0, 0.18, 0.55), (4.07, 0.1, 0.35))
    s = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t / d) for r, a, d in parts)
    s *= 1 + 0.12 * np.sin(2 * np.pi * 1.3 * t)
    return s * np.minimum(t / 0.002, 1)


def timp(f):                                # ティンパニのような低い「どーん」
    t = np.arange(int(1.2 * SR)) / SR
    body = np.sin(2 * np.pi * np.cumsum(f * (1 + 0.08 * np.exp(-t / 0.05))) / SR) * np.exp(-t / 0.55)
    return body + 0.3 * onepole(noise(1.2), 0.08) * np.exp(-t / 0.03)


def jingles(seed=11):                        # 鈴ひと鳴りの音を10とおり（高い小さな鈴を7つ＋「しゃっ」という雑音）。種を固定して毎回同じ音に
    jr = np.random.default_rng(seed)
    def one(dur=0.35):
        t = np.arange(int(dur * SR)) / SR; out = np.zeros_like(t)
        for _ in range(7):
            f = 2600 + 4400 * jr.random(); o = int(jr.random() * 0.022 * SR); d = 0.05 + 0.12 * jr.random(); tt = t[: len(t) - o]
            out[o:] += (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 2.31 * tt)) * np.exp(-tt / d) * (0.5 + 0.5 * jr.random())
        nz = fft_filter(jr.standard_normal(len(t)), lambda fr: (fr > 4500) * 1.0)
        return (out / 7 + 0.35 * nz * np.exp(-t / 0.018))
    return [2.6 * one() for _ in range(10)]   # 鈴がほかの楽器に埋もれないよう大きめに


def sleigh_run(m, J, t0, t1, step, g0, g1, accent=2):   # 鈴を一定の間隔で鳴らし続ける（g0 → g1 へ大きさを変える）
    k, t = 0, t0
    while t < t1 - 1e-6:
        g = g0 + (g1 - g0) * (t - t0) / max(1e-6, t1 - t0)
        m.add(J[k % 10], t, g * (1.0 if k % accent == 0 else 0.6), (-0.25, 0.25)[k % 2]); k += 1; t += step


def shake_once(m, J, t0, g):                  # 鈴をひと振り
    for k in range(7): m.add(J[k % 10], t0 + k * 0.06, g * np.sin(np.pi * (k + 0.5) / 7), (-0.3, 0.3)[k % 2])


def r6():
    """カミングスーン（16.5秒）。2026-11-24 運営「音楽をもっとクリスマスに」で作り直し（その前は、風と低いうなりの暗い音）。
    鈴・チェレスタ・弦・聖歌隊ふうの声・教会の鐘・ハープの音で、イ長調・3拍子のオリジナルの旋律（既存の曲ではない）。
    星（チェレスタの旋律と弦、鈴がだんだん）→ 扉で鐘と「しゃらん」→ ずん・ちゃっ・ちゃっのワルツ → 箱が飛び出す前の高まり → 飛び出してきらきら →
    暗転で止めて低い鐘 → 日付で温かい和音と声（A → D/A → A で終わる）。場面の時刻は r6.html と同じ"""
    m = Mix(16.5); B = 0.55
    J = jingles(11)
    def sleigh(t0, t1, step, g0, g1, accent=2): sleigh_run(m, J, t0, t1, step, g0, g1, accent)
    def shake(t0, g): shake_once(m, J, t0, g)
    def cel(n, t, g, pan=0.0): m.add(celesta(note(n)), t, g, pan); m.add(bell(note(n) * 2), t, g * 0.12, -pan)

    # 1. 星（0〜5.5秒）：3拍子の旋律。A → F#m → D・E
    m.add(wind(3.5), 0.0, 0.16)
    for n, t in (("E5", 0.55), ("A5", 1.1), ("C#6", 1.65), ("B5", 2.2), ("A5", 3.025), ("F#5", 3.3), ("A5", 3.85), ("D6", 4.4), ("C#6", 4.95), ("B5", 5.225)):
        cel(n, t, 0.3, 0.1)
    m.add(strings(("A2", "E3", "A3", "C#4"), 1.75, att=1.3, rel=0.4), 0.55, 0.14)
    m.add(strings(("F#2", "C#3", "F#3", "A3"), 1.75, att=0.5, rel=0.4), 2.2, 0.18)
    m.add(strings(("D3", "F#3", "A3", "D4"), 1.15, att=0.3, rel=0.3), 3.85, 0.2)
    m.add(strings(("E3", "G#3", "B3", "E4"), 0.62, att=0.1, rel=0.08), 4.95, 0.24)
    sleigh(2.2, 5.45, B / 2, 0.04, 0.15)
    for i, n in enumerate(("A4", "B4", "C#5", "D5", "E5", "F#5", "G#5", "A5", "B5", "C#6", "D6", "E6")):   # ハープのかけ上がり
        m.add(pluck(note(n), 1.2, 0.8), 4.95 + 0.5 * i / 12, 0.1, -0.4 + 0.8 * i / 12)
    # 2. 扉（5.5〜8.4秒）：鐘・ティンパニ・「しゃらん」・弦 → ワルツ
    m.add(toll(note("A2")), 5.5, 0.36); m.add(timp(note("A1")), 5.5, 0.42); m.add(sleigh_crash(), 5.5, 0.3, 0.1)
    m.add(strings(("A2", "E3", "A3", "C#4", "E4", "A4"), 1.7, att=0.02, rel=1.1, cutoff=3200), 5.5, 0.26)
    for bar, (bass, ch) in enumerate((("A2", ("C#5", "E5", "A5")), ("D3", ("D5", "F#5", "A5")))):
        t = 5.5 + bar * 3 * B
        m.add(pluck(note(bass), 0.9, 0.5), t, 0.45)
        for j in (1, 2):
            for n in ch: m.add(celesta(note(n)), t + j * B, 0.06, (-0.3, 0.3)[j - 1])
    for n, t in (("C#6", 5.5), ("E6", 6.6), ("F#6", 7.15), ("E6", 7.7), ("D6", 8.25)): cel(n, t, 0.24)
    sleigh(5.5, 8.4, B / 2, 0.13, 0.17)
    m.add(toll(note("E3")), 7.1, 0.12, -0.3)                                           # 遠くでもう一度
    # 3. 雪の上（8.4〜10.6秒）：高まり → 箱が飛び出してきらきら
    m.add(impact(), 8.4, 0.28)
    m.add(strings(("E3", "G#3", "B3", "D4", "E4"), 0.78, att=0.6, rel=0.04), 8.4, 0.24)
    sleigh(8.4, 9.15, B / 4, 0.07, 0.2)
    for i, n in enumerate(("E5", "G#5", "B5", "D6", "E6", "G#6")): cel(n, 8.5 + i * 0.11, 0.15)
    m.add(pop(520), 9.15, 0.4); m.add(sleigh_crash(), 9.15, 0.28, -0.1)
    for n in ("A6", "C#7", "E7"): m.add(bell(note(n)), 9.16, 0.05)
    m.add(strings(("A2", "E3", "A3", "C#4", "E4"), 1.45, att=0.03, rel=0.3), 9.15, 0.22)
    for n, t in (("E6", 9.45), ("C#6", 9.725), ("B5", 10.0), ("A5", 10.275)): cel(n, t, 0.2)
    sleigh(9.15, 10.55, B / 2, 0.13, 0.11)
    # 暗転：ここまでの音を止め、低い鐘だけ残す
    k0, k1 = int(10.56 * SR), int(10.6 * SR); g = np.ones(m.n); g[k0:k1] = np.linspace(1, 0, k1 - k0); g[k1:] = 0
    m.L *= g; m.R *= g
    m.add(impact(), 10.58, 0.4); m.add(toll(note("A2")), 10.58, 0.22)
    # 4. 日付（11.0〜16.5秒）：A → D/A → A。弦と声、チェレスタ、鈴をひと振りずつ
    for names, t0, d, a, r in ((("A2", "E3", "A3", "C#4", "E4"), 11.0, 2.4, 0.9, 0.6), (("A2", "D3", "F#3", "A3", "D4"), 13.2, 1.3, 0.4, 0.5), (("A2", "E3", "A3", "C#4", "E4"), 14.3, 2.2, 0.5, 1.6)):
        m.add(strings(names, d, att=a, rel=r), t0, 0.2)
        m.add(choir(names[2:], d, att=a + 0.3, rel=r), t0 + 0.05, 0.16)
    for n, t, gg in (("E6", 11.05, 0.24), ("C#6", 11.6, 0.22), ("A5", 12.15, 0.22), ("B5", 12.7, 0.22), ("A5", 13.25, 0.2), ("C#6", 14.3, 0.2), ("A5", 14.32, 0.14)):
        cel(n, t, gg)
    for t, gg in ((11.0, 0.12), (12.1, 0.09), (13.2, 0.08), (14.3, 0.07), (15.4, 0.05)): shake(t, gg)
    master(m, "r6", fade_out=2.0)


if __name__ == "__main__":
    {"r1": r1, "r2": r2, "r3": r3, "r2d": r2d, "r4": r4, "r5": r5, "r6": r6}[sys.argv[1]]()
