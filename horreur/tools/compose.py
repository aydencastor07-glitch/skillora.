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
    for j, (num, txt, t0) in enumerate(((1, 'EINSTEIGEN', K['eins']), (2, 'UMDREHEN', K['zwei']))):
        if t < t0 - 0.2: continue
        u = min(1, (t - t0 + 0.2) / 0.25); y = 560 + j * 190; on = t0 - 0.2 <= t < (K['zwei'] - 0.2 if j == 0 else K['schreib'])
        x0 = int(W / 2 - 400 + (1 - u) * -300)
        d.rounded_rectangle([x0, y, x0 + 800, y + 150], 28, fill=(200, 20, 20, int(230 * u)) if on else (15, 15, 18, int(215 * u)), outline=(255, 255, 255, int(255 * u)), width=5)
        d.ellipse([x0 + 25, y + 22, x0 + 131, y + 128], fill=(255, 255, 255, int(255 * u)))
        d.text((x0 + 78, y + 77), str(num), font=F(74), fill=(15, 15, 18, int(255 * u)), anchor='mm')
        d.text((x0 + 470, y + 78), txt, font=F(70), fill=(255, 255, 255, int(255 * u)), anchor='mm')
def render(n):
    t = n / FPS
    a = np.asarray(Image.open(f'{FR}/f{n:05d}.jpg').convert('RGB')).astype(np.float32)
    rs = np.random.RandomState(n); a = a * VIG + rs.normal(0, 2.0, (H, W, 1))
    if t > DUR - 0.9: a *= max(0, (DUR - t) / 0.9)
    img = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert('RGBA')
    card(img, t)
    w, dt = word_at(t)
    if w and t < DUR - 0.9:
        s = 1 + 0.18 * max(0, 1 - dt / 0.09); f = F(int(92 * s))
        d = ImageDraw.Draw(img); d.text((W / 2, 1290), w, font=f, fill=(255, 255, 255), anchor='mm', stroke_width=10, stroke_fill=(0, 0, 0))
    if t < 2.2: ImageDraw.Draw(img).text((70, 230), 'TEIL 1', font=F(46), fill=(255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0))
    if t > DUR - 1.6:
        u = min(1, (t - (DUR - 1.6)) / 0.4); ImageDraw.Draw(img).text((W / 2, H / 2), 'TEIL 2?', font=F(130), fill=(220, 30, 30, int(255 * u)), anchor='mm', stroke_width=8, stroke_fill=(0, 0, 0, int(255 * u)))
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
    put(fx, rumble(4, 1) * env(int(4 * SR), 0.05, 2.5), 0, 0.5)                          # rame qui part
    t = K['gitter']; g = rumble(1.8, 2, 400) * env(int(1.8 * SR), 0.05, 0.4) * (1 + 0.6 * np.sign(np.sin(np.arange(int(1.8 * SR)) / SR * 2 * np.pi * 14))); put(fx, g, t, 0.25)   # grille
    k = np.zeros(int(0.06 * SR), np.float32); k[:200] = np.random.RandomState(3).normal(0, 1, 200); put(fx, k, K['drei'], 0.5)   # clac du tableau
    d = K['tueren'] - K['kommt'] + 0.6; put(fx, rumble(d, 4) * env(int(d * SR), 1.2, 0.6), K['kommt'] - 0.3, 0.7)              # rame qui arrive
    sq = np.sin(2 * np.pi * np.cumsum(np.linspace(2600, 1900, int(1.2 * SR))) / SR).astype(np.float32) * env(int(1.2 * SR), 0.2, 0.5); put(fx, sq, K['tueren'] - 1.3, 0.05)   # freins
    hs = lp(noise(1.0, 5), 3) * env(int(1.0 * SR), 0.02, 0.6); put(fx, hs, K['tueren'], 0.12)                                 # portes
    bz = (np.sin(2 * np.pi * 100 * np.arange(int(1.4 * SR)) / SR) * (np.random.RandomState(6).rand(int(1.4 * SR)) > 0.4)).astype(np.float32) * env(int(1.4 * SR), 0.02, 0.3); put(fx, bz, K['drei'], 0.05); put(fx, bz, K['flue'] - 0.2, 0.06)
    wh = noise(2.2, 7); wh = wh - lp(wh, 41); wh *= (0.5 + 0.5 * np.sin(np.arange(len(wh)) / SR * 2 * np.pi * 3.2)) ** 2 * env(len(wh), 0.4, 0.8); put(fx, wh, K['flue'] - 0.1, 0.07)   # chuchotement
    t = K['flue']                                                                           # battements de cœur
    while t < DUR - 1:
        b = np.sin(2 * np.pi * 55 * np.arange(int(0.16 * SR)) / SR).astype(np.float32) * np.exp(-np.arange(int(0.16 * SR)) / SR * 25)
        put(fx, b, t, 0.55); put(fx, b, t + 0.22, 0.35); t += 0.78
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
