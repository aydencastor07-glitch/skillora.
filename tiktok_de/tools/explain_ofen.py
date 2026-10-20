# Vidéo explicative « four » (style TikTok DE, même moteur que explain_tacho) : symbole grill, four, pâte qui lève, ventilateur, résistance,
# sous-titres mot à mot (mot clé en jaune). Calée sur la voix nettoyée. usage : explain_tacho.py dossier out.mp4
import sys, os, re, math, json, subprocess, shutil, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe(); DIR = sys.argv[1]; OUT = sys.argv[2]
VOICE = os.environ.get('VOICE', 'voix_clean.mp3'); HANDLE = os.environ.get('HANDLE', ''); NAME = os.environ.get('NAME', '')  # signature en haut à gauche
W, H, FPS, SS = 1080, 1920, 30, 2          # SS : sur-échantillonnage des dessins (traits lisses)
BG = (229, 219, 201); INK = (42, 37, 33); RED = (204, 60, 46); GREY = (120, 110, 100); YEL = (255, 226, 40)
FD = '/home/user/skillora./temu/fonts/'
def F(n, s): return ImageFont.truetype(FD + n, s)
HAND = lambda s: F('Caveat.ttf', s)
# ---------- 1. voix + calage des mots (pauses détectées, phrases ancrées sur les vraies pauses)
SR = 16000
a = np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', os.path.join(DIR, VOICE), '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(float)
DUR = len(a) / SR + 0.6
e = np.array([np.sqrt(np.mean(a[i:i + 160] ** 2)) for i in range(0, len(a) - 160, 160)]); db = 20 * np.log10(e + 1); sp = db > db.max() - 33
gaps = []; i = 0
while i < len(sp):
    if not sp[i]:
        j = i
        while j < len(sp) and not sp[j]: j += 1
        if j - i >= 9 and i > 0 and j < len(sp): gaps.append(((i + j) / 200, (j - i) / 100))
        i = j
    else: i += 1
start = np.argmax(sp) / 100; end = (len(sp) - np.argmax(sp[::-1])) / 100
TXT = open(os.path.join(DIR, 'script.txt')).read().split('=== TRADUCTION')[0].split('===\n', 1)[1].strip()
SENT = [s.strip() for s in re.split(r'(?<=[.:!?–,])\s+', TXT.replace('\n', ' ')) if s.strip()]
def syl(w):
    w = re.sub('[^a-zäöüß0-9]', '', w.lower())
    if re.fullmatch(r'\d+', w): return {'100': 3, '114': 5}.get(w, 2)
    if w == 'kmh': return 4
    return max(1, len(re.findall('[aeiouyäöü]+', w)))
wts = [sum(syl(w) + 0.35 for w in s.split()) for s in SENT]; tot = sum(wts)
# limites de phrases : proportionnelles, puis « aimantées » vers la pause la plus proche
bounds = [start]; acc = 0
for k in range(len(SENT) - 1):
    acc += wts[k]; t = start + (end - start) * acc / tot
    near = [g for g in gaps if abs(g[0] - t) < 1.0 and g[0] > bounds[-1] + 0.3]
    bounds.append(min(near, key=lambda g: abs(g[0] - t) - g[1])[0] if near else t)
bounds.append(end)
SEG = json.load(open(os.path.join(DIR, 'segments.json'))) if os.path.exists(os.path.join(DIR, 'segments.json')) else None
if SEG: SENT = [x[0] for x in SEG]; bounds = [x[1] for x in SEG] + [SEG[-1][2]]   # calage manuel si fourni
WORDS = []
for k, s in enumerate(SENT):
    t0, t1 = (SEG[k][1], SEG[k][2]) if SEG else (bounds[k] + (0.04 if k else 0), bounds[k + 1] - 0.06); ws = s.split(); ww = [syl(w) + 0.35 for w in ws]; tt = sum(ww); c = 0
    for w, q in zip(ws, ww):
        WORDS.append([w, t0 + (t1 - t0) * c / tt, t0 + (t1 - t0) * (c + q) / tt]); c += q
def at(word, n=0):
    m = [w for w in WORDS if word.lower() in w[0].lower()]; return m[n][1] if len(m) > n else None
json.dump({'sent': SENT, 'bounds': bounds, 'words': WORDS}, open(os.path.join(DIR, 'timing.json'), 'w'), ensure_ascii=False, indent=0)
# ---------- 2. outils de dessin (sur toile 2x)
def ease(u): u = max(0, min(1, u)); return 1 - (1 - u) ** 3
def back(u): u = max(0, min(1, u)); c = 1.7; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2
def clamp(u): return max(0, min(1, u))
def S(v): return int(v * SS)
def arc(d, cx, cy, r, a0, a1, col, w):
    if a1 - a0 < 0.5: return
    d.arc([S(cx - r), S(cy - r), S(cx + r), S(cy + r)], a0, a1, fill=col, width=S(w))
def line(d, x0, y0, x1, y1, col, w, p=1.0):
    if p <= 0: return
    d.line([S(x0), S(y0), S(x0 + (x1 - x0) * p), S(y0 + (y1 - y0) * p)], fill=col, width=S(w))
    if p >= 1: [d.ellipse([S(x) - S(w) // 2, S(y) - S(w) // 2, S(x) + S(w) // 2, S(y) + S(w) // 2], fill=col) for x, y in ((x0, y0), (x1, y1))]
def rect(d, x0, y0, x1, y1, col, w, p=1.0, r=24):
    # rectangle qui se dessine (périmètre parcouru selon p)
    if p >= 1: d.rounded_rectangle([S(x0), S(y0), S(x1), S(y1)], S(r), outline=col, width=S(w)); return
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]; L = 2 * (x1 - x0 + y1 - y0); left = L * p
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        seg = abs(bx - ax) + abs(by - ay)
        if left <= 0: break
        q = min(1, left / seg); line(d, ax, ay, bx, by, col, w, q); left -= seg
def text(img, xy, s, f, col, alpha=1.0, anchor='mm'):
    if alpha <= 0: return
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); ImageDraw.Draw(lay).text((S(xy[0]), S(xy[1])), s, font=f, fill=col + (int(255 * alpha),), anchor=anchor); img.alpha_composite(lay)
def H2(s): return HAND(S(s * 1.45))
def underline(d, x0, x1, y, col, p, w=7):
    if p > 0: d.line([S(x0), S(y), S(x0 + (x1 - x0) * p), S(y + 3)], fill=col + (150,), width=S(w))
def cross(d, cx, cy, r, p, col=RED, w=9):
    line(d, cx - r, cy - r, cx + r, cy + r, col, w, clamp(p * 2)); line(d, cx + r, cy - r, cx - r, cy + r, col, w, clamp(p * 2 - 1))
def check(d, cx, cy, r, p, col=RED, w=10):
    line(d, cx - r, cy, cx - r * 0.3, cy + r * 0.7, col, w, clamp(p * 2)); line(d, cx - r * 0.3, cy + r * 0.7, cx + r, cy - r * 0.8, col, w, clamp(p * 2 - 1))

# ---------- 3. dessins du four
def oven(img, d, cx, cy, w, h, p, heat_top=0.0, heat_bot=0.0, fan=None, coil=0.0, trays=(), t=0):
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    rect(d, x0, y0, x1, y1, INK, 9, ease(p), 26)
    if p < 0.5: return
    k = clamp((p - 0.5) / 0.5)
    line(d, x0, y0 + 110, x1, y0 + 110, INK, 6, k)
    for j in range(4):
        kx = x0 + w * (0.2 + 0.2 * j); arc(d, kx, y0 + 55, 24, 0, 360 * k, INK, 6); line(d, kx, y0 + 55, kx, y0 + 35, INK, 5, k)
    rect(d, x0 + 50, y0 + 150, x1 - 50, y1 - 40, INK, 6, k, 16)
    if coil > 0:   # résistance du grill en haut (zigzag qui rougit)
        col = tuple(int(INK[i] + (RED[i] - INK[i]) * coil) for i in range(3)); n = 9; xs = [x0 + 80 + j * (w - 160) / n for j in range(n + 1)]
        for j in range(n): line(d, xs[j], y0 + 175 + (14 if j % 2 else 0), xs[j + 1], y0 + 175 + (0 if j % 2 else 14), col, 7)
    for (yy, a_) in ((y0 + 200, heat_top), (y1 - 75, heat_bot)):
        if a_ > 0:
            pts = [(S(x0 + 70 + q * 6), S(yy + 10 * math.sin(q * 0.35 + t * 6))) for q in range(int((w - 140) / 6))]
            d.line(pts, fill=RED + (int(255 * a_),), width=S(5))
    for ty, pz in trays:
        line(d, x0 + 60, ty, x1 - 60, ty, GREY, 5); 
        if pz: pizza(d, cx, ty - 18, 120, pz)
    if fan is not None:
        fx, fy = cx, (y0 + 150 + y1 - 40) / 2; fanicon(d, fx, fy, 60, fan)
def pizza(d, cx, cy, r, p=1.0, col=(214, 160, 120)):
    if p <= 0: return
    d.ellipse([S(cx - r * p), S(cy - r * 0.32 * p), S(cx + r * p), S(cy + r * 0.32 * p)], fill=col + (255,), outline=INK, width=S(5))
    for (ax, ay) in ((-0.4, -0.05), (0.1, 0.08), (0.45, -0.08), (-0.1, -0.12)):
        d.ellipse([S(cx + ax * r * p - 9), S(cy + ay * r * p - 6), S(cx + ax * r * p + 9), S(cy + ay * r * p + 6)], fill=RED + (230,))
def fanicon(d, cx, cy, r, ang):
    arc(d, cx, cy, r * 1.35, 0, 360, INK, 6)
    for j in range(3):
        a0 = ang + j * 120; d.pieslice([S(cx - r), S(cy - r), S(cx + r), S(cy + r)], a0, a0 + 55, fill=(200, 130, 115, 255))
    d.ellipse([S(cx - 10), S(cy - 10), S(cx + 10), S(cy + 10)], fill=INK)
def grillsym(d, cx, cy, s, p, col=INK):
    rect(d, cx - s, cy - s, cx + s, cy + s, col, 10, ease(p), 18)
    n = 6; xs = [cx - s * 0.7 + j * s * 1.4 / n for j in range(n + 1)]
    for j in range(n): line(d, xs[j], cy - s * 0.55 + (s * 0.22 if j % 2 else 0), xs[j + 1], cy - s * 0.55 + (0 if j % 2 else s * 0.22), col, 8, ease(p * 1.6 - 0.6 - j * 0.05))
def dough(d, cx, cy, w, h, bub=0.0, rise=1.0, col=(214, 160, 140)):
    hh = h * rise; d.chord([S(cx - w / 2), S(cy - hh), S(cx + w / 2), S(cy + hh)], 180, 360, fill=col + (255,), outline=INK, width=S(5))
    if bub > 0:
        for j, (bx, by, br) in enumerate(((-0.25, 0.45, 0.10), (0.05, 0.6, 0.13), (0.28, 0.4, 0.09), (-0.05, 0.3, 0.07), (0.15, 0.75, 0.06))):
            r_ = w * br * (0.6 + 0.8 * bub) * rise ** 0.5; d.ellipse([S(cx + bx * w - r_), S(cy - by * hh - r_), S(cx + bx * w + r_), S(cy - by * hh + r_)], fill=(245, 236, 222, 255), outline=INK, width=S(3))
BF = lambda s: F('Poppins-ExtraBold.ttf', S(s))
# ---------- 4. scènes (temps tirés de la voix)
KEYS = {'genauso': ('Genauso',), 'geld': ('Geld',), 'vorh2': ('Vorheizen', 1), 'brot': ('Brot',), 'luft': ('Luftblasen',), 'zuschl': ('zuschlägt',), 'trieb': ('Ofentrieb',),
        'kalten': ('kalten',), 'flach': ('flach',), 'deine': ('Deine',), 'zusammen': ('zusammen',), 'zwanzig': ('zwanzig',), 'umluft': ('Umluft',), 'trocknet': ('trocknet',),
        'bleche': ('Bleche',), 'einzelne': ('einzelne',), 'saftig': ('saftig',), 'unterste': ('unterste',), 'symbol2': ('Symbol', 1), 'kaese': ('Käse',), 'dabei': ('dabei',), 'sags': ("Sag's",)}
def atx(word, n=0):   # mot exact (ponctuation ignorée)
    m = [w for w in WORDS if w[0].strip('.,:!?–;"„“').lower() == word.lower()]; return m[n][1] if len(m) > n else None
T = {k: atx(*v) for k, v in KEYS.items()}
print({k: round(v, 2) if v else v for k, v in T.items()})
SC = [0, T['genauso'] - 0.1, T['vorh2'] + 0.5, T['deine'] - 0.1, T['umluft'] - 0.1, T['einzelne'] - 0.2, T['symbol2'] - 0.1, T['sags'] - 0.15, DUR]
def scene_alpha(i, t):
    a0, a1 = SC[i], SC[i + 1]; return clamp((t - a0) / 0.25) * clamp((a1 - t) / 0.25 + (1 if i == len(SC) - 2 else 0))
def draw(t):
    img = Image.new('RGBA', (W * SS, H * SS), BG + (255,)); lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    sc = max(i for i in range(len(SC) - 1) if t >= SC[i]); CX = W / 2; u0 = t - SC[sc]
    if sc == 0:   # symbole du grill + point d'interrogation
        grillsym(d, CX, 760, 230, u0 / 0.9)
        if u0 > 0.9: text(lay, (CX + 290, 520), '?', BF(int(200 * min(1, back((u0 - 0.9) / 0.4)))), RED)
        text(lay, (CX, 1130), 'wofür ist das?', H2(70), GREY, clamp((u0 - 1.2) / 0.4))
    elif sc == 1:  # four qui préchauffe + argent qui brûle
        warm = clamp((u0 - 0.6) / 1.8); oven(lay, d, CX, 740, 640, 560, u0 / 0.8, heat_top=warm, heat_bot=warm, t=t)
        text(lay, (CX, 330), 'vorheizen …', H2(60), GREY, clamp(u0 / 0.4))
        if T['geld'] and t > T['geld'] - 0.2:
            q = back((t - T['geld'] + 0.2) / 0.4); text(lay, (CX, 1160), '€ € €', BF(int(120 * max(0.2, q))), RED)
            text(lay, (CX, 1290), 'Geld verbrannt', H2(70), INK, clamp((t - T['geld']) / 0.3))
    elif sc == 2:  # pain / gâteau, bulles de CO2, poussée au four, four froid
        text(lay, (CX, 330), 'nur was aufgehen muss', H2(52), GREY, clamp(u0 / 0.4))
        if not (T['luft'] and t > T['luft'] - 0.3):
            dough(d, CX - 210, 820, 260, 150, 0, ease(u0 / 0.5)); dough(d, CX + 210, 820, 260, 120, 0, ease(u0 / 0.5 - 0.3))
            text(lay, (CX - 210, 880), 'BROT', BF(44), INK, clamp(u0 / 0.5)); text(lay, (CX + 210, 880), 'KUCHEN', BF(44), INK, clamp(u0 / 0.5 - 0.3))
        elif not (T['kalten'] and t > T['kalten'] - 0.3):
            b = clamp((t - T['luft']) / 0.6) * 0.5 + (0.5 * ease((t - T['zuschl']) / 0.5) if T['zuschl'] and t > T['zuschl'] else 0)
            r = 1 + (0.35 * ease((t - T['zuschl']) / 0.6) if T['zuschl'] and t > T['zuschl'] else 0)
            dough(d, CX, 900, 520, 260, b, r); text(lay, (CX, 1000), 'CO2 im Teig', H2(60), GREY, clamp((t - T['luft']) / 0.4))
            if T['zuschl'] and t > T['zuschl']:
                for j in range(3): pts = [(S(CX - 300 + q * 10), S(560 + j * 30 + 12 * math.sin(q * 0.4 + t * 7))) for q in range(60)]; d.line(pts, fill=RED + (200,), width=S(5))
            if T['trieb'] and t > T['trieb'] - 0.1: text(lay, (CX, 1150), 'OFENTRIEB', BF(int(90 * max(0.3, back((t - T['trieb'] + 0.1) / 0.35)))), RED)
        else:
            q = clamp((t - T['kalten'] + 0.3) / 0.5)
            for j in range(3): pts = [(S(CX - 330 + q2 * 6), S(600 + j * 22 + 10 * math.sin(q2 * 0.4 + t * 7))) for q2 in range(36)]; d.line(pts, fill=RED + (int(220 * q),), width=S(5))
            pts = [(S(CX + 110 + q2 * 6), S(615 + 6 * math.sin(q2 * 0.3))) for q2 in range(36)]; d.line(pts, fill=GREY + (int(220 * q),), width=S(4))
            dough(d, CX - 220, 900, 300, 200, 0.9, ease(q)); dough(d, CX + 220, 900, 300, 200 * (1 - 0.55 * ease((t - (T['flach'] or t)) / 0.5)), 0.3, ease(q))
            text(lay, (CX - 220, 980), 'heiß rein', H2(60), RED, q); text(lay, (CX + 220, 980), 'kalt rein', H2(60), INK, q)
            if T['flach'] and t > T['flach']: text(lay, (CX + 220, 1080), 'flach & klein', H2(56), GREY, clamp((t - T['flach']) / 0.3))
    elif sc == 3:  # la pizza chauffe avec le four, -20 %
        warm = clamp((t - (T['zusammen'] or t) + 0.3) / 1.5) if T['zusammen'] else 0
        oven(lay, d, CX, 740, 640, 560, u0 / 0.7, heat_top=warm, heat_bot=warm, trays=((900, ease(u0 / 0.6 - 0.4)),), t=t)
        text(lay, (CX, 330), 'muss nur durchgaren', H2(56), GREY, clamp(u0 / 0.4))
        if T['zusammen'] and t > T['zusammen']: text(lay, (CX, 1110), 'Ofen & Pizza zusammen warm', H2(54), INK, clamp((t - T['zusammen']) / 0.3))
        if T['zwanzig'] and t > T['zwanzig'] - 0.1:
            text(lay, (CX, 1260), '− 20 % Energie', BF(int(84 * max(0.3, back((t - T['zwanzig'] + 0.1) / 0.35)))), RED)
    elif sc == 4:  # chaleur tournante : ventilateur, sèche, utile pour 2 plaques
        if not (T['bleche'] and t > T['bleche'] - 0.4):
            fanicon(d, CX, 720, 150, t * 400); text(lay, (CX, 470), 'UMLUFT?', BF(70), INK, clamp(u0 / 0.3))
            for j in range(4):
                ph = ((t * 1.5) + j / 4) % 1; pts = [(S(CX + 220 + ph * 200 + q * 5), S(640 + j * 50 + 8 * math.sin(q * 0.5))) for q in range(20)]; d.line(pts, fill=RED + (int(200 * (1 - ph)),), width=S(5))
            if T['trocknet'] and t > T['trocknet'] - 0.1:
                pizza(d, CX, 1060, 170, 1, col=(190, 150, 110)); text(lay, (CX, 1190), 'TROCKEN', BF(72), RED, clamp((t - T['trocknet']) / 0.3))
        else:
            q = (t - T['bleche'] + 0.4) / 0.6
            oven(lay, d, CX, 760, 640, 600, 1, fan=t * 400, trays=((800, ease(q)), (960, ease(q - 0.3))), t=t)
            for j in range(2):
                pts = [(S(CX - 250 + q2 * 8), S(730 + j * 160 + 10 * math.sin(q2 * 0.5 + t * 8))) for q2 in range(64)]; d.line(pts, fill=RED + (180,), width=S(4))
            text(lay, (CX, 1150), '2 Bleche? Dann Umluft', H2(60), INK, clamp(q)); check(d, CX + 400, 1150, 30, q - 0.6)
    elif sc == 5:  # chaleur haut et bas, grille du bas
        low = T['unterste'] and t > T['unterste']; ty = 900 + (100 * ease((t - T['unterste']) / 0.5) if low else 0)
        oven(lay, d, CX, 740, 640, 560, u0 / 0.6, heat_top=0.9, heat_bot=0.9, trays=((ty, ease(u0 / 0.6 - 0.3)),), t=t)
        text(lay, (CX, 330), 'Ober- & Unterhitze', H2(60), RED, clamp(u0 / 0.4))
        if T['saftig'] and t > T['saftig'] - 0.1: text(lay, (CX, 1110), 'Luft steht still – saftig', H2(56), INK, clamp((t - T['saftig']) / 0.3))
        if low: text(lay, (CX, 1220), 'unten = knuspriger Boden', H2(56), RED, clamp((t - T['unterste']) / 0.3))
    elif sc == 6:  # retour du symbole : le grill
        if u0 < 1.4:
            grillsym(d, CX, 760, 200, 1, RED if u0 > 0.5 else INK); text(lay, (CX, 1060), 'GRILL', BF(84), RED, clamp((u0 - 0.5) / 0.3))
        else:
            glow = clamp((u0 - 1.4) / 0.8); oven(lay, d, CX, 740, 640, 560, 1, coil=glow, trays=((900, 1),), t=t)
            if T['kaese'] and t > T['kaese']:
                g = clamp((t - T['kaese']) / 1.2); pizza(d, CX, 882, 120, 1, col=(int(214 + 30 * g), int(160 + 40 * g), int(120 - 80 * g)))
                text(lay, (CX, 1110), 'Käse goldbraun', H2(62), INK, clamp((t - T['kaese']) / 0.3))
            if T['dabei'] and t > T['dabei']: text(lay, (CX, 1230), 'nicht weggehen!', H2(64), RED, clamp((t - T['dabei']) / 0.3))
    elif sc == 7:  # partage
        p = u0 / 0.7; cx, cy = CX, 760
        for (x, y) in ((cx - 170, cy), (cx + 150, cy - 140), (cx + 150, cy + 140)): arc(d, x, y, 62, -90, -90 + 360 * ease(p), INK, 9)
        line(d, cx - 115, cy - 25, cx + 95, cy - 115, INK, 8, ease(p - 0.4)); line(d, cx - 115, cy + 25, cx + 95, cy + 115, INK, 8, ease(p - 0.4))
        text(lay, (CX, 1120), "sag's weiter", H2(96), RED, clamp((u0 - 0.3) / 0.4)); underline(d, CX - 230, CX + 230, 1180, RED, ease((u0 - 0.6) / 0.5), 10)
    al = scene_alpha(sc, t)
    if al < 1: lay.putalpha(lay.getchannel('A').point(lambda v: int(v * al)))
    img.alpha_composite(lay)
    if NAME or HANDLE:
        sg = Image.new('RGBA', img.size, (0, 0, 0, 0))
        if NAME: ImageDraw.Draw(sg).text((S(70), S(185)), NAME, font=HAND(S(86)), fill=GREY + (255,), anchor='ls')
        if HANDLE: ImageDraw.Draw(sg).text((S(72), S(250)), HANDLE, font=HAND(S(62)), fill=RED + (255,), anchor='ls')
        img.alpha_composite(sg)
    img = img.resize((W, H), Image.LANCZOS); caption(img, t); return img.convert('RGB')

# ---------- 5. sous-titres : 3 mots max, majuscules, contour noir, mot clé en jaune
HOT = re.compile(r'(\d|symbol|ofen|vorheiz|geld|brot|kuchen|co2|luftblasen|hefe|ofentrieb|kalten|pizza|energie|prozent|zwanzig|umluft|trocknet|bleche|unterhitze|saftig|knusprig|grill|käse|goldbraun)', re.I)
GROUPS = []; cur = []
for k, w in enumerate(WORDS):
    cur.append(k)
    if len(cur) == 3 or re.search(r'[.,:!?–]$', w[0]) or w[0] == '–': GROUPS.append(cur); cur = []
if cur: GROUPS.append(cur)
CF = F('Poppins-ExtraBold.ttf', 70)
def caption(img, t):
    g = next((g for g in GROUPS if WORDS[g[0]][1] - 0.05 <= t < (WORDS[g[-1]][2] + 0.25)), None)
    if not g: return
    ws = [WORDS[k][0].strip('.,:!?').upper() for k in g if WORDS[k][0] != '–']; ks = [k for k in g if WORDS[k][0] != '–']
    if not ws: return
    d = ImageDraw.Draw(img); sp = 22; cf = CF; wd = [cf.getbbox(w)[2] for w in ws]; tw = sum(wd) + sp * (len(ws) - 1)
    if tw > W - 120: cf = F('Poppins-ExtraBold.ttf', int(70 * (W - 120) / tw)); wd = [cf.getbbox(w)[2] for w in ws]; tw = sum(wd) + sp * (len(ws) - 1)
    x = W / 2 - tw / 2; y = 1640
    for w, k, ww in zip(ws, ks, wd):
        said = t >= WORDS[k][1] - 0.03
        col = YEL if HOT.search(w) else (255, 255, 255)
        if said: d.text((x, y), w, font=cf, fill=col, anchor='lm', stroke_width=8, stroke_fill=(0, 0, 0))
        x += ww + sp
# ---------- 6. rendu + son
tmp = OUT + '_fr'; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
NF = int(DUR * FPS)
if os.environ.get('PREVIEW'): NF = 0
for n in range(NF): draw(n / FPS).save(f'{tmp}/f{n:05d}.jpg', quality=92)
for ts in os.environ.get('PREVIEW', '').split(',') if os.environ.get('PREVIEW') else []: draw(float(ts)).save(f'{OUT}_{ts}.jpg', quality=85)
if os.environ.get('PREVIEW'): shutil.rmtree(tmp); sys.exit(0)
SR2 = 44100; v = np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', os.path.join(DIR, VOICE), '-ac', '1', '-ar', str(SR2), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(float) / 32768
mix = np.zeros(int(DUR * SR2)); mix[:len(v)] += v
def sfx(name, t0, g):
    w = wave.open('/home/user/skillora./motion/sfx/' + name + '.wav'); s = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float) / 32768
    if w.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
    if w.getframerate() != SR2: s = np.interp(np.arange(0, len(s), w.getframerate() / SR2), np.arange(len(s)), s)
    i0 = int(max(0, t0) * SR2); L = min(len(s), len(mix) - i0); mix[i0:i0 + L] += s[:L] * g
for t0 in SC[1:-1]: sfx('swish', t0, 0.12)
for k in ('geld', 'luft', 'trieb', 'flach', 'zwanzig', 'trocknet', 'bleche', 'unterste', 'kaese', 'dabei'):
    if T[k]: sfx('pop', T[k], 0.1)
sfx('ding', 1.0, 0.08)
mix = mix / max(1e-6, np.abs(mix).max()) * 0.95
wo = wave.open(f'{tmp}/a.wav', 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR2); wo.writeframes((mix * 32767).astype('<i2').tobytes()); wo.close()
subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/f%05d.jpg', '-i', f'{tmp}/a.wav', '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
shutil.rmtree(tmp); print('ok', OUT, round(DUR, 2))
