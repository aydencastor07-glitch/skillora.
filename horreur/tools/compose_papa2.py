# Montage complet « Ich bin's. Mach auf. » (format interactif, en boucle) :
# images 3D + grain/vignette, sous-titres MOT PAR MOT style jeu (mot dit en ambre, étiquette PAPA / AN DER TÜR),
# écrans de choix [1]/[2] avec barre de temps, mauvaises fins (« FALSCHE ENTSCHEIDUNG ») + rembobinage VHS,
# vue par le judas en fish-eye, glitchs aux révélations, carte de chapitre. Son : voix, coups, sonnerie derrière la porte,
# grincements, battements de cœur, rembobinage, nappe grave. La vidéo s'arrête pile sur le dernier mot.
# usage : compose_papa2.py dossier_episode dossier_frames sortie.mp4
import sys, os, json, re, subprocess, shutil, wave
import numpy as np
from multiprocessing import Pool
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
EP, FR, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
W, H, FPS, SR = 1080, 1920, 30, 44100
FD = '/home/user/skillora./temu/fonts/'; SFX = '/home/user/skillora./motion/sfx/'
C = json.load(open(os.path.join(EP, 'compose2.json')))
WORDS = json.load(open(os.path.join(EP, C['words'])))
NF = int(os.environ.get('NF', 0)) or len([f for f in os.listdir(FR) if f.endswith('.jpg')]); DUR = NF / FPS
_fc = {}
def F(n, s):
    if (n, s) not in _fc: _fc[(n, s)] = ImageFont.truetype(FD + n, s)
    return _fc[(n, s)]
def clamp(u): return max(0.0, min(1.0, u))
def ss(a, b, x): u = clamp((x - a) / (b - a)); return u * u * (3 - 2 * u)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIG = (1 - 0.45 * (((xx - W / 2) / (W / 2)) ** 2 * 0.7 + ((yy - H / 2) / (H / 2)) ** 2 * 0.55)).clip(0.45, 1)[..., None]
# fish-eye du judas
r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (W / 2)) ** 2); k = 1 + 0.55 * r ** 2
FX = np.clip(W / 2 + (xx - W / 2) / k * 0.92, 0, W - 1).astype(np.int32); FY = np.clip(H / 2 + (yy - H / 2) / k * 0.92, 0, H - 1).astype(np.int32)
PEEPM = (1 - np.clip((r - 0.9) / 0.08, 0, 1))[..., None]
del yy, xx, r, k
# ---- phrases (sous-titres) : coupe après . ? ! : et au début d'une citation, 6 mots max
PHR = []; cur = []
for i, (w, a, b) in enumerate(WORDS):
    if cur and (w.startswith('„') or len(cur) >= 6): PHR.append(cur); cur = []
    cur.append(i)
    if re.search(r'[.?!:]["“]?$', w) or w.endswith('“'): PHR.append(cur); cur = []
if cur: PHR.append(cur)
def label_at(t):
    for a, b, l in C['labels']:
        if a <= t < b: return l
    return None
def subs(img, t):
    for ph in PHR:
        a = WORDS[ph[0]][1] - 0.05; b = WORDS[ph[-1]][2] + 0.25
        nxt = [p for p in PHR if WORDS[p[0]][1] > WORDS[ph[0]][1]]
        if nxt: b = min(b, WORDS[nxt[0][0]][1] - 0.06)
        if not (a <= t < b): continue
        f = F('Nunito.ttf', 58); fb = F('Poppins-ExtraBold.ttf', 40)
        lab = label_at(WORDS[ph[0]][1] + 0.01)
        toks = [WORDS[i][0].replace('…', '').strip() for i in ph]; sp = f.getbbox(' ')[2]
        widths = [f.getbbox(x)[2] for x in toks]; lw = fb.getbbox(lab + '  ')[2] if lab else 0
        tot = lw + sum(widths) + sp * (len(toks) - 1); x = W / 2 - tot / 2; y = C.get('sub_y', 1440)
        d = ImageDraw.Draw(img, 'RGBA'); d.rounded_rectangle([x - 28, y - 48, x + tot + 28, y + 44], 12, fill=(0, 0, 0, 160))
        if lab: d.text((x, y), lab, font=fb, fill=(255, 184, 72), anchor='lm'); x += lw
        for i, tk, wd in zip(ph, toks, widths):
            st = WORDS[i][1]
            if t >= st - 0.03:
                now = st - 0.03 <= t < WORDS[i][2] + 0.05
                k = clamp((t - st + 0.03) / 0.08); col = (255, 196, 90) if now else (240, 240, 236)
                d.text((x, y + 6 * (1 - k)), tk, font=f, fill=col + (int(255 * k),), anchor='lm')
            x += wd + sp
def chapter(img, t):
    c = C.get('chapter')
    if not c or not (c['t0'] <= t < c['t1']): return
    k = clamp((t - c['t0']) / 0.35) * clamp((c['t1'] - t) / 0.35); a = int(255 * k); d = ImageDraw.Draw(img, 'RGBA'); y = c.get('y', 470)
    d.text((W / 2, y), c['top'], font=F('Nunito.ttf', 34), fill=(215, 215, 210, a), anchor='mm')
    w = int(260 * clamp((t - c['t0']) / 0.6)); d.rectangle([W / 2 - w, y + 32, W / 2 + w, y + 34], fill=(255, 184, 72, a))
    d.text((W / 2, y + 92), c['title'], font=F('PlayfairDisplay-Italic.ttf', 84), fill=(245, 242, 235, a), anchor='mm')
def choice(img, t, ch):
    k = clamp((t - ch['t0']) / 0.25) * clamp((ch['t1'] - t) / 0.2) if ch['t1'] < DUR - 0.1 else clamp((t - ch['t0']) / 0.25)
    d = ImageDraw.Draw(img, 'RGBA'); y = C.get('choice_y', 1190); hi = 0
    for tt, which in ch['hi']:
        if t >= tt: hi = which
    d.text((W / 2, y - 120), ch.get('q', 'WAS MACHST DU?'), font=F('Poppins-ExtraBold.ttf', 40), fill=(255, 255, 255, int(230 * k)), anchor='mm', stroke_width=3, stroke_fill=(0, 0, 0, int(200 * k)))
    for j, (num, txt) in enumerate(((1, ch['a']), (2, ch['b']))):
        on = hi in (num, 3); cx = W / 2 + (-1 if j == 0 else 1) * 250; slide = (1 - ss(ch['t0'], ch['t0'] + 0.35, t)) * 220 * (-1 if j == 0 else 1)
        x0, x1 = cx - 225 + slide, cx + 225 + slide; s = 1.06 if on and hi != 3 else 1.0
        x0, x1 = cx + (x0 - cx) * s, cx + (x1 - cx) * s
        d.rounded_rectangle([x0, y - 70 * s, x1, y + 70 * s], 18, fill=((190, 30, 30) if on else (14, 14, 18)) + (int(225 * k),), outline=(255, 255, 255, int(240 * k)), width=4)
        d.rounded_rectangle([x0 + 18, y - 40, x0 + 98, y + 40], 14, fill=(255, 255, 255, int(255 * k)))
        d.text((x0 + 58, y + 2), str(num), font=F('Poppins-ExtraBold.ttf', 56), fill=(14, 14, 18, int(255 * k)), anchor='mm')
        ft = F('Poppins-ExtraBold.ttf', 40)
        while max(ft.getbbox(l)[2] for l in txt.split('\n')) > x1 - x0 - 140 and ft.size > 22: ft = F('Poppins-ExtraBold.ttf', ft.size - 2)
        lines = txt.split('\n')
        for li, l in enumerate(lines): d.text(((x0 + 110 + x1 - 16) / 2, y + (li - (len(lines) - 1) / 2) * 44), l, font=ft, fill=(255, 255, 255, int(255 * k)), anchor='mm')
    u = clamp((t - ch['t0']) / (ch['t1'] - ch['t0'])); bw = 700
    d.rounded_rectangle([W / 2 - bw / 2, y + 100, W / 2 + bw / 2, y + 112], 6, fill=(255, 255, 255, int(70 * k)))
    d.rounded_rectangle([W / 2 - bw / 2, y + 100, W / 2 - bw / 2 + bw * (1 - u), y + 112], 6, fill=((255, 184, 72) if u < 0.75 else (230, 50, 40)) + (int(240 * k),))
def wrong(img, t):
    for a, b in C['wrong']:
        if a <= t < b:
            k = clamp((t - a) / 0.08); d = ImageDraw.Draw(img, 'RGBA'); sh = int(6 * np.sin(t * 90))
            d.text((W / 2 + sh, 900), 'FALSCHE', font=F('Poppins-ExtraBold.ttf', 110), fill=(230, 40, 35, int(255 * k)), anchor='mm', stroke_width=6, stroke_fill=(0, 0, 0, int(255 * k)))
            d.text((W / 2 - sh, 1030), 'ENTSCHEIDUNG', font=F('Poppins-ExtraBold.ttf', 96), fill=(230, 40, 35, int(255 * k)), anchor='mm', stroke_width=6, stroke_fill=(0, 0, 0, int(255 * k)))
def src_index(n):
    t = n / FPS
    for a, b, s0, s1 in C['rewind']:            # [début, fin, temps source au début, temps source à la fin] : lecture à l'envers
        if a <= t < b: return int((s0 + (s1 - s0) * (t - a) / (b - a)) * FPS), True
    return n, False
def glitch(a, t, n):
    for g in C['glitch']:
        if g <= t < g + 0.16:
            rs = np.random.RandomState(n); o = a.copy(); s = int(rs.randint(10, 26))
            o[..., 0] = np.roll(a[..., 0], s, 1); o[..., 2] = np.roll(a[..., 2], -s, 1)
            for _ in range(6):
                y0 = rs.randint(0, H - 120); h = rs.randint(20, 120); o[y0:y0 + h] = np.roll(o[y0:y0 + h], rs.randint(-80, 80), 1)
            return o
    return a
def render(n):
    t = n / FPS; si, rew = src_index(n)
    a = np.asarray(Image.open(f'{FR}/f{min(NF - 1, max(0, si)):05d}.jpg').convert('RGB')).astype(np.float32)
    if C['peep'][0] <= t < C['peep'][1]: a = a[FY, FX] * PEEPM * 1.7
    for c0, c1 in [(c['t0'], c['t1']) for c in C['choices']]:   # ralenti des couleurs pendant le choix
        if c0 <= t < c1 + 0.1:
            u = ss(c0, c0 + 0.3, t) * (1 - ss(c1, c1 + 0.1, t)) if c1 < DUR - 0.1 else ss(c0, c0 + 0.3, t)
            g = a.mean(2, keepdims=True); a = a * (1 - 0.55 * u) + g * 0.55 * u; a *= 1 - 0.15 * u
    for b0, b1 in C.get('black', []):
        if b0 <= t < b1: a *= 0.0
    a = glitch(a, t, n)
    if rew:   # bandes VHS
        rs = np.random.RandomState(n); a = a * 0.85 + 20
        for _ in range(4):
            y0 = rs.randint(0, H - 60); h = rs.randint(8, 40); a[y0:y0 + h] = np.roll(a[y0:y0 + h], rs.randint(-120, 120), 1) * 1.3 + 30
    for fl in C.get('flash', []):
        if fl <= t < fl + 0.08: a = a * 0.4 + 150
    a = a * VIG + np.random.RandomState(n).normal(0, 3.0, (H, W, 1))
    img = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert('RGBA')
    if rew:
        d = ImageDraw.Draw(img, 'RGBA'); d.text((W / 2, 420), '◀◀  ZURÜCK', font=F('Poppins-ExtraBold.ttf', 64), fill=(255, 255, 255, 235), anchor='mm', stroke_width=4, stroke_fill=(0, 0, 0))
    chapter(img, t)
    for ch in C['choices']:
        if ch['t0'] <= t < ch['t1']: choice(img, t, ch)
    wrong(img, t)
    if not rew: subs(img, t)
    img.convert('RGB').save(f'{TMP}/g{n:05d}.jpg', quality=93)
# ---------- son
def load(f):
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
def creak(d, seed):
    n = int(d * SR); tt = np.arange(n) / SR; f = 180 + 60 * np.sin(2 * np.pi * 0.7 * tt + seed) + 30 * np.random.RandomState(seed).normal(0, 1, n).cumsum() / np.sqrt(n)
    s = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * (0.5 + 0.5 * np.sin(2 * np.pi * 23 * tt)) ** 4
    return (lp(s.astype(np.float32), 8) * np.minimum(1, tt / 0.1) * np.minimum(1, (d - tt) / 0.2)).astype(np.float32)
def ring(d):
    n = int(d * SR); tt = np.arange(n) / SR; on = ((tt % 2.0) < 1.2) * ((tt * 12 % 1) < 0.6)
    s = (np.sin(2 * np.pi * 880 * tt) + 0.6 * np.sin(2 * np.pi * 1320 * tt)) * on
    return lp(s.astype(np.float32), 18)   # étouffée (derrière la porte)
def stinger(seed):
    d = 1.6; n = int(d * SR); s_ = np.arange(n) / SR
    return (np.sin(2 * np.pi * np.cumsum(np.linspace(70, 30, n)) / SR) * np.exp(-s_ * 2.2) + lp(noise(d, seed), 3) * np.exp(-s_ * 3) * 0.2).astype(np.float32)
def wavf(name):
    ws = wave.open(SFX + name + '.wav'); s = np.frombuffer(ws.readframes(ws.getnframes()), '<i2').astype(np.float32) / 32768
    if ws.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
    if ws.getframerate() != SR: s = np.interp(np.arange(0, len(s), ws.getframerate() / SR), np.arange(len(s)), s).astype(np.float32)
    return s
def audio(path):
    A = C['audio']; n = int(DUR * SR); m = np.zeros(n, np.float32)
    v = load(os.path.join(EP, C['voice']))[:n]; v = np.pad(v, (0, n - len(v)))
    tt = np.arange(n) / SR
    drone = (np.sin(2 * np.pi * 41 * tt) * 0.6 + np.sin(2 * np.pi * 61.5 * tt) * 0.3) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.13 * tt))
    hiss = lp(noise(DUR, 9), 60); hiss /= np.abs(hiss).max() + 1e-9
    fx = np.zeros(n, np.float32)
    for i, k in enumerate(A['knocks']): put(fx, knock(i), k, 0.9)
    for i, k in enumerate(A['pound']): put(fx, knock(50 + i, True), k, 1.1)
    for a, b in A.get('rattle', []):
        t = a
        while t < b: put(fx, knock(int(t * 100)) * 0.3, t, 0.5); t += 0.09
    for i, s in enumerate(A['stingers']): put(fx, stinger(i), s, 0.85)
    for a, b in A['heart']:
        t = a
        while t < b: put(fx, beat(), t, 0.7); put(fx, beat(), t + 0.2, 0.45); t += 0.62
    for b in A.get('buzz', []): put(fx, wavf('buzz') * 0.6, b, 0.5)
    for b in A.get('msg', []): put(fx, wavf('tap'), b, 0.5)
    for a, b in A.get('ring', []): put(fx, ring(b - a), a, 0.12)
    for a, d in A.get('creak', []): put(fx, creak(d, int(a)), a, 0.12)
    for a, b in A.get('rewind', []):
        d = b - a; nn = int(d * SR); s_ = np.arange(nn) / SR
        wh = np.sin(2 * np.pi * np.cumsum(np.linspace(300, 1400, nn)) / SR) * 0.3 + lp(noise(d, 4), 2) * 0.5
        rv = v[int((a - 1.6) * SR):int((a - 1.6) * SR) + nn * 3][::-3][:nn] if a > 1.7 else np.zeros(nn)
        put(fx, (wh * np.minimum(1, s_ / 0.05)).astype(np.float32), a, 0.35); put(fx, np.pad(rv, (0, nn - len(rv))).astype(np.float32), a, 0.5)
        v[int(a * SR):int(b * SR)] *= 0.15
    ve = lp(np.abs(v), 4410); duck = 1 - 0.4 * np.clip(ve / (ve.max() * 0.25 + 1e-9), 0, 1)
    out = v + (drone * 0.05 + hiss * 0.02) * duck + fx
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
    subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{TMP}/g%05d.jpg', '-i', f'{TMP}/a.wav', '-c:v', 'libx264', '-preset', 'slow', '-crf', '21', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
    shutil.rmtree(TMP); print('ok', OUT, round(DUR, 2))
