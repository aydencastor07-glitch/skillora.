# Vidéo explicative « Winterreifen von O bis O? » – même moteur que le rasage : même feuille du début à la fin, sans transition
# glissée : l'ancien dessin s'efface vite et le suivant se dessine trait par trait. Images envoyées directement à ffmpeg.
# usage : explain_winterreifen.py dossier sortie.mp4  [PREVIEW=t1,t2,...] [K=1 (1080p, défaut) | K=2 (4K)] [TAIL=0.5]
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
# ---------- repères temporels
T = dict(oktober=tw('oktober'), ostern=tw('ostern'), winterreifen=tw('winterreifen'), bussgeld=tw('bußgeld'), hab=tw('hab'), quatsch=tw('quatsch'), in_=tw('in'),
         datum=tw('datum'), o=tw('o'), faustregel=tw('faustregel'), gesetz=tw('gesetz'), paragraf=tw('paragraf'), stvo=tw('straßenverkehrsordnung'), sobald=tw('sobald'),
         glatteis=tw('glatteis'), schnee=tw('schnee'), matsch=tw('schneematsch'), reif=tw('reifglätte'), winter1=tw('winterreifen', 1), egal=tw('egal'), okt2=tw('oktober', 1),
         april=tw('april'), mai=tw('mai'), heisst=tw('heißt'), januar=tw('januar'), sommer=tw('sommerreifen'), aber=tw('aber', 1), nacht=tw('nacht'), friert=tw('friert'),
         dann=tw('dann'), e60=tw('60'), punkt=tw('punkt'), flensburg=tw('flensburg'), behinderst=tw('behinderst'), e80=tw('80'), unfall=tw('unfall'), e120=tw('120'),
         versicherung=tw('versicherung'), kuerzen=tw('kürzen'), jetzt=tw('jetzt'), seit=tw('seit'), j2024=tw('2024'), ms=tw('ms-zeichen'), ueberhaupt=tw('überhaupt'),
         als=tw('als'), symbol=tw('symbol'), berg=tw('berg'), drei=tw('drei'), flocke=tw('schneeflocke'), alpine=tw('alpine-symbol'), steht=tw('steht', 1), ms2=tw('ms'),
         sommer2=tw('sommerreifen', 1), also=tw('also'), heute=tw('heute'), flanke=tw('reifenflanke'), such=tw('such'), dot=tw('dot-nummer'), letzten=tw('letzten'),
         woche=tw('woche'), herstellung=tw('herstellung'), aelter=tw('älter'), acht=tw('acht'), gummi=tw('gummi'), hart=tw('hart'), greift=tw('greift'), beim=tw('beim'),
         profil=tw('profil'), m16=tw('16'), erlaubt=tw('erlaubt'), experten=tw('experten'), vier2=tw('vier', 1), lieber=tw('lieber'), fuenf=tw('fünf'), graben=tw('graben'), sags=tw("sag's"))
for k, v in T.items():
    if v is None: print('mot introuvable :', k)
SC = [0, T['in_'] - 0.12, T['heisst'] - 0.12, T['jetzt'] - 0.3, T['also'] - 0.12, T['beim'] - 0.12, T['sags'] - 0.12, DUR]
SOURCES = [(T['gesetz'] - 0.1, T['heisst'] - 0.3, 'Quelle: § 2 Abs. 3a StVO'), (T['dann'] - 0.1, T['jetzt'] - 0.5, 'Quelle: Bußgeldkatalog (BKatV)'),
           (T['seit'] - 0.1, T['also'] - 0.3, 'Quelle: BMDV · ADAC'), (T['such'] - 0.1, T['lieber'] - 0.3, 'Quelle: ADAC')]
# ---------- caméra : très léger zoom continu + petits zooms d'impact (pas de transition glissée)
PUNCH = [(T['quatsch'], 0.06), (T['paragraf'], 0.04), (T['e60'], 0.05), (T['e120'], 0.05), (T['ueberhaupt'], 0.06), (T['alpine'], 0.04), (T['acht'], 0.04), (T['vier2'], 0.04)]
SHAKE = [(T['quatsch'], 12), (T['ueberhaupt'], 10)]
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
HOT = re.compile(r'(\d|quatsch|winterreifen|sommerreifen|datum|faustregel|gesetz|glatteis|schnee|reifglätte|friert|euro|punkt|flensburg|unfall|versicherung|symbol|schneeflocke|alpine|dot|hart|profil|millimeter|graben|bußgeld)', re.I)
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
    if sc == 0:   # « O bis O » : octobre → Pâques, pneu hiver, amende ? → croix rouge « Quatsch »
        calendar(img, d, 290, 640, 'Okt', sc_(t, 'oktober', -0.2, 0.4), BLUE); calendar(img, d, 790, 640, 'Ostern', sc_(t, 'ostern', -0.2, 0.4), GREEN)
        arrow(d, 410, 640, 670, 640, INK, 7, sc_(t, 'ostern', -0.3, 0.4))
        tire(d, CX, 980, 170, sc_(t, 'winterreifen', -0.2, 0.7), t * 2.2, flake=sc_(t, 'winterreifen', 0.4))
        if T['bussgeld'] and t > T['bussgeld'] - 0.2: k = sc_(t, 'bussgeld', -0.2, 0.3); text(img, (850, 1000), '€ ?', BF(96), RED, k, rot=-8, scale=1.4 - 0.4 * k)
        if T['hab'] and t > T['hab'] - 0.2: text(img, (CX, 470), 'O bis O?', H2(84), INK, sc_(t, 'hab', -0.2, 0.3))
        if T['quatsch'] and t > T['quatsch'] - 0.05:
            cross(d, CX, 800, 300, sc_(t, 'quatsch', -0.05, 0.35), RED, 18)
            k = since(t, T['quatsch'], 0.2); text(img, (CX, 1230), 'Quatsch!', BF(110), RED, k, rot=-6, scale=1.5 - 0.5 * k)
    elif sc == 1:  # pas de date dans la loi ; § 2 StVO ; glace, neige, gadoue, givre → pneus hiver ; même en octobre, avril, mai
        def nodate(lay, dl):
            calendar(lay, dl, CX, 720, '', clamp(u0 / 0.4), RED, 1.6); k = sc_(t, 'datum', -0.3, 0.3)
            text(lay, (CX, 760), '?', BF(150), RED, k, scale=1.5 - 0.5 * k); text(lay, (CX, 1000), 'kein festes Datum', BF(62), INK, sc_(t, 'datum', -0.2, 0.3))
            if T['o'] and t > T['o'] - 0.2:
                k2 = sc_(t, 'faustregel', -0.3, 0.3); text(lay, (CX, 1140), '„O bis O“ = nur Faustregel', H2(64), GREY, sc_(t, 'o', -0.2, 0.3)); underline(dl, CX - 300, CX + 300, 1190, RED, k2, 7)
        sub(img, gone(t, T['gesetz'] - 0.1), nodate)
        def law(lay, dl):
            k = sc_(t, 'gesetz', -0.2, 0.4); q = back(k); w, h = 380 * q, 460 * q
            if k > 0:
                dl.rounded_rectangle([S(CX - w / 2), S(800 - h / 2), S(CX + w / 2), S(800 + h / 2)], S(20), fill=(130, 40, 40, 255), outline=INK, width=S(7))
                dl.rectangle([S(CX - w / 2 + 26 * q), S(800 - h / 2), S(CX - w / 2 + 42 * q), S(800 + h / 2)], fill=(90, 26, 26, 255))
            text(lay, (CX + 10, 760), '§ 2', BF(140), WHITE, sc_(t, 'paragraf', -0.2, 0.3), scale=1.3 - 0.3 * sc_(t, 'paragraf', -0.2, 0.3))
            text(lay, (CX + 10, 900), 'StVO', BF(70), (240, 210, 170), sc_(t, 'stvo', -0.1, 0.4)); text(lay, (CX, 1150), 'Straßenverkehrsordnung', H2(56), INK, sc_(t, 'stvo', 0.2, 0.4))
        if T['gesetz'] and t > T['gesetz'] - 0.3: sub(img, gone(t, T['sobald'] - 0.05), law)
        def weather(lay, dl):
            text(lay, (CX, 470), 'sobald auf der Straße …', H2(62), INK, sc_(t, 'sobald', -0.2, 0.3))
            cells = [('glatteis', 'Glatteis'), ('schnee', 'Schnee'), ('matsch', 'Schneematsch'), ('reif', 'Reifglätte')]
            for j, (k_, lab) in enumerate(cells):
                x, y = 300 + (j % 2) * 480, 640 + (j // 2) * 270; q = back(sc_(t, k_, -0.2, 0.4))
                if q <= 0.02: continue
                dl.rounded_rectangle([S(x - 190 * q), S(y - 110 * q), S(x + 190 * q), S(y + 110 * q)], S(26), fill=(226, 238, 248, 255), outline=INK, width=S(6))
                if j == 0: road(dl, x - 150 * q, x + 150 * q, y - 50 * q, 1, 1.0, t)
                elif j == 1: [snowflake(dl, x - 90 + i * 90, y - 40 + 25 * math.sin(t * 2 + i), 24 * q, BLUE, 5) for i in range(3)]
                elif j == 2: dl.ellipse([S(x - 140 * q), S(y - 60 * q), S(x + 140 * q), S(y + 10 * q)], fill=(150, 140, 125, 255)); snowflake(dl, x + 60, y - 30, 20 * q, WHITE, 4)
                else: [snowflake(dl, x - 110 + i * 55, y - 30, 12 * q, (150, 190, 230), 3) for i in range(5)]
                text(lay, (x, y + 65 * q), lab, BF(44 * q), INK)
            if T['winter1'] and t > T['winter1'] - 0.3:
                k = sc_(t, 'winter1', -0.3, 0.6); tire(dl, CX, 1170, 105, k, t * 2, flake=sc_(t, 'winter1', 0.2)); check(dl, CX + 200, 1170, 45, sc_(t, 'winter1', 0.3, 0.4))
                text(lay, (CX - 260, 1170), 'nur mit', H2(56), INK, k)
        if T['sobald'] and t > T['sobald'] - 0.3: sub(img, gone(t, T['egal'] - 0.1), weather)
        if T['egal'] and t > T['egal'] - 0.2:
            text(img, (CX, 480), 'egal wann!', BF(84), RED, sc_(t, 'egal', -0.2, 0.3), scale=1.3 - 0.3 * sc_(t, 'egal', -0.2, 0.3))
            for j, (k_, lab) in enumerate((('okt2', 'Okt'), ('april', 'April'), ('mai', 'Mai'))):
                x = 240 + j * 300; calendar(img, d, x, 760, lab, sc_(t, k_, -0.2, 0.4), BLUE)
                if T[k_] and t > T[k_]:
                    for i in range(4): yy = 900 + ((t - T[k_]) * 120 + i * 70) % 300; snowflake(d, x - 60 + i * 40, yy, 16, BLUE, 4)
    elif sc == 2:  # janvier sec = pneus été OK ; la nuit ça gèle ; 60 € + 1 point, 80 €, 120 € ; l'assurance réduit
        def dry(lay, dl):
            calendar(lay, dl, 260, 560, 'Januar', sc_(t, 'januar', -0.3, 0.4), BLUE); sun(dl, 800, 560, 70, t, sc_(t, 'januar', 0.0, 0.4) * gone(t, T['nacht'] - 0.1))
            k = since(t, T['heisst'] - 0.1, 0.5); road(dl, 120, 960, 1100, k, ice=since(t, T['friert'] - 0.1, 0.8) if T['friert'] else 0, t=t)
            car(dl, CX, 1010, 0.9, sc_(t, 'sommer', -0.3, 0.5)); text(lay, (CX, 820), 'trocken = Sommerreifen ok', H2(58), GREEN, sc_(t, 'sommer', -0.1, 0.3) * gone(t, T['aber'] + 0.1))
            if T['aber'] and t > T['aber'] - 0.1:
                moon(dl, 800, 560, 60, sc_(t, 'nacht', -0.2, 0.4)); text(lay, (CX, 820), 'über Nacht: Glätte!', BF(62), BLUE, sc_(t, 'friert', -0.1, 0.3))
                for i in range(6): snowflake(dl, 180 + i * 140, 680 + ((t - T['aber']) * 90 + i * 40) % 300, 14, BLUE, 4)
        sub(img, gone(t, T['dann'] - 0.05), dry)
        def fines(lay, dl):
            ty = 720 - 120 * sc_(t, 'behinderst', -0.2, 0.4)
            ticket(lay, dl, CX, ty, sc_(t, 'e60', -0.4, 0.4), '60 €', '+ 1 Punkt' if T['punkt'] and t > T['punkt'] - 0.1 else '')
            if T['flensburg'] and t > T['flensburg'] - 0.1: text(lay, (CX + 250, ty + 190), 'Flensburg', H2(54), RED, sc_(t, 'flensburg', -0.1, 0.3) * gone(t, T['behinderst'] - 0.05), rot=-8)
            if T['behinderst'] and t > T['behinderst'] - 0.2:
                for j, (k_, val, lab, col) in enumerate((('e60', 60, 'Glätte', INK), ('e80', 80, 'behindert', (210, 120, 40)), ('e120', 120, 'Unfall', RED))):
                    x = 270 + j * 270; q = sc_(t, k_ if j else 'behinderst', -0.1, 0.5); h = 260 * val / 120 * ease(q)
                    if h > 4: dl.rounded_rectangle([S(x - 70), S(1150 - h), S(x + 70), S(1150)], S(12), fill=col + (255,), outline=INK, width=S(5))
                    text(lay, (x, 1150 - h - 40), f'{val} €', BF(52), col, q); text(lay, (x, 1195), lab, H2(46), INK, q)
        if T['dann'] and t > T['dann'] - 0.2: sub(img, gone(t, T['versicherung'] - 0.25), fines)
        if T['versicherung'] and t > T['versicherung'] - 0.3:
            shield(img, d, CX, 760, 1.2, sc_(t, 'versicherung', -0.3, 0.45)); text(img, (CX, 1030), 'Versicherung', BF(60), BLUE, sc_(t, 'versicherung', -0.1, 0.3))
            if T['kuerzen'] and t > T['kuerzen'] - 0.2:
                k = sc_(t, 'kuerzen', -0.2, 0.3); line(d, CX - 230, 600, CX + 230, 940, RED, 14, k); text(img, (CX, 1140), 'zahlt weniger', H2(66), RED, k)
    elif sc == 3:  # depuis 10/2024 : « M+S » seul ne compte plus ; seul le symbole montagne + flocon ; « M+S » seul = pneu été
        def ms(lay, dl):
            tire(dl, CX, 860, 300, clamp(u0 / 0.5), 0.2)
            k = sc_(t, 'seit', -0.2, 0.3); dl.rounded_rectangle([S(CX - 260 * back(k)), S(440), S(CX + 260 * back(k)), S(540)], S(26), fill=RED + (255,)) if k > 0.05 else None
            text(lay, (CX, 492), 'seit 10/2024', BF(62), WHITE, sc_(t, 'j2024', -0.3, 0.3))
            q = sc_(t, 'ms', -0.5, 0.35); text(lay, (CX - 225, 860), 'M+S', BF(66), (215, 215, 220), q, rot=72)
            if T['ueberhaupt'] and t > T['ueberhaupt'] - 0.2:
                cross(dl, CX - 225, 860, 80, sc_(t, 'ueberhaupt', -0.2, 0.35), RED, 14); text(lay, (CX, 1215), 'zählt nicht mehr!', BF(70), RED, sc_(t, 'ueberhaupt', 0.0, 0.3))
        sub(img, gone(t, T['als'] - 0.05), ms)
        def symbol(lay, dl):
            text(lay, (CX, 470), 'nur noch dieses Symbol:', H2(64), INK, sc_(t, 'als', -0.1, 0.3))
            alpine(dl, CX, 820, 270, sc_(t, 'berg', -0.3, 1.0), sc_(t, 'flocke', -0.2, 0.4))
            if T['drei'] and T['drei'] - 0.1 < t < T['flocke']:
                for j, (x, y) in enumerate(((-0.62, -0.15), (0, -0.85), (0.62, -0.15))):
                    if t > T['drei'] + j * 0.15: circ(dl, CX + x * 270, 820 + y * 270, 26, RED, None, 7)
            if T['alpine'] and t > T['alpine'] - 0.2:
                k = sc_(t, 'alpine', -0.2, 0.3); text(lay, (CX, 1150), 'Alpine-Symbol', BF(70), GREEN, k, scale=1.3 - 0.3 * k); check(dl, CX + 345, 1150, 40, sc_(t, 'alpine', 0.2, 0.4))
        if T['als'] and t > T['als'] - 0.2: sub(img, gone(t, T['steht'] - 0.1), symbol)
        if T['steht'] and t > T['steht'] - 0.2:
            tire(d, 330, 820, 190, sc_(t, 'steht', -0.2, 0.5), 0.2); text(img, (330 - 140, 820), 'M+S', BF(48), (215, 215, 220), sc_(t, 'ms2', -0.2, 0.3), rot=72)
            k = sc_(t, 'sommer2', -0.4, 0.4); text(img, (700, 760), '=', BF(110), INK, sc_(t, 'ms2', 0.1, 0.3)); sun(d, 860, 760, 60, t, k)
            text(img, (CX, 1120), 'rechtlich Sommerreifen', BF(62), RED, k)
    elif sc == 4:  # vérifier le flanc ; code DOT : semaine + année ; plus de 8 ans → gomme dure
        def look(lay, dl):
            text(lay, (CX, 470), 'heute checken', BF(72), INK, sc_(t, 'heute', -0.2, 0.3))
            tire(dl, 420, 880, 260, clamp(u0 / 0.5), 0.2); eye(dl, 870, 700, 1.0, sc_(t, 'flanke', -0.3, 0.4), t); arrow(dl, 830, 770, 690, 860, INK, 7, sc_(t, 'flanke', 0.0, 0.4))
            text(lay, (840, 1080), 'Reifenflanke', H2(58), INK, sc_(t, 'flanke', 0.0, 0.3))
        sub(img, gone(t, T['such'] - 0.05), look)
        def dot(lay, dl):
            k = sc_(t, 'such', -0.2, 0.4); q = back(k)
            if k > 0.02: dl.rounded_rectangle([S(CX - 430 * q), S(700 - 95 * q), S(CX + 430 * q), S(700 + 95 * q)], S(30), fill=(52, 52, 58, 255), outline=INK, width=S(6))
            text(lay, (300, 700), 'DOT', BF(74), (205, 205, 210), k); text(lay, (520, 700), 'XK9T', BF(74), (205, 205, 210), k)
            hi = sc_(t, 'letzten', -0.1, 0.3)
            if hi > 0: dl.rounded_rectangle([S(680), S(630), S(940), S(770)], S(18), outline=YEL + (255,), width=S(8))
            text(lay, (760, 700), '45', BF(74), mix((205, 205, 210), YEL, hi), k); text(lay, (870, 700), '18', BF(74), mix((205, 205, 210), YEL, hi), k)
            magnifier(dl, 810, 700, 150, sc_(t, 'dot', -0.2, 0.4))
            if T['woche'] and t > T['woche'] - 0.2: text(lay, (560, 940), 'Woche 45', BF(58), INK, sc_(t, 'woche', -0.2, 0.3)); arrow(dl, 700, 900, 755, 790, INK, 6, sc_(t, 'woche', 0, 0.3))
            if T['herstellung'] and t > T['herstellung'] - 0.6: text(lay, (900, 1040), '= 2018', BF(58), INK, sc_(t, 'herstellung', -0.6, 0.3)); arrow(dl, 900, 990, 875, 790, INK, 6, sc_(t, 'herstellung', -0.5, 0.3))
        if T['such'] and t > T['such'] - 0.3: sub(img, gone(t, T['aelter'] - 0.05), dot)
        if T['aelter'] and t > T['aelter'] - 0.2:
            k = sc_(t, 'aelter', -0.2, 0.3); text(img, (CX, 480), 'älter als 8 Jahre?', BF(72), RED, k, scale=1.3 - 0.3 * k)
            hd = sc_(t, 'hart', -0.4, 0.8); tire(d, CX, 790, 210, clamp((t - T['aelter'] + 0.2) / 0.4), 0.2, hard=hd)
            if T['hart'] and t > T['hart'] - 0.1: text(img, (CX, 790), 'hart', BF(80), WHITE, sc_(t, 'hart', -0.1, 0.3))
            if T['greift'] and t > T['greift'] - 0.2:
                q = sc_(t, 'greift', -0.2, 0.4); road(d, 140, 940, 1010, q, ice=1.0, t=t)
                for i in range(3): arrow(d, 300 + i * 200, 1110, 300 + i * 200 + 120 + 20 * math.sin(t * 8 + i), 1110, RED, 6, q, 20)
                text(img, (CX, 1190), 'greift schlechter', H2(60), RED, q)
    elif sc == 5:  # profil : 1,6 mm autorisé / 4 mm conseillé ; 5 minutes maintenant plutôt que le fossé
        def prof(lay, dl):
            text(lay, (CX, 470), 'Profiltiefe', BF(72), INK, clamp(u0 / 0.3))
            tread(lay, dl, 90, 700, 22, sc_(t, 'm16', -0.3, 0.5), RED, '1,6 mm', 'erlaubt')
            tread(lay, dl, 630, 700, 62, sc_(t, 'experten', -0.2, 0.5), GREEN, '4 mm', 'empfohlen')
            if T['vier2'] and t > T['vier2'] - 0.1: check(dl, 980, 600, 40, sc_(t, 'vier2', -0.1, 0.4))
        sub(img, gone(t, T['lieber'] - 0.05), prof)
        if T['lieber'] and t > T['lieber'] - 0.2:
            clock(d, 300, 760, 120, t * 3, 10, sc_(t, 'lieber', -0.2, 0.4)); text(img, (300, 950), '5 Minuten', BF(56), GREEN, sc_(t, 'fuenf', -0.1, 0.3)); check(d, 300, 1050, 40, sc_(t, 'fuenf', 0.3, 0.4))
            if T['graben'] and t > T['graben'] - 0.5:
                k = sc_(t, 'graben', -0.5, 0.4); arc(d, 780, 860, 170, 10, 170, INK, 8) if k > 0.3 else None
                car(d, 780, 860, 0.62, k, rot=24 * ease(k), col=RED); cross(d, 780, 860, 150, sc_(t, 'graben', 0.1, 0.35), RED, 12); text(img, (780, 1050), 'Graben', H2(56), RED, k)
            text(img, (CX, 1220), 'lieber jetzt checken', BF(62), INK, sc_(t, 'lieber', 0.2, 0.3))
    elif sc == 6:  # partage
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
    sfx('pop', T['oktober'] - 0.2, 0.1); sfx('pop', T['ostern'] - 0.2, 0.1); sfx('whoosh', T['winterreifen'] - 0.2, 0.12); sfx('pop', T['bussgeld'] - 0.2, 0.12)
    sfx('hit', T['quatsch'] - 0.03, 0.4); sfx('swish', T['quatsch'] - 0.05, 0.2); sfx('pop', T['datum'] - 0.3, 0.12); sfx('tap', T['faustregel'], 0.1)
    sfx('thud', T['gesetz'] - 0.2, 0.2); sfx('pop', T['paragraf'] - 0.2, 0.12)
    for k in ('glatteis', 'schnee', 'matsch', 'reif'): sfx('pop', T[k] - 0.2, 0.12)
    sfx('ding', T['winter1'] + 0.3, 0.1); sfx('hit', T['egal'] - 0.2, 0.15)
    for k in ('okt2', 'april', 'mai'): sfx('tap', T[k] - 0.2, 0.12)
    sfx('shine', T['januar'], 0.1); sfx('ding', T['sommer'], 0.1); sfx('whoosh', T['nacht'] - 0.2, 0.1); sfx('glitch', T['friert'], 0.06)
    sfx('hit', T['e60'] - 0.4, 0.25); sfx('pop', T['punkt'], 0.12); sfx('pop', T['e80'] - 0.1, 0.12); sfx('hit', T['e120'] - 0.1, 0.2)
    sfx('pop', T['versicherung'] - 0.3, 0.12); sfx('cut1', T['kuerzen'] - 0.2, 0.15)
    sfx('pop', T['seit'] - 0.2, 0.12); sfx('hit', T['ueberhaupt'] - 0.2, 0.3); sfx('shine', T['flocke'] - 0.2, 0.12); sfx('ding', T['alpine'] + 0.2, 0.12)
    sfx('pop', T['steht'] - 0.2, 0.1); sfx('buzz', T['sommer2'] - 0.4, 0.07); sfx('pop', T['flanke'] - 0.3, 0.1); sfx('pop', T['such'] - 0.2, 0.12)
    sfx('ding', T['letzten'], 0.1); sfx('hit', T['aelter'] - 0.2, 0.2); sfx('clank', T['hart'] - 0.1, 0.15); sfx('swish', T['greift'] - 0.2, 0.15)
    sfx('pop', T['m16'] - 0.3, 0.12); sfx('pop', T['experten'] - 0.2, 0.12); sfx('ding', T['vier2'], 0.12); sfx('tap', T['lieber'] - 0.2, 0.12)
    sfx('thud', T['graben'] - 0.3, 0.2); sfx('pop', T['sags'] + 0.3, 0.15)
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
