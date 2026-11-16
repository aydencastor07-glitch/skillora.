# Style « Ascend × Gesetz » (compte US philo, TikTok + Instagram), format carré 1080×1080.
# Fond noir, une phrase à la fois en capitales gravées (Cinzel) qui apparaissent mot par mot avec la voix, mot clé en or ;
# images sombres révélées par une fissure / diagonale / iris / volet, zoom lent, grain ; coup de marteau au titre ;
# frappes graves à chaque image, silence avant la citation, montée puis DROP sur la phrase finale.
# usage : ascend.py dossier sortie.mp4   (lit dossier/plan.json, words.json, voix_clean.mp3)   PREVIEW=t1,t2 pour des images
import sys, os, json, math, re, subprocess, shutil, wave
import numpy as np
from multiprocessing import Pool
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
D, OUT = sys.argv[1], sys.argv[2]
W = H = 1080; FPS = 30; SR = 44100
PLAN = json.load(open(os.path.join(D, 'plan.json'))); WORDS = json.load(open(os.path.join(D, 'words.json')))
FONT = '/home/user/skillora./temu/fonts/Cinzel.ttf'
GOLD = (222, 184, 98); WHITE = (238, 234, 226)
DUR = PLAN['dur']
def F(sz): return ImageFont.truetype(FONT, int(sz))
def clamp(u): return max(0.0, min(1.0, u))
def ease(u): u = clamp(u); return u * u * (3 - 2 * u)
def cw(w): return re.sub(r"[^\w']", '', w).lower()
def find(word, n=0, end=False):
    m = [x for x in WORDS if cw(x[0]) == word.lower()]
    return (m[n][2] if end else m[n][1]) if len(m) > n else None
# ---- images : recadrées en carré, légèrement plus grandes pour le zoom lent
IMG = {}
def img(name):
    if name not in IMG:
        im = Image.open(os.path.join(D, 'img', name)).convert('RGB'); s = 1.12 * W / min(im.size)
        im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
        IMG[name] = im
    return IMG[name]
yy, xx = np.mgrid[0:H, 0:W]
VIG = (1 - 0.55 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / 2).clip(0.25, 1)[..., None].astype(np.float32)
GRAD = np.clip((yy - H * 0.45) / (H * 0.5), 0, 1)[..., None].astype(np.float32)   # assombrit le bas pour le texte
def mask(kind, u, seed=0):
    # masque de révélation (0 → 1) : fissure, diagonale, iris, volet
    u = ease(u)
    if u >= 1: return None
    if kind == 'iris':
        r = u * 0.9 * W; return ((xx - W / 2) ** 2 + (yy - H / 2) ** 2 < r * r).astype(np.float32)
    if kind == 'diag':
        return ((xx + yy) < u * 2.1 * W).astype(np.float32)
    if kind == 'wipe':
        return (yy > H * (1 - u * 1.05)).astype(np.float32)
    if kind == 'crack':   # fissure en zigzag qui s'ouvre depuis le centre
        rs = np.random.RandomState(seed); pts = np.cumsum(rs.uniform(-60, 60, 12)); line = np.interp(yy, np.linspace(0, H, 12), W / 2 + pts)
        return (np.abs(xx - line) < u * W * 0.75).astype(np.float32)
    return np.ones((H, W), np.float32) * u
def picture(name, t, t0, t1, kind, zoom=(1.0, 1.08), seed=0):
    im = img(name); k = clamp((t - t0) / max(0.1, t1 - t0)); z = zoom[0] + (zoom[1] - zoom[0]) * k
    cw_, ch_ = im.width / (z * 1.12), im.height / (z * 1.12)
    cx, cy = im.width / 2 + 10 * math.sin(t * 0.3 + seed), im.height / 2 + 8 * math.cos(t * 0.25 + seed)
    a = np.asarray(im.resize((W, H), Image.BILINEAR, box=(cx - cw_ / 2, cy - ch_ / 2, cx + cw_ / 2, cy + ch_ / 2))).astype(np.float32)
    m = mask(kind, (t - t0) / 0.55, seed)
    if m is not None: a = a * m[..., None]
    return a
def text_layer(img_, words, t, y, size, gold=(), big=False, alpha=1.0):
    # la phrase apparaît mot par mot quand la voix les dit (petit fondu + léger glissement)
    f = F(size); d = ImageDraw.Draw(img_); toks = [(w, a) for w, a in words]
    lines, cur, wsp = [], [], f.getbbox(' ')[2]
    for w, a in toks:
        tw = f.getbbox(w)[2]
        if cur and sum(f.getbbox(x)[2] for x, _ in cur) + wsp * len(cur) + tw > W - 160: lines.append(cur); cur = []
        cur.append((w, a))
    if cur: lines.append(cur)
    lh = size * 1.32; y0 = y - lh * (len(lines) - 1) / 2
    for li, L in enumerate(lines):
        tot = sum(f.getbbox(w)[2] for w, _ in L) + wsp * (len(L) - 1); x = W / 2 - tot / 2
        for w, a in L:
            k = clamp((t - a + 0.08) / 0.22) * alpha
            if k > 0:
                col = GOLD if re.sub(r'[^A-Z]', '', w) in gold else WHITE
                yy_ = y0 + li * lh + 10 * (1 - k)
                d.text((x, yy_), w, font=f, fill=col + (int(255 * k),), anchor='lm', stroke_width=2 if big else 1, stroke_fill=(0, 0, 0, int(200 * k)))
            x += f.getbbox(w)[2] + wsp
def frame(n):
    t = n / FPS; a = np.zeros((H, W, 3), np.float32); cards = PLAN['cards']
    c = next((c for c in cards if c['t0'] <= t < c['t1']), None)
    shake = 0
    if c:
        if c.get('img'):
            a = picture(c['img'], t, c['t0'], c['t1'], c.get('reveal', 'iris'), tuple(c.get('zoom', (1.0, 1.08))), c.get('seed', 0))
            a *= c.get('bright', 1.0)
            out = clamp((c['t1'] - t) / 0.18); a *= out
            a = a * (1 - 0.65 * GRAD) if c.get('text_y', 820) > 600 else a
        for fl in PLAN.get('flash', []):
            if fl <= t < fl + 0.14: u = 1 - (t - fl) / 0.14; a = a * (1 - 0.8 * u) + 255 * 0.8 * u
        for dr in PLAN.get('drop', []):
            if dr <= t < dr + 0.5: shake = 14 * (1 - (t - dr) / 0.5)
    a = a * VIG + np.random.RandomState(n).normal(0, 2.5, (H, W, 1))
    if t > DUR - 0.6: a *= clamp((DUR - t) / 0.6)
    im = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    if shake: im = im.transform(im.size, Image.AFFINE, (1, 0, math.sin(t * 90) * shake, 0, 1, math.cos(t * 70) * shake))
    im = im.convert('RGBA')
    if c and c.get('words'):
        ws = [(w, find(*k) if isinstance(k, list) else k) for w, k in c['words']]
        al = clamp((c['t1'] - t) / 0.2)
        text_layer(im, ws, t, c.get('text_y', 820), c.get('size', 54), set(c.get('gold', [])), c.get('big', False), al)
    if c and c.get('label'):
        k = clamp((t - c['t0']) / 0.4) * clamp((c['t1'] - t) / 0.2); d = ImageDraw.Draw(im)
        d.text((W / 2, 140), c['label'], font=F(30), fill=GOLD + (int(220 * k),), anchor='mm')
    return im.convert('RGB')
def render(n): frame(n).save(f'{TMP}/f{n:05d}.jpg', quality=93)
# ---------- son
def load(f, sr=SR):
    a = np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', f, '-ac', '1', '-ar', str(sr), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(np.float32) / 32768
    return a
def put(m, s, t0, g):
    a0 = int(t0 * SR); s0 = 0
    if a0 < 0: s0 = -a0; a0 = 0
    L = min(len(s) - s0, len(m) - a0)
    if L > 0: m[a0:a0 + L] += s[s0:s0 + L] * g
def env(n, att, rel):
    e = np.ones(n, np.float32); a, r = int(att * SR), int(rel * SR)
    if a: e[:a] = np.linspace(0, 1, a)
    if r: e[-r:] *= np.linspace(1, 0, r)
    return e
def boom(d=1.6, f0=70, f1=32):
    n = int(d * SR); ph = 2 * np.pi * np.cumsum(np.linspace(f0, f1, n)) / SR; return (np.sin(ph) * np.exp(-np.arange(n) / SR * 2.6)).astype(np.float32)
def lp(x, k): c = np.cumsum(np.concatenate([np.zeros(k), x])); return ((c[k:] - c[:-k]) / k).astype(np.float32)
def audio(path):
    n = int(DUR * SR); out = np.zeros(n, np.float32); A = PLAN['audio']
    v = load(os.path.join(D, 'voix_clean.mp3')); vv = np.zeros(n, np.float32); put(vv, v, A.get('voice_at', 0), 1.0)
    ve = lp(np.abs(vv), 4410); duck = 1 - 0.55 * np.clip(ve / (ve.max() * 0.22), 0, 1)
    mus = np.zeros(n, np.float32)
    for seg in A['music']:   # {file, src0, at, t1, gain, fin, fout}
        s = load(os.path.join(D, seg['file']) if not seg['file'].startswith('/') else seg['file'])
        s = s / (np.abs(s).max() + 1e-9); a0 = int(seg['src0'] * SR); L = int((seg['t1'] - seg['at']) * SR)
        part = s[a0:a0 + L]; part = part * env(len(part), seg.get('fin', 0.5), seg.get('fout', 0.8)); put(mus, part, seg['at'], seg['gain'])
    out += vv * 1.0 + mus * duck
    for t in A.get('booms', []): put(out, boom(), t, 0.55)
    if A.get('gavel'):
        g = load(A['gavel']['file']); put(out, g / (np.abs(g).max() + 1e-9), A['gavel']['t'], 0.8)
    for r in A.get('riser', []):   # bruit qui monte avant le drop
        d = r[1] - r[0]; x = np.random.RandomState(3).normal(0, 1, int(d * SR)).astype(np.float32); x = x - lp(x, 30)
        x *= np.linspace(0, 1, len(x)) ** 2; put(out, x, r[0], 0.12)
    for t in PLAN.get('drop', []): put(out, boom(2.2, 90, 28), t, 0.9)
    fd = int(0.7 * SR); out[-fd:] *= np.linspace(1, 0, fd); out = out / max(1e-6, np.abs(out).max()) * 0.95
    wo = wave.open(path, 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((out * 32767).astype('<i2').tobytes()); wo.close()
TMP = OUT + '_tmp'
if __name__ == '__main__':
    if os.environ.get('PREVIEW'):
        for ts in os.environ['PREVIEW'].split(','): frame(int(float(ts) * FPS)).save(f'{OUT}_{ts}.jpg', quality=88)
        sys.exit(0)
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
    with Pool(4) as p: p.map(render, range(int(DUR * FPS)), chunksize=15)
    audio(f'{TMP}/a.wav')
    subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{TMP}/f%05d.jpg', '-i', f'{TMP}/a.wav', '-c:v', 'libx264', '-preset', 'slow', '-crf', '22', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
    shutil.rmtree(TMP); print('ok', OUT, DUR)
