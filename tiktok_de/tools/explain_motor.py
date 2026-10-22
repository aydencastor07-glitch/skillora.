# Vidéo explicative « Motor warmlaufen lassen? » – même feuille du début à la fin, sans transition glissée :
# l'ancien dessin s'efface vite et le suivant se dessine trait par trait (comme la vidéo de référence).
# Mots calés par align_tts.py (words_final.json). Voix gardée intacte.
# usage : explain_motor.py dossier sortie.mp4  [PREVIEW=t1,t2,...] [AUDIO_ONLY=1] [MINDUR=61.5]
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
DUR = max(len(VOICE) / SR + 1.0, float(os.environ.get('MINDUR', 0)))      # MINDUR : durée minimale (récompenses TikTok > 60 s)
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
def car(img, d, cx, cy, s, p, t, ice=0.0, smoke=0.0, move=0.0):
    # voiture vue de côté (vers la droite) : carrosserie, vitres (givrées), roues, fumée d'échappement
    if p <= 0: return
    cx += move
    body = [(-240, -12), (-246, -72), (-200, -88), (-122, -96), (-72, -166), (72, -166), (132, -96), (222, -82), (252, -52), (252, -12)]
    P = lambda pts: [(cx + x * s, cy + y * s) for x, y in pts]
    if p >= 0.6: d.polygon([(S(x), S(y)) for x, y in P(body)], fill=WHITE + (255,))
    poly(d, P(body), INK, 7, ease(p / 0.6), closed=True)
    if p >= 0.6:
        win = [(-60, -152), (58, -152), (108, -102), (-104, -102)]
        wc = tuple(int(c1 + (c2 - c1) * ice) for c1, c2 in zip((200, 220, 235), (240, 248, 252)))
        d.polygon([(S(x), S(y)) for x, y in P(win)], fill=wc + (255,)); poly(d, P(win), INK, 5, closed=True); line(d, *P([(-2, -152)])[0], *P([(-2, -102)])[0], INK, 5)
        if ice > 0.05:   # givre : petites étoiles sur les vitres + neige sur le toit
            for k, (x, y) in enumerate([(-50, -130), (-20, -118), (30, -136), (70, -118), (88, -110)]):
                X, Y = P([(x, y)])[0]; r = 9 * s * ice
                for a in range(3): line(d, X - r * math.cos(a * 1.05), Y - r * math.sin(a * 1.05), X + r * math.cos(a * 1.05), Y + r * math.sin(a * 1.05), COLD, 3)
            snow = P([(-80, -166), (-60, -184), (-20, -190), (30, -188), (70, -180), (84, -166)]); d.polygon([(S(x), S(y)) for x, y in snow], fill=(255, 255, 255, int(255 * ice))); poly(d, snow, GREY, 4, ice)
    for wx in (-142, 152):
        X, Y = P([(wx, 0)])[0]; circ(d, X, Y, 50 * s * ease(p), INK, (70, 64, 60, 255), 6)
        if p > 0.8: circ(d, X, Y, 20 * s, None, (200, 195, 190, 255))
    if smoke > 0:   # bouffées qui sortent du pot et s'envolent vers la gauche
        ex, ey = P([(-250, -24)])[0]; line(d, ex, ey, ex - 26 * s, ey, INK, 8)
        for k in range(5):
            q = ((t * 0.55 + k / 5) % 1); r = (16 + 42 * q) * s
            circ(d, ex - 40 * s - 200 * q * s, ey - 30 * q * s, r, None, SMOKE + (int(170 * (1 - q) * smoke),))
def gauge(img, d, cx, cy, r, val, p, lo='C', hi='H', red_from=None, label=None, nums=None):
    # cadran demi-cercle : graduations, zone rouge, aiguille
    if p <= 0: return
    arc(d, cx, cy, r, 180, 180 + 180 * ease(p), INK, 9)
    if red_from is not None and p > 0.7: arc(d, cx, cy, r - 16, 180 + 180 * red_from, 360, RED, 14)
    if p < 0.7: return
    for k in range(9):
        a = math.radians(180 + k * 22.5); line(d, cx + (r - 34) * math.cos(a), cy + (r - 34) * math.sin(a), cx + (r - 8) * math.cos(a), cy + (r - 8) * math.sin(a), INK, 5 if k % 2 == 0 else 3)
    if nums:
        for k, n in enumerate(nums): a = math.radians(180 + 180 * k / (len(nums) - 1)); text(img, (cx + (r - 70) * math.cos(a), cy + (r - 70) * math.sin(a)), n, BF(r * 0.12), INK)
    else:
        text(img, (cx - r + 10, cy + 44), lo, BF(r * 0.2), COLD); text(img, (cx + r - 10, cy + 44), hi, BF(r * 0.2), RED)
    a = math.radians(180 + 180 * clamp(val)); line(d, cx, cy, cx + (r - 50) * math.cos(a), cy + (r - 50) * math.sin(a), RED, 9); circ(d, cx, cy, 18, None, INK + (255,))
    if label: text(img, (cx, cy + 100), label, H2(r * 0.26), INK)
def clock(d, cx, cy, r, t, speed, p):
    if p <= 0: return
    arc(d, cx, cy, r, -90, -90 + 360 * ease(p), INK, 8)
    if p < 0.8: return
    for k in range(12): a = k * math.pi / 6; line(d, cx + (r - 22) * math.cos(a), cy + (r - 22) * math.sin(a), cx + (r - 8) * math.cos(a), cy + (r - 8) * math.sin(a), INK, 4)
    a1 = t * speed - math.pi / 2; a2 = t * speed / 12 - math.pi / 2
    line(d, cx, cy, cx + r * 0.75 * math.cos(a1), cy + r * 0.75 * math.sin(a1), INK, 6); line(d, cx, cy, cx + r * 0.5 * math.cos(a2), cy + r * 0.5 * math.sin(a2), INK, 9)
def engine(img, d, cx, cy, s, p, heat=0.0, t=0):
    # bloc moteur : carter, culasse, 3 cylindres ; couleur du bleu (froid) au rouge (chaud)
    if p <= 0: return
    col = tuple(int(c1 + (c2 - c1) * heat) for c1, c2 in zip((205, 222, 240), (246, 196, 170)))
    if p > 0.6: d.rounded_rectangle([S(cx - 170 * s), S(cy - 110 * s), S(cx + 170 * s), S(cy + 120 * s)], S(22 * s), fill=col + (255,))
    rect(d, cx - 170 * s, cy - 110 * s, cx + 170 * s, cy + 120 * s, INK, 7, ease(p / 0.6), 22 * s)
    if p > 0.6:
        rect(d, cx - 150 * s, cy - 170 * s, cx + 150 * s, cy - 110 * s, INK, 6, 1, 10, fill=WHITE + (255,))
        for k in (-1, 0, 1):
            y = cy + 10 * s + 14 * s * math.sin(t * (2 + 10 * heat) + k * 2.1)
            rect(d, cx + k * 95 * s - 34 * s, y - 50 * s, cx + k * 95 * s + 34 * s, y + 30 * s, INK, 5, 1, 8, fill=(235, 230, 222, 255))
        if heat > 0.4:
            for k in (-1, 0, 1): poly(d, [(cx + k * 80 * s + 10 * math.sin(t * 4 + y * 0.06), cy - 190 * s - y * s) for y in range(0, 90, 8)], RED, 5, (heat - 0.4) / 0.6)
def drop(d, cx, cy, r, col, stretch=1.0):
    d.ellipse([S(cx - r), S(cy - r), S(cx + r), S(cy + r)], fill=col + (255,))
    d.polygon([(S(cx - r * 0.92), S(cy - r * 0.35)), (S(cx), S(cy - r * (1.0 + 1.3 * stretch))), (S(cx + r * 0.92), S(cy - r * 0.35))], fill=col + (255,))
def gear(d, cx, cy, r, n, ang, col=INK, fill=(232, 226, 216)):
    pts = []
    for k in range(n * 4):
        a = ang + k * math.pi / (2 * n); rr = r if (k // 2) % 2 == 0 else r * 0.8; pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon([(S(x), S(y)) for x, y in pts], fill=fill + (255,)); poly(d, pts, col, 5, closed=True); circ(d, cx, cy, r * 0.25, col, WHITE + (255,), 5)
def ticket(img, d, cx, cy, s, rot=0):
    lay = Image.new('RGBA', (S(420 * s), S(260 * s)), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    dl.rounded_rectangle([S(6), S(6), S(414 * s), S(254 * s)], S(14), fill=WHITE + (255,), outline=INK, width=S(6))
    dl.rectangle([S(6), S(6), S(414 * s), S(64 * s)], fill=RED + (255,))
    f = BF(40 * s); dl.text((S(210 * s), S(36 * s)), 'BUSSGELD', font=f, fill=WHITE, anchor='mm')
    dl.text((S(210 * s), S(160 * s)), '10 €', font=BF(96 * s), fill=INK, anchor='mm')
    lay = lay.rotate(rot, expand=True, resample=Image.BICUBIC); comp(img, lay, S(cx) - lay.width / 2, S(cy) - lay.height / 2)
def chip(img, d, cx, cy, s, p):
    if p <= 0: return
    q = back(p); a = 110 * s * q
    for k in range(5):
        o = -a + (k + 0.5) * 2 * a / 5
        for (x0, y0, x1, y1) in ((cx + o, cy - a, cx + o, cy - a - 30 * s), (cx + o, cy + a, cx + o, cy + a + 30 * s), (cx - a, cy + o, cx - a - 30 * s, cy + o), (cx + a, cy + o, cx + a + 30 * s, cy + o)): line(d, x0, y0, x1, y1, INK, 6)
    d.rounded_rectangle([S(cx - a), S(cy - a), S(cx + a), S(cy + a)], S(16), fill=(60, 66, 74, 255), outline=INK, width=S(6))
    d.rounded_rectangle([S(cx - a * 0.55), S(cy - a * 0.55), S(cx + a * 0.55), S(cy + a * 0.55)], S(8), outline=(120, 200, 140), width=S(4))
def carb(img, d, cx, cy, s, p):
    # vieux carburateur : entonnoir + corps + petite vis de réglage
    if p <= 0: return
    poly(d, [(cx - 110 * s, cy - 150 * s), (cx - 45 * s, cy - 40 * s), (cx + 45 * s, cy - 40 * s), (cx + 110 * s, cy - 150 * s)], INK, 7, ease(p))
    if p > 0.5:
        rect(d, cx - 75 * s, cy - 40 * s, cx + 75 * s, cy + 110 * s, INK, 7, 1, 10, fill=(214, 200, 176, 255)); line(d, cx + 75 * s, cy + 30 * s, cx + 150 * s, cy + 30 * s, INK, 8)
        circ(d, cx + 160 * s, cy + 30 * s, 16 * s, INK, WHITE + (255,), 5); line(d, cx - 75 * s, cy + 110 * s, cx - 75 * s, cy + 170 * s, INK, 7); line(d, cx + 75 * s, cy + 110 * s, cx + 75 * s, cy + 170 * s, INK, 7)
def scraper(d, cx, cy, s, ang):
    a = math.radians(ang); ca, sa = math.cos(a), math.sin(a)
    P = lambda x, y: (cx + (x * ca - y * sa) * s, cy + (x * sa + y * ca) * s)
    d.polygon([(S(x), S(y)) for x, y in (P(-70, -20), P(70, -20), P(50, 20), P(-50, 20))], fill=(250, 210, 60, 255)); poly(d, [P(-70, -20), P(70, -20), P(50, 20), P(-50, 20)], INK, 5, closed=True)
    line(d, *P(0, 20), *P(0, 150), INK, 16); line(d, *P(0, 20), *P(0, 150), (60, 120, 200), 10)
def share(img, d, cx, cy, p):
    for (x, y) in ((cx - 170, cy), (cx + 150, cy - 140), (cx + 150, cy + 140)): arc(d, x, y, 62, -90, -90 + 360 * ease(p), INK, 9)
    line(d, cx - 115, cy - 25, cx + 95, cy - 115, INK, 8, ease(p - 0.4)); line(d, cx - 115, cy + 25, cx + 95, cy + 115, INK, 8, ease(p - 0.4))
# ---------- repères temporels
T = dict(winter=tw('winter'), minuten=tw('minuten'), warmlaufen=tw('warmlaufen'), kaputt=tw('kaputt'), gedacht=tw('gedacht'), quatsch=tw('quatsch'), stand=tw('stand'),
         kaum=tw('kaum'), leerlauf=tw('leerlauf'), last=tw('last'), ewig=tw('ewig'), temperatur=tw('temperatur'), solange=tw('solange'), oel=tw('öl'), honig=tw('honig'),
         teile=tw('teile'), verschleisst=tw('verschleißt'), laesst=tw('lässt'), kaltphase=tw('kaltphase'), dabei=tw('dabei'), halben=tw('halben'), stunde=tw('stunde'),
         null=tw('null'), km=tw('kilometer'), kat=tw('katalysator'), kalt2=tw('kalt', 1), garnicht=tw('nicht'), abgase=tw('abgase'), ungefiltert=tw('ungefiltert'),
         jetzt=tw('jetzt'), deutschland=tw('deutschland'), verboten=tw('verboten'), unnoetig=tw('unnötiges'), paragraf=tw('paragraf'), stvo=tw('straßenverkehrsordnung'),
         kostet=tw('kostet'), euro=tw('euro'), scheiben=tw('scheiben'), freikratzt=tw('freikratzt'), woher=tw('woher'), mythos=tw('mythos'), frueher=tw('früher'),
         vergaser=tw('vergaser-motoren'), sinnvoll=tw('sinnvoll'), heute=tw('heute'), elektronik=tw('elektronik'), also=tw('also'), freikratzen=tw('freikratzen'),
         einsteigen=tw('einsteigen'), starten=tw('starten'), losfahren=tw('losfahren'), ersten=tw('ersten'), sanft=tw('sanft'), drehzahlen=tw('drehzahlen'), vollgas=tw('vollgas'),
         schnellsten=tw('schnellsten'), sparst=tw('sparst'), nerven=tw('nerven'), sags=tw("sag's"))
for k, v in T.items():
    if v is None: print('mot introuvable :', k)
SC = [0, T['stand'] - 0.2, T['solange'] - 0.35, T['dabei'] - 0.12, T['kat'] - 0.55, T['jetzt'] - 0.25, T['woher'] - 0.12, T['also'] - 0.12, T['sags'] - 0.12, DUR]
# ---------- caméra : très léger zoom continu + petits zooms d'impact (pas de transition glissée)
PUNCH = [(T['quatsch'], 0.06), (T['verschleisst'], 0.04), (T['null'], 0.05), (T['verboten'], 0.07), (T['euro'], 0.05), (T['vollgas'], 0.04)]
SHAKE = [(T['quatsch'], 12), (T['verboten'], 18), (T['euro'] + 0.25, 10)]
def camera(t, sc):
    a0, a1 = SC[sc], SC[sc + 1]; z = 1.02 + 0.025 * eio((t - a0) / max(1, a1 - a0))
    for t0, amp in PUNCH:
        if t0 and 0 <= t - t0 < 0.6: z += amp * math.exp(-(t - t0) * 7) * min(1, (t - t0) / 0.05)
    ox = oy = 0
    for t0, amp in SHAKE:
        if t0 and 0 <= t - t0 < 0.4: k = (1 - (t - t0) / 0.4) ** 2; ox += amp * k * math.sin((t - t0) * 95); oy += amp * k * math.cos((t - t0) * 83)
    return z, 0.5, 0.42, ox, oy
# ---------- texture papier + vignette (fixes, appliquées après la caméra)
_rs = np.random.RandomState(7); NOISE = np.asarray(Image.fromarray((_rs.normal(128, 9, (H, W))).clip(0, 255).astype('uint8')).filter(ImageFilter.GaussianBlur(0.8))).astype(np.int16) - 128
yy, xx = np.mgrid[0:H, 0:W]; VIG = (1 - 0.10 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H * 0.45) / (H * 0.6)) ** 2)).clip(0.82, 1)[..., None]
# ---------- sous-titres : 3 mots max, mot actif qui « pop », mots clés en jaune
HOT = re.compile(r'(\d|quatsch|motor|leerlauf|warm|kalt|öl|honig|verschleißt|sprit|liter|null|kilometer|katalysator|abgase|ungefiltert|verboten|paragraf|euro|vergaser|elektronik|losfahren|sanft|vollgas|drehzahl|nerven|winter|temperatur|ewig)', re.I)
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
# ---------- les scènes (tout se dessine sur la même feuille)
def scene(img, d, sc, t):
    CX = W / 2; u0 = t - SC[sc]
    if sc == 0:   # voiture givrée qui tourne au ralenti, minuteur « 5 min », puis croix rouge sur « Quatsch »
        car(img, d, CX, 1060, 1.45, u0 / 0.5, t, ice=1.0, smoke=since(t, T['warmlaufen'] - 0.2, 0.4))
        for k in range(14):   # flocons
            rs = np.random.RandomState(k); x = rs.uniform(120, 960); y = 420 + ((t * rs.uniform(40, 90) + rs.uniform(0, 600)) % 560)
            circ(d, x, y, rs.uniform(5, 10), None, (255, 255, 255, 230))
        if T['minuten'] and t > T['minuten'] - 0.2:
            k = since(t, T['minuten'] - 0.2, 0.4); clock(d, 790, 560, 95, t, 6, k); text(img, (790, 700), 'erst warmlaufen?', H2(60), INK, k)
        if T['kaputt'] and t > T['kaputt'] - 0.1: text(img, (330, 560), 'sonst kaputt?', H2(62), RED, since(t, T['kaputt'] - 0.1, 0.3) * gone(t, T['quatsch'] + 0.05))
        if T['quatsch'] and t > T['quatsch'] - 0.05:
            q = since(t, T['quatsch'] - 0.05, 0.35); cross(d, 790, 600, 130, q, RED, 14)
            text(img, (330, 600), 'Quatsch!', BF(96), RED, since(t, T['quatsch'], 0.2), rot=-6, scale=1.5 - 0.5 * since(t, T['quatsch'], 0.2))
    elif sc == 1:  # moteur au ralenti : jauge de température qui monte à peine, horloge « ewig »
        engine(img, d, 330, 900, 1.05, u0 / 0.5, heat=0.08, t=t)
        text(img, (330, 1110), 'im Stand', H2(64), INK, clamp((u0 - 0.3) / 0.3))
        val = 0.05 + 0.06 * clamp((t - SC[1]) / 6)
        gauge(img, d, 790, 840, 190, val, (u0 - 0.2) / 0.5, label='Motor-Temperatur')
        if T['leerlauf'] and t > T['leerlauf'] - 0.1:
            k = since(t, T['leerlauf'] - 0.1, 0.3); text(img, (330, 560), 'Leerlauf', BF(62), INK, k); text(img, (330, 630), '≈ 800 U/min'.replace('≈ ', '~ '), H2(52), GREY, k)
        if T['last'] and t > T['last'] - 0.1: text(img, (330, 1190), 'kaum Last', H2(56), GREY, since(t, T['last'] - 0.1, 0.3))
        if T['ewig'] and t > T['ewig'] - 0.15:
            k = since(t, T['ewig'] - 0.15, 0.35); clock(d, 790, 520, 80, t * 3, 9, k); text(img, (650, 520), 'ewig', H2(66), RED, k, anchor='rm')
    elif sc == 2:  # huile épaisse comme du miel, engrenages qui frottent, phase froide qui s'allonge
        A = gone(t, T['teile'] - 0.15); B = gone(t, T['laesst'] - 0.1) if t < T['laesst'] else 0
        def oil(lay, dl):
            k = clamp((t - SC[2]) / 0.4); rect(dl, 330, 470, 750, 560, INK, 7, k, 14, fill=(205, 205, 210, 255) if k >= 1 else None)
            text(lay, (540, 515), 'Öl', BF(54), INK, k)
            if T['kaltphase'] is not None and t > T['oel'] - 0.2:   # goutte de miel qui s'étire lentement
                q = clamp((t - T['oel']) / 3.2); y = 600 + 380 * q * q
                line(dl, 540, 560, 540, y - 40, OIL, 26); drop(dl, 540, y, 46, OIL, stretch=1.3)
            if T['honig'] and t > T['honig'] - 0.1: text(lay, (790, 820), 'zäh wie Honig', H2(64), BROWN, since(t, T['honig'] - 0.1, 0.3)); thermo = 0
            if T['kalt2'] is None or t > T['solange']: text(lay, (290, 820), 'kalt', BF(66), COLD, since(t, T['solange'] + 0.3, 0.3))
        sub(img, A, oil)
        if t > T['teile'] - 0.2 and t < T['laesst']:
            def gears(lay, dl):
                k = since(t, T['teile'] - 0.2, 0.4); sp = 0.6
                gear(dl, 420, 820, 150 * back(k), 12, t * sp); gear(dl, 670, 820, 110 * back(k), 9, -t * sp * 150 / 110 + 0.2)
                if T['verschleisst'] and t > T['verschleisst'] - 0.1:
                    v = since(t, T['verschleisst'] - 0.1, 0.3)
                    for j in range(8):
                        rs = np.random.RandomState(int(t * 20) + j); a = rs.uniform(-1, 1); r = rs.uniform(20, 90) * v
                        line(dl, 560, 760, 560 + r * math.cos(a - 1.57), 760 + r * math.sin(a - 1.57), (240, 140, 40), 5)
                    text(lay, (540, 1120), 'Verschleiß', BF(70), RED, v)
            sub(img, B, gears)
        if T['laesst'] and t > T['laesst'] - 0.1:   # barre « Kaltphase » : courte en roulant, longue à l'arrêt
            k = since(t, T['laesst'] - 0.1, 0.3); text(img, (150, 560), 'Kaltphase', H2(70), COLD, k, anchor='lm')
            text(img, (150, 700), 'fahren', BF(44), INK, k, anchor='lm'); d.rounded_rectangle([S(380), S(670), S(380 + 220 * ease(k)), S(730)], S(14), fill=COLD + (255,))
            q = since(t, T['laesst'] + 0.3, 2.0) if T['laesst'] else 0
            text(img, (150, 860), 'im Stand', BF(44), INK, k, anchor='lm'); d.rounded_rectangle([S(380), S(830), S(380 + 220 * ease(k) + 360 * eio(q)), S(890)], S(14), fill=RED + (255,))
            if T['kaltphase'] and t > T['kaltphase'] - 0.1: text(img, (540, 1060), 'schädlich', BF(72), RED, since(t, T['kaltphase'] - 0.1, 0.25), rot=-5)
    elif sc == 3:  # demi-litre par heure pour zéro kilomètre
        k = clamp(u0 / 0.4)   # pompe à essence
        rect(d, 200, 560, 420, 1000, INK, 8, k, 18, fill=(220, 90, 70, 255) if k >= 1 else None); rect(d, 235, 610, 385, 720, INK, 6, k, 10, fill=WHITE + (255,) if k >= 1 else None)
        if k >= 1:
            poly(d, [(420, 640), (500, 640), (520, 700), (520, 880)], INK, 9); rect(d, 495, 870, 560, 940, INK, 7, 1, 8, fill=(80, 80, 80, 255))
            for j in range(4):   # gouttes qui tombent du pistolet
                q = ((t - SC[3]) * 1.1 + j / 4) % 1; drop(d, 528, 960 + 300 * q * q, 18, OIL, 0.8)
            text(img, (310, 665), f'{min(0.5, (t - SC[3]) * 0.12):.1f} l'.replace('.', ','), BF(44), INK)
        if T['halben'] and t > T['halben'] - 0.1: text(img, (790, 620), '0,5 Liter', BF(72), INK, since(t, T['halben'] - 0.1, 0.3)); text(img, (790, 700), 'pro Stunde', H2(58), GREY, since(t, T['stunde'] - 0.1, 0.3) if T['stunde'] else 0)
        if T['null'] and t > T['null'] - 0.1:
            k2 = since(t, T['null'] - 0.1, 0.3); rect(d, 640, 880, 940, 1010, INK, 7, k2, 16, fill=(40, 40, 44, 255) if k2 >= 1 else None)
            text(img, (790, 945), '0 km', BF(78), WHITE if k2 >= 1 else INK, k2); underline(d, 650, 930, 1050, RED, since(t, T['km'], 0.4) if T['km'] else 0, 10)
    elif sc == 4:  # pot d'échappement + catalyseur froid : la fumée passe sans être filtrée
        k = clamp(u0 / 0.45); line(d, 80, 860, 1000, 860, INK, 9, k); line(d, 80, 940, 1000, 940, INK, 9, k)
        kk = clamp((u0 - 0.2) / 0.35); rect(d, 380, 790, 700, 1010, INK, 8, kk, 20, fill=(225, 220, 210, 255) if kk >= 1 else None)
        if kk >= 1:
            for j in range(7): line(d, 410 + j * 44, 805, 410 + j * 44, 995, GREY, 4)
            text(img, (540, 740), 'Katalysator', H2(64), INK)
        if T['kalt2'] and t > T['kalt2'] - 0.1:
            k2 = since(t, T['kalt2'] - 0.1, 0.3); text(img, (540, 1090), 'kalt', BF(70), COLD, k2)
            for a in range(3): line(d, 700 + 40 * math.cos(a * 1.05), 1090 + 40 * math.sin(a * 1.05), 700 - 40 * math.cos(a * 1.05), 1090 - 40 * math.sin(a * 1.05), COLD, 6, k2)
        if T['garnicht'] and t > T['garnicht'] - 0.2: cross(d, 540, 900, 150, since(t, T['garnicht'] - 0.2, 0.4), RED, 12)
        dirty = since(t, T['abgase'] - 0.3, 0.6) if T['abgase'] else 0
        for j in range(6):   # nuages qui traversent le pot puis sortent à droite
            q = ((t - SC[4]) * 0.35 + j / 6) % 1; x = 80 + 1000 * q; r = 22 + (60 if x > 1000 else 0) * dirty
            c = tuple(int(SMOKE[i] * (1 - 0.6 * dirty)) for i in range(3)); circ(d, x, 900 - 8 * math.sin(q * 20 + j), r + 18 * dirty, None, c + (int(200 * min(1, k)),))
        if T['ungefiltert'] and t > T['ungefiltert'] - 0.1:
            text(img, (540, 600), 'ungefiltert', BF(80), INK, since(t, T['ungefiltert'] - 0.1, 0.25), rot=-4, scale=1.3 - 0.3 * since(t, T['ungefiltert'] - 0.1, 0.25))
            for j in range(4): circ(d, 960 + 25 * j, 830 - 60 * j - 20 * math.sin(t * 3 + j), 40 + 12 * j, None, (60, 58, 56, 170))
    elif sc == 5:  # interdit : tampon VERBOTEN, § 30 StVO, amende de 10 €
        A = gone(t, T['paragraf'] - 0.1)
        def idle(lay, dl):
            car(lay, dl, CX, 1040, 1.25, (t - SC[5]) / 0.5, t, ice=0.6, smoke=1)
            if T['deutschland'] and t > T['deutschland'] - 0.1:
                k = since(t, T['deutschland'] - 0.1, 0.3)
                for j, c in enumerate(((30, 30, 30), (210, 40, 40), (250, 200, 40))): dl.rectangle([S(440), S(500 + j * 40 * k), S(640), S(500 + (j + 1) * 40 * k)], fill=c + (255,))
            if T['verboten'] and t > T['verboten'] - 0.05:
                q = since(t, T['verboten'] - 0.05, 0.22); text(lay, (CX, 820), 'VERBOTEN', BF(130), RED, q, rot=-9, scale=1.8 - 0.8 * ease(q))
                rect(dl, CX - 380, 730, CX + 380, 910, RED, 10, q, 20)
        sub(img, A, idle)
        if T['paragraf'] and t > T['paragraf'] - 0.15:
            k = since(t, T['paragraf'] - 0.15, 0.35); text(img, (CX, 600), '§ 30', BF(170), INK, k, scale=1.3 - 0.3 * ease(k))
            if T['stvo'] and t > T['stvo'] - 0.1: text(img, (CX, 720), 'Straßenverkehrsordnung', H2(64), GREY, since(t, T['stvo'] - 0.1, 0.3))
            if T['kostet'] and t > T['kostet'] - 0.1:
                q = clamp((t - T['kostet'] + 0.1) / 0.55); ticket(img, d, CX, 760 + 260 * ease(q) - 400 * (1 - q), 1.25, rot=-6 + 10 * (1 - q))
            if T['scheiben'] and t > T['scheiben'] - 0.1:
                k2 = since(t, T['scheiben'] - 0.1, 0.3); scraper(d, 880, 1215, 0.75, -30 + 25 * math.sin(t * 9)); text(img, (430, 1250), 'auch beim Kratzen!', H2(60), RED, k2)
    elif sc == 6:  # d'où vient le mythe : carburateur (früher) → puce électronique (heute)
        text(img, (CX, 520), 'Woher kommt der Mythos?', H2(66), INK, clamp(u0 / 0.3) * gone(t, T['frueher'] - 0.05))
        if T['frueher'] and t > T['frueher'] - 0.15:
            k = since(t, T['frueher'] - 0.15, 0.4); text(img, (290, 540), 'früher', H2(76), GREY, k); carb(img, d, 290, 840, 1.05, since(t, T['vergaser'] - 0.2, 0.6) if T['vergaser'] else k)
            if T['vergaser'] and t > T['vergaser']: text(img, (290, 1100), 'Vergaser', BF(52), INK, since(t, T['vergaser'], 0.3))
            if T['sinnvoll'] and t > T['sinnvoll'] - 0.1: check(d, 430, 600, 40, since(t, T['sinnvoll'] - 0.1, 0.4))
        if T['heute'] and t > T['heute'] - 0.15:
            k = since(t, T['heute'] - 0.15, 0.4); arrow(d, 470, 840, 620, 840, INK, 8, k); text(img, (790, 540), 'heute', H2(76), INK, k); chip(img, d, 790, 840, 1.0, k)
            if T['elektronik'] and t > T['elektronik'] - 0.1: text(img, (790, 1100), 'Elektronik', BF(52), GREEN, since(t, T['elektronik'] - 0.1, 0.3))
    elif sc == 7:  # la bonne méthode : liste cochée, compte-tours bas, moteur qui chauffe vite en roulant
        A = gone(t, T['ersten'] - 0.1); B = gone(t, T['schnellsten'] - 0.25) if t > T['ersten'] - 0.2 else 0
        def todo(lay, dl):
            items = [('Scheiben freikratzen', T['freikratzen']), ('einsteigen', T['einsteigen']), ('starten', T['starten']), ('losfahren', T['losfahren'])]
            for j, (lab, t0) in enumerate(items):
                if t0 and t > t0 - 0.25:
                    y = 560 + j * 150; k = since(t, t0 - 0.25, 0.3); rect(dl, 150, y - 40, 230, y + 40, INK, 6, k, 12); text(lay, (270, y), lab, BF(58), INK, k, anchor='lm')
                    check(dl, 190, y, 34, since(t, t0, 0.35))
            if T['losfahren'] and t > T['losfahren']: car(lay, dl, 540 + 700 * eio((t - T['losfahren']) / 1.3), 1180, 0.7, 1, t)
        sub(img, A, todo)
        if t > T['ersten'] - 0.2:
            def rpm(lay, dl):
                k = since(t, T['ersten'] - 0.2, 0.5); v = 0.28 + 0.03 * math.sin(t * 5)
                gauge(lay, dl, CX, 940, 300, v, k, red_from=0.7, nums=['0', '1', '2', '3', '4', '5', '6', '7'])
                text(lay, (CX, 1080), 'U/min × 1000', H2(48), GREY, k)
                if T['sanft'] and t > T['sanft'] - 0.1: text(lay, (CX, 520), 'sanft fahren', H2(80), GREEN, since(t, T['sanft'] - 0.1, 0.3))
                if T['vollgas'] and t > T['vollgas'] - 0.1: cross(dl, CX + 230, 760, 70, since(t, T['vollgas'] - 0.1, 0.35)); text(lay, (CX + 230, 640), 'kein Vollgas', BF(46), RED, since(t, T['vollgas'] - 0.1, 0.3))
            sub(img, B, rpm)
        if T['schnellsten'] and t > T['schnellsten'] - 0.3:
            k = since(t, T['schnellsten'] - 0.3, 0.4); v = 0.08 + 0.42 * eio((t - T['schnellsten'] + 0.1) / 1.4)
            gauge(img, d, CX, 880, 240, v, k, label='am schnellsten warm')
            if T['sparst'] and t > T['sparst'] - 0.1:
                text(img, (330, 1130), 'Sprit', BF(60), INK, since(t, T['sparst'] - 0.1, 0.3)); check(d, 460, 1125, 34, since(t, T['sparst'], 0.4))
            if T['nerven'] and t > T['nerven'] - 0.1:
                text(img, (700, 1130), 'Nerven', BF(60), INK, since(t, T['nerven'] - 0.1, 0.3)); check(d, 860, 1125, 34, since(t, T['nerven'], 0.4))
    elif sc == 8:  # partage
        share(img, d, CX, 760, u0 / 0.7); text(img, (CX, 1120), "sag's weiter", H2(96), RED, clamp((u0 - 0.3) / 0.4)); underline(d, CX - 230, CX + 230, 1180, RED, ease((u0 - 0.6) / 0.5), 10)
def draw(t):
    sc = max(i for i in range(len(SC) - 1) if t >= SC[i])
    lay = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    scene(lay, d, sc, t)
    # pas de transition glissée : la scène s'efface vite sur place, la suivante se dessine trait par trait
    tout = clamp((SC[sc + 1] - t) / 0.16) if sc < len(SC) - 2 else 1
    if tout < 1: lay.putalpha(lay.getchannel('A').point(lambda v: int(v * tout)))
    img = Image.new('RGBA', (W * SS, H * SS), BG + (255,)); img.alpha_composite(lay)
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
    AUDIO_ONLY = os.environ.get('AUDIO_ONLY') == '1'      # refait seulement le son d'une vidéo déjà rendue (images gardées)
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP); NF = int(DUR * FPS); CH = 90
    if not AUDIO_ONLY:
        with Pool(4) as pool:
            for k, _ in enumerate(pool.imap_unordered(render_chunk, [(i, min(NF, i + CH)) for i in range(0, NF, CH)])):
                if k % 8 == 0: print('images', min(NF, (k + 1) * CH), '/', NF, flush=True)
    # ---------- son : voix + effets synchronisés (pas de musique)
    N = int(DUR * SR); mix = np.zeros(N); mix[:len(VOICE)] += VOICE
    def sfx(name, t0, g):
        if t0 is None: return
        w = wave.open(SFXD + name + '.wav'); s = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float) / 32768
        if w.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
        if w.getframerate() != SR: s = np.interp(np.arange(0, len(s), w.getframerate() / SR), np.arange(len(s)), s)
        i0 = int(max(0, t0) * SR); L = min(len(s), N - i0); mix[i0:i0 + L] += s[:L] * g
    for t0 in SC[1:-1]: sfx('swish', t0 + 0.02, 0.1)
    sfx('pop', T['minuten'] - 0.2, 0.12); sfx('hit', T['quatsch'] - 0.03, 0.4); sfx('swish', T['quatsch'] - 0.05, 0.2); sfx('tap', T['ewig'] - 0.1, 0.14)
    sfx('pop', T['honig'], 0.12); sfx('clank', T['verschleisst'], 0.25); sfx('pop', T['kaltphase'], 0.14); sfx('pop', T['halben'], 0.12)
    sfx('hit', T['null'] - 0.05, 0.25); sfx('pop', T['garnicht'] - 0.1, 0.14); sfx('swish', T['ungefiltert'], 0.15)
    sfx('hit', T['verboten'] - 0.05, 0.45); sfx('thud', T['verboten'], 0.3); sfx('pop', T['paragraf'] - 0.1, 0.15); sfx('thud', T['kostet'] + 0.45, 0.4); sfx('tap', T['scheiben'], 0.12)
    sfx('pop', T['frueher'], 0.1); sfx('ding', T['sinnvoll'], 0.1); sfx('shine', T['heute'], 0.15)
    for k in ('freikratzen', 'einsteigen', 'starten', 'losfahren'): sfx('tap', T[k], 0.15)
    sfx('zoom1', T['losfahren'] + 0.1, 0.15); sfx('pop', T['vollgas'] - 0.1, 0.15); sfx('ding', T['sparst'], 0.12); sfx('ding', T['nerven'], 0.12); sfx('pop', T['sags'] + 0.3, 0.15)
    fd = int(0.8 * SR); mix[-fd:] *= np.linspace(1, 0, fd); mix = mix / max(1e-6, np.abs(mix).max()) * 0.92
    wo = wave.open(f'{TMP}/a.wav', 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((mix * 32767).astype('<i2').tobytes()); wo.close()
    AUD = ['-c:a', 'aac', '-b:a', '256k', '-af', 'pan=stereo|c0=c0|c1=c0', '-shortest', '-movflags', '+faststart']
    if AUDIO_ONLY:
        subprocess.run([FF, '-y', '-loglevel', 'error', '-i', OUT, '-i', f'{TMP}/a.wav', '-map', '0:v', '-map', '1:a', '-c:v', 'copy'] + AUD + [f'{TMP}/v.mp4'], check=True)
        shutil.move(f'{TMP}/v.mp4', OUT)
    else:
        subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{TMP}/f%05d.jpg', '-i', f'{TMP}/a.wav', '-c:v', 'libx264', '-preset', 'slow', '-crf', '15', '-tune', 'animation',
                        '-pix_fmt', 'yuv420p', '-r', str(FPS)] + AUD + [OUT], check=True)
    shutil.rmtree(TMP); print('ok', OUT, round(DUR, 2))
