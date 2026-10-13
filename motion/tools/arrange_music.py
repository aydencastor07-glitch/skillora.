# Arrange une musique sur la vidéo : boucle invisible (raccord calé sur les battements), creux de la musique
# placé sur un moment fort, coupures, volume qui suit les scènes (médaillons plus forts, cartes plus calmes).
# usage : arrange_music.py music.wav long.json out.wav '<json options>'
#   options : {"break_m": 129.9, "break_v": 161.5, "cut": [[t0,t1],...], "outro_m": 158, "outro_v": 189.6}
import sys, json, wave
import numpy as np
mw, cfgp, out, opt = sys.argv[1], sys.argv[2], sys.argv[3], json.loads(sys.argv[4])
SR = 44100
w = wave.open(mw); x = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float).reshape(-1, w.getnchannels()) / 32768
if x.shape[1] == 1: x = np.repeat(x, 2, 1)
cfg = json.load(open(cfgp)); DUR = cfg['dur']; N = int(DUR * SR)
D = opt['break_v'] - opt['break_m']                       # retard à ajouter avant le creux
if D < 1.0:   # la vidéo arrive au creux plus tôt que la musique : on démarre la musique plus loin, sans boucle
    off = -D; y = x[int(off * SR):int(off * SR) + N]; y = np.pad(y, ((0, max(0, N - len(y))), (0, 0)))
    print('musique démarrée à', round(off, 2), 's ; creux → vidéo', opt['break_v'], '; outro → vidéo', round(opt['outro_m'] - off, 2))
    P = L = None
# --- point de boucle : là où la musique ressemble le plus à elle-même D secondes plus tôt
hop = 441; mono = x.mean(1); env = np.array([np.abs(mono[i:i + hop]).mean() for i in range(0, len(mono) - hop, hop)])
on = np.maximum(0, np.diff(env)); fps = SR / hop
best = (-1, 0, 0)
for P in ([] if D < 1.0 else np.arange(opt.get('loop_from', 60), opt.get('loop_to', opt['break_m'] - 12), 0.5)):     # P en temps musique (fin de la 1re lecture)
    Ls = [round(D / opt['phrase']) * opt['phrase']] if opt.get('phrase') else np.arange(D - 0.6, D + 0.6, 0.01)  # saut = nombre entier de phrases musicales
    for L in Ls:
        a, b = int(P * fps), int((P - L) * fps); n = int(6 * fps)
        if b < 0: continue
        u, v = on[a:a + n], on[b:b + n]; c = (u * v).sum() / (np.sqrt((u * u).sum() * (v * v).sum()) + 1e-9)
        if c > best[0]: best = (c, P, L)
if D >= 1.0:
  c, P, L = best; print('boucle : musique', round(P, 2), 's → reprend à', round(P - L, 2), 's (saut', round(L, 2), 's, ressemblance', round(c, 3), ')')
# --- carte temps vidéo → temps musique
def seg(m0, m1): return x[int(m0 * SR):int(m1 * SR)]
if D >= 1.0:
    parts = [seg(0, P), seg(P - L, opt['outro_m'])]           # 1re lecture, puis reprise jusqu'à la fin du corps
    v_outro = P + (opt['outro_m'] - (P - L))
    parts.append(seg(opt['outro_m'], opt['outro_m'] + max(0, DUR - v_outro) + 1))
    y = np.zeros((N + SR, 2)); pos = 0; XF = int(0.25 * SR)
    for k, p in enumerate(parts):
        p = p.copy()
        if k: r = np.linspace(0, 1, XF)[:, None]; p[:XF] *= r; y[pos - XF:pos] *= (1 - r)    # fondu enchaîné au raccord
        y[pos - (XF if k else 0):pos - (XF if k else 0) + len(p)] += p; pos += len(p) - (XF if k else 0)
    y = y[:N]; print('creux musical → vidéo', round(opt['break_m'] + L, 2), '(voulu', opt['break_v'], ') ; outro → vidéo', round(v_outro, 2))
# --- volume qui suit les scènes
t = np.arange(N) / SR; g = np.ones(N)
def ramp(a, b, val, fade=0.4):
    m = np.clip(np.minimum((t - a) / fade, (b - t) / fade) + 1, 0, 1); return 1 + (val - 1) * m
for s in cfg['scenes']:
    if s.get('medal'): g *= ramp(s['t0'] - 0.2, s['t1'] + 0.3, opt.get('medal_gain', 1.6))
    elif s.get('card'): g *= ramp(s['t0'] - 0.1, s['t1'], opt.get('card_gain', 0.75))
for a, b in opt.get('cut', []): g *= 1 - np.clip(np.minimum((t - a) / 0.08, (b - t) / 0.25) + 1, 0, 1)   # coupure nette, reprise douce
g *= np.clip(t / 1.0, 0, 1) * np.clip((DUR - t) / 3.0, 0, 1)                                      # fondu début / fin
y *= g[:, None]
y = y / max(1e-6, np.abs(y).max()) * 0.95
o = wave.open(out, 'wb'); o.setnchannels(2); o.setsampwidth(2); o.setframerate(SR); o.writeframes((y * 32767).astype('<i2').tobytes()); o.close()
print('ok', out, round(N / SR, 2), 's')
