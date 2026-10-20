# Vidéo explicative « chauffage » (style TikTok DE, même moteur que explain_tacho) : radiateur, thermostat, circuit de l'air, pertes de chaleur, aération,
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

# ---------- 3. dessins du chauffage
BLUE = (60, 110, 190)
BF = lambda s: F('Poppins-ExtraBold.ttf', S(s))
def radiator(d, cx, cy, w, h, p, hot=0.0):
    col = tuple(int(INK[i] + (RED[i] - INK[i]) * hot) for i in range(3))
    rect(d, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, col, 8, ease(p), 18)
    n = 7
    for j in range(1, n): x = cx - w / 2 + j * w / n; line(d, x, cy - h / 2 + 18, x, cy + h / 2 - 18, col, 5, ease(p * 1.5 - 0.5 - j * 0.04))
def knob(img, d, cx, cy, r, val, p=1.0, hi=None):
    arc(d, cx, cy, r, -90, -90 + 360 * ease(p), INK, 8)
    if p < 0.6: return
    for j in range(1, 6):
        ang = math.radians(150 + (j - 1) * 60); col = RED if hi == j else INK
        text(img, (cx + r * 0.72 * math.cos(ang), cy + r * 0.72 * math.sin(ang)), str(j), BF(int(r * 0.22)), col, clamp((p - 0.6) / 0.4))
    ang = math.radians(150 + (val - 1) * 60); line(d, cx, cy, cx + r * 0.45 * math.cos(ang), cy + r * 0.45 * math.sin(ang), RED, 9)
    d.ellipse([S(cx - 14), S(cy - 14), S(cx + 14), S(cy + 14)], fill=RED)
def thermo(d, x, y, h, lvl):
    rect(d, x - 22, y - h, x + 22, y, INK, 6, 1, 22); d.ellipse([S(x - 36), S(y - 20), S(x + 36), S(y + 50)], outline=INK, width=S(6), fill=RED + (255,))
    d.rectangle([S(x - 10), S(y - (h - 20) * clamp(lvl)), S(x + 10), S(y)], fill=RED + (255,))
def arrow(d, x0, y0, x1, y1, col, w=7, p=1.0):
    if p <= 0: return
    x1, y1 = x0 + (x1 - x0) * p, y0 + (y1 - y0) * p; line(d, x0, y0, x1, y1, col, w)
    a_ = math.atan2(y1 - y0, x1 - x0); L = 26
    d.polygon([(S(x1), S(y1)), (S(x1 - L * math.cos(a_ - 0.5)), S(y1 - L * math.sin(a_ - 0.5))), (S(x1 - L * math.cos(a_ + 0.5)), S(y1 - L * math.sin(a_ + 0.5)))], fill=col + (255,))
# pièce en coupe : mur gauche avec fenêtre, radiateur dessous ; boucle de l'air
RX0, RY0, RX1, RY1 = 140, 420, 940, 1150
LOOP = [(250, 1010), (250, 520), (830, 520), (830, 1060), (300, 1080)]
def room(img, d, p, t, loop=0.0, flow=False):
    rect(d, RX0, RY0, RX1, RY1, INK, 9, ease(p), 6)
    if p < 0.5: return
    k = clamp((p - 0.5) / 0.5)
    rect(d, RX0 - 14, 560, RX0 + 14, 820, INK, 6, k, 4); line(d, RX0, 690, RX0 + 14, 690, INK, 4, k)   # fenêtre
    radiator(d, RX0 + 110, 1030, 150, 150, k, hot=0.8)
    if loop > 0:   # tracé de la boucle (rouge en haut, bleu en bas)
        segs = list(zip(LOOP, LOOP[1:])); L = len(segs); q = loop * L
        for j, ((ax, ay), (bx, by)) in enumerate(segs):
            pj = clamp(q - j)
            if pj <= 0: break
            col = RED if j < 2 else (BLUE if j > 2 else (150, 90, 140))
            arrow(d, ax, ay, bx, by, col, 7, pj)
    if flow:     # points qui circulent dans la boucle
        pts = LOOP; lens = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]; T_ = sum(lens)
        for j in range(8):
            s_ = ((t * 260) + j * T_ / 8) % T_
            for (a, b), L_ in zip(zip(pts, pts[1:]), lens):
                if s_ <= L_:
                    x = a[0] + (b[0] - a[0]) * s_ / L_; y = a[1] + (b[1] - a[1]) * s_ / L_; c = RED if y < 700 or x < 400 and y < 1000 else BLUE
                    d.ellipse([S(x - 11), S(y - 11), S(x + 11), S(y + 11)], fill=c + (230,)); break
                s_ -= L_
def house(d, p):
    cx = W / 2; rect(d, cx - 330, 640, cx + 330, 1120, INK, 9, ease(p), 6)
    line(d, cx - 380, 660, cx, 380, INK, 9, ease(p - 0.3)); line(d, cx, 380, cx + 380, 660, INK, 9, ease(p - 0.45))
    rect(d, cx - 230, 760, cx - 80, 900, INK, 6, ease(p - 0.5), 4); rect(d, cx + 80, 760, cx + 230, 900, INK, 6, ease(p - 0.55), 4); rect(d, cx - 60, 960, cx + 60, 1120, INK, 6, ease(p - 0.6), 4)
def window(d, cx, cy, tilt, p):
    rect(d, cx - 110, cy - 160, cx + 110, cy + 160, INK, 7, ease(p), 6)
    if tilt == 'kipp': line(d, cx - 110, cy - 160, cx - 60, cy + 160, INK, 6, ease(p - 0.4)); line(d, cx + 110, cy - 160, cx + 60, cy + 160, INK, 6, ease(p - 0.4)); line(d, cx - 60, cy + 160, cx + 60, cy + 160, INK, 6, ease(p - 0.4))
    if tilt == 'auf': line(d, cx + 110, cy - 160, cx + 210, cy - 110, INK, 6, ease(p - 0.4)); line(d, cx + 210, cy - 110, cx + 210, cy + 210, INK, 6, ease(p - 0.5)); line(d, cx + 110, cy + 160, cx + 210, cy + 210, INK, 6, ease(p - 0.6))
# ---------- 4. scènes (temps tirés de la voix)
KEYS = {'verschw': ('verschwindet',), 'wohin': ('wohin',), 'fangen': ('Fangen',), 'zahlen': ('Zahlen',), 'drei': ('3',), 'auf5': ('Auf', 1), 'f28': ('28',), 'reise': ('Reise',),
        'warme': ('Warme',), 'decke': ('Decke',), 'sinkt': ('sinkt',), 'boden': ('Boden',), 'kreis': ('Kreislauf',), 'darum': ('Darum',), 'vorhang': ('Vorhang',),
        'aber': ('Aber', 1), 'fenster': ('Fenster', 1), 'waende': ('Wände',), 'dach': ('Dach',), 'sofa': ('Sofa',), 'kalt': ('kalt',), 'fehler': ('Fehler',), 'kippen': ('kippen',),
        'kuehlen': ('kühlen',), 'besser': ('Besser',), 'stoss': ('Stoßlüften',), 'warm2': ('warm', 1), 'bonus': ('Bonus',), 'sechs': ('sechs',), 'von': ('Von',), 'zwanzig': ('zwanzig',), 'sags': ("Sag's",)}
def atx(word, n=0):   # mot exact (ponctuation ignorée)
    m = [w for w in WORDS if w[0].strip('.,:!?–;"„“').lower() == word.lower()]; return m[n][1] if len(m) > n else None
T = {k: atx(*v) for k, v in KEYS.items()}
print({k: round(v, 2) if v else v for k, v in T.items()})
SC = [0, T['fangen'] - 0.1, T['reise'] - 0.1, T['darum'] - 0.1, T['aber'] - 0.1, T['sofa'] - 0.3, T['fehler'] - 0.15, T['bonus'] - 0.15, T['sags'] - 0.1, DUR]
def scene_alpha(i, t):
    a0, a1 = SC[i], SC[i + 1]; return clamp((t - a0) / 0.25) * clamp((a1 - t) / 0.25 + (1 if i == len(SC) - 2 else 0))
def draw(t):
    img = Image.new('RGBA', (W * SS, H * SS), BG + (255,)); lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    sc = max(i for i in range(len(SC) - 1) if t >= SC[i]); CX = W / 2; u0 = t - SC[sc]
    if sc == 0:   # radiateur sur 5, thermomètre qui ne monte pas plus vite, chaleur qui s'en va
        radiator(d, CX - 120, 820, 420, 300, u0 / 0.8, hot=clamp(u0 / 2)); knob(lay, d, CX - 120, 560, 90, 1 + 4 * ease((u0 - 0.6) / 0.8), clamp((u0 - 0.3) / 0.6))
        thermo(d, CX + 280, 980, 380, 0.25 + 0.05 * clamp(u0 / 4))
        text(lay, (CX, 330), 'Heizung auf 5 …', H2(56), GREY, clamp(u0 / 0.4))
        if T['verschw'] and t > T['verschw']:
            for j in range(4):
                ph = ((t - T['verschw']) * 0.8 + j / 4) % 1; pts = [(S(CX - 300 + q * 7 + ph * 40), S(620 - ph * 260 + 10 * math.sin(q * 0.5 + t * 5))) for q in range(60)]
                d.line(pts, fill=RED + (int(220 * (1 - ph)),), width=S(5))
        if T['wohin'] and t > T['wohin'] - 0.2: text(lay, (CX, 1160), 'wohin?', H2(110), RED, clamp((t - T['wohin'] + 0.2) / 0.3))
    elif sc == 1:  # le thermostat : des températures
        val = 3
        if T['auf5'] and t > T['auf5']: val = 3 + 2 * ease((t - T['auf5']) / 0.6)
        hi = 5 if val > 4.9 else (3 if T['drei'] and t > T['drei'] - 0.2 else None)
        knob(lay, d, CX, 720, 260, val if T['drei'] and t > T['drei'] - 0.3 else 1 + 2 * ease(u0 / 1.2), u0 / 0.8, hi)
        text(lay, (CX, 330), 'keine Geschwindigkeit …', H2(54), GREY, clamp(u0 / 0.4))
        if T['zahlen'] and t > T['zahlen'] + 0.6: text(lay, (CX, 1080), '… sondern Temperaturen', H2(64), INK, clamp((t - T['zahlen'] - 0.6) / 0.3))
        if T['drei'] and t > T['drei']: text(lay, (CX, 1170), '3 = ca. 20 °C', BF(60), INK, clamp((t - T['drei']) / 0.3))
        if T['f28'] and t > T['f28'] - 0.1: text(lay, (CX, 1250), '5 = ca. 28 °C', BF(60), RED, clamp((t - T['f28'] + 0.1) / 0.3))
        if T['auf5'] and t > T['auf5'] + 0.8: text(lay, (CX, 1330), 'nicht schneller – nur länger', H2(52), RED, clamp((t - T['auf5'] - 0.8) / 0.3))
    elif sc == 2:  # le voyage de la chaleur : boucle de convection
        lp = 0
        if T['warme'] and t > T['warme']: lp = clamp((t - T['warme']) / max(1, (T['boden'] or t + 3) - T['warme'] + 0.8))
        room(lay, d, u0 / 0.8, t, loop=lp, flow=bool(T['kreis'] and t > T['kreis'] - 0.2))
        text(lay, (CX, 330), 'die Reise der Wärme', H2(56), GREY, clamp(u0 / 0.4))
        if T['warme'] and t > T['warme']: text(lay, (275, 700), 'warm steigt', H2(52), RED, clamp((t - T['warme']) / 0.3), anchor='lm')
        if T['decke'] and t > T['decke']: text(lay, (CX, 480), 'unter der Decke', H2(50), RED, clamp((t - T['decke']) / 0.3))
        if T['sinkt'] and t > T['sinkt']: text(lay, (810, 900), 'kühlt ab, sinkt', H2(48), BLUE, clamp((t - T['sinkt']) / 0.3), anchor='rm')
        if T['boden'] and t > T['boden']: text(lay, (600, 1110), 'zurück am Boden', H2(46), BLUE, clamp((t - T['boden']) / 0.3))
        if T['kreis'] and t > T['kreis'] - 0.2: text(lay, (CX, 1250), 'ein unsichtbarer Kreislauf', H2(64), INK, clamp((t - T['kreis'] + 0.2) / 0.3))
    elif sc == 3:  # rideau d'air chaud devant la fenêtre
        room(lay, d, 1, t, flow=True)
        q = clamp(u0 / 0.6)
        for j in range(5):
            ph = ((t * 0.9) + j / 5) % 1; x = RX0 + 40 + j * 14; pts = [(S(x + 8 * math.sin(yq * 0.08 + t * 6)), S(980 - ph * 440 - yq)) for yq in range(0, 120, 6)]
            d.line(pts, fill=RED + (int(230 * q * (1 - ph)),), width=S(5))
        for j in range(3): arrow(d, 20, 600 + j * 90, RX0 - 30, 600 + j * 90, BLUE, 6, clamp(u0 / 0.5 - j * 0.15))
        text(lay, (CX, 330), 'Heizung unterm Fenster', H2(56), GREY, clamp(u0 / 0.4))
        if T['vorhang'] and t > T['vorhang'] - 0.2: text(lay, (CX + 60, 1250), 'Vorhang aus warmer Luft', H2(64), RED, clamp((t - T['vorhang'] + 0.2) / 0.3))
    elif sc == 4:  # la maison perd sa chaleur
        house(d, u0 / 0.9); cx = CX
        for key, (x0, y0, x1, y1), lab, ly in (('fenster', (cx - 155, 830, cx - 420, 830), 'Fenster', 1180), ('waende', (cx + 330, 1000, cx + 480, 1000), 'Wände', 1240), ('dach', (cx, 420, cx, 250), 'Dach', 1300)):
            if T[key] and t > T[key] - 0.15:
                k = clamp((t - T[key] + 0.15) / 0.5); wob = 10 * math.sin(t * 6); arrow(d, x0, y0, x1 + (wob if key == 'dach' else 0), y1, RED, 9, k)
                text(lay, (CX, ly), '– ' + lab, H2(60), RED, k)
        text(lay, (CX, 300), 'hier verlierst du Wärme', H2(54), GREY, clamp(u0 / 0.4))
    elif sc == 5:  # canapé devant le radiateur
        room(lay, d, 1, t)
        q = clamp(u0 / 0.6); sx = RX0 + 220
        rect(d, sx, 930, sx + 300, 1100, INK, 8, ease(q), 20); rect(d, sx + 10, 860, sx + 290, 940, INK, 7, ease(q - 0.3), 16)
        for j in range(3): arc(d, RX0 + 110, 920 - j * 20, 50 + j * 25, 200 + (t * 200) % 360, 320 + (t * 200) % 360, RED, 6)
        text(lay, (CX, 330), 'Sofa vor der Heizung', H2(56), GREY, clamp(u0 / 0.4))
        if T['kalt'] and t > T['kalt'] - 0.2: text(lay, (CX, 1250), 'Wärme staut sich – Zimmer bleibt kalt', H2(52), RED, clamp((t - T['kalt'] + 0.2) / 0.3)); cross(d, sx + 150, 1000, 70, (t - T['kalt'] + 0.2) / 0.5)
    elif sc == 6:  # fenêtre basculée vs aération en grand
        window(d, CX - 230, 760, 'kipp', u0 / 0.6); text(lay, (CX - 230, 980), 'gekippt', H2(60), INK, clamp(u0 / 0.4))
        if T['kuehlen'] and t > T['kuehlen']:
            k = clamp((t - T['kuehlen']) / 1.2); d.rectangle([S(CX - 375), S(560), S(CX - 359), S(960)], fill=BLUE + (int(255 * k),)); text(lay, (CX - 230, 1060), 'Wände kühlen aus', H2(50), BLUE, k); cross(d, CX - 230, 760, 80, k)
        if T['stoss'] and t > T['stoss'] - 0.2:
            k = clamp((t - T['stoss'] + 0.2) / 0.5); window(d, CX + 200, 760, 'auf', k); text(lay, (CX + 230, 980), '5 Min. Stoßlüften', H2(56), RED, k)
            if T['warm2'] and t > T['warm2'] - 0.2: text(lay, (CX + 230, 1060), 'Wände bleiben warm', H2(50), RED, clamp((t - T['warm2'] + 0.2) / 0.3)); check(d, CX + 230, 1160, 40, (t - T['warm2'] + 0.2) / 0.5)
        text(lay, (CX, 330), 'der größte Fehler', H2(60), RED, clamp(u0 / 0.4))
    elif sc == 7:  # bonus économies
        thermo(d, CX, 900, 420, 0.7 - 0.25 * clamp((t - (T['von'] or t + 9)) / 1.2) if T['von'] else 0.7)
        if T['sechs'] and t > T['sechs'] - 0.2: text(lay, (CX, 1130), '1 °C weniger = − 6 %', BF(int(70 * max(0.3, back((t - T['sechs'] + 0.2) / 0.35)))), RED)
        if T['von'] and t > T['von']: text(lay, (CX, 1240), 'von 23 auf 20 °C', BF(64), INK, clamp((t - T['von']) / 0.3))
        if T['zwanzig'] and t > T['zwanzig'] - 0.1: text(lay, (CX, 1340), 'fast − 20 %', BF(int(84 * max(0.3, back((t - T['zwanzig'] + 0.1) / 0.35)))), RED)
        text(lay, (CX, 330), 'kleiner Bonus', H2(60), GREY, clamp(u0 / 0.4))
    elif sc == 8:  # partage
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
HOT = re.compile(r'(\d|heizung|thermostat|grad|temperatur|wärme|warm|luft|decke|boden|kreislauf|fenster|vorhang|wände|dach|sofa|kalt|fehler|kippen|stoßlüften|prozent|heizkosten|zwanzig|sechs)', re.I)
GROUPS = []; cur = []
for k, w in enumerate(WORDS):
    cur.append(k)
    if len(cur) == 3 or re.search(r'[.,:!?–]$', w[0]) or w[0] == '–': GROUPS.append(cur); cur = []
if cur: GROUPS.append(cur)
CF = F('Poppins-ExtraBold.ttf', 56)   # plus petit et plus haut : hors de la zone du texte TikTok
def caption(img, t):
    g = next((g for g in GROUPS if WORDS[g[0]][1] - 0.05 <= t < (WORDS[g[-1]][2] + 0.25)), None)
    if not g: return
    ws = [WORDS[k][0].strip('.,:!?').upper() for k in g if WORDS[k][0] != '–']; ks = [k for k in g if WORDS[k][0] != '–']
    if not ws: return
    d = ImageDraw.Draw(img); sp = 22; cf = CF; wd = [cf.getbbox(w)[2] for w in ws]; tw = sum(wd) + sp * (len(ws) - 1)
    if tw > W - 120: cf = F('Poppins-ExtraBold.ttf', int(56 * (W - 120) / tw)); wd = [cf.getbbox(w)[2] for w in ws]; tw = sum(wd) + sp * (len(ws) - 1)
    x = W / 2 - tw / 2; y = 1390
    for w, k, ww in zip(ws, ks, wd):
        said = t >= WORDS[k][1] - 0.03
        col = YEL if HOT.search(w) else (255, 255, 255)
        if said: d.text((x, y), w, font=cf, fill=col, anchor='lm', stroke_width=6, stroke_fill=(0, 0, 0))
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
for k in ('wohin', 'drei', 'f28', 'warme', 'kreis', 'vorhang', 'fenster', 'waende', 'dach', 'kalt', 'kuehlen', 'stoss', 'sechs', 'zwanzig'):
    if T[k]: sfx('pop', T[k], 0.1)
sfx('ding', 1.0, 0.08)
mix = mix / max(1e-6, np.abs(mix).max()) * 0.95
wo = wave.open(f'{tmp}/a.wav', 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR2); wo.writeframes((mix * 32767).astype('<i2').tobytes()); wo.close()
subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/f%05d.jpg', '-i', f'{tmp}/a.wav', '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
shutil.rmtree(tmp); print('ok', OUT, round(DUR, 2))
