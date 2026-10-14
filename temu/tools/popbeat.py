# Petite musique pop entraînante générée (libre de droits) pour les vidéos produit.
# usage : popbeat.py durée out.wav [seed] [bpm] [tonalité midi]
import sys, wave
import numpy as np
dur = float(sys.argv[1]); out = sys.argv[2]
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1; bpm = float(sys.argv[4]) if len(sys.argv) > 4 else 112
key = int(sys.argv[5]) if len(sys.argv) > 5 else 60
SR = 44100; N = int(SR * (dur + 1)); rng = np.random.default_rng(seed); mix = np.zeros(N)
beat = 60 / bpm; bar = 4 * beat
f = lambda m: 440 * 2 ** ((m - 69) / 12)
PROG = [[0, 4, 7], [7, 11, 14], [9, 12, 16], [5, 9, 12]] if seed % 2 else [[9, 12, 16], [5, 9, 12], [0, 4, 7], [7, 11, 14]]
def add(x, at, g):
    i = int(at * SR); x = x[:max(0, N - i)]; mix[i:i + len(x)] += x * g
def env(n, a=0.005, d=0.25):
    t = np.arange(n) / SR; return np.minimum(1, t / a) * np.exp(-t / d)
def pluck(fr, d=0.3):
    n = int(d * SR); t = np.arange(n) / SR
    return (np.sign(np.sin(2 * np.pi * fr * t)) * 0.3 + np.sin(2 * np.pi * fr * t)) * env(n, 0.003, d / 3)
def kick():
    n = int(0.3 * SR); t = np.arange(n) / SR; fr = 50 + 90 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t * 9)
def clap():
    n = int(0.2 * SR); return rng.standard_normal(n) * env(n, 0.002, 0.05)
def hat():
    n = int(0.05 * SR); x = rng.standard_normal(n); x = np.diff(np.concatenate([[0], x])); return x * env(n, 0.001, 0.015)
pat = rng.integers(0, 3, 8)
t = 0.0; b = 0
while t < dur + 1:
    ch = PROG[b % 4]
    for k in range(4):
        add(kick(), t + k * beat, 0.9)
        if k % 2: add(clap(), t + k * beat, 0.35)
        for h in (0, 0.5): add(hat(), t + (k + h) * beat, 0.25 if h else 0.15)
    for k in range(8):   # arpège
        m = key + ch[(k + pat[k]) % 3] + (12 if k % 4 == 3 else 0)
        add(pluck(f(m), 0.35), t + k * beat / 2, 0.22)
    for k in range(4):   # basse
        n = int(beat * 0.9 * SR); tt = np.arange(n) / SR
        add(np.sin(2 * np.pi * f(key - 24 + ch[0]) * tt) * env(n, 0.01, 0.4), t + k * beat, 0.45)
    t += bar; b += 1
mix = mix[:int(SR * dur)]; fade = np.clip((len(mix) - np.arange(len(mix))) / SR, 0, 1); mix *= fade
mix = mix / max(1e-6, np.abs(mix).max()) * 0.9
w = wave.open(out, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype('<i2').tobytes()); w.close()
print('ok', out)
