# Compte US – « The man who said his car ran on water » (version anglaise courte de explain_wasserauto.py + 3 clips IA bonhomme bâton) – histoire de Stanley Meyer, la rumeur, puis la vraie raison (physique) et la voiture à hydrogène.
# Même moteur que l ampoule (explain_gluehbirne.py) + un personnage animé (person) : marche, court, tombe, hausse les épaules.
# usage : explain_wasserauto.py dossier sortie.mp4  [PREVIEW=t1,t2,...] [K=1 (1080p, défaut) | K=2 (4K)] [TAIL=0.5]
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
NAME, HANDLE = '', ''   # compte US : pas de nom à l'écran pour l'instant
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
# ---------- personnage animé (vu de face, membres articulés) : angle 0 = vers le bas, 90 = vers la droite, 180 = vers le haut
PANTS = (52, 58, 78); SHOE = (40, 34, 30); SUIT = (70, 70, 80)
POSES = {
    'stand':  dict(lu=-12, ll=-6, ru=12, rl=6, lt=-6, ls=-4, rt=6, rs=4),
    'shock':  dict(lu=-145, ll=-175, ru=145, rl=175, lt=-10, ls=-6, rt=10, rs=6),
    'throat': dict(lu=-30, ll=145, ru=30, rl=-145, lt=-8, ls=-4, rt=8, rs=4),
    'shrug':  dict(lu=-55, ll=-140, ru=55, rl=140, lt=-6, ls=-4, rt=6, rs=4),
    'point':  dict(lu=-12, ll=-6, ru=95, rl=100, lt=-6, ls=-4, rt=6, rs=4),
    'hold':   dict(lu=-12, ll=-6, ru=60, rl=110, lt=-6, ls=-4, rt=6, rs=4),
    'cheer':  dict(lu=-150, ll=-165, ru=150, rl=165, lt=-8, ls=-4, rt=8, rs=4),
    'sit':    dict(lu=-10, ll=40, ru=10, rl=70, lt=-80, ls=-4, rt=-75, rs=4),
    'toast':  dict(lu=-10, ll=40, ru=40, rl=150, lt=-80, ls=-4, rt=-75, rs=4),
}
def lerp_pose(a, b, u):
    A, B = POSES[a] if isinstance(a, str) else a, POSES[b] if isinstance(b, str) else b
    return {k: A[k] + (B[k] - A[k]) * eio(u) for k in A}
def run_pose(t, sp=9.0):
    ph = math.sin(t * sp); q = math.cos(t * sp)
    return dict(lu=-35 * ph - 10, ll=-35 * ph + 50, ru=35 * ph + 10, rl=35 * ph - 50, lt=32 * ph, ls=32 * ph - 25 - 20 * max(0, q), rt=-32 * ph, rs=-32 * ph - 25 - 20 * max(0, -q))
def person(img, d, x, y, s, pose, t, shirt=BLUE, hair=(70, 48, 32), rot=0.0, mouth='smile', beard=False, grey=False, eyes=True, alpha=1.0, bob=0.0):
    # (x, y) = point entre les pieds ; rot = bascule autour des pieds (chute) ; respiration légère
    if alpha <= 0.01: return
    P = POSES[pose] if isinstance(pose, str) else pose
    br = 3 * math.sin(t * 2.4) + bob; ar = math.radians(rot)
    def R(px, py):   # repère du personnage -> écran (rotation autour des pieds)
        return (x + (px * math.cos(ar) - py * math.sin(ar)) * s, y + (px * math.sin(ar) + py * math.cos(ar)) * s)
    def v(a, L): return (L * math.sin(math.radians(a)), L * math.cos(math.radians(a)))
    hip = (0, -190 + br * 0.3); sh_l = (-46, -350 + br); sh_r = (46, -350 + br); neck = (0, -372 + br); head = (0, -432 + br)
    def limb(p0, a1, l1, a2, l2, col, w):
        k = (p0[0] + v(a1, l1)[0], p0[1] + v(a1, l1)[1]); e = (k[0] + v(a2, l2)[0], k[1] + v(a2, l2)[1])
        A, B, C = R(*p0), R(*k), R(*e); d.line([(S(A[0]), S(A[1])), (S(B[0]), S(B[1])), (S(C[0]), S(C[1]))], fill=col, width=S(w * s), joint='curve')
        for pt in (A, B): circ(d, pt[0], pt[1], w * s / 2, None, col + (255,))
        return C
    # jambes
    for side, (ta, sa) in ((-1, (P['lt'], P['ls'])), (1, (P['rt'], P['rs']))):
        foot = limb((side * 22, hip[1]), ta, 100, sa, 98, PANTS, 34)
        fx, fy = foot; d.ellipse([S(fx - 26 * s), S(fy - 12 * s), S(fx + 30 * s), S(fy + 12 * s)], fill=SHOE + (255,))
    # bras derrière le corps (gauche), corps, bras devant (droit)
    hand_l = limb(sh_l, P['lu'], 84, P['ll'], 80, shirt, 28)
    body = [R(-52, -352 + br), R(52, -352 + br), R(42, hip[1] + 6), R(-42, hip[1] + 6)]
    d.polygon([(S(px), S(py)) for px, py in body], fill=shirt + (255,)); poly(d, body, INK, 5 * s, 1, closed=True)
    hand_r = limb(sh_r, P['ru'], 84, P['rl'], 80, shirt, 28)
    for hx, hy in (hand_l, hand_r): circ(d, hx, hy, 17 * s, INK, SKIN + (255,), 4 * s)
    # tête
    hx, hy = R(*head); r = 58 * s
    circ(d, hx, hy, r, INK, SKIN + (255,), 5 * s)
    hc = (196, 196, 200) if grey else hair
    d.chord([S(hx - r), S(hy - r), S(hx + r), S(hy + r)], 195 + rot, 345 + rot, fill=hc + (255,))
    if beard: d.chord([S(hx - r), S(hy - r), S(hx + r), S(hy + r)], 15 + rot, 165 + rot, fill=hc + (255,))
    def F2(px, py): return (hx + (px * math.cos(ar) - py * math.sin(ar)) * s, hy + (px * math.sin(ar) + py * math.cos(ar)) * s)
    blink = (t % 3.1) < 0.12
    for ex in (-20, 20):
        X, Y = F2(ex, -4)
        if not eyes or blink: line(d, X - 8 * s, Y, X + 8 * s, Y, INK, 4 * s)
        else: circ(d, X, Y, 7 * s, None, INK + (255,))
    mx, my = F2(0, 26)
    if beard: my -= 4 * s
    if mouth == 'o': circ(d, mx, my, 11 * s, INK, (120, 40, 40, 255), 3 * s)
    elif mouth == 'flat': line(d, mx - 14 * s, my, mx + 14 * s, my, INK, 4 * s)
    elif mouth == 'pain': poly(d, [(mx - 16 * s, my + 3 * s), (mx - 8 * s, my - 4 * s), (mx, my + 3 * s), (mx + 8 * s, my - 4 * s), (mx + 16 * s, my + 3 * s)], INK, 4 * s)
    else: arc(d, mx, my - 8 * s, 16 * s, 20 + rot, 160 + rot, INK, 4 * s)
    return hand_l, hand_r
# ---------- objets propres à l'épisode « Wasserauto »
WATER = (90, 160, 230); WATERL = (170, 210, 245); MONEY = (110, 170, 90); DIRT = (150, 130, 110)
def faucet(d, cx, cy, s, p):
    if p <= 0: return
    q = back(p) * s; P = lambda x, y: (S(cx + x * q), S(cy + y * q))
    d.rounded_rectangle([*P(-140, -40), *P(40, 20)], S(16 * q), fill=(190, 194, 202, 255), outline=INK, width=S(5))
    d.rounded_rectangle([*P(0, -40), *P(40, 90)], S(14 * q), fill=(190, 194, 202, 255), outline=INK, width=S(5))
    d.rounded_rectangle([*P(-90, -90), *P(-40, -40)], S(10 * q), fill=(170, 174, 182, 255), outline=INK, width=S(5))
    d.rounded_rectangle([*P(-130, -110), *P(0, -86)], S(10 * q), fill=(210, 60, 50, 255), outline=INK, width=S(4))
def stream(d, x, y0, y1, t, p, w=26):
    # jet d'eau qui tombe, avec des reflets qui défilent
    if p <= 0: return
    ye = y0 + (y1 - y0) * ease(p)
    d.rounded_rectangle([S(x - w / 2), S(y0), S(x + w / 2), S(ye)], S(w / 2), fill=WATER + (230,))
    for k in range(6):
        yy = y0 + ((t * 600 + k * 70) % max(1, ye - y0)); line(d, x - 3, yy, x - 3, min(ye, yy + 26), WATERL, 5)
    if p >= 1:
        for k in range(5):
            a = math.pi + 0.3 + k * 0.6; u = (t * 3 + k * 0.23) % 1; circ(d, x + math.cos(a) * 60 * u, y1 - math.sin(abs(a)) * 40 * u * (1 - u) * 4, 6, None, WATER + (int(220 * (1 - u)),))
def drop(d, cx, cy, r, col=WATER):
    d.polygon([(S(cx), S(cy - r * 1.9)), (S(cx - r * 0.85), S(cy - r * 0.35)), (S(cx + r * 0.85), S(cy - r * 0.35))], fill=col + (255,)); circ(d, cx, cy, r, None, col + (255,))
def price_board(img, d, cx, cy, s, p, val, col=RED):
    if p <= 0: return
    q = back(p) * s
    d.rounded_rectangle([S(cx - 210 * q), S(cy - 90 * q), S(cx + 210 * q), S(cy + 90 * q)], S(18 * q), fill=(30, 30, 34, 255), outline=INK, width=S(6))
    text(img, (cx, cy - 46 * q), 'SUPER E10', BF(34 * q), (200, 200, 200)); text(img, (cx, cy + 22 * q), val, BF(92 * q), col)
def nozzle(d, x, y, s, p):
    if p <= 0: return
    q = back(p) * s; P = lambda a, b: (S(x + a * q), S(y + b * q))
    d.polygon([P(0, 0), P(120, -20), P(140, 10), P(30, 40)], fill=(40, 40, 46, 255)); d.rounded_rectangle([*P(120, -16), *P(210, 4)], S(6 * q), fill=(150, 150, 156, 255))
def sparkle(d, cx, cy, r, t, col=YEL):
    for k in range(4):
        a = k * math.pi / 2 + t * 2; rr = r * (0.8 + 0.3 * math.sin(t * 10 + k)); line(d, cx + 0.2 * rr * math.cos(a), cy + 0.2 * rr * math.sin(a), cx + rr * math.cos(a), cy + rr * math.sin(a), col, 7)
def exhaust(d, x, y, t, p, col=(170, 166, 160), water=False):
    if p <= 0: return
    for k in range(6):
        u = (t * 1.6 + k / 6) % 1
        if water: drop(d, x - 30 - 120 * u, y + 10 + 260 * u * u, 12 * (1 - 0.3 * u), WATER)
        else: circ(d, x - 30 - 170 * u, y - 30 * u + 8 * math.sin(t * 5 + k), (16 + 40 * u) * p, None, col + (int(180 * (1 - u)),))
def buggy(img, d, cx, cy, s, p, t, shake=0.0):
    # dune buggy de Meyer : châssis tubulaire, gros pneus, réservoir transparent avec bulles
    if p <= 0: return
    q = back(p) * s; oy = shake * 5 * math.sin(t * 60); P = lambda x, y: (S(cx + x * q), S(cy + (y + oy) * q))
    d.polygon([P(-230, 0), P(-200, -70), P(-60, -80), P(-10, -150), P(110, -150), P(170, -70), P(230, -50), P(240, 0)], fill=(230, 160, 50, 255), outline=INK)
    poly(d, [(cx - 20 * q, cy + (-150 + oy) * q), (cx - 70 * q, cy + (-230 + oy) * q), (cx + 120 * q, cy + (-230 + oy) * q), (cx + 110 * q, cy + (-150 + oy) * q)], INK, 9)
    for wx in (-150, 160): circ(d, cx + wx * q, cy + 10 * q, 70 * q, INK, RUB + (255,), 6); circ(d, cx + wx * q, cy + 10 * q, 28 * q, None, (190, 192, 198, 255))
    tx, ty = cx + 40 * q, cy + (-60 + oy) * q
    d.rounded_rectangle([S(tx - 40 * q), S(ty - 70 * q), S(tx + 40 * q), S(ty + 30 * q)], S(14 * q), fill=WATERL + (220,), outline=INK, width=S(5))
    for k in range(7):
        u = (t * 0.9 + k * 0.143) % 1; circ(d, tx - 22 * q + (k * 13 % 44) * q, ty + 25 * q - 90 * q * u, 6 * q, None, WHITE + (int(230 * (1 - u)),))
def usa(img, d, cx, cy, s, p, route):
    # silhouette simplifiée des États-Unis + trajet Los Angeles -> New York
    if p <= 0: return
    q = s; pts = [(-300, -120), (-170, -150), (60, -140), (180, -120), (250, -170), (300, -150), (290, -70), (250, -20), (240, 60), (170, 70), (120, 130), (90, 90), (-40, 100), (-90, 160), (-150, 100), (-250, 70), (-300, 0)]
    pts = [(cx + x * q, cy + y * q) for x, y in pts]
    if p >= 1: d.polygon([(S(x), S(y)) for x, y in pts], fill=(214, 226, 200, 255))
    poly(d, pts, INK, 7, ease(p), closed=p >= 1)
    if route > 0:
        a = (cx - 270 * q, cy + 20 * q); b = (cx + 265 * q, cy - 110 * q); path = [(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u - 80 * q * math.sin(u * math.pi)) for u in np.linspace(0, 1, 30)]
        poly(d, path, RED, 8, route); circ(d, *a, 14 * q, INK, RED + (255,), 4)
        if route >= 1: circ(d, *b, 14 * q, INK, RED + (255,), 4)
        text(img, (a[0] + 10, a[1] + 60 * q), 'Los Angeles', H2(40 * q), INK, clamp(route * 3)); text(img, (b[0] - 30, b[1] - 50 * q), 'New York', H2(40 * q), INK, clamp(route * 2 - 1))
def bill(d, cx, cy, s, rot):
    a = math.radians(rot); P = lambda x, y: (S(cx + (x * math.cos(a) - y * math.sin(a)) * s), S(cy + (x * math.sin(a) + y * math.cos(a)) * s))
    d.polygon([P(-70, -34), P(70, -34), P(70, 34), P(-70, 34)], fill=MONEY + (255,), outline=INK)
    d.ellipse([*P(-18, -18), *P(18, 18)] if abs(rot) < 1 else [S(cx - 18 * s), S(cy - 18 * s), S(cx + 18 * s), S(cy + 18 * s)], outline=(60, 110, 50), width=S(4 * s))
def money_rain(d, x0, x1, y0, y1, t, p):
    if p <= 0: return
    for k in range(12):
        u = (t * 0.5 + k * 0.083) % 1; x = x0 + (k * 97 % max(1, int(x1 - x0))) + 30 * math.sin(t * 2 + k)
        bill(d, x, y0 + (y1 - y0) * u, 0.8, 30 * math.sin(t * 3 + k))
def tvcam(img, d, cx, cy, s, p, t):
    if p <= 0: return
    q = back(p) * s; P = lambda x, y: (S(cx + x * q), S(cy + y * q))
    d.rounded_rectangle([*P(-110, -70), *P(80, 60)], S(16 * q), fill=(60, 60, 68, 255), outline=INK, width=S(5))
    d.polygon([P(80, -40), P(150, -70), P(150, 70), P(80, 40)], fill=(80, 80, 90, 255), outline=INK)
    for k, ox in enumerate((-60, 30)): circ(d, cx + ox * q, cy - 100 * q, 42 * q, INK, (80, 80, 90, 255), 5)
    if (t * 2) % 1 < 0.5: circ(d, cx - 80 * q, cy - 45 * q, 12 * q, None, RED + (255,))
    text(img, (cx - 20 * q, cy + 100 * q), 'LIVE', BF(40 * q), RED)
    line(d, cx - 40 * q, cy + 60 * q, cx - 90 * q, cy + 200 * q, INK, 8); line(d, cx - 40 * q, cy + 60 * q, cx + 10 * q, cy + 200 * q, INK, 8)
def flash(img, alpha):
    if alpha <= 0.01: return
    img.alpha_composite(Image.new('RGBA', img.size, (255, 255, 255, int(255 * alpha))))
def table(d, cx, cy, s, p):
    if p <= 0: return
    q = back(p) * s
    d.rounded_rectangle([S(cx - 260 * q), S(cy - 20 * q), S(cx + 260 * q), S(cy + 20 * q)], S(10 * q), fill=(150, 100, 60, 255), outline=INK, width=S(5))
    for x in (-220, 220): line(d, cx + x * q, cy + 20 * q, cx + x * q, cy + 220 * q, INK, 10)
def glass(d, cx, cy, s, tilt=0.0):
    a = math.radians(tilt); P = lambda x, y: (S(cx + (x * math.cos(a) - y * math.sin(a)) * s), S(cy + (x * math.sin(a) + y * math.cos(a)) * s))
    d.polygon([P(-26, -70), P(26, -70), P(18, 10), P(-18, 10)], fill=(240, 220, 150, 230), outline=INK)
    d.polygon([P(-26, -70), P(26, -70), P(24, -54), P(-24, -54)], fill=WHITE + (240,))
    line(d, *[c / SS for c in P(0, 10)], *[c / SS for c in P(0, 50)], INK, 6); line(d, *[c / SS for c in P(-22, 50)], *[c / SS for c in P(22, 50)], INK, 6)
def door(d, cx, cy, s, p, open_=0.0):
    if p <= 0: return
    q = back(p) * s
    d.rectangle([S(cx - 90 * q), S(cy - 220 * q), S(cx + 90 * q), S(cy + 220 * q)], fill=(60, 50, 44, 255), outline=INK, width=S(6))
    w = 180 * q * (1 - 0.8 * open_); d.rectangle([S(cx - 90 * q), S(cy - 220 * q), S(cx - 90 * q + w), S(cy + 220 * q)], fill=(150, 100, 60, 255), outline=INK, width=S(5))
    if open_ < 0.5: circ(d, cx + 60 * q, cy, 10 * q, None, (230, 190, 90, 255))
def derrick(d, cx, cy, s, p, t):
    # tour de forage + pompe qui hoche la tête
    if p <= 0: return
    q = back(p) * s
    poly(d, [(cx - 90 * q, cy + 200 * q), (cx, cy - 220 * q), (cx + 90 * q, cy + 200 * q)], INK, 9)
    for k in range(4): y = cy + (-120 + 80 * k) * q; w = (25 + 21 * k) * q; line(d, cx - w, y, cx + w, y, INK, 6)
    a = 0.35 * math.sin(t * 3); bx, by = cx + 230 * q, cy + 60 * q
    line(d, bx, by, bx, by + 140 * q, INK, 12); line(d, bx - 120 * q * math.cos(a), by - 120 * q * math.sin(a), bx + 120 * q * math.cos(a), by + 120 * q * math.sin(a), (40, 40, 44), 22)
    circ(d, bx - 130 * q * math.cos(a), by - 130 * q * math.sin(a), 30 * q, INK, (60, 60, 66, 255), 5)
def suit(img, d, cx, cy, s, p, t):
    # silhouette en costume (homme d'affaires, sans visage)
    if p <= 0: return
    q = back(p) * s; P = lambda x, y: (S(cx + x * q), S(cy + y * q))
    d.polygon([P(-80, 0), P(80, 0), P(100, 260), P(-100, 260)], fill=(34, 34, 40, 255)); d.polygon([P(-16, 0), P(16, 0), P(8, 120), P(-8, 120)], fill=(170, 30, 30, 255))
    circ(d, cx, cy - 60 * q, 58 * q, None, (34, 34, 40, 255)); d.rectangle([*P(-70, -130), *P(70, -112)], fill=(20, 20, 24, 255)); d.rectangle([*P(-44, -190), *P(44, -128)], fill=(20, 20, 24, 255))
def doc(img, d, cx, cy, s, p, title, lines, rot=0):
    if p <= 0: return
    q = back(p) * s
    d.rounded_rectangle([S(cx - 190 * q), S(cy - 240 * q), S(cx + 190 * q), S(cy + 240 * q)], S(12 * q), fill=WHITE + (255,), outline=INK, width=S(6))
    text(img, (cx, cy - 180 * q), title, BF(44 * q), INK)
    for k in range(lines): line(d, cx - 140 * q, cy - 100 * q + k * 50 * q, cx + (140 - 60 * (k % 2)) * q, cy - 100 * q + k * 50 * q, (190, 184, 174), 8)
def stamp(img, cx, cy, label, p, col=RED, rot=-12, size=96):
    if p <= 0: return
    k = clamp(p); sc = 1.8 - 0.8 * ease(k)
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    f = BF(size * sc); bb = f.getbbox(label); w = (bb[2] - bb[0]) / SS + 50 * sc; h = (bb[3] - bb[1]) / SS + 40 * sc
    dl.rounded_rectangle([S(cx - w / 2), S(cy - h / 2), S(cx + w / 2), S(cy + h / 2)], S(14), outline=col + (255,), width=S(10 * sc))
    text(lay, (cx, cy), label, f, col)
    lay = lay.rotate(rot, center=(S(cx), S(cy)), resample=Image.BICUBIC)
    if k < 1: lay.putalpha(lay.getchannel('A').point(lambda v: int(v * k)))
    img.alpha_composite(lay)
def molecule(img, d, cx, cy, s, p, split=0.0, t=0):
    # H2O : gros O rouge, deux H blancs ; split = les atomes s'écartent (eau cassée)
    if p <= 0: return
    q = back(p) * s; sp = ease(split) * 170 * q; j = 3 * split * math.sin(t * 40)
    hs = [(cx - 120 * q - sp, cy + 90 * q + j), (cx + 120 * q + sp, cy + 90 * q - j)]
    if split < 0.3:
        for hx, hy in hs: line(d, cx, cy, hx, hy, INK, 14 * q)
    circ(d, cx, cy - sp * 0.4, 100 * q, INK, (220, 70, 60, 255), 7); text(img, (cx, cy - sp * 0.4), 'O', BF(80 * q), WHITE)
    for hx, hy in hs: circ(d, hx, hy, 62 * q, INK, WHITE + (255,), 6); text(img, (hx, hy), 'H', BF(56 * q), INK)
def bolt(d, cx, cy, s, col=YEL):
    d.polygon([(S(cx + 10 * s), S(cy - 70 * s)), (S(cx - 30 * s), S(cy + 10 * s)), (S(cx), S(cy + 10 * s)), (S(cx - 12 * s), S(cy + 70 * s)), (S(cx + 32 * s), S(cy - 10 * s)), (S(cx + 2 * s), S(cy - 10 * s))], fill=col + (255,), outline=INK)
def energy_bar(img, d, x0, y, label, val, col, p):
    if p <= 0: return
    k = ease(p); w = 520 * val * k
    text(img, (x0, y - 46), label, BF(44), INK, clamp(p * 3), anchor='lm')
    d.rounded_rectangle([S(x0), S(y), S(x0 + 520), S(y + 56)], S(14), outline=INK, width=S(5))
    if w > 20: d.rounded_rectangle([S(x0 + 6), S(y + 6), S(x0 + w - 6), S(y + 50)], S(10), fill=col + (255,))
    for k2 in range(int(5 * val * k)): bolt(d, x0 + 50 + k2 * 100, y + 28, 0.33, WHITE)
def ash(d, cx, cy, s, p, t):
    if p <= 0: return
    q = back(p) * s
    d.polygon([(S(cx - 180 * q), S(cy + 40 * q)), (S(cx - 90 * q), S(cy - 40 * q)), (S(cx - 10 * q), S(cy - 70 * q)), (S(cx + 80 * q), S(cy - 40 * q)), (S(cx + 180 * q), S(cy + 40 * q))], fill=(150, 146, 140, 255), outline=INK)
    for k in range(9): circ(d, cx - 140 * q + k * 35 * q, cy + 10 * q - 30 * q * math.sin(k), 9 * q, None, (110, 106, 100, 255))
def match_(d, cx, cy, s, p, t, lit=0.0):
    if p <= 0: return
    q = back(p) * s; line(d, cx, cy, cx + 160 * q, cy - 160 * q, (230, 200, 140), 16 * q); circ(d, cx, cy, 20 * q, INK, (190, 50, 40, 255), 4)
    if lit > 0: flame(d, cx, cy - 10 * q, 0.35 * q * lit, t)
def bubble(img, d, cx, cy, s, p, label):
    if p <= 0: return
    q = back(p) * s
    d.rounded_rectangle([S(cx - 300 * q), S(cy - 120 * q), S(cx + 300 * q), S(cy + 120 * q)], S(40 * q), fill=WHITE + (255,), outline=INK, width=S(7))
    d.polygon([(S(cx - 120 * q), S(cy + 115 * q)), (S(cx - 170 * q), S(cy + 210 * q)), (S(cx - 40 * q), S(cy + 115 * q))], fill=WHITE + (255,), outline=INK)
    d.line([(S(cx - 118 * q), S(cy + 113 * q)), (S(cx - 42 * q), S(cy + 113 * q))], fill=WHITE + (255,), width=S(10 * q))
    text(img, (cx, cy), label, BF(50 * q), INK)
def h2car(img, d, cx, cy, s, p, t):
    car(d, cx, cy, s, p, 0, (240, 244, 250))
    if p >= 0.5: text(img, (cx - 4 * s, cy - 18 * s), 'H', BF(64 * s), BLUE); text(img, (cx + 30 * s, cy + 2 * s), '2', BF(38 * s), BLUE)
def beaker(img, d, cx, cy, s, p, t):
    # électrolyse : bécher d'eau, deux électrodes reliées à une pile, bulles qui montent
    if p <= 0: return
    q = back(p) * s
    d.rectangle([S(cx - 150 * q), S(cy - 60 * q), S(cx + 150 * q), S(cy + 160 * q)], fill=WATERL + (220,))
    poly(d, [(cx - 150 * q, cy - 140 * q), (cx - 150 * q, cy + 160 * q), (cx + 150 * q, cy + 160 * q), (cx + 150 * q, cy - 140 * q)], INK, 7)
    for ex in (-70, 70):
        d.rectangle([S(cx + (ex - 10) * q), S(cy - 200 * q), S(cx + (ex + 10) * q), S(cy + 110 * q)], fill=(110, 110, 118, 255))
        for k in range(5):
            u = (t * 0.8 + k * 0.2 + (0.1 if ex > 0 else 0)) % 1; circ(d, cx + (ex + 18 * math.sin(k * 2.1)) * q, cy + 100 * q - 160 * q * u, 7 * q, None, WHITE + (int(240 * (1 - u)),))
    poly(d, [(cx - 70 * q, cy - 200 * q), (cx - 70 * q, cy - 260 * q), (cx - 30 * q, cy - 260 * q)], INK, 6); poly(d, [(cx + 70 * q, cy - 200 * q), (cx + 70 * q, cy - 260 * q), (cx + 30 * q, cy - 260 * q)], INK, 6)
    batt(img, d, cx, cy - 270 * q, 60 * q, 90 * q, 1, 0.8)
# ---------- repères temporels
T = dict(gas=tw('gas'), water=tw('water'), starts=tw('starts'), in1980=tw('in'), american=tw('american'), stanley=tw('stanley'), claimed=tw('claimed'),
         los=tw('los'), york=tw('york'), n22=tw('22'), gallons=tw('gallons'), then=tw('then'), y1998=tw('1998'), dinner=tw('dinner'), throat=tw('throat'),
         ran=tw('ran'), collapsed=tw('collapsed'), his=tw('his', 1), brother=tw('brother'), they=tw('they'), poisoned=tw('poisoned'), millions=tw('millions'),
         oil=tw('oil'), silenced=tw('silenced'), but=tw('but'), coroner=tw('coroner'), aneurysm=tw('aneurysm'), and2=tw('and', 2), court=tw('court'),
         fraud=tw('fraud'), because=tw('because'), hydrogen=tw('hydrogen'), burned=tw('burned'), your=tw('your', 2), stop=tw('stop'), feet=tw('feet'),
         would2=tw('would', 1), believed=tw('believed'))
for k, v in T.items():
    if v is None: print('mot introuvable :', k)
SC = [0, T['in1980'] - 0.12, T['then'] - 0.15, T['his'] - 0.15, T['millions'] - 0.15, T['but'] - 0.15, T['and2'] - 0.15, T['because'] - 0.15,
      T['your'] - 0.15, T['would2'] - 0.15, DUR]
SOURCES = [(T['stanley'], T['then'] - 0.3, 'Stanley Meyer, Grove City (Ohio)'), (T['coroner'] - 0.1, T['and2'] - 0.3, 'Coroner, Ohio 1998'),
           (T['court'] - 0.1, T['because'] - 0.3, 'Ohio court ruling, 1996')]
PUNCH = [(T['gas'], 0.05), (T['starts'], 0.06), (T['gallons'], 0.04), (T['poisoned'], 0.07), (T['oil'], 0.05), (T['aneurysm'], 0.06), (T['fraud'], 0.07),
         (T['burned'], 0.05), (T['feet'], 0.05)]
SHAKE = [(T['poisoned'], 10), (T['fraud'], 12)]
CLIPSC = {0: 1, 2: 2, 8: 3}          # scène -> clip IA bonhomme bâton (vid/1..3.mp4)
def camera(t, sc):
    a0, a1 = SC[sc], SC[sc + 1]; z = 1.02 + 0.025 * eio((t - a0) / max(1, a1 - a0))
    if sc in CLIPSC: z = 1.0
    for t0, amp in PUNCH:
        if t0 and 0 <= t - t0 < 0.6: z += amp * math.exp(-(t - t0) * 7) * min(1, (t - t0) / 0.05)
    ox = oy = 0
    for t0, amp in SHAKE:
        if t0 and 0 <= t - t0 < 0.4: k = (1 - (t - t0) / 0.4) ** 2; ox += amp * k * math.sin((t - t0) * 95); oy += amp * k * math.cos((t - t0) * 83)
    return z, 0.5, 0.42, ox, oy
DIM = []
def dimness(t):   # la scène des derniers mots est assombrie
    a = 0.0
    if t >= SC[3] - 0.1: a = 0.45 * since(t, SC[3] - 0.1, 0.4)
    if t >= SC[4] - 0.15: a *= 1 - since(t, SC[4] - 0.15, 0.3)
    return a
def clip_frames(k):
    dd = os.path.join(DIR, 'vid', f'{k}_fr')
    if not os.path.isdir(dd) or not os.listdir(dd):
        os.makedirs(dd, exist_ok=True)
        subprocess.run([FF, '-v', 'error', '-i', os.path.join(DIR, 'vid', f'{k}.mp4'), '-vf', f'fps=30,scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}',
                        '-q:v', '1', os.path.join(dd, '%04d.jpg')], check=True)
    return dd, len(os.listdir(dd))
for _k in (1, 2, 3): clip_frames(_k)
def clip(img, k, t0, t, speed=1.0, start=0.0):
    dd, n = clip_frames(k); fi = max(0, min(n - 1, int((start + (t - t0) * speed) * 30)))
    img.alpha_composite(Image.open(os.path.join(dd, f'{fi + 1:04d}.jpg')).convert('RGBA').resize((W * SS, H * SS), Image.LANCZOS))
def tagbox(img, d, cx, cy, s, size, col, k):
    if k <= 0.01: return
    f = BF(size); w = (f.getbbox(s)[2] - f.getbbox(s)[0]) / SS / 2 + 34; h = size * 0.62 + 18; q = back(k)
    d.rounded_rectangle([S(cx - w * q), S(cy - h), S(cx + w * q), S(cy + h)], S(24), fill=(255, 255, 255, 235), outline=INK, width=S(5))
    text(img, (cx, cy), s, f, col, clamp(k * 2))
# ---------- texture papier + vignette à la taille de sortie
_rs = np.random.RandomState(7); NOISE = np.asarray(Image.fromarray((_rs.normal(128, 9, (H * K, W * K))).clip(0, 255).astype('uint8')).filter(ImageFilter.GaussianBlur(0.8 * K))).astype(np.int16) - 128
yy, xx = np.mgrid[0:H * K, 0:W * K]; VIG = (1 - 0.10 * (((xx - W * K / 2) / (W * K / 2)) ** 2 + ((yy - H * K * 0.45) / (H * K * 0.6)) ** 2)).clip(0.82, 1)[..., None].astype(np.float32); del yy, xx
# ---------- sous-titres
HOTW = re.compile(r'(\d|water|gas|car|meyer|poisoned|oil|coroner|aneurysm|court|fraud|hydrogen|burned|stop|feet|believed)', re.I)
GROUPS = []; cur = []
for k, w in enumerate(WORDS):
    cur.append(k)
    if len(cur) == 3 or re.search(r'[.,:!?–…“]$', w[0]): GROUPS.append(cur); cur = []
if cur: GROUPS.append(cur)
def caption(img, t):
    g = next((g for g in GROUPS if WORDS[g[0]][1] - 0.05 <= t < WORDS[g[-1]][2] + 0.3), None)
    if not g: return
    ws = [WORDS[k][0].strip('.,:!?„“"…').upper() for k in g]; base = 56 * K; cf = F('Poppins-ExtraBold.ttf', base)
    wd = [cf.getbbox(w)[2] for w in ws]; sp = 20 * K; tw_ = sum(wd) + sp * (len(ws) - 1)
    if tw_ > (W - 120) * K: base = int(base * (W - 120) * K / tw_); cf = F('Poppins-ExtraBold.ttf', base); wd = [cf.getbbox(w)[2] for w in ws]; tw_ = sum(wd) + sp * (len(ws) - 1)
    d = ImageDraw.Draw(img); x = W * K / 2 - tw_ / 2; y = 1390 * K
    for w, k, ww in zip(ws, g, wd):
        t0 = WORDS[k][1]
        if t >= t0 - 0.03:
            u = (t - t0) / 0.12; pop = 1 + 0.14 * math.sin(clamp(u) * math.pi) if u < 1 else 1
            f2 = F('Poppins-ExtraBold.ttf', base * pop) if pop != 1 else cf
            d.text((x + ww / 2, y), w, font=f2, fill=YEL if HOTW.search(w) else (255, 255, 255), anchor='mm', stroke_width=6 * K, stroke_fill=(0, 0, 0))
        x += ww + sp
# ---------- les scènes
def sc_(t, k, dt=-0.15, d=0.35): return since(t, T[k] + dt, d) if T[k] else 0
def meyer(img, d, x, y, s, pose, t, **kw): return person(img, d, x, y, s, pose, t, shirt=(150, 110, 70), grey=True, beard=True, **kw)
def scene(img, d, sc, t):
    CX = W / 2; u0 = t - SC[sc]
    if sc == 0:   # CLIP 1 : le plein avec de l'eau, la voiture démarre
        clip(img, 1, SC[0], t, speed=1.35)
        tagbox(img, d, CX, 470, '$0 FOR GAS?', 74, INK, clamp(u0 / 0.3) * (1 - since(t, T['water'] - 0.2, 0.15)))
        if t > T['water'] - 0.2: tagbox(img, d, CX, 470, 'WATER INSTEAD OF GAS!', 66, BLUE, sc_(t, 'water', -0.2, 0.3))
    elif sc == 1:   # Stanley Meyer, USA, années 80 ; Los Angeles → New York avec 22 gallons
        if t < T['los'] - 0.25:
            text(img, (CX, 470), 'Stanley Meyer', BF(84), INK, clamp(u0 / 0.3)); text(img, (CX, 565), 'USA, 1980s', H2(64), RED, sc_(t, 'stanley', 0.2, 0.3))
            buggy(img, d, 700, 1150, 1.15, sc_(t, 'stanley', 0.2, 0.5), t)
            meyer(img, d, 250, 1290, 0.8, lerp_pose('stand', 'point', sc_(t, 'claimed', -0.2, 0.3)), t)
        else:
            k = sc_(t, 'n22', -0.2, 0.3); text(img, (CX + 30, 480), '22 gallons of water', BF(76), BLUE, k, scale=1.3 - 0.3 * k); drop(d, 110, 495, 26 * back(k))
            usa(img, d, CX, 900, 1.45, since(t, T['los'] - 0.25, 0.5), since(t, T['los'] - 0.1, 1.2))
            text(img, (CX, 1210), 'across the USA', H2(60), INK, sc_(t, 'york', 0.2, 0.3))
    elif sc == 2:   # CLIP 2 : le dîner de 1998
        clip(img, 2, SC[2], t, speed=1.2)
        tagbox(img, d, CX, 470, '1998', 90, INK, clamp(u0 / 0.3))
    elif sc == 3:   # ses derniers mots, selon son frère
        meyer(img, d, 750, 1290, 0.8, 'stand', t, rot=-85, eyes=False, mouth='flat')
        text(img, (CX, 520), 'According to his brother:', H2(66), WHITE, clamp(u0 / 0.3))
        if T['they'] and t > T['they'] - 0.1:
            k = sc_(t, 'they', -0.1, 0.3); text(img, (CX, 790), '"They poisoned', BF(84), (255, 90, 80), k, scale=1.3 - 0.3 * k)
            k2 = sc_(t, 'poisoned', 0.2, 0.25); text(img, (CX, 900), 'me."', BF(120), (255, 90, 80), k2, scale=1.5 - 0.5 * k2)
    elif sc == 4:   # la rumeur : les pétroliers
        text(img, (CX, 470), 'Oil companies?', BF(90), RED, sc_(t, 'oil', -0.3, 0.3))
        derrick(d, 190, 930, 1.0, clamp(u0 / 0.4), t)
        for k, x in enumerate((680, 815, 950)): suit(img, d, x, 1010, 0.75, sc_(t, 'oil', -0.2 + 0.12 * k, 0.4), t)
        if T['silenced'] and t > T['silenced'] - 0.2:
            for k in range(3):
                kk = sc_(t, 'silenced', -0.2 + 0.1 * k, 0.3); text(img, (620 + 150 * k, 640 - 30 * math.sin(t * 2 + k)), '?', BF(110), RED, kk, rot=10 * math.sin(t * 2 + k))
    elif sc == 5:   # la vérité : l'autopsie
        k = clamp(u0 / 0.3); text(img, (CX, 470), 'The truth', BF(88), GREEN, k); underline(d, CX - 220, CX + 220, 530, GREEN, ease((u0 - 0.2) / 0.4), 9)
        doc(img, d, CX, 920, 1.0, sc_(t, 'coroner', -0.2, 0.4), 'AUTOPSY', 5)
        stamp(img, CX, 1010, 'ANEURYSM', sc_(t, 'aneurysm', -0.05, 0.25), BLUE, -10, 76)
    elif sc == 6:   # le tribunal : fraude
        doc(img, d, CX, 880, 1.0, clamp(u0 / 0.35), 'RULING 1996', 5)
        stamp(img, CX, 980, 'FRAUD', sc_(t, 'fraud', -0.05, 0.25), RED, -12, 110)
        text(img, (CX, 470), 'A court said:', BF(80), INK, clamp(u0 / 0.3))
    elif sc == 7:   # l'eau = de l'hydrogène déjà brûlé
        text(img, (CX, 470), 'Water =', BF(84), BLUE, clamp(u0 / 0.3))
        molecule(img, d, CX, 860, 1.15, clamp(u0 / 0.4), 0, t)
        text(img, (CX, 1150), 'already burned hydrogen', H2(66), RED, sc_(t, 'burned', -0.3, 0.3))
        if T['burned'] and t > T['burned'] - 0.2: flame(d, CX + 230, 760, 0.35 * (1 - since(t, T['burned'] + 0.4, 0.5)), t)
    elif sc == 8:   # CLIP 3 : la voiture s'arrête après quelques mètres
        clip(img, 3, SC[8], t, speed=2.2, start=0.8)
        tagbox(img, d, CX, 470, 'A FEW FEET… STOP', 66, RED, clamp(u0 / 0.25))
    elif sc == 9:   # question pour les commentaires
        bubble(img, d, CX, 760, 1.15, clamp(u0 / 0.4), "Would you believe it?")
        person(img, d, 800, 1290, 0.8, 'point', t)
        k = clamp((u0 - 0.2) / 0.3); text(img, (360, 1180), 'Tell me in the', H2(60), INK, k); text(img, (360, 1250), 'comments', BF(56), RED, k)
def draw(t):
    sc = max(i for i in range(len(SC) - 1) if t >= SC[i])
    lay = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    scene(lay, d, sc, t)
    for s0, s1, src in SOURCES:
        if s0 <= t < s1: text(lay, (W / 2, 1468), src, H2(36), GREY, min(since(t, s0, 0.3), 1 - since(t, s1 - 0.3, 0.3)))
    tout = clamp((SC[sc + 1] - t) / 0.16) if sc < len(SC) - 2 else 1
    if tout < 1: lay.putalpha(lay.getchannel('A').point(lambda v: int(v * tout)))
    img = Image.new('RGBA', (W * SS, H * SS), BG + (255,))
    dm = dimness(t)
    if dm > 0: img.alpha_composite(Image.new('RGBA', img.size, (24, 20, 18, int(255 * dm * 1.6 if sc == 3 else 255 * dm))))
    img.alpha_composite(lay)
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
    N = int(DUR * SR); mix_ = np.zeros(N); mix_[:len(VOICE)] += VOICE
    def sfx(name, t0, g):
        if t0 is None: return
        w = wave.open(SFXD + name + '.wav'); s = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float) / 32768
        if w.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
        if w.getframerate() != SR: s = np.interp(np.arange(0, len(s), w.getframerate() / SR), np.arange(len(s)), s)
        i0 = int(max(0, t0) * SR); L = min(len(s), N - i0); mix_[i0:i0 + L] += s[:L] * g
    for t0 in SC[1:-1]: sfx('swish', t0 + 0.02, 0.1)
    sfx('pop', T['gas'] - 0.1, 0.12); sfx('shine', T['water'], 0.1); sfx('hit', T['starts'], 0.25); sfx('pop', T['stanley'] + 0.2, 0.12)
    sfx('zoom1', T['los'] - 0.1, 0.15); sfx('ding', T['gallons'], 0.1); sfx('glitch', T['throat'] - 0.1, 0.15); sfx('thud', T['collapsed'], 0.3)
    sfx('hit', T['poisoned'] - 0.1, 0.3); sfx('glitch', T['oil'] - 0.2, 0.12); sfx('ding', T['coroner'], 0.12); sfx('hit', T['aneurysm'] - 0.05, 0.25)
    sfx('hit', T['fraud'] - 0.05, 0.3); sfx('pop', T['hydrogen'], 0.12); sfx('clank', T['stop'] - 0.1, 0.25); sfx('pop', T['would2'], 0.15)
    fd = int(0.5 * SR); mix_[-fd:] *= np.linspace(1, 0, fd); mix_ = mix_ / max(1e-6, np.abs(mix_).max()) * 0.92
    wo = wave.open(f'{TMP}/a.wav', 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((mix_ * 32767).astype('<i2').tobytes()); wo.close()
    enc = subprocess.Popen([FF, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W * K}x{H * K}', '-r', str(FPS), '-i', '-', '-i', f'{TMP}/a.wav',
                            '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-tune', 'animation', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k',
                            '-af', 'pan=stereo|c0=c0|c1=c0', '-shortest', '-movflags', '+faststart', OUT], stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for n, b in enumerate(pool.imap(frame_bytes, range(NF), chunksize=4)):
            enc.stdin.write(b)
            if n % 600 == 0: print('images', n, '/', NF, flush=True)
    enc.stdin.close(); enc.wait(); shutil.rmtree(TMP); print('ok', OUT, round(DUR, 2), f'{W * K}x{H * K}')
