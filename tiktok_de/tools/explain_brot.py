# Vidéo explicative « Brot im Kühlschrank? » – même feuille du début à la fin, sans transition glissée :
# l'ancien dessin s'efface vite et le suivant se dessine trait par trait. Export en vrai 4K (2160×3840) :
# les dessins sont calculés à 2× et ne sont plus réduits ; images envoyées directement à ffmpeg (pas de fichiers).
# usage : explain_brot.py dossier sortie.mp4  [PREVIEW=t1,t2,...] [K=2 (4K) | K=1 (1080p)] [TAIL=0.5]
import sys, os, re, math, json, subprocess, shutil, wave
import numpy as np
from multiprocessing import Pool
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe(); DIR, OUT = sys.argv[1], sys.argv[2]
W, H, FPS, SS = 1080, 1920, 60, 2
BG = (229, 219, 201); INK = (42, 37, 33); RED = (204, 60, 46); GREY = (120, 110, 100); YEL = (255, 226, 40)
BLUE = (60, 110, 190); GREEN = (40, 160, 90); SKIN = (236, 200, 172); WHITE = (252, 250, 245); BROWN = (120, 80, 50)
FD = '/home/user/skillora./temu/fonts/'; SFXD = '/home/user/skillora./motion/sfx/'
NAME, HANDLE = 'arkonees.', '@arkonees'
_fc = {}
def F(n, s):
    k = (n, int(s))
    if k not in _fc: _fc[k] = ImageFont.truetype(FD + n, int(s))
    return _fc[k]
def H2(s): return F('Caveat.ttf', S(s * 1.45))
def BF(s): return F('Poppins-ExtraBold.ttf', S(s))
# ---------- voix, mots, pauses
WORDS = json.load(open(os.path.join(DIR, 'words_final.json'))); BEATS = json.load(open(os.path.join(DIR, 'beats.json')))
SR = 44100; wv = wave.open(os.path.join(DIR, 'voix_final.wav')); VOICE = np.frombuffer(wv.readframes(wv.getnframes()), '<i2').astype(float) / 32768
DUR = len(VOICE) / SR + float(os.environ.get('TAIL', 0.5)); K = int(os.environ.get('K', 2))      # K : taille de sortie (2 = 4K)
def cw(w): return re.sub(r"[^\wäöüß'-]", '', w).lower()
def tw(word, n=0, end=False):
    m = [x for x in WORDS if cw(x[0]) == word.lower()]
    return (m[n][2] if end else m[n][1]) if len(m) > n else None
def tbefore(word):   # début du mot qui précède
    i = [k for k, x in enumerate(WORDS) if cw(x[0]) == word.lower()][0]; return WORDS[i - 1][1]
BT = {b['name']: b for b in BEATS}
# ---------- outils
def ease(u): u = max(0, min(1, u)); return 1 - (1 - u) ** 3
def eio(u): u = max(0, min(1, u)); return u * u * (3 - 2 * u)
def back(u): u = max(0, min(1, u)); c = 1.7; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2
def clamp(u): return max(0, min(1, u))
def S(v): return int(round(v * SS))
def since(t, t0, d=0.35): return clamp((t - t0) / d) if t0 is not None else 0
def arc(d, cx, cy, r, a0, a1, col, w):
    if a1 - a0 < 0.5 or r <= 0: return
    d.arc([S(cx - r), S(cy - r), S(cx + r), S(cy + r)], a0, a1, fill=col, width=max(1, S(w)))
def line(d, x0, y0, x1, y1, col, w, p=1.0):
    if p <= 0: return
    p = min(1, p); xe, ye = x0 + (x1 - x0) * p, y0 + (y1 - y0) * p
    d.line([S(x0), S(y0), S(xe), S(ye)], fill=col, width=S(w))
    r = S(w) / 2
    for x, y in ((x0, y0), (xe, ye)): d.ellipse([S(x) - r, S(y) - r, S(x) + r, S(y) + r], fill=col)
def poly(d, pts, col, w, p=1.0, closed=False):
    # polyligne qui se dessine progressivement (p de 0 à 1)
    if p <= 0 or len(pts) < 2: return
    if closed: pts = list(pts) + [pts[0]]
    L = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]; tot = sum(L) * min(1, p); acc = 0; out = [pts[0]]
    for (a, b), l in zip(zip(pts, pts[1:]), L):
        if acc + l >= tot: q = (tot - acc) / l if l else 0; out.append((a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q)); break
        out.append(b); acc += l
    d.line([(S(x), S(y)) for x, y in out], fill=col, width=S(w), joint='curve')
def rect(d, x0, y0, x1, y1, col, w, p=1.0, r=24, fill=None):
    if p >= 1 or fill:
        if p > 0: d.rounded_rectangle([S(x0), S(y0), S(x1), S(y1)], S(r), outline=col, width=S(w), fill=fill)
        return
    poly(d, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], col, w, p, closed=True)
def circ(d, cx, cy, r, col=None, fill=None, w=6):
    d.ellipse([S(cx - r), S(cy - r), S(cx + r), S(cy + r)], outline=col, width=S(w) if col else 0, fill=fill)
def comp(img, lay, x, y):
    x, y = int(x), int(y); cx0, cy0 = max(0, -x), max(0, -y)
    if cx0 >= lay.width or cy0 >= lay.height or x >= img.width or y >= img.height: return
    img.alpha_composite(lay.crop((cx0, cy0, min(lay.width, img.width - x), min(lay.height, img.height - y))), (x + cx0, y + cy0))
def text(img, xy, s, f, col, alpha=1.0, anchor='mm', rot=0, scale=1.0):
    # texte rendu dans une petite image (rapide), avec alpha, rotation et échelle
    if alpha <= 0.01 or scale <= 0.01: return
    if scale != 1.0: f = ImageFont.truetype(f.path, max(4, int(f.size * scale)))
    bb = f.getbbox(s, anchor=anchor); pad = 6; w, h = bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad
    t = Image.new('RGBA', (w, h), (0, 0, 0, 0)); ImageDraw.Draw(t).text((-bb[0] + pad, -bb[1] + pad), s, font=f, fill=tuple(col) + (int(255 * alpha),), anchor=anchor)
    if rot:
        t = t.rotate(rot, expand=True, resample=Image.BICUBIC); comp(img, t, S(xy[0]) - t.width / 2, S(xy[1]) - t.height / 2)
    else: comp(img, t, S(xy[0]) + bb[0] - pad, S(xy[1]) + bb[1] - pad)
def cross(d, cx, cy, r, p, col=RED, w=10):
    line(d, cx - r, cy - r, cx + r, cy + r, col, w, clamp(p * 2)); line(d, cx + r, cy - r, cx - r, cy + r, col, w, clamp(p * 2 - 1))
def check(d, cx, cy, r, p, col=GREEN, w=11):
    line(d, cx - r, cy, cx - r * 0.3, cy + r * 0.7, col, w, clamp(p * 2)); line(d, cx - r * 0.3, cy + r * 0.7, cx + r, cy - r * 0.8, col, w, clamp(p * 2 - 1))
def arrow(d, x0, y0, x1, y1, col, w=8, p=1.0, head=30):
    if p <= 0: return
    xe, ye = x0 + (x1 - x0) * min(1, p), y0 + (y1 - y0) * min(1, p); line(d, x0, y0, xe, ye, col, w)
    a = math.atan2(ye - y0, xe - x0)
    d.polygon([(S(xe + 6 * math.cos(a)), S(ye + 6 * math.sin(a))), (S(xe - head * math.cos(a - 0.45)), S(ye - head * math.sin(a - 0.45))), (S(xe - head * math.cos(a + 0.45)), S(ye - head * math.sin(a + 0.45)))], fill=col)
def underline(d, x0, x1, y, col, p, w=8):
    if p > 0: poly(d, [(x0, y), ((x0 + x1) / 2, y + 4), (x1, y - 2)], col, w, p)
# ---------- objets dessinés
ICE = (214, 232, 244); OIL = (214, 160, 40); SMOKE = (150, 145, 140); COLD = (70, 120, 200)
def sub(img, alpha, fn):
    # dessine un groupe d'objets dans un calque à part, puis le pose avec une transparence (effacement rapide)
    if alpha <= 0.01: return
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); fn(lay, ImageDraw.Draw(lay))
    if alpha < 0.99: lay.putalpha(lay.getchannel('A').point(lambda v: int(v * alpha)))
    img.alpha_composite(lay)
def gone(t, t1, d=0.18): return 1 - since(t, t1 - d, d) if t1 else 1      # visible jusqu'à t1, puis s'efface
def clock(d, cx, cy, r, t, speed, p):
    if p <= 0: return
    arc(d, cx, cy, r, -90, -90 + 360 * ease(p), INK, 8)
    if p < 0.8: return
    for k in range(12): a = k * math.pi / 6; line(d, cx + (r - 22) * math.cos(a), cy + (r - 22) * math.sin(a), cx + (r - 8) * math.cos(a), cy + (r - 8) * math.sin(a), INK, 4)
    a1 = t * speed - math.pi / 2; a2 = t * speed / 12 - math.pi / 2
    line(d, cx, cy, cx + r * 0.75 * math.cos(a1), cy + r * 0.75 * math.sin(a1), INK, 6); line(d, cx, cy, cx + r * 0.5 * math.cos(a2), cy + r * 0.5 * math.sin(a2), INK, 9)
def drop(d, cx, cy, r, col, stretch=1.0):
    d.ellipse([S(cx - r), S(cy - r), S(cx + r), S(cy + r)], fill=col + (255,))
    d.polygon([(S(cx - r * 0.92), S(cy - r * 0.35)), (S(cx), S(cy - r * (1.0 + 1.3 * stretch))), (S(cx + r * 0.92), S(cy - r * 0.35))], fill=col + (255,))
def share(img, d, cx, cy, p):
    for (x, y) in ((cx - 170, cy), (cx + 150, cy - 140), (cx + 150, cy + 140)): arc(d, x, y, 62, -90, -90 + 360 * ease(p), INK, 9)
    line(d, cx - 115, cy - 25, cx + 95, cy - 115, INK, 8, ease(p - 0.4)); line(d, cx - 115, cy + 25, cx + 95, cy + 115, INK, 8, ease(p - 0.4))
# ---------- objets dessinés
COLD = (70, 120, 200); CRUST = (196, 132, 66); CRUMB = (246, 226, 186); MOLD = (90, 150, 80); FROST = (205, 228, 246)
def mix(c1, c2, u): return tuple(int(a + (b - a) * clamp(u)) for a, b in zip(c1, c2))
def loaf(img, d, cx, cy, s, p, stale=0.0, gold=0.0, t=0, mold=0.0):
    # miche vue de côté : dôme, entailles ; rassis = plus pâle + fissures ; doré = croûte qui brille
    if p <= 0: return
    pts = [(cx + 230 * s * math.cos(a), cy - 150 * s * math.sin(a) ** 0.8) for a in np.linspace(0, math.pi, 30)] + [(cx - 230 * s, cy), (cx + 230 * s, cy)]
    col = mix(mix(CRUST, (190, 172, 140), stale), (214, 140, 50), gold)
    if p >= 0.6: d.polygon([(S(x), S(y)) for x, y in pts], fill=col + (255,))
    poly(d, pts[:30] + [(cx - 230 * s, cy), (cx + 230 * s, cy)], INK, 7, ease(p / 0.6))
    if p < 0.6: return
    for k in (-1, 0, 1): line(d, cx + k * 95 * s - 40 * s, cy - 115 * s + abs(k) * 20 * s, cx + k * 95 * s + 40 * s, cy - 75 * s + abs(k) * 20 * s, mix(INK, col, 0.45), 6)
    if stale > 0.05:   # fissures
        for k, (x0, y0) in enumerate(((-120, -60), (40, -110), (150, -40), (-30, -30))):
            pts2 = [(cx + (x0 + j * 18 * (1 if k % 2 else -1)) * s, cy + (y0 + j * 14 - 8 * (j % 2)) * s) for j in range(5)]; poly(d, pts2, INK, 4, stale)
    if mold > 0:
        for k in range(9): rs = np.random.RandomState(k); circ(d, cx + rs.uniform(-170, 170) * s, cy - rs.uniform(20, 110) * s, rs.uniform(10, 22) * s * mold, None, MOLD + (230,))
    if gold > 0.5:
        for k in range(4):
            a = k * 1.6 + t * 0.8; x, y = cx + (150 + 60 * math.sin(k)) * s * math.cos(a) , cy - 170 * s + 30 * s * math.sin(a * 2); r = 16 * s * (0.6 + 0.4 * math.sin(t * 9 + k))
            line(d, x - r, y, x + r, y, (250, 200, 60), 5); line(d, x, y - r, x, y + r, (250, 200, 60), 5)
def fridge(img, d, cx, cy, p, door=1.0):
    # frigo ouvert : caisson, étagères, intérieur bleuté, porte ouverte à gauche
    if p <= 0: return
    w, h = 400, 640; x0, y0 = cx - w / 2, cy - h / 2
    if p >= 0.6: d.rectangle([S(x0), S(y0), S(x0 + w), S(y0 + h)], fill=(226, 238, 246, 255))
    rect(d, x0, y0, x0 + w, y0 + h, INK, 8, ease(p / 0.6), 18)
    if p < 0.6: return
    for k in (1, 2, 3): line(d, x0 + 20, y0 + k * h / 4, x0 + w - 20, y0 + k * h / 4, GREY, 5)
    dw = 150 * door; poly(d, [(x0, y0), (x0 - dw, y0 + 40), (x0 - dw, y0 + h - 40), (x0, y0 + h)], INK, 8, closed=True)
    d.polygon([(S(x0), S(y0)), (S(x0 - dw), S(y0 + 40)), (S(x0 - dw), S(y0 + h - 40)), (S(x0), S(y0 + h))], fill=(240, 240, 236, 255)); poly(d, [(x0, y0), (x0 - dw, y0 + 40), (x0 - dw, y0 + h - 40), (x0, y0 + h)], INK, 8, closed=True)
def thermo(img, d, x, y, val, label, col, p):
    if p <= 0: return
    d.rounded_rectangle([S(x - 18), S(y - 200), S(x + 18), S(y)], S(18), fill=WHITE + (255,), outline=INK, width=S(6)); circ(d, x, y + 22, 36, INK, col + (255,), 6)
    d.rectangle([S(x - 8), S(y - 190 * clamp(val) * ease(p)), S(x + 8), S(y + 10)], fill=col + (255,)); text(img, (x, y + 100), label, BF(54), col, p)
def calendar(img, d, cx, cy, label, p, col=RED):
    if p <= 0: return
    s = back(p); w, h = 170 * s, 160 * s
    d.rounded_rectangle([S(cx - w / 2), S(cy - h / 2), S(cx + w / 2), S(cy + h / 2)], S(14), fill=WHITE + (255,), outline=INK, width=S(6))
    d.rectangle([S(cx - w / 2 + 3), S(cy - h / 2 + 3), S(cx + w / 2 - 3), S(cy - h / 2 + 46 * s)], fill=col + (255,)); text(img, (cx, cy + 20 * s), label, H2(46 * s), INK)
def granule(d, x, y, r, swell=0.0, crystal=0.0, water=0.0):
    # grain d'amidon : gonfle avec l'eau (plus gros, doux), puis se resserre en cristal (lignes droites, plus petit)
    rr = r * (1 + 0.45 * swell - 0.3 * crystal)
    fill = mix(mix((236, 226, 200), (210, 228, 246), water * (1 - crystal)), (225, 214, 186), crystal)
    circ(d, x, y, rr, INK, fill + (255,), 5)
    if crystal > 0.05:
        for k in (-1, 0, 1): line(d, x - rr * 0.6, y + k * rr * 0.35, x + rr * 0.6, y + k * rr * 0.35, INK, 3, crystal)
def breadbox(img, d, cx, cy, p):
    if p <= 0: return
    q = back(p); w, h = 330 * q, 220 * q
    d.rounded_rectangle([S(cx - w / 2), S(cy - h / 2), S(cx + w / 2), S(cy + h / 2)], S(40), fill=(214, 172, 120, 255), outline=INK, width=S(7))
    arc(d, cx, cy - h / 2 + 50 * q, w / 2 - 10, 200, 340, INK, 6); text(img, (cx, cy + 20 * q), 'BROT', BF(54 * q), WHITE)
def claypot(img, d, cx, cy, p):
    if p <= 0: return
    q = back(p); pts = [(cx - 120 * q, cy - 90 * q), (cx + 120 * q, cy - 90 * q), (cx + 95 * q, cy + 110 * q), (cx - 95 * q, cy + 110 * q)]
    d.polygon([(S(x), S(y)) for x, y in pts], fill=(196, 110, 70, 255)); poly(d, pts, INK, 7, closed=True)
    d.rounded_rectangle([S(cx - 135 * q), S(cy - 125 * q), S(cx + 135 * q), S(cy - 90 * q)], S(14), fill=(176, 96, 60, 255), outline=INK, width=S(6)); circ(d, cx, cy - 140 * q, 18 * q, INK, (176, 96, 60, 255), 5)
def board(img, d, cx, cy, p):
    if p <= 0: return
    rect(d, cx - 330, cy, cx + 330, cy + 50, INK, 7, ease(p), 14, fill=(206, 160, 104, 255) if p >= 1 else None)
def bag(img, d, cx, cy, p):
    if p <= 0: return
    pts = [(cx - 190, cy - 160), (cx + 190, cy - 160), (cx + 210, cy + 170), (cx - 210, cy + 170)]
    d.polygon([(S(x), S(y)) for x, y in pts], fill=(225, 235, 240, 140)); poly(d, pts, GREY, 6, ease(p), closed=True)
    for k in (-1, 1): arc(d, cx + k * 90, cy - 160, 50, 180, 360, GREY, 6)
def freezer(img, d, cx, cy, p):
    if p <= 0: return
    rect(d, cx - 190, cy - 150, cx + 190, cy + 150, INK, 8, ease(p), 18, fill=FROST + (255,) if p >= 1 else None)
    if p >= 1:
        for a in range(3): line(d, cx - 60 * math.cos(a * 1.05), cy - 60 * math.sin(a * 1.05), cx + 60 * math.cos(a * 1.05), cy + 60 * math.sin(a * 1.05), COLD, 9)
def slice_(d, cx, cy, s, rot=0):
    a = math.radians(rot); P = lambda x, y: (cx + (x * math.cos(a) - y * math.sin(a)) * s, cy + (x * math.sin(a) + y * math.cos(a)) * s)
    pts = [P(-60, 70), P(-60, -20), P(-40, -60), (P(0, -72)), P(40, -60), P(60, -20), P(60, 70)]
    d.polygon([(S(x), S(y)) for x, y in pts], fill=CRUMB + (255,)); poly(d, pts, CRUST, 9, closed=True)
def toaster(img, d, cx, cy, p, pop=0.0):
    if p <= 0: return
    slice_(d, cx - 50, cy - 110 - 90 * back(pop), 1.0); slice_(d, cx + 55, cy - 110 - 70 * back(pop), 1.0)
    rect(d, cx - 170, cy - 120, cx + 170, cy + 110, INK, 8, ease(p), 40, fill=(200, 205, 210, 255) if p >= 1 else None)
    if p >= 1: line(d, cx - 110, cy - 120, cx - 10, cy - 120, INK, 12); line(d, cx + 10, cy - 120, cx + 110, cy - 120, INK, 12); circ(d, cx + 130, cy + 20, 16, INK, WHITE + (255,), 5)
def oven(img, d, cx, cy, p, heat=0.0, t=0):
    if p <= 0: return
    rect(d, cx - 280, cy - 230, cx + 280, cy + 230, INK, 8, ease(p), 22, fill=(236, 232, 226, 255) if p >= 1 else None)
    if p < 1: return
    glow = mix((70, 66, 64), (250, 150, 60), heat * (0.85 + 0.15 * math.sin(t * 6)))
    d.rounded_rectangle([S(cx - 220), S(cy - 130), S(cx + 220), S(cy + 180)], S(16), fill=glow + (255,), outline=INK, width=S(6))
    for k in range(4): circ(d, cx - 180 + k * 120, cy - 185, 18, INK, WHITE + (255,), 5)
def sparkle(d, x, y, r, col=(250, 200, 60)):
    line(d, x - r, y, x + r, y, col, 6); line(d, x, y - r, x, y + r, col, 6); line(d, x - r * 0.6, y - r * 0.6, x + r * 0.6, y + r * 0.6, col, 4); line(d, x - r * 0.6, y + r * 0.6, x + r * 0.6, y - r * 0.6, col, 4)
# ---------- repères temporels
T = dict(kuehl=tw('kühlschrank'), frisch=tw('frisch'), quatsch=tw('quatsch'), dreimal=tw('dreimal'), alt=tw('alt'), morgens=tw('morgens'), naechsten=tw('nächsten'),
         trocken=tw('trocken'), zaeh=tw('zäh'), austrocknet=tw('austrocknet'), staerke=tw('stärke'), backen=tw('backen'), wasser=tw('wasser'), weich=tw('weich'),
         zusammen=tw('zusammenzuziehen'), hart=tw('hart'), altbacken=tw('altbacken'), vorgang=tw('vorgang'), ktemp=tw('kühlschranktemperatur'), vier=tw('vier'), turbo=tw('turbo'),
         gefrier=tw('gefrierfach'), stehen=tw('stehen'), also=tw('also'), brotkasten=tw('brotkasten'), tontopf=tw('tontopf'), schnitt=tw('schnittfläche'), brett=tw('brett'),
         plastik=tw('plastiktüte'), kruste=tw('kruste'), schimmelt=tw('schimmelt'), scheiben=tw('scheiben'), einfrieren=tw('einfrieren'), morgen=tw('morgen'), jetzt=tw('jetzt'),
         retten=tw('retten'), bespritzen=tw('bespritzen'), ofen=tw('ofen'), weich2=tw('weich', 1), baecker=tw('bäcker'), danach2=tw('danach', 1), hart2=tw('hart', 1),
         essen=tw('essen'), sags=tw("sag's"), im=tw('im'), beim=tw('beim'))
for k, v in T.items():
    if v is None: print('mot introuvable :', k)
SC = [0, T['im'] - 0.12, T['beim'] - 0.12, T['also'] - 0.12, T['jetzt'] - 0.3, T['danach2'] - 0.12, T['sags'] - 0.12, DUR]
SOURCE = (T['dreimal'] - 0.2, T['also'] - 0.3)     # source affichée pendant les chiffres
# ---------- caméra : très léger zoom continu + petits zooms d'impact (pas de transition glissée)
PUNCH = [(T['quatsch'], 0.06), (T['dreimal'], 0.05), (T['turbo'], 0.05), (T['schimmelt'], 0.04), (T['baecker'], 0.04)]
SHAKE = [(T['quatsch'], 12), (T['turbo'], 10)]
def camera(t, sc):
    a0, a1 = SC[sc], SC[sc + 1]; z = 1.02 + 0.025 * eio((t - a0) / max(1, a1 - a0))
    for t0, amp in PUNCH:
        if t0 and 0 <= t - t0 < 0.6: z += amp * math.exp(-(t - t0) * 7) * min(1, (t - t0) / 0.05)
    ox = oy = 0
    for t0, amp in SHAKE:
        if t0 and 0 <= t - t0 < 0.4: k = (1 - (t - t0) / 0.4) ** 2; ox += amp * k * math.sin((t - t0) * 95); oy += amp * k * math.cos((t - t0) * 83)
    return z, 0.5, 0.42, ox, oy
# ---------- texture papier + vignette à la taille de sortie
_rs = np.random.RandomState(7); NOISE = np.asarray(Image.fromarray((_rs.normal(128, 9, (H * K, W * K))).clip(0, 255).astype('uint8')).filter(ImageFilter.GaussianBlur(0.8 * K))).astype(np.int16) - 128
yy, xx = np.mgrid[0:H * K, 0:W * K]; VIG = (1 - 0.10 * (((xx - W * K / 2) / (W * K / 2)) ** 2 + ((yy - H * K * 0.45) / (H * K * 0.6)) ** 2)).clip(0.82, 1)[..., None].astype(np.float32); del yy, xx
# ---------- sous-titres : 3 mots max, mot actif qui « pop », mots clés en jaune (dessinés à la taille de sortie)
HOT = re.compile(r'(\d|quatsch|kühlschrank|brot|stärke|wasser|altbacken|turbo|grad|gefrierfach|brotkasten|tontopf|schnittfläche|plastiktüte|schimmelt|einfrieren|retten|ofen|bäcker|hart|dreimal|frisch|zäh)', re.I)
GROUPS = []; cur = []
for k, w in enumerate(WORDS):
    cur.append(k)
    if len(cur) == 3 or re.search(r'[.,:!?–]$', w[0]): GROUPS.append(cur); cur = []
if cur: GROUPS.append(cur)
def caption(img, t):
    g = next((g for g in GROUPS if WORDS[g[0]][1] - 0.05 <= t < WORDS[g[-1]][2] + 0.3), None)
    if not g: return
    ws = [WORDS[k][0].strip('.,:!?„“"').upper() for k in g]; base = 56 * K; cf = F('Poppins-ExtraBold.ttf', base)
    wd = [cf.getbbox(w)[2] for w in ws]; sp = 20 * K; tw_ = sum(wd) + sp * (len(ws) - 1)
    if tw_ > (W - 120) * K: base = int(base * (W - 120) * K / tw_); cf = F('Poppins-ExtraBold.ttf', base); wd = [cf.getbbox(w)[2] for w in ws]; tw_ = sum(wd) + sp * (len(ws) - 1)
    d = ImageDraw.Draw(img); x = W * K / 2 - tw_ / 2; y = 1390 * K
    for w, k, ww in zip(ws, g, wd):
        t0 = WORDS[k][1]
        if t >= t0 - 0.03:
            u = (t - t0) / 0.12; pop = 1 + 0.14 * math.sin(clamp(u) * math.pi) if u < 1 else 1
            f2 = F('Poppins-ExtraBold.ttf', base * pop) if pop != 1 else cf
            d.text((x + ww / 2, y), w, font=f2, fill=YEL if HOT.search(w) else (255, 255, 255), anchor='mm', stroke_width=6 * K, stroke_fill=(0, 0, 0))
        x += ww + sp
# ---------- les scènes (tout se dessine sur la même feuille)
def scene(img, d, sc, t):
    CX = W / 2; u0 = t - SC[sc]
    if sc == 0:   # frigo ouvert, pain dedans, 4 °C ; croix rouge sur « Quatsch »
        fridge(img, d, 610, 860, u0 / 0.5, door=ease((u0 - 0.2) / 0.5))
        if u0 > 0.4: loaf(img, d, 610, 790, 0.62, (u0 - 0.4) / 0.4)
        if T['frisch'] and t > T['frisch'] - 0.2: thermo(img, d, 200, 900, 0.25, '4 °C', COLD, since(t, T['frisch'] - 0.2, 0.4)); text(img, (610, 450), 'länger frisch?', H2(66), INK, since(t, T['frisch'] - 0.2, 0.3))
        if T['quatsch'] and t > T['quatsch'] - 0.05:
            cross(d, 610, 860, 220, since(t, T['quatsch'] - 0.05, 0.35), RED, 16)
            k = since(t, T['quatsch'], 0.2); text(img, (CX, 1220), 'Quatsch!', BF(110), RED, k, rot=-6, scale=1.5 - 0.5 * k)
    elif sc == 1:  # 3× plus vite ; aujourd'hui → demain : le pain se fissure ; ce n'est pas l'eau, c'est l'amidon
        A = gone(t, T['austrocknet'] - 0.15)
        def fast(lay, dl):
            k = since(t, SC[1], 0.4); clock(dl, 250, 560, 95, t * 4, 10, k); text(lay, (250, 720), 'im Kühlschrank', H2(52), COLD, k)
            if T['dreimal'] and t > T['dreimal'] - 0.1:
                q = since(t, T['dreimal'] - 0.1, 0.25); text(lay, (700, 560), '3× schneller', BF(84), RED, q, scale=1.4 - 0.4 * ease(q)); text(lay, (700, 660), 'alt', H2(70), RED, q)
            if T['morgens'] and t > T['morgens'] - 0.2:
                calendar(lay, dl, 270, 960, 'heute', since(t, T['morgens'] - 0.2, 0.35), COLD); loaf(lay, dl, 270, 1180, 0.45, 1)
            if T['naechsten'] and t > T['naechsten'] - 0.2:
                k2 = since(t, T['naechsten'] - 0.2, 0.35); arrow(dl, 420, 1080, 580, 1080, INK, 7, k2); calendar(lay, dl, 760, 960, 'morgen', k2, RED)
                loaf(lay, dl, 760, 1180, 0.45, k2, stale=since(t, T['trocken'] - 0.1, 0.6) if T['trocken'] else 0)
                if T['zaeh'] and t > T['zaeh'] - 0.1: text(lay, (760, 1260), 'trocken & zäh', H2(54), RED, since(t, T['zaeh'] - 0.1, 0.3))
        sub(img, A, fast)
        if T['austrocknet'] and t > T['austrocknet'] - 0.2:
            k = since(t, T['austrocknet'] - 0.2, 0.35); drop(d, 300, 760, 70, (110, 170, 230), 1.1); cross(d, 300, 720, 110, since(t, T['austrocknet'], 0.35), RED, 12)
            text(img, (300, 920), 'nicht das Wasser', H2(56), INK, k)
            if T['staerke'] and t > T['staerke'] - 0.2:
                q = since(t, T['staerke'] - 0.2, 0.4); text(img, (770, 920), 'die Stärke', BF(66), RED, q)
                for j, (x, y) in enumerate(((700, 700), (800, 690), (750, 780), (850, 780), (660, 790))): granule(d, x, y, 40 * back(clamp(q * 1.5 - j * 0.1)))
    elif sc == 2:  # l'amidon gonfle avec l'eau, puis se resserre (rassis) ; courbe : 4 °C = turbo, congélateur = stop
        A = gone(t, T['vorgang'] - 0.15)
        def starch(lay, dl):
            sw = since(t, T['wasser'] - 0.2, 1.0); cr = since(t, T['zusammen'] - 0.1, 1.4)
            text(lay, (CX, 470), 'Stärke', H2(72), INK, clamp(u0 / 0.3))
            for j in range(9):
                x, y = 300 + (j % 3) * 240, 650 + (j // 3) * 200; granule(dl, x, y, 55 * back(clamp(u0 / 0.4 - j * 0.05)), sw * (1 - cr), cr, sw)
            if T['wasser'] and t > T['wasser'] - 0.3 and cr < 0.5:
                for j in range(10): q = ((t - T['wasser']) * 1.2 + j / 10) % 1; drop(dl, 180 + j * 80, 520 + 500 * q, 14, (110, 170, 230), 0.7)
            if T['weich'] and t > T['weich'] - 0.1 and cr < 0.3: text(lay, (CX, 1230), 'weich', BF(70), COLD, since(t, T['weich'] - 0.1, 0.3) * (1 - cr * 3))
            if cr > 0:
                for j in range(9):   # l'eau est chassée
                    x, y = 300 + (j % 3) * 240, 650 + (j // 3) * 200; q = clamp(cr * 1.5 - 0.3); drop(dl, x + 70 * q, y - 60 * q, 10, (110, 170, 230), 0.5) if q < 1 else None
                text(lay, (CX, 1230), 'hart', BF(70), RED, cr)
            if T['altbacken'] and t > T['altbacken'] - 0.1: text(lay, (CX, 1300), 'altbacken', H2(64), RED, since(t, T['altbacken'] - 0.1, 0.3))
        sub(img, A, starch)
        if T['vorgang'] and t > T['vorgang'] - 0.2:   # graphique : vitesse du rassissement selon la température
            k = since(t, T['vorgang'] - 0.2, 0.5); ox, oy, gw, gh = 150, 1150, 800, 560
            line(d, ox, oy, ox + gw, oy, INK, 7, k); line(d, ox, oy, ox, oy - gh, INK, 7, k)
            text(img, (ox + 10, oy - gh - 100), 'wie schnell Brot alt wird', H2(50), GREY, k, anchor='lm'); text(img, (ox + gw - 10, oy - 40), 'Temperatur', H2(44), GREY, k, anchor='rm')
            def xt(c): return ox + gw * (c + 20) / 50       # de −20 °C à +30 °C
            def spd(c): return 0.04 if c < -5 else (math.exp(-((c - 4) / 9) ** 2) * 0.95 + 0.08)
            q = since(t, T['ktemp'] - 0.3, 1.2) if T['ktemp'] else 0
            curve = [(xt(c), oy - gh * 0.95 * spd(c)) for c in np.linspace(-20, 30, 60)]
            poly(d, curve, RED, 8, q)
            for c, lab, col in ((-18, '−18 °C', COLD), (4, '4 °C', RED), (21, '21 °C', INK)): text(img, (xt(c), oy + 45), lab, BF(36), col, k)
            if T['turbo'] and t > T['turbo'] - 0.1:
                q2 = since(t, T['turbo'] - 0.1, 0.25); text(img, (xt(4) + 230, oy - gh * 0.95 + 40), 'TURBO', BF(76), RED, q2, scale=1.4 - 0.4 * q2); circ(d, xt(4), oy - gh * 0.95 * spd(4), 16, None, RED + (255,))
            if T['gefrier'] and t > T['gefrier'] - 0.1:
                q3 = since(t, T['gefrier'] - 0.1, 0.3); text(img, (xt(-14), oy - 150), 'Gefrierfach', H2(48), COLD, q3); text(img, (xt(-14), oy - 90), 'Stopp', BF(54), COLD, since(t, T['stehen'] - 0.1, 0.3) if T['stehen'] else q3)
    elif sc == 3:  # rangement : boîte à pain / pot, côté coupé sur la planche, pas de sac plastique, congélation en tranches, grille-pain
        A = gone(t, T['schnitt'] - 0.15); B = gone(t, T['plastik'] - 0.12) if t > T['schnitt'] - 0.3 else 0
        Cv = gone(t, T['scheiben'] - 0.12) if t > T['plastik'] - 0.3 else 0
        def store(lay, dl):
            text(lay, (CX, 470), '2–3 Tage', H2(72), INK, clamp(u0 / 0.3))
            breadbox(lay, dl, 300, 820, since(t, T['brotkasten'] - 0.2, 0.4) if T['brotkasten'] else 0); claypot(lay, dl, 780, 840, since(t, T['tontopf'] - 0.2, 0.4) if T['tontopf'] else 0)
            if T['brotkasten'] and t > T['brotkasten']: check(dl, 300, 1050, 40, since(t, T['brotkasten'], 0.4))
            if T['tontopf'] and t > T['tontopf']: check(dl, 780, 1050, 40, since(t, T['tontopf'], 0.4))
        sub(img, A, store)
        def cutside(lay, dl):
            k = since(t, T['schnitt'] - 0.3, 0.4); board(lay, dl, CX, 960, k)
            loaf(lay, dl, CX + 60, 960, 0.85, k)
            dl.rectangle([S(CX + 60 - 200), S(950), S(CX + 60 - 192), S(960)], fill=CRUMB + (255,))
            if T['brett'] and t > T['brett'] - 0.2: text(lay, (330, 620), 'Schnittfläche', H2(60), INK, since(t, T['brett'] - 0.2, 0.3)); arrow(dl, 330, 670, CX - 140, 930, RED, 7, since(t, T['brett'] - 0.1, 0.4))
        sub(img, B, cutside)
        def plastic(lay, dl):
            k = since(t, T['plastik'] - 0.25, 0.4); bag(lay, dl, CX, 850, k); loaf(lay, dl, CX, 960, 0.6, k, mold=since(t, T['schimmelt'] - 0.2, 0.7) if T['schimmelt'] else 0)
            if T['kruste'] and t > T['kruste'] - 0.1: text(lay, (CX, 560), 'Kruste weich', H2(60), INK, since(t, T['kruste'] - 0.1, 0.3))
            if T['schimmelt'] and t > T['schimmelt'] - 0.1: cross(dl, CX, 860, 200, since(t, T['schimmelt'], 0.35), RED, 14); text(lay, (CX, 1180), 'Schimmel', BF(70), MOLD, since(t, T['schimmelt'] - 0.1, 0.3))
        sub(img, Cv, plastic)
        if T['scheiben'] and t > T['scheiben'] - 0.25:
            k = since(t, T['scheiben'] - 0.25, 0.4); freezer(img, d, 760, 760, since(t, T['einfrieren'] - 0.3, 0.4) if T['einfrieren'] else 0)
            for j in range(4):
                q = clamp((t - T['scheiben'] - j * 0.25) / 0.8); x = 250 + (700 - 250) * eio(q) + j * 25; y = 760 + 40 * j * (1 - q) - 160 * math.sin(math.pi * q)
                if q < 0.98: slice_(d, x, y, 0.9 * k, rot=-15 + 30 * q)
            if T['einfrieren'] and t > T['einfrieren']: text(img, (760, 960), 'einfrieren', BF(58), COLD, since(t, T['einfrieren'], 0.3))
            if T['morgen'] and t > T['morgen'] - 0.2: toaster(img, d, 330, 1130, since(t, T['morgen'] - 0.2, 0.4), pop=since(t, T['morgen'] + 0.6, 0.4)); text(img, (330, 1300), 'jeden Morgen', H2(52), INK, since(t, T['morgen'], 0.3))
    elif sc == 4:  # sauver le pain rassis : un peu d'eau, four chaud, il redevient croustillant
        st = 1 - since(t, T['weich2'] - 0.2, 0.8) if T['weich2'] else 1; gd = since(t, T['weich2'] - 0.2, 0.8) if T['weich2'] else 0
        heat = since(t, T['ofen'] - 0.2, 0.6) if T['ofen'] else 0
        if T['ofen'] and t > T['ofen'] - 0.3: oven(img, d, CX, 860, since(t, T['ofen'] - 0.3, 0.4), heat, t)
        loaf(img, d, CX, 960 if t > (T['ofen'] or 99) - 0.3 else 900, 0.75, clamp(u0 / 0.4), stale=st, gold=gd, t=t)
        if T['retten'] and t > T['retten'] - 0.1: text(img, (CX, 470), 'altes Brot retten', H2(74), INK, since(t, T['retten'] - 0.1, 0.3))
        if T['bespritzen'] and t > T['bespritzen'] - 0.2 and t < (T['ofen'] or 99):
            for j in range(9): q = ((t - T['bespritzen']) * 1.6 + j / 9) % 1; drop(d, 340 + j * 50, 560 + 260 * q, 13, (110, 170, 230), 0.7)
        if T['baecker'] and t > T['baecker'] - 0.3:
            q = since(t, T['baecker'] - 0.3, 0.3); text(img, (CX, 1220), 'wie frisch vom Bäcker', BF(58), (190, 120, 40), q)
            for j in range(5): sparkle(d, 300 + j * 120, 640 - 40 * math.sin(t * 4 + j), 16 + 8 * math.sin(t * 9 + j))
    elif sc == 5:  # il redurcit vite : manger tout de suite
        loaf(img, d, 330, 900, 0.6, clamp(u0 / 0.3), stale=since(t, T['hart2'] - 0.2, 0.6) if T['hart2'] else 0)
        clock(d, 780, 760, 100, t * 6, 14, clamp(u0 / 0.4)); text(img, (780, 920), 'schnell wieder hart', H2(52), RED, clamp((u0 - 0.3) / 0.3))
        if T['essen'] and t > T['essen'] - 0.2:
            k = since(t, T['essen'] - 0.2, 0.3); text(img, (CX, 1160), 'gleich essen!', BF(80), GREEN, k, scale=1.3 - 0.3 * k); check(d, 870, 1160, 40, since(t, T['essen'], 0.4))
    elif sc == 6:  # partage
        share(img, d, CX, 760, u0 / 0.7); text(img, (CX, 1120), "sag's weiter", H2(96), RED, clamp((u0 - 0.3) / 0.4)); underline(d, CX - 230, CX + 230, 1180, RED, ease((u0 - 0.6) / 0.5), 10)
def draw(t):
    sc = max(i for i in range(len(SC) - 1) if t >= SC[i])
    lay = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    scene(lay, d, sc, t)
    if SOURCE[0] <= t < SOURCE[1]: text(lay, (W / 2, 1468), 'Quelle: Verbraucherzentrale', H2(36), GREY, min(since(t, SOURCE[0], 0.3), 1 - since(t, SOURCE[1] - 0.3, 0.3)))
    tout = clamp((SC[sc + 1] - t) / 0.16) if sc < len(SC) - 2 else 1      # pas de transition glissée : effacement sur place
    if tout < 1: lay.putalpha(lay.getchannel('A').point(lambda v: int(v * tout)))
    img = Image.new('RGBA', (W * SS, H * SS), BG + (255,)); img.alpha_composite(lay)
    z, fx, fy, ox, oy = camera(t, sc); cw_, ch_ = W * SS / z, H * SS / z
    cx = min(max(W * SS * fx + S(ox), cw_ / 2), W * SS - cw_ / 2); cy = min(max(H * SS * fy + S(oy), ch_ / 2), H * SS - ch_ / 2)
    img = img.convert('RGB').resize((W * K, H * K), Image.LANCZOS, box=(cx - cw_ / 2, cy - ch_ / 2, cx + cw_ / 2, cy + ch_ / 2))
    arr = (np.asarray(img).astype(np.float32) * VIG + NOISE[..., None] * 0.6).clip(0, 255).astype('uint8'); img = Image.fromarray(arr)
    dd = ImageDraw.Draw(img); dd.text((70 * K, 185 * K), NAME, font=F('Caveat.ttf', 86 * K), fill=GREY, anchor='ls'); dd.text((72 * K, 250 * K), HANDLE, font=F('Caveat.ttf', 62 * K), fill=RED, anchor='ls')
    caption(img, t); return img
def frame_bytes(n): return draw(n / FPS).tobytes()
if __name__ == '__main__':
    if os.environ.get('PREVIEW'):
        for ts in os.environ['PREVIEW'].split(','): draw(float(ts)).resize((W, H), Image.LANCZOS).save(f'{OUT}_{ts}.jpg', quality=88)
        sys.exit(0)
    TMP = OUT + '_fr'; shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP); NF = int(DUR * FPS)
    # ---------- son : voix + effets synchronisés (pas de musique)
    N = int(DUR * SR); mix_ = np.zeros(N); mix_[:len(VOICE)] += VOICE
    def sfx(name, t0, g):
        if t0 is None: return
        w = wave.open(SFXD + name + '.wav'); s = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float) / 32768
        if w.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
        if w.getframerate() != SR: s = np.interp(np.arange(0, len(s), w.getframerate() / SR), np.arange(len(s)), s)
        i0 = int(max(0, t0) * SR); L = min(len(s), N - i0); mix_[i0:i0 + L] += s[:L] * g
    for t0 in SC[1:-1]: sfx('swish', t0 + 0.02, 0.1)
    sfx('pop', T['frisch'] - 0.2, 0.12); sfx('hit', T['quatsch'] - 0.03, 0.4); sfx('swish', T['quatsch'] - 0.05, 0.2); sfx('pop', T['dreimal'] - 0.1, 0.15); sfx('tap', T['naechsten'], 0.12)
    sfx('pop', T['staerke'], 0.12); sfx('tap', T['wasser'], 0.12); sfx('clank', T['zusammen'] + 0.3, 0.15); sfx('hit', T['turbo'] - 0.05, 0.25); sfx('pop', T['gefrier'], 0.12)
    sfx('ding', T['brotkasten'], 0.1); sfx('ding', T['tontopf'], 0.1); sfx('pop', T['schnitt'], 0.12); sfx('pop', T['schimmelt'], 0.15); sfx('swish', T['scheiben'], 0.15)
    sfx('pop', T['morgen'] + 0.6, 0.15); sfx('shine', T['retten'], 0.12); sfx('tap', T['bespritzen'], 0.12); sfx('shine', T['baecker'] - 0.2, 0.15); sfx('ding', T['essen'], 0.12); sfx('pop', T['sags'] + 0.3, 0.15)
    fd = int(0.5 * SR); mix_[-fd:] *= np.linspace(1, 0, fd); mix_ = mix_ / max(1e-6, np.abs(mix_).max()) * 0.92
    wo = wave.open(f'{TMP}/a.wav', 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((mix_ * 32767).astype('<i2').tobytes()); wo.close()
    # ---------- images envoyées directement à ffmpeg (pas de fichiers : en 4K ils prendraient plusieurs Go)
    enc = subprocess.Popen([FF, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W * K}x{H * K}', '-r', str(FPS), '-i', '-', '-i', f'{TMP}/a.wav',
                            '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-tune', 'animation', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k',
                            '-af', 'pan=stereo|c0=c0|c1=c0', '-shortest', '-movflags', '+faststart', OUT], stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for n, b in enumerate(pool.imap(frame_bytes, range(NF), chunksize=4)):
            enc.stdin.write(b)
            if n % 600 == 0: print('images', n, '/', NF, flush=True)
    enc.stdin.close(); enc.wait(); shutil.rmtree(TMP); print('ok', OUT, round(DUR, 2), f'{W * K}x{H * K}')
