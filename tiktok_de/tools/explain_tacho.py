# Vidéo explicative « dessin au trait » (style TikTok DE) : fond papier, schémas noir/rouge qui se dessinent, notes manuscrites,
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
TXT = open(os.path.join(DIR, 'script_v2.txt')).read().split('=== SCRIPT V2')[1].split('===\n', 1)[1].split('=== TRADUCTION')[0].strip()
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
WORDS = []
for k, s in enumerate(SENT):
    t0, t1 = bounds[k] + (0.04 if k else 0), bounds[k + 1] - 0.06; ws = s.split(); ww = [syl(w) + 0.35 for w in ws]; tt = sum(ww); c = 0
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
# ---------- 3. le compteur (0 à 160, aiguille)
def gauge(img, d, cx, cy, r, p_draw, val, alpha=1.0, red_from=None, label=True):
    arc(d, cx, cy, r, -90, -90 + 360 * ease(p_draw), INK, 9)
    if p_draw < 0.6: return
    k = clamp((p_draw - 0.6) / 0.4)
    arc(d, cx, cy, r * 0.78, 135, 405, GREY, 3)
    for v in range(0, 161, 20):
        ang = math.radians(135 + v / 160 * 270); r1 = r * 0.86; r2 = r * (0.95 if v % 40 == 0 else 0.91)
        line(d, cx + r1 * math.cos(ang), cy + r1 * math.sin(ang), cx + r2 * math.cos(ang), cy + r2 * math.sin(ang), GREY, 4, k)
        if v % 40 == 0 and label: text(img, (cx + r * 0.64 * math.cos(ang), cy + r * 0.64 * math.sin(ang)), str(v), F('Poppins-ExtraBold.ttf', S(r * 0.13)), GREY, k)
    if red_from is not None:
        a0 = 135 + red_from / 160 * 270; arc(d, cx, cy, r * 0.82, a0, 135 + val / 160 * 270, RED + (140,), 16)
    ang = math.radians(135 + val / 160 * 270); col = RED
    line(d, cx, cy, cx + r * 0.72 * math.cos(ang), cy + r * 0.72 * math.sin(ang), col, 7, k)
    d.ellipse([S(cx - 14), S(cy - 14), S(cx + 14), S(cy + 14)], fill=col)
# ---------- 4. les scènes (temps tirés de la voix)
T = {k: at(*v) if isinstance(v, tuple) else at(v) for k, v in {
    'vor': 'vor', 'f100': ('100', 0), 'tacho1': ('Tacho', 0), 'z114': ('114', 0), 'witz': 'Witz', 'erlaubt': 'erlaubt', 'misst': 'misst', 'direkt': 'direkt',
    'zaehlt': 'zählt', 'drehen': 'drehen', 'rechnet': ('rechnet', 0), 'umfang1': 'Reifenumfang', 'aber': 'Aber', 'staendig': 'ständig', 'luft': 'Luft', 'profil': 'Profil',
    'andere': 'andere', 'rechnung': 'Rechnung', 'niemals': 'niemals', 'erlaubt2': ('Erlaubt', 1), 'zehn': 'zehn', 'vier': 'vier', 'genau': 'Genau', 'v100': ('100', 1), 'v114': ('114', 1),
    'handy': 'Handy', 'gps': 'GPS', 'position': 'Position', 'maps': 'Maps', 'genauer': 'genauer', 'sags': "Sag's"}.items()}
print({k: round(v, 2) if v else v for k, v in T.items()})
SC = [0, T['misst'] - 0.1, T['zaehlt'] - 0.1, T['aber'] - 0.1, T['niemals'] - 0.5, T['handy'] - 0.2, T['sags'] - 0.15, DUR]
def scene_alpha(i, t):
    a0, a1 = SC[i], SC[i + 1]; return clamp((t - a0) / 0.25) * clamp((a1 - t) / 0.25 + (1 if i == len(SC) - 2 else 0))
def draw(t):
    img = Image.new('RGBA', (W * SS, H * SS), BG + (255,)); lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    sc = max(i for i in range(len(SC) - 1) if t >= SC[i])
    CX, CY = W / 2, 760
    if sc == 0:   # « Stell dir vor … 100 … 114 … erlaubt »
        text(lay, (CX, 330), 'stell dir vor …', H2(46), GREY, clamp((t - 0.1) / 0.4))
        v = 100 * ease((t - T['f100'] + 0.6) / 0.9)
        if t > T['z114'] - 0.1: v = 100 + 14 * back((t - T['z114'] + 0.1) / 0.5)
        gauge(lay, d, CX, CY, 300, (t - 0.05) / 0.9, v, red_from=100 if t > T['z114'] else None)
        if t > T['f100']: text(lay, (CX, 1160), 'du fährst: 100', H2(70), INK, clamp((t - T['f100']) / 0.3))
        if t > T['z114']:
            s = back((t - T['z114']) / 0.35); text(lay, (CX, 1290), '114', F('Poppins-ExtraBold.ttf', S(120 * max(0.3, s))), RED)
        if t > T['erlaubt']:
            text(lay, (CX, 1440), '… und das ist erlaubt!', H2(66), INK, clamp((t - T['erlaubt']) / 0.3)); underline(d, CX - 250, CX + 250, 1478, RED, ease((t - T['erlaubt']) / 0.5))
    elif sc == 1:  # « misst gar nicht direkt »
        gauge(lay, d, CX, CY, 300, 1, 114 + 3 * math.sin(t * 9), red_from=None)
        text(lay, (CX, 330), 'misst dein Tempo …', H2(46), GREY, clamp((t - SC[1]) / 0.4))
        if t > T['direkt'] - 0.3:
            cross(d, CX, CY, 230, (t - T['direkt'] + 0.3) / 0.5); text(lay, (CX, 1190), 'gar nicht direkt', H2(78), RED, clamp((t - T['direkt'] + 0.2) / 0.3))
    elif sc == 2:  # roue qui tourne + formule
        rot = (t - SC[2]) * 260; R = 230; p = (t - SC[2]) / 0.7; cy = 640
        arc(d, CX, cy, R, -90, -90 + 360 * ease(p), INK, 26); arc(d, CX, cy, R * 0.62, 0, 360 * ease(p - 0.2), GREY, 5)
        for k in range(6):
            ang = math.radians(rot + k * 60); line(d, CX, cy, CX + R * 0.6 * math.cos(ang), cy + R * 0.6 * math.sin(ang), INK, 6, ease(p - 0.4))
        ang = math.radians(rot); d.ellipse([S(CX + R * math.cos(ang)) - S(16), S(cy + R * math.sin(ang)) - S(16), S(CX + R * math.cos(ang)) + S(16), S(cy + R * math.sin(ang)) + S(16)], fill=RED)
        n = int(max(0, t - T['zaehlt']) * 260 / 360) + 1 if t > T['zaehlt'] else 0
        if n: text(lay, (CX, 960), f'Umdrehungen: {n}', H2(72), INK, clamp((t - T['zaehlt']) / 0.3))
        if t > T['rechnet'] - 0.2:
            q = (t - T['rechnet'] + 0.2) / 0.7; rect(d, 150, 1060, 930, 1330, INK, 7, ease(q))
            text(lay, (CX, 1150), 'Umdrehungen × Umfang', F('Poppins-ExtraBold.ttf', S(54)), INK, clamp(q * 1.5 - 0.4))
            text(lay, (CX, 1250), '= dein Tempo', F('Poppins-ExtraBold.ttf', S(58)), RED, clamp(q * 1.5 - 0.7))
        if T['umfang1'] and t > T['umfang1']:
            underline(d, 620, 840, 1180, RED, ease((t - T['umfang1']) / 0.4), 14); text(lay, (CX, 1400), 'ab Werk fest eingestellt', H2(54), GREY, clamp((t - T['umfang1']) / 0.4))
    elif sc == 3:  # le pneu change : air, profil, autres pneus
        base = 230; cy = 700; r = base
        if T['luft'] and t > T['luft']: r -= 22 * ease((t - T['luft']) / 0.5)
        if T['profil'] and t > T['profil']: r -= 14 * ease((t - T['profil']) / 0.5)
        if T['andere'] and t > T['andere']: r += 60 * math.sin(clamp((t - T['andere']) / 0.6) * math.pi / 2) * (1 if int((t - T['andere']) * 2) % 2 == 0 else 0.6)
        for k in range(40):
            if k % 2 == 0: arc(d, CX, cy, base + 28, k * 9, k * 9 + 5, GREY, 3)
        arc(d, CX, cy, r, -90, 270, INK, 24); text(lay, (CX, 330), 'der Umfang ändert sich ständig', H2(46), GREY, clamp((t - SC[3]) / 0.4))
        for key, lab, y in (('luft', '– weniger Luft', 1040), ('profil', '– Profil abgefahren', 1150), ('andere', '– andere Reifen', 1260)):
            if T[key] and t > T[key] - 0.1: text(lay, (CX, y), lab, H2(70), RED, clamp((t - T[key] + 0.1) / 0.3))
        if T['rechnung'] and t > T['rechnung'] - 0.2:
            q = (t - T['rechnung'] + 0.2) / 0.5; rect(d, 200, 1360, 880, 1490, RED, 6, ease(q)); text(lay, (CX, 1425), 'Rechnung stimmt nicht', F('Poppins-ExtraBold.ttf', S(48)), RED, clamp(q * 2 - 0.5))
    elif sc == 4:  # la loi : jamais trop peu, +10 % +4 km/h, 100 → 114
        v = 100
        if T['zehn'] and t > T['zehn']: v += 10 * ease((t - T['zehn']) / 0.5)
        if T['vier'] and t > T['vier']: v += 4 * ease((t - T['vier']) / 0.5)
        gauge(lay, d, CX, CY - 60, 290, (t - SC[4]) / 0.6, v, red_from=100 if v > 100.5 else None)
        text(lay, (CX, 330), 'so viel darf oben drauf', H2(46), GREY, clamp((t - SC[4]) / 0.4))
        if T['niemals']: text(lay, (CX, 1090), 'zu wenig anzeigen? niemals', H2(54), INK, clamp((t - T['niemals']) / 0.3) * (1 - clamp((t - (T['zehn'] or 99) + 0.3) / 0.3)))
        if T['zehn'] and t > T['zehn']: text(lay, (CX - 170, 1110), '+ 10 %', F('Poppins-ExtraBold.ttf', S(74)), RED, clamp((t - T['zehn']) / 0.3))
        if T['vier'] and t > T['vier']: text(lay, (CX + 170, 1110), '+ 4 km/h', F('Poppins-ExtraBold.ttf', S(74)), RED, clamp((t - T['vier']) / 0.3))
        if T['v100'] and t > T['v100'] - 0.2:
            q = clamp((t - T['v100'] + 0.2) / 0.3); text(lay, (CX - 200, 1300), '100', F('Poppins-ExtraBold.ttf', S(110)), INK, q)
            line(d, CX - 80, 1300, CX + 60, 1300, INK, 8, ease((t - T['v100']) / 0.4)); line(d, CX + 30, 1275, CX + 60, 1300, INK, 8, ease((t - T['v100'] - 0.3) / 0.2)); line(d, CX + 30, 1325, CX + 60, 1300, INK, 8, ease((t - T['v100'] - 0.3) / 0.2))
        if T['v114'] and t > T['v114'] - 0.1: text(lay, (CX + 200, 1300), '114', F('Poppins-ExtraBold.ttf', S(int(110 * max(0.3, back((t - T['v114'] + 0.1) / 0.35))))), RED)
    elif sc == 5:  # téléphone + satellite GPS
        p = (t - SC[5]) / 0.8; px0, py0, px1, py1 = 560, 520, 860, 1080
        rect(d, px0, py0, px1, py1, INK, 9, ease(p), 40); line(d, 680, 548, 740, 548, INK, 6, ease(p - 0.6))
        if T['gps'] and t > T['gps'] - 0.3:
            q = (t - T['gps'] + 0.3) / 0.6; sx, sy = 270, 470
            rect(d, sx - 50, sy - 40, sx + 50, sy + 40, INK, 7, ease(q), 8); rect(d, sx - 150, sy - 25, sx - 70, sy + 25, INK, 6, ease(q - 0.2), 4); rect(d, sx + 70, sy - 25, sx + 150, sy + 25, INK, 6, ease(q - 0.2), 4)
            line(d, sx - 70, sy, sx - 50, sy, INK, 6, ease(q - 0.3)); line(d, sx + 50, sy, sx + 70, sy, INK, 6, ease(q - 0.3))
            for k in range(3):
                ph = ((t - T['gps']) * 1.2 - k * 0.33) % 1; rr = 60 + ph * 260
                if t > T['gps']: arc(d, sx, sy, rr, 20, 70, RED + (int(255 * (1 - ph)),), 6)
            text(lay, ((px0 + px1) / 2, 760), 'GPS', F('Poppins-ExtraBold.ttf', S(76)), RED, clamp(q * 2 - 0.6))
        if T['position'] and t > T['position'] - 0.2:
            q = ease((t - T['position'] + 0.2) / 0.4); pcx, pcy = (px0 + px1) / 2, 930
            d.ellipse([S(pcx - 34 * q), S(pcy - 70 * q), S(pcx + 34 * q), S(pcy - 2 * q)], fill=RED); d.polygon([(S(pcx - 30 * q), S(pcy - 30 * q)), (S(pcx + 30 * q), S(pcy - 30 * q)), (S(pcx), S(pcy + 20 * q))], fill=RED)
            d.ellipse([S(pcx - 12 * q), S(pcy - 48 * q), S(pcx + 12 * q), S(pcy - 24 * q)], fill=BG); text(lay, (CX, 1180), 'deine echte Position', H2(66), INK, q)
        text(lay, (CX, 330), 'dein Handy rechnet anders', H2(46), GREY, clamp((t - SC[5]) / 0.4))
        if T['genauer'] and t > T['genauer'] - 0.3:
            q = (t - T['genauer'] + 0.3) / 0.5; rect(d, 190, 1290, 890, 1430, RED, 6, ease(q)); text(lay, (CX - 40, 1360), 'meistens genauer', F('Poppins-ExtraBold.ttf', S(54)), RED, clamp(q * 2 - 0.5)); check(d, 830, 1360, 30, q - 0.5)
    elif sc == 6:  # partage
        p = (t - SC[6]) / 0.7; cx, cy = CX, 760
        for (x, y) in ((cx - 170, cy), (cx + 150, cy - 140), (cx + 150, cy + 140)):
            arc(d, x, y, 62, -90, -90 + 360 * ease(p), INK, 9)
        line(d, cx - 115, cy - 25, cx + 95, cy - 115, INK, 8, ease(p - 0.4)); line(d, cx - 115, cy + 25, cx + 95, cy + 115, INK, 8, ease(p - 0.4))
        text(lay, (CX, 1120), "sag's weiter", H2(96), RED, clamp((t - SC[6] - 0.3) / 0.4)); underline(d, CX - 230, CX + 230, 1180, RED, ease((t - SC[6] - 0.6) / 0.5), 10)
        text(lay, (CX, 1260), 'sagt dir ja sonst keiner.', H2(64), GREY, clamp((t - SC[6] - 0.9) / 0.4))
    al = scene_alpha(sc, t)
    if al < 1: lay.putalpha(lay.getchannel('A').point(lambda v: int(v * al)))
    img.alpha_composite(lay)
    if NAME or HANDLE:   # signature fixe (nom manuscrit + @pseudo en rouge), comme sur les vidéos de référence
        sg = Image.new('RGBA', img.size, (0, 0, 0, 0))
        if NAME: ImageDraw.Draw(sg).text((S(70), S(150)), NAME, font=HAND(S(56)), fill=GREY + (255,), anchor='ls')
        if HANDLE: ImageDraw.Draw(sg).text((S(70), S(200)), HANDLE, font=HAND(S(44)), fill=RED + (255,), anchor='ls')
        img.alpha_composite(sg)
    img = img.resize((W, H), Image.LANCZOS)
    caption(img, t); return img.convert('RGB')
# ---------- 5. sous-titres : 3 mots max, majuscules, contour noir, mot clé en jaune
HOT = re.compile(r'(\d|tacho|reifen|umfang|gps|maps|luft|profil|erlaubt|niemals|prozent|kmh|km/h|rechnung|position|genauer|direkt|witz|handy)', re.I)
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
for n in range(NF): draw(n / FPS).save(f'{tmp}/f{n:05d}.jpg', quality=92)
SR2 = 44100; v = np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', os.path.join(DIR, VOICE), '-ac', '1', '-ar', str(SR2), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(float) / 32768
mix = np.zeros(int(DUR * SR2)); mix[:len(v)] += v
def sfx(name, t0, g):
    w = wave.open('/home/user/skillora./motion/sfx/' + name + '.wav'); s = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float) / 32768
    if w.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
    if w.getframerate() != SR2: s = np.interp(np.arange(0, len(s), w.getframerate() / SR2), np.arange(len(s)), s)
    i0 = int(max(0, t0) * SR2); L = min(len(s), len(mix) - i0); mix[i0:i0 + L] += s[:L] * g
for t0 in SC[1:-1]: sfx('swish', t0, 0.12)
for k in ('z114', 'erlaubt', 'direkt', 'rechnet', 'luft', 'profil', 'andere', 'rechnung', 'zehn', 'vier', 'v114', 'gps', 'position', 'genauer'):
    if T[k]: sfx('pop', T[k], 0.1)
mix = mix / max(1e-6, np.abs(mix).max()) * 0.95
wo = wave.open(f'{tmp}/a.wav', 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR2); wo.writeframes((mix * 32767).astype('<i2').tobytes()); wo.close()
subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/f%05d.jpg', '-i', f'{tmp}/a.wav', '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
shutil.rmtree(tmp); print('ok', OUT, round(DUR, 2))
