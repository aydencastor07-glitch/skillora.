# Vidéos Temu « animaux » (copie du style ref_animaux) : une photo d'animal plein écran + cartes de texte façon TikTok.
# usage : animaux.py videos.json <clé> out.mp4 [PREVIEW=t1,t2]
# Chaque vidéo : img, dur, focus [x,y] (0-1), zoom, font, code_font, styles [[fond, texte]...], entry (pop|slide|drop),
#   disc_y (hauteur de l'avertissement permanent), cards [{k: intro|offre, off, y, st, how, al, d}]
import json, sys, os, math, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
ALL = json.load(open(sys.argv[1])); C = ALL[sys.argv[2]]; OUT = sys.argv[3]
W, H, FPS = 1080, 1920, 30
FD = '/home/user/skillora./temu/fonts/'; SFX = '/home/user/skillora./motion/sfx/'
LOGO = Image.open('/home/user/skillora./temu/temu_logo.png').convert('RGBA')
OFF = {  # offres et codes donnés par Temu (compte affilié)
    '0':    (["Cadeaux à 0€"], 'alr391702', "avec des commandes éligibles"),
    '100':  (["Lot de coupons", "de 100€"], 'all201843'),
    '200':  (["Lot de coupons", "de 200€"], 'als427239'),
    '40':   (["40% de réduction"], 'als427239'),
    'prix': (["Prix abordables"], 'alx673514'),
}
HOW = ["1. Téléchargez l'appli Temu", "2. Ouvrez l'application", "3. Tapez le code dans", "la barre de recherche"]
DISC = ["Réservé aux utilisateurs de l'application France.", "Accédez à l'application Temu et recherchez", "le code dans la barre de recherche."]
_fc = {}
def F(name, sz):
    k = (name, int(sz))
    if k not in _fc: _fc[k] = ImageFont.truetype(FD + name, int(sz))
    return _fc[k]
def hexc(c): return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) if isinstance(c, str) else tuple(c)

def tbox(lines, font, sz, fg, bg, maxw=940, al='c', padx=30, pady=14, rad=24, stroke=0):
    """Texte façon TikTok : chaque ligne dans son bloc arrondi, blocs collés les uns aux autres."""
    f = F(font, sz)
    while max(f.getbbox(l)[2] for l in lines) + 2 * padx > maxw and sz > 30: sz -= 2; f = F(font, sz)
    asc, dsc = f.getmetrics(); lh = asc + dsc; rows = []
    for l in lines:
        bb = f.getbbox(l); rows.append((l, bb[2] - bb[0], bb[0]))
    bw = max(r[1] for r in rows) + 2 * padx; bh = len(rows) * (lh + 2 * pady) - (len(rows) - 1) * 10
    im = Image.new('RGBA', (bw, bh + 4)); d = ImageDraw.Draw(im); y = 0; fg, bg = hexc(fg), hexc(bg)
    for l, w, x0 in rows:
        x = {'c': (bw - w - 2 * padx) // 2, 'l': 0, 'r': bw - w - 2 * padx}[al]
        d.rounded_rectangle([x, y, x + w + 2 * padx, y + lh + 2 * pady], rad, fill=bg + (255,))
        y += lh + 2 * pady - 10
    y = 0
    for l, w, x0 in rows:
        x = {'c': (bw - w - 2 * padx) // 2, 'l': 0, 'r': bw - w - 2 * padx}[al]
        d.text((x + padx - x0, y + pady + 2), l, font=f, fill=fg + (255,), stroke_width=stroke, stroke_fill=bg + (255,))
        y += lh + 2 * pady - 10
    return im

def stack(parts, gap=18, al='c'):
    w = max(p.width for p in parts); h = sum(p.height for p in parts) + gap * (len(parts) - 1)
    im = Image.new('RGBA', (w, h)); y = 0
    for p in parts:
        x = {'c': (w - p.width) // 2, 'l': 0, 'r': w - p.width}[al]; im.alpha_composite(p, (x, y)); y += p.height + gap
    return im

def logo_badge(h=120):
    lg = LOGO.resize((int(LOGO.width * h / LOGO.height), h), Image.LANCZOS)
    return lg

def card(c):
    st = C['styles']; s = st[c.get('st', 0) % len(st)]; al = c.get('al', 'c'); font = C['font']
    parts = []
    if c['k'] == 'intro':
        parts.append(logo_badge(C.get('logo_h', 150)))
        parts.append(tbox(C.get('intro', ["Les offres Temu", "à découvrir"])[:2], font, C.get('tsz', 84), s[1], s[0], al=al))
    else:
        lines, code = OFF[c['off']][:2]
        if c.get('logo'): parts.append(logo_badge(100))
        tb = tbox(lines, font, C.get('tsz', 84), s[1], s[0], al=al)
        if len(OFF[c['off']]) > 2:  # sous-ligne plus petite, collée au titre
            tb = stack([tb, tbox([OFF[c['off']][2]], font, int(C.get('tsz', 84) * 0.55), s[1], s[0], al=al, pady=8, rad=16)], -8, al)
        parts.append(tb)
        cs = st[(c.get('st', 0) + 1) % len(st)] if not c.get('cst') else c['cst']
        parts.append(tbox([C.get('code_lbl', 'Code :') + ' ' + code], C.get('code_font', font), C.get('csz', 78), cs[1], cs[0], al=al, padx=34, pady=18))
        if c.get('how'):
            hs = c.get('hst', C.get('how_style', ['#ffffff', '#111111']))
            parts.append(tbox(HOW, C.get('how_font', 'Poppins-ExtraBold.ttf'), 46, hs[1], hs[0], al=al, rad=18, pady=10))
    return stack(parts, C.get('gap', 16), al)

def disc_img():
    f = F('Poppins-ExtraBold.ttf', 32); asc, dsc = f.getmetrics(); lh = asc + dsc + 4
    im = Image.new('RGBA', (W, lh * len(DISC) + 8)); d = ImageDraw.Draw(im)
    for i, l in enumerate(DISC):
        w = f.getbbox(l)[2]; d.text(((W - w) // 2, 4 + i * lh), l, font=f, fill=(255, 255, 255, 240), stroke_width=3, stroke_fill=(0, 0, 0, 235))
    return im

# --- préparation
SRC = Image.open(C['img']).convert('RGB')
sc = max(W / SRC.width, H / SRC.height); BW, BH = SRC.width * sc, SRC.height * sc
CARDS = []; t = 0
for c in C['cards']:
    CARDS.append((t, t + c['d'], card(c), c)); t += c['d']
DUR = t; DISC_IM = disc_img(); ENTRY = C.get('entry', 'pop'); DY = int(C.get('disc_y', 0.105) * H)
YMIN, YMAX = (DY + DISC_IM.height + 24, 1590) if DY < H / 2 else (300, DY - 24)
def ease_back(x):
    x = min(1, max(0, x)); c1 = 1.7; return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2

def frame(tt):
    z = 1 + C.get('zoom', 0.1) * tt / DUR; fx, fy = C.get('focus', [0.5, 0.5])
    vw, vh = W / (sc * z), H / (sc * z)
    pan = C.get('pan', [0, 0]); cx = fx * SRC.width + pan[0] * tt / DUR * SRC.width; cy = fy * SRC.height + pan[1] * tt / DUR * SRC.height
    x0 = min(max(0, cx - vw / 2), SRC.width - vw); y0 = min(max(0, cy - vh / 2), SRC.height - vh)
    bg = SRC.transform((W, H), Image.EXTENT, (x0, y0, x0 + vw, y0 + vh), Image.BILINEAR).convert('RGBA')
    for a, b, im, c in CARDS:
        if not (a <= tt < b): continue
        p = (tt - a) / 0.32; e = ease_back(p); alpha = min(1, (tt - a) / 0.12, (b - tt) / 0.1)
        ci = im; dx = dy = 0
        if ENTRY == 'pop':
            s = 0.75 + 0.25 * e; ci = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)
        elif ENTRY == 'slide': dx = int((1 - e) * (-W if c.get('al', 'c') != 'r' else W) * 0.6)
        elif ENTRY == 'drop': dy = int((1 - e) * -260)
        if c['k'] == 'offre' and tt - a > 0.4:  # petit battement
            s = 1 + 0.018 * math.sin((tt - a) * 7); ci = ci.resize((int(ci.width * s), int(ci.height * s)), Image.BILINEAR)
        al = c.get('al', 'c'); cyp = int(c['y'] * H)
        x = {'c': (W - ci.width) // 2, 'l': 60, 'r': W - 60 - ci.width}[al] + dx; y = cyp - ci.height // 2 + dy
        y = min(max(y, YMIN), YMAX - ci.height)  # jamais sur l'avertissement ni dans les zones de l'interface
        if alpha < 1:
            ci = ci.copy(); ci.putalpha(ci.getchannel('A').point(lambda v: int(v * alpha)))
        bg.alpha_composite(ci, (x, y))
    bg.alpha_composite(DISC_IM, (0, DY))
    return bg.convert('RGB')

if __name__ == '__main__':
    if os.environ.get('PREVIEW'):
        for ts in os.environ['PREVIEW'].split(','): frame(float(ts)).save(f'{OUT}_{ts}.jpg', quality=88)
        sys.exit(0)
    SR = 44100; tmpw = OUT + '_m.wav'
    subprocess.run([sys.executable, '/home/user/skillora./temu/tools/popbeat.py', str(DUR), tmpw, str(C.get('seed', 1)), str(C.get('bpm', 112)), str(C.get('key', 57))], check=True, capture_output=True)
    wm = wave.open(tmpw); m = np.frombuffer(wm.readframes(wm.getnframes()), '<i2').astype(float) / 32768
    if wm.getnchannels() == 2: m = m.reshape(-1, 2).mean(1)
    m = np.pad(m, (0, max(0, int(DUR * SR) - len(m))))[:int(DUR * SR)] * 0.55
    fo = int(0.25 * SR); m[-fo:] *= np.linspace(1, 0, fo)
    def sfx(name, t0, g):
        ws = wave.open(SFX + name + '.wav'); s = np.frombuffer(ws.readframes(ws.getnframes()), '<i2').astype(float) / 32768
        if ws.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
        if ws.getframerate() != SR: s = np.interp(np.arange(0, len(s), ws.getframerate() / SR), np.arange(len(s)), s)
        a0 = int(max(0, t0) * SR); L = min(len(s), len(m) - a0)
        if L > 0: m[a0:a0 + L] += s[:L] * g
    for a, b, im, c in CARDS: sfx(C.get('sfx', 'pop'), a, 0.35)
    m = np.clip(m, -1, 1)  # niveau final réglé par loudnorm (-14 LUFS) à l'encodage
    wo = wave.open(tmpw, 'w'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR)
    wo.writeframes((m * 32767).astype('<i2').tobytes()); wo.close()
    p = subprocess.Popen([FF, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                          '-i', tmpw, '-c:v', 'libx264', '-crf', '19', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', '44100', '-c:a', 'aac', '-b:a', '160k',
                          '-shortest', '-movflags', '+faststart', OUT], stdin=subprocess.PIPE)
    for n in range(int(round(DUR * FPS))): p.stdin.write(frame(n / FPS).tobytes())
    p.stdin.close(); p.wait(); os.remove(tmpw)
    print(OUT, DUR)
