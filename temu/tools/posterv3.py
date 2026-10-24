# Style « cartes qu'on swipe » (3e style Temu) : fond flou, photo en carte qui arrive et repart comme un swipe,
# barre de progression façon story + compteur, neige qui tombe, étiquette « $0 GIFTS » suspendue qui se balance,
# nom de l'article tapé sur une étiquette, CODE sur une plaque d'immatriculation, description dans une bulle de commentaire.
# Le code est toujours affiché en entier.  usage : posterv3.py config.json out.mp4  [PREVIEW=t1,t2]
import json, sys, os, math, subprocess, shutil, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
C = json.load(open(sys.argv[1])); OUT = sys.argv[2]; D = os.path.dirname(os.path.abspath(sys.argv[1]))
W, H, FPS = 1080, 1920, 30; SL = C['slide_dur']; TR = 0.5
FD = '/home/user/skillora./temu/fonts/'; SFX = '/home/user/skillora./motion/sfx/'
P = C['palette']; C1, C2, DK, ACC = [tuple(P[k]) for k in ('c1', 'c2', 'dark', 'acc')]; HF = C['font']; CF = 'Poppins-ExtraBold.ttf'
CODE = C['code']; TXT = C['code_text']; HEAD = C['header']
DISC = C.get('disclaimer', '*T&Cs apply. The purchase required is determined by the gift(s)\' value.')
DESC = C.get('desc', f"These Temu finds can't be missed! Search my code [{CODE}] to unlock $0 gifts with qualifying orders on Temu! T&Cs apply.")
LOGO = Image.open('/home/user/skillora./temu/temu_logo.png').convert('RGBA')
_fc = {}
def F(name, sz):
    k = (name, int(sz))
    if k not in _fc: _fc[k] = ImageFont.truetype(FD + name, max(8, int(sz)))
    return _fc[k]
def clamp(u): return max(0.0, min(1.0, u))
def ease(u): u = clamp(u); return 1 - (1 - u) ** 3
def eio(u): u = clamp(u); return u * u * (3 - 2 * u)
def back(u): u = clamp(u); c = 1.7; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2
def fit(txt, name, sz, maxw):
    f = F(name, sz)
    while f.getbbox(txt)[2] > maxw and sz > 18: sz -= 3; f = F(name, sz)
    return f
def comp(img, lay, xy):
    x, y = int(xy[0]), int(xy[1]); cx0, cy0 = max(0, -x), max(0, -y)
    if cx0 >= lay.width or cy0 >= lay.height or x >= img.width or y >= img.height: return
    img.alpha_composite(lay.crop((cx0, cy0, min(lay.width, img.width - x), min(lay.height, img.height - y))), (x + cx0, y + cy0))
def put(img, lay, cx, cy, s=1.0, rot=0.0, a=1.0):
    if s <= 0.02 or a <= 0.01: return
    if s != 1.0: lay = lay.resize((max(1, int(lay.width * s)), max(1, int(lay.height * s))), Image.BILINEAR)
    if rot: lay = lay.rotate(rot, expand=True, resample=Image.BICUBIC)
    if a < 0.99: lay = lay.copy(); lay.putalpha(lay.getchannel('A').point(lambda v: int(v * a)))
    comp(img, lay, (cx - lay.width / 2, cy - lay.height / 2))
# ---- photos : fond flou sombre + carte à bords arrondis avec cadre blanc et ombre
CW, CH, CY = 860, 1180, 850
def cover(im, w, h):
    s = max(w / im.width, h / im.height); im = im.resize((int(im.width * s + 0.5), int(im.height * s + 0.5)), Image.LANCZOS)
    return im.crop(((im.width - w) // 2, (im.height - h) // 2, (im.width - w) // 2 + w, (im.height - h) // 2 + h))
BGS, CARDS = [], []
for s in C['slides']:
    im = Image.open(os.path.join(D, s['img'])).convert('RGB')
    bg = cover(im, W, H).filter(ImageFilter.GaussianBlur(28)); bg = Image.blend(bg, Image.new('RGB', (W, H), DK), 0.45); BGS.append(bg)
    ph = cover(im, CW, CH); m = Image.new('L', (CW, CH), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, CW - 1, CH - 1], 36, fill=255)
    card = Image.new('RGBA', (CW + 80, CH + 80), (0, 0, 0, 0)); sh = Image.new('L', card.size, 0); ImageDraw.Draw(sh).rounded_rectangle([40, 52, CW + 40, CH + 52], 44, fill=150)
    card.putalpha(sh.filter(ImageFilter.GaussianBlur(18)))
    fr = Image.new('RGBA', (CW + 24, CH + 24), (0, 0, 0, 0)); ImageDraw.Draw(fr).rounded_rectangle([0, 0, CW + 23, CH + 23], 46, fill=(255, 255, 255, 255)); comp(card, fr, (28, 28))
    pr = ph.convert('RGBA'); pr.putalpha(m); comp(card, pr, (40, 40)); CARDS.append(card)
N = len(CARDS); DUR = N * SL
# ---- éléments
def snow(img, T, n=70, front=False):
    rs = np.random.RandomState(9 if front else 3); d = ImageDraw.Draw(img)
    for j in range(n):
        x0 = rs.uniform(0, W); sp = rs.uniform(70, 160) * (1.5 if front else 1); r = rs.uniform(3, 7) * (1.6 if front else 1); ph = rs.uniform(0, 6.3)
        y = (rs.uniform(0, H) + sp * T) % (H + 40) - 20; x = x0 + 30 * math.sin(T * 1.3 + ph)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 200 if front else 150))
def header(img, T, i, t):
    d = ImageDraw.Draw(img); sw = (W - 120 - (N - 1) * 12) / N
    for k in range(N):   # barre de progression façon story
        x0 = 60 + k * (sw + 12); d.rounded_rectangle([x0, 52, x0 + sw, 62], 5, fill=(255, 255, 255, 90))
        p = 1 if k < i else (clamp(t / SL) if k == i else 0)
        if p > 0: d.rounded_rectangle([x0, 52, x0 + sw * p, 62], 5, fill=(255, 255, 255, 255))
    comp(img, LOGO.resize((96, 96), Image.LANCZOS), (60, 92))
    d.text((176, 140), HEAD, font=fit(HEAD, HF, 76, 650), fill=(255, 255, 255), anchor='lm', stroke_width=3, stroke_fill=DK)
    k = back(t / 0.35); cnt = f'{i + 1}/{N}'; lay = Image.new('RGBA', (170, 100), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
    ld.rounded_rectangle([0, 0, 169, 99], 50, fill=C2 + (255,)); ld.text((85, 52), cnt, font=F(CF, 54), fill=DK, anchor='mm'); put(img, lay, W - 135, 140, k)
def tag(img, cx, cy, T, t):
    # étiquette suspendue « $0 GIFTS » : ficelle + balancement amorti
    sw = 22 * math.sin(T * 3.1) * (0.4 + 0.6 * math.exp(-t * 1.2)); a = math.radians(sw); L = 120
    ex, ey = cx + L * math.sin(a), cy + L * math.cos(a); d = ImageDraw.Draw(img); d.line([cx, cy, ex, ey], fill=(255, 255, 255), width=5); d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=(255, 255, 255))
    lay = Image.new('RGBA', (240, 300), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
    ld.polygon([(120, 0), (240, 70), (240, 300), (0, 300), (0, 70)], fill=ACC + (255,)); ld.ellipse([105, 30, 135, 60], fill=(0, 0, 0, 0))
    ld.text((120, 150), '$0', font=F(CF, 110), fill=(255, 255, 255), anchor='mm'); ld.text((120, 245), 'GIFTS', font=F(CF, 50), fill=(255, 255, 255), anchor='mm')
    lay = lay.rotate(-sw, expand=True, resample=Image.BICUBIC); put(img, lay, ex + 150 * math.sin(a) * 0.98, ey + 130 * math.cos(a), back(t / 0.45))
def label(img, txt, x, y, t):
    # nom de l'article tapé sur une bande, puis coche
    n = int(max(0, t - 0.35) * 30); s = txt[:n]; f = fit(txt, HF, 70, 700); tw = f.getbbox(txt)[2]
    u = ease((t - 0.25) / 0.3)
    if u <= 0: return
    d = ImageDraw.Draw(img); d.rounded_rectangle([x, y - 55, x + (tw + 150) * u, y + 55], 22, fill=DK + (235,))
    d.text((x + 32, y), s, font=f, fill=C1, anchor='lm')
    if n >= len(txt):
        q = ease((t - 0.35 - len(txt) / 30) / 0.3); cx = x + tw + 95
        d.ellipse([cx - 32, y - 32, cx + 32, y + 32], fill=C2 + (255,))
        if q > 0: d.line([(cx - 16, y), (cx - 4, y + 13)], fill=DK, width=8); d.line([(cx - 4, y + 13), (cx - 4 + 22 * q, y + 13 - 28 * q)], fill=DK, width=8)
def plate(img, T):
    # plaque d'immatriculation (bande bleue avec logo, code en noir) + phrase officielle dessous ; rien ne passe jamais devant le code
    x0, y0, pw, ph = 110, 1555, W - 220, 150; d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0 - 6, y0 - 6, x0 + pw + 6, y0 + ph + 6], 22, fill=(20, 20, 20, 255)); d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], 18, fill=(250, 250, 250, 255))
    st = tuple(C.get('strip', [0, 51, 153])) + (255,)   # bande de gauche (bleu plaque par défaut)
    d.rounded_rectangle([x0, y0, x0 + 110, y0 + ph], 18, fill=st); d.rectangle([x0 + 60, y0, x0 + 110, y0 + ph], fill=st)
    comp(img, LOGO.resize((76, 76), Image.LANCZOS), (x0 + 17, y0 + 20)); d.text((x0 + 55, y0 + 122), 'CODE', font=F(CF, 26), fill=(255, 220, 0), anchor='mm')
    d.text((x0 + 110 + (pw - 110) / 2, y0 + ph / 2 + 4), CODE, font=fit(CODE, CF, 112, pw - 170), fill=(15, 15, 15), anchor='mm')
    f = fit(TXT, CF, 42, W - 100); d.text((W / 2, y0 + ph + 62), TXT, font=f, fill=(255, 255, 255), anchor='mm', stroke_width=3, stroke_fill=DK)
    d.text((W / 2, 1878), DISC, font=fit(DISC, 'Nunito.ttf', 26, W - 100), fill=(255, 255, 255), anchor='mm', stroke_width=3, stroke_fill=(0, 0, 0))
def comment(img, t):
    # bulle de commentaire façon TikTok avec la description qui s'écrit
    u = back(t / 0.4)
    if u <= 0.02: return
    f = F(CF, 40); ws = DESC.split(); lines = []; cur = ''
    for w in ws:
        if cur and f.getbbox(cur + ' ' + w)[2] > 700: lines.append(cur); cur = w
        else: cur = (cur + ' ' + w).strip()
    lines.append(cur); n = int(max(0, t - 0.3) * 120); bh = 110 + 54 * len(lines)
    lay = Image.new('RGBA', (900, bh + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); d.rounded_rectangle([0, 0, 899, bh], 36, fill=(255, 255, 255, 245))
    d.polygon([(90, bh - 2), (150, bh - 2), (95, bh + 38)], fill=(255, 255, 255, 245))
    comp(lay, LOGO.resize((70, 70), Image.LANCZOS), (30, 22)); d.text((120, 57), 'temu.finds  ·  #ad', font=F(CF, 34), fill=(110, 110, 110), anchor='lm')
    y = 128
    for l in lines:
        s = l[:max(0, n)]; n -= len(l) + 1; x = 40
        for w in s.split(' '):
            d.text((x, y), w, font=f, fill=ACC if (CODE in w or '$0' in w) else (25, 25, 25), anchor='lm'); x += f.getbbox(w + ' ')[2]
        y += 54
    put(img, lay, W / 2, 1060, u)
def card_pos(i, t):
    # carte qui arrive de la droite en tournant, se pose, puis repart à gauche (swipe) pendant la transition suivante
    q = ease(t / TR); x = W / 2 + 1150 * (1 - q); rot = -14 * (1 - q) + 1.2 * math.sin(t * 1.6) * q; z = 1 + 0.025 * clamp(t / SL)
    return x, CY, rot, z
def frame(T):
    i = min(N - 1, int(T / SL)); t = T - i * SL; s = C['slides'][i]
    bg = BGS[i] if (i == 0 or t >= TR) else Image.blend(BGS[i - 1], BGS[i], ease(t / TR))
    img = bg.convert('RGBA'); snow(img, T)
    if i > 0 and t < TR:   # l'ancienne carte part à gauche
        q = eio(t / TR); put(img, CARDS[i - 1], W / 2 - 1200 * q, CY - 80 * q, 1.0, 16 * q)
    x, y, rot, z = card_pos(i, t); put(img, CARDS[i], x, y, z, rot); snow(img, T, 22, True)   # neige devant la photo, mais derrière tous les textes
    if t > TR * 0.8:
        if s.get('comment'): comment(img, t - TR * 0.8)
        else: label(img, s['label'], 90 + (x - W / 2), 1390, t - TR * 0.8)
        tag(img, W - 230 + (x - W / 2), 300, T, t - TR * 0.8)
    header(img, T, i, t); plate(img, T)   # la plaque est dessinée en dernier : ni neige ni reflet sur le code
    return img.convert('RGB')
if __name__ == '__main__':
    if os.environ.get('PREVIEW'):
        for ts in os.environ['PREVIEW'].split(','): frame(float(ts)).save(f'{OUT}_{ts}.jpg', quality=88)
        sys.exit(0)
    NF = int(DUR * FPS); tmp = OUT + '_fr'; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    for n in range(NF): frame(n / FPS).save(f'{tmp}/f{n:05d}.jpg', quality=93)
    SR = 44100; mus = os.path.join(tmp, 'm.wav')
    subprocess.run([sys.executable, '/home/user/skillora./temu/tools/popbeat.py', str(DUR), mus, str(C.get('music_seed', 1)), str(C.get('bpm', 110)), str(C.get('key', 57))], check=True, capture_output=True)
    wm = wave.open(mus); m = np.frombuffer(wm.readframes(wm.getnframes()), '<i2').astype(float) / 32768
    if wm.getnchannels() == 2: m = m.reshape(-1, 2).mean(1)
    m = np.pad(m, (0, max(0, int(DUR * SR) - len(m))))[:int(DUR * SR)] * 0.55
    def sfx(name, t0, g):
        ws = wave.open(SFX + name + '.wav'); s = np.frombuffer(ws.readframes(ws.getnframes()), '<i2').astype(float) / 32768
        if ws.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
        if ws.getframerate() != SR: s = np.interp(np.arange(0, len(s), ws.getframerate() / SR), np.arange(len(s)), s)
        a0 = int(max(0, t0) * SR); L = min(len(s), len(m) - a0)
        if L > 0: m[a0:a0 + L] += s[:L] * g
    for k in range(N):
        sfx('swish', k * SL, 0.4); sfx('pop', k * SL + TR * 0.8 + 0.1, 0.18); sfx('tap', k * SL + TR * 0.8 + 0.45, 0.1); sfx('ding', k * SL + 1.6, 0.08)
    fd = int(0.6 * SR); m[-fd:] *= np.linspace(1, 0, fd); m = m / max(1e-6, np.abs(m).max()) * 0.9
    wo = wave.open(os.path.join(tmp, 'a.wav'), 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((m * 32767).astype('<i2').tobytes()); wo.close()
    subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/f%05d.jpg', '-i', os.path.join(tmp, 'a.wav'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
    shutil.rmtree(tmp); print('ok', OUT, DUR)
