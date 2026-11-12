# Montage « motivation » pro pour une vidéo face caméra (créole haïtien) :
#  - étalonnage contrasté (bleu/orange gardés), vignette, grain léger ;
#  - poussée lente + « punch-in » (zoom rapide) avec petite secousse sur les phrases fortes ;
#  - accroche en haut pendant les premières secondes ; sous-titres mot par mot (blanc, mot dit en jaune, mots forts en orange), au centre ;
#  - son : voix d'origine + musique de fond synthétisée (pad + piano + basse, baissée sous la voix) + whoosh / impacts sur les zooms.
# usage : montage_ht.py dossier  (lit dossier/config.json)
import sys, os, json, math, subprocess, shutil, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe(); D = sys.argv[1]; C = json.load(open(os.path.join(D, 'config.json')))
W, H, FPS, SR = 1080, 1920, 30, 44100
FD = '/home/user/skillora./temu/fonts/'; SFX = '/home/user/skillora./motion/sfx/'
WORDS = json.load(open(os.path.join(D, C['words']))); KEY = set(C['keywords'])
YEL = (255, 214, 0); ORA = (255, 138, 36); WH = (255, 255, 255)
_fc = {}
def F(n, s):
    if (n, int(s)) not in _fc: _fc[(n, int(s))] = ImageFont.truetype(FD + n, int(s))
    return _fc[(n, int(s))]
def clamp(u): return max(0.0, min(1.0, u))
def ease(u): u = clamp(u); return 1 - (1 - u) ** 3
def back(u): u = clamp(u); c = 1.9; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2
norm = lambda w: ''.join(ch for ch in w.lower() if ch.isalpha() or ch in 'èòà')
# ---- zoom : poussée lente + punch-in
PUNCH = C['punch']   # [[t, zoom], ...] : le zoom saute à t et redescend doucement
def zoom_at(t):
    z = 1.02 + 0.05 * t / C['dur']; sh = (0.0, 0.0)
    for k, (tp, zp) in enumerate(PUNCH):
        if t >= tp:
            nxt = PUNCH[k + 1][0] if k + 1 < len(PUNCH) else C['dur']
            u = (t - tp); a = ease(u / 0.12) * (1 - 0.6 * ease((u - 0.12) / max(0.3, nxt - tp - 0.2)))
            z += (zp - 1) * a
            if u < 0.25: amp = 14 * (1 - u / 0.25); sh = (amp * math.sin(u * 90), amp * math.cos(u * 70))
    return z, sh
# ---- étalonnage
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIG = (1 - 0.5 * (((xx - W / 2) / (W / 2)) ** 2 * 0.6 + ((yy - H * 0.45) / (H / 2)) ** 2 * 0.5)).clip(0.4, 1)[..., None]
del yy, xx
def grade(a):
    a = a / 255.0; l = a.mean(2, keepdims=True)
    a = l + (a - l) * 1.18                                     # saturation
    a = np.clip(a, 0, 1); a = a * a * (3 - 2 * a) * 0.55 + a * 0.45   # contraste (courbe en S)
    a[..., 2:] = np.clip(a[..., 2:] * 1.03 + (1 - l) * 0.03, 0, 1)    # ombres un peu bleutées
    return a * 255
# ---- textes
def outlined(d, xy, txt, f, fill, sw=8, anchor='mm'):
    d.text(xy, txt, font=f, fill=fill, anchor=anchor, stroke_width=sw, stroke_fill=(0, 0, 0, fill[3] if len(fill) > 3 else 255))
CH = []; cur = []
for i, (w, a, b) in enumerate(WORDS):
    cur.append(i)
    if w[-1] in ',.!?»' or len(cur) >= 3: CH.append(cur); cur = []
if cur: CH.append(cur)
def subs(img, t):
    for ci, ch in enumerate(CH):
        a = WORDS[ch[0]][1] - 0.06; b = CH[ci + 1] and WORDS[CH[ci + 1][0]][1] - 0.06 if ci + 1 < len(CH) else C['dur']
        if not (a <= t < b): continue
        lay = Image.new('RGBA', (W, 420), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        toks = [WORDS[i][0].replace('»', '').replace('«', '').strip().upper() for i in ch]
        f = F(C.get('font', 'Poppins-ExtraBold.ttf'), 100); sp = 30
        kk = [1.14 if norm(WORDS[i][0]) in KEY else 1.0 for i in ch]   # place réservée pour le mot fort agrandi
        ws = [f.getbbox(x)[2] * q for x, q in zip(toks, kk)]; tot = sum(ws) + sp * (len(ws) - 1)
        if tot > W - 110: f = F(C.get('font', 'Poppins-ExtraBold.ttf'), int(100 * (W - 110) / tot)); ws = [f.getbbox(x)[2] * q for x, q in zip(toks, kk)]; tot = sum(ws) + sp * (len(ws) - 1)
        x = W / 2 - tot / 2
        for i, tk, wd in zip(ch, toks, ws):
            st, en = WORDS[i][1], WORDS[i][2]
            if t >= st - 0.05:
                k = back((t - st + 0.05) / 0.16); now = st - 0.05 <= t < en + 0.08; key = norm(WORDS[i][0]) in KEY
                col = (ORA if key else YEL) if now or (key and t > en) else WH
                s = (1.12 if now and key else 1.0) * max(0.01, k)
                fl = F(C.get('font', 'Poppins-ExtraBold.ttf'), max(10, int(f.size * s)))
                outlined(d, (x + wd / 2, 210), tk, fl, col + (255,), sw=max(4, int(9 * s)))
            x += wd + sp
        sh = Image.new('RGBA', lay.size, (0, 0, 0, 0)); sh.putalpha(lay.getchannel('A').point(lambda v: int(v * 0.6))); sh = sh.filter(ImageFilter.GaussianBlur(12))
        y = C.get('sub_y', 1300); img.alpha_composite(sh, (0, y - 210 + 8)); img.alpha_composite(lay, (0, y - 210))
def hook(img, t):
    h = C.get('hook')
    if not h or t > h['t1']: return
    k = ease((t - 0.05) / 0.3) * (1 - ease((t - h['t1'] + 0.35) / 0.35))
    if k <= 0: return
    lay = Image.new('RGBA', (W, 400), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for j, l in enumerate(h['lines']):
        f = F('Anton-Regular.ttf', h.get('size', 120)); tw = f.getbbox(l)[2]
        if j == h.get('box_line', 1):
            d.rounded_rectangle([W / 2 - tw / 2 - 30, 70 + j * 150 - 10, W / 2 + tw / 2 + 30, 70 + j * 150 + 140], 18, fill=YEL + (255,))
            d.text((W / 2, 70 + j * 150 + 66), l, font=f, fill=(15, 15, 15, 255), anchor='mm')
        else: outlined(d, (W / 2, 70 + j * 150 + 66), l, f, WH + (255,), 9)
    s = 0.85 + 0.15 * back((t - 0.05) / 0.35); lay = lay.resize((int(W * s), int(400 * s)), Image.BICUBIC); a = lay.getchannel('A').point(lambda v: int(v * k)); lay.putalpha(a)
    img.alpha_composite(lay, (int(W / 2 - lay.width / 2), int(h.get('y', 300) - lay.height / 2)))
def flashk(t):
    return max([max(0, 1 - (t - f) / 0.12) for f in C.get('flash', []) if t >= f] + [0])
def render(n, src, out):
    t = n / FPS; im = Image.open(src).convert('RGB'); z, (sx, sy) = zoom_at(t)
    cw, ch = W / z, H / z; cx, cy = W / 2 + sx, H * C.get('zoom_cy', 0.42) + sy
    x0 = min(max(0, cx - cw / 2), W - cw); y0 = min(max(0, cy - ch * C.get('zoom_cy', 0.42)), H - ch)
    im = im.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
    a = grade(np.asarray(im).astype(np.float32)) * VIG + np.random.RandomState(n).normal(0, 3.5, (H, W, 1))
    fk = flashk(t); a = a * (1 - 0.5 * fk) + 255 * 0.5 * fk
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert('RGBA')
    hook(img, t); subs(img, t)
    d = ImageDraw.Draw(img); d.rectangle([0, H - 14, int(W * t / C['dur']), H - 8], fill=YEL + (230,))   # barre de progression fine
    img.convert('RGB').save(out, quality=93)
# ---- musique de fond (accords de motivation : Am – F – C – G)
def music(dur):
    n = int(dur * SR); tt = np.arange(n) / SR; bpm = C.get('bpm', 84); beat = 60 / bpm; bar = beat * 4
    chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]; out = np.zeros(n, np.float32)
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    for bi in range(int(dur / bar) + 1):
        t0 = bi * bar; cd = chords[bi % 4]; i0 = int(t0 * SR); L = min(n - i0, int(bar * SR) + int(0.4 * SR))
        if L <= 0: break
        u = np.arange(L) / SR; env = np.minimum(1, u / 0.6) * np.exp(-np.maximum(0, u - bar) * 6)
        pad = sum(np.sin(2 * np.pi * hz(m) * u) + 0.5 * np.sin(2 * np.pi * hz(m) * 1.003 * u) + 0.25 * np.sin(2 * np.pi * hz(m + 12) * u) for m in cd) * 0.06 * env
        bass = np.sin(2 * np.pi * hz(cd[0] - 24) * u) * 0.22 * np.minimum(1, u / 0.05) * np.exp(-u * 0.6)
        out[i0:i0 + L] += (pad + bass).astype(np.float32)
        for k in range(8):   # piano en croches (arpège)
            m = cd[[0, 1, 2, 1, 0, 2, 1, 2][k]] + 12; ts = t0 + k * beat / 2; j0 = int(ts * SR); Lp = min(n - j0, int(1.2 * SR))
            if Lp > 0: up = np.arange(Lp) / SR; out[j0:j0 + Lp] += (np.sin(2 * np.pi * hz(m) * up) * np.exp(-up * 4) * 0.07 * (0.6 if k % 2 else 1)).astype(np.float32)
        if t0 >= C.get('drums_from', 6.9):   # grosse caisse douce sur les temps
            for k in range(4):
                j0 = int((t0 + k * beat) * SR); Lk = min(n - j0, int(0.35 * SR))
                if Lk > 0: uk = np.arange(Lk) / SR; out[j0:j0 + Lk] += (np.sin(2 * np.pi * (45 + 60 * np.exp(-uk * 30)) * uk) * np.exp(-uk * 9) * 0.35).astype(np.float32)
    return out
def wavf(name):
    ws = wave.open(SFX + name + '.wav'); s = np.frombuffer(ws.readframes(ws.getnframes()), '<i2').astype(np.float32) / 32768
    if ws.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
    if ws.getframerate() != SR: s = np.interp(np.arange(0, len(s), ws.getframerate() / SR), np.arange(len(s)), s).astype(np.float32)
    return s
def boom():
    L = int(1.2 * SR); u = np.arange(L) / SR
    return (np.sin(2 * np.pi * (38 + 50 * np.exp(-u * 12)) * u) * np.exp(-u * 3.2) + np.random.RandomState(1).normal(0, 1, L) * np.exp(-u * 25) * 0.15).astype(np.float32)
def put(m, s, t0, g):
    a0 = int(t0 * SR); L = min(len(s), len(m) - a0)
    if L > 0 and a0 >= 0: m[a0:a0 + L] += s[:L] * g
def audio(path):
    n = int(C['dur'] * SR)
    v = np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', os.path.join(D, C['src']), '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(np.float32) / 32768
    v = np.pad(v, (0, max(0, n - len(v))))[:n]; v = v / (np.abs(v).max() + 1e-9) * 0.9
    k = 4410; c = np.cumsum(np.concatenate([np.zeros(k), np.abs(v)])); ve = (c[k:] - c[:-k]) / k
    mus = music(C['dur']); mus = mus / (np.abs(mus).max() + 1e-9) * C.get('music_gain', 0.16)
    mus *= 1 - 0.55 * np.clip(ve / (ve.max() * 0.3), 0, 1)
    fx = np.zeros(n, np.float32)
    for tp, zp in PUNCH:
        put(fx, wavf('whoosh'), tp - 0.32, 0.18); put(fx, boom(), tp, 0.32)
    fd = int(0.5 * SR); mus[-fd:] *= np.linspace(1, 0, fd)
    out = v + mus + fx; out = out / (np.abs(out).max() + 1e-9) * 0.95
    wo = wave.open(path, 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((out * 32767).astype('<i2').tobytes()); wo.close()
if __name__ == '__main__':
    tmp = os.path.join(D, '_tmp'); shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    subprocess.run([FF, '-v', 'error', '-i', os.path.join(D, C['src']), '-q:v', '2', f'{tmp}/s%05d.jpg'], check=True)
    srcs = sorted(f for f in os.listdir(tmp) if f.startswith('s'))
    prev = os.environ.get('PREVIEW')
    idx = [int(float(x) * FPS) for x in prev.split(',')] if prev else range(len(srcs))
    for n in idx: render(n, f'{tmp}/{srcs[min(n, len(srcs) - 1)]}', f'{tmp}/g{n:05d}.jpg' if not prev else os.path.join(os.environ.get('PDIR', tmp), f'p_{n / FPS:.2f}.jpg'))
    if prev: shutil.rmtree(tmp); sys.exit(0)
    audio(f'{tmp}/a.wav'); out = os.path.join(D, C['out'])
    subprocess.run([FF, '-y', '-v', 'error', '-framerate', str(FPS), '-i', f'{tmp}/g%05d.jpg', '-i', f'{tmp}/a.wav', '-c:v', 'libx264', '-preset', 'slow', '-crf', '19', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', out], check=True)
    shutil.rmtree(tmp); print('ok', out)
