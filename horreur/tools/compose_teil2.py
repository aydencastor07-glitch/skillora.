# Montage de « Die letzte U-Bahn – Teil 2 » (même principe que compose.py) : noir quand la lumière s'éteint, « FALSCHE WAHL »,
# rembobinage (images rejouées à l'envers avec glitch), paupières qui se ferment, cartes NOTBREMSE / AUGEN ZU.
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
    for j, (num, txt, t0) in enumerate(((1, 'NOTBREMSE', K['eins']), (2, 'AUGEN ZU', K['zwei']))):
        if t < t0 - 0.2: continue
        u = min(1, (t - t0 + 0.2) / 0.25); y = 560 + j * 190; on = t0 - 0.2 <= t < (K['zwei'] - 0.2 if j == 0 else K['schreib'])
        x0 = int(W / 2 - 400 + (1 - u) * -300)
        d.rounded_rectangle([x0, y, x0 + 800, y + 150], 28, fill=(200, 20, 20, int(230 * u)) if on else (15, 15, 18, int(215 * u)), outline=(255, 255, 255, int(255 * u)), width=5)
        d.ellipse([x0 + 25, y + 22, x0 + 131, y + 128], fill=(255, 255, 255, int(255 * u)))
        d.text((x0 + 78, y + 77), str(num), font=F(74), fill=(15, 15, 18, int(255 * u)), anchor='mm')
        d.text((x0 + 470, y + 78), txt, font=F(70), fill=(255, 255, 255, int(255 * u)), anchor='mm')
def ssf(a, b, x): u = min(1, max(0, (x - a) / (b - a))); return u * u * (3 - 2 * u)
def src_time(t):
    # rembobinage : la fin de la scène (9,0 s) rejouée à l'envers jusqu'à 3,5 s, très vite
    if K['spulen'] <= t < K['diesmal'] - 0.15: return 9.0 - (t - K['spulen']) / (K['diesmal'] - 0.15 - K['spulen']) * 5.5
    return t
def tri(d, x, y, s, col):
    d.polygon([(x, y), (x + s, y - s * 0.6), (x + s, y + s * 0.6)], fill=col); d.polygon([(x + s, y), (x + 2 * s, y - s * 0.6), (x + 2 * s, y + s * 0.6)], fill=col)
def render(n):
    t = n / FPS; st = src_time(t); rew = st != t
    sn = min(NF - 1, max(0, int(round(st * FPS))))
    a = np.asarray(Image.open(f'{FR}/f{sn:05d}.jpg').convert('RGB')).astype(np.float32)
    rs = np.random.RandomState(n); a = a * VIG + rs.normal(0, 2.0, (H, W, 1))
    if not rew and K['licht'] - 0.2 <= t < K['spulen']: a *= 1 - ssf(K['licht'], K['aus'] + 0.2, t)          # la lumière s'éteint : noir
    if rew:   # VHS : décalage des couleurs, bandes, lignes
        a[..., 0] = np.roll(a[..., 0], 14, 1); a[..., 2] = np.roll(a[..., 2], -14, 1)
        for _ in range(6):
            y = rs.randint(0, H - 120); h = rs.randint(10, 90); a[y:y + h] = np.roll(a[y:y + h], rs.randint(-120, 120), 1)
        a[::4] *= 0.75; a = a * 0.9 + 18
    if abs(t - K['steht']) < 0.07: a = a * 0.4 + 255 * 0.6                                                     # flash
    ey = ssf(K['zwei'] + 0.6, K['zwei'] + 1.3, t) * (1 - ssf(K['schreib'] - 0.05, K['schreib'] + 0.25, t))     # paupières
    if ey > 0:
        hh = int(H / 2 * ey); a[:hh] *= 0.02; a[H - hh:] *= 0.02
    if t > DUR - 0.9: a *= max(0, (DUR - t) / 0.9)
    img = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert('RGBA')
    d = ImageDraw.Draw(img)
    if rew:
        tri(d, 90, 260, 46, (255, 255, 255)); d.text((210, 260), 'REWIND', font=F(52), fill=(255, 255, 255), anchor='lm')
    if K['falsche'] - 0.05 <= t < K['spulen']:
        u = min(1, (t - K['falsche'] + 0.05) / 0.15); j = rs.randint(-8, 9) if u >= 1 else 0
        d.text((W / 2 + j, H / 2 - 60), 'FALSCHE', font=F(150), fill=(225, 25, 25, int(255 * u)), anchor='mm', stroke_width=8, stroke_fill=(0, 0, 0))
        d.text((W / 2 - j, H / 2 + 110), 'WAHL', font=F(150), fill=(225, 25, 25, int(255 * u)), anchor='mm', stroke_width=8, stroke_fill=(0, 0, 0))
    card(img, t)
    w, dt = word_at(t)
    if w and t < DUR - 0.9 and not (K['falsche'] - 0.05 <= t < K['spulen']):
        s = 1 + 0.18 * max(0, 1 - dt / 0.09); f = F(int(92 * s))
        d.text((W / 2, 1290), w, font=f, fill=(255, 255, 255), anchor='mm', stroke_width=10, stroke_fill=(0, 0, 0))
    if t < 2.2: d.text((70, 230), 'TEIL 2', font=F(46), fill=(255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0))
    if t > DUR - 1.6:
        u = min(1, (t - (DUR - 1.6)) / 0.4); d.text((W / 2, H / 2), 'TEIL 3?', font=F(130), fill=(220, 30, 30, int(255 * u)), anchor='mm', stroke_width=8, stroke_fill=(0, 0, 0, int(255 * u)))
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
    def heart(t0, t1, g=0.55, per=0.78):
        t = t0
        while t < t1:
            b = np.sin(2 * np.pi * 55 * np.arange(int(0.16 * SR)) / SR).astype(np.float32) * np.exp(-np.arange(int(0.16 * SR)) / SR * 25)
            put(fx, b, t, g); put(fx, b, t + 0.22, g * 0.6); t += per
    boom = (np.sin(2 * np.pi * np.cumsum(np.linspace(90, 35, int(1.4 * SR))) / SR) * np.exp(-np.arange(int(1.4 * SR)) / SR * 2.5)).astype(np.float32)
    heart(K['du_drehst'], K['licht'], 0.5, 0.62)
    put(fx, boom, K['steht'] - 0.02, 0.9)                                                        # « da steht er »
    put(fx, rumble(0.5, 9, 300) * env(int(0.5 * SR), 0.005, 0.3), K['licht'], 0.5)              # clac : lumière coupée
    wh = noise(2.2, 7); wh = wh - lp(wh, 41); wh *= (0.5 + 0.5 * np.sin(np.arange(len(wh)) / SR * 2 * np.pi * 3.2)) ** 2 * env(len(wh), 0.4, 0.8); put(fx, wh, K['laechelt'] - 0.4, 0.08)   # souffle / rire étouffé
    L = K['diesmal'] - 0.15 - K['spulen']; sw = noise(L, 11); sw = sw - lp(sw, 6); sw *= np.linspace(0.2, 1, len(sw)); put(fx, sw, K['spulen'], 0.12)   # rembobinage
    put(fx, np.sin(2 * np.pi * np.cumsum(np.linspace(1800, 200, int(L * SR))) / SR).astype(np.float32) * env(int(L * SR), 0.05, 0.1), K['spulen'], 0.06)
    hs = lp(noise(1.0, 5), 3) * env(int(1.0 * SR), 0.02, 0.6); put(fx, hs, K['tueren'] + 0.1, 0.14)   # portes qui se ferment
    d = 24.2 - K['bahn']; put(fx, rumble(d, 4) * env(int(d * SR), 1.5, 0.8), K['bahn'], 0.75)          # la rame démarre et file
    d = K['haelt'] + 0.5 - 24.2; put(fx, rumble(d, 12) * env(int(d * SR), 0.6, 0.4), 24.2, 0.7)
    for k in range(3): put(fx, np.sin(2 * np.pi * (880 if k % 2 == 0 else 660) * np.arange(int(0.12 * SR)) / SR).astype(np.float32) * env(int(0.12 * SR), 0.005, 0.05), K['leuchtet'] + k * 0.16, 0.08)   # gong de l'annonce
    sq = np.sin(2 * np.pi * np.cumsum(np.linspace(2600, 1900, int(1.2 * SR))) / SR).astype(np.float32) * env(int(1.2 * SR), 0.2, 0.5); put(fx, sq, K['haelt'] - 1.0, 0.05)   # freins
    for k in range(9): put(fx, lp(noise(0.06, 20 + k), 2) * env(int(0.06 * SR), 0.005, 0.03), K['wer'] + k * 0.22, 0.05)   # feutre qui écrit
    for k in range(2): put(fx, rumble(0.25, 30 + k, 160) * env(int(0.25 * SR), 0.003, 0.2), K['und2'] + 0.55 + k * 0.45, 0.6)   # coups sur la porte
    heart(K['und2'], K['schreib'], 0.45, 0.55)
    put(fx, boom, K['schreib'] + 0.1, 0.8)                                                        # il est derrière lui
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
