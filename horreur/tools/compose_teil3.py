# Montage de « Die letzte U-Bahn – Teil 3 » : accroche son (freins + alarme) dès la 1re image, flashs, glitch et voix grave
# doublée sur « Jetzt bin ich dran », pas de course, cartes 1/2.
# Montage final d'un épisode d'horreur rendu en 3D : images (frames/f%05d.jpg) + sous-titres mot à mot
# + carte du choix (1 / 2) + vignette et grain + voix, musique et bruitages synthétisés.
# usage : compose.py dossier_episode dossier_frames sortie.mp4
import sys, os, json, re, math, subprocess, shutil, wave
import numpy as np
from multiprocessing import Pool
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
EP, FR, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
W, H, FPS, SR = 1080, 1920, 30, 44100
FONT = '/home/user/skillora./temu/fonts/Poppins-ExtraBold.ttf'
WORDS = json.load(open(os.path.join(EP, 'words.json')))
CFG = json.load(open(os.path.join(EP, 'compose.json')))
K = CFG['k']
NF = len([f for f in os.listdir(FR) if f.endswith('.jpg')]); DUR = NF / FPS
def F(sz): return ImageFont.truetype(FONT, sz)
def clean(w): return re.sub(r'[„“"»«]', '', w).upper()
def word_at(t):
    for i, (w, a, b) in enumerate(WORDS):
        nxt = WORDS[i + 1][1] if i + 1 < len(WORDS) else b + 0.6
        if a - 0.04 <= t < min(nxt, b + 0.6): return clean(w), t - a
    return None, 0
yy, xx = np.mgrid[0:H, 0:W]; VIG = (1 - 0.38 * (((xx - W / 2) / (W / 2)) ** 2 * 0.6 + ((yy - H / 2) / (H / 2)) ** 2 * 0.5)).clip(0.55, 1)[..., None].astype(np.float32); del yy, xx
def card(img, t):
    # choix final : deux cartes qui s'allument quand la voix dit « Eins » / « Zwei »
    if t < K['eins'] - 0.2: return
    d = ImageDraw.Draw(img, 'RGBA')
    for j, (num, txt, t0) in enumerate(((1, 'ZURÜCK IN DEN TUNNEL', K['eins']), (2, 'MIT IHM REDEN', K['zwei']))):
        if t < t0 - 0.2: continue
        u = min(1, (t - t0 + 0.2) / 0.25); y = 560 + j * 190; on = t0 - 0.2 <= t < (K['zwei'] - 0.2 if j == 0 else K['schreib'])
        x0 = int(W / 2 - 400 + (1 - u) * -300)
        d.rounded_rectangle([x0, y, x0 + 800, y + 150], 28, fill=(200, 20, 20, int(230 * u)) if on else (15, 15, 18, int(215 * u)), outline=(255, 255, 255, int(255 * u)), width=5)
        d.ellipse([x0 + 25, y + 22, x0 + 131, y + 128], fill=(255, 255, 255, int(255 * u)))
        d.text((x0 + 78, y + 77), str(num), font=F(74), fill=(15, 15, 18, int(255 * u)), anchor='mm')
        d.text((x0 + 470, y + 78), txt, font=F(70 if len(txt) < 12 else 50), fill=(255, 255, 255, int(255 * u)), anchor='mm')
def ssf(a, b, x): u = min(1, max(0, (x - a) / (b - a))); return u * u * (3 - 2 * u)
def render(n):
    t = n / FPS
    a = np.asarray(Image.open(f'{FR}/f{n:05d}.jpg').convert('RGB')).astype(np.float32)
    rs = np.random.RandomState(n); a = a * VIG + rs.normal(0, 2.0, (H, W, 1))
    for t0, col, k in ((0.0, (255, 40, 30), 0.7), (K['fliegst'] - 0.05, (255, 255, 255), 0.75), (K['gesicht'], (255, 255, 255), 0.8)):   # flashs
        if t0 <= t < t0 + 0.12: u = 1 - (t - t0) / 0.12; a = a * (1 - k * u) + np.array(col) * k * u
    if K['jetzt'] <= t < K['also'] or K['gesicht'] <= t < K['gesicht'] + 0.25:   # glitch
        o = int(10 + 14 * rs.rand()); a[..., 0] = np.roll(a[..., 0], o, 1); a[..., 2] = np.roll(a[..., 2], -o, 1)
        for _ in range(3):
            y = rs.randint(0, H - 80); h = rs.randint(8, 60); a[y:y + h] = np.roll(a[y:y + h], rs.randint(-80, 80), 1)
    if t > DUR - 0.9: a *= max(0, (DUR - t) / 0.9)
    img = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert('RGBA'); d = ImageDraw.Draw(img)
    card(img, t)
    w, dt = word_at(t)
    if w and t < DUR - 0.9:
        s = 1 + 0.18 * max(0, 1 - dt / 0.09); f = F(int(92 * s)); red = K['jetzt'] - 0.05 <= t < K['also']
        d.text((W / 2, 1290), w, font=f, fill=(235, 30, 30) if red else (255, 255, 255), anchor='mm', stroke_width=10, stroke_fill=(0, 0, 0))
    if t < 2.2: d.text((70, 230), 'TEIL 3', font=F(46), fill=(255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0))
    if t > DUR - 1.6:
        u = min(1, (t - (DUR - 1.6)) / 0.4); d.text((W / 2, H / 2), 'TEIL 4?', font=F(130), fill=(220, 30, 30, int(255 * u)), anchor='mm', stroke_width=8, stroke_fill=(0, 0, 0, int(255 * u)))
    img.convert('RGB').save(f'{TMP}/g{n:05d}.jpg', quality=93)
# ---------- son
def load(f):
    return np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', f, '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(np.float32) / 32768
def lp(x, k):   # moyenne glissante = passe-bas simple (même longueur)
    c = np.cumsum(np.concatenate([np.zeros(k), x])); return ((c[k:] - c[:-k]) / k).astype(np.float32)
def noise(d, seed): return np.random.RandomState(seed).normal(0, 1, int(d * SR)).astype(np.float32)
def env(n, att, rel):
    e = np.ones(n, np.float32); a = int(att * SR); r = int(rel * SR)
    if a: e[:a] = np.linspace(0, 1, a)
    if r: e[-r:] *= np.linspace(1, 0, r)
    return e
def put(m, s, t0, g):
    a0 = int(t0 * SR); L = min(len(s), len(m) - a0)
    if L > 0 and a0 >= 0: m[a0:a0 + L] += s[:L] * g
def rumble(d, seed, f=90):
    x = lp(noise(d, seed), max(2, SR // (f * 2))); x /= np.abs(x).max() + 1e-9; return x
def audio(path):
    n = int(DUR * SR); m = np.zeros(n, np.float32)
    v = load(os.path.join(EP, 'voix_clean.mp3')); put(m, v, 0, 1.0)
    mu = load(os.path.join(EP, 'musique.mp3')); mu = np.tile(mu, int(n / len(mu)) + 1)[:n]; mu /= np.abs(mu).max() + 1e-9
    ve = np.abs(np.pad(v, (0, max(0, n - len(v))))[:n]); ve = lp(ve, 4410); duck = 1 - 0.45 * np.clip(ve / (ve.max() * 0.25), 0, 1)
    fx = np.zeros(n, np.float32)
    ar = lambda d: np.arange(int(d * SR)) / SR
    def tone(f, d): return np.sin(2 * np.pi * f * ar(d)).astype(np.float32)
    sq = np.sin(2 * np.pi * np.cumsum(3100 + 600 * np.sin(ar(5.6) * 31) - 200 * ar(5.6)) / SR).astype(np.float32)
    sq = (sq + 0.6 * noise(5.6, 41) * 0.3) * env(len(sq), 0.01, 1.2); put(fx, sq, 0.0, 0.16)                   # crissement de freins dès la 1re image
    put(fx, rumble(5.8, 42) * env(int(5.8 * SR), 0.01, 1.5), 0.0, 0.9)                                         # grondement
    boom = (np.sin(2 * np.pi * np.cumsum(np.linspace(90, 35, int(1.4 * SR))) / SR) * np.exp(-ar(1.4) * 2.5)).astype(np.float32)
    put(fx, boom, K['fliegst'] - 0.05, 0.9); put(fx, rumble(0.4, 43, 250) * env(int(0.4 * SR), 0.002, 0.3), K['fliegst'] - 0.05, 0.6)   # choc
    t = 0.0                                                                                                     # alarme deux tons
    while t < K['rennst'] + 2.5:
        b = np.concatenate([tone(950, 0.25), tone(700, 0.25)]) * 0.5; put(fx, b * env(len(b), 0.005, 0.02), t, 0.07 if t < K['rotes'] else 0.11); t += 0.55
    hs = lp(noise(1.0, 5), 3) * env(int(1.0 * SR), 0.02, 0.6); put(fx, hs, K['tueren'], 0.14)                 # portes
    # (pas de bruits de pas : retirés à la demande)
    put(fx, boom, K['gesicht'] - 0.02, 1.0)                                                                     # « dein Gesicht »
    def heart(t0, t1, g=0.5, per=0.62):
        t = t0
        while t < t1:
            b = tone(55, 0.16) * np.exp(-ar(0.16) * 25); put(fx, b, t, g); put(fx, b, t + 0.22, g * 0.6); t += per
    heart(K['schon'], K['gesicht'], 0.45, 0.7); heart(K['also'], DUR - 1, 0.45, 0.55)
    # voix grave et lente doublée sous « Jetzt bin ich dran »
    a0, a1 = int(K['jetzt'] * SR), int(K['also'] * SR); seg = v[a0:a1]
    low = np.interp(np.arange(0, len(seg), 0.78), np.arange(len(seg)), seg).astype(np.float32)
    put(fx, low * env(len(low), 0.02, 0.2), K['jetzt'] - 0.02, 0.55)
    wh = noise(1.6, 7); wh = wh - lp(wh, 41); wh *= env(len(wh), 0.3, 0.6); put(fx, wh, K['jetzt'] - 0.2, 0.05)
    out = np.pad(v, (0, max(0, n - len(v))))[:n] + mu * 0.16 * duck + fx
    fd = min(n, int(0.9 * SR)); out[-fd:] *= np.linspace(1, 0, fd); out = out / max(1e-6, np.abs(out).max()) * 0.95
    wo = wave.open(path, 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((out * 32767).astype('<i2').tobytes()); wo.close()
TMP = OUT + '_tmp'
if __name__ == '__main__':
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
    with Pool(4) as p: p.map(render, range(NF), chunksize=20)
    audio(f'{TMP}/a.wav')
    subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{TMP}/g%05d.jpg', '-i', f'{TMP}/a.wav', '-c:v', 'libx264', '-preset', 'slow', '-crf', '21', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
    shutil.rmtree(TMP); print('ok', OUT, round(DUR, 2))
