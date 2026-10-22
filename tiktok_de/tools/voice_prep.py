# Préparation de la voix off : assemble les parties dans l'ordre, égalise leur volume, raccourcit les silences trop longs
# (fondus aux raccords). usage : voice_prep.py sortie.mp3 partie1.mp3 partie2.mp3 ...  [MAXP=0.2 durée max d'une pause]
import sys, os, subprocess, wave
import numpy as np, imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe(); SR = 44100; out = sys.argv[1]; parts = sys.argv[2:]
MAXP = float(os.environ.get('MAXP', 0.2)); TARGET = -14.2          # volume moyen visé pendant la parole (dB)
def load(f): return np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', f, '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(float) / 32768
def speech_db(a):
    hop = 441; e = np.array([np.sqrt(np.mean(a[k:k + hop] ** 2)) for k in range(0, len(a) - hop, hop)]); sp = e[e > np.abs(a).max() * 0.03]
    return 20 * np.log10(np.sqrt(np.mean(sp ** 2)))
seq = []
for f in parts:
    a = load(f); g = TARGET - speech_db(a); a = a * 10 ** (g / 20); print(f'{os.path.basename(f)} : gain {g:+.1f} dB'); seq += [a, np.zeros(int(0.3 * SR))]
a = np.concatenate(seq); a = a / max(1, np.abs(a).max() / 0.98)
hop = int(SR * 0.01); e = np.array([np.sqrt(np.mean(a[i:i + hop] ** 2)) for i in range(0, len(a) - hop, hop)]); db = 20 * np.log10(e + 1e-6); sp = db > db.max() - 40
sil = []; i = 0; n = len(sp)
while i < n:
    if not sp[i]:
        j = i
        while j < n and not sp[j]: j += 1
        sil.append((i, j)); i = j
    else: i += 1
res = []; pos = 0
for s, e2 in sil:
    t0, t1 = s * 0.01, e2 * 0.01
    if s == 0: pos = int(max(0, t1 - 0.05) * SR); continue
    if e2 >= n: res.append(a[pos:int((t0 + 0.12) * SR)]); pos = None; break
    if t1 - t0 > MAXP + 0.04: res.append(a[pos:int((t0 + MAXP / 2) * SR)]); pos = int((t1 - MAXP / 2) * SR)
if pos is not None: res.append(a[pos:])
fd = int(0.012 * SR); out_a = []
for seg in res:
    seg = seg.copy(); f = min(len(seg) // 2, fd)
    if f > 0: seg[:f] *= np.linspace(0, 1, f); seg[-f:] *= np.linspace(1, 0, f)
    out_a.append(seg)
b = np.concatenate(out_a); print('brut', round(len(a) / SR, 2), 's → nettoyé', round(len(b) / SR, 2), 's')
tmp = out + '.tmp.wav'; w = wave.open(tmp, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(b, -1, 1) * 32767).astype('<i2').tobytes()); w.close()
subprocess.run([FF, '-y', '-v', 'error', '-i', tmp, '-b:a', '256k', out], check=True); os.remove(tmp)
