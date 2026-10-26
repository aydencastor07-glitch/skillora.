# Vidéo explicative « Warum hält dein Handy-Akku nicht 100 Tage? » – style « Warum ist das nicht anders? » : la vraie raison (physique),
# puis « stell dir vor, es ginge doch » (effet domino). Même moteur que la voiture / les pneus : même feuille, dessin trait par trait.
# usage : explain_akku.py dossier sortie.mp4  [PREVIEW=t1,t2,...] [K=1 (1080p, défaut) | K=2 (4K)] [TAIL=0.5]
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
RUB = (38, 38, 42); ICE = (180, 215, 240); ROAD = (90, 88, 86); SUN = (250, 190, 40); MOON = (240, 228, 170)
def mix(c1, c2, u): return tuple(int(a + (b - a) * clamp(u)) for a, b in zip(c1, c2))
def share(img, d, cx, cy, p):
    for (x, y) in ((cx - 170, cy), (cx + 150, cy - 140), (cx + 150, cy + 140)): arc(d, x, y, 62, -90, -90 + 360 * ease(p), INK, 9)
    line(d, cx - 115, cy - 25, cx + 95, cy - 115, INK, 8, ease(p - 0.4)); line(d, cx - 115, cy + 25, cx + 95, cy + 115, INK, 8, ease(p - 0.4))
def calendar(img, d, cx, cy, label, p, col=RED, s=1.0):
    if p <= 0: return
    q = back(p) * s; w, h = 190 * q, 170 * q
    d.rounded_rectangle([S(cx - w / 2), S(cy - h / 2), S(cx + w / 2), S(cy + h / 2)], S(14), fill=WHITE + (255,), outline=INK, width=S(6))
    if q > 0.15: d.rectangle([S(cx - w / 2 + 3), S(cy - h / 2 + 3), S(cx + w / 2 - 3), S(cy - h / 2 + 46 * q)], fill=col + (255,))   # trop petit : pas de bandeau (sinon hauteur négative)
    text(img, (cx, cy + 22 * q), label, H2(46 * q), INK)
def clock(d, cx, cy, r, t, speed, p):
    if p <= 0: return
    arc(d, cx, cy, r, -90, -90 + 360 * ease(p), INK, 8)
    if p < 0.8: return
    for k in range(12): a = k * math.pi / 6; line(d, cx + (r - 22) * math.cos(a), cy + (r - 22) * math.sin(a), cx + (r - 8) * math.cos(a), cy + (r - 8) * math.sin(a), INK, 4)
    a1 = t * speed - math.pi / 2; a2 = t * speed / 12 - math.pi / 2
    line(d, cx, cy, cx + r * 0.75 * math.cos(a1), cy + r * 0.75 * math.sin(a1), INK, 6); line(d, cx, cy, cx + r * 0.5 * math.cos(a2), cy + r * 0.5 * math.sin(a2), INK, 9)
def tire(d, cx, cy, R, p, rot=0.0, hard=0.0, flake=0.0):
    # pneu vu de côté : contour qui se dessine, gomme, crans, flanc, jante à 5 branches ; hard = gomme durcie (grise, fissurée)
    if p <= 0: return
    arc(d, cx, cy, R, -90, -90 + 360 * ease(p / 0.5), INK, 8)
    if p < 0.5: return
    rub = mix(RUB, (128, 124, 118), hard); circ(d, cx, cy, R, INK, rub + (255,), 7)
    for j in range(30):
        a = rot + j * 2 * math.pi / 30; line(d, cx + (R - 6) * math.cos(a), cy + (R - 6) * math.sin(a), cx + (R - 26) * math.cos(a), cy + (R - 26) * math.sin(a), mix((78, 78, 84), (160, 156, 150), hard), 7)
    arc(d, cx, cy, R * 0.66, 0, 360, mix((70, 70, 76), (150, 146, 140), hard), 4)
    circ(d, cx, cy, R * 0.5, INK, (196, 198, 204, 255), 6)
    for j in range(5):
        a = rot + j * 2 * math.pi / 5; line(d, cx + R * 0.12 * math.cos(a), cy + R * 0.12 * math.sin(a), cx + R * 0.46 * math.cos(a), cy + R * 0.46 * math.sin(a), (150, 152, 160), R * 0.08)
    circ(d, cx, cy, R * 0.13, INK, (160, 162, 170, 255), 5)
    if hard > 0.05:   # fissures dans la gomme
        for j in range(7):
            a = 0.4 + j * 0.9; r0 = R * 0.7; pts = [(cx + (r0 + k * R * 0.045) * math.cos(a + 0.05 * (k % 2)), cy + (r0 + k * R * 0.045) * math.sin(a + 0.05 * (k % 2))) for k in range(6)]
            poly(d, pts, (60, 56, 52), 4, hard)
    if flake > 0: snowflake(d, cx + R * 0.82 * math.cos(-0.7), cy + R * 0.82 * math.sin(-0.7), R * 0.16 * back(flake), WHITE, 5)
def flag(d, cx, cy, w, h, p, t):
    # drapeau allemand qui flotte (bandes noir / rouge / or découpées en tranches ondulées) + hampe
    if p <= 0: return
    q = back(p); w, h = w * q, h * q; x0 = cx - w / 2; y0 = cy - h / 2; n = 24
    line(d, x0 - 6, y0 - 20 * q, x0 - 6, y0 + h + 45 * q, INK, 8)
    for k in range(n):
        xa, xb = x0 + k * w / n, x0 + (k + 1) * w / n + 1
        da = 9 * q * math.sin(t * 5 - k * 0.45) * k / n; db = 9 * q * math.sin(t * 5 - (k + 1) * 0.45) * (k + 1) / n
        for j, col in enumerate(((20, 20, 20), (221, 0, 0), (255, 206, 0))):
            ya, yb = y0 + j * h / 3, y0 + (j + 1) * h / 3
            d.polygon([(S(xa), S(ya + da)), (S(xb), S(ya + db)), (S(xb), S(yb + db)), (S(xa), S(yb + da))], fill=col + (255,))
def snowflake(d, cx, cy, r, col, w=6, p=1.0):
    if r <= 1 or p <= 0: return
    for k in range(6):
        a = k * math.pi / 3 - math.pi / 2; tx, ty = cx + r * math.cos(a), cy + r * math.sin(a); line(d, cx, cy, tx, ty, col, w, p)
        if p > 0.6:
            bx, by = cx + r * 0.6 * math.cos(a), cy + r * 0.6 * math.sin(a)
            for s_ in (-1, 1): line(d, bx, by, bx + r * 0.28 * math.cos(a + s_ * 0.8), by + r * 0.28 * math.sin(a + s_ * 0.8), col, max(2, w - 2))
def sun(d, cx, cy, r, t, p):
    if p <= 0: return
    q = back(p); circ(d, cx, cy, r * q, INK, SUN + (255,), 6)
    for k in range(10):
        a = k * math.pi / 5 + t * 0.6; line(d, cx + r * 1.3 * q * math.cos(a), cy + r * 1.3 * q * math.sin(a), cx + r * 1.7 * q * math.cos(a), cy + r * 1.7 * q * math.sin(a), SUN, 8)
def moon(d, cx, cy, r, p):
    if p <= 0: return
    q = back(p); circ(d, cx, cy, r * q, None, MOON + (255,)); circ(d, cx + r * 0.45 * q, cy - r * 0.25 * q, r * 0.85 * q, None, BG + (255,))
def road(d, x0, x1, y, p, ice=0.0, t=0):
    if p <= 0: return
    xe = x0 + (x1 - x0) * ease(p); d.rectangle([S(x0), S(y), S(xe), S(y + 70)], fill=mix(ROAD, ICE, ice) + (255,))
    for k in range(int((xe - x0) / 120)): line(d, x0 + 30 + k * 120, y + 35, x0 + 90 + k * 120, y + 35, mix(WHITE, (255, 255, 255), 0), 6)
    if ice > 0.3:
        for k in range(10):
            x = x0 + 40 + k * (x1 - x0 - 80) / 9; s = 9 * (0.5 + 0.5 * math.sin(t * 6 + k)) * ice
            line(d, x - s, y + 15, x + s, y + 15, WHITE, 3); line(d, x, y + 15 - s, x, y + 15 + s, WHITE, 3)
def car(d, cx, cy, s, p, rot=0.0, col=BLUE):
    if p <= 0: return
    a = math.radians(rot)
    def P(x, y): return (cx + (x * math.cos(a) - y * math.sin(a)) * s, cy + (x * math.sin(a) + y * math.cos(a)) * s)
    body = [P(-200, 20), P(-200, -40), P(-120, -50), P(-70, -110), P(90, -110), P(150, -50), P(200, -40), P(200, 20)]
    if p >= 0.5: d.polygon([(S(x), S(y)) for x, y in body], fill=col + (255,))
    poly(d, body, INK, 7, ease(p / 0.5), closed=True)
    if p < 0.5: return
    win = [P(-55, -98), P(5, -98), P(5, -52), P(-100, -52)]; win2 = [P(20, -98), P(80, -98), P(125, -52), P(20, -52)]
    for wn in (win, win2): d.polygon([(S(x), S(y)) for x, y in wn], fill=(210, 230, 245, 255))
    for wx in (-120, 120): x, y = P(wx, 22); circ(d, x, y, 42 * s, INK, RUB + (255,), 6); circ(d, x, y, 18 * s, None, (190, 192, 198, 255))
def ticket(img, d, cx, cy, p, amount, sub_):
    if p <= 0: return
    q = back(p); w, h = 440 * q, 330 * q
    d.rounded_rectangle([S(cx - w / 2), S(cy - h / 2), S(cx + w / 2), S(cy + h / 2)], S(18), fill=WHITE + (255,), outline=INK, width=S(6))
    if q > 0.1: d.rectangle([S(cx - w / 2 + 3), S(cy - h / 2 + 3), S(cx + w / 2 - 3), S(cy - h / 2 + 64 * q)], fill=RED + (255,))
    text(img, (cx, cy - h / 2 + 34 * q), 'BUSSGELD', BF(36 * q), WHITE); text(img, (cx, cy + 10 * q), amount, BF(104 * q), RED); text(img, (cx, cy + 112 * q), sub_, H2(44 * q), INK)
def shield(img, d, cx, cy, s, p):
    if p <= 0: return
    q = back(p) * s; pts = [(cx - 150 * q, cy - 170 * q), (cx + 150 * q, cy - 170 * q), (cx + 150 * q, cy + 10 * q), (cx, cy + 190 * q), (cx - 150 * q, cy + 10 * q)]
    d.polygon([(S(x), S(y)) for x, y in pts], fill=(214, 230, 248, 255)); poly(d, pts, INK, 7, 1, closed=True)
    check(d, cx, cy - 20 * q, 60 * q, 1, BLUE, 12)
def alpine(d, cx, cy, s, pm, pf):
    # symbole « Alpine » (3PMSF) : montagne à trois sommets + flocon dedans
    pts = [(cx + x * s, cy + y * s) for x, y in ((-1, 0.75), (-0.62, -0.15), (-0.38, 0.12), (0, -0.85), (0.38, 0.12), (0.62, -0.15), (1, 0.75))]
    if pm >= 1: d.polygon([(S(x), S(y)) for x, y in pts], fill=(236, 240, 246, 255))
    poly(d, pts, INK, 11, ease(pm), closed=pm >= 1)
    snowflake(d, cx, cy + 0.33 * s, 0.27 * s * back(pf), BLUE, 7, 1 if pf > 0 else 0)
def magnifier(d, cx, cy, r, p):
    if p <= 0: return
    q = back(p); arc(d, cx, cy, r * q, 0, 360, INK, 10); line(d, cx + r * q * 0.72, cy + r * q * 0.72, cx + r * q * 1.25, cy + r * q * 1.25, INK, 22 * q)
def eye(d, cx, cy, s, p, t):
    if p <= 0: return
    q = back(p) * s; bl = 0.15 if (t % 2.2) < 0.12 else 1
    d.ellipse([S(cx - 90 * q), S(cy - 50 * q * bl), S(cx + 90 * q), S(cy + 50 * q * bl)], fill=WHITE + (255,), outline=INK, width=S(6))
    if bl > 0.5: circ(d, cx + 10 * q, cy, 30 * q, None, INK + (255,)); circ(d, cx + 18 * q, cy - 10 * q, 9 * q, None, WHITE + (255,))
def tread(img, d, x0, y0, depth, p, col, lab, sub_):
    # coupe du profil : bloc de gomme avec rainures de la profondeur donnée, flèche de mesure
    if p <= 0: return
    k = ease(p); w = 360; h = 170
    d.rectangle([S(x0), S(y0), S(x0 + w * k), S(y0 + h)], fill=RUB + (255,))
    if p < 1: return
    for j in range(3): gx = x0 + 60 + j * 110; d.rectangle([S(gx), S(y0 - 1), S(gx + 40), S(y0 + depth)], fill=BG + (255,))
    gx = x0 + 170; arrow(d, gx + 20, y0 - 70, gx + 20, y0 + depth - 4, col, 6, 1, 22)
    text(img, (x0 + w / 2, y0 + h + 60), lab, BF(64), col); text(img, (x0 + w / 2, y0 + h + 125), sub_, H2(48), INK)
# ---------- objets propres à l'épisode « Akku »
BATG = (60, 190, 90); BATR = (220, 60, 50); PHONE = (40, 40, 46); SCREEN = (215, 232, 245); OIL = (30, 30, 34); GOLD = (240, 190, 60)
def batt(img, d, cx, cy, w, h, p, level, label='', col=None, fs=56):
    # pile vue de face : corps arrondi, borne, remplissage (vert → rouge quand c'est bas), étiquette au centre
    if p <= 0: return
    q = back(p); w, h = w * q, h * q; x0, y0 = cx - w / 2, cy - h / 2
    if w < 30 or h < 30: return   # trop petite (début du rebond) : rien à dessiner
    d.rounded_rectangle([S(cx - w * 0.18), S(y0 - h * 0.08), S(cx + w * 0.18), S(y0 + 4)], S(8), fill=INK + (255,))
    d.rounded_rectangle([S(x0), S(y0), S(x0 + w), S(y0 + h)], S(w * 0.12), fill=WHITE + (255,), outline=INK, width=S(7))
    c = col or mix(BATR, BATG, level / 0.6); fh = (h - 24) * clamp(level)
    if fh > 6: d.rounded_rectangle([S(x0 + 12), S(y0 + h - 12 - fh), S(x0 + w - 12), S(y0 + h - 12)], S(w * 0.08), fill=c + (255,))
    if label: text(img, (cx, cy), label, BF(fs * q), INK)
def phone(img, d, cx, cy, s, p, level=1.0, t=0, bolt=False):
    if p <= 0: return
    q = back(p) * s; w, h = 230 * q, 440 * q
    d.rounded_rectangle([S(cx - w / 2), S(cy - h / 2), S(cx + w / 2), S(cy + h / 2)], S(36 * q), fill=PHONE + (255,))
    d.rounded_rectangle([S(cx - w / 2 + 14 * q), S(cy - h / 2 + 30 * q), S(cx + w / 2 - 14 * q), S(cy + h / 2 - 30 * q)], S(20 * q), fill=SCREEN + (255,))
    batt(img, d, cx, cy + 10 * q, 90 * q, 170 * q, 1, level)
    if bolt: d.polygon([(S(cx + 8 * q), S(cy - 60 * q)), (S(cx - 26 * q), S(cy + 20 * q)), (S(cx), S(cy + 20 * q)), (S(cx - 10 * q), S(cy + 80 * q)), (S(cx + 26 * q), S(cy)), (S(cx), S(cy))], fill=YEL + (255,))
def flame(d, cx, cy, s, t, p=1.0):
    if p <= 0: return
    q = back(p) * s
    for k, (col, sc_) in enumerate((((240, 90, 30), 1.0), ((250, 170, 40), 0.68), ((255, 235, 120), 0.38))):
        f = 1 + 0.08 * math.sin(t * 14 + k * 2); w, h = 110 * q * sc_, 220 * q * sc_ * f; sw = 14 * q * math.sin(t * 9 + k)
        pts = [(cx - w, cy), (cx - w * 0.8, cy - h * 0.45), (cx - w * 0.2 + sw, cy - h * 0.7), (cx + sw * 1.5, cy - h), (cx + w * 0.35 + sw, cy - h * 0.6), (cx + w * 0.85, cy - h * 0.35), (cx + w, cy)]
        d.polygon([(S(x), S(y)) for x, y in pts], fill=col + (255,)); d.ellipse([S(cx - w), S(cy - w * 0.7), S(cx + w), S(cy + w * 0.7)], fill=col + (255,))
def plane(d, cx, cy, s, p):
    if p <= 0: return
    q = back(p) * s; P = lambda x, y: (S(cx + x * q), S(cy + y * q))
    d.rounded_rectangle([*P(-260, -38), *P(240, 38)], S(38 * q), fill=(235, 238, 244, 255), outline=INK, width=S(6))
    d.polygon([P(-40, -10), P(90, -10), P(-60, -200), P(-120, -200)], fill=(200, 210, 225, 255), outline=INK)
    d.polygon([P(-40, 10), P(90, 10), P(-60, 170), P(-120, 170)], fill=(200, 210, 225, 255), outline=INK)
    d.polygon([P(-250, -20), P(-200, -20), P(-250, -130), P(-285, -130)], fill=(200, 210, 225, 255), outline=INK)
    for k in range(6): circ(d, cx + (-150 + k * 55) * q, cy - 6 * q, 9 * q, None, (90, 140, 200, 255))
def factory(img, d, cx, cy, s, p, t):
    if p <= 0: return
    q = back(p) * s; P = lambda x, y: (S(cx + x * q), S(cy + y * q))
    d.polygon([P(-200, 120), P(-200, -20), P(-110, -80), P(-110, -20), P(-20, -80), P(-20, -20), P(70, -80), P(70, -20), P(200, -20), P(200, 120)], fill=(190, 196, 206, 255), outline=INK)
    d.rectangle([*P(120, -170), *P(170, -20)], fill=(160, 166, 176, 255), outline=INK, width=S(5))
    for k in range(3): r = (24 + 10 * k) * q; y = cy - (200 + 60 * k + 20 * math.sin(t * 2 + k)) * q; circ(d, cx + (145 + 20 * k) * q, y, r, None, (200, 200, 205, 200))
def atom(d, cx, cy, s, t, p):
    if p <= 0: return
    q = back(p) * s
    for k in range(3):
        a = k * math.pi / 3 + t * 0.4; pts = [(cx + 150 * q * math.cos(u) * math.cos(a) - 55 * q * math.sin(u) * math.sin(a), cy + 150 * q * math.cos(u) * math.sin(a) + 55 * q * math.sin(u) * math.cos(a)) for u in np.linspace(0, 2 * math.pi, 40)]
        poly(d, pts, BLUE, 6, 1, closed=True); u = t * 3 + k * 2; x = cx + 150 * q * math.cos(u) * math.cos(a) - 55 * q * math.sin(u) * math.sin(a); y = cy + 150 * q * math.cos(u) * math.sin(a) + 55 * q * math.sin(u) * math.cos(a); circ(d, x, y, 12 * q, None, RED + (255,))
    circ(d, cx, cy, 30 * q, INK, YEL + (255,), 5)
def plug(d, cx, cy, s, rot):
    # chargeur secteur : boîtier blanc + deux broches
    a = math.radians(rot); P = lambda x, y: (S(cx + (x * math.cos(a) - y * math.sin(a)) * s), S(cy + (x * math.sin(a) + y * math.cos(a)) * s))
    d.polygon([P(-70, -60), P(70, -60), P(70, 60), P(-70, 60)], fill=WHITE + (255,), outline=INK);
    for x in (-30, 30): d.polygon([P(x - 8, -60), P(x + 8, -60), P(x + 8, -110), P(x - 8, -110)], fill=(170, 170, 175, 255))
def pbank(d, cx, cy, s, rot):
    a = math.radians(rot); P = lambda x, y: (S(cx + (x * math.cos(a) - y * math.sin(a)) * s), S(cy + (x * math.sin(a) + y * math.cos(a)) * s))
    d.polygon([P(-60, -110), P(60, -110), P(60, 110), P(-60, 110)], fill=(70, 80, 95, 255), outline=INK)
    for k in range(4): d.polygon([P(-30 + k * 20 - 6, 70), P(-30 + k * 20 + 6, 70), P(-30 + k * 20 + 6, 82), P(-30 + k * 20 - 6, 82)], fill=BATG + (255,))
def cable(d, cx, cy, s, rot):
    a = math.radians(rot); pts = [(cx + (x * math.cos(a) - y * math.sin(a)) * s, cy + (x * math.sin(a) + y * math.cos(a)) * s) for x, y in [(-90 + 9 * k, 40 * math.sin(k * 0.5)) for k in range(21)]]
    poly(d, pts, INK, 7 * s); x, y = pts[-1]; d.ellipse([S(x - 18 * s), S(y - 18 * s), S(x + 18 * s), S(y + 18 * s)], fill=WHITE + (255,), outline=INK, width=S(5))
def pump(img, d, cx, cy, s, p, empty=0.0):
    if p <= 0: return
    q = back(p) * s
    d.rounded_rectangle([S(cx - 100 * q), S(cy - 200 * q), S(cx + 100 * q), S(cy + 200 * q)], S(24 * q), fill=(220, 60, 50, 255), outline=INK, width=S(6))
    d.rectangle([S(cx - 70 * q), S(cy - 160 * q), S(cx + 70 * q), S(cy - 60 * q)], fill=WHITE + (255,), outline=INK, width=S(4))
    poly(d, [(cx + 100 * q, cy - 80 * q), (cx + 150 * q, cy - 60 * q), (cx + 160 * q, cy + 60 * q), (cx + 130 * q, cy + 100 * q)], INK, 9)
    if empty > 0: text(img, (cx, cy - 110 * q), 'LEER', BF(44 * q), RED, empty)
def barrel(img, d, cx, cy, s, p):
    if p <= 0: return
    q = back(p) * s
    d.rounded_rectangle([S(cx - 90 * q), S(cy - 130 * q), S(cx + 90 * q), S(cy + 130 * q)], S(30 * q), fill=OIL + (255,), outline=INK, width=S(5))
    for y in (-60, 60): line(d, cx - 88 * q, cy + y * q, cx + 88 * q, cy + y * q, (90, 90, 96), 6)
    d.ellipse([S(cx - 26 * q), S(cy - 22 * q), S(cx + 26 * q), S(cy + 30 * q)], fill=(80, 80, 88, 255)); d.polygon([(S(cx - 24 * q), S(cy)), (S(cx), S(cy - 50 * q)), (S(cx + 24 * q), S(cy))], fill=(80, 80, 88, 255))
def globe(d, cx, cy, r, t, p):
    if p <= 0: return
    rr = r * back(p); circ(d, cx, cy, rr, INK, (90, 170, 235, 255), 7)
    for lon, lat, s in ((0.0, -0.3, 0.32), (1.4, 0.15, 0.38), (2.6, 0.45, 0.24), (3.9, -0.1, 0.3), (5.0, 0.35, 0.22)):
        a = lon + t * 0.9
        if math.cos(a) < 0: continue
        cx2 = cx + math.sin(a) * rr * 0.75; sx = max(0.15, math.cos(a)); s2 = s * rr
        d.ellipse([S(cx2 - s2 * sx), S(cy + lat * rr - s2 * 0.8), S(cx2 + s2 * sx), S(cy + lat * rr + s2 * 0.8)], fill=(90, 180, 90, 255))
    circ(d, cx, cy, rr, INK, None, 7)
def bottle(d, cx, cy, s, p):
    if p <= 0: return
    q = back(p) * s; pts = [(cx - 70 * q, cy + 230 * q), (cx - 70 * q, cy - 80 * q), (cx - 30 * q, cy - 160 * q), (cx - 30 * q, cy - 230 * q), (cx + 30 * q, cy - 230 * q), (cx + 30 * q, cy - 160 * q), (cx + 70 * q, cy - 80 * q), (cx + 70 * q, cy + 230 * q)]
    d.polygon([(S(x), S(y)) for x, y in pts], fill=(200, 230, 250, 200)); poly(d, pts, INK, 6, 1, closed=True)
    d.rectangle([S(cx - 36 * q), S(cy - 262 * q), S(cx + 36 * q), S(cy - 230 * q)], fill=RED + (255,))
# ---------- repères temporels
T = dict(warum=tw('warum'), hersteller=tw('hersteller'), nein=tw('nein'), in_=tw('in'), wh15=tw('15'), tag=tw('tag'), h100=tw('100', 1), hundertmal=tw('hundertmal'),
         heutiger=tw('heutiger'), fuenf=tw('fünf'), kilo=tw('kilo'), flasche=tw('zwei-liter-flasche'), viel=tw('viel', 1), tasche=tw('hosentasche'), dazu=tw('dazu'),
         gefaehrlicher=tw('gefährlicher'), feuer=tw('feuer'), flugzeug=tw('flugzeug'), erlaubt=tw('erlaubt'), w100=tw('100', 2), chemie=tw('chemie'), prozent=tw('prozent'),
         herstellern=tw('herstellern'), physik=tw('physik'), aber=tw('aber'), ginge=tw('ginge'), ladekabel=tw('ladekabel'), netzteile=tw('netzteile'), powerbanks=tw('powerbanks'),
         ueberfluessig=tw('überflüssig'), milliarden=tw('milliardenmarkt'), auto=tw('auto'), eauto=tw('e-auto'), k400=tw('400'), k40000=tw('40000'), einmal=tw('einmal'),
         jahr2=tw('jahr', 1), tankstellen=tw('tankstellen'), leer=tw('leer'), oel=tw('ölkonzerne'), problem=tw('problem'), solar=tw('solarstrom'), sommer=tw('sommer'),
         winter=tw('winter'), welt=tw('welt'), forscher=tw('forscher'), fest=tw('festkörper-akkus'), doppelt=tw('doppelt'), hundert2=tw('hundertmal', 1), entfernt=tw('entfernt'), sags=tw("sag's"))
for k, v in T.items():
    if v is None: print('mot introuvable :', k)
SC = [0, T['in_'] - 0.12, T['heutiger'] - 0.25, T['dazu'] - 0.12, T['chemie'] - 0.35, T['aber'] - 0.12, T['eauto'] - 0.25, T['solar'] - 0.2, T['forscher'] - 0.12, T['sags'] - 0.12, DUR]
SOURCES = [(T['wh15'] - 0.2, T['dazu'] - 0.3, 'Richtwert: Li-Ionen-Akkus ca. 250–300 Wh pro Kilo'), (T['flugzeug'] - 0.1, T['chemie'] - 0.4, 'Quelle: IATA-Gefahrgutvorschriften')]
# ---------- caméra : très léger zoom continu + petits zooms d'impact (pas de transition glissée)
PUNCH = [(T['nein'], 0.06), (T['fuenf'], 0.05), (T['feuer'], 0.06), (T['physik'], 0.06), (T['milliarden'], 0.05), (T['k40000'], 0.06), (T['leer'], 0.05), (T['welt'], 0.05)]
SHAKE = [(T['nein'], 12), (T['feuer'], 10), (T['milliarden'], 12)]
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
HOT = re.compile(r'(\d|akku|wattstunden|tag|energie|kilo|flasche|gefährlich|feuer|flugzeug|chemie|physik|hersteller|ladekabel|netzteile|powerbanks|milliarden|auto|kilometer|tankstellen|leer|ölkonzerne|solarstrom|winter|welt|festkörper|hundertmal)', re.I)
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
    if sc == 0:   # « 100 jours ? » ; les fabricants ? → NEIN
        lv = 1 - 0.85 * ((t * 0.5) % 1); phone(img, d, 330, 860, 1.0, clamp(u0 / 0.4), lv, t)
        calendar(img, d, 780, 740, '100', sc_(t, 'warum', 0.6, 0.4), BLUE, 1.5); text(img, (780, 920), 'Tage?', H2(64), BLUE, sc_(t, 'warum', 0.8, 0.3))
        factory(img, d, 780, 1190, 0.8, sc_(t, 'hersteller', -0.2, 0.4), t); text(img, (980, 1080), '?', BF(110), RED, sc_(t, 'hersteller', 0.1, 0.3))
        if T['nein'] and t > T['nein'] - 0.05:
            cross(d, CX, 900, 320, sc_(t, 'nein', -0.05, 0.35), RED, 18)
            k = since(t, T['nein'], 0.2); text(img, (CX, 1260), 'NEIN!', BF(130), RED, k, rot=-6, scale=1.5 - 0.5 * k)
    elif sc == 1:  # 15 Wh = 1 jour ; 100 jours = ×100
        def one(lay, dl):
            phone(lay, dl, 330, 820, 1.0, clamp(u0 / 0.4), 0.9, t); text(lay, (330, 1120), '≈ 15 Wh', BF(70), INK, sc_(t, 'wh15', -0.2, 0.3))
            arrow(dl, 500, 820, 640, 820, INK, 8, sc_(t, 'tag', -0.4, 0.3)); calendar(lay, dl, 790, 820, '1 Tag', sc_(t, 'tag', -0.3, 0.4), GREEN, 1.4)
        sub(img, gone(t, T['h100'] - 0.15), one)
        if T['h100'] and t > T['h100'] - 0.2:
            text(img, (CX, 470), 'für 100 Tage', H2(80), INK, sc_(t, 'h100', -0.2, 0.3))
            for j in range(100):
                x = 170 + (j % 10) * 82; y = 600 + (j // 10) * 58; q = since(t, T['h100'] + j * 0.012, 0.2)
                if q > 0: batt(img, d, x, y, 44 * q, 52 * q, 1, 0.9)
            if T['hundertmal'] and t > T['hundertmal'] - 0.1: k = sc_(t, 'hundertmal', -0.1, 0.25); text(img, (CX, 1220), '× 100 Energie', BF(90), RED, k, scale=1.4 - 0.4 * k)
    elif sc == 2:  # 5 kg, comme une bouteille de 2 litres ; dans la poche…
        def big(lay, dl):
            batt(lay, dl, 340, 860, 300, 520, sc_(t, 'heutiger', -0.1, 0.5), 0.95, '', fs=70)
            if T['kilo'] and t > T['fuenf'] - 0.2: k = sc_(t, 'fuenf', -0.2, 0.3); text(lay, (340, 860), '5 kg', BF(110), INK, k, scale=1.4 - 0.4 * k)
            bottle(dl, 790, 860, 1.25, sc_(t, 'flasche', -0.4, 0.4)); text(lay, (790, 1220), '2 Liter', H2(66), BLUE, sc_(t, 'flasche', -0.2, 0.3))
            text(lay, (565, 860), '=', BF(110), INK, sc_(t, 'flasche', -0.3, 0.3))
        sub(img, gone(t, T['viel'] - 0.1), big)
        if T['viel'] and t > T['viel'] - 0.2:
            k = sc_(t, 'viel', -0.2, 0.5); pts = [(260, 640), (820, 640), (790, 1240), (540, 1340), (290, 1240)]
            d.polygon([(S(x), S(y)) for x, y in pts], fill=(70, 110, 170, 255)); poly(d, pts, INK, 7, 1, closed=True)
            poly(d, [(300, 700), (780, 700)], (230, 190, 90), 5, 1)
            batt(img, d, CX + 10 * math.sin(t * 9), 760 - 60 * ease(k), 240, 380, k, 0.95, '5 kg', fs=70)
            for j in range(3): circ(d, 900 + 20 * j, 560 + ((t * 2 + j * 0.3) % 1) * 140, 14, None, (110, 170, 230, 220))
            text(img, (CX, 430), 'viel Spaß …', H2(84), INK, sc_(t, 'tasche', -0.3, 0.3))
    elif sc == 3:  # plus d'énergie = plus dangereux ; feu ; avion : max 100 Wh
        def fire(lay, dl):
            text(lay, (CX, 470), 'mehr Energie = gefährlicher', BF(56), RED, sc_(t, 'gefaehrlicher', -0.6, 0.3))
            batt(lay, dl, CX, 920, 280, 440, clamp(u0 / 0.4), 0.95)
            flame(dl, CX, 720, 1.4, t, sc_(t, 'feuer', -0.2, 0.4))
        sub(img, gone(t, T['flugzeug'] - 0.1), fire)
        if T['flugzeug'] and t > T['flugzeug'] - 0.3:
            plane(d, CX, 760, 1.2, sc_(t, 'flugzeug', -0.3, 0.45)); batt(img, d, CX, 1110, 140, 220, sc_(t, 'flugzeug', 0.1, 0.4), 0.95, '5 kg', fs=40)
            cross(d, CX, 1110, 140, sc_(t, 'erlaubt', -0.2, 0.35), RED, 14)
            if T['w100'] and t > T['w100'] - 0.2: k = sc_(t, 'w100', -0.2, 0.3); text(img, (CX, 470), 'erlaubt: max. 100 Wh', BF(70), INK, k, scale=1.3 - 0.3 * k)
    elif sc == 4:  # la chimie progresse lentement ; pas les fabricants : la physique
        def slow(lay, dl):
            ox, oy, gw, gh = 170, 1150, 760, 520; k = clamp(u0 / 0.5)
            line(dl, ox, oy, ox + gw * k, oy, INK, 7); line(dl, ox, oy, ox, oy - gh * k, INK, 7)
            q = sc_(t, 'prozent', -0.6, 1.2); poly(dl, [(ox + gw * u, oy - 140 - 90 * u) for u in np.linspace(0, 1, 30)], GREEN, 8, q)
            text(lay, (ox + gw - 10, oy - 280), '+ ein paar % / Jahr', H2(58), GREEN, sc_(t, 'prozent', -0.2, 0.3), anchor='rm')
            text(lay, (CX, 470), 'Akku-Chemie', BF(72), INK, clamp(u0 / 0.3)); text(lay, (ox + gw, oy + 50), 'Jahre', H2(48), GREY, k, anchor='rm')
        sub(img, gone(t, T['herstellern'] - 0.6), slow)
        if T['herstellern'] and t > T['herstellern'] - 0.7:
            def who(lay, dl):
                factory(lay, dl, 300, 860, 0.9, sc_(t, 'herstellern', -0.6, 0.4), t); cross(dl, 300, 820, 170, sc_(t, 'herstellern', 0.0, 0.35), RED, 13)
                text(lay, (300, 1110), 'nicht die Hersteller', H2(52), INK, sc_(t, 'herstellern', -0.2, 0.3))
                atom(dl, 790, 840, 1.0, t, sc_(t, 'physik', -0.3, 0.4)); k = sc_(t, 'physik', -0.1, 0.25); text(lay, (790, 1110), 'PHYSIK', BF(84), BLUE, k, scale=1.4 - 0.4 * k)
            sub(img, 1, who)
    elif sc == 5:  # « et si c'était possible ? » : câbles, chargeurs, powerbanks inutiles ; un marché s'effondre ; téléphone → voiture
        def what(lay, dl):
            k = clamp(u0 / 0.3); text(lay, (CX, 480), 'Was wäre, wenn …?', BF(80), RED, k, scale=1.3 - 0.3 * k)
            fall = sc_(t, 'ueberfluessig', -0.2, 0.8)
            for j, (k_, fn, x) in enumerate((('ladekabel', cable, 250), ('netzteile', plug, CX), ('powerbanks', pbank, 830))):
                q = sc_(t, k_, -0.2, 0.4)
                if q <= 0: continue
                y = 860 + 520 * fall ** 2 * (1 + 0.2 * j); fn(dl, x, y, 1.2 * back(q), 70 * fall * (1 if j % 2 else -1))
            if T['milliarden'] and t > T['milliarden'] - 0.2:
                kk = sc_(t, 'milliarden', -0.2, 0.25); text(lay, (CX, 1000), 'Milliardenmarkt', BF(76), INK, kk, scale=1.4 - 0.4 * kk)
                arrow(dl, CX - 220, 1080, CX + 220, 1280, RED, 12, sc_(t, 'milliarden', 0.1, 0.4), 44)
        sub(img, gone(t, T['auto'] - 0.9), what)
        if T['auto'] and t > T['auto'] - 0.9:
            phone(img, d, 260, 860, 0.8, sc_(t, 'auto', -0.9, 0.4), 1.0, t); arrow(d, 400, 860, 560, 860, INK, 8, sc_(t, 'auto', -0.4, 0.3))
            car(d, 800, 900, 1.0, sc_(t, 'auto', -0.2, 0.5), col=GREEN)
    elif sc == 6:  # 40 000 km, un an sans recharger ; stations vides ; pétroliers en difficulté
        def drive(lay, dl):
            road(dl, 80, 1000, 1000, clamp(u0 / 0.4), t=t); car(dl, 300 + 60 * math.sin(t * 1.3), 930, 1.0, clamp(u0 / 0.4), col=GREEN)
            if T['k40000']:
                v = 400 if t < T['k40000'] - 0.1 else int(400 + 39600 * eio((t - T['k40000'] + 0.1) / 0.9))
                text(lay, (CX, 560), f'{v:,} km'.replace(',', '.'), BF(110), GREEN if v > 400 else INK, sc_(t, 'k400', -0.2, 0.3))
            if T['einmal'] and t > T['einmal'] - 0.2: calendar(lay, dl, 790, 780, '1 Jahr', sc_(t, 'einmal', -0.2, 0.4), GREEN, 1.2); text(lay, (CX, 1200), '1× laden', H2(70), INK, sc_(t, 'einmal', -0.1, 0.3))
        sub(img, gone(t, T['tankstellen'] - 0.1), drive)
        if T['tankstellen'] and t > T['tankstellen'] - 0.2:
            pump(img, d, 300, 860, 1.2, sc_(t, 'tankstellen', -0.2, 0.4), sc_(t, 'leer', -0.1, 0.3))
            if T['oel'] and t > T['oel'] - 0.2:
                barrel(img, d, 780, 840, 1.1, sc_(t, 'oel', -0.2, 0.4)); arrow(d, 680, 1080, 900, 1300, RED, 12, sc_(t, 'problem', -0.3, 0.4), 40)
                text(img, (CX, 470), 'Ölkonzerne?', BF(86), INK, sc_(t, 'oel', -0.1, 0.3))
    elif sc == 7:  # solaire de l'été utilisé en hiver ; une batterie change le monde
        def season(lay, dl):
            sun(dl, 230, 760, 80, t, sc_(t, 'sommer', -0.3, 0.4)); text(lay, (230, 960), 'Sommer', H2(60), (220, 150, 30), sc_(t, 'sommer', -0.2, 0.3))
            arrow(dl, 350, 760, 430, 760, INK, 7, sc_(t, 'sommer', 0.1, 0.3)); batt(lay, dl, CX, 760, 150, 240, sc_(t, 'sommer', 0.2, 0.4), 0.3 + 0.7 * sc_(t, 'winter', -0.6, 0.6))
            arrow(dl, 650, 760, 730, 760, INK, 7, sc_(t, 'winter', -0.3, 0.3)); snowflake(dl, 850, 760, 80 * back(sc_(t, 'winter', -0.2, 0.4)), BLUE, 8)
            text(lay, (850, 960), 'Winter', H2(60), BLUE, sc_(t, 'winter', -0.1, 0.3)); text(lay, (CX, 470), 'Solarstrom speichern', BF(66), INK, sc_(t, 'solar', -0.1, 0.3))
        sub(img, gone(t, T['welt'] - 0.6), season)
        if T['welt'] and t > T['welt'] - 0.7:
            globe(d, CX, 860, 260, sc_(t, 'welt', -0.7, 0.5), t); batt(img, d, CX + 230, 1080, 120, 190, sc_(t, 'welt', -0.4, 0.4), 1.0)
            k = sc_(t, 'welt', 0.0, 0.3); text(img, (CX, 470), 'die Welt verändern', BF(76), GREEN, k, scale=1.3 - 0.3 * k)
    elif sc == 8:  # batteries solides : ×2 peut-être, ×100 encore loin
        text(img, (CX, 470), 'Festkörper-Akku', BF(76), INK, sc_(t, 'fest', -0.3, 0.3))
        batt(img, d, 300, 880, 180, 300, sc_(t, 'fest', -0.2, 0.4), 1.0, '', col=GOLD)
        k = sc_(t, 'doppelt', -0.1, 0.3); text(img, (300, 1120), '× 2', BF(90), GREEN, k, scale=1.3 - 0.3 * k); check(d, 420, 1120, 36, sc_(t, 'doppelt', 0.2, 0.4))
        if T['hundert2'] and t > T['hundert2'] - 0.2:
            k2 = sc_(t, 'hundert2', -0.2, 0.3); text(img, (790, 880), '× 100?', BF(110), RED, k2, scale=1.4 - 0.4 * k2)
            if T['entfernt'] and t > T['entfernt'] - 0.3: cross(d, 790, 880, 150, sc_(t, 'entfernt', -0.3, 0.35), RED, 12); text(img, (790, 1120), 'noch weit weg', H2(60), INK, sc_(t, 'entfernt', -0.2, 0.3))
    elif sc == 9:  # partage
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
    sfx('pop', T['warum'] + 0.6, 0.1); sfx('pop', T['hersteller'] - 0.2, 0.1); sfx('hit', T['nein'] - 0.03, 0.4); sfx('pop', T['wh15'] - 0.2, 0.12); sfx('ding', T['tag'] - 0.3, 0.1)
    sfx('whoosh', T['h100'] - 0.1, 0.12); sfx('hit', T['hundertmal'] - 0.1, 0.2); sfx('thud', T['fuenf'] - 0.2, 0.25); sfx('pop', T['flasche'] - 0.4, 0.12); sfx('swish', T['viel'] - 0.2, 0.15)
    sfx('buzz', T['gefaehrlicher'] - 0.5, 0.06); sfx('hit', T['feuer'] - 0.2, 0.25); sfx('whoosh', T['flugzeug'] - 0.3, 0.15); sfx('buzz', T['erlaubt'] - 0.2, 0.08); sfx('pop', T['w100'] - 0.2, 0.12)
    sfx('tap', T['prozent'] - 0.2, 0.1); sfx('pop', T['herstellern'] - 0.6, 0.1); sfx('hit', T['physik'] - 0.1, 0.3); sfx('glitch', T['aber'], 0.12)
    for k in ('ladekabel', 'netzteile', 'powerbanks'): sfx('pop', T[k] - 0.2, 0.12)
    sfx('clank', T['ueberfluessig'] + 0.3, 0.2); sfx('hit', T['milliarden'] - 0.2, 0.25); sfx('whoosh', T['auto'] - 0.3, 0.12); sfx('zoom1', T['k40000'] - 0.1, 0.15)
    sfx('ding', T['einmal'] - 0.2, 0.12); sfx('pop', T['tankstellen'] - 0.2, 0.12); sfx('buzz', T['leer'] - 0.1, 0.08); sfx('thud', T['oel'] - 0.2, 0.2)
    sfx('shine', T['sommer'] - 0.3, 0.12); sfx('pop', T['winter'] - 0.2, 0.12); sfx('shine', T['welt'] - 0.2, 0.15); sfx('pop', T['fest'] - 0.2, 0.12)
    sfx('ding', T['doppelt'] + 0.2, 0.12); sfx('hit', T['hundert2'] - 0.2, 0.2); sfx('pop', T['sags'] + 0.3, 0.15)
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
