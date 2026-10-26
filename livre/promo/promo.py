# Vidéo promo TikTok du livre « Das Gesetzbuch des Geistes » (1080×1920, 30 i/s, ~24 s, sans voix : texte + musique + effets).
# 1) accroche tapée  2) le livre tombe (coup de marteau)  3) 5 pages qui défilent  4) ce qu'il y a dedans  5) « Link in Bio ».
# usage : python3 promo.py sortie.mp4  [PREVIEW=t1,t2,...]
import os, sys, math, subprocess, shutil, wave
import numpy as np
from multiprocessing import Pool
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe(); D = os.path.dirname(os.path.abspath(__file__)); L = os.path.dirname(D)
W, H, FPS = 1080, 1920, 30; DUR = 24.0
GOLD = (201, 162, 90); GOLD2 = (168, 128, 58); IVORY = (243, 236, 224); MUTED = (185, 171, 147); DARK = (20, 17, 13)
_fc = {}
def F(name, s):
    k = (name, int(s))
    if k not in _fc: _fc[k] = ImageFont.truetype(os.path.join(L, 'fonts', name), max(6, int(s)))
    return _fc[k]
def CZ(s): return F('Cinzel-700.ttf', s)
def CZ5(s): return F('Cinzel-500.ttf', s)
def GA(s): return F('EBGaramond-400.ttf', s)
def GAI(s): return F('EBGaramond-400i.ttf', s)
def clamp(u): return max(0.0, min(1.0, u))
def ease(u): u = clamp(u); return 1 - (1 - u) ** 3
def eio(u): u = clamp(u); return u * u * (3 - 2 * u)
def back(u): u = clamp(u); c = 1.7; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2
BOOK = Image.open(os.path.join(L, 'livre_3d.png')).convert('RGBA')
PAGES = [Image.open(os.path.join(D, f'page_{n}.png')).convert('RGBA') for n in (6, 14, 16, 22, 28)]
LAWS = ['Handle nie aus Wut', 'Rede weniger, als du weißt', 'Sei niemals zu verfügbar', 'Finde dein Warum', 'Lebe, als könntest du morgen gehen']
yy, xx = np.mgrid[0:H, 0:W]
BG = np.clip(np.dstack([np.full((H, W), c, np.float32) for c in DARK]) + (np.exp(-(((xx - W / 2) / 700) ** 2 + ((yy - H * 0.45) / 900) ** 2)) * 30)[..., None] * np.array([1.0, 0.8, 0.5]), 0, 255).astype('uint8'); del yy, xx
BG = Image.fromarray(BG).convert('RGBA')
def put(img, lay, cx, cy, s=1.0, rot=0.0, a=1.0):
    if s <= 0.01 or a <= 0.01: return
    if s != 1.0: lay = lay.resize((max(1, int(lay.width * s)), max(1, int(lay.height * s))), Image.BILINEAR)
    if rot: lay = lay.rotate(rot, expand=True, resample=Image.BICUBIC)
    if a < 0.99: lay = lay.copy(); lay.putalpha(lay.getchannel('A').point(lambda v: int(v * a)))
    img.alpha_composite(lay, (int(cx - lay.width / 2), int(cy - lay.height / 2)))
def text(img, xy, s, f, col, a=1.0, scale=1.0, anchor='mm'):
    if a <= 0.01: return
    if scale != 1.0: f = ImageFont.truetype(f.path, max(6, int(f.size * scale)))
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); ImageDraw.Draw(lay).text(xy, s, font=f, fill=col + (int(255 * a),), anchor=anchor); img.alpha_composite(lay)
def rule(img, cx, y, w, p, a=1.0):
    if p <= 0: return
    d = ImageDraw.Draw(img); h = w / 2 * ease(p); c = GOLD2 + (int(255 * a),)
    d.line([(cx - h, y), (cx - 12, y)], fill=c, width=3); d.line([(cx + 12, y), (cx + h, y)], fill=c, width=3)
    d.polygon([(cx, y - 8), (cx + 8, y), (cx, y + 8), (cx - 8, y)], fill=GOLD + (int(255 * a),))
def dust(img, t, n=40):
    d = ImageDraw.Draw(img); rs = np.random.RandomState(4)
    for j in range(n):
        x0, sp, r, ph = rs.uniform(0, W), rs.uniform(15, 45), rs.uniform(1.5, 4), rs.uniform(0, 6.3)
        y = (rs.uniform(0, H) - sp * t) % H; x = x0 + 20 * math.sin(t * 0.7 + ph); k = 0.4 + 0.6 * abs(math.sin(t * 1.5 + ph))
        d.ellipse([x - r, y - r, x + r, y + r], fill=GOLD + (int(120 * k),))
def typed(s, t, t0, cps=24): return s[:max(0, int((t - t0) * cps))]
T_BOOK, T_PAGES, T_LIST, T_CTA = 3.4, 7.6, 15.0, 19.0
def frame(t):
    img = BG.copy(); dust(img, t)
    if t < T_BOOK:   # accroche
        a = 1 - clamp((t - (T_BOOK - 0.3)) / 0.3)
        l1, l2 = 'Was wäre, wenn du nur', '21 Regeln bräuchtest?'
        text(img, (W / 2, 860), typed(l1, t, 0.2), CZ5(62), IVORY, a)
        text(img, (W / 2, 960), typed(l2, t, 0.2 + len(l1) / 24), CZ(70), GOLD, a)
        rule(img, W / 2, 1060, 380, (t - 2.2) / 0.5, a)
    elif t < T_PAGES:   # le livre tombe, coup, titre
        u = t - T_BOOK; k = back(u / 0.45); y = 820 - 900 * (1 - ease(u / 0.35)); out = 1 - clamp((t - (T_PAGES - 0.3)) / 0.3)
        if u > 0.35:   # éclat doré derrière le livre au moment du coup
            q = clamp((u - 0.35) / 0.7); g = Image.new('RGBA', (W, H), (0, 0, 0, 0)); r = 380 + 260 * q
            ImageDraw.Draw(g).ellipse([W / 2 - r, 820 - r, W / 2 + r, 820 + r], fill=GOLD + (int(110 * (1 - q)),)); img.alpha_composite(g.filter(ImageFilter.GaussianBlur(90)))
        put(img, BOOK, W / 2, y, 0.62 * (0.92 + 0.08 * k) * (1 + 0.015 * math.sin(t * 2)), 2 * math.sin(t * 1.3), out)
        text(img, (W / 2, 1480), 'Das Gesetzbuch des Geistes', CZ(54), GOLD, clamp((u - 0.6) / 0.4) * out)
        text(img, (W / 2, 1560), '21 Gesetze, die dein Leben formen', GA(44), IVORY, clamp((u - 0.9) / 0.4) * out)
        text(img, (W / 2, 1650), '@magniizz', CZ5(36), MUTED, clamp((u - 1.2) / 0.4) * out)
    elif t < T_LIST:   # pages qui défilent
        seg = (T_LIST - T_PAGES) / len(PAGES); i = min(len(PAGES) - 1, int((t - T_PAGES) / seg)); u = (t - T_PAGES - i * seg) / seg
        text(img, (W / 2, 300), 'Jedes Gesetz auf einer Seite', CZ(46), GOLD, clamp((t - T_PAGES) / 0.4) * (1 - clamp((t - (T_LIST - 0.3)) / 0.3)))
        if i > 0 and u < 0.25:   # l'ancienne page part à gauche
            q = eio(u / 0.25); put(img, PAGES[i - 1], W / 2 - 1100 * q, 1000, 0.82, -12 * q, 1 - q)
        q = eio(u / 0.25); x = W / 2 + 1100 * (1 - q); z = 0.82 * (1 + 0.04 * u)
        put(img, PAGES[i], x, 1000, z, 10 * (1 - q) + 1.5 * math.sin(t * 2), 1 - clamp((t - (T_LIST - 0.3)) / 0.3))
        text(img, (W / 2, 1720), f'Gesetz Nr. {[1, 8, 10, 15, 21][i]} · {LAWS[i]}', GAI(44), IVORY, clamp((u - 0.15) / 0.2))
    elif t < T_CTA:   # ce que contient le livre
        u = t - T_LIST; out = 1 - clamp((t - (T_CTA - 0.3)) / 0.3)
        put(img, BOOK, W / 2, 620, 0.42, 2 * math.sin(t * 1.3), out * clamp(u / 0.3))
        rows = [('21', 'Gesetze der größten Denker'), ('1', 'Seite pro Gesetz'), ('3', 'Übungen zu jedem Gesetz'), ('21', 'Tage – ein Gesetz pro Tag')]
        for j, (n, s) in enumerate(rows):
            q = back((u - 0.3 - j * 0.45) / 0.35)
            if q <= 0.01: continue
            y = 1130 + j * 140; x0 = 170 + 300 * (1 - clamp(q))
            text(img, (x0 + 60, y), n, CZ(84), GOLD, out * clamp(q), anchor='mm'); text(img, (x0 + 150, y), s, GA(52), IVORY, out * clamp(q), anchor='lm')
    else:   # appel à l'action
        u = t - T_CTA
        put(img, BOOK, W / 2, 760, 0.6 * (0.9 + 0.1 * back(u / 0.5)) * (1 + 0.02 * math.sin(t * 2)), 2 * math.sin(t * 1.3), clamp(u / 0.3))
        k = back((u - 0.4) / 0.4); text(img, (W / 2, 1440), 'Link in Bio', CZ(92), GOLD, clamp((u - 0.4) / 0.3), scale=max(0.3, 1.3 - 0.3 * k))
        rule(img, W / 2, 1530, 420, (u - 0.7) / 0.5)
        text(img, (W / 2, 1610), 'gesetze.skillora.me', GA(54), IVORY, clamp((u - 0.9) / 0.4))
        text(img, (W / 2, 1690), 'Sofort-Download · 9,99 €', GAI(44), MUTED, clamp((u - 1.2) / 0.4))
        if u > 1.0:   # flèche qui pointe vers le haut (vers la bio)
            b = 18 * math.sin(u * 5); d = ImageDraw.Draw(img); x, y = W / 2, 1810 + b
            d.polygon([(x, y - 40), (x + 30, y), (x + 10, y), (x + 10, y + 30), (x - 10, y + 30), (x - 10, y), (x - 30, y)], fill=GOLD + (int(255 * clamp((u - 1.0) / 0.3)),))
    return img.convert('RGB')
def fb(n): return frame(n / FPS).tobytes()
if __name__ == '__main__':
    OUT = sys.argv[1]
    if os.environ.get('PREVIEW'):
        for ts in os.environ['PREVIEW'].split(','): frame(float(ts)).save(f'{OUT}_{ts}.jpg', quality=88)
        sys.exit(0)
    SR = 44100; N = int(DUR * SR); tmp = OUT + '_a.wav'
    mu = np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', os.path.join(L, '..', 'tiktok_de', 'v2_gesetz10', 'musique.mp3'), '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(float) / 32768
    mu = np.tile(mu, int(N / len(mu)) + 1)[:N]; mix = mu / max(1e-6, np.abs(mu).max()) * 0.55
    def sfx(path, t0, g):
        w = wave.open(path); s = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float) / 32768
        if w.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
        if w.getframerate() != SR: s = np.interp(np.arange(0, len(s), w.getframerate() / SR), np.arange(len(s)), s)
        i0 = int(t0 * SR); n = min(len(s), N - i0); mix[i0:i0 + n] += s[:n] * g
    SX = os.path.join(L, '..', 'motion', 'sfx')
    for k in range(40): sfx(os.path.join(SX, 'tap.wav'), 0.2 + k / 24, 0.035)          # frappe du texte
    sfx(os.path.join(SX, 'whoosh.wav'), T_BOOK - 0.1, 0.35); sfx(os.path.join(L, '..', 'tiktok_de', 'v14_gesetz7', 'gavel', 'coup.wav'), T_BOOK + 0.33, 0.9)
    for i in range(5): sfx(os.path.join(SX, 'swish.wav'), T_PAGES + i * (T_LIST - T_PAGES) / 5, 0.3)
    for j in range(4): sfx(os.path.join(SX, 'pop.wav'), T_LIST + 0.3 + j * 0.45, 0.2)
    sfx(os.path.join(SX, 'shine.wav'), T_CTA, 0.3); sfx(os.path.join(SX, 'ding.wav'), T_CTA + 0.45, 0.25)
    fi, fo = int(0.3 * SR), int(1.0 * SR); mix[:fi] *= np.linspace(0, 1, fi); mix[-fo:] *= np.linspace(1, 0, fo); mix = mix / np.abs(mix).max() * 0.95
    wo = wave.open(tmp, 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((mix * 32767).astype('<i2').tobytes()); wo.close()
    enc = subprocess.Popen([FF, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-i', tmp, '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-af', 'pan=stereo|c0=c0|c1=c0', '-shortest', '-movflags', '+faststart', OUT], stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for b in pool.imap(fb, range(int(DUR * FPS)), chunksize=4): enc.stdin.write(b)
    enc.stdin.close(); enc.wait(); os.remove(tmp); print('ok', OUT, DUR)
