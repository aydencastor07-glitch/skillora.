# Voix ep07 : chaque « BOING! » devient un cri punchy comme le « HUSS! » de la vidéo de référence :
#  - petite pause avant / pause après (le temps de voir la blague) ;
#  - le BOING du héros : plus fort + écho de salle ; les BOING de la ville : la voix + 3 copies (hauteurs différentes, légers décalages) = une foule ;
#  - un son de ressort « boing » (synthétisé) sous chaque BOING.
# Entrées : voix_base.mp3 + words_base.json  →  voix_clean.mp3 + words.json + env.json (ouverture de bouche, 30 i/s)
import json, subprocess, wave, os, numpy as np, imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe(); SR = 44100
def load(f, af=None):
    cmd = [FF, '-v', 'error', '-i', f] + (['-af', af] if af else []) + ['-ac', '1', '-ar', str(SR), '-f', 's16le', '-']
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, np.int16).astype(float) / 32768
v = load('voix_base.mp3'); W = json.load(open('words_base.json'))
COP = [load('voix_base.mp3', f'rubberband=pitch={2 ** (st / 12):.4f}:pitchq=quality') for st in (4, -3, 7)]
n = min(len(v), *(len(c) for c in COP)); v = v[:n]; COP = [c[:n] for c in COP]
B = [i for i, w in enumerate(W) if w[0].strip('".!?…,').lower() == 'boing']
HERO, FINAL = B[0], B[-1]; MID = [i for i in B if W[i][0].startswith('BOING') and i not in (HERO, FINAL) and not W[i][0].endswith('G')]   # « BOING is forbidden » reste normal
def spring(d=0.55):
    t = np.arange(int(d * SR)) / SR; f = 170 + 120 * t / d
    ph = 2 * np.pi * np.cumsum(f * (1 + 0.32 * np.exp(-5 * t) * np.sin(2 * np.pi * 15 * t))) / SR
    return (np.sin(ph) + 0.35 * np.sin(2 * ph)) * np.exp(-4.5 * t) * np.minimum(1, t / 0.008) * 0.32
def echo(x, d=0.09, g=0.35, k=3):
    o = x.copy()
    for j in range(1, k + 1):
        s = int(d * j * SR); o[s:] += x[:-s] * g ** j
    return o
out = []; pos = 0; shift = []; t_new = 0.0; NW = []
pre, post = 0.10, 0.32
for i, (w, a, b) in enumerate(W):
    if i in B and i != FINAL and i in [HERO] + MID:
        cut = int(max(a - 0.03, 0) * SR); out.append(v[pos:cut]); t_new += (cut - pos) / SR
        pr = 0.02 if (i - 1) in B and W[i - 1][0].startswith('BOING') else pre; out.append(np.zeros(int(pr * SR))); t_new += pr
        e = int(min(b + 0.06, len(v) / SR) * SR); seg = v[cut:e].copy()
        if i == HERO: seg = echo(seg * 1.5, 0.11, 0.3)
        else:
            L = len(seg); crowd = seg * 1.15
            for k, c in enumerate(COP): dl = int((0.012 + 0.017 * k) * SR); s2 = np.zeros(L); s2[dl:] = c[cut:e][:L - dl] * 0.55; crowd += s2
            seg = echo(crowd, 0.08, 0.25, 2)
        sp = spring(); L = max(len(seg), int(0.05 * SR) + len(sp)); m = np.zeros(L); m[:len(seg)] += seg; m[int(0.05 * SR):int(0.05 * SR) + len(sp)] += sp
        st = t_new; out.append(m); t_new += L / SR
        NW.append([w, round(st + 0.03, 3), round(st + (b - a) + 0.03, 3)])
        po = 0.06 if (i + 1) in B and W[i + 1][0].startswith('BOING') else post; out.append(np.zeros(int(po * SR))); t_new += po; pos = e
    else:
        off = t_new - pos / SR; NW.append([w, round(a + off, 3), round(b + off, 3)])
out.append(v[pos:]); a_ = np.concatenate(out)
# le dernier « …boing. » chuchoté : petit ressort discret
fa = NW[FINAL][1]; sp = spring(0.5) * 0.45; s0 = int((fa + 0.05) * SR); a_ = np.concatenate([a_, np.zeros(max(0, s0 + len(sp) - len(a_)))]); a_[s0:s0 + len(sp)] += sp
a_ = a_ / max(1, np.abs(a_).max() / 0.97)
with wave.open('voix_tmp.wav', 'wb') as f: f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR); f.writeframes((a_ * 32767).astype(np.int16).tobytes())
subprocess.run([FF, '-y', '-v', 'error', '-i', 'voix_tmp.wav', '-af', 'acompressor=threshold=-20dB:ratio=3:attack=5:release=80,loudnorm=I=-14:TP=-1.5', '-ar', '44100', '-b:a', '192k', 'voix_clean.mp3'], check=True)
os.remove('voix_tmp.wav'); json.dump(NW, open('words.json', 'w'))
# enveloppe de la voix (bouche) : une valeur par image
y = load('voix_clean.mp3'); hop = SR // 30; e = np.array([np.sqrt(np.mean(y[k:k + hop] ** 2)) for k in range(0, len(y) - hop, hop)]); e = np.clip(e / np.percentile(e, 95), 0, 1)
json.dump([round(float(x), 3) for x in e], open('env.json', 'w'))
print('voix', round(len(y) / SR, 2), 's ; BOING héros', HERO, 'foule', MID, 'final', FINAL)
