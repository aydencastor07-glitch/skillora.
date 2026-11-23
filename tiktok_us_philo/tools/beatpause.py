# Ajoute des pauses dans une voix trop rapide, calées sur le tempo de la musique : chaque phrase démarre sur un temps,
# chaque respiration en milieu de phrase sur un demi-temps ; longue pause (marteau) après le titre.
import json, subprocess, wave, numpy as np, imageio_ffmpeg, librosa
FF = imageio_ffmpeg.get_ffmpeg_exe(); SR = 44100
v = np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', 'voix_clean.mp3', '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(float) / 32768
W = json.load(open('words.json'))
import os
y, sr = librosa.load(os.environ.get('MUS', '../law01_v2/musique.wav'), sr=22050); tempo, b = librosa.beat.beat_track(y=y, sr=sr); bt = librosa.frames_to_time(b, sr=sr)
per = float(np.median(np.diff(bt))); grid = sorted([bt[0] - per * k for k in range(1, 400) if bt[0] - per * k >= 0] + list(bt) + [bt[-1] + per * k for k in range(1, 200)])
half = sorted(grid + [g + per / 2 for g in grid])
# coupures : (index du mot qui commence le morceau, type)
CUT = {int(k): v for k, v in json.loads(os.environ['CUT']).items()} if os.environ.get('CUT') else {3: 'gavel', 6: 's', 14: 's', 18: 's', 22: 's', 29: 'm', 33: 's', 35: 'm', 39: 'm', 41: 'm', 44: 's', 49: 's', 53: 's', 57: 's', 63: 'm', 66: 's'}
hop = int(0.01 * SR); env = np.array([np.sqrt(np.mean(v[i:i + hop] ** 2)) for i in range(0, len(v) - hop, hop)])
def quiet(a, b):
    i0, i1 = int(a / 0.01), max(int(a / 0.01) + 1, int(b / 0.01)); return (i0 + int(np.argmin(env[i0:i1]))) * 0.01
starts = [0] + sorted(CUT); cuts = [0.0]
for i in sorted(CUT): cuts.append(quiet(W[i - 1][2] - 0.04, W[i][1] + 0.02))
cuts.append(len(v) / SR)
out = []; pos = 0.0; NW = [None] * len(W); gav = None
for k, s in enumerate(starts):
    c0, c1 = cuts[k], cuts[k + 1]; lead = W[s][1] - c0
    kind = CUT.get(s); gap = {'gavel': 1.0, 's': 0.42, 'm': 0.18}.get(kind, 0.0)
    if k == 0: on = 0.15 + lead
    else:
        need = pos + gap + lead; G = half if kind == 'm' else grid; on = min(g for g in G if g >= need - 0.03)
        if kind == 'gavel': gav = pos + 0.05
    t0 = on - lead; seg = v[int(c0 * SR):int(c1 * SR)].copy(); f = int(0.008 * SR); seg[:f] *= np.linspace(0, 1, f); seg[-f:] *= np.linspace(1, 0, f)
    e = k + 1 < len(starts) and starts[k + 1] or len(W)
    for j in range(s, e): NW[j] = [W[j][0], round(W[j][1] - c0 + t0, 3), round(W[j][2] - c0 + t0, 3)]
    out.append((t0, seg)); pos = t0 + (c1 - c0) - 0.0
    lastw = NW[e - 1][2]; pos = max(lastw, t0 + (W[e - 1][2] - c0))
n = int((out[-1][0] + len(out[-1][1]) / SR + 0.1) * SR); m = np.zeros(n)
for t0, seg in out: a = int(t0 * SR); m[a:a + len(seg)] += seg
wo = wave.open('voix_final.wav', 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((np.clip(m, -1, 1) * 32767).astype('<i2').tobytes()); wo.close()
json.dump(NW, open('words_final.json', 'w'), indent=0)
never = NW[3][1]; json.dump({'gavel_t': round(gav, 3), 'gavel_dur': round(never - 0.08 - gav, 3), 'tempo': float(np.atleast_1d(tempo)[0]), 'dur': n / SR}, open('timing.json', 'w'))
print('tempo', tempo, 'durée', round(n / SR, 2)); print(' '.join(f'{w[0]}@{w[1]:.2f}' for w in NW)); print(open('timing.json').read())
