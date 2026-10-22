# Pauses dramatiques : insère un silence entre un mot et le suivant, dans le vrai creux de silence qui précède le mot suivant
# (jamais au milieu d'un son), avec fondus courts, puis décale les temps des mots qui suivent.
# Le début des mots est la donnée la plus fiable de l'alignement : on prend le dernier creux avant ce début. Chercher le point
# le plus silencieux d'une large zone peut tomber dans l'occlusion d'un « k » ou d'un « t » au milieu d'un mot (Ha|ken).
# usage : beats.py dossier 'mot:durée:nom[:n[:t_coupe]]' ...   (n = n-ième occurrence du mot, t_coupe = point de coupe imposé)
# lit voix_clean.mp3 + words.json, écrit voix_final.wav, words_final.json, beats.json
import sys, os, re, json, subprocess, wave
import numpy as np, imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe(); SR = 44100; D = sys.argv[1]; HOP = 0.005
v = np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', os.path.join(D, 'voix_clean.mp3'), '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(float) / 32768
W = json.load(open(os.path.join(D, 'words.json')))
def cw(w): return re.sub(r"[^\wäöüß'-]", '', w).lower()
h = int(HOP * SR); env = np.array([np.sqrt(np.mean(v[k:k + 2 * h] ** 2)) for k in range(0, len(v) - 2 * h, h)])
envdb = 20 * np.log10(env + 1e-9); sm = np.convolve(envdb, np.ones(3) / 3, 'same')       # niveau (dB) toutes les 5 ms
ins = []
for spec in sys.argv[2:]:
    p = spec.split(':'); word, dur, name = p[0], float(p[1]), p[2]; n = int(p[3]) if len(p) > 3 and p[3] else 0
    i = [k for k, x in enumerate(W) if cw(x[0]) == word.lower()][n]
    s1 = W[i + 1][1] if i + 1 < len(W) else len(v) / SR
    lo = max((W[i][1] + W[i][2]) / 2, s1 - 0.30); hi = s1 + 0.06
    k0, k1 = int(lo / HOP), int(hi / HOP); seg = sm[k0:k1]; thr = seg.max() - 18
    q = np.r_[False, seg < thr, False]; d = np.diff(q.astype(int)); runs = [(a, b) for a, b in zip(np.where(d == 1)[0], np.where(d == -1)[0]) if b - a >= 3]
    if len(p) > 4: k = int(float(p[4]) / HOP); how = 'imposé'
    elif runs: a, b = runs[-1]; k = k0 + a + int(np.argmin(seg[a:b])); how = 'creux'
    else: k = k0 + int(np.argmin(seg)); how = 'ATTENTION pas de creux net'
    t = k * HOP + HOP; ins.append((t, i, dur, name, round(float(envdb[k]), 1), how))
    print(f'{W[i][0]} → {W[i + 1][0] if i + 1 < len(W) else "fin"} : coupe {t:.3f} s ({how}, {envdb[k]:.1f} dB)')
    print('   ', ' '.join(('[' if kk == k else '') + f'{int(sm[kk])}' + (']' if kk == k else '') for kk in range(int((s1 - 0.35) / HOP), int((s1 + 0.15) / HOP))))
ins.sort(); out = []; prev = 0; shift = 0; beats = []; fd = int(0.01 * SR)
for t, i, dur, name, lvl, how in ins:
    seg = v[int(prev * SR):int(t * SR)].copy()
    if len(seg) > 2 * fd: seg[-fd:] *= np.linspace(1, 0, fd)
    if prev > 0 and len(seg) > 2 * fd: seg[:fd] *= np.linspace(0, 1, fd)
    out += [seg, np.zeros(int(dur * SR))]; beats.append({'name': name, 't': round(t + shift, 3), 'dur': dur, 'after': W[i][0], 'niveau_dB': lvl}); prev = t; shift += dur
    # le mot dure jusqu'au creux, le suivant ne peut pas commencer avant la coupe
    W[i][2] = max(W[i][2], round(t - 0.01, 3))
    if i + 1 < len(W): W[i + 1][1] = max(W[i + 1][1], round(t + 0.01, 3))
last = v[int(prev * SR):].copy(); last[:fd] *= np.linspace(0, 1, fd); out.append(last)
vv = np.concatenate(out)
def sh(j): return sum(d for t, i, d, *_ in ins if j > i)       # décalage d'un mot = pauses insérées avant lui
json.dump([[w, round(a + sh(j), 3), round(b + sh(j), 3)] for j, (w, a, b) in enumerate(W)], open(os.path.join(D, 'words_final.json'), 'w'), ensure_ascii=False, indent=0)
json.dump(beats, open(os.path.join(D, 'beats.json'), 'w'), indent=1, ensure_ascii=False)
w = wave.open(os.path.join(D, 'voix_final.wav'), 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(vv, -1, 1) * 32767).astype('<i2').tobytes()); w.close()
print('voix finale', round(len(vv) / SR, 2), 's')
