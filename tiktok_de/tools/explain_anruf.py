# Vidéo explicative « appel téléphonique » (style TikTok DE, même moteur que explain_tacho) : bouton d'appel, antenne, fibre, central, alvéoles,
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

# ---------- 3. dessins : téléphone, antenne, câble, central, alvéoles
GREEN = (52, 190, 90); BLUE = (60, 110, 190)
BF = lambda s: F('Poppins-ExtraBold.ttf', S(s))
def phone(d, cx, cy, w, h, p, shake=0.0):
    cx += shake; rect(d, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, INK, 8, ease(p), int(w * 0.16))
    if p > 0.6: line(d, cx - w * 0.15, cy - h / 2 + 22, cx + w * 0.15, cy - h / 2 + 22, INK, 6)
def handset(d, cx, cy, r, col=(255, 255, 255)):
    d.arc([S(cx - r), S(cy - r), S(cx + r), S(cy + r)], 110, 250, fill=col, width=S(r * 0.42))
def callbtn(img, d, cx, cy, r, p, pressed=False, red=False):
    if p <= 0: return
    rr = r * (0.4 + 0.6 * back(p)) * (0.88 if pressed else 1)
    d.ellipse([S(cx - rr), S(cy - rr), S(cx + rr), S(cy + rr)], fill=((220, 60, 60) if red else GREEN) + (255,)); handset(d, cx, cy, rr * 0.5)
def tower(d, x, y, h, p, col=INK):
    line(d, x - h * 0.22, y, x, y - h, col, 7, ease(p)); line(d, x + h * 0.22, y, x, y - h, col, 7, ease(p))
    for j in range(1, 5):
        yy = y - h * j / 5; ww = h * 0.22 * (1 - j / 5); line(d, x - ww, yy, x + ww, yy, col, 4, ease(p * 1.5 - 0.5))
    if p > 0.8: d.ellipse([S(x - 12), S(y - h - 12), S(x + 12), S(y - h + 12)], fill=RED)
def waves(d, x0, y0, x1, y1, t, col=RED, n=4):
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0)); L = math.hypot(x1 - x0, y1 - y0)
    for j in range(n):
        ph = ((t * 1.2) + j / n) % 1; r = 30 + ph * L * 0.9
        arc(d, x0, y0, r, ang - 22, ang + 22, col + (int(240 * (1 - ph)),), 6)
def central(img, d, cx, cy, p):
    rect(d, cx - 140, cy - 170, cx + 140, cy + 170, INK, 8, ease(p), 10)
    for j in range(5): line(d, cx - 100, cy - 120 + j * 55, cx + 100, cy - 120 + j * 55, GREY, 6, ease(p * 1.5 - 0.5 - j * 0.08))
    text(img, (cx, cy + 215), 'Zentrale', H2(56), INK, clamp(p * 2 - 1))
def hexagon(d, cx, cy, r, col, w=5, fill=None):
    pts = [(S(cx + r * math.cos(math.radians(60 * k + 30))), S(cy + r * math.sin(math.radians(60 * k + 30)))) for k in range(6)]
    if fill: d.polygon(pts, fill=fill)
    d.line(pts + [pts[0]], fill=col, width=S(w))
def battery(d, cx, cy, lvl):
    rect(d, cx - 80, cy - 40, cx + 80, cy + 40, INK, 7, 1, 10); d.rectangle([S(cx + 80), S(cy - 16), S(cx + 94), S(cy + 16)], fill=INK)
    col = RED if lvl < 0.3 else GREEN; d.rectangle([S(cx - 68), S(cy - 28), S(cx - 68 + 136 * clamp(lvl)), S(cy + 28)], fill=col + (255,))
# ---------- 4. scènes (débuts de phrases tirés de segments.json)
def atx(word, n=0):
    m = [w for w in WORDS if w[0].strip('.,:!?–;"„“').lower() == word.lower()]; return m[n][1] if len(m) > n else None
def st(prefix): return next(x[1] for x in SEG if x[0].startswith(prefix))
KEYS = {'knopf': ('Knopf',), 'wahr': ('wahrscheinlich',), 'klingelt': ('klingelt',), 'woher': ('woher',), 'stuecke': ('Stücke',), 'fuenfzig': ('fünfzig',), 'zahlen': ('Zahlen',),
        'licht': ('Lichtgeschwindigkeit',), 'trick': ('Trick',), 'ende': ('Ende',), 'glas': ('Glasfaserkabel',), 'zentrale': ('Zentrale',), 'meldet': ('meldet',), 'waben': ('Waben',),
        'zuletzt': ('zuletzt',), 'klingelt2': ('klingelt', 1), 'uebergibt': ('übergibt',), 'milli': ('Millisekunden',), 'beide': ('beide',), 'keller': ('Keller',), 'beton': ('Beton',), 'akku': ('Akku',)}
T = {k: atx(*v) for k, v in KEYS.items()}
print({k: round(v, 2) if v else v for k, v in T.items()})
SC = [0, st('Alles') - 0.1, st('Diese Zahlen') - 0.1, st('Von dort') - 0.1, st('Die Zentrale') - 0.1, st('Also schickt') - 0.1, st('Und wenn du') - 0.1, st('Und das alles') - 0.1, st('Kleiner') - 0.1, st("Sag's") - 0.1, DUR]
def scene_alpha(i, t):
    a0, a1 = SC[i], SC[i + 1]; return clamp((t - a0) / 0.25) * clamp((a1 - t) / 0.25 + (1 if i == len(SC) - 2 else 0))
def draw(t):
    img = Image.new('RGBA', (W * SS, H * SS), BG + (255,)); lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    sc = max(i for i in range(len(SC) - 1) if t >= SC[i]); CX = W / 2; u0 = t - SC[sc]
    if sc == 0:   # bouton « Anrufen », doigt qui appuie, téléphone qui sonne de l'autre côté
        phone(d, 300, 800, 300, 560, u0 / 0.6)
        pressed = T['knopf'] and T['knopf'] < t < T['knopf'] + 0.25
        callbtn(lay, d, 300, 960, 62, (u0 - 0.4) / 0.4, pressed); text(lay, (300, 1060), 'Anrufen', BF(36), INK, clamp((u0 - 0.6) / 0.3))
        text(lay, (300, 700), '0171 …', BF(40), GREY, clamp((u0 - 0.5) / 0.3))
        if T['knopf'] and t > T['knopf'] - 0.4:   # doigt (rond + rectangle) qui descend sur le bouton
            k = ease((t - T['knopf'] + 0.4) / 0.4); fy = 1180 - 110 * k
            d.rounded_rectangle([S(275), S(fy), S(325), S(fy + 200)], S(25), fill=(232, 196, 170, 255), outline=INK, width=S(4))
        if T['wahr'] and t > T['wahr']: text(lay, (CX, 330), 'du auch?', H2(70), GREY, clamp((t - T['wahr']) / 0.3))
        if T['klingelt'] and t > T['klingelt'] - 0.2:
            k = clamp((t - T['klingelt'] + 0.2) / 0.4); sh = 8 * math.sin(t * 60) * k
            phone(d, 790, 800, 300, 560, k, shake=sh); text(lay, (790 + sh, 700), 'Eingehender', BF(30), INK, k); text(lay, (790 + sh, 745), 'Anruf', BF(30), INK, k)
            callbtn(lay, d, 790 + sh, 960, 52, k)
            for j in range(3): arc(d, 790, 800, 330 + j * 30 + 15 * math.sin(t * 10), -30, 30, RED, 5)
        if T['woher'] and t > T['woher'] - 0.2: text(lay, (CX + 5, 790), '?', BF(int(180 * max(0.2, back((t - T['woher'] + 0.2) / 0.35)))), RED)
    elif sc == 1:  # la voix découpée en morceaux, transformée en chiffres
        text(lay, (CX, 330), 'alles beginnt mit deiner Stimme', H2(50), GREY, clamp(u0 / 0.4))
        pts = [(S(140 + q * 4), S(700 + 90 * math.sin(q * 0.17 + t * 4) * math.sin(q * 0.031))) for q in range(200)]
        d.line(pts, fill=INK, width=S(6))
        if T['stuecke'] and t > T['stuecke'] - 0.2:
            k = clamp((t - T['stuecke'] + 0.2) / 0.6)
            for j in range(10): line(d, 140 + j * 80, 590, 140 + j * 80, 810, RED + (int(255 * k),), 4)
        if T['fuenfzig'] and t > T['fuenfzig'] - 0.1: text(lay, (CX, 900), '50 × pro Sekunde', BF(64), RED, clamp((t - T['fuenfzig'] + 0.1) / 0.3))
        if T['zahlen'] and t > T['zahlen'] - 0.2:
            k = clamp((t - T['zahlen'] + 0.2) / 0.5); rs = np.random.RandomState(int(t * 8))
            text(lay, (CX, 1040), ' '.join(''.join(str(rs.randint(2)) for _ in range(4)) for _ in range(4)), BF(54), INK, k)
    elif sc == 2:  # ondes radio vers l'antenne
        phone(d, 230, 1000, 170, 300, u0 / 0.5); tower(d, 820, 1150, 520, u0 / 0.8)
        waves(d, 300, 930, 800, 650, t)
        text(lay, (CX, 330), 'Funkwellen zum Sendemast', H2(52), GREY, clamp(u0 / 0.4))
        if T['licht'] and t > T['licht'] - 0.2: text(lay, (CX, 1260), '300.000 km pro Sekunde', BF(54), RED, clamp((t - T['licht'] + 0.2) / 0.3))
        if T['ende'] and t > T['ende'] - 0.2: text(lay, (820, 520), 'nicht das Ende!', H2(60), RED, clamp((t - T['ende'] + 0.2) / 0.3))
    elif sc == 3:  # fibre optique sous terre jusqu'au central
        line(d, 60, 1000, 1020, 1000, GREY, 5); tower(d, 200, 1000, 420, 1)
        k = clamp(u0 / 0.8); line(d, 200, 1000, 200, 1120, RED, 8, k); line(d, 200, 1120, 800, 1120, RED, 8, clamp(u0 / 0.8 - 0.4)); line(d, 800, 1120, 800, 980, RED, 8, clamp(u0 / 0.8 - 0.9))
        central(lay, d, 800, 790, clamp((u0 - 0.6) / 0.8))
        for j in range(5):
            ph = ((t * 0.9) + j / 5) % 1; x = 200 + ph * 600; d.ellipse([S(x - 10), S(1110), S(x + 10), S(1130)], fill=(255, 220, 80, 255))
        text(lay, (500, 1180), 'Glasfaser unter der Erde', H2(52), INK, clamp((u0 - 0.5) / 0.3))
        text(lay, (CX, 330), 'der Mast ist nicht das Ende', H2(50), GREY, clamp(u0 / 0.4))
    elif sc == 4:  # alvéoles : le réseau sait dans quelle zone est le téléphone
        r = 95; k = clamp(u0 / 0.8); hi = (T['zuletzt'] and t > T['zuletzt'] - 0.2)
        for row in range(5):
            for col in range(5):
                hx = 180 + col * r * 1.73 + (r * 0.87 if row % 2 else 0); hy = 520 + row * r * 1.5
                if hx > 1000: continue
                special = (row, col) == (2, 2)
                hexagon(d, hx, hy, r * k, GREY if not (special and hi) else RED, 5, fill=(RED + (60,)) if special and hi else None)
                if special:
                    d.ellipse([S(hx - 16), S(hy - 16), S(hx + 16), S(hy + 16)], fill=INK)
                    if T['meldet'] and t > T['meldet']:
                        ph = ((t - T['meldet']) * 1.5) % 1; rr = 20 + ph * 80; arc(d, hx, hy, rr, 0, 360, RED + (int(230 * (1 - ph)),), 4)
        if T['meldet'] and t > T['meldet']: text(lay, (CX, 1230), 'Ich bin hier!', H2(64), RED, clamp((t - T['meldet']) / 0.3))
        if T['waben'] and t > T['waben'] - 0.2: text(lay, (CX, 330), 'das Netz = viele kleine Waben', H2(52), INK, clamp((t - T['waben'] + 0.2) / 0.3))
        else: text(lay, (CX, 330), 'die Zentrale weiß ungefähr …', H2(50), GREY, clamp(u0 / 0.4))
    elif sc == 5:  # central -> antenne -> téléphone qui sonne
        central(lay, d, 190, 700, 1); tower(d, 560, 1000, 420, 1); line(d, 330, 820, 560, 1000, RED, 6, clamp(u0 / 0.6))
        k = clamp((u0 - 0.5) / 0.5); waves(d, 600, 620, 860, 760, t) if k > 0 else None
        ring = T['klingelt2'] and t > T['klingelt2'] - 0.2; sh = 8 * math.sin(t * 60) if ring else 0
        phone(d, 880, 900, 170, 300, k, shake=sh); callbtn(lay, d, 880 + sh, 980, 36, k)
        if ring: text(lay, (880, 1120), 'klingelt!', H2(70), RED, clamp((t - T['klingelt2'] + 0.2) / 0.3))
        text(lay, (CX, 330), 'zum richtigen Mast', H2(56), GREY, clamp(u0 / 0.4))
    elif sc == 6:  # voiture : passage d'une antenne à l'autre
        line(d, 60, 1080, 1020, 1080, GREY, 5); tower(d, 250, 1050, 380, 1); tower(d, 830, 1050, 380, 1)
        x = 150 + 780 * clamp(u0 / max(1, SC[7] - SC[6] - 0.3))
        rect(d, x - 70, 1000, x + 70, 1050, INK, 7, 1, 14); rect(d, x - 40, 965, x + 40, 1005, INK, 6, 1, 10)
        for wx in (x - 40, x + 40): d.ellipse([S(wx - 16), S(1040), S(wx + 16), S(1072)], fill=INK)
        sw = T['uebergibt'] and t > T['uebergibt'] + 0.4; tx = 830 if sw else 250
        line(d, x, 960, tx, 680, RED if sw else BLUE, 5)
        text(lay, (CX, 330), 'Mast → Mast'.replace('→', '–'), H2(56), GREY, clamp(u0 / 0.4))
        if T['milli'] and t > T['milli'] - 0.2: text(lay, (CX, 1210), 'in Millisekunden', BF(58), RED, clamp((t - T['milli'] + 0.2) / 0.3))
    elif sc == 7:  # dans les deux sens
        phone(d, 250, 820, 200, 360, u0 / 0.5); phone(d, 830, 820, 200, 360, u0 / 0.5)
        for j in range(4):
            ph = ((t * 0.8) + j / 4) % 1; x1 = 360 + ph * 360; x2 = 720 - ph * 360
            d.ellipse([S(x1 - 12), S(780 - 12), S(x1 + 12), S(780 + 12)], fill=RED + (230,)); d.ellipse([S(x2 - 12), S(860 - 12), S(x2 + 12), S(860 + 12)], fill=BLUE + (230,))
        text(lay, (CX, 330), 'gleichzeitig in beide Richtungen', H2(48), GREY, clamp(u0 / 0.4))
        if T['beide'] and t > T['beide']: text(lay, (CX, 1120), 'für jedes Wort', H2(66), INK, clamp((t - T['beide']) / 0.3))
    elif sc == 8:  # cave / ascenseur : pas de réseau, batterie qui se vide
        line(d, 60, 820, 1020, 820, INK, 7); d.rectangle([S(200), S(830), S(880), S(860)], fill=GREY + (200,))
        rect(d, 200, 860, 880, 1180, INK, 7, ease(u0 / 0.6), 6); phone(d, 540, 1030, 110, 190, clamp(u0 / 0.6))
        tower(d, 860, 780, 360, 1); waves(d, 820, 470, 560, 900, t, n=3)
        text(lay, (CX, 330), 'Keller & Aufzug', H2(60), GREY, clamp(u0 / 0.4))
        if T['beton'] and t > T['beton'] - 0.2: cross(d, 640, 840, 40, (t - T['beton'] + 0.2) / 0.5); text(lay, (300, 1240), 'kein Netz', H2(60), RED, clamp((t - T['beton']) / 0.3))
        if T['akku'] and t > T['akku'] - 0.2: battery(d, 780, 1250, 1 - 0.85 * clamp((t - T['akku']) / 2.0))
    elif sc == 9:  # partage
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
HOT = re.compile(r'(\d|knopf|handy|netz|stimme|zahlen|funkwellen|sendemast|mast|licht|glasfaser|zentrale|waben|klingelt|millisekunden|keller|aufzug|beton|metall|akku|fünfzig)', re.I)
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
for k in ('knopf', 'klingelt', 'woher', 'fuenfzig', 'licht', 'glas', 'meldet', 'zuletzt', 'klingelt2', 'uebergibt', 'beton', 'akku'):
    if T[k]: sfx('pop', T[k], 0.1)
sfx('ding', 1.0, 0.08)
mix = mix / max(1e-6, np.abs(mix).max()) * 0.95
wo = wave.open(f'{tmp}/a.wav', 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR2); wo.writeframes((mix * 32767).astype('<i2').tobytes()); wo.close()
subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/f%05d.jpg', '-i', f'{tmp}/a.wav', '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
shutil.rmtree(tmp); print('ok', OUT, round(DUR, 2))
