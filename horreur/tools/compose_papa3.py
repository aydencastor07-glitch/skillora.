# Montage « Ich bin's. Mach auf. – Teil 2 » : nouveau style d'écran (demande de l'utilisateur) :
#  - sous-titres mot par mot SANS fond noir (blanc, contour fin + ombre douce, mot dit en ambre, étiquette du personnage) ;
#  - choix : écran coupé en deux avec les deux vraies scènes (gauche = image en cours, droite = images d'un autre moment du film),
#    gros « 1 » / « 2 » à la craie, cercle de craie autour du choix nommé, MÈCHE qui brûle sur la ligne de coupe (compte à rebours) ;
#  - mauvaise fin : glitch, rembobinage VHS, le « 1 » barré à la craie rouge ;  « TEIL 2 » à la craie.
# Son : voix, coups à la porte (proches / étouffés), vibrations, battements de cœur, grincements, pas lourds, mèche, coupe nette à la fin.
# usage : compose_papa3.py dossier_episode dossier_frames sortie.mp4   [PREVIEW=t1,t2 PDIR=dossier NF=n]
import sys, os, json, re, math, subprocess, shutil, wave
import numpy as np
from multiprocessing import Pool
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
EP, FR, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
W, H, FPS, SR = 1080, 1920, 30, 44100
FD = '/home/user/skillora./temu/fonts/'; SFX = '/home/user/skillora./motion/sfx/'
C = json.load(open(os.path.join(EP, 'compose.json')))
WORDS = json.load(open(os.path.join(EP, C['words'])))
NF = int(os.environ.get('NF', 0)) or len([f for f in os.listdir(FR) if f.endswith('.jpg')]); DUR = NF / FPS
AMBER = (255, 190, 80); CHALK = (244, 240, 230); REDC = (226, 60, 48)
_fc = {}
def F(n, s):
    if (n, s) not in _fc: _fc[(n, s)] = ImageFont.truetype(FD + n, int(s))
    return _fc[(n, s)]
def clamp(u): return max(0.0, min(1.0, u))
def ss(a, b, x): u = clamp((x - a) / (b - a)); return u * u * (3 - 2 * u)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIG = (1 - 0.42 * (((xx - W / 2) / (W / 2)) ** 2 * 0.7 + ((yy - H / 2) / (H / 2)) ** 2 * 0.55)).clip(0.48, 1)[..., None]
del yy, xx
_rs = np.random.RandomState(11); _n = _rs.rand(H // 3, W // 3).astype(np.float32)
CHALKTEX = np.asarray(Image.fromarray((np.clip(0.62 + 0.6 * _n, 0, 1) * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)).astype(np.float32) / 255
def load(n): return np.asarray(Image.open(f'{FR}/f{min(NF - 1, max(0, n)):05d}.jpg').convert('RGB')).astype(np.float32)
def chalked(layer):
    """Donne à un calque RGBA un grain de craie (alpha irrégulier)."""
    a = np.asarray(layer).astype(np.float32); a[..., 3] *= CHALKTEX; return Image.fromarray(a.clip(0, 255).astype(np.uint8), 'RGBA')
# ---- phrases (sous-titres)
PHR = []; cur = []
for i, (w, a, b) in enumerate(WORDS):
    if cur and (w.startswith('„') or len(cur) >= 5): PHR.append(cur); cur = []
    cur.append(i)
    if re.search(r'[.?!:]["“]?$', w) or w.endswith('“'): PHR.append(cur); cur = []
if cur: PHR.append(cur)
def label_at(t):
    for a, b, l in C['labels']:
        if a <= t < b: return l
    return None
def subs(img, t):
    for pi, ph in enumerate(PHR):
        a = WORDS[ph[0]][1] - 0.05; b = WORDS[ph[-1]][2] + 0.3
        if pi + 1 < len(PHR): b = min(b, WORDS[PHR[pi + 1][0]][1] - 0.05)
        if not (a <= t < b): continue
        f = F('Poppins-ExtraBold.ttf', 62); fb = F('Poppins-ExtraBold.ttf', 36)
        lab = label_at(WORDS[ph[0]][1] + 0.01); toks = [WORDS[i][0].replace('…', '').strip() for i in ph]; sp = f.getbbox(' ')[2]
        widths = [f.getbbox(x)[2] for x in toks]; tot = sum(widths) + sp * (len(toks) - 1); y = C.get('sub_y', 1450)
        if tot > W - 120: f = F('Poppins-ExtraBold.ttf', int(62 * (W - 120) / tot)); sp = f.getbbox(' ')[2]; widths = [f.getbbox(x)[2] for x in toks]; tot = sum(widths) + sp * (len(toks) - 1)
        lay = Image.new('RGBA', (W, 260), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); x = W / 2 - tot / 2; yb = 150
        if lab: d.text((W / 2, yb - 78), lab, font=fb, fill=AMBER + (255,), anchor='mm', stroke_width=4, stroke_fill=(0, 0, 0, 255))
        for i, tk, wd in zip(ph, toks, widths):
            st = WORDS[i][1]
            if t >= st - 0.03:
                now = st - 0.03 <= t < WORDS[i][2] + 0.06; k = clamp((t - st + 0.03) / 0.08)
                d.text((x, yb + 10 * (1 - k)), tk, font=f, fill=(AMBER if now else (255, 255, 255)) + (int(255 * k),), anchor='lm', stroke_width=5, stroke_fill=(0, 0, 0, int(255 * k)))
            x += wd + sp
        sh = Image.new('RGBA', lay.size, (0, 0, 0, 0)); sh.putalpha(lay.getchannel('A').point(lambda v: int(v * 0.75))); sh = sh.filter(ImageFilter.GaussianBlur(9))
        img.alpha_composite(sh, (0, int(y - 150 + 6))); img.alpha_composite(lay, (0, int(y - 150)))
def chapter(img, t):
    c = C.get('chapter')
    if not c or not (c['t0'] <= t < c['t1']): return
    k = clamp((t - c['t0']) / 0.25) * clamp((c['t1'] - t) / 0.25); lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    f = F('PermanentMarker.ttf', 190); y = c.get('y', 430); d.text((W / 2, y), c['title'], font=f, fill=CHALK + (int(255 * k),), anchor='mm', stroke_width=6, stroke_fill=(0, 0, 0, int(140 * k)))
    tw = f.getbbox(c['title'])[2]; u = clamp((t - c['t0']) / 0.45); x0 = W / 2 - tw / 2
    pts = [(x0 + tw * u * j / 20, y + 120 + 8 * math.sin(j * 1.3)) for j in range(21)]; d.line(pts, fill=AMBER + (int(255 * k),), width=12)
    img.alpha_composite(chalked(lay))
def number(lay, cx, cy, num, label, on, off, circle_u, t, struck=0):
    """Chiffre à la craie + mot ; cercle tracé autour quand la voix le nomme."""
    d = ImageDraw.Draw(lay); a = 255 if not off else 120; f = F('PermanentMarker.ttf', 250 if on else 220)
    d.text((cx, cy), str(num), font=f, fill=CHALK + (a,), anchor='mm', stroke_width=8, stroke_fill=(0, 0, 0, int(a * 0.55)))
    fl = F('PermanentMarker.ttf', 66)
    while max(fl.getbbox(l)[2] for l in label.split('\n')) > 470 and fl.size > 30: fl = F('PermanentMarker.ttf', fl.size - 2)
    for li, l in enumerate(label.split('\n')): d.text((cx, cy + 190 + li * 74), l, font=fl, fill=(AMBER if on else CHALK) + (a,), anchor='mm', stroke_width=5, stroke_fill=(0, 0, 0, int(a * 0.7)))
    if circle_u > 0:
        rs = np.random.RandomState(num); n = int(64 * clamp(circle_u)) + 1; pts = []
        for j in range(n): th = -1.9 + j / 64 * 6.6; pts.append((cx + (150 + 6 * math.sin(th * 3 + num)) * math.cos(th), cy - 6 + (165 + 8 * math.cos(th * 2)) * math.sin(th)))
        if len(pts) > 1: d.line(pts, fill=AMBER + (255,), width=13, joint='curve')
    if struck > 0:
        u = clamp(struck); d.line([(cx - 150, cy - 170), (cx - 150 + 300 * min(1, u * 2), cy - 170 + 340 * min(1, u * 2))], fill=REDC + (255,), width=24)
        if u > 0.5: d.line([(cx + 150, cy - 170), (cx + 150 - 300 * (u - 0.5) * 2, cy - 170 + 340 * (u - 0.5) * 2)], fill=REDC + (255,), width=24)
def fuse(img, x, t, u, n):
    """Mèche le long de la coupe : la partie brûlée est grise, une étincelle descend ; arrivée en bas = fin du temps."""
    y0, y1 = 250, 1660; ys = y0 + (y1 - y0) * clamp(u); d = ImageDraw.Draw(img, 'RGBA')
    d.line([(x, 0), (x, H)], fill=(0, 0, 0, 255), width=10)
    pts = [(x + 5 * math.sin(yv * 0.045), yv) for yv in range(y0, y1 + 1, 12)]
    burnt = [p for p in pts if p[1] <= ys]; rope = [p for p in pts if p[1] >= ys - 12]
    if len(burnt) > 1: d.line(burnt, fill=(70, 66, 62, 255), width=5)
    if len(rope) > 1:
        d.line(rope, fill=(150, 112, 70, 255), width=13)
        for p in rope[::2]: d.line([(p[0] - 6, p[1] - 3), (p[0] + 6, p[1] + 3)], fill=(96, 70, 44, 255), width=3)
    d.ellipse([x - 16, y1 - 4, x + 16, y1 + 28], fill=(60, 44, 30, 255))
    rs = np.random.RandomState(n); gx = x + 5 * math.sin(ys * 0.045)
    glow = Image.new('RGBA', (240, 240), (0, 0, 0, 0)); g = ImageDraw.Draw(glow)
    for r_, a_ in ((110, 40), (70, 80), (40, 150), (20, 255)): g.ellipse([120 - r_, 120 - r_, 120 + r_, 120 + r_], fill=(255, 200 + (r_ < 30) * 40, 110 + (r_ < 30) * 120, a_))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)), (int(gx - 120), int(ys - 120)))
    for _ in range(14):
        ang = rs.uniform(0, 6.28); L = rs.uniform(18, 70); d.line([(gx, ys), (gx + L * math.cos(ang), ys + L * math.sin(ang) - 10)], fill=(255, 230, 150, 255), width=3)
def dim(a, k):   # panneau non choisi : sombre et presque gris
    g = a.mean(2, keepdims=True); return (a * (1 - 0.6 * k) + g * 0.6 * k) * (1 - 0.5 * k)
def choice_frame(a, ch, t, n):
    """Compose l'écran coupé en deux. a = image en cours (float). Retourne (image float, calque de craie)."""
    end = ch['t1'] >= DUR - 0.05
    u = ss(ch['t0'], ch['t0'] + 0.3, t) * (1 if end else 1 - ss(ch['t1'] - 0.25, ch['t1'], t))
    xs = int(W - (W / 2) * u); hi = 0
    for tt, which in ch['hi']:
        if t >= tt: hi = which
    r = ch['right']; span = r['src']; tb = span[0] + ((t - ch['t0']) * r.get('rate', 0.5)) % (span[1] - span[0]); b = load(int(tb * FPS))
    lcx = W / 2 + (ch['left'].get('cx', 540) - W / 2) * u; x0 = int(clamp((lcx - xs / 2) / max(1, W - xs)) * (W - xs)) if xs < W else 0
    out = np.empty_like(a); L = a[:, x0:x0 + xs]; out[:, :xs] = dim(L, u) if hi == 2 else L
    if xs < W:
        wr = W - xs; rx = int(min(W - wr, max(0, r.get('cx', 540) - wr / 2))); R = b[:, rx:rx + wr]; out[:, xs:] = dim(R, u) if hi == 1 else R
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    if u > 0.5:
        k = (u - 0.5) * 2; cy = C.get('num_y', 470)
        for j, side in enumerate(('left', 'right')):
            num = j + 1; on = hi in (num, 3); tt = [x for x, wch in ch['hi'] if wch == num]; cu = clamp((t - tt[0]) / 0.35) if tt and t >= tt[0] else 0
            if hi == 3: cu = 1
            number(lay, W / 4 + j * W / 2, cy, num, ch[side]['label'], on, hi in (1, 2) and not on, cu, t)
        lay = chalked(lay); al = np.asarray(lay).astype(np.float32); al[..., 3] *= k; lay = Image.fromarray(al.astype(np.uint8), 'RGBA')
    return out, lay, xs, u
def src_index(n):
    t = n / FPS
    for a, b, s0, s1 in C['rewind']:
        if a <= t < b: return int((s0 + (s1 - s0) * (t - a) / (b - a)) * FPS), (t - a) / (b - a)
    return n, None
def glitch(a, t, n):
    for g in C['glitch']:
        if g <= t < g + 0.15:
            rs = np.random.RandomState(n); o = a.copy(); s = int(rs.randint(10, 26))
            o[..., 0] = np.roll(a[..., 0], s, 1); o[..., 2] = np.roll(a[..., 2], -s, 1)
            for _ in range(6):
                y0 = rs.randint(0, H - 120); h = rs.randint(20, 120); o[y0:y0 + h] = np.roll(o[y0:y0 + h], rs.randint(-80, 80), 1)
            return o
    return a
def render(n):
    t = n / FPS; si, rew = src_index(n); a = load(si); lay = None; fz = None
    for ch in C['choices']:
        if ch['t0'] <= t < ch['t1']: a, lay, xs, u = choice_frame(a, ch, t, n); fz = (xs, (t - ch['t0']) / (ch['t1'] - ch['t0']), u)
    for b0, b1 in C.get('black', []):
        if b0 <= t < b1: a *= 0.0
    a = glitch(a, t, n)
    if rew is not None:
        rs = np.random.RandomState(n); a = a * 0.85 + 20
        for _ in range(5):
            y0 = rs.randint(0, H - 60); h = rs.randint(8, 40); a[y0:y0 + h] = np.roll(a[y0:y0 + h], rs.randint(-120, 120), 1) * 1.3 + 30
    for fl in C.get('flash', []):
        if fl <= t < fl + 0.08: a = a * 0.4 + 150
    a = a * VIG + np.random.RandomState(n).normal(0, 3.0, (H, W, 1))
    img = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert('RGBA')
    if fz and fz[2] > 0.6: fuse(img, fz[0], t, fz[1], n)
    if lay is not None: img.alpha_composite(lay)
    if rew is not None:   # le « 1 » barré
        l2 = Image.new('RGBA', (W, H), (0, 0, 0, 0)); number(l2, W / 2, 820, 1, C.get('wrong_label', ''), True, False, 0, t, struck=rew * 1.6); img.alpha_composite(chalked(l2))
    chapter(img, t)
    if rew is None: subs(img, t)
    img.convert('RGB').save(f'{TMP}/g{n:05d}.jpg', quality=93)
# ---------- son
def loada(f):
    return np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', f, '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(np.float32) / 32768
def lp(x, k): c = np.cumsum(np.concatenate([np.zeros(k), x])); return ((c[k:] - c[:-k]) / k).astype(np.float32)
def put(m, s, t0, g):
    a0 = int(t0 * SR); L = min(len(s), len(m) - a0)
    if L > 0 and a0 >= 0: m[a0:a0 + L] += s[:L] * g
def noise(d, seed): return np.random.RandomState(seed).normal(0, 1, int(d * SR)).astype(np.float32)
def knock(seed, heavy=False):
    n = int(0.3 * SR); tt = np.arange(n) / SR; r = np.random.RandomState(seed); f0 = 75 if heavy else 95
    body = np.sin(2 * np.pi * f0 * tt) * np.exp(-tt * (18 if heavy else 28)) + 0.5 * np.sin(2 * np.pi * f0 * 1.9 * tt) * np.exp(-tt * 40)
    click = lp(r.normal(0, 1, n).astype(np.float32), 6) * np.exp(-tt * 120) * (3.5 if heavy else 2.5)
    return (body + click).astype(np.float32)
def beat():
    n = int(0.18 * SR); tt = np.arange(n) / SR; return (np.sin(2 * np.pi * 52 * tt) * np.exp(-tt * 22)).astype(np.float32)
def step():
    n = int(0.35 * SR); tt = np.arange(n) / SR; return (np.sin(2 * np.pi * 60 * tt) * np.exp(-tt * 14) + lp(noise(0.35, 5), 40) * np.exp(-tt * 30) * 2).astype(np.float32)
def creak(d, seed):
    n = int(d * SR); tt = np.arange(n) / SR; f = 180 + 60 * np.sin(2 * np.pi * 0.7 * tt + seed) + 30 * np.random.RandomState(seed).normal(0, 1, n).cumsum() / np.sqrt(n)
    s = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * (0.5 + 0.5 * np.sin(2 * np.pi * 23 * tt)) ** 4
    return (lp(s.astype(np.float32), 8) * np.minimum(1, tt / 0.1) * np.minimum(1, (d - tt) / 0.2)).astype(np.float32)
def stinger(seed):
    d = 1.6; n = int(d * SR); s_ = np.arange(n) / SR
    return (np.sin(2 * np.pi * np.cumsum(np.linspace(70, 30, n)) / SR) * np.exp(-s_ * 2.2) + lp(noise(d, seed), 3) * np.exp(-s_ * 3) * 0.2).astype(np.float32)
def hiss(d, seed):   # mèche : souffle aigu qui crépite
    x = noise(d, seed); x = x - lp(x, 12); n = len(x); cr = (np.random.RandomState(seed + 1).rand(n) > 0.9993).astype(np.float32); cr = np.convolve(cr, np.exp(-np.arange(300) / 40), 'same')
    return (x * (0.5 + 0.5 * np.sin(np.arange(n) / SR * 2 * np.pi * 9)) * 0.6 + cr * x * 3).astype(np.float32) * np.minimum(1, np.arange(n) / (0.2 * SR))
def wavf(name):
    ws = wave.open(SFX + name + '.wav'); s = np.frombuffer(ws.readframes(ws.getnframes()), '<i2').astype(np.float32) / 32768
    if ws.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
    if ws.getframerate() != SR: s = np.interp(np.arange(0, len(s), ws.getframerate() / SR), np.arange(len(s)), s).astype(np.float32)
    return s
def audio(path):
    A = C['audio']; n = int(DUR * SR)
    v = loada(os.path.join(EP, C['voice']))[:n]; v = np.pad(v, (0, n - len(v))); tt = np.arange(n) / SR
    drone = (np.sin(2 * np.pi * 41 * tt) * 0.6 + np.sin(2 * np.pi * 61.5 * tt) * 0.3) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.13 * tt))
    air = lp(noise(DUR, 9), 60); air /= np.abs(air).max() + 1e-9
    fx = np.zeros(n, np.float32)
    for i, k in enumerate(A.get('pound', [])): put(fx, knock(50 + i, True), k, 1.0)
    for i, k in enumerate(A.get('pound_far', [])): put(fx, lp(knock(80 + i, True), 30), k, 1.3)
    for i, k in enumerate(A.get('thud', [])): put(fx, knock(20 + i, True), k, 1.0)
    for k in A.get('steps', []): put(fx, step(), k, 0.6)
    for i, s in enumerate(A['stingers']): put(fx, stinger(i), s, 0.8)
    for a, b in A['heart']:
        t = a
        while t < b: put(fx, beat(), t, 0.7); put(fx, beat(), t + 0.2, 0.45); t += 0.6
    for b in A.get('buzz', []): put(fx, wavf('buzz') * 0.6, b, 0.55)
    for b in A.get('msg', []): put(fx, wavf('tap'), b, 0.5)
    for a, d in A.get('creak', []): put(fx, creak(d, int(a)), a, 0.12)
    for a, b in A.get('fuse', []): put(fx, hiss(b - a, int(a)), a, 0.05)
    for a, b in A.get('rewind', []):
        d = b - a; nn = int(d * SR); s_ = np.arange(nn) / SR
        wh = np.sin(2 * np.pi * np.cumsum(np.linspace(300, 1400, nn)) / SR) * 0.3 + lp(noise(d, 4), 2) * 0.5
        put(fx, (wh * np.minimum(1, s_ / 0.05)).astype(np.float32), a, 0.35)
    for a, b in A.get('riser', []):
        d = b - a; x = noise(d, 3); x = x - lp(x, 30); x *= np.linspace(0, 1, len(x)) ** 2; put(fx, x, a, 0.1)
    ve = lp(np.abs(v), 4410); duck = 1 - 0.4 * np.clip(ve / (ve.max() * 0.25 + 1e-9), 0, 1)
    out = v + (drone * 0.05 + air * 0.02) * duck + fx
    out = out / max(1e-6, np.abs(out).max()) * 0.95
    wo = wave.open(path, 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((out * 32767).astype('<i2').tobytes()); wo.close()
TMP = OUT + '_tmp'
if __name__ == '__main__':
    if os.environ.get('PREVIEW'):
        TMP = os.environ.get('PDIR', '/tmp'); os.makedirs(TMP, exist_ok=True)
        for ts in os.environ['PREVIEW'].split(','): render(int(float(ts) * FPS))
        sys.exit(0)
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
    with Pool(4) as p: p.map(render, range(NF), chunksize=20)
    audio(f'{TMP}/a.wav')
    subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{TMP}/g%05d.jpg', '-i', f'{TMP}/a.wav', '-vf', 'hqdn3d=1.5:1.5:4:4', '-c:v', 'libx264', '-preset', 'slow', '-crf', '23', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
    shutil.rmtree(TMP); print('ok', OUT, round(DUR, 2))
