# Style « scrapbook » (4e style Temu, pour le compte alu426339) : fond papier quadrillé, chaque photo arrive en polaroid
# qui tombe et se pose de travers (scotch washi en haut), légende écrite à la main sous la photo, pastille « $0 GIFT »
# collée comme un autocollant, l'ancien polaroid part en glissant. En bas : un ticket de caisse avec le CODE en entier.
# Dernière slide : un post-it avec la phrase officielle écrite à la main.  usage : posterv4.py config.json out.mp4  [PREVIEW=t1,t2]
import json, sys, os, math, subprocess, shutil, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
C = json.load(open(sys.argv[1])); OUT = sys.argv[2]; D = os.path.dirname(os.path.abspath(sys.argv[1]))
W, H, FPS = 1080, 1920, 30; SL = C['slide_dur']; TR = 0.55
FD = '/home/user/skillora./temu/fonts/'; SFX = '/home/user/skillora./motion/sfx/'
P = C['palette']; PAPER, INK, ACC, TAPE = [tuple(P[k]) for k in ('paper', 'ink', 'acc', 'tape')]
HAND = C.get('hand', 'PermanentMarker.ttf'); CF = 'Poppins-ExtraBold.ttf'; MONO = 'RubikMono.ttf'
CODE = C['code']; TXT = C['code_text']
DISC = C.get('disclaimer', '*T&Cs apply. The purchase required is determined by the gift(s)\' value.')
LOGO = Image.open('/home/user/skillora./temu/temu_logo.png').convert('RGBA')
_fc = {}
def F(name, sz):
    k = (name, int(sz))
    if k not in _fc: _fc[k] = ImageFont.truetype(FD + name, max(8, int(sz)))
    return _fc[k]
def fit(txt, name, sz, maxw):
    f = F(name, sz)
    while f.getbbox(txt)[2] > maxw and sz > 18: sz -= 3; f = F(name, sz)
    return f
def clamp(u): return max(0.0, min(1.0, u))
def ease(u): u = clamp(u); return 1 - (1 - u) ** 3
def back(u): u = clamp(u); c = 1.6; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2
def bounce(u):
    u = clamp(u)
    if u < 0.6: return (u / 0.6) ** 2
    v = (u - 0.6) / 0.4; return 1 - 0.06 * math.sin(v * math.pi) * (1 - v)
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
def with_shadow(lay, off=(10, 16), blur=14, op=0.45):
    pad = 40; o = Image.new('RGBA', (lay.width + 2 * pad, lay.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new('RGBA', lay.size, (0, 0, 0, 0)); sh.putalpha(lay.getchannel('A').point(lambda v: int(v * op)))
    o.alpha_composite(sh, (pad + off[0], pad + off[1])); o = o.filter(ImageFilter.GaussianBlur(blur)); o.alpha_composite(lay, (pad, pad)); return o
# ---- fond : papier quadrillé avec grain (calculé une fois)
def make_bg():
    rs = np.random.RandomState(3); a = np.ones((H, W, 3)) * np.array(PAPER, float)
    a += rs.normal(0, 5, (H, W, 1)); g = Image.fromarray(a.clip(0, 255).astype('uint8')).convert('RGBA'); d = ImageDraw.Draw(g)
    gc = tuple(int(c * 0.9) for c in PAPER) + (255,)
    for x in range(0, W, 54): d.line([(x, 0), (x, H)], fill=gc, width=2)
    for y in range(0, H, 54): d.line([(0, y), (W, y)], fill=gc, width=2)
    return g
BG = make_bg()
# ---- polaroid (photo recadrée en 4:5 + marge blanche épaisse en bas) et légende manuscrite
PW, PH_, M, MB = 800, 1000, 32, 150
def polaroid(im, fy):
    s = max(PW / im.width, PH_ / im.height); im = im.resize((int(im.width * s + 0.5), int(im.height * s + 0.5)), Image.LANCZOS)
    y0 = int((im.height - PH_) * fy); x0 = (im.width - PW) // 2; ph = im.crop((x0, y0, x0 + PW, y0 + PH_))
    lay = Image.new('RGBA', (PW + 2 * M, PH_ + M + MB), (250, 248, 242, 255)); lay.paste(ph, (M, M))
    return lay
def caption_layer(base, txt, n):
    lay = base.copy(); d = ImageDraw.Draw(lay); f = fit(txt, HAND, 62, PW - 20)
    d.text((lay.width / 2, PH_ + M + MB / 2 + 4), txt[:n], font=f, fill=INK, anchor='mm'); return lay
def tape(w=230, h=64, rot=0):
    t = Image.new('RGBA', (w, h), TAPE + (170,)); d = ImageDraw.Draw(t)
    for x in range(0, w, 18): d.line([(x, 0), (x - 10, h)], fill=(255, 255, 255, 50), width=6)
    for x in (0, w - 1):   # bords déchirés
        for y in range(0, h, 8): d.rectangle([x - 4, y, x + 4, y + 4], fill=(0, 0, 0, 0))
    return t.rotate(rot, expand=True, resample=Image.BICUBIC)
def sticker(txt1='$0', txt2='GIFT', r=118):
    lay = Image.new('RGBA', (2 * r + 30, 2 * r + 30), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); c = r + 15
    d.ellipse([c - r, c - r, c + r, c + r], fill=ACC + (255,), outline=(255, 255, 255), width=10)
    d.text((c, c - r * 0.16), txt1, font=fit(txt1, CF, int(r * 0.95), int(r * 1.5)), fill=(255, 255, 255), anchor='mm')
    d.text((c, c + r * 0.52), txt2, font=fit(txt2, CF, int(r * 0.34), int(r * 1.3)), fill=(255, 255, 255), anchor='mm')
    return with_shadow(lay, (4, 6), 6, 0.35)
# ---- ticket de caisse avec le code
def receipt():
    w, h = 900, 300; lay = Image.new('RGBA', (w, h + 24), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rectangle([0, 0, w, h], fill=(255, 255, 255, 255))
    for x in range(0, w + 24, 24): d.polygon([(x - 12, h), (x, h + 22), (x + 12, h)], fill=(255, 255, 255, 255))
    d.text((40, 46), 'TEMU', font=F(MONO, 30), fill=(40, 40, 40), anchor='lm'); lay.alpha_composite(LOGO.resize((58, 58), Image.LANCZOS), (w - 98, 18))
    for x in range(40, w - 40, 22): d.line([(x, 90), (x + 10, 90)], fill=(120, 120, 120), width=3)
    d.text((40, 128), 'SEARCH CODE', font=F(MONO, 28), fill=(40, 40, 40), anchor='lm')
    f = fit(CODE, CF, 112, w - 80); d.text((w / 2, 196), CODE, font=f, fill=INK, anchor='mm')
    d.text((w / 2, 266), 'GIFTS AT $0 IN TEMU APP', font=fit('GIFTS AT $0 IN TEMU APP', MONO, 30, w - 80), fill=(40, 40, 40), anchor='mm')
    return with_shadow(lay, (6, 10), 10, 0.35)
REC = receipt()
def postit(t):
    # post-it de la dernière slide : la phrase officielle écrite à la main, code en couleur
    w = 760; lay = Image.new('RGBA', (w, 560), (255, 230, 120, 255)); d = ImageDraw.Draw(lay)
    d.polygon([(w - 90, 560), (w, 470), (w, 560)], fill=(235, 200, 90, 255))
    lines = ['Search code', CODE, 'for Gifts at $0', 'in TEMU app']; n = int(max(0, t) * 30)
    for k, l in enumerate(lines):
        s = l[:max(0, n)] if k != 1 else (l if n > 0 else ''); n -= len(l)
        if k == 1 and s: d.text((w / 2, 110 + k * 112), s, font=fit(l, CF, 104, w - 80), fill=ACC, anchor='mm')
        elif s: d.text((w / 2, 110 + k * 112), s, font=fit(l, HAND, 72, w - 80), fill=INK, anchor='mm')
    return with_shadow(lay, (8, 12), 12, 0.4)
SLIDES = C['slides']; N = len(SLIDES); DUR = N * SL
POL = [polaroid(Image.open(os.path.join(D, s['img'])).convert('RGB'), s.get('fy', 0.4)) for s in SLIDES]
STK = sticker()
def pol_full(i, t):
    s = SLIDES[i]; n = int(max(0, t - 0.55) * 22); lay = caption_layer(POL[i], s['caption'], n)
    tp = tape(220, 60, -8 if i % 2 else 8); comp(lay, tp, (lay.width / 2 - tp.width / 2, -18))
    return with_shadow(lay)
ROT = [(-4 if i % 2 == 0 else 3.5) + (1.2 if i % 3 == 0 else -0.8) for i in range(N)]
PY = 300 + (PH_ + M + MB) / 2
def draw_pol(img, i, t, leaving=0.0):
    lay = pol_full(i, t)
    if leaving > 0:
        e = ease(leaving); put(img, lay, W / 2 + 1300 * e, PY + 120 * e, 0.9, ROT[i] - 25 * e); return
    u = bounce(t / 0.5); y = -900 * (1 - u) + PY * u; r = ROT[i] + 14 * (1 - u)
    put(img, lay, W / 2, y, 0.9, r)
    s = SLIDES[i]; k = back((t - 0.75) / 0.3)
    if k > 0: put(img, STK, s.get('stk_x', 820), s.get('stk_y', 380), k, -12 + 4 * math.sin(t * 2.5))
def header(img, t, i):
    d = ImageDraw.Draw(img); txt = C['header']; f = fit(txt, HAND, 70, W - 260)
    lay = Image.new('RGBA', (f.getbbox(txt)[2] + 80, 120), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
    ld.rounded_rectangle([0, 0, lay.width - 1, 119], 18, fill=INK + (255,)); ld.text((lay.width / 2, 62), txt, font=f, fill=(255, 255, 255), anchor='mm')
    put(img, lay, W / 2, 200, 1, -2)
    # petits points de progression façon carnet
    for j in range(N):
        x = W / 2 - (N - 1) * 22 + j * 44; c = ACC if j <= i else tuple(int(v * 0.7) for v in PAPER)
        d.ellipse([x - 10, 278 - 10, x + 10, 278 + 10], fill=c)
def frame(T):
    i = min(N - 1, int(T / SL)); t = T - i * SL; img = BG.copy(); header(img, t, i)
    if i > 0 and t < TR: draw_pol(img, i - 1, SL + t, leaving=t / TR)
    last = SLIDES[i].get('postit')
    if last:
        k = back(t / 0.45); put(img, postit(t - 0.4), W / 2, 860, k, 3)
        put(img, LOGO.resize((150, 150), Image.LANCZOS), W / 2 + 330, 560, back((t - 0.3) / 0.3), 10)
    else:
        draw_pol(img, i, t)
    u = ease(T / 0.5); put(img, REC, W / 2, 1640 + 400 * (1 - u), 1, 1.5)
    d = ImageDraw.Draw(img); d.text((W / 2, 1875), DISC, font=fit(DISC, 'Nunito.ttf', 26, W - 100), fill=(90, 90, 90), anchor='mm')
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
    m = np.pad(m, (0, max(0, int(DUR * SR) - len(m))))[:int(DUR * SR)] * 0.5
    def sfx(name, t0, g):
        ws = wave.open(SFX + name + '.wav'); s = np.frombuffer(ws.readframes(ws.getnframes()), '<i2').astype(float) / 32768
        if ws.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
        if ws.getframerate() != SR: s = np.interp(np.arange(0, len(s), ws.getframerate() / SR), np.arange(len(s)), s)
        a0 = int(max(0, t0) * SR); L = min(len(s), len(m) - a0)
        if L > 0: m[a0:a0 + L] += s[:L] * g
    for k in range(N):
        if k: sfx('swish', k * SL, 0.35)
        sfx('thud', k * SL + 0.32, 0.3); sfx('snap', k * SL + 0.78, 0.2)
    fd = int(0.6 * SR); m[-fd:] *= np.linspace(1, 0, fd); m = m / max(1e-6, np.abs(m).max()) * 0.9
    wo = wave.open(os.path.join(tmp, 'a.wav'), 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((m * 32767).astype('<i2').tobytes()); wo.close()
    subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/f%05d.jpg', '-i', os.path.join(tmp, 'a.wav'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
    shutil.rmtree(tmp); print('ok', OUT, DUR)
