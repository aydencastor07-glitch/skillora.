# Style « photo plein écran + code bien visible » (5e style Temu, compte alu426339) :
# la photo occupe tout l'écran, nette (agrandie en LANCZOS + accentuation), dès la 1re image (jamais d'écran vide en miniature).
# En haut : légende façon texte TikTok (blanc contour noir). Au milieu-bas : grand bandeau blanc « CODE alu426339 » + « $0 GIFTS IN THE TEMU APP ».
# Pastille $0 qui rebondit. Transition : coupe nette avec petit zoom (pas de fondu flou). Dernière image : grande carte code au centre.
# usage : posterv5.py config.json out.mp4  [PREVIEW=t1,t2]
import json, sys, os, math, subprocess, shutil, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
C = json.load(open(sys.argv[1])); OUT = sys.argv[2]; D = os.path.dirname(os.path.abspath(sys.argv[1]))
W, H, FPS = 1080, 1920, 30; SL = C['slide_dur']
FD = '/home/user/skillora./temu/fonts/'; SFX = '/home/user/skillora./motion/sfx/'
ACC = tuple(C.get('acc', [251, 119, 1])); BAR = tuple(C.get('bar', [255, 255, 255])); INK = tuple(C.get('ink', [20, 20, 20]))
CF = 'Poppins-ExtraBold.ttf'; TF = C.get('font', 'Poppins-ExtraBold.ttf')
CODE = C['code']; DISC = C.get('disclaimer', '*T&Cs apply. The purchase required is determined by the gift(s)\' value.')
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
def back(u): u = clamp(u); c = 1.7; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2
def put(img, lay, cx, cy, s=1.0, rot=0.0):
    if s <= 0.02: return
    if s != 1.0: lay = lay.resize((max(1, int(lay.width * s)), max(1, int(lay.height * s))), Image.BILINEAR)
    if rot: lay = lay.rotate(rot, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(lay, (int(cx - lay.width / 2), int(cy - lay.height / 2)))
def shadowed(lay, blur=12, op=0.45, off=(0, 10)):
    pad = 30; o = Image.new('RGBA', (lay.width + 2 * pad, lay.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new('RGBA', lay.size, (0, 0, 0, 0)); sh.putalpha(lay.getchannel('A').point(lambda v: int(v * op)))
    o.alpha_composite(sh, (pad + off[0], pad + off[1])); o = o.filter(ImageFilter.GaussianBlur(blur)); o.alpha_composite(lay, (pad, pad)); return o
# ---- photos : recadrage plein écran, agrandissement net (un peu plus grand pour le zoom lent)
Z = 1.06
def prep(path, fy):
    im = Image.open(path).convert('RGB'); tw, th = int(W * Z), int(H * Z)
    s = max(tw / im.width, th / im.height); im = im.resize((int(im.width * s + 0.5), int(im.height * s + 0.5)), Image.LANCZOS)
    x0 = (im.width - tw) // 2; y0 = int((im.height - th) * fy); im = im.crop((x0, y0, x0 + tw, y0 + th))
    return im.filter(ImageFilter.UnsharpMask(radius=2, percent=90, threshold=2))
SLIDES = C['slides']; N = len(SLIDES); DUR = N * SL
PH = [prep(os.path.join(D, s['img']), s.get('fy', 0.5)) for s in SLIDES]
# ---- éléments
def code_bar():
    w, h = 960, 300; lay = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 34, fill=BAR + (255,), outline=ACC + (255,), width=8)
    lay.alpha_composite(LOGO.resize((120, 120), Image.LANCZOS), (34, 34))
    d.text((180, 58), 'SEARCH CODE', font=F(CF, 40), fill=INK, anchor='lm')
    d.text((180, 150), CODE, font=fit(CODE, CF, 112, w - 220), fill=ACC, anchor='lm')
    d.rounded_rectangle([34, 228, w - 34, 278], 25, fill=ACC + (255,))
    d.text((w / 2, 254), 'for Gifts at $0 in TEMU app', font=fit('for Gifts at $0 in TEMU app', CF, 38, w - 120), fill=(255, 255, 255), anchor='mm')
    return shadowed(lay)
BARL = code_bar()
def badge(r=105):
    lay = Image.new('RGBA', (2 * r + 20, 2 * r + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); c = r + 10
    pts = [(c + (r if j % 2 == 0 else r * 0.84) * math.cos(j * math.pi / 12), c + (r if j % 2 == 0 else r * 0.84) * math.sin(j * math.pi / 12)) for j in range(24)]
    d.polygon(pts, fill=ACC + (255,)); d.text((c, c - r * 0.16), '$0', font=F(CF, int(r * 0.85)), fill=(255, 255, 255), anchor='mm')
    d.text((c, c + r * 0.45), 'GIFTS', font=F(CF, int(r * 0.3)), fill=(255, 255, 255), anchor='mm')
    return shadowed(lay, 8, 0.4, (0, 6))
BADGE = badge()
def caption(img, txt, t):
    if not txt: return
    k = ease(t / 0.3); f = fit(txt, TF, 76, W - 140); d = ImageDraw.Draw(img)
    words = txt.split(' '); lines = []; cur = ''
    for w in words:
        if cur and f.getbbox(cur + ' ' + w)[2] > W - 140: lines.append(cur); cur = w
        else: cur = (cur + ' ' + w).strip()
    lines.append(cur); y0 = C.get('cap_y', 330) - 20 * (1 - k)
    a = int(255 * k)
    for j, l in enumerate(lines):
        d.text((W / 2, y0 + j * 92), l, font=f, fill=(255, 255, 255, a), anchor='mm', stroke_width=9, stroke_fill=(0, 0, 0, a))
def final_card(t):
    w, h = 900, 620; lay = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 44, fill=(255, 255, 255, 250), outline=ACC + (255,), width=10)
    lay.alpha_composite(LOGO.resize((150, 150), Image.LANCZOS), (w // 2 - 75, 36))
    d.text((w / 2, 250), 'Search code', font=F(CF, 64), fill=INK, anchor='mm')
    d.text((w / 2, 360), CODE, font=fit(CODE, CF, 150, w - 80), fill=ACC, anchor='mm')
    d.text((w / 2, 470), 'for Gifts at $0', font=F(CF, 64), fill=INK, anchor='mm'); d.text((w / 2, 548), 'in TEMU app', font=F(CF, 64), fill=INK, anchor='mm')
    return shadowed(lay, 16, 0.5)
FINAL = final_card(0)
def frame(T):
    i = min(N - 1, int(T / SL)); t = T - i * SL; s = SLIDES[i]
    z = Z - (Z - 1.0) * 0.8 * clamp(t / SL) if i % 2 == 0 else 1.0 + (Z - 1.0) * 0.8 * clamp(t / SL)
    if i > 0 and t < 0.18: z *= 1 + 0.06 * (1 - t / 0.18)   # petit « punch » à la coupe
    z = max(1.0, z); cw, ch = W * Z / z, H * Z / z; ox, oy = (W * Z - cw) / 2, (H * Z - ch) / 2
    img = PH[i].resize((W, H), Image.BICUBIC, box=(ox, oy, ox + cw, oy + ch)).convert('RGBA')
    if s.get('final'):
        dim = Image.new('RGBA', (W, H), (0, 0, 0, int(110 * ease(t / 0.3)))); img.alpha_composite(dim)
        put(img, FINAL, W / 2, H * 0.47, back(t / 0.4))
    else:
        caption(img, s.get('caption', ''), t)
        put(img, BADGE, s.get('bx', 860), s.get('by', 560), back((t - 0.25) / 0.35), -10 + 5 * math.sin(T * 3))
        put(img, BARL, W / 2, C.get('bar_y', 1560), 1.0 + 0.015 * math.sin(T * 5))
    d = ImageDraw.Draw(img); f = fit(DISC, 'Nunito.ttf', 26, W - 120)
    d.text((W / 2, 1735), DISC, font=f, fill=(255, 255, 255), anchor='mm', stroke_width=3, stroke_fill=(0, 0, 0))
    return img.convert('RGB')
if __name__ == '__main__':
    if os.environ.get('PREVIEW'):
        for ts in os.environ['PREVIEW'].split(','): frame(float(ts)).save(f'{OUT}_{ts}.jpg', quality=90)
        sys.exit(0)
    NF = int(DUR * FPS); tmp = OUT + '_fr'; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    for n in range(NF): frame(n / FPS).save(f'{tmp}/f{n:05d}.jpg', quality=95)
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
        if k: sfx('cut2', k * SL, 0.35)
        sfx('pop', k * SL + 0.3, 0.2)
    fd = int(0.6 * SR); m[-fd:] *= np.linspace(1, 0, fd); m = m / max(1e-6, np.abs(m).max()) * 0.9
    wo = wave.open(os.path.join(tmp, 'a.wav'), 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((m * 32767).astype('<i2').tobytes()); wo.close()
    subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/f%05d.jpg', '-i', os.path.join(tmp, 'a.wav'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
    shutil.rmtree(tmp); print('ok', OUT, DUR)
