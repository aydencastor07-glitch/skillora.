# Vidéo « affiches » (style carousel coupon) : chaque photo devient une affiche (gros titre, pastille coupon, CODE, phrase officielle),
# mises en page A/B/C/D qui changent d'une photo à l'autre, puis diaporama avec transitions.
# usage : posterv.py config.json out.mp4
import json, sys, os, math, subprocess, shutil, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
C = json.load(open(sys.argv[1])); OUT = sys.argv[2]; D = os.path.dirname(os.path.abspath(sys.argv[1]))
W, H, FPS = 1080, 1920, 30; SL = C['slide_dur']; TR = 0.45
FD = '/home/user/skillora./temu/fonts/'; SFX = '/home/user/skillora./motion/sfx/'
P = C['palette']; C1, C2, DK, ACC = [tuple(P[k]) for k in ('c1', 'c2', 'dark', 'acc')]; HF = C['font']; CF = C.get('code_font', HF)  # CF : police avec minuscules pour le code exact
def F(name, sz): return ImageFont.truetype(FD + name, sz)
CODE = C['code']; TXT = C['code_text']; i0 = TXT.index(CODE); PRE, POST = TXT[:i0].strip(), TXT[i0 + len(CODE):].strip()
AMOUNT = C.get('amount', '100€'); LOGO = Image.open('/home/user/skillora./temu/temu_logo.png').convert('RGBA')
def comp(img, lay, xy):
    # colle un calque même s'il dépasse du bord de l'image
    x, y = int(xy[0]), int(xy[1]); cx0, cy0 = max(0, -x), max(0, -y)
    if cx0 >= lay.width or cy0 >= lay.height: return
    img.alpha_composite(lay.crop((cx0, cy0, lay.width, lay.height)), (x + cx0, y + cy0))
def logo(img, x, y, s): comp(img, LOGO.resize((s, s), Image.LANCZOS), (int(x - s / 2), int(y - s / 2)))
def shadow(img, fn):
    # dessine via fn(draw) sur un calque, ajoute une ombre douce dessous
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); fn(ImageDraw.Draw(lay))
    sh = Image.new('RGBA', img.size, (0, 0, 0, 0)); sh.putalpha(lay.getchannel('A').point(lambda v: v * 0.6)); sh = sh.filter(ImageFilter.GaussianBlur(8))
    img.alpha_composite(sh, (4, 6)); img.alpha_composite(lay)
def fit(txt, name, sz, maxw):
    f = F(name, sz)
    while f.getbbox(txt)[2] > maxw and sz > 20: sz -= 4; f = F(name, sz)
    return f
def sentence(d, cx, y, f, col, ccol, lh):
    l1 = PRE + ' ' + CODE + ' ' + POST.split(' ')[0]; rest = ' '.join(POST.split(' ')[1:])
    x = cx - f.getbbox(l1)[2] / 2; d.text((x, y), PRE + ' ', font=f, fill=col, anchor='lm'); x += f.getbbox(PRE + ' ')[2]
    d.text((x, y), CODE, font=f, fill=ccol, anchor='lm'); x += f.getbbox(CODE + ' ')[2]; d.text((x, y), POST.split(' ')[0], font=f, fill=col, anchor='lm')
    d.text((cx, y + lh), rest, font=f, fill=col, anchor='mm')
def disclaimer(img, y=1868):
    f = F('Nunito.ttf', 26); d = ImageDraw.Draw(img); d.text((W / 2, y), C['disclaimer'], font=f, fill=(255, 255, 255), anchor='mm', stroke_width=3, stroke_fill=(0, 0, 0))
def badge(img, cx, cy, r, rot=0):
    lay = Image.new('RGBA', (2 * r + 20, 2 * r + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); c = r + 10
    d.ellipse([c - r, c - r, c + r, c + r], fill=ACC + (255,), outline=(255, 255, 255), width=8)
    d.text((c, c - r * 0.3), AMOUNT, font=fit(AMOUNT, HF, int(r * 0.75), int(r * 1.6)), fill=(255, 255, 255), anchor='mm')
    d.text((c, c + r * 0.22), 'Coupon', font=F(HF, int(r * 0.36)), fill=(255, 255, 255), anchor='mm'); d.text((c, c + r * 0.55), 'Bundle', font=F(HF, int(r * 0.36)), fill=(255, 255, 255), anchor='mm')
    lay = lay.rotate(rot, expand=True, resample=Image.BICUBIC); comp(img, lay, (int(cx - lay.width / 2), int(cy - lay.height / 2)))
def burst(img, cx, cy, r, rot=0):
    lay = Image.new('RGBA', (2 * r + 40, 2 * r + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); c = r + 20
    pts = [(c + (r if j % 2 == 0 else r * 0.82) * math.cos(j * math.pi / 14), c + (r if j % 2 == 0 else r * 0.82) * math.sin(j * math.pi / 14)) for j in range(28)]
    d.polygon(pts, fill=C2 + (255,)); d.text((c, c - r * 0.25), AMOUNT, font=fit(AMOUNT, HF, int(r * 0.6), int(r * 1.3)), fill=DK, anchor='mm')
    d.text((c, c + r * 0.3), 'Coupon Bundle', font=fit('Coupon Bundle', HF, int(r * 0.26), int(r * 1.3)), fill=DK, anchor='mm')
    lay = lay.rotate(rot, expand=True, resample=Image.BICUBIC); comp(img, lay, (int(cx - lay.width / 2), int(cy - lay.height / 2)))
def lines_of(t): return t.split('|')
# ---- les 4 mises en page
def layout_A(img, title, k):
    bx, by = C['slides'][k].get('badge_xy', (220, 1360))   # titre empilé aligné à droite, phrase en bandeau haut, pastille ronde + CODE en bas à gauche
    d = ImageDraw.Draw(img); f = F('Nunito.ttf', 52); d.rounded_rectangle([60, 120, W - 60, 300], 40, fill=DK + (190,))
    sentence(d, W / 2, 175, F(CF, 60), (255, 255, 255), C2, 72)
    ls = lines_of(title); sz = 128
    def tt(dd):
        for j, l in enumerate(ls): dd.text((W - 70, 380 + j * sz * 1.02), l, font=fit(l, HF, sz, W - 380), fill=C1 if j % 2 == 0 else C2, anchor='ra')
    shadow(img, tt); badge(img, bx, by, 165, -6)
    shadow(img, lambda dd: dd.text((70, 1610), 'CODE: ' + CODE, font=fit('CODE: ' + CODE, CF, 118, W - 330), fill=C1, anchor='lm'))
    logo(img, W - 150, 1600, 180); disclaimer(img)
def layout_B(img, title, k):   # blocs penchés foncés en haut à droite, CODE en bloc couleur haut gauche, bannière coupon en bas
    d = ImageDraw.Draw(img)
    d.rectangle([0, 150, 520, 400], fill=C2 + (255,)); d.text((50, 215), 'CODE:', font=F(HF, 80), fill=DK, anchor='lm'); d.text((50, 325), CODE, font=fit(CODE, CF, 100, 440), fill=DK, anchor='lm')
    ls = lines_of(title); y = 470
    for j, l in enumerate(ls):
        f = fit(l, HF, 120, 760); tw = f.getbbox(l)[2]; blk = Image.new('RGBA', (tw + 70, 160), (0, 0, 0, 0)); bd = ImageDraw.Draw(blk)
        bd.rectangle([0, 0, tw + 69, 159], fill=DK + (235,)); bd.text((35, 80), l, font=f, fill=C1 if j % 2 == 0 else C2, anchor='lm')
        blk = blk.rotate(9, expand=True, resample=Image.BICUBIC); comp(img, blk, (W - blk.width - 40 - j * 25, y)); y += 150
    logo(img, 160, 1040, 180)
    d = ImageDraw.Draw(img); d.rounded_rectangle([90, 1340, W - 90, 1520], 20, fill=DK + (235,), outline=C2, width=5)
    sentence(d, W / 2, 1395, fit(PRE + ' ' + CODE + ' for', CF, 66, W - 260), (255, 255, 255), C2, 75)
    d.rounded_rectangle([90, 1560, W - 90, 1720], 18, fill=(255, 255, 255)); d.rectangle([380, 1560, W - 90, 1720], fill=C2)
    d.text((235, 1640), AMOUNT, font=fit(AMOUNT, HF, 130, 270), fill=C2, anchor='mm'); d.text((380 + (W - 470) / 2, 1640), 'Coupon Bundle', font=fit('Coupon Bundle', HF, 110, W - 520), fill=(255, 255, 255), anchor='mm')
    disclaimer(img)
def layout_C(img, title, k):   # titre centré en haut avec contour, ticket coupon penché à droite, pilule CODE en bas + phrase
    ls = lines_of(title)
    def tt(dd):
        for j, l in enumerate(ls): dd.text((W / 2, 170 + j * 132), l, font=fit(l, HF, 136, W - 140), fill=C1 if j % 2 == 0 else C2, anchor='ma', stroke_width=6, stroke_fill=DK)
    shadow(img, tt); logo(img, 110, 90, 120)
    tk = Image.new('RGBA', (520, 280), (0, 0, 0, 0)); td = ImageDraw.Draw(tk); td.rounded_rectangle([0, 0, 519, 279], 24, fill=ACC + (255,))
    for yy in (60, 140, 220): td.ellipse([-30, yy - 30, 30, yy + 30], fill=(0, 0, 0, 0)); td.ellipse([490, yy - 30, 550, yy + 30], fill=(0, 0, 0, 0))
    td.rectangle([40, 20, 479, 259], outline=(255, 255, 255), width=4); td.text((260, 110), AMOUNT, font=fit(AMOUNT, HF, 130, 400), fill=(255, 255, 255), anchor='mm')
    td.text((260, 215), 'COUPON BUNDLE', font=fit('COUPON BUNDLE', HF, 56, 400), fill=(255, 255, 255), anchor='mm')
    tk = tk.rotate(-8, expand=True, resample=Image.BICUBIC); comp(img, tk, (W - tk.width - 30, C['slides'][k].get('tk_y', 1080)))
    d = ImageDraw.Draw(img); f = fit('CODE: ' + CODE, CF, 104, 760); tw = f.getbbox('CODE: ' + CODE)[2]
    d.rounded_rectangle([W / 2 - tw / 2 - 50, 1470, W / 2 + tw / 2 + 50, 1610], 70, fill=C2); d.text((W / 2, 1540), 'CODE: ' + CODE, font=f, fill=DK, anchor='mm')
    shadow(img, lambda dd: sentence(dd, W / 2, 1680, F(CF, 56), (255, 255, 255), C1, 66)); disclaimer(img)
def layout_D(img, title, k):   # dégradé sombre en bas, titre aligné à gauche, étoile coupon en haut à droite, CODE souligné
    g = Image.new('RGBA', (W, 900), (0, 0, 0, 0)); a = np.linspace(0, 215, 900).astype('uint8'); g.putalpha(Image.fromarray(np.repeat(a[:, None], W, 1)))
    dk = Image.new('RGBA', (W, 900), DK + (255,)); dk.putalpha(g.getchannel('A')); img.alpha_composite(dk, (0, H - 900))
    d = ImageDraw.Draw(img); d.rectangle([0, 90, W, 230], fill=DK + (200,)); sentence(d, W / 2, 132, F(CF, 52), (255, 255, 255), C2, 60)
    burst(img, W - 220, 470, 190, 8)
    ls = lines_of(title); y0 = 1480 - len(ls) * 120
    shadow(img, lambda dd: [dd.text((70, y0 + j * 120), l, font=fit(l, HF, 124, W - 140), fill=C1 if j % 2 == 0 else C2, anchor='la') for j, l in enumerate(ls)])
    d = ImageDraw.Draw(img); f = fit('CODE: ' + CODE, CF, 100, 700); d.text((70, 1620), 'CODE: ' + CODE, font=f, fill=(255, 255, 255), anchor='lm')
    d.rectangle([70, 1690, 70 + f.getbbox('CODE: ' + CODE)[2], 1702], fill=C2); logo(img, W - 140, 1630, 150); disclaimer(img)
LAY = {'A': layout_A, 'B': layout_B, 'C': layout_C, 'D': layout_D}
# ---- affiches fixes
slides = []
for k, s in enumerate(C['slides']):
    im = Image.open(os.path.join(D, s['img'])).convert('RGB').resize((W, H), Image.LANCZOS).convert('RGBA')
    LAY[s['layout']](im, s['title'], k); im = im.convert('RGB'); slides.append(im)
    if C.get('save_slides'): im.save(os.path.join(D, C['save_slides'] + f'_{k + 1}.jpg'), quality=92)
N = len(slides); DUR = N * SL
def frame(i, t):   # léger zoom (avant/arrière en alternance) sur l'affiche
    q = min(1, t / SL); z = 1 + 0.045 * (q if i % 2 == 0 else 1 - q) + 0.002; cw, ch = W / z, H / z
    return slides[i].resize((W, H), Image.BILINEAR, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2))
def ease(u): u = max(0, min(1, u)); return 1 - (1 - u) ** 3
TP = C['transition']
def trans(a, b, u, T):
    e = ease(u)
    if TP == 'push':
        o = Image.new('RGB', (W, H)); o.paste(a, (int(-W * e), 0)); o.paste(b, (int(W * (1 - e)), 0)); return o
    if TP == 'pushdown':
        o = Image.new('RGB', (W, H)); o.paste(a, (0, int(H * e))); o.paste(b, (0, int(-H * (1 - e)))); return o
    if TP == 'glitch':
        src = a if u < 0.45 else b; k = 1 - abs(u - 0.45) / 0.55; arr = np.asarray(src).copy(); o = int(36 * k)
        arr[..., 0] = np.roll(arr[..., 0], o, 1); arr[..., 2] = np.roll(arr[..., 2], -o, 1); rs = np.random.RandomState(int(T * 60))
        for _ in range(7):
            y = rs.randint(0, H - 100); h = rs.randint(15, 90); arr[y:y + h] = np.roll(arr[y:y + h], int(rs.randint(-110, 110) * k), 1)
        return Image.fromarray(arr)
    if TP == 'flashzoom':
        z = 1 + 0.25 * (1 - e); cw, ch = W / z, H / z; bb = b.resize((W, H), Image.BILINEAR, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2))
        return Image.blend(bb, Image.new('RGB', (W, H), (255, 255, 255)), max(0, 1 - u * 2.2) * 0.85)
    if TP == 'iris':
        m = Image.new('L', (W, H), 0); R = e * 1150; ImageDraw.Draw(m).ellipse([W / 2 - R, H / 2 - R, W / 2 + R, H / 2 + R], fill=255); o = a.copy(); o.paste(b, (0, 0), m.filter(ImageFilter.GaussianBlur(10))); return o
    if TP == 'blinds':   # volets verticaux qui se retournent
        o = a.copy(); n = 8; sw = W // n
        for j in range(n):
            uj = ease((u - j * 0.05) / 0.6); w = int(sw * uj)
            if w > 0: o.paste(b.crop((j * sw, 0, j * sw + w, H)), (j * sw, 0))
        return o
NF = int(DUR * FPS); tmp = OUT + '_fr'; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
for n in range(NF):
    T = n / FPS; i = min(N - 1, int(T / SL)); t = T - i * SL; img = frame(i, t)
    if i > 0 and t < TR: img = trans(frame(i - 1, SL + t), img, t / TR, T)
    img.save(f'{tmp}/f{n:05d}.jpg', quality=93)
SR = 44100; mus = os.path.join(tmp, 'm.wav')
subprocess.run([sys.executable, '/home/user/skillora./temu/tools/popbeat.py', str(DUR), mus, str(C.get('music_seed', 1)), str(C.get('bpm', 110)), str(C.get('key', 57))], check=True, capture_output=True)
wm = wave.open(mus); m = np.frombuffer(wm.readframes(wm.getnframes()), '<i2').astype(float) / 32768; m = np.pad(m, (0, max(0, int(DUR * SR) - len(m))))[:int(DUR * SR)] * 0.55
ws = wave.open(SFX + C.get('sfx', 'whoosh') + '.wav'); s = np.frombuffer(ws.readframes(ws.getnframes()), '<i2').astype(float) / 32768
if ws.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
if ws.getframerate() != SR: s = np.interp(np.arange(0, len(s), ws.getframerate() / SR), np.arange(len(s)), s)
for k in range(1, N):
    a0 = int((k * SL - 0.05) * SR); L = min(len(s), len(m) - a0); m[a0:a0 + L] += s[:L] * 0.45
fd = int(0.6 * SR); m[-fd:] *= np.linspace(1, 0, fd); m = m / max(1e-6, np.abs(m).max()) * 0.9
wo = wave.open(os.path.join(tmp, 'a.wav'), 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((m * 32767).astype('<i2').tobytes()); wo.close()
subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/f%05d.jpg', '-i', os.path.join(tmp, 'a.wav'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
shutil.rmtree(tmp); print('ok', OUT, DUR)
