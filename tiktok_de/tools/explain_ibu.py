# Vidéo explicative « Ibu 400 / 600 » – version haute qualité : 60 i/s, dessins au trait plus détaillés,
# caméra (zoom lent, zooms d'impact, secousses), transitions glissées, texture papier, sons synchronisés.
# Mots calés par align_tts.py (words_final.json) + pauses dramatiques (beats.json).
# usage : explain_ibu.py dossier sortie.mp4  [PREVIEW=t1,t2,...]
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
DUR = len(VOICE) / SR + 1.0
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
def ibubox(img, d, cx, cy, w, h, mg, p, hl=False):
    # boîte de comprimés : bandeau rouge, IBU, dosage, petits comprimés dessinés
    if p <= 0: return
    s = back(p); w, h = w * s, h * s
    rect(d, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, INK, 7, 1, 16, fill=WHITE + (255,))
    d.rectangle([S(cx - w / 2 + 4), S(cy - h / 2 + h * 0.18), S(cx + w / 2 - 4), S(cy - h / 2 + h * 0.36)], fill=RED + (255,))
    text(img, (cx, cy - h / 2 + h * 0.27), 'IBU', BF(h * 0.12), WHITE)
    text(img, (cx, cy + h * 0.08), f'{mg}', BF(h * 0.24), RED if hl else INK)
    text(img, (cx, cy + h * 0.26), 'mg', BF(h * 0.09), GREY)
def tablet(d, img, cx, cy, r, label=None, col=WHITE, rot=0, score=True):
    circ(d, cx, cy, r, INK, col + (255,), 5)
    if not score: return
    a = math.radians(rot); line(d, cx - r * 0.7 * math.cos(a), cy - r * 0.7 * math.sin(a), cx + r * 0.7 * math.cos(a), cy + r * 0.7 * math.sin(a), GREY, 3)
    if label: text(img, (cx, cy + r + 26), label, BF(28), INK)
def trash(d, cx, cy, s=1.0, lid=0.0):
    w, h = 150 * s, 190 * s
    poly(d, [(cx - w / 2, cy - h / 2), (cx - w / 2 + 18 * s, cy + h / 2), (cx + w / 2 - 18 * s, cy + h / 2), (cx + w / 2, cy - h / 2)], INK, 7)
    for k in (-1, 0, 1): line(d, cx + k * 35 * s, cy - h / 2 + 30 * s, cx + k * 30 * s, cy + h / 2 - 25 * s, GREY, 4)
    a = math.radians(-35 * lid); lx, ly = cx - w / 2 - 12 * s, cy - h / 2 - 12 * s
    line(d, lx, ly, lx + (w + 24 * s) * math.cos(a), ly + (w + 24 * s) * math.sin(a), INK, 8)
def head(d, cx, cy, r, ache=0.0, t=0):
    circ(d, cx, cy, r, INK, None, 7); line(d, cx - r * 0.35, cy + r * 0.95, cx - r * 0.3, cy + r * 1.45, INK, 7); line(d, cx + r * 0.35, cy + r * 0.95, cx + r * 0.3, cy + r * 1.45, INK, 7)
    circ(d, cx - r * 0.35, cy - r * 0.1, r * 0.08, None, INK + (255,)); circ(d, cx + r * 0.35, cy - r * 0.1, r * 0.08, None, INK + (255,))
    poly(d, [(cx - r * 0.3, cy + r * 0.45), (cx, cy + r * 0.35), (cx + r * 0.3, cy + r * 0.45)], INK, 5)
    if ache > 0:   # éclairs de douleur qui grésillent
        for side in (-1, 1):
            j = 6 * math.sin(t * 40 + side)
            pts = [(cx + side * (r + 20), cy - r * 0.6 + j), (cx + side * (r + 60), cy - r * 0.35), (cx + side * (r + 35), cy - r * 0.2), (cx + side * (r + 80), cy + r * 0.05)]
            poly(d, pts, RED, 8, ease(ache))
def foot(d, cx, cy, s=1.0, toe_red=0.0):
    # pied vu du dessus : semelle + 5 orteils (le petit orteil peut rougir)
    pts = [(cx + s * 70 * math.cos(a) * (1.15 if math.sin(a) > 0 else 1), cy + s * 175 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 40)]
    d.polygon([(S(x), S(y)) for x, y in pts], fill=SKIN + (255,)); poly(d, pts, INK, 7, closed=True)
    toes = [(-52, -190, 30), (-12, -205, 24), (22, -200, 21), (50, -188, 19), (74, -168, 17)]
    for k, (dx, dy, r) in enumerate(toes):
        fill = tuple(int(SKIN[i] + (RED[i] - SKIN[i]) * toe_red) for i in range(3)) if k == 4 else SKIN
        circ(d, cx + dx * s, cy + dy * s, r * s * (1 + 0.25 * toe_red if k == 4 else 1), INK, fill + (255,), 6)
def starburst(d, cx, cy, r, p, col=RED):
    if p <= 0: return
    rr = r * back(p); pts = [(cx + (rr if k % 2 == 0 else rr * 0.45) * math.cos(k * math.pi / 8), cy + (rr if k % 2 == 0 else rr * 0.45) * math.sin(k * math.pi / 8)) for k in range(16)]
    d.polygon([(S(x), S(y)) for x, y in pts], fill=(255, 230, 120, 255)); poly(d, pts, col, 6, closed=True)
def brain(d, cx, cy, r, flash=0.0):
    col = tuple(int(INK[i] + (RED[i] - INK[i]) * flash) for i in range(3))
    fill = tuple(int(250 + (255 - 250) * flash) for _ in range(3))
    for k, (dx, dy, rr) in enumerate([(-0.45, 0.05, 0.5), (-0.1, -0.3, 0.52), (0.35, -0.2, 0.5), (0.5, 0.2, 0.42), (0.0, 0.3, 0.45)]):
        circ(d, cx + dx * r, cy + dy * r, rr * r, None, (255, int(240 - 60 * flash), int(235 - 80 * flash), 255))
    for k, (dx, dy, rr) in enumerate([(-0.45, 0.05, 0.5), (-0.1, -0.3, 0.52), (0.35, -0.2, 0.5), (0.5, 0.2, 0.42), (0.0, 0.3, 0.45)]):
        arc(d, cx + dx * r, cy + dy * r, rr * r, 160, 380, col, 6)
    poly(d, [(cx - r * 0.3, cy - r * 0.1), (cx - r * 0.1, cy + r * 0.05), (cx + r * 0.1, cy - r * 0.12), (cx + r * 0.3, cy + r * 0.02)], col, 5)
def heart(d, cx, cy, r, pulse=0.0):
    rr = r * (1 + 0.22 * pulse)
    circ(d, cx - rr * 0.48, cy - rr * 0.25, rr * 0.55, None, RED + (255,)); circ(d, cx + rr * 0.48, cy - rr * 0.25, rr * 0.55, None, RED + (255,))
    d.polygon([(S(cx - rr * 1.0), S(cy - rr * 0.1)), (S(cx + rr * 1.0), S(cy - rr * 0.1)), (S(cx), S(cy + rr * 1.05))], fill=RED + (255,))
def slider(img, d, x, y0, y1, val, p=1.0, label=True):
    # bouton de volume vertical : graduations, remplissage rouge, poignée
    line(d, x, y0, x, y0 + (y1 - y0) * ease(p), INK, 10)
    if p < 0.5: return
    for k in range(6): line(d, x - 34, y1 - (y1 - y0) * k / 5, x - 18, y1 - (y1 - y0) * k / 5, GREY, 4)
    yv = y1 - (y1 - y0) * clamp(val)
    d.rounded_rectangle([S(x - 7), S(yv), S(x + 7), S(y1)], S(7), fill=RED + (255,))
    d.rounded_rectangle([S(x - 46), S(yv - 22), S(x + 46), S(yv + 22)], S(12), fill=WHITE + (255,), outline=INK, width=S(6))
    if label: text(img, (x, y0 - 50), 'Lautstärke', H2(40), INK, clamp(p * 2 - 1))
def speaker(d, cx, cy, s, level):
    d.polygon([(S(cx - 40 * s), S(cy - 22 * s)), (S(cx - 10 * s), S(cy - 22 * s)), (S(cx + 25 * s), S(cy - 50 * s)), (S(cx + 25 * s), S(cy + 50 * s)), (S(cx - 10 * s), S(cy + 22 * s)), (S(cx - 40 * s), S(cy + 22 * s))], fill=INK + (255,))
    for k in range(3):
        if level > k / 3 + 0.05: arc(d, cx + 30 * s, cy, (35 + 28 * k) * s, -45, 45, RED if level > 0.7 else INK, 7)
def cup(d, cx, cy, s, t, steam=1.0):
    poly(d, [(cx - 90 * s, cy - 80 * s), (cx - 75 * s, cy + 90 * s), (cx + 75 * s, cy + 90 * s), (cx + 90 * s, cy - 80 * s)], INK, 8, closed=True)
    d.polygon([(S(cx - 84 * s), S(cy - 50 * s)), (S(cx - 72 * s), S(cy + 84 * s)), (S(cx + 72 * s), S(cy + 84 * s)), (S(cx + 84 * s), S(cy - 50 * s))], fill=BROWN + (255,))
    arc(d, cx + 100 * s, cy, 40 * s, -80, 80, INK, 8)
    for k in (-1, 0, 1):
        if steam > 0: poly(d, [(cx + k * 40 * s + 12 * math.sin(t * 3 + y * 0.05 + k), cy - 100 * s - y * s) for y in range(0, 140, 10)], GREY, 5, steam)
def stomach(d, cx, cy, s, irr=0.0, t=0):
    pts = [(cx + s * (120 * math.cos(a) - 35 * math.sin(a) ** 2), cy + s * (95 * math.sin(a) + 45 * math.cos(a) ** 3 * (1 if math.sin(a) > 0 else 0.4))) for a in np.linspace(0, 2 * math.pi, 60)]
    fill = tuple(int(SKIN[i] + ((240, 150, 140)[i] - SKIN[i]) * irr) for i in range(3))
    d.polygon([(S(x), S(y)) for x, y in pts], fill=fill + (255,)); poly(d, pts, INK, 7, closed=True)
    line(d, cx - 70 * s, cy - 80 * s, cx - 95 * s, cy - 200 * s, INK, 9); line(d, cx + 95 * s, cy + 40 * s, cx + 150 * s, cy + 120 * s, INK, 9)
    if irr > 0:
        for k in range(4):
            j = 5 * math.sin(t * 25 + k); x0 = cx - 60 * s + k * 35 * s
            poly(d, [(x0, cy - 20 * s + j), (x0 + 12 * s, cy - 40 * s), (x0 + 24 * s, cy - 15 * s), (x0 + 30 * s, cy - 35 * s)], RED, 6, irr)
def hand(d, cx, cy, s, inflam=0.0, t=0):
    d.rounded_rectangle([S(cx - 110 * s), S(cy - 40 * s), S(cx + 110 * s), S(cy + 150 * s)], S(40 * s), fill=SKIN + (255,), outline=INK, width=S(7))
    for k in range(4):
        x = cx - 82 * s + k * 55 * s; d.rounded_rectangle([S(x - 22 * s), S(cy - 210 * s), S(x + 22 * s), S(cy - 20 * s)], S(22 * s), fill=SKIN + (255,), outline=INK, width=S(7))
        if inflam > 0:
            g = 0.5 + 0.5 * math.sin(t * 6 + k); circ(d, x, cy - 70 * s, 26 * s * (1 + 0.15 * g), None, RED + (int(150 * inflam),)); circ(d, x, cy - 70 * s, 14 * s, None, RED + (int(230 * inflam),))
def apotheke(img, d, cx, cy, r, p):
    s = back(p); a, b = r * 0.36 * s, r * s
    d.rounded_rectangle([S(cx - a), S(cy - b), S(cx + a), S(cy + b)], S(18), fill=GREEN + (255,)); d.rounded_rectangle([S(cx - b), S(cy - a), S(cx + b), S(cy + a)], S(18), fill=GREEN + (255,))
def share(img, d, cx, cy, p):
    for (x, y) in ((cx - 170, cy), (cx + 150, cy - 140), (cx + 150, cy + 140)): arc(d, x, y, 62, -90, -90 + 360 * ease(p), INK, 9)
    line(d, cx - 115, cy - 25, cx + 95, cy - 115, INK, 8, ease(p - 0.4)); line(d, cx - 115, cy + 25, cx + 95, cy + 115, INK, 8, ease(p - 0.4))
# ---------- repères temporels
T = dict(ibu=tw('ibu'), staerker=tw('stärker'), kopf=tw('kopfschmerzen'), z200=tw('200'), umsonst=tw('umsonst'), schau=tw('schau'), stoesst=tw('stößt'), zeh=tw('zeh'),
         zellen=tw('zellen'), stoff=tw('stoff'), prosta=tw('prostaglandin'), dreht=tw('dreht'), volle=tw('volle'), feuern=tw('feuern'), gehirn=tw('gehirn'), pocht=tw('pocht'),
         herzens=tw('herzens'), ibuprofen=tw('ibuprofen'), blockiert=tw('blockiert'), runter=tw('runter'), leiser=tw('leiser'), aber=tw('aber'), haken=tw('haken'),
         regler=tw('regler'), m400=tw('400'), unten=tw('unten'), mehrgeht=tw('geht', 1), ceiling=tw('ceiling-effekt'), mehrw=tw('wirkstoff'), kaum=tw('kaum'), warum=tw('warum'),
         e600=tw('600er'), entz=tw('entzündungen'), rheuma=tw('rheuma'), tag=tw('tag'), x600ern=tw('600ern'), weniger=tw('weniger'), zwei=tw('zwei'), kopfweh=tw('kopfweh'),
         bringt=tw('bringt'), magen=tw('magen'), preis=tw('preis'), jetzt=tbefore('jetzt'), niemand=tw('niemand'), kaffee=tw('kaffee'), verst=tw('verstärken'), studien=tw('studien'),
         wichtig=tw('wichtig'), apotheke=tw('apotheke'), sags=tw("sag's"))
for k, v in T.items():
    if v is None: print('mot introuvable :', k)
SC = [0, T['schau'] - 0.12, T['dreht'] - 0.25, T['ibuprofen'] - 0.12, T['aber'] - 0.12, T['warum'] - 0.12, T['zwei'] - 0.12, T['jetzt'] - 0.12, T['wichtig'] - 0.12, T['sags'] - 0.12, DUR]
HEARTS = [T['pocht'] + k * 0.72 for k in range(8) if T['pocht'] + k * 0.72 < SC[3] - 0.15]
BONKS = [T['ceiling'] - 0.05, T['ceiling'] + 0.3, BT['ceiling']['t'] + 0.25]
# ---------- caméra : zoom lent par scène + zooms d'impact + secousses
PUNCH = [(T['umsonst'], 0.07), (T['stoesst'] + 0.25, 0.09), (T['prosta'], 0.05), (T['ceiling'], 0.07), (T['kaffee'], 0.06), (T['magen'], 0.04)] + [(h, 0.025) for h in HEARTS]
SHAKE = [(BT['trash']['t'] + 0.45, 14), (T['stoesst'] + 0.25, 26), (T['ceiling'], 16), (BT['ceiling']['t'] + 0.25, 12)]
FOCUS = {1: (0.62, 0.42)}   # scène du pied : la caméra se rapproche de l'orteil sur « Prostaglandin »
def camera(t, sc):
    a0, a1 = SC[sc], SC[sc + 1]; z = 1.025 + 0.035 * eio((t - a0) / max(1, a1 - a0))
    for t0, amp in PUNCH:
        if t0 and 0 <= t - t0 < 0.6: z += amp * math.exp(-(t - t0) * 7) * min(1, (t - t0) / 0.05)
    ox = oy = 0
    for t0, amp in SHAKE:
        if t0 and 0 <= t - t0 < 0.4: k = (1 - (t - t0) / 0.4) ** 2; ox += amp * k * math.sin((t - t0) * 95); oy += amp * k * math.cos((t - t0) * 83)
    fx, fy = 0.5, 0.42
    if sc == 1 and T['prosta']: q = eio((t - T['zellen'] + 0.2) / 0.8); fx, fy = 0.5 + 0.1 * q, 0.42 - 0.04 * q; z += 0.12 * q
    return z, fx, fy, ox, oy
# ---------- texture papier + vignette (fixes, appliquées après la caméra)
_rs = np.random.RandomState(7); NOISE = np.asarray(Image.fromarray((_rs.normal(128, 9, (H, W))).clip(0, 255).astype('uint8')).filter(ImageFilter.GaussianBlur(0.8))).astype(np.int16) - 128
yy, xx = np.mgrid[0:H, 0:W]; VIG = (1 - 0.10 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H * 0.45) / (H * 0.6)) ** 2)).clip(0.82, 1)[..., None]
# ---------- sous-titres : 3 mots max, mot actif qui « pop », mots clés en jaune
HOT = re.compile(r'(\d|ibu|milligramm|umsonst|zeh|prostaglandin|lautstärke|gehirn|herz|blockiert|leiser|haken|regler|ceiling|wirkstoff|wirkung|rheuma|entzündung|tabletten|magen|preis|kaffee|studien|apotheke|kopf)', re.I)
GROUPS = []; cur = []
for k, w in enumerate(WORDS):
    cur.append(k)
    if len(cur) == 3 or re.search(r'[.,:!?–]$', w[0]): GROUPS.append(cur); cur = []
if cur: GROUPS.append(cur)
def caption(img, t):
    g = next((g for g in GROUPS if WORDS[g[0]][1] - 0.05 <= t < WORDS[g[-1]][2] + 0.3), None)
    if not g: return
    ws = [WORDS[k][0].strip('.,:!?„“"').upper() for k in g]; base = 56; cf = F('Poppins-ExtraBold.ttf', base)
    wd = [cf.getbbox(w)[2] for w in ws]; sp = 20; tw_ = sum(wd) + sp * (len(ws) - 1)
    if tw_ > W - 120: base = int(base * (W - 120) / tw_); cf = F('Poppins-ExtraBold.ttf', base); wd = [cf.getbbox(w)[2] for w in ws]; tw_ = sum(wd) + sp * (len(ws) - 1)
    d = ImageDraw.Draw(img); x = W / 2 - tw_ / 2; y = 1390
    for w, k, ww in zip(ws, g, wd):
        t0 = WORDS[k][1]
        if t >= t0 - 0.03:
            u = (t - t0) / 0.12; pop = 1 + 0.14 * math.sin(clamp(u) * math.pi) if u < 1 else 1
            f2 = F('Poppins-ExtraBold.ttf', base * pop) if pop != 1 else cf
            d.text((x + ww / 2, y), w, font=f2, fill=YEL if HOT.search(w) else (255, 255, 255), anchor='mm', stroke_width=6, stroke_fill=(0, 0, 0))
        x += ww + sp
# ---------- les scènes
def scene(img, d, sc, t):
    CX = W / 2; u0 = t - SC[sc]
    if sc == 0:   # boîtes 400 / 600, tête qui a mal, 200 mg à la poubelle, tampon UMSONST
        grow = 0.12 * since(t, T['staerker'], 0.3) * (1 - since(t, T['z200'] - 0.1, 0.3))
        ibubox(img, d, 300, 760, 300, 380, 400, u0 / 0.15)
        split = since(t, T['z200'] - 0.1, 0.35)
        ibubox(img, d, 760, 760 - 30 * grow * 3, 300 * (1 + grow), 380 * (1 + grow), 600 if split < 0.5 else 400, (u0 - 0.06) / 0.15, hl=split < 0.5)
        if T['staerker'] and t > T['staerker'] and split < 0.3: text(img, (760, 500), 'stärker?', H2(70), RED, since(t, T['staerker'], 0.25))
        if T['kopf'] and t > T['kopf'] - 0.1: head(d, CX, 360, 70, ache=since(t, T['kopf'], 0.4), t=t)
        if split > 0:   # le bloc « 200 mg » se détache et tombe dans la poubelle
            trash(d, 905, 1170, 0.95, lid=since(t, T['z200'], 0.3) * (1 - since(t, BT['trash']['t'] + 0.6, 0.3)))
            q = clamp((t - T['z200']) / max(0.4, BT['trash']['t'] + 0.45 - T['z200']))
            bx = 760 + 145 * q; by = 980 + (1080 - 980) * q - 320 * math.sin(q * math.pi) * (1 - q)
            if q < 1:
                d.rounded_rectangle([S(bx - 85), S(by - 60), S(bx + 85), S(by + 60)], S(14), fill=WHITE + (255,), outline=RED, width=S(6))
                text(img, (bx, by), '200 mg', BF(40), RED)
        if T['umsonst'] and t > T['umsonst'] - 0.05:
            k = since(t, T['umsonst'] - 0.05, 0.22); text(img, (450, 1170), 'UMSONST', BF(104), RED, k, rot=-8, scale=1.6 - 0.6 * ease(k))
    elif sc == 1:  # le pied heurte la marche, impact, cellules et prostaglandine
        hit = T['stoesst'] + 0.25; q = ease((t - (hit - 0.55)) / 0.55); fx = 380 + 190 * q
        d.rectangle([S(700), S(380), S(1000), S(1150)], fill=(205, 192, 172, 255)); poly(d, [(700, 380), (700, 1150)], INK, 9)
        text(img, (850, 340), 'Kante', H2(54), GREY, clamp(u0 / 0.4))
        red = since(t, hit, 0.3) * (0.75 + 0.25 * math.sin(t * 9))
        foot(d, fx, 900, 1.25, toe_red=red)
        if t > hit: starburst(d, fx + 95, 690, 70, since(t, hit, 0.25)); text(img, (fx + 160, 560), 'AUA!', BF(80), RED, since(t, hit, 0.2) * (1 - since(t, hit + 1.1, 0.3)), rot=10)
        if T['zellen'] and t > T['zellen'] - 0.1:   # cellules autour de l'orteil, puis points de prostaglandine
            k = since(t, T['zellen'] - 0.1, 0.4); cx0, cy0 = fx + 95, 690
            for j in range(6):
                a = j * 1.05 + 0.3; circ(d, cx0 + 95 * math.cos(a), cy0 + 85 * math.sin(a), 26 * k, INK, (245, 225, 215, 255), 4); circ(d, cx0 + 95 * math.cos(a), cy0 + 85 * math.sin(a), 8 * k, None, GREY + (255,))
        if T['stoff'] and t > T['stoff'] - 0.1:
            rs = np.random.RandomState(3); k = since(t, T['stoff'] - 0.1, 1.2); cx0, cy0 = fx + 95, 690
            for j in range(26):
                a = rs.uniform(0, 6.28); r = 60 + rs.uniform(30, 170) * ease(k - j * 0.015); circ(d, cx0 + r * math.cos(a), cy0 + r * math.sin(a), 9, None, RED + (255,))
        if T['prosta'] and t > T['prosta'] - 0.1:
            text(img, (600, 430), 'Prostaglandin', H2(66), RED, since(t, T['prosta'] - 0.1, 0.3)); arrow(d, 600, 470, fx + 80, 600, RED, 6, since(t, T['prosta'], 0.4))
    elif sc == 2:  # volume au maximum, signaux vers le cerveau, cœur qui bat
        foot(d, 250, 1150, 0.7, toe_red=0.9); vol = 0.15 + 0.85 * ease((t - T['volle'] + 0.2) / 0.7) if T['volle'] else 0.2
        slider(img, d, 900, 800, 1130, vol, u0 / 0.5); speaker(d, 900, 1205, 0.7, vol)
        bx, by = 820, 520; flash = 0
        nerve = [(285, 1010), (300, 900), (360, 800), (400, 690), (480, 600), (580, 560), (bx - 125, by + 20)]
        poly(d, nerve, INK, 6, clamp(u0 / 0.6))
        if T['feuern'] and t > T['feuern'] - 0.1:   # rafale de signaux le long du nerf
            L = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(nerve, nerve[1:])]; tot = sum(L)
            for j in range(7):
                s_ = ((t - T['feuern']) * 900 + j * tot / 7) % tot; acc = 0
                for (a, b), l in zip(zip(nerve, nerve[1:]), L):
                    if acc + l >= s_: q = (s_ - acc) / l; x, y = a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q; circ(d, x, y, 13, None, RED + (255,)); break
                    acc += l
            flash = 0.5 + 0.5 * math.sin(t * 22)
        brain(d, bx, by, 120, flash)
        if T['gehirn'] and t > T['gehirn'] - 0.1: text(img, (bx, by - 175), 'Gehirn', H2(56), INK, since(t, T['gehirn'] - 0.1, 0.3))
        if T['pocht'] and t > T['pocht'] - 0.15:
            pulse = max([math.exp(-(t - h) * 9) for h in HEARTS if t >= h] or [0])
            heart(d, 470, 1000, 50, pulse); text(img, (470, 1095), 'pocht im Takt', H2(50), RED, since(t, T['pocht'], 0.3))
            ecg = []
            for k in range(52):
                x = 110 + k * 12; tt = t - (51 - k) * 0.012; ph = min([(tt - h) for h in HEARTS if tt >= h] or [9])
                ecg.append((x, 1245 - (60 * math.exp(-((ph - 0.04) / 0.015) ** 2) - 25 * math.exp(-((ph - 0.08) / 0.02) ** 2))))
            poly(d, ecg, RED, 5)
    elif sc == 3:  # le comprimé bloque la prostaglandine, le volume baisse
        cx0, cy0 = 330, 760; land = T['ibuprofen'] + 0.35; q = ease((t - T['ibuprofen'] + 0.1) / 0.45)
        rs = np.random.RandomState(3); blk = since(t, T['blockiert'], 0.6) if T['blockiert'] else 0
        for j in range(24):
            a = rs.uniform(0, 6.28); r = 70 + rs.uniform(30, 190); s_ = 9 * (1 - blk)
            if s_ > 0.5: circ(d, cx0 + r * math.cos(a), cy0 + r * math.sin(a), s_, None, RED + (255,))
        tablet(d, img, cx0, cy0 - 600 * (1 - q), 95, None, WHITE, rot=20, score=False); text(img, (cx0, cy0 - 600 * (1 - q)), 'IBU', BF(48), INK)
        if blk > 0: arc(d, cx0, cy0, 230 * ease(blk), 0, 360, GREEN, 8); text(img, (cx0, cy0 + 300), 'blockiert', BF(60), GREEN, blk)
        vol = 1 - 0.75 * since(t, T['runter'] - 0.3, 0.9) if T['runter'] else 1
        slider(img, d, 820, 520, 1080, vol, 1); speaker(d, 820, 1150, 0.9, vol)
        if T['leiser'] and t > T['leiser'] - 0.1: text(img, (820, 1250), 'leiser', H2(66), INK, since(t, T['leiser'] - 0.1, 0.3))
    elif sc == 4:  # le haken + graphique avec plafond (ceiling)
        hk = since(t, T['haken'] - 0.2, 0.5) * (1 - since(t, T['regler'] - 0.3, 0.3))
        if hk > 0:
            poly(d, [(CX, 470), (CX, 760)], INK, 10, hk); arc(d, CX - 60, 760, 60, 0, 180 * ease(hk), INK, 10); line(d, CX - 120, 760, CX - 140, 720, INK, 10, ease(hk - 0.6))
            text(img, (CX, 950), 'der Haken …', H2(80), RED, hk)
        g = since(t, T['regler'] - 0.3, 0.4)
        if g > 0:
            ox, oy, gw, gh = 170, 1150, 800, 640
            line(d, ox, oy, ox + gw, oy, INK, 7, g); line(d, ox, oy, ox, oy - gh, INK, 7, g)
            text(img, (ox + 10, oy - gh - 40), 'Wirkung gegen Schmerz', H2(46), GREY, g, anchor='lm')
            cap = 420; vals = [(200, 0.55), (400, 0.97), (600, 1.02), (800, 1.05)]
            tstart = [T['regler'] - 0.1, T['m400'] - 0.15, T['mehrgeht'] - 0.2, T['mehrgeht'] + 0.15]
            for j, ((mg, h), t0) in enumerate(zip(vals, tstart)):
                x = ox + 110 + j * 180; k = ease((t - t0) / 0.5) if t0 else 0
                hh = cap * h * k; bonk = 0
                if h > 1 and k > 0.9:   # écrasé contre le plafond
                    hh = cap; bonk = max([math.exp(-(t - b) * 12) for b in BONKS if t >= b] or [0])
                    hh = cap - 18 * bonk
                d.rectangle([S(x - 55), S(oy - hh), S(x + 55), S(oy)], fill=((175, 160, 140) if h < 1 else (200, 120, 100)) + (255,), outline=INK, width=S(5))
                text(img, (x, oy + 40), str(mg), BF(36), INK, g)
            cl = since(t, T['mehrgeht'] - 0.1, 0.4)
            if cl > 0:
                for k in range(14): line(d, ox + k * 58, oy - cap - 10, ox + k * 58 + 34, oy - cap - 10, RED, 7, clamp(cl * 14 - k))
            if T['ceiling'] and t > T['ceiling'] - 0.1:
                k = since(t, T['ceiling'] - 0.1, 0.2); text(img, (CX, oy - cap - 110), 'CEILING-EFFEKT', BF(70), RED, k, scale=1.5 - 0.5 * ease(k))
            if T['mehrw'] and t > T['mehrw'] - 0.1:
                text(img, (CX, 1240), 'mehr mg – kaum mehr Wirkung', H2(58), INK, since(t, T['mehrw'] - 0.1, 0.3))
    elif sc == 5:  # 600 pour les rhumatismes : main enflammée, comprimés sur la journée
        (ibubox(img, d, CX, 600, 260, 330, 600, u0 / 0.2), text(img, (CX, 880), 'wozu dann 600?', H2(72), RED, clamp((u0 - 0.3) / 0.3))) if not (T['entz'] and t > T['entz'] - 0.2) else None
        if T['entz'] and t > T['entz'] - 0.2 and not (T['tag'] and t > T['tag'] - 0.2):
            hand(d, CX, 800, 1.2, inflam=since(t, T['entz'], 0.6), t=t); text(img, (CX, 1130), 'Rheuma', BF(70), RED, since(t, T['rheuma'] - 0.1, 0.3) if T['rheuma'] else 0)
        if T['tag'] and t > T['tag'] - 0.2:
            k = since(t, T['tag'] - 0.2, 0.4); line(d, 140, 520, 940, 520, INK, 6, k)
            circ(d, 140, 520, 34, INK, (255, 214, 90, 255), 5); circ(d, 940, 520, 30, INK, (210, 210, 230, 255), 5); text(img, (CX, 450), 'über den Tag', H2(54), GREY, k)
            for j in range(6): tablet(d, img, 210 + j * 120, 720, 38 * ease((t - T['tag'] - 0.2 - j * 0.12) / 0.3), None)
            text(img, (CX, 640), '6 × 400', BF(46), INK, k)
            if T['x600ern'] and t > T['x600ern'] - 0.2:
                k2 = since(t, T['x600ern'] - 0.2, 0.3); text(img, (CX, 860), '4 × 600', BF(46), RED, k2)
                for j in range(4): tablet(d, img, 330 + j * 140, 960, 46 * ease((t - T['x600ern'] - j * 0.12) / 0.3), None, (255, 236, 230))
                if T['weniger'] and t > T['weniger']: text(img, (CX, 1110), 'weniger Tabletten', H2(64), INK, since(t, T['weniger'], 0.3)); check(d, 900, 960, 40, since(t, T['weniger'], 0.5))
    elif sc == 6:  # deux 400 contre le mal de tête : presque rien de plus, l'estomac paie
        mag = T['magen'] and t > T['magen'] - 0.25
        if not mag:
            head(d, 300, 700, 90, ache=1 - 0.3 * since(t, T['bringt'], 0.5) if T['bringt'] else 1, t=t)
            tablet(d, img, 620, 640, 56, '400'); text(img, (700, 640), '+', BF(70), INK); tablet(d, img, 780, 640, 56, '400')
            if T['bringt'] and t > T['bringt']: arrow(d, 540, 900, 860, 900, INK, 7, since(t, T['bringt'], 0.4)); text(img, (700, 980), 'kaum mehr', H2(66), INK, since(t, T['bringt'], 0.3))
        else:
            k = since(t, T['magen'] - 0.25, 0.4); stomach(d, CX, 820, 1.4, irr=since(t, T['magen'], 0.6), t=t)
            text(img, (CX, 470), 'dein Magen', H2(64), INK, k)
            if T['preis'] and t > T['preis'] - 0.1: text(img, (CX, 1150), 'zahlt den Preis', BF(62), RED, since(t, T['preis'] - 0.1, 0.25), scale=1.3 - 0.3 * since(t, T['preis'] - 0.1, 0.25))
    elif sc == 7:  # révélation : le café
        rv = BT['reveal']; t_rev = rv['t'] + rv['dur']
        if t < t_rev - 0.05:
            text(img, (CX, 760), 'fast niemand', H2(84), GREY, clamp(u0 / 0.3)); text(img, (CX, 880), 'weiß das …', H2(84), GREY, clamp(u0 / 0.3))
            for j in range(3): circ(d, CX - 40 + j * 40, 1000, 10, None, INK + (int(255 * (0.5 + 0.5 * math.sin(t * 10 - j))),))
        else:
            k = since(t, t_rev - 0.05, 0.4); cup(d, 380, 820 + 300 * (1 - back(k)), 1.3, t, steam=k)
            if T['kaffee'] and t > T['kaffee']: text(img, (380, 1060), 'Kaffee', BF(60), BROWN, since(t, T['kaffee'], 0.3))
            if T['verst'] and t > T['verst'] - 0.3:
                k2 = since(t, T['verst'] - 0.3, 0.4); tablet(d, img, 760, 820, 60, None, score=False); text(img, (760, 820), 'IBU', BF(32), INK, k2)
                arrow(d, 860, 900, 860, 640, GREEN, 10, k2); text(img, (760, 560), 'Wirkung', BF(54), GREEN, k2)
            if T['studien'] and t > T['studien'] - 0.2:
                k3 = since(t, T['studien'] - 0.2, 0.4)
                for j in range(3): rect(d, 330 + j * 40, 1150 - j * 25, 530 + j * 40, 1330 - j * 25, INK, 5, 1, 6, fill=WHITE + (int(255 * k3),))
                text(img, (700, 1240), 'Studien', H2(64), INK, k3); check(d, 860, 1235, 40, since(t, T['studien'], 0.5))
    elif sc == 8:  # apotheke
        apotheke(img, d, CX, 760, 190, clamp(u0 / 0.35)); text(img, (CX, 1060), 'Frag deine Apotheke', BF(60), GREEN, clamp((u0 - 0.2) / 0.3))
    elif sc == 9:  # partage
        share(img, d, CX, 760, u0 / 0.7); text(img, (CX, 1120), "sag's weiter", H2(96), RED, clamp((u0 - 0.3) / 0.4)); underline(d, CX - 230, CX + 230, 1180, RED, ease((u0 - 0.6) / 0.5), 10)
def draw(t):
    sc = max(i for i in range(len(SC) - 1) if t >= SC[i])
    lay = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    scene(lay, d, sc, t)
    a0, a1 = SC[sc], SC[sc + 1]; tin = clamp((t - a0) / 0.28); tout = clamp((a1 - t) / 0.22) if sc < len(SC) - 2 else 1
    al = min(ease(tin), tout); dx = (1 - ease(tin)) * 160 - (1 - tout) * 120     # glisse depuis la droite, part vers la gauche
    if al < 1: lay.putalpha(lay.getchannel('A').point(lambda v: int(v * al)))
    img = Image.new('RGBA', (W * SS, H * SS), BG + (255,)); comp(img, lay, S(dx), 0)
    z, fx, fy, ox, oy = camera(t, sc); cw_, ch_ = W * SS / z, H * SS / z
    cx = min(max(W * SS * fx + S(ox), cw_ / 2), W * SS - cw_ / 2); cy = min(max(H * SS * fy + S(oy), ch_ / 2), H * SS - ch_ / 2)
    img = img.convert('RGB').resize((W, H), Image.LANCZOS, box=(cx - cw_ / 2, cy - ch_ / 2, cx + cw_ / 2, cy + ch_ / 2))
    arr = (np.asarray(img).astype(np.float32) * VIG + NOISE[..., None] * 0.6).clip(0, 255).astype('uint8'); img = Image.fromarray(arr)
    dd = ImageDraw.Draw(img); dd.text((70, 185), NAME, font=F('Caveat.ttf', 86), fill=GREY, anchor='ls'); dd.text((72, 250), HANDLE, font=F('Caveat.ttf', 62), fill=RED, anchor='ls')
    caption(img, t); return img
TMP = OUT + '_fr'
def render_chunk(rng):
    for n in range(*rng): draw(n / FPS).save(f'{TMP}/f{n:05d}.jpg', quality=96, subsampling=0)
    return rng
if __name__ == '__main__':
    if os.environ.get('PREVIEW'):
        for ts in os.environ['PREVIEW'].split(','): draw(float(ts)).save(f'{OUT}_{ts}.jpg', quality=88)
        sys.exit(0)
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP); NF = int(DUR * FPS); CH = 90
    with Pool(4) as pool:
        for k, _ in enumerate(pool.imap_unordered(render_chunk, [(i, min(NF, i + CH)) for i in range(0, NF, CH)])):
            if k % 8 == 0: print('images', min(NF, (k + 1) * CH), '/', NF, flush=True)
    # ---------- son : voix + effets synchronisés (musique seulement avec MUSIC=1)
    N = int(DUR * SR); mix = np.zeros(N); mix[:len(VOICE)] += VOICE
    def sfx(name, t0, g):
        if t0 is None: return
        w = wave.open(SFXD + name + '.wav'); s = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float) / 32768
        if w.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
        if w.getframerate() != SR: s = np.interp(np.arange(0, len(s), w.getframerate() / SR), np.arange(len(s)), s)
        i0 = int(max(0, t0) * SR); L = min(len(s), N - i0); mix[i0:i0 + L] += s[:L] * g
    def synth(t0, sig, g):
        i0 = int(t0 * SR); L = min(len(sig), N - i0); mix[i0:i0 + L] += sig[:L] * g
    x = np.arange(int(0.25 * SR)) / SR
    thump = np.sin(2 * np.pi * 55 * x) * np.exp(-x / 0.05) + 0.5 * np.sin(2 * np.pi * 90 * x) * np.exp(-x / 0.03)
    for h in HEARTS: synth(h, thump, 0.55); synth(h + 0.24, thump, 0.38)          # « boum-boum »
    for t0 in SC[1:-1]: sfx('whoosh', t0 - 0.08, 0.16)
    sfx('pop', 0.02, 0.15); sfx('pop', 0.1, 0.15); sfx('swish', T['z200'], 0.2); sfx('thud', BT['trash']['t'] + 0.45, 0.45); sfx('hit', T['umsonst'] - 0.05, 0.35)
    sfx('hit', T['stoesst'] + 0.25, 0.55); sfx('thud', T['stoesst'] + 0.25, 0.4); sfx('pop', T['zellen'], 0.12); sfx('pop', T['prosta'], 0.15)
    sfx('zoom1', T['volle'] - 0.2, 0.18); sfx('tap', T['feuern'], 0.12); sfx('pop', T['ibuprofen'] + 0.3, 0.2); sfx('shine', T['blockiert'], 0.18)
    sfx('swish', T['haken'], 0.18); [sfx('clank', b, 0.32) for b in BONKS]; sfx('hit', T['ceiling'] - 0.1, 0.3)
    sfx('pop', T['rheuma'], 0.15); sfx('pop', T['x600ern'], 0.12); sfx('ding', T['weniger'], 0.12); sfx('pop', T['magen'], 0.15); sfx('hit', T['preis'], 0.25)
    rv = BT['reveal']; x2 = np.arange(int(rv['dur'] * SR)) / SR; riser = (np.random.RandomState(1).randn(len(x2)) * 0.3 + np.sin(2 * np.pi * (200 + 900 * x2 / rv['dur']) * x2)) * (x2 / rv['dur']) ** 2
    synth(rv['t'], riser, 0.18); sfx('ding', rv['t'] + rv['dur'], 0.3); sfx('shine', T['studien'], 0.15); sfx('ding', T['apotheke'], 0.15); sfx('pop', T['sags'] + 0.3, 0.15)
    if os.environ.get('MUSIC') == '1':          # musique de fond : désactivée par défaut (voix + effets seulement)
        mus = TMP + '/m.wav'; subprocess.run([sys.executable, '/home/user/skillora./temu/tools/popbeat.py', str(DUR), mus, '19', '98', '57'], check=True, capture_output=True)
        wm = wave.open(mus); m = np.frombuffer(wm.readframes(wm.getnframes()), '<i2').astype(float) / 32768; m = np.pad(m, (0, max(0, N - len(m))))[:N]
        env = np.convolve(np.abs(np.pad(VOICE, (0, max(0, N - len(VOICE))))[:N]) > 0.02, np.ones(int(0.25 * SR)) / int(0.25 * SR), 'same')
        mix += m / max(1e-6, np.abs(m).max()) * (0.07 - 0.035 * np.clip(env * 3, 0, 1))
    fd = int(0.8 * SR); mix[-fd:] *= np.linspace(1, 0, fd); mix = mix / max(1e-6, np.abs(mix).max()) * 0.95
    wo = wave.open(f'{TMP}/a.wav', 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((mix * 32767).astype('<i2').tobytes()); wo.close()
    subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{TMP}/f%05d.jpg', '-i', f'{TMP}/a.wav', '-c:v', 'libx264', '-preset', 'slow', '-crf', '15', '-tune', 'animation',
                    '-pix_fmt', 'yuv420p', '-r', str(FPS), '-c:a', 'aac', '-b:a', '256k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
    shutil.rmtree(TMP); print('ok', OUT, round(DUR, 2))
