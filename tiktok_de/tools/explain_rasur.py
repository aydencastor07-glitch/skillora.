# Vidéo explicative « Rasieren macht Haare dicker? » – même moteur que le pain : même feuille du début à la fin, sans transition
# glissée : l'ancien dessin s'efface vite et le suivant se dessine trait par trait. Images envoyées directement à ffmpeg.
# usage : explain_rasur.py dossier sortie.mp4  [PREVIEW=t1,t2,...] [K=1 (1080p, défaut) | K=2 (4K)] [TAIL=0.5]
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
DUR = len(VOICE) / SR + float(os.environ.get('TAIL', 0.5)); K = int(os.environ.get('K', 1))      # K : taille de sortie (1 = 1080p, 2 = 4K)
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
# ---------- objets dessinés
DEAD = (168, 156, 142); DERM = (222, 170, 140); BUMP = (214, 84, 72); WATER = (110, 170, 230)
def mix(c1, c2, u): return tuple(int(a + (b - a) * clamp(u)) for a, b in zip(c1, c2))
def drop(d, cx, cy, r, col, stretch=1.0):
    d.ellipse([S(cx - r), S(cy - r), S(cx + r), S(cy + r)], fill=col + (255,))
    d.polygon([(S(cx - r * 0.92), S(cy - r * 0.35)), (S(cx), S(cy - r * (1.0 + 1.3 * stretch))), (S(cx + r * 0.92), S(cy - r * 0.35))], fill=col + (255,))
def share(img, d, cx, cy, p):
    for (x, y) in ((cx - 170, cy), (cx + 150, cy - 140), (cx + 150, cy + 140)): arc(d, x, y, 62, -90, -90 + 360 * ease(p), INK, 9)
    line(d, cx - 115, cy - 25, cx + 95, cy - 115, INK, 8, ease(p - 0.4)); line(d, cx - 115, cy + 25, cx + 95, cy + 115, INK, 8, ease(p - 0.4))
def skin(d, x0, x1, y, depth, p):
    # coupe de peau : surface légèrement ondulée qui se dessine, couche du dessus plus foncée, dessous rosé
    if p <= 0: return
    top = [(x, y + 6 * math.sin(x / 70)) for x in np.linspace(x0, x1, 40)]
    if p >= 0.5:
        a = int(255 * clamp((p - 0.5) / 0.4))
        d.polygon([(S(x), S(yy)) for x, yy in top] + [(S(x1), S(y + depth)), (S(x0), S(y + depth))], fill=SKIN + (a,))
        d.polygon([(S(x), S(yy)) for x, yy in top] + [(S(x), S(yy + 34)) for x, yy in top[::-1]], fill=DERM + (a,))
    poly(d, top, INK, 7, ease(p / 0.5))
def follicle(d, x, yb, h, p, live=0.0, t=0):
    # gaine de la racine (deux traits) + bulbe ; la papille rouge au fond « bat » quand on dit qu'elle vit
    if p <= 0: return
    for sx in (-1, 1): poly(d, [(x + sx * 22, yb - h), (x + sx * 22, yb - 50)], GREY, 5, ease(p))
    if p < 0.5: return
    q = back(clamp((p - 0.5) / 0.5))
    d.ellipse([S(x - 42 * q), S(yb - 85 * q), S(x + 42 * q), S(yb)], outline=GREY + (255,), width=S(5))
    pr = 15 * q * (1 + 0.3 * live * (0.5 + 0.5 * math.sin(t * 9)))
    circ(d, x, yb - 12, pr, None, mix((226, 160, 150), RED, live) + (255,))
def taper(d, x, yb, ytop, wb, col, ya, yz):
    # morceau [ya (haut) → yz (bas)] d'un poil effilé : largeur wb à la base yb, pointe en ytop
    ya, yz = max(ya, ytop), min(yz, yb)
    if yz - ya < 0.5: return
    def w(y): return max(2.5, wb * (y - ytop) / max(1, yb - ytop))
    d.polygon([(S(x - w(ya) / 2), S(ya)), (S(x + w(ya) / 2), S(ya)), (S(x + w(yz) / 2), S(yz)), (S(x - w(yz) / 2), S(yz))], fill=col + (255,))
def hair(d, x, yb, ytop, wb, sky, dead=0.0, cut=None):
    # poil : partie sous la peau (vivante, foncée) + partie dehors (devient grise quand on dit « tot ») ; cut = coupé net à cette hauteur
    top = ytop if cut is None else max(ytop, cut)
    taper(d, x, yb, ytop, wb, INK, max(top, sky), yb); taper(d, x, yb, ytop, wb, mix(INK, DEAD, dead), top, sky)
def piece(d, x, yb, ytop, wb, y0, y1, dx, dy, col=INK):
    # morceau coupé d'un poil (de y0 à y1) déplacé de (dx, dy)
    taper(d, x + dx, yb + dy, ytop + dy, wb, col, y0 + dy, y1 + dy)
LEG = [(440, 500), (440, 1030), (395, 1062), (338, 1082), (326, 1118), (350, 1138), (642, 1138), (648, 1060), (640, 500)]
def leg(img, d, cx, cy, s, p, shaved=None, regrow=1.0, thick=0.0):
    # jambe vue de côté : contour qui se dessine, poils sur les bords et dedans ; shaved = hauteur (repère jambe) jusqu'où le rasoir est passé
    if p <= 0: return
    P = lambda x, y: (cx + (x - 540) * s, cy + (y - 820) * s)
    pts = [P(*q) for q in LEG]
    if p >= 0.6: d.polygon([(S(x), S(y)) for x, y in pts], fill=SKIN + (255,))
    poly(d, pts, INK, 8, ease(p / 0.6))
    if p < 0.6: return
    k = ease((p - 0.6) / 0.4); rs = np.random.RandomState(3)
    for j in range(21):
        y = 530 + j * 24; xi = rs.uniform(470, 610); yi = y + rs.uniform(-8, 8)
        L = (regrow * (1 + 0.5 * thick)) if (shaved is not None and y < shaved) else 1.0
        if L <= 0.03: continue
        w = 4 + 3 * thick * (shaved is not None and y < shaved)
        for x0, y0, dx in ((440, y, -1), (640, y + 10, 1)):
            a = P(x0, y0); line(d, a[0], a[1], a[0] + dx * 20 * s * L * k, a[1] - 13 * s * L * k, INK, w)
        a = P(xi, yi); line(d, a[0], a[1], a[0] + 3 * s * L * k, a[1] - 15 * s * L * k, INK, w)
def legpt(cx, cy, s, x, y): return cx + (x - 540) * s, cy + (y - 820) * s
def razor(d, x, y, s=1.0, ang=0):
    # rasoir manuel : tête blanche avec lame + manche bleu ; ang = -90 (tête verticale, manche à droite) ou 180 (lame en bas, manche en haut)
    a = math.radians(ang); R = lambda u, v: (x + (u * math.cos(a) - v * math.sin(a)) * s, y + (u * math.sin(a) + v * math.cos(a)) * s)
    h0, h1 = R(10, 20), R(60, 240); line(d, h0[0], h0[1], h1[0], h1[1], INK, 30 * s); line(d, h0[0], h0[1], h1[0], h1[1], BLUE, 19 * s)
    hd = [R(-80, -20), R(80, -20), R(80, 20), R(-80, 20)]; d.polygon([(S(u), S(v)) for u, v in hd], fill=WHITE + (255,)); poly(d, hd, INK, 6 * s, closed=True)
    b0, b1 = R(-72, -8), R(72, -8); line(d, b0[0], b0[1], b1[0], b1[1], GREY, 5 * s)
def scissors(d, x, y, s, op):
    # ciseaux, pointes vers la gauche ; op = ouverture 0..1
    for sg in (-1, 1):
        a = math.radians(sg * 16 * op); tx, ty = x - 175 * s * math.cos(a), y - 175 * s * math.sin(a); hx, hy = x + 70 * s * math.cos(a), y + 70 * s * math.sin(a) + sg * 0
        line(d, tx, ty, x, y, INK, 16 * s); line(d, tx, ty, x, y, (200, 205, 212), 9 * s)
        line(d, x, y, hx, hy, INK, 10 * s); circ(d, hx + 34 * s * math.cos(a), hy + 34 * s * math.sin(a) + sg * 12 * s, 34 * s, INK, None, 9 * s)
    circ(d, x, y, 7 * s, None, INK + (255,))
def finger(img, d, cx, cy, s, p):
    if p <= 0: return
    q = back(p) * s
    d.rounded_rectangle([S(cx - 55 * q), S(cy - 100 * q), S(cx + 55 * q), S(cy + 120 * q)], S(55 * q), fill=SKIN + (255,), outline=INK, width=S(6))
    d.rounded_rectangle([S(cx - 36 * q), S(cy - 84 * q), S(cx + 36 * q), S(cy - 2 * q)], S(30 * q), fill=(248, 226, 220, 255), outline=INK, width=S(5))
def furball(img, d, cx, cy, p, t):
    # bonhomme tout poilu (façon Wookiee) : boule de poils qui frémit, yeux qui clignent
    if p <= 0: return
    q = back(p); R = 200 * q; rs = np.random.RandomState(5)
    d.ellipse([S(cx - R), S(cy - R * 1.15), S(cx + R), S(cy + R * 1.15)], fill=(140, 96, 60, 255))
    for j in range(170):
        a = rs.uniform(0, 2 * math.pi); r0 = R * math.sqrt(rs.uniform(0.15, 1.0)); L = rs.uniform(28, 60) * q
        x0, y0 = cx + r0 * math.cos(a), cy + r0 * 1.15 * math.sin(a); w = a + 0.18 * math.sin(t * 7 + j) + rs.uniform(-0.4, 0.4)
        line(d, x0, y0, x0 + L * math.cos(w), y0 + L * 1.1 * math.sin(w), (96, 62, 38) if j % 3 else (176, 126, 82), 5)
    bl = 0.12 if (t % 2.4) < 0.12 else 1
    for sx in (-1, 1):
        ex, ey = cx + sx * 66 * q, cy - 60 * q
        d.ellipse([S(ex - 32 * q), S(ey - 32 * q * bl), S(ex + 32 * q), S(ey + 32 * q * bl)], fill=WHITE + (255,), outline=INK, width=S(5))
        d.ellipse([S(ex - 7 * q), S(ey + 4 * q - 13 * q * bl), S(ex + 19 * q), S(ey + 4 * q + 13 * q * bl)], fill=INK + (255,))
    arc(d, cx, cy + 30 * q, 55 * q, 25, 155, INK, 8)
def eshaver(img, d, cx, cy, p, t, on=False):
    # rasoir électrique : corps gris foncé, tête à 3 grilles rondes, vibre quand il tourne
    if p <= 0: return
    q = back(p); x = cx + (3 * math.sin(t * 90) if on else 0); y = cy + (2 * math.cos(t * 77) if on else 0)
    d.rounded_rectangle([S(x - 85 * q), S(y - 120 * q), S(x + 85 * q), S(y + 230 * q)], S(70 * q), fill=(72, 76, 86, 255), outline=INK, width=S(7))
    d.rounded_rectangle([S(x - 115 * q), S(y - 235 * q), S(x + 115 * q), S(y - 110 * q)], S(40 * q), fill=(192, 198, 206, 255), outline=INK, width=S(7))
    for k in (-1, 0, 1):
        circ(d, x + k * 70 * q, y - 172 * q, 31 * q, INK, (228, 231, 235, 255), 5)
        for r in (12, 22): arc(d, x + k * 70 * q, y - 172 * q, r * q, 0, 359, GREY, 3)
    circ(d, x, y + 60 * q, 22 * q, INK, (BLUE if on else GREY) + (255,), 5)
    if on:
        for k in range(3): arc(d, x + 120 * q, y - 172 * q, 40 + 24 * k + 6 * math.sin(t * 30), -35, 35, GREY, 5)
def bump(d, x, y, r, head=0.0):
    # bouton : bosse rouge sur la peau, tête jaunâtre au sommet
    if r <= 1: return
    d.chord([S(x - r), S(y - r * 0.85), S(x + r), S(y + r * 0.85)], 180, 360, fill=BUMP + (255,), outline=INK, width=S(5))
    if head > 0: circ(d, x, y - r * 0.5, r * 0.3 * head, None, (250, 236, 170, 255))
def glow(img, x, y, r, col, a):
    # halo flou (inflammation) ; image plus grande que le cercle pour que le flou ne soit pas coupé en carré
    if r <= 2 or a <= 0: return
    n = S(3 * r); g = Image.new('RGBA', (n, n), (0, 0, 0, 0)); ImageDraw.Draw(g).ellipse([n / 6, n / 6, n * 5 / 6, n * 5 / 6], fill=col + (int(170 * a),))
    g = g.filter(ImageFilter.GaussianBlur(S(r * 0.25))); comp(img, g, S(x) - n / 2, S(y) - n / 2)
def magnifier(d, cx, cy, r, p):
    if p <= 0: return
    q = back(p); arc(d, cx, cy, r * q, 0, 360, INK, 10); line(d, cx - r * q * 0.72, cy + r * q * 0.72, cx - r * q * 1.25, cy + r * q * 1.25, INK, 22 * q)
def curl(d, cx, cy, s, p, col=INK):
    # poil bouclé (spirale qui monte)
    pts = [(cx + s * (6 + 4 * a) * math.cos(a), cy + s * (6 + 4 * a) * math.sin(a) - s * 5 * a) for a in np.linspace(0, 4 * math.pi, 80)]
    poly(d, pts, col, 8, p)
# ---------- repères temporels
T = dict(schneller=tw('schneller'), rasierst=tw('rasierst'), hab=tw('hab'), quatsch=tw('quatsch'), jedes=tw('jedes'), wurzel=tw('wurzel'), haut=tw('haut'),
         lebt=tw('lebt'), von=tw('von'), null3=tw('03'), oben=tw('oben'), alles=tw('alles'), tot=tw('tot'), finger=tw('fingernagel'), schneiden=tw('haareschneiden'),
         weh=tw('weh'), beim=tw('beim'), rasieren=tw('rasieren'), toten=tw('toten'), merkt=tw('merkt'), waechst2=tw('wächst', 1), das=tw('das'), j1970=tw('1970'),
         bein=tw('bein'), woche=tw('woche'), rasiert=tw('rasiert'), andere=tw('andere'), ergebnis=tw('ergebnis'), beide=tw('beide'), gleich=tw('gleich'), kein=tw('kein'),
         sonst=tw('sonst'), irgendwann=tw('irgendwann'), wookiee=tw('wookiee'), aber2=tw('aber', 1), fuehlen=tw('fühlen'), ein3=tw('ein', 2), spitze=tw('spitze'),
         wurzel3=tw('wurzel', 2), dicker4=tw('dicker', 3), rasierst2=tw('rasierst', 1), dicke=tw('dicke'), stumpfe=tw('stumpfe'), nervigen=tw('nervigen'), oft=tw('oft'),
         zurueck=tw('zurück'), lockigen=tw('lockigen'), fremd=tw('fremdkörper'), wehrt=tw('wehrt'), pickel=tw('pickel'), so=tw('so'), nie=tw('nie'), wasser=tw('wasser'),
         wuchs=tw('wuchsrichtung'), drueck=tw('drück'), spuel=tw('spül'), wechsel=tw('wechsel'), oder=tw('oder'), elektr=tw('elektrischen'), stoppeln2=tw('stoppeln', 1),
         laenger=tw('länger'), pickel2=tw('pickel', 1), erst2=tw('erst', 1), sags=tw("sag's"))
for k, v in T.items():
    if v is None: print('mot introuvable :', k)
SC = [0, T['jedes'] - 0.12, T['das'] - 0.12, T['aber2'] - 0.12, T['nervigen'] - 0.42, T['so'] - 0.12, T['oder'] - 0.12, T['sags'] - 0.12, DUR]
SOURCES = [(T['null3'] - 0.2, T['alles'] - 0.2, 'gemessen am Bein · Lynfield & MacWilliams 1970'), (T['alles'], T['beim'] - 0.2, 'Quelle: IQWiG'),
           (T['j1970'] - 0.1, T['sonst'] - 0.2, 'Lynfield & MacWilliams, J Invest Dermatol 1970'), (T['oft'] - 0.2, T['so'] - 0.2, 'Quelle: DermNet'),
           (T['nie'] - 0.2, T['oder'] - 0.2, 'Quelle: American Academy of Dermatology'), (T['elektr'] - 0.2, T['sags'] - 0.2, 'Quelle: DermNet')]
# ---------- caméra : très léger zoom continu + petits zooms d'impact (pas de transition glissée)
PUNCH = [(T['quatsch'], 0.06), (T['null3'], 0.05), (T['tot'], 0.04), (T['j1970'], 0.05), (T['wookiee'], 0.05), (T['rasierst2'], 0.04), (T['pickel'], 0.06), (T['elektr'], 0.04)]
SHAKE = [(T['quatsch'], 12), (T['pickel'], 10)]
# coupe de peau des scènes 1 : 5 poils
FX = [200, 370, 540, 710, 880]; SKY = 830; FB = 1160; FTOP = [SKY - 205, SKY - 235, SKY - 185, SKY - 225, SKY - 195]
SCI0 = T['schneiden'] - 0.25 if T['schneiden'] else 99; RZ0 = T['rasieren'] - 0.15 if T['rasieren'] else 99
def sci_x(t): return 1170 - 300 * eio((t - SCI0) / 0.9)                 # pivot des ciseaux
def rz_x(t): return -120 + 1300 * eio((t - RZ0) / 1.3)                   # rasoir qui glisse sur la peau
def cut_time(fx, scis):                                                 # moment où l'outil passe sur le poil
    t0 = SCI0 if scis else RZ0
    for k in range(400):
        tt = t0 + k * 0.005
        if (sci_x(tt) - 175 <= fx) if scis else (rz_x(tt) >= fx): return tt
    return 99
SCUT = {j: cut_time(FX[j], True) for j in (3, 4)}; RCUT = {j: cut_time(FX[j], False) for j in range(5)}
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
HOT = re.compile(r'(\d|quatsch|wurzel|lebt|tot|millimeter|dick|schneller|wookiee|stoppeln|spitze|dünn|stumpf|pickel|fremdkörper|lockig|trocken|wasser|schaum|wuchsrichtung|klinge|elektrisch|fingernagel)', re.I)
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
def sc_(t, k, dt=-0.15, d=0.35): return since(t, T[k] + dt, d) if T[k] else 0
def scene(img, d, sc, t):
    CX = W / 2; u0 = t - SC[sc]
    if sc == 0:   # jambe : le rasoir descend, les poils repoussent « plus vite, plus épais » ; croix rouge sur « Quatsch »
        text(img, (CX, 450), 'wächst schneller & dicker nach?', H2(62), INK, clamp(u0 / 0.3))
        yr = 520 + 600 * eio((t - 0.3) / 2.3); rg = sc_(t, 'hab', -0.3, 1.0)
        leg(img, d, CX, 860, 1.0, u0 / 0.5, shaved=yr if t > 0.3 else None, regrow=rg, thick=rg)
        if 0.3 < t < 2.9: xr, yy = legpt(CX, 860, 1.0, 662, yr); razor(d, xr, yy, 0.95, -90)
        if T['hab'] and t > T['hab'] - 0.3:
            k = sc_(t, 'hab', -0.1, 0.4); arrow(d, 820, 900, 820, 700, RED, 9, k); text(img, (820, 960), 'dicker?', H2(56), RED, k)
        if T['quatsch'] and t > T['quatsch'] - 0.05:
            cross(d, CX, 860, 260, sc_(t, 'quatsch', -0.05, 0.35), RED, 18)
            k = since(t, T['quatsch'], 0.2); text(img, (CX, 1230), 'Quatsch!', BF(110), RED, k, rot=-6, scale=1.5 - 0.5 * k)
    elif sc == 1:  # coupe de peau : racines, poils qui poussent (0,3 mm/jour), partie dehors morte, ciseaux, puis rasoir au ras de la peau
        skin(d, 50, 1030, SKY, 470, u0 / 0.6)
        live = sc_(t, 'lebt', -0.1, 0.4); dead = sc_(t, 'tot', -0.3, 0.6); g = eio((t - T['von'] + 0.2) / (T['oben'] + 0.5 - T['von'])) if T['von'] else 0
        for j, x in enumerate(FX):
            follicle(d, x, FB, 330, (u0 - 0.3 - 0.1 * j) / 0.5, live, t + j)
            if u0 < 0.6 + 0.1 * j: continue
            ytop = (SKY + 140) + (FTOP[j] - SKY - 140) * g; yb = FB - 45; cuts = []
            if j in SCUT and t >= SCUT[j]: cuts.append((SCUT[j], SKY - 110))
            if t >= RCUT[j]: cuts.append((RCUT[j], SKY - 3))
            cut = max([c for _, c in cuts], default=None)
            hair(d, x, yb, ytop, 26, SKY, dead, cut)
            prev = None
            for tc, cy in sorted(cuts):                                   # morceaux coupés : tombent (ciseaux) ou s'envolent (rasoir)
                q = (t - tc) / 0.6
                if q < 1:
                    if cy < SKY - 50: piece(d, x, yb, ytop, 26, ytop, cy, -60 * q, 260 * q * q, mix(INK, DEAD, dead))
                    else: piece(d, x, yb, ytop, 26, prev if prev else ytop, cy, 420 * q, -180 * q, mix(INK, DEAD, dead))
                prev = cy
        if T['wurzel'] and t > T['wurzel'] - 0.2:
            k = sc_(t, 'wurzel', -0.2, 0.35) * gone(t, T['merkt'] - 0.1); text(img, (210, 1250), 'Haarwurzel', H2(54), INK, k); arrow(d, 290, 1215, 350, 1150, INK, 6, k)
        if T['haut'] and t > T['haut'] - 0.2: text(img, (1000, SKY + 90), 'Haut', H2(54), GREY, sc_(t, 'haut', -0.2), anchor='rm')
        if T['lebt'] and t > T['lebt'] - 0.1: text(img, (760, 1250), 'lebt', BF(60), RED, live * gone(t, T['merkt'] - 0.1))
        if T['null3'] and t > T['null3'] - 0.2:
            def growth(lay, dl):
                k = sc_(t, 'null3', -0.2, 0.3); text(lay, (CX, 480), '0,3 mm', BF(100), RED, k, scale=1.4 - 0.4 * ease(k)); text(lay, (CX, 570), 'pro Tag', H2(56), INK, k)
                arrow(dl, 1000, 900, 1000, 700 - 40 * math.sin(t * 3), RED, 9, k)
            sub(img, gone(t, T['alles'] - 0.05), growth)
        if T['tot'] and t > T['tot'] - 0.3:
            def deadpart(lay, dl):
                text(lay, (440, 470), 'tot', BF(100), (130, 120, 110), dead, scale=1.3 - 0.3 * dead)
                if T['finger'] and t > T['finger'] - 0.2:
                    k = sc_(t, 'finger', -0.2, 0.35); text(lay, (620, 470), '=', BF(80), INK, k); finger(lay, dl, 780, 470, 0.7, k)
            sub(img, gone(t, T['schneiden'] - 0.3), deadpart)
        if SCI0 < t < T['rasieren'] - 0.05:
            scissors(d, sci_x(t), SKY - 110, 1.0, abs(math.sin((t - SCI0) * 9)))
        if T['weh'] and t > T['weh'] - 0.2:
            def noharm(lay, dl): k = sc_(t, 'weh', -0.2, 0.3); text(lay, (CX - 40, 480), 'tut nicht weh', BF(66), GREEN, k); check(dl, CX + 290, 470, 40, since(t, T['weh'], 0.4))
            sub(img, gone(t, T['toten'] - 0.1), noharm)
        if RZ0 < t < RZ0 + 1.4: razor(d, rz_x(t), SKY - 24, 1.0, 180)
        if T['toten'] and t > T['toten'] - 0.1:
            def deadcut(lay, dl): text(lay, (CX, 520), 'nur der tote Teil', BF(66), (130, 120, 110), sc_(t, 'toten', -0.1, 0.3))
            sub(img, gone(t, T['waechst2'] - 0.1), deadcut)
        if T['merkt'] and t > T['merkt'] - 0.1: text(img, (CX, 1250), 'Wurzel merkt nichts', H2(58), INK, sc_(t, 'merkt', -0.1, 0.3))
        if T['waechst2'] and t > T['waechst2'] - 0.1:
            k = sc_(t, 'waechst2', -0.1, 0.3); text(img, (CX, 520), 'nicht schneller', BF(78), RED, k, scale=1.3 - 0.3 * k)
    elif sc == 2:  # l'étude de 1970 : une jambe rasée chaque semaine, l'autre jamais → même vitesse ; sinon : Wookiee
        def study(lay, dl):
            k = since(t, T['j1970'] - 0.15, 0.3); text(lay, (CX, 490), '1970', BF(130), RED, k, scale=1.5 - 0.5 * k); text(lay, (CX, 585), 'Studie', H2(60), INK, k)
            if t < T['ergebnis'] - 0.05:
                pl = since(t, T['j1970'] + 0.4, 0.6); yr = 520 + 600 * eio((t - T['rasiert'] + 0.25) / 0.8)
                leg(lay, dl, 320, 1000, 0.62, pl, shaved=yr if t > T['rasiert'] - 0.25 else None, regrow=0)
                if T['rasiert'] - 0.25 < t < T['rasiert'] + 0.6: xr, yy = legpt(320, 1000, 0.62, 662, yr); razor(dl, xr, yy, 0.6, -90)
                if T['woche'] and t > T['woche'] - 0.2: text(lay, (320, 735), 'jede Woche rasiert', H2(44), BLUE, sc_(t, 'woche', -0.2))
                leg(lay, dl, 760, 1000, 0.62, since(t, T['j1970'] + 0.7, 0.6))
                if T['andere'] and t > T['andere'] - 0.1: text(lay, (760, 735), 'nie rasiert', H2(44), GREEN, sc_(t, 'andere', -0.1))
            else:
                h = 300 * eio((t - T['beide'] + 0.1) / 0.9) if T['beide'] else 0; kb = sc_(t, 'ergebnis', -0.05, 0.3)
                text(lay, (CX, 690), 'Wachstum', H2(54), GREY, kb)
                for x, col, lab in ((370, BLUE, 'rasiert'), (710, GREEN, 'nie rasiert')):
                    line(dl, x - 110, 1180, x + 110, 1180, INK, 7, kb); text(lay, (x, 1228), lab, H2(48), col, kb)
                    if h > 8: dl.rounded_rectangle([S(x - 70), S(1180 - h), S(x + 70), S(1176)], S(14), fill=col + (255,), outline=INK, width=S(6))
                if T['gleich'] and t > T['gleich'] - 0.1:
                    q = sc_(t, 'gleich', -0.1, 0.25); text(lay, (CX, 1020), '=', BF(120), INK, q, scale=1.4 - 0.4 * q)
                    if t < T['kein'] - 0.1: text(lay, (CX, 770), 'gleich schnell', BF(56), INK, q)
                if T['kein'] and t > T['kein'] - 0.1: text(lay, (CX - 30, 770), 'kein Haar dicker', BF(56), GREEN, sc_(t, 'kein', -0.1, 0.3)); check(dl, CX + 290, 760, 34, since(t, T['kein'] + 0.1, 0.4))
        sub(img, gone(t, T['sonst'] - 0.05), study)
        if T['sonst'] and t > T['sonst'] - 0.05:
            text(img, (CX, 500), 'sonst …', H2(80), INK, sc_(t, 'sonst', -0.05, 0.3)); furball(img, d, CX, 880, sc_(t, 'irgendwann', -0.3, 0.5), t)
    elif sc == 3:  # un poil : fin en haut, épais en bas ; rasé, il ne reste que le bout épais et plat
        text(img, (CX, 470), 'fühlt sich dicker an?', H2(70), INK, sc_(t, 'fuehlen', -0.2, 0.3) if T['fuehlen'] else clamp(u0 / 0.3))
        sky = 1080; skin(d, 50, 1030, sky, 230, u0 / 0.5)
        yb, top0, wb = 1250, 600, 84; g = eio((t - T['ein3'] + 0.2) / 0.8) if T['ein3'] else 0; ytop = yb - (yb - top0) * g
        tc = T['rasierst2'] - 0.15 + 0.7 * 0.5 if T['rasierst2'] else 99
        hair(d, CX, yb, ytop, wb, sky, 0, sky - 4 if t >= tc else None)
        if t >= tc and t < tc + 0.7: q = (t - tc) / 0.7; piece(d, CX, yb, ytop, wb, ytop, sky - 4, 480 * q, -260 * q)
        if T['rasierst2'] and T['rasierst2'] - 0.15 < t < T['rasierst2'] + 0.6:
            q = (t - T['rasierst2'] + 0.15) / 0.7; razor(d, CX - 560 + 1120 * eio(q), sky - 24, 1.0, 180)
        def labels(lay, dl):
            if T['spitze'] and t > T['spitze'] - 0.2: k = sc_(t, 'spitze', -0.2); text(lay, (790, 640), 'dünn', H2(64), BLUE, k); arrow(dl, 720, 650, 565, 650, BLUE, 6, k)
            if T['wurzel3'] and t > T['wurzel3'] - 0.2: k = sc_(t, 'wurzel3', -0.2); text(lay, (810, 1010), 'dick', H2(64), RED, k); arrow(dl, 740, 1010, 600, 1010, RED, 6, k)
            if T['dicker4'] and t > T['dicker4'] - 0.2:
                k = sc_(t, 'dicker4', -0.2, 0.6); poly(dl, [(330, 640), (300, 840), (280, 1040)], GREY, 6, k); text(lay, (250, 840), 'immer dicker', H2(46), GREY, k, rot=80)
        sub(img, gone(t, T['rasierst2'] - 0.1), labels)
        if T['dicke'] and t > T['dicke'] - 0.25:
            k = sc_(t, 'dicke', -0.25, 0.4); magnifier(d, 780, 780, 150, k); line(d, 600, 1060, 700, 880, GREY, 4, k)
            if k > 0.5:
                w2 = 84 * (sky - top0) / (yb - top0) * 2.2; d.rectangle([S(780 - w2 / 2), S(800), S(780 + w2 / 2), S(915)], fill=INK + (255,))
                d.rectangle([S(660), S(915), S(900), S(925)], fill=DERM + (255,))
            if T['stumpfe'] and t > T['stumpfe'] - 0.1: text(img, (780, 1000), 'stumpf', BF(64), RED, sc_(t, 'stumpfe', -0.1, 0.3))
    elif sc == 4:  # poil incarné : il ressort, se recourbe et rentre dans la peau → la peau réagit → bouton
        k0 = clamp(u0 / 0.3); text(img, (CX, 470), 'Rasierpickel?', BF(84), RED, k0, scale=1.3 - 0.3 * k0)
        sky = 900; skin(d, 50, 1030, sky, 390, u0 / 0.5); follicle(d, 400, 1230, 330, (u0 - 0.3) / 0.5)
        g = eio((t - T['oft'] + 0.2) / (T['zurueck'] + 0.6 - T['oft'])) if T['oft'] else 0
        path = [(400, 1185), (400, 870)] + [(480 + 80 * math.cos(a), 870 - 80 * math.sin(a)) for a in np.linspace(math.pi, 0, 24)] + [(566, 920), (580, 990)]
        poly(d, path, INK, 14, 0.18 + 0.82 * g if u0 > 0.6 else 0)
        if T['lockigen'] and t > T['lockigen'] - 0.2:
            def curly(lay, dl): curl(dl, 850, 690, 1.3, sc_(t, 'lockigen', -0.2, 0.6)); text(lay, (850, 790), 'lockig', H2(56), INK, sc_(t, 'lockigen', -0.2))
            sub(img, gone(t, T['fremd'] - 0.1), curly)
        if T['fremd'] and t > T['fremd'] - 0.2:
            k = sc_(t, 'fremd', -0.2, 0.5); glow(img, 580, 975, 120 * k, BUMP, k * (0.75 + 0.25 * math.sin(t * 8)))
            text(img, (CX, 1245), 'Fremdkörper!', BF(62), RED, k)
        if T['wehrt'] and t > T['wehrt'] - 0.1: bump(d, 575, sky + 6, 80 * back(sc_(t, 'wehrt', -0.1, 0.6)), sc_(t, 'pickel', -0.05, 0.3))
        if T['pickel'] and t > T['pickel'] - 0.05: k = since(t, T['pickel'] - 0.05, 0.2); text(img, (820, 760), 'Pickel', BF(80), RED, k, rot=-6, scale=1.5 - 0.5 * k)
    elif sc == 5:  # la liste des conseils, qui se remplit au fil de la voix ; ligne active surlignée
        text(img, (CX, 450), 'so verhinderst du sie', H2(70), INK, clamp(u0 / 0.3))
        rows = [('nie', 'nie trocken rasieren', RED), ('wasser', 'erst Wasser, dann Schaum', INK), ('wuchs', 'in Wuchsrichtung', INK),
                ('drueck', 'nicht fest drücken', INK), ('spuel', 'Klinge abspülen', INK), ('wechsel', 'neue Klinge: alle 5–7 Mal', INK)]
        act = max([i for i, (c, _, _) in enumerate(rows) if T[c] and t > T[c] - 0.15], default=None)
        if act is not None:
            y = 570 + act * 122; d.rounded_rectangle([S(95), S(y - 50), S(1000), S(y + 50)], S(24), fill=YEL + (110,))
        for i, (c, lab, col) in enumerate(rows):
            if not T[c] or t < T[c] - 0.15: continue
            k = since(t, T[c] - 0.15, 0.3); y = 570 + i * 122; x = 160 - 50 * (1 - ease(k)); r = 44 * back(k)
            circ(d, x, y, r, INK, WHITE + (255,), 6)
            if i == 0: cross(d, x, y, 20, since(t, T[c], 0.3), RED, 9)
            elif i in (1, 4): drop(d, x, y + 10, 16 * back(k), WATER)
            elif i == 2: arrow(d, x, y - 26, x, y + 24, INK, 6, k, 16)
            elif i == 3: arrow(d, x, y - 24, x, y + 22, INK, 8, k, 18); line(d, x - 24, y + 24, x + 24, y - 24, RED, 6, k)
            else: text(img, (x, y), '5–7', BF(26), INK, k)
            text(img, (x + 70, y), lab, BF(44), col, k, anchor='lm')
    elif sc == 6:  # rasoir électrique : laisse un tout petit bout de poil → pas de poil incarné
        text(img, (CX, 450), 'Elektrorasierer', H2(70), INK, clamp(u0 / 0.3))
        eshaver(img, d, 270, 900, sc_(t, 'elektr', -0.3, 0.45), t, on=t > T['elektr'] + 0.2)
        sky = 1020; skin(d, 500, 1040, sky, 200, sc_(t, 'elektr', 0.0, 0.5))
        ln = 34 * eio((t - T['stoppeln2'] + 0.2) / 0.6) if T['stoppeln2'] else 0
        for j, x in enumerate(range(570, 1000, 85)):
            if t > T['elektr'] + 0.3: hair(d, x, sky + 150, sky - 160, 22, sky, 0, sky - ln)
        if T['laenger'] and t > T['laenger'] - 0.2:
            k = sc_(t, 'laenger', -0.2, 0.3); line(d, 1010, sky - ln, 1030, sky - ln, RED, 5, k); text(img, (770, sky - 90), 'minimal länger', H2(54), RED, k)
        if T['pickel2'] and t > T['pickel2'] - 0.2:
            k = sc_(t, 'pickel2', -0.2, 0.4); bump(d, 560, 700, 55 * back(k), 1); cross(d, 560, 680, 70, sc_(t, 'pickel2', 0.1, 0.35), RED, 12)
            if T['erst2'] and t > T['erst2'] - 0.3: q = sc_(t, 'erst2', -0.3, 0.3); text(img, (830, 690), 'keine Pickel', BF(52), GREEN, q, scale=1.3 - 0.3 * q)
    elif sc == 7:  # partage
        share(img, d, CX, 760, u0 / 0.7); text(img, (CX, 1120), "sag's weiter", H2(96), RED, clamp((u0 - 0.3) / 0.4)); underline(d, CX - 230, CX + 230, 1180, RED, ease((u0 - 0.6) / 0.5), 10)
def draw(t):
    sc = max(i for i in range(len(SC) - 1) if t >= SC[i])
    lay = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    scene(lay, d, sc, t)
    for s0, s1, src in SOURCES:
        if s0 <= t < s1: text(lay, (W / 2, 1468), src, H2(36), GREY, min(since(t, s0, 0.3), 1 - since(t, s1 - 0.3, 0.3)))
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
    sfx('whoosh', 0.3, 0.12); sfx('pop', T['hab'], 0.12); sfx('hit', T['quatsch'] - 0.03, 0.4); sfx('swish', T['quatsch'] - 0.05, 0.2)
    sfx('pop', T['wurzel'] - 0.1, 0.1); sfx('ding', T['lebt'], 0.1); sfx('pop', T['null3'] - 0.1, 0.15); sfx('pop', T['tot'] - 0.1, 0.12); sfx('pop', T['finger'], 0.1)
    for j in SCUT: sfx('snap', SCUT[j], 0.15)
    sfx('swish', RZ0 + 0.2, 0.18); sfx('cut1', RZ0 + 0.5, 0.12); sfx('pop', T['waechst2'], 0.12); sfx('hit', T['j1970'] - 0.1, 0.25); sfx('swish', T['rasiert'] - 0.2, 0.15)
    sfx('pop', T['andere'], 0.1); sfx('ding', T['gleich'], 0.12); sfx('ding', T['kein'] + 0.1, 0.12); sfx('pop', T['irgendwann'] - 0.2, 0.15); sfx('shine', T['wookiee'] - 0.1, 0.12)
    sfx('pop', T['spitze'], 0.1); sfx('pop', T['wurzel3'], 0.1); sfx('swish', T['rasierst2'] - 0.1, 0.18); sfx('cut1', T['rasierst2'] + 0.2, 0.12); sfx('pop', T['stumpfe'], 0.12)
    sfx('pop', T['lockigen'], 0.1); sfx('buzz', T['fremd'], 0.08); sfx('hit', T['pickel'] - 0.05, 0.25)
    for c in ('nie', 'wasser', 'wuchs', 'drueck', 'spuel', 'wechsel'): sfx('tap', T[c] - 0.15, 0.14)
    sfx('pop', T['elektr'] - 0.3, 0.12); sfx('buzz', T['elektr'] + 0.2, 0.06); sfx('pop', T['pickel2'], 0.12); sfx('ding', T['erst2'] - 0.2, 0.12); sfx('pop', T['sags'] + 0.3, 0.15)
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
