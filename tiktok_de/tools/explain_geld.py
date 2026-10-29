# Vidéo explicative « Warum druckt der Staat nicht einfach mehr Geld? » – la machine à billets chez toi, l'interdit, l'hyperinflation allemande de 1923,
# l'argent comme bon pour des choses réelles, la Rentenmark, l'objectif de 2 % de la BCE. Même moteur que Wasserauto (personnage animé), passage de 1923 en sépia.
# usage : explain_geld.py dossier sortie.mp4  [PREVIEW=t1,t2,...] [K=1 (1080p, défaut) | K=2 (4K)] [TAIL=0.5]
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
# ---------- objets propres à l'épisode « Geld drucken »
EURO = (130, 175, 215); MARKC = (196, 178, 128); RENTEN = (205, 190, 150); BREAD = (206, 150, 80); GOLDC = (240, 190, 60); MONEYG = (110, 170, 90)
def mix(c1, c2, u): return tuple(int(a + (b - a) * clamp(u)) for a, b in zip(c1, c2))
def note(d, cx, cy, s, rot=0.0, col=EURO, alpha=255):
    # billet : fond coloré, cadre intérieur, filigrane rond ; rot en degrés
    a = math.radians(rot)
    def P(x, y): return (cx + (x * math.cos(a) - y * math.sin(a)) * s, cy + (x * math.sin(a) + y * math.cos(a)) * s)
    pts = [P(-80, -40), P(80, -40), P(80, 40), P(-80, 40)]
    d.polygon([(S(x), S(y)) for x, y in pts], fill=col + (alpha,)); poly(d, pts, INK + (alpha,), max(2, 4 * s), 1, closed=True)
    inn = [P(-66, -28), P(66, -28), P(66, 28), P(-66, 28)]; poly(d, inn, mix(col, INK, 0.4) + (alpha,), max(1, 2.5 * s), 1, closed=True)
    wx, wy = P(32, 0); circ(d, wx, wy, 15 * s, mix(col, INK, 0.4) + (alpha,), None, max(1, 2.5 * s))
def big_note(img, d, cx, cy, s, p, label, col=EURO, sub_=''):
    if p <= 0: return
    q = back(p) * s; note(d, cx, cy, q, 0, col)
    fs = min(22, 200 / max(1, len(label)))      # le libellé reste dans le cadre du billet
    text(img, (cx - 12 * q, cy - (6 if sub_ else 0) * q), label, BF(fs * q), INK)
    if sub_: text(img, (cx - 18 * q, cy + 18 * q), sub_, H2(14 * q), INK)
def pile(d, cx, cy, s, n, col=EURO, seed=1):
    # tas de billets en pyramide (n billets), du bas vers le haut
    rs = np.random.RandomState(seed); k = 0; row = 0
    while k < n:
        per = max(1, 6 - row)
        for j in range(per):
            if k >= n: break
            x = cx + (j - (per - 1) / 2) * 70 * s + rs.uniform(-12, 12) * s; y = cy - row * 26 * s + rs.uniform(-5, 5) * s
            note(d, x, y, 0.55 * s, rs.uniform(-18, 18), col); k += 1
        row += 1
def bundle(d, cx, cy, s, col=MARKC):
    # liasse vue de côté : bloc de billets + bande de papier
    d.rounded_rectangle([S(cx - 85 * s), S(cy - 26 * s), S(cx + 85 * s), S(cy + 26 * s)], S(6 * s), fill=col + (255,), outline=INK, width=S(4 * s))
    for k in range(3): line(d, cx - 80 * s, cy - 13 * s + k * 13 * s, cx + 80 * s, cy - 13 * s + k * 13 * s, mix(col, INK, 0.3), 2 * s)
    d.rectangle([S(cx - 16 * s), S(cy - 28 * s), S(cx + 16 * s), S(cy + 28 * s)], fill=(240, 236, 226, 255), outline=INK, width=S(3 * s))
def printer(img, d, cx, cy, s, p, t, rate=0.0, col=(92, 112, 142), ncol=EURO):
    # machine à billets : caisse, rouleaux qui tournent, voyant ; rate = billets par seconde qui sortent à droite
    if p <= 0: return
    q = back(p) * s; P = lambda x, y: (S(cx + x * q), S(cy + y * q))
    d.rounded_rectangle([*P(-170, -130), *P(170, 120)], S(26 * q), fill=col + (255,), outline=INK, width=S(6 * q))
    d.rounded_rectangle([*P(-120, -175), *P(120, -125)], S(10 * q), fill=(236, 232, 222, 255), outline=INK, width=S(5 * q))   # bac à papier
    for k in range(4): line(d, cx + (-100 + k * 20) * q, cy - 168 * q, cx + (100 - k * 20) * q, cy - 168 * q + 1, (200, 196, 186), 3 * q)
    for rx in (-80, 10):
        circ(d, cx + rx * q, cy - 10 * q, 46 * q, INK, (200, 204, 212, 255), 5 * q)
        for j in range(3):
            a = t * (6 if rate > 0 else 0.5) + j * 2.094; line(d, cx + rx * q, cy - 10 * q, cx + (rx + 40 * math.cos(a)) * q, cy + (-10 + 40 * math.sin(a)) * q, INK, 5 * q)
    d.rounded_rectangle([*P(100, 40), *P(178, 64)], S(6 * q), fill=(40, 40, 46, 255))   # fente de sortie
    on = rate > 0 and (t * 4) % 1 < 0.5; circ(d, cx + 120 * q, cy - 80 * q, 14 * q, INK, ((80, 220, 100) if on else (90, 120, 95)) + (255,), 4 * q)
    if rate > 0:
        n = max(1, int(rate * 1.2))
        for k in range(n):
            u = (t * rate / n + k / n) % 1; x = cx + (185 + 190 * u) * q; y = cy + (52 + 230 * u * u) * q
            note(d, x, y, 0.62 * q, 25 * u + 8 * math.sin(t * 5 + k), ncol)
def bars(d, x0, y0, x1, y1, p):
    # barreaux de prison qui tombent d'en haut
    if p <= 0: return
    ye = y0 + (y1 - y0) * ease(p)
    for k in range(int((x1 - x0) / 72) + 1):
        x = x0 + k * 72; line(d, x, y0, x, ye, (70, 70, 78), 16); line(d, x - 4, y0, x - 4, ye, (130, 130, 140), 3)
    line(d, x0 - 10, y0, x1 + 10, y0, (60, 60, 66), 22)
    if p >= 1: line(d, x0 - 10, y0 + (y1 - y0) * 0.45, x1 + 10, y0 + (y1 - y0) * 0.45, (60, 60, 66), 18); line(d, x0 - 10, y1, x1 + 10, y1, (60, 60, 66), 22)
def bank(img, d, cx, cy, s, p, label, col=(232, 226, 212)):
    # bâtiment à colonnes (l'État / la banque)
    if p <= 0: return
    q = back(p) * s; P = lambda x, y: (S(cx + x * q), S(cy + y * q))
    d.polygon([P(-300, -170), P(0, -300), P(300, -170)], fill=col + (255,), outline=INK); poly(d, [(cx - 300 * q, cy - 170 * q), (cx, cy - 300 * q), (cx + 300 * q, cy - 170 * q)], INK, 6 * q, 1, closed=True)
    d.rectangle([*P(-290, -170), *P(290, -140)], fill=col + (255,), outline=INK, width=S(5 * q))
    for k in range(5):
        x = -230 + k * 115; d.rectangle([*P(x - 26, -140), *P(x + 26, 130)], fill=(246, 242, 232, 255), outline=INK, width=S(4 * q))
    d.rectangle([*P(-320, 130), *P(320, 165)], fill=col + (255,), outline=INK, width=S(5 * q)); d.rectangle([*P(-345, 165), *P(345, 200)], fill=col + (255,), outline=INK, width=S(5 * q))
    text(img, (cx, cy - 205 * q), label, BF(46 * q), INK)
def bread(d, cx, cy, s, p=1.0):
    if p <= 0: return
    q = back(p) * s
    d.ellipse([S(cx - 120 * q), S(cy - 62 * q), S(cx + 120 * q), S(cy + 62 * q)], fill=BREAD + (255,), outline=INK, width=S(6 * q))
    d.chord([S(cx - 120 * q), S(cy - 62 * q), S(cx + 120 * q), S(cy + 62 * q)], 200, 340, fill=mix(BREAD, (240, 190, 120), 0.6) + (255,))
    for k in (-1, 0, 1): line(d, cx + (k * 55 - 22) * q, cy - 22 * q, cx + (k * 55 + 22) * q, cy - 2 * q, (150, 95, 45), 6 * q)
def shoe(d, cx, cy, s, p=1.0, col=(120, 74, 44)):
    if p <= 0: return
    q = back(p) * s; P = lambda x, y: (S(cx + x * q), S(cy + y * q))
    d.polygon([P(-90, 30), P(-90, -50), P(-30, -50), P(-20, -10), P(70, 0), P(100, 30)], fill=col + (255,), outline=INK)
    d.rectangle([*P(-95, 30), *P(105, 44)], fill=(50, 40, 34, 255))
def shelf(d, x0, x1, y, p):
    if p <= 0: return
    xe = x0 + (x1 - x0) * ease(p); d.rectangle([S(x0), S(y), S(xe), S(y + 26)], fill=(160, 112, 70, 255), outline=INK, width=S(4))
def chart(d, x0, y0, w, h, p, col=RED):
    # courbe des prix qui s'envole (exponentielle) + axes
    if p <= 0: return
    line(d, x0, y0, x0, y0 + h, INK, 7); line(d, x0, y0 + h, x0 + w, y0 + h, INK, 7)
    pts = [(x0 + w * u, y0 + h - h * (math.exp(5 * u) - 1) / (math.exp(5) - 1)) for u in np.linspace(0, 1, 40)]
    poly(d, pts, col, 11, p)
    if p >= 0.98: arrow(d, *pts[-3], pts[-1][0], pts[-1][1] - 40, col, 11, 1, 40)
def shop(img, d, cx, cy, s, p):
    # petit magasin : vitrine, auvent rayé
    if p <= 0: return
    q = back(p) * s; P = lambda x, y: (S(cx + x * q), S(cy + y * q))
    d.rectangle([*P(-170, -150), *P(170, 230)], fill=(236, 226, 206, 255), outline=INK, width=S(6 * q))
    for k in range(6): d.polygon([P(-190 + k * 63, -150), P(-127 + k * 63, -150), P(-127 + k * 63, -90), P(-190 + k * 63, -90)], fill=((200, 60, 50) if k % 2 == 0 else (246, 242, 232)) + (255,), outline=INK)
    d.rectangle([*P(-130, -50), *P(130, 90)], fill=(205, 225, 240, 255), outline=INK, width=S(5 * q)); bread(d, cx - 40 * q, cy + 40 * q, 0.42 * q)
    d.rectangle([*P(-40, 110), *P(40, 230)], fill=(140, 96, 60, 255), outline=INK, width=S(4 * q))
    text(img, (cx, cy - 190 * q), 'BÄCKER', BF(40 * q), INK)
def barrow(d, cx, cy, s, p, t, n=14):
    # brouette pleine de billets (vue de côté) ; (cx, cy) = sol sous la roue
    if p <= 0: return
    q = back(p) * s; r = 46 * q; wx, wy = cx + 150 * q, cy - r
    pile(d, cx, cy - 165 * q, 1.0 * q, n, MARKC, 4)
    d.polygon([(S(cx - 170 * q), S(cy - 170 * q)), (S(cx + 170 * q), S(cy - 170 * q)), (S(cx + 120 * q), S(cy - 80 * q)), (S(cx - 120 * q), S(cy - 80 * q))], fill=(90, 120, 90, 255), outline=INK)
    line(d, cx - 120 * q, cy - 80 * q, cx - 280 * q, cy - 160 * q, INK, 10 * q); line(d, cx - 90 * q, cy - 80 * q, cx - 100 * q, cy, INK, 9 * q)
    line(d, cx + 100 * q, cy - 90 * q, wx, wy, INK, 9 * q); circ(d, wx, wy, r, INK, (60, 60, 66, 255), 6 * q)
    for j in range(4): a = -t * 6 + j * math.pi / 2; line(d, wx, wy, wx + r * 0.8 * math.cos(a), wy + r * 0.8 * math.sin(a), (170, 170, 176), 4 * q)
def stove(d, cx, cy, s, p, t, fire=0.0):
    # poêle en fonte : corps, porte vitrée avec flammes, tuyau
    if p <= 0: return
    q = back(p) * s; P = lambda x, y: (S(cx + x * q), S(cy + y * q))
    d.rectangle([*P(-25, -420), *P(25, -200)], fill=(60, 60, 66, 255), outline=INK, width=S(4 * q))
    d.rounded_rectangle([*P(-150, -210), *P(150, 170)], S(20 * q), fill=(52, 52, 58, 255), outline=INK, width=S(6 * q))
    d.rounded_rectangle([*P(-100, -120), *P(100, 70)], S(14 * q), fill=(30, 22, 18, 255), outline=(120, 120, 128), width=S(6 * q))
    if fire > 0: flame(d, cx, cy + 60 * q, 0.55 * q * fire, t)
    for x in (-110, 110): d.rectangle([*P(x - 14, 170), *P(x + 14, 210)], fill=(40, 40, 46, 255))
def log_(d, cx, cy, s):
    d.rounded_rectangle([S(cx - 130 * s), S(cy - 34 * s), S(cx + 130 * s), S(cy + 34 * s)], S(30 * s), fill=(150, 100, 60, 255), outline=INK, width=S(5 * s))
    circ(d, cx + 112 * s, cy, 32 * s, INK, (220, 180, 120, 255), 4 * s); arc(d, cx + 112 * s, cy, 16 * s, 0, 360, (160, 110, 60), 3 * s)
def piggy(img, d, cx, cy, s, p, crack=0.0):
    # tirelire cochon ; crack = fêlures puis le cochon se vide
    if p <= 0: return
    q = back(p) * s; PK = (240, 160, 170); j = 4 * crack * math.sin(t_glob[0] * 50) if 0 < crack < 1 else 0
    for x in (-70, 60): d.rounded_rectangle([S(cx + (x - 18) * q + j), S(cy + 60 * q), S(cx + (x + 18) * q + j), S(cy + 120 * q)], S(8 * q), fill=PK + (255,), outline=INK, width=S(4 * q))
    d.ellipse([S(cx - 150 * q + j), S(cy - 100 * q), S(cx + 150 * q + j), S(cy + 100 * q)], fill=PK + (255,), outline=INK, width=S(6 * q))
    d.polygon([(S(cx - 80 * q + j), S(cy - 80 * q)), (S(cx - 50 * q + j), S(cy - 140 * q)), (S(cx - 20 * q + j), S(cy - 90 * q))], fill=PK + (255,), outline=INK)
    d.ellipse([S(cx + 120 * q + j), S(cy - 30 * q), S(cx + 180 * q + j), S(cy + 30 * q)], fill=(230, 140, 150, 255), outline=INK, width=S(4 * q))
    for y in (-8, 8): circ(d, cx + 150 * q + j, cy + y * q, 5 * q, None, INK + (255,))
    circ(d, cx + 70 * q + j, cy - 30 * q, 8 * q, None, INK + (255,)); d.rectangle([S(cx - 30 * q + j), S(cy - 96 * q), S(cx + 30 * q + j), S(cy - 86 * q)], fill=INK + (255,))
    if crack > 0:
        for k in range(4):
            a = -0.5 + k * 0.7; pts = [(cx + j + (20 + 25 * m) * q * math.cos(a + 0.2 * (m % 2)), cy + (20 + 25 * m) * q * math.sin(a + 0.2 * (m % 2))) for m in range(5)]
            poly(d, pts, INK, 5 * q, crack)
t_glob = [0.0]
def moneybag(img, d, cx, cy, s):
    d.ellipse([S(cx - 70 * s), S(cy - 60 * s), S(cx + 70 * s), S(cy + 80 * s)], fill=(214, 180, 110, 255), outline=INK, width=S(5 * s))
    d.polygon([(S(cx - 30 * s), S(cy - 55 * s)), (S(cx - 45 * s), S(cy - 100 * s)), (S(cx + 45 * s), S(cy - 100 * s)), (S(cx + 30 * s), S(cy - 55 * s))], fill=(214, 180, 110, 255), outline=INK)
    line(d, cx - 34 * s, cy - 58 * s, cx + 34 * s, cy - 58 * s, INK, 6 * s); text(img, (cx, cy + 14 * s), '€', BF(70 * s), INK)
def star5(d, cx, cy, r, col):
    pts = [(cx + (r if k % 2 == 0 else r * 0.42) * math.cos(-math.pi / 2 + k * math.pi / 5), cy + (r if k % 2 == 0 else r * 0.42) * math.sin(-math.pi / 2 + k * math.pi / 5)) for k in range(10)]
    d.polygon([(S(x), S(y)) for x, y in pts], fill=col + (255,))
def eu_stars(img, d, cx, cy, r, p, t):
    # cercle de 12 étoiles autour d'un grand €
    if p <= 0: return
    q = back(p); circ(d, cx, cy, r * 1.25 * q, INK, (40, 70, 160, 255), 7)
    for k in range(12):
        a = -math.pi / 2 + k * math.pi / 6 + 0.15 * math.sin(t); kk = clamp(p * 12 - k * 0.6)
        if kk > 0: star5(d, cx + r * q * math.cos(a), cy + r * q * math.sin(a), 22 * q * back(kk), (255, 210, 40))
    text(img, (cx, cy + 6), '€', BF(170 * q), WHITE)
def gauge(img, d, cx, cy, r, p, val, label):
    # cadran en demi-cercle de 0 à 10 % ; zone verte autour de 2 %
    if p <= 0: return
    q = ease(p); arc(d, cx, cy, r, 180, 180 + 180 * q, INK, 14)
    if p < 1: return
    arc(d, cx, cy, r - 2, 180 + 180 * 0.1, 180 + 180 * 0.3, GREEN, 18); arc(d, cx, cy, r - 2, 180 + 180 * 0.55, 360, RED, 18)
    for k in range(6): a = math.pi + k * math.pi / 5; line(d, cx + (r - 30) * math.cos(a), cy + (r - 30) * math.sin(a), cx + (r - 12) * math.cos(a), cy + (r - 12) * math.sin(a), INK, 5)
    a = math.pi + math.pi * clamp(val / 10); line(d, cx, cy, cx + (r - 40) * math.cos(a), cy + (r - 40) * math.sin(a), INK, 10); circ(d, cx, cy, 18, INK, INK + (255,), 3)
    text(img, (cx, cy + 70), label, BF(58), GREEN)
def doc(img, d, cx, cy, s, p, title, lines):
    if p <= 0: return
    q = back(p) * s
    d.rounded_rectangle([S(cx - 190 * q), S(cy - 240 * q), S(cx + 190 * q), S(cy + 240 * q)], S(12 * q), fill=WHITE + (255,), outline=INK, width=S(6))
    text(img, (cx, cy - 180 * q), title, BF(44 * q), INK)
    for k in range(lines): line(d, cx - 140 * q, cy - 100 * q + k * 50 * q, cx + (140 - 60 * (k % 2)) * q, cy - 100 * q + k * 50 * q, (190, 184, 174), 8)
def flash(img, alpha):
    if alpha <= 0.01: return
    img.alpha_composite(Image.new('RGBA', img.size, (255, 255, 255, int(255 * alpha))))
def bubble(img, d, cx, cy, s, p, label):
    if p <= 0: return
    q = back(p) * s
    d.rounded_rectangle([S(cx - 330 * q), S(cy - 120 * q), S(cx + 330 * q), S(cy + 120 * q)], S(40 * q), fill=WHITE + (255,), outline=INK, width=S(7))
    d.polygon([(S(cx + 60 * q), S(cy + 115 * q)), (S(cx + 150 * q), S(cy + 210 * q)), (S(cx + 150 * q), S(cy + 115 * q))], fill=WHITE + (255,), outline=INK)
    d.line([(S(cx + 62 * q), S(cy + 113 * q)), (S(cx + 148 * q), S(cy + 113 * q))], fill=WHITE + (255,), width=S(10 * q))
    text(img, (cx, cy), label, BF(48 * q), INK)
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
def rain(d, x0, x1, y0, y1, t, p, col=EURO, n=12):
    if p <= 0: return
    for k in range(n):
        u = (t * 0.45 + k / n) % 1; x = x0 + (k * 97 % max(1, int(x1 - x0))) + 30 * math.sin(t * 2 + k)
        note(d, x, y0 + (y1 - y0) * u, 0.7, 35 * math.sin(t * 3 + k), col, int(255 * p))
def big_num(v):
    return f'{int(v):,}'.replace(',', '.')
# ---------- repères temporels
T = dict(maschine=tw('maschine'), druckt=tw('druckt'), handy=tw('handy'), druckst=tw('druckst'), n1000=tw('1000'), euro=tw('euro'), nur=tw('nur'),
         verboten=tw('verboten'), faelscht=tw('fälscht'), gefaengnis=tw('gefängnis'), aber=tw('aber'), staat=tw('staat'), drucken=tw('drucken'),
         warum=tw('warum'), reich=tw('reich'), de1=tw('deutschland', 1), ausprobiert=tw('ausprobiert'), y1923=tw('1923'), schulden=tw('schulden'),
         also=tw('also'), druckmaschinen=tw('druckmaschinen'), tag=tw('tag'), nacht=tw('nacht'), hundert=tw('hundert'), druckereien=tw('druckereien'),
         am=tw('am'), anfang=tw('anfang'), gut=tw('gut'), aber1=tw('aber', 1), passiert=tw('passiert'), laeden=tw('läden'), brot=tw('brot'), schuhe=tw('schuhe'),
         papier=tw('papier'), also1=tw('also', 1), steigen=tw('steigen'), preise=tw('preise'), november=tw('november'), kostet=tw('kostet'), n200=tw('200'),
         milliarden=tw('milliarden'), arbeiter=tw('arbeiter'), zweimal=tw('zweimal'), bezahlt=tw('bezahlt'), rennen=tw('rennen'), pause=tw('pause'),
         lohn=tw('lohn'), weniger=tw('weniger'), leute=tw('leute'), schubkarren=tw('schubkarren'), kinder=tw('kinder'), tuerme=tw('türme'), manche=tw('manche'),
         ofen=tw('ofen'), holz=tw('holz'), wer1=tw('wer', 1), gespart=tw('gespart'), verliert=tw('verliert'), alles=tw('alles'), denn=tw('denn'),
         gutschein=tw('gutschein'), dinge=tw('dinge'), wenn=tw('wenn'), verdoppelt=tw('verdoppelt'), brot2=tw('brot', 2), preis=tw('preis'), wenn1=tw('wenn', 1),
         niemand=tw('niemand'), am2=tw('am', 2), ende=tw('ende'), rentenmark=tw('rentenmark'), billion=tw('billion'), deshalb=tw('deshalb'),
         zentralbank=tw('zentralbank'), zwei=tw('zwei'), prozent=tw('prozent'), deine=tw('deine'), jeder=tw('jeder'), wertlos=tw('wertlos'), y1923b=tw('1923', 2),
         was=tw('was'), kaufen=tw('kaufen'), kommentare=tw('kommentare'))
for k, v in T.items():
    if v is None: print('mot introuvable :', k)
SC = [0, T['nur'] - 0.15, T['aber'] - 0.15, T['de1'] - 0.15, T['y1923'] - 0.15, T['also'] - 0.15, T['am'] - 0.15, T['laeden'] - 0.4, T['also1'] - 0.15,
      T['arbeiter'] - 0.15, T['leute'] - 0.3, T['kinder'] - 0.15, T['wer1'] - 0.3, T['denn'] - 0.15, T['wenn'] - 0.15, T['wenn1'] - 0.15, T['am2'] - 0.15,
      T['deshalb'] - 0.35, T['deine'] - 0.3, T['was'] - 0.15, DUR]
OLD = (4, 12)   # scènes de 1923 : image sépia
SOURCES = [(T['faelscht'], T['aber'] - 0.3, '§ 146 Strafgesetzbuch (Geldfälschung)'), (T['november'], T['arbeiter'] - 0.3, 'Brotpreis in Berlin, November 1923'),
           (T['rentenmark'] - 0.2, T['deshalb'] - 0.4, 'Rentenmark, eingeführt am 15. November 1923'), (T['zentralbank'], T['deine'] - 0.4, 'Inflationsziel der EZB: 2 %')]
PUNCH = [(T['druckt'], 0.04), (T['n1000'], 0.05), (T['verboten'], 0.07), (T['gefaengnis'], 0.06), (T['reich'], 0.05), (T['y1923'], 0.06), (T['hundert'], 0.05),
         (T['aber1'], 0.05), (T['papier'], 0.05), (T['milliarden'], 0.07), (T['schubkarren'], 0.04), (T['alles'], 0.06), (T['verdoppelt'], 0.04), (T['niemand'], 0.06),
         (T['billion'], 0.06), (T['wertlos'], 0.06)]
SHAKE = [(T['verboten'], 12), (T['gefaengnis'], 14), (T['milliarden'], 10), (T['alles'], 12), (T['wertlos'], 10)]
def camera(t, sc):
    a0, a1 = SC[sc], SC[sc + 1]; z = 1.02 + 0.025 * eio((t - a0) / max(1, a1 - a0))
    for t0, amp in PUNCH:
        if t0 and 0 <= t - t0 < 0.6: z += amp * math.exp(-(t - t0) * 7) * min(1, (t - t0) / 0.05)
    ox = oy = 0
    for t0, amp in SHAKE:
        if t0 and 0 <= t - t0 < 0.4: k = (1 - (t - t0) / 0.4) ** 2; ox += amp * k * math.sin((t - t0) * 95); oy += amp * k * math.cos((t - t0) * 83)
    return z, 0.5, 0.42, ox, oy
def dimness(t):
    a = 0.0
    if T['aber1'] and t >= T['aber1'] - 0.1: a = 0.28 * since(t, T['aber1'] - 0.1, 0.4) * (1 - since(t, SC[7] - 0.15, 0.3))
    return a
def sepia(t):
    a0, a1 = SC[OLD[0]], SC[OLD[1] + 1]
    return clamp((t - a0 + 0.1) / 0.3) * (1 - clamp((t - a1 + 0.1) / 0.3))
# ---------- texture papier + vignette à la taille de sortie
_rs = np.random.RandomState(7); NOISE = np.asarray(Image.fromarray((_rs.normal(128, 9, (H * K, W * K))).clip(0, 255).astype('uint8')).filter(ImageFilter.GaussianBlur(0.8 * K))).astype(np.int16) - 128
yy, xx = np.mgrid[0:H * K, 0:W * K]; VIG = (1 - 0.10 * (((xx - W * K / 2) / (W * K / 2)) ** 2 + ((yy - H * K * 0.45) / (H * K * 0.6)) ** 2)).clip(0.82, 1)[..., None].astype(np.float32); del yy, xx
# ---------- sous-titres
HOTW = re.compile(r'(\d|geld|maschine|verboten|gefängnis|staat|reich|druck|brot|papier|preis|milliarden|schubkarren|ofen|holz|alles|gutschein|verdoppel|niemand|rentenmark|billion|zentralbank|prozent|wertlos|kommentare)', re.I)
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
def after(t, k, dt=-0.15): return T[k] is not None and t > T[k] + dt
OLDSHIRT = (120, 104, 88)
def scene(img, d, sc, t):
    CX = W / 2; u0 = t - SC[sc]; t_glob[0] = t
    if sc == 0:   # toi, chez toi, avec une machine à billets ; le nouveau téléphone ; 1000 € imprimés
        text(img, (CX, 470), 'Deine eigene Geldmaschine', BF(68), INK, clamp(u0 / 0.3))
        rate = 0 if t < T['druckt'] - 0.1 else (1.5 if t < T['druckst'] - 0.1 else 4.0)
        printer(img, d, 330, 960, 1.05, sc_(t, 'maschine', -0.3, 0.4), t, rate)
        if after(t, 'druckst', 0.1): pile(d, 420, 1250, 1.0, int(min(16, (t - T['druckst']) * 9)), EURO, 2)
        pose = 'stand' if t < T['handy'] - 0.1 else ('hold' if t < T['euro'] - 0.1 else 'cheer')
        person(img, d, 830, 1290, 0.8, pose, t, mouth='o' if t < T['euro'] else 'smile', bob=-6 * abs(math.sin(t * 6)) if pose == 'cheer' else 0)
        if after(t, 'handy', -0.15) and t < T['euro']: phone(img, d, 930, 830, 0.42, sc_(t, 'handy', -0.15, 0.3), 1.0, t)
        if after(t, 'n1000', -0.1):
            k = sc_(t, 'n1000', -0.1, 0.25); text(img, (330, 650), '1000 €', BF(110), GREEN, k, scale=1.4 - 0.4 * k)
    elif sc == 1:   # interdit : fausse monnaie = au moins un an de prison
        printer(img, d, 330, 960, 1.05, 1, t, 0); pile(d, 420, 1250, 1.0, 16, EURO, 2)
        stamp(img, 330, 900, 'VERBOTEN', sc_(t, 'verboten', -0.1, 0.25), RED, -12, 84)
        jail = sc_(t, 'gefaengnis', -0.15, 0.3)
        person(img, d, 830, 1290, 0.8, 'shock' if t > T['verboten'] else 'cheer', t, mouth='o')
        bars(d, 650, 760, 1010, 1300, jail)
        if after(t, 'faelscht', -0.2): text(img, (CX, 470), 'Geld fälschen = Straftat', BF(66), RED, sc_(t, 'faelscht', -0.2, 0.3))
        if after(t, 'gefaengnis', -0.6): k = sc_(t, 'gefaengnis', -0.6, 0.3); text(img, (CX, 570), 'mindestens 1 Jahr Gefängnis', H2(62), INK, k)
    elif sc == 2:   # mais l'État a le droit d'imprimer : pourquoi pas assez pour que tout le monde soit riche ?
        text(img, (CX, 470), 'Der Staat darf drucken', BF(72), BLUE, clamp(u0 / 0.3) * (1 - sc_(t, 'warum', -0.2, 0.2)))
        bank(img, d, CX, 860, 0.8, clamp(u0 / 0.4), 'STAAT')
        if after(t, 'drucken', -0.1): rain(d, 80, 1000, 540, 1300, t, sc_(t, 'drucken', -0.1, 0.4), EURO, 14)
        if after(t, 'warum', -0.2):
            k = sc_(t, 'warum', -0.2, 0.3); text(img, (CX, 470), 'Warum nicht für alle?', BF(70), RED, k, scale=1.3 - 0.3 * k)
        if after(t, 'reich', -0.3):
            for j, x in enumerate((230, 540, 850)):
                kk = sc_(t, 'reich', -0.3 + 0.08 * j, 0.3)
                if kk > 0: person(img, d, x, 1290, 0.5, 'cheer', t + j, shirt=(BLUE, GREEN, RED)[j], bob=-5 * abs(math.sin(t * 6 + j)), alpha=kk)
    elif sc == 3:   # l'Allemagne l'a déjà essayé
        text(img, (CX, 470), 'Deutschland hat es', BF(70), INK, clamp(u0 / 0.3)); text(img, (CX, 560), 'schon ausprobiert …', H2(70), RED, sc_(t, 'ausprobiert', -0.4, 0.3))
        flag(d, CX, 900, 560, 340, clamp(u0 / 0.4), t)
    elif sc == 4:   # 1923 : d'énormes dettes
        k = clamp(u0 / 0.3); text(img, (CX, 520), '1923', BF(170), INK, k, scale=1.4 - 0.4 * k)
        doc(img, d, CX, 1000, 0.85, clamp((u0 - 0.5) / 0.4), 'SCHULDEN', 5)
        stamp(img, CX, 1060, 'RIESIG', sc_(t, 'schulden', 0.0, 0.25), RED, -10, 80)
    elif sc == 5:   # les presses tournent jour et nuit ; plus de 100 imprimeries
        first = 1 - sc_(t, 'hundert', -0.3, 0.25)
        def presses(lay, dl):
            text(lay, (CX, 470), 'Die Druckmaschinen laufen', BF(62), INK, clamp(u0 / 0.3))
            printer(lay, dl, 280, 1000, 0.8, clamp(u0 / 0.35), t, 5.0, (110, 100, 90), MARKC); printer(lay, dl, 720, 1000, 0.8, clamp((u0 - 0.15) / 0.35), t, 5.0, (110, 100, 90), MARKC)
            if after(t, 'tag', -0.15): sun(dl, 170, 690, 50, t, sc_(t, 'tag', -0.15, 0.3) * (1 - sc_(t, 'nacht', -0.1, 0.2)))
            if after(t, 'nacht', -0.1): moon(dl, 910, 690, 52, sc_(t, 'nacht', -0.1, 0.3))
            if after(t, 'tag', -0.15): text(lay, (CX, 690), 'Tag und Nacht', H2(64), RED, sc_(t, 'tag', -0.15, 0.3))
        sub(img, first, presses)
        if after(t, 'hundert', -0.3):
            k0 = sc_(t, 'hundert', -0.3, 0.3); n = int(clamp((t - T['hundert'] + 0.3) / 1.0) * 100)
            text(img, (CX, 470), f'{max(1, n)}{"+" if n >= 100 else ""} Druckereien', BF(80), RED, k0)
            for j in range(15):
                kk = sc_(t, 'hundert', -0.3 + 0.06 * j, 0.3); x = 180 + (j % 5) * 180; y = 780 + (j // 5) * 190
                if kk > 0: factory(img, d, x, y, 0.36, kk, t + j); note(d, x + 60, y - 70 - 25 * ((t * 1.5 + j * 0.3) % 1), 0.35, 10 * math.sin(t * 3 + j), MARKC)
    elif sc == 6:   # au début, c'est bien… mais ensuite
        bad = after(t, 'aber1', -0.1)
        rain(d, 80, 1000, 560, 1300, t, 1 - sc_(t, 'aber1', -0.1, 0.4), MARKC, 12)
        person(img, d, CX, 1290, 0.85, 'shock' if bad else 'cheer', t, shirt=OLDSHIRT, mouth='o' if bad else 'smile', bob=0 if bad else -6 * abs(math.sin(t * 6)))
        text(img, (CX, 470), 'Am Anfang: super!', BF(76), GREEN, clamp(u0 / 0.3) * (1 - sc_(t, 'aber1', -0.2, 0.2)))
        if bad: k = sc_(t, 'aber1', -0.1, 0.3); text(img, (CX, 470), 'Aber dann …', BF(86), RED, k, scale=1.3 - 0.3 * k)
    elif sc == 7:   # autant de pain et de chaussures… seulement plus de papier
        text(img, (CX, 470), 'Gleich viel Brot und Schuhe', BF(62), INK, clamp(u0 / 0.3))
        shelf(d, 80, 1000, 1080, clamp(u0 / 0.4))
        bread(d, 230, 1020, 0.9, sc_(t, 'brot', -0.2, 0.3)); shoe(d, 480, 1040, 0.85, sc_(t, 'schuhe', -0.2, 0.3))
        if after(t, 'papier', -0.7):
            pile(d, 800, 1050, 1.15, int(min(21, (t - T['papier'] + 0.7) * 14)), MARKC, 3)
            text(img, (CX, 570), '… aber viel mehr Papier', H2(66), RED, sc_(t, 'papier', -0.3, 0.3))
    elif sc == 8:   # les prix s'envolent ; novembre 1923 : un pain = 200 milliards de marks
        if t < T['november'] - 0.15:
            text(img, (CX, 470), 'Die Preise steigen', BF(76), RED, clamp(u0 / 0.3)); chart(d, 200, 640, 680, 600, sc_(t, 'steigen', -0.2, 0.9))
            text(img, (330, 700), 'Preis', H2(60), INK, sc_(t, 'preise', -0.2, 0.3))
        else:
            k = sc_(t, 'november', -0.15, 0.3); text(img, (CX, 470), 'November 1923', BF(76), INK, k)
            bread(d, CX, 820, 1.6, k)
            if after(t, 'kostet', -0.1):
                u = clamp((t - T['kostet']) / max(0.3, T['milliarden'] + 0.3 - T['kostet'])); v = 10 ** (11.301 * eio(u))
                text(img, (CX, 1090), big_num(min(v, 2e11)) if u < 1 else '200.000.000.000', BF(74), RED); text(img, (CX, 1190), 'Mark', BF(60), INK, sc_(t, 'kostet', 0, 0.3))
    elif sc == 9:   # payés deux fois par jour ; on court acheter avant que l'argent perde encore de la valeur
        clock(d, 200, 720, 100, t, 9, clamp(u0 / 0.4))
        text(img, (CX + 90, 470), '2x am Tag Lohn', BF(74), INK, sc_(t, 'zweimal', -0.2, 0.3))
        shop(img, d, 860, 1060, 0.75, sc_(t, 'rennen', -0.4, 0.4))
        tr = T['rennen']
        if t < tr - 0.1: x, pose = 330, 'hold'
        else: u = clamp((t - tr + 0.1) / 1.6); x, pose = 330 + 360 * eio(u), (run_pose(t, 11) if u < 1 else 'stand')
        person(img, d, x, 1290, 0.75, pose, t, shirt=OLDSHIRT, mouth='o' if t > tr else 'smile')
        if after(t, 'bezahlt', -0.2) and t < tr: note(d, x + 70, 1040 - 10 * math.sin(t * 5), 0.7, -10, MARKC); note(d, x + 90, 1010 - 10 * math.sin(t * 5 + 1), 0.7, 8, MARKC)
        if after(t, 'weniger', -0.3): text(img, (CX, 1250), 'bevor das Geld noch weniger wert ist', H2(54), RED, sc_(t, 'weniger', -0.3, 0.3))
    elif sc == 10:   # l'argent en brouette
        text(img, (CX, 470), 'Geld in der Schubkarre', BF(70), INK, clamp(u0 / 0.3))
        u = clamp(u0 / (SC[11] - SC[10])); x = 300 + 260 * u
        line(d, 0, 1300, W, 1300, (150, 130, 100), 6)
        barrow(d, x + 140, 1300, 1.25, clamp(u0 / 0.35), t, 16)
        person(img, d, x - 220, 1295, 0.75, dict(lu=-12, ll=-6, ru=70, rl=85, lt=18 * math.sin(t * 7), ls=-6, rt=-18 * math.sin(t * 7), rs=-6), t, shirt=OLDSHIRT, rot=8)
    elif sc == 11:   # des tours de billets ; on chauffe le poêle avec l'argent, moins cher que le bois
        cut = T['manche'] - 0.2
        if t < cut:
            text(img, (CX, 470), 'Türme aus Geldscheinen', BF(66), INK, clamp(u0 / 0.3))
            n = int(clamp(u0 / 1.4) * 11) + 1
            for j in range(n): bundle(d, 640 + 6 * math.sin(j * 1.7), 1270 - j * 56, 1.1)
            person(img, d, 330, 1290, 0.55, 'cheer', t, shirt=(200, 120, 60), bob=-5 * abs(math.sin(t * 6)))
        else:
            k = since(t, cut, 0.3); text(img, (CX, 470), 'Heizen mit Geld', BF(80), RED, k)
            stove(d, 380, 1100, 0.95, k, t, fire=sc_(t, 'ofen', -0.2, 0.4))
            u = ((t - cut) * 1.3) % 1
            if t > T['ofen'] - 0.3: note(d, 640 - 200 * u, 900 + 120 * u, 0.7, -30 * u, MARKC, int(255 * (1 - u)))
            person(img, d, 700, 1290, 0.75, 'point', t, shirt=OLDSHIRT)
            if after(t, 'holz', -0.4):
                kk = sc_(t, 'holz', -0.4, 0.3); log_(d, 820, 760, 0.9 * back(kk)); cross(d, 820, 760, 110, sc_(t, 'holz', -0.1, 0.3), RED, 12)
                text(img, (CX, 560), 'billiger als Holz', H2(64), INK, kk)
    elif sc == 12:   # toute une vie d'économies : perdue
        text(img, (CX, 470), 'Ein Leben lang gespart', BF(70), INK, clamp(u0 / 0.3))
        cr = sc_(t, 'verliert', -0.1, 0.5)
        piggy(img, d, 700, 1040, 1.25, clamp(u0 / 0.4), cr)
        person(img, d, 280, 1290, 0.8, 'shock' if t > T['verliert'] else 'stand', t, shirt=OLDSHIRT, grey=True, beard=True, mouth='o' if t > T['verliert'] else 'smile')
        if cr > 0:
            for j in range(6):
                u = clamp((t - T['verliert'] - 0.1 * j) / 1.2); note(d, 700 + (j - 2.5) * 70 * u * 3, 1000 - 300 * u + 400 * u * u, 0.6, 90 * u, mix(MARKC, (160, 160, 160), u), int(255 * (1 - u)))
        stamp(img, 700, 760, 'ALLES WEG', sc_(t, 'alles', -0.1, 0.25), RED, -10, 78)
    elif sc == 13:   # l'argent = un bon pour des choses qui existent
        text(img, (CX, 470), 'Geld = ein Gutschein', BF(76), INK, clamp(u0 / 0.3))
        big_note(img, d, CX, 760, 2.4, sc_(t, 'gutschein', -0.3, 0.4), 'GUTSCHEIN')
        if after(t, 'dinge', -0.2):
            k = sc_(t, 'dinge', -0.2, 0.3); arrow(d, CX, 900, CX, 1010, INK, 9, k, 34)
            bread(d, CX - 150, 1130, 0.75, k); shoe(d, CX + 150, 1150, 0.7, sc_(t, 'dinge', 0.0, 0.3))
    elif sc == 14:   # le double d'argent, le même pain → le double du prix
        text(img, (CX, 470), 'Doppelt so viel Geld …', BF(68), INK, clamp(u0 / 0.3))
        two = after(t, 'verdoppelt', -0.1); k2 = sc_(t, 'verdoppelt', -0.1, 0.3)
        for j in range(4 if two else 2):
            kk = 1 if j < 2 else k2; note(d, 280, 1000 - j * 70, 1.05 * back(kk), 0, EURO) if kk > 0 else None
        text(img, (CX, 920), '=', BF(120), INK, clamp(u0 / 0.4))
        bread(d, 790, 960, 1.0, clamp(u0 / 0.4))
        if after(t, 'brot2', -0.2): text(img, (790, 840), 'gleich viel Brot', H2(52), INK, sc_(t, 'brot2', -0.2, 0.3))
        if t < T['preis'] - 0.2: text(img, (790, 1130), '2 €', BF(90), INK, clamp(u0 / 0.4))
        else: k = sc_(t, 'preis', -0.2, 0.25); text(img, (790, 1130), '4 €', BF(100), RED, k, scale=1.5 - 0.5 * k); text(img, (CX, 570), '… doppelter Preis', H2(66), RED, k)
    elif sc == 15:   # si tout le monde est riche, personne n'est riche
        text(img, (CX, 470), 'Alle reich …', BF(80), GREEN, clamp(u0 / 0.3) * (1 - sc_(t, 'niemand', -0.2, 0.2)))
        for j, x in enumerate((170, 410, 650, 890)):
            person(img, d, x, 1290, 0.52, 'hold', t + j, shirt=(BLUE, GREEN, RED, (150, 110, 70))[j]); moneybag(img, d, x + 70, 1090, 0.55)
        if after(t, 'niemand', -0.2):
            k = sc_(t, 'niemand', -0.2, 0.3); text(img, (CX, 470), '= niemand reich', BF(84), RED, k, scale=1.3 - 0.3 * k); cross(d, CX, 1030, 300, sc_(t, 'niemand', 0.0, 0.35), RED, 16)
    elif sc == 16:   # nouvelle monnaie : 1 Rentenmark = 1 000 milliards de marks
        text(img, (CX, 470), 'Neues Geld: die Rentenmark', BF(64), INK, clamp(u0 / 0.3))
        big_note(img, d, CX, 760, 2.2, sc_(t, 'rentenmark', -0.3, 0.4), '1 RENTENMARK', RENTEN)
        if after(t, 'billion', -0.5):
            k = sc_(t, 'billion', -0.5, 0.3); text(img, (CX, 960), '=', BF(90), INK, k)
            k2 = sc_(t, 'billion', -0.15, 0.3); text(img, (CX, 1080), '1.000.000.000.000', BF(80), RED, k2, scale=1.3 - 0.3 * k2); text(img, (CX, 1180), 'alte Mark', H2(64), INK, k2)
    elif sc == 17:   # la BCE vise environ 2 % par an
        text(img, (CX, 470), 'Europäische Zentralbank', BF(64), BLUE, clamp(u0 / 0.3))
        eu_stars(img, d, CX, 760, 150, clamp(u0 / 0.6), t)
        gauge(img, d, CX, 1170, 170, sc_(t, 'zwei', -0.6, 0.5), 2.0 * sc_(t, 'zwei', -0.1, 0.6), '≈ 2 % pro Jahr')
    elif sc == 18:   # ta machine… si tout le monde en avait une, l'argent ne vaudrait rien, comme en 1923
        text(img, (CX, 470), 'Und deine Geldmaschine?', BF(68), INK, clamp(u0 / 0.3) * (1 - sc_(t, 'jeder', -0.2, 0.2)))
        many = sc_(t, 'jeder', -0.2, 0.3); wl = sc_(t, 'wertlos', -0.1, 0.4); nc = mix(EURO, (170, 170, 170), wl)
        if many <= 0:
            printer(img, d, 330, 960, 1.0, clamp(u0 / 0.35), t, 3.0); person(img, d, 830, 1290, 0.8, 'cheer', t, bob=-6 * abs(math.sin(t * 6)))
        else:
            text(img, (CX, 470), 'Wenn jeder eine hätte …', BF(66), INK, many)
            for j in range(6):
                kk = sc_(t, 'jeder', -0.2 + 0.07 * j, 0.3); x = 200 + (j % 3) * 330; y = 760 + (j // 3) * 330
                printer(img, d, x - 40, y, 0.55, kk, t + j, 3.0, ncol=nc)
            if wl > 0: rain(d, 80, 1000, 560, 1300, t, wl, (170, 170, 170), 10)
        stamp(img, CX, 960, 'WERTLOS', wl, RED, -10, 100)
        if after(t, 'y1923b', -0.1): k = sc_(t, 'y1923b', -0.1, 0.3); text(img, (CX, 1255), 'wie 1923', BF(86), (150, 110, 60), k, scale=1.3 - 0.3 * k)
    elif sc == 19:   # question pour les commentaires
        bubble(img, d, 470, 760, 1.15, clamp(u0 / 0.4), 'Was würdest du kaufen?')
        printer(img, d, 300, 1130, 0.6, clamp(u0 / 0.4), t, 2.0)
        person(img, d, 820, 1290, 0.8, 'point', t)
        k = sc_(t, 'kommentare', -0.4, 0.3); text(img, (CX, 470), 'Schreib’s in die', H2(70), INK, k); text(img, (CX, 560), 'Kommentare ↓', BF(66), RED, k)
SEPIA_M = np.array([[0.393, 0.769, 0.189], [0.349, 0.686, 0.168], [0.272, 0.534, 0.131]], np.float32).T
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
    if dm > 0: img.alpha_composite(Image.new('RGBA', img.size, (24, 20, 18, int(255 * dm))))
    img.alpha_composite(lay)
    z, fx, fy, ox, oy = camera(t, sc); cw_, ch_ = W * SS / z, H * SS / z
    cx = min(max(W * SS * fx + S(ox), cw_ / 2), W * SS - cw_ / 2); cy = min(max(H * SS * fy + S(oy), ch_ / 2), H * SS - ch_ / 2)
    img = img.convert('RGB').resize((W * K, H * K), Image.LANCZOS, box=(cx - cw_ / 2, cy - ch_ / 2, cx + cw_ / 2, cy + ch_ / 2))
    arr = np.asarray(img).astype(np.float32)
    sp = sepia(t)
    if sp > 0: arr = arr * (1 - 0.75 * sp) + np.clip(arr @ SEPIA_M, 0, 255) * 0.75 * sp      # 1923 : vieille photo
    arr = (arr * VIG + NOISE[..., None] * (0.6 + 0.8 * sp)).clip(0, 255).astype('uint8'); img = Image.fromarray(arr)
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
    sfx('pop', T['maschine'] - 0.3, 0.12); sfx('click', T['druckt'] - 0.1, 0.3); sfx('pop', T['handy'] - 0.15, 0.12); sfx('ding', T['n1000'] - 0.1, 0.12)
    sfx('hit', T['verboten'] - 0.1, 0.3); sfx('clank', T['gefaengnis'] - 0.15, 0.3); sfx('pop', T['drucken'] - 0.1, 0.1); sfx('zoom1', T['warum'] - 0.2, 0.12)
    sfx('shine', T['reich'] - 0.3, 0.12); sfx('pop', T['de1'], 0.1); sfx('hit', T['y1923'] - 0.1, 0.25); sfx('hit', T['schulden'], 0.2)
    sfx('click', T['druckmaschinen'], 0.25); sfx('pop', T['tag'] - 0.15, 0.1); sfx('pop', T['nacht'] - 0.1, 0.1); sfx('zoom2', T['hundert'] - 0.3, 0.12)
    sfx('shine', T['anfang'], 0.1); sfx('glitch', T['aber1'] - 0.1, 0.15); sfx('pop', T['brot'] - 0.2, 0.1); sfx('pop', T['schuhe'] - 0.2, 0.1)
    sfx('zoom1', T['steigen'] - 0.2, 0.12); sfx('ding', T['november'] - 0.15, 0.1); sfx('hit', T['milliarden'], 0.3); sfx('pop', T['zweimal'] - 0.2, 0.1)
    sfx('whoosh', T['rennen'], 0.15); sfx('pop', T['schubkarren'], 0.1); sfx('pop', T['tuerme'], 0.1); sfx('snap', T['ofen'], 0.15); sfx('hit', T['holz'] - 0.1, 0.2)
    sfx('glitch', T['verliert'] - 0.1, 0.15); sfx('thud', T['alles'] - 0.1, 0.3); sfx('ding', T['gutschein'] - 0.3, 0.12); sfx('pop', T['dinge'] - 0.2, 0.1)
    sfx('pop', T['verdoppelt'] - 0.1, 0.12); sfx('hit', T['preis'] - 0.2, 0.2); sfx('hit', T['niemand'] - 0.2, 0.25); sfx('ding', T['rentenmark'] - 0.3, 0.12)
    sfx('hit', T['billion'] - 0.15, 0.25); sfx('shine', T['zentralbank'], 0.12); sfx('ding', T['zwei'], 0.12); sfx('pop', T['jeder'] - 0.2, 0.12)
    sfx('hit', T['wertlos'] - 0.1, 0.3); sfx('pop', T['was'], 0.15); sfx('ding', T['kommentare'], 0.12)
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
