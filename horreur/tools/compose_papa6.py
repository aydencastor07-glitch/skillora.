# Montage « Ich bin's. Mach auf. – Teil 5 » : MÊME style de texte que la partie 3 (demande de l'utilisateur : la partie 3 a eu
# beaucoup de commentaires) — choix « 1 » / « 2 » écrits au doigt dans la BUÉE, « TEIL 5 » dans la buée, « 1 » barré + rembobinage.
# Sous-titres mot par mot classiques : blanc, mot prononcé en JAUNE, sans fond noir.
# Son : la musique fournie par l'utilisateur (prolongée sur le temps, voir son_bed.wav), voix (effet téléphone / voix étouffée
# derrière la porte), sonnerie dans la poche, coups sur la porte, sonnette, verrou, battements de cœur.
# usage : compose_papa6.py dossier_episode dossier_frames sortie.mp4   [PREVIEW=t1,t2 PDIR=dossier NF=n]
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
AMBER = (255, 221, 0);   # jaune classique CHALK = (244, 240, 230); REDC = (226, 60, 48)
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

_dr = np.random.RandomState(5)
DROPS = [(int(_dr.randint(0, W)), int(_dr.randint(0, H)), float(_dr.uniform(1.5, 4.5))) for _ in range(900)]
def fogify(a, k):
    """Vitre embuée : image floue, éclaircie et refroidie + petites gouttelettes."""
    im = Image.fromarray(a.clip(0, 255).astype(np.uint8)); sm = im.resize((W // 5, H // 5), Image.BILINEAR).filter(ImageFilter.GaussianBlur(2)).resize((W, H), Image.BILINEAR)
    f = np.asarray(sm).astype(np.float32) * 0.42 + np.array([178, 186, 196], np.float32) * 0.58
    return a * (1 - k) + f * k
def stroke_mask(texts, t):
    """Masque des lettres « essuyées » au doigt. texts = [(texte, cx, cy, taille, révélé 0..1, brillance, coulure 0..1)]."""
    m = Image.new('L', (W, H), 0); d = ImageDraw.Draw(m); glow = Image.new('L', (W, H), 0); g = ImageDraw.Draw(glow)
    for txt, cx, cy, sz, rev, br, drip in texts:
        if rev <= 0: continue
        f = F('PermanentMarker.ttf', sz); bb = d.textbbox((cx, cy), txt, font=f, anchor='mm')
        lay = Image.new('L', (W, H), 0); ImageDraw.Draw(lay).text((cx, cy), txt, font=f, fill=255, anchor='mm', stroke_width=max(4, sz // 22), stroke_fill=255)
        cut = Image.new('L', (W, H), 0); ImageDraw.Draw(cut).rectangle([0, 0, W, bb[1] + (bb[3] - bb[1]) * rev], fill=255)   # écrit de haut en bas
        lay = Image.fromarray(np.minimum(np.asarray(lay), np.asarray(cut)))
        m = Image.fromarray(np.maximum(np.asarray(m), np.asarray(lay)))
        if br > 0: g.text((cx, cy), txt, font=f, fill=int(255 * br), anchor='mm', stroke_width=max(4, sz // 22), stroke_fill=int(255 * br))
        if drip > 0 and rev >= 1:   # coulures sous les lettres
            rs = np.random.RandomState(abs(hash(txt)) % 999)
            for _ in range(5 if sz > 150 else 2):
                x = rs.uniform(bb[0] + 10, bb[2] - 10); L = drip * rs.uniform(60, 260); y0 = bb[3] - 8
                d.line([(x, y0), (x + rs.uniform(-4, 4), y0 + L)], fill=200, width=int(rs.uniform(5, 9))); d.ellipse([x - 7, y0 + L - 7, x + 7, y0 + L + 7], fill=200)
    m = np.asarray(m.filter(ImageFilter.GaussianBlur(2.2))).astype(np.float32)[..., None] / 255
    gl = np.asarray(glow.filter(ImageFilter.GaussianBlur(18))).astype(np.float32)[..., None] / 255
    return m, gl
def fog_screen(a, t, items, k):
    fa = fogify(a, k)
    if not items: return fa
    m, gl = stroke_mask(items, t)
    rim = np.clip(np.asarray(Image.fromarray((m[..., 0] * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(4))).astype(np.float32)[..., None] / 255 - m, 0, 1)
    clear = a * 0.62 + gl * np.array([150, 95, 25], np.float32)
    out = fa * (1 - m) + clear * m + rim * 55 * k
    return out
def choice_items(ch, t):
    hi = 0
    for tt, which in ch['hi']:
        if t >= tt: hi = which
    items = []; cy = C.get('num_y', 560); dripu = clamp((t - ch['t0']) / (ch['t1'] - ch['t0']))
    for j, (num, lab) in enumerate(((1, ch['a']), (2, ch['b']))):
        tt = [x for x, w in ch['hi'] if w == num]; t0 = tt[0] if tt else ch['t0']
        rev = clamp((t - t0 + 0.05) / 0.5); on = hi in (num, 3); off = hi in (1, 2) and not on
        cx = W / 4 + j * W / 2; br = (0.9 if on else 0) * (1 if not off else 0)
        items.append((str(num), cx, cy, 330, rev, br, dripu))
        for li, l in enumerate(lab.split('\n')): items.append((l, cx, cy + 235 + li * 92, 84, clamp((t - t0 - 0.2) / 0.5), br * 0.8, 0))
    return items
def render(n):
    t = n / FPS; si, rew = src_index(n); a = load(si); items = None; k = 0
    for ch in C['choices']:
        if ch['t0'] <= t < ch['t1']:
            end = ch['t1'] >= DUR - 0.05; k = ss(ch['t0'], ch['t0'] + 0.35, t) * (1 if end else 1 - ss(ch['t1'] - 0.25, ch['t1'], t)); items = choice_items(ch, t)
    c = C.get('chapter')
    if c and c['t0'] <= t < c['t1']:
        k = ss(c['t0'], c['t0'] + 0.25, t) * (1 - ss(c['t1'] - 0.25, c['t1'], t)); items = [(c['title'], W / 2, c.get('y', 560), 230, clamp((t - c['t0']) / 0.45), 0, 0)]
    if rew is not None:
        k = 0.85; items = [('1', W / 2, 760, 420, 1, 0, 0), ('X', W / 2, 760, 520, clamp(rew * 2.2), 0.9, 0)]
    for b0, b1 in C.get('black', []):
        if b0 <= t < b1: a *= 0.0
    a = glitch(a, t, n)
    if rew is not None:
        rs = np.random.RandomState(n); a = a * 0.85 + 20
        for _ in range(5):
            y0 = rs.randint(0, H - 60); h = rs.randint(8, 40); a[y0:y0 + h] = np.roll(a[y0:y0 + h], rs.randint(-120, 120), 1) * 1.3 + 30
    if k > 0: a = fog_screen(a, t, items, k)
    for fl in C.get('flash', []):
        if fl <= t < fl + 0.08: a = a * 0.4 + 150
    a = a * VIG + np.random.RandomState(n).normal(0, 3.0, (H, W, 1))
    img = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert('RGBA')
    if rew is None and not (c and c['t0'] <= t < c['t1']): subs(img, t)
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

def bandpass(x, lo, hi):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); X[(f < lo) | (f > hi)] = 0; return np.fft.irfft(X, len(x)).astype(np.float32)
def phone_fx(seg, seed):
    y = bandpass(seg, 320, 3300); y = np.tanh(y * 3.0) / 3.0 * 1.6
    cr = (np.random.RandomState(seed).rand(len(y)) > 0.9996).astype(np.float32); cr = np.convolve(cr, np.exp(-np.arange(200) / 30), 'same')
    nz = bandpass(np.resize(noise(len(y) / SR + 0.01, seed), len(y)), 800, 3000)
    return y + nz * 0.006 + cr * 0.05
def ringtone(d):
    n = int(d * SR); tt = np.arange(n) / SR; on = ((tt % 1.6) < 0.9).astype(np.float32)
    s = (np.sin(2 * np.pi * 784 * tt) * (np.sin(2 * np.pi * 8 * tt) > 0) + np.sin(2 * np.pi * 988 * tt) * (np.sin(2 * np.pi * 8 * tt) <= 0)) * on
    return (s * 0.5).astype(np.float32)
def gravel():
    n = int(0.3 * SR); tt = np.arange(n) / SR; return (bandpass(noise(0.3, int(tt.size)), 300, 4000) * np.exp(-tt * 18) * 1.5 + np.sin(2 * np.pi * 70 * tt) * np.exp(-tt * 20)).astype(np.float32)
def audio(path):
    A = C['audio']; n = int(DUR * SR)
    v = loada(os.path.join(EP, C['voice']))[:n]; v = np.pad(v, (0, n - len(v)))
    for i, (a, b) in enumerate(A.get('phone_voice', [])):
        i0, i1 = int(a * SR), int(b * SR); f = int(0.03 * SR); seg = phone_fx(v[i0:i1].copy(), 40 + i); e = np.ones(len(seg), np.float32); e[:f] = np.linspace(0, 1, f); e[-f:] = np.linspace(1, 0, f)
        v[i0:i1] = v[i0:i1] * (1 - e) + seg * e
    tt = np.arange(n) / SR
    drone = (np.sin(2 * np.pi * 41 * tt) * 0.6 + np.sin(2 * np.pi * 61.5 * tt) * 0.3) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.13 * tt))
    air = lp(noise(DUR, 9), 60); air /= np.abs(air).max() + 1e-9
    fx = np.zeros(n, np.float32)
    for a, b in A.get('ring', []): put(fx, ringtone(b - a), a, 0.22)
    for a, b in A.get('ring_pocket', []): put(fx, bandpass(ringtone(b - a), 300, 1800) * 1.6, a, 0.3)   # étouffée (dans la poche)
    for k_ in A.get('knock', []): put(fx, knock(int(k_ * 100)), k_, 0.55)
    for k_ in A.get('knock_heavy', []): put(fx, knock(int(k_ * 100), True), k_, 0.8)
    for b in A.get('doorbell', []):
        for j, f0 in enumerate((659, 523)):
            nn = int(0.9 * SR); tb = np.arange(nn) / SR; put(fx, ((np.sin(2 * np.pi * f0 * tb) + 0.3 * np.sin(2 * np.pi * f0 * 2.01 * tb)) * np.exp(-tb * 3.2)).astype(np.float32), b + j * 0.45, 0.28)
    for b in A.get('lock', []):
        for j in range(2): cl = noise(0.05, 30 + j); put(fx, (lp(cl, 3) * np.exp(-np.arange(len(cl)) / SR * 90)).astype(np.float32), b + j * 0.12, 0.6)
    for b in A.get('thud', []): put(fx, knock(3, True), b, 1.0)
    for b in A.get('buzz', []): put(fx, wavf('buzz') * 0.6, b, 0.55)
    for b in A.get('beep', []):
        d = 0.18; tb = np.arange(int(d * SR)) / SR; bp = (np.sin(2 * np.pi * 425 * tb) * 0.5).astype(np.float32); put(fx, bp, b, 0.3); put(fx, bp, b + 0.35, 0.3); put(fx, bp, b + 0.7, 0.3)
    for i, s in enumerate(A['stingers']): put(fx, stinger(i), s, 0.8)
    for a, b in A['heart']:
        t = a
        while t < b: put(fx, beat(), t, 0.7); put(fx, beat(), t + 0.2, 0.45); t += 0.6
    for a, d in A.get('creak', []): put(fx, creak(d, int(a)), a, 0.12)
    for k in A.get('steps_out', []): put(fx, gravel(), k, 0.5)
    for a, b in A.get('wind', []):
        w_ = bandpass(noise(b - a, 12), 120, 900); w_ *= (0.6 + 0.4 * np.sin(np.arange(len(w_)) / SR * 2 * np.pi * 0.3)); w_ *= np.minimum(1, np.arange(len(w_)) / (0.5 * SR)); put(fx, w_ / (np.abs(w_).max() + 1e-9), a, 0.12)
    for a, b in A.get('rewind', []):
        d = b - a; nn = int(d * SR); s_ = np.arange(nn) / SR
        wh = np.sin(2 * np.pi * np.cumsum(np.linspace(300, 1400, nn)) / SR) * 0.3 + lp(noise(d, 4), 2) * 0.5
        put(fx, (wh * np.minimum(1, s_ / 0.05)).astype(np.float32), a, 0.35)
    for a, b in A.get('riser', []):
        d = b - a; x = noise(d, 3); x = x - lp(x, 30); x *= np.linspace(0, 1, len(x)) ** 2; put(fx, x, a, 0.1)
    for a, b in A.get('muffle', []):   # voix derrière la porte : étouffée
        i0, i1 = int(a * SR), int(b * SR); v[i0:i1] = bandpass(v[i0:i1].copy(), 90, 1500) * 1.5
    ve = lp(np.abs(v), 4410); duck = 1 - 0.4 * np.clip(ve / (ve.max() * 0.25 + 1e-9), 0, 1)
    mus = np.zeros(n, np.float32)
    if A.get('music'):
        mu = loada(os.path.join(EP, A['music']))[:n]; mus[:len(mu)] = mu; mus *= A.get('music_gain', 0.22) / (np.abs(mus).max() + 1e-9)
        for a, b in A.get('music_low', []): i0, i1 = int(a * SR), int(b * SR); mus[i0:i1] *= 0.35   # pendant le rembobinage
    out = v + (drone * 0.03 + air * 0.015) * duck + mus * (1 - 0.45 * np.clip(ve / (ve.max() * 0.25 + 1e-9), 0, 1)) + fx
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
