# Musique lo-fi sombre (libre de droits, générée) : Em - Cmaj7 - Am7 - B7, ~84 BPM,
# piano feutré, basse douce, kick étouffé, charleston léger, craquement de vinyle.
import sys, wave
import numpy as np
dur = float(sys.argv[1]); out = sys.argv[2]
SR = 44100; N = int(SR * dur); t = np.arange(N) / SR
rng = np.random.default_rng(7); mix = np.zeros(N)
midi = lambda m: 440 * 2 ** ((m - 69) / 12)
bpm = 84; beat = 60 / bpm; bar = 4 * beat
CH = [[52, 55, 59, 64], [48, 52, 55, 59], [45, 52, 55, 60], [47, 51, 54, 57]]
def add(x, at, gain):
    i = int(at * SR); x = x[:max(0, N - i)]; mix[i:i + len(x)] += x * gain
def piano(f, d):
    n = int(d * SR); tt = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * f * k * tt) * (0.6 ** k) for k in range(1, 5))
    return x * np.exp(-tt * 2.2) * np.minimum(1, tt / 0.01)
pos, b = 0.0, 0
while pos < dur:
    ch = CH[b % 4]
    for k, m in enumerate(ch):  # accord arpégé doucement
        add(piano(midi(m + 12), bar), pos + k * 0.06, 0.05)
    add(piano(midi(ch[0] - 12), bar) * 0.9, pos, 0.12)  # basse
    for q in range(4):
        n = int(0.3 * SR); tt = np.arange(n) / SR
        if q in (0, 2): add(np.sin(2 * np.pi * (45 + 70 * np.exp(-tt * 25)) * tt) * np.exp(-tt * 9), pos + q * beat, 0.35)
        if q in (1, 3): add(rng.normal(0, 1, n) * np.exp(-tt * 18) * 0.5, pos + q * beat, 0.06)
        for h in (0, 0.5):
            m = int(0.04 * SR); add(rng.normal(0, 1, m) * np.exp(-np.arange(m) / SR * 120), pos + (q + h) * beat, 0.02)
    pos += bar; b += 1
# filtre passe-bas simple (son feutré) + vinyle
k = 6; mix = np.convolve(mix, np.ones(k) / k, 'same')
crack = (rng.random(N) < 0.0004) * rng.normal(0, 1, N) * 0.3 + rng.normal(0, 0.004, N)
mix = mix + crack
fade = np.minimum(1, t / 1.5) * np.clip((dur - t) / 2.0, 0, 1)
mix = mix * fade; mix = mix / np.abs(mix).max() * 0.9
w = wave.open(out, 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((np.stack([mix, mix], 1) * 32767).astype('<i2').tobytes()); w.close(); print('ok')
