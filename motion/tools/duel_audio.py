# Bande son : phrases de la voix off replacées sur leurs scènes + musique douce + effets.
import json, sys, wave
import numpy as np
cfg = json.load(open(sys.argv[1])); ev = json.load(open(sys.argv[2])); voice = sys.argv[3]; out = sys.argv[4]
SR = 44100
w = wave.open(voice); v = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float) / 32768
if w.getnchannels() == 2: v = v.reshape(-1, 2).mean(1)
assert w.getframerate() == SR
dur = ev['dur']; N = int(SR * dur)
vo = np.zeros(N + SR)
for c in cfg['clips']:
    a, b = int((c['src'][0] - 0.06) * SR), int((c['src'][1] + 0.12) * SR)
    seg = v[max(0, a):b].copy(); f = int(0.02 * SR); seg[:f] *= np.linspace(0, 1, f); seg[-f:] *= np.linspace(1, 0, f)
    i = int((c['at'] - 0.06) * SR); vo[i:i + len(seg)] += seg[:len(vo) - i]
vo = vo[:N]
# musique + effets (réutilise le générateur du quiz), puis baisse sous la voix
BG = out + '.bg.wav'; OUT = out
sys.argv = ['', sys.argv[2], BG]
exec(open(__file__.replace('duel_audio.py', 'sound.py')).read())
out = OUT; N = len(vo)
w2 = wave.open(BG); bg = np.frombuffer(w2.readframes(w2.getnframes()), '<i2').astype(float).reshape(-1, 2)[:, 0] / 32768
bg = bg[:N]; bg = np.pad(bg, (0, N - len(bg)))
env = np.convolve(np.abs(vo) > 0.02, np.ones(int(0.25 * SR)) / int(0.25 * SR), 'same')
duck = 1 - 0.6 * np.clip(env * 3, 0, 1)
mix = vo * 1.0 + bg * 0.32 * duck
mix = mix / max(1e-6, np.abs(mix).max()) * 0.92
st = (np.stack([mix, mix], 1) * 32767).astype('<i2')
o = wave.open(out, 'wb'); o.setnchannels(2); o.setsampwidth(2); o.setframerate(SR); o.writeframes(st.tobytes()); o.close()
print('ok', dur)
