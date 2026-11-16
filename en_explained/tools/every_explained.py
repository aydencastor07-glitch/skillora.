# Vidéo « Every ___ Explained » (compte anglais) – style de la référence @valor.humano3 :
# fond blanc, bonhomme bâton dessiné, illustrations fournies (prompts) qui apparaissent d'abord en esquisse grise puis se colorent,
# mots-clés en GROS (police condensée), relances « It gets stranger », beaucoup de motion design, sous-titres, musique. Export en vrai 4K, images envoyées à ffmpeg.
# usage : every_explained.py dossier sortie.mp4  [PREVIEW=t1,t2,...] [K=2 (4K) | K=1] [TAIL=0.4]
#   dossier : voix_clean.mp3, words.json (align_tts.py), img/1.png … (illustrations sur fond blanc), musique.mp3, scenes.py (l'épisode)
import sys, os, re, math, json, subprocess, shutil, wave
import numpy as np
from multiprocessing import Pool
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe(); DIR, OUT = sys.argv[1], sys.argv[2]
W, H, FPS, SS = 1080, 1920, 60, 2; K = int(os.environ.get('K', 2))
BG = (255, 255, 255); INK = (25, 25, 28); RED = (214, 40, 40); GREY = (150, 150, 150); YEL = (255, 210, 40)
BLUE = (40, 120, 230); GREEN = (40, 170, 80); WHITE = (255, 255, 255); BROWN = (110, 70, 40); SKY = (150, 210, 245)
FD = '/home/user/skillora./temu/fonts/'; SFXD = '/home/user/skillora./motion/sfx/'
_fc = {}
def F(n, s):
    k = (n, int(s))
    if k not in _fc: _fc[k] = ImageFont.truetype(FD + n, int(s))
    return _fc[k]
def AF(s): return F('Anton-Regular.ttf', S(s))                      # mots-clés condensés
def HF(s):                                                             # relances écrites à la main (gras)
    k = ('hand', int(s))
    if k not in _fc: f = ImageFont.truetype(FD + 'Caveat.ttf', S(s)); f.set_variation_by_axes([700]); _fc[k] = f
    return _fc[k]
def BF(s): return F('Poppins-ExtraBold.ttf', S(s))
# ---------- outils
def ease(u): u = max(0, min(1, u)); return 1 - (1 - u) ** 3
def eio(u): u = max(0, min(1, u)); return u * u * (3 - 2 * u)
def back(u): u = max(0, min(1, u)); c = 1.7; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2
def clamp(u): return max(0, min(1, u))
def S(v): return int(round(v * SS))
def since(t, t0, d=0.35): return clamp((t - t0) / d) if t0 is not None else 0
def arc(d, cx, cy, r, a0, a1, col, w):
    if a1 - a0 < 0.5 or r <= 0: return
    d.arc([S(cx - r), S(cy - r), S(cx + r), S(cy + r)], a0, a1, fill=col, width=max(1, S(w)))
def line(d, x0, y0, x1, y1, col, w, p=1.0):
    if p <= 0: return
    p = min(1, p); xe, ye = x0 + (x1 - x0) * p, y0 + (y1 - y0) * p
    d.line([S(x0), S(y0), S(xe), S(ye)], fill=col, width=S(w))
    r = S(w) / 2
    for x, y in ((x0, y0), (xe, ye)): d.ellipse([S(x) - r, S(y) - r, S(x) + r, S(y) + r], fill=col)
def poly(d, pts, col, w, p=1.0, closed=False):
    # polyligne qui se dessine progressivement (p de 0 à 1)
    if p <= 0 or len(pts) < 2: return
    if closed: pts = list(pts) + [pts[0]]
    L = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]; tot = sum(L) * min(1, p); acc = 0; out = [pts[0]]
    for (a, b), l in zip(zip(pts, pts[1:]), L):
        if acc + l >= tot: q = (tot - acc) / l if l else 0; out.append((a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q)); break
        out.append(b); acc += l
    d.line([(S(x), S(y)) for x, y in out], fill=col, width=S(w), joint='curve')
def rect(d, x0, y0, x1, y1, col, w, p=1.0, r=24, fill=None):
    if p >= 1 or fill:
        if p > 0: d.rounded_rectangle([S(x0), S(y0), S(x1), S(y1)], S(r), outline=col, width=S(w), fill=fill)
        return
    poly(d, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], col, w, p, closed=True)
def circ(d, cx, cy, r, col=None, fill=None, w=6):
    d.ellipse([S(cx - r), S(cy - r), S(cx + r), S(cy + r)], outline=col, width=S(w) if col else 0, fill=fill)
def comp(img, lay, x, y):
    x, y = int(x), int(y); cx0, cy0 = max(0, -x), max(0, -y)
    if cx0 >= lay.width or cy0 >= lay.height or x >= img.width or y >= img.height: return
    img.alpha_composite(lay.crop((cx0, cy0, min(lay.width, img.width - x), min(lay.height, img.height - y))), (x + cx0, y + cy0))
def text(img, xy, s, f, col, alpha=1.0, anchor='mm', rot=0, scale=1.0):
    # texte rendu dans une petite image (rapide), avec alpha, rotation et échelle
    if alpha <= 0.01 or scale <= 0.01: return
    if scale != 1.0: f = ImageFont.truetype(f.path, max(4, int(f.size * scale)))
    bb = f.getbbox(s, anchor=anchor); pad = 6; w, h = bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad
    t = Image.new('RGBA', (w, h), (0, 0, 0, 0)); ImageDraw.Draw(t).text((-bb[0] + pad, -bb[1] + pad), s, font=f, fill=tuple(col) + (int(255 * alpha),), anchor=anchor)
    if rot:
        t = t.rotate(rot, expand=True, resample=Image.BICUBIC); comp(img, t, S(xy[0]) - t.width / 2, S(xy[1]) - t.height / 2)
    else: comp(img, t, S(xy[0]) + bb[0] - pad, S(xy[1]) + bb[1] - pad)
def cross(d, cx, cy, r, p, col=RED, w=10):
    line(d, cx - r, cy - r, cx + r, cy + r, col, w, clamp(p * 2)); line(d, cx + r, cy - r, cx - r, cy + r, col, w, clamp(p * 2 - 1))
def check(d, cx, cy, r, p, col=GREEN, w=11):
    line(d, cx - r, cy, cx - r * 0.3, cy + r * 0.7, col, w, clamp(p * 2)); line(d, cx - r * 0.3, cy + r * 0.7, cx + r, cy - r * 0.8, col, w, clamp(p * 2 - 1))
def arrow(d, x0, y0, x1, y1, col, w=8, p=1.0, head=30):
    if p <= 0: return
    xe, ye = x0 + (x1 - x0) * min(1, p), y0 + (y1 - y0) * min(1, p); line(d, x0, y0, xe, ye, col, w)
    a = math.atan2(ye - y0, xe - x0)
    d.polygon([(S(xe + 6 * math.cos(a)), S(ye + 6 * math.sin(a))), (S(xe - head * math.cos(a - 0.45)), S(ye - head * math.sin(a - 0.45))), (S(xe - head * math.cos(a + 0.45)), S(ye - head * math.sin(a + 0.45)))], fill=col)
def underline(d, x0, x1, y, col, p, w=8):
    if p > 0: poly(d, [(x0, y), ((x0 + x1) / 2, y + 4), (x1, y - 2)], col, w, p)
# ---------- voix + mots
SR = 44100
VOICE = np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', os.path.join(DIR, 'voix_clean.mp3'), '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(float) / 32768
WORDS = json.load(open(os.path.join(DIR, 'words.json'))); DUR = len(VOICE) / SR + float(os.environ.get('TAIL', 0.4))
def cw(w): return re.sub(r"[^\w'-]", '', w).lower()
def tw(word, n=0, end=False):
    m = [x for x in WORDS if cw(x[0]) == word.lower()]
    return (m[n][2] if end else m[n][1]) if len(m) > n else None
# ---------- illustrations : fond blanc retiré, version « esquisse » (traits gris), apparition trait puis couleur
_ill = {}
def load_ill(n):
    p = os.path.join(DIR, 'img', f'{n}.png')
    if not os.path.exists(p): p = os.path.join(DIR, 'img', f'{n}.jpg')
    if not os.path.exists(p):    # image pas encore fournie : cadre provisoire
        im = Image.new('RGB', (800, 800), (255, 255, 255)); dd = ImageDraw.Draw(im); dd.rounded_rectangle([40, 40, 760, 760], 60, outline=(170, 170, 170), width=12)
        dd.text((400, 400), f'IMG {n}', font=ImageFont.truetype(FD + 'Anton-Regular.ttf', 160), fill=(170, 170, 170), anchor='mm')
    else: im = Image.open(p).convert('RGB')
    a = np.asarray(im).astype(np.float32); d = 255 - a.min(2); al = np.clip((d - 8) / 26, 0, 1)
    rgba = Image.fromarray(np.dstack([a, al * 255]).astype('uint8'), 'RGBA'); bb = rgba.getchannel('A').point(lambda v: 255 if v > 20 else 0).getbbox() or (0, 0, im.width, im.height)
    return rgba.crop(bb)
def ill(n, w, h):
    # version redimensionnée (cache) : couleur, esquisse, masque de dévoilement
    key = (n, int(w), int(h))
    if key not in _ill:
        src = load_ill(n); s = min(S(w) / src.width, S(h) / src.height); col = src.resize((max(1, int(src.width * s)), max(1, int(src.height * s))), Image.LANCZOS)
        if s > 1.2 and globals().get('SHARPEN'):     # image source petite et très agrandie : on raffermit les traits
            rgb = col.convert('RGB').filter(ImageFilter.UnsharpMask(radius=S(2), percent=SHARPEN, threshold=2)); rgb.putalpha(col.getchannel('A')); col = rgb
        g = col.convert('L'); e = g.filter(ImageFilter.FIND_EDGES).point(lambda v: 255 if v > 40 else 0).filter(ImageFilter.MaxFilter(3))
        e = ImageChops.multiply(e, col.getchannel('A').point(lambda v: 255 if v > 60 else 0))
        sk = Image.new('RGBA', col.size, (110, 110, 115, 0)); sk.putalpha(e)
        yy, xx = np.mgrid[0:col.height, 0:col.width]; rs = np.random.RandomState(n)
        grad = (xx / col.width * 0.55 + yy / col.height * 0.45 + rs.uniform(-0.04, 0.04, (col.height, col.width))).astype(np.float32)
        _ill[key] = (col, sk, grad)
    return _ill[key]
def show(img, n, cx, cy, w, h, t0, t, out=None, mode='pop', float_=10, wob=2.0):
    # illustration toujours en mouvement : entrée (pop = rotation « 3D » sur l'axe vertical + rebond, sketch = esquisse puis couleur),
    # puis flottement et léger balancement tant qu'elle est à l'écran ; out = sortie rapide (rétrécit)
    if t0 is None or t < t0: return
    col, sk, grad = ill(n, w, h); p = t - t0
    al = 1.0 if out is None else 1 - clamp((t - out + 0.15) / 0.15)
    if al <= 0: return
    if mode == 'sketch':
        x, y = S(cx) - col.width // 2, S(cy) - col.height // 2
        m = Image.fromarray((np.clip((p / 0.4 * 1.15 - grad) * 12, 0, 1) * 255 * al).astype('uint8'))
        if p < 0.7: s2 = sk.copy(); s2.putalpha(ImageChops.multiply(sk.getchannel('A'), m)); comp(img, s2, x, y)
        ca = clamp((p - 0.25) / 0.3) * al
        if ca > 0: c2 = col.copy(); c2.putalpha(col.getchannel('A').point(lambda v: int(v * ca))); comp(img, c2, x, y)
        return
    k = clamp(p / 0.38); sx = max(0.02, abs(math.cos((1 - ease(k)) * math.pi / 2))) * (back(k) if k < 1 else 1); sy = 0.85 + 0.15 * back(k)
    if out is not None: q = clamp((t - out + 0.15) / 0.15); sx *= 1 - 0.4 * q; sy *= 1 - 0.4 * q
    sw, sh_ = max(2, int(col.width * sx)), max(2, int(col.height * sy))
    im = col.resize((sw, sh_), Image.BILINEAR) if (sw, sh_) != col.size else col
    rot = wob * math.sin(t * 1.7 + n)
    if abs(rot) > 0.05: im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    if al < 0.99: im = im.copy(); im.putalpha(im.getchannel('A').point(lambda v: int(v * al)))
    fy = float_ * math.sin(t * 2.1 + n * 0.7) * k
    comp(img, im, S(cx) - im.width // 2, S(cy + fy) - im.height // 2)
# ---------- clips vidéo (image animée) : vid/<k>.mp4, joués plein écran, images extraites une fois (30 i/s, 1080x1920)
def clip_frames(k):
    src = os.path.join(DIR, 'vid', f'{k}.mp4'); dd = os.path.join(DIR, 'vid', f'{k}_fr')
    if not os.path.exists(src): return None, 0
    if not os.path.isdir(dd) or not os.listdir(dd):
        os.makedirs(dd, exist_ok=True)
        subprocess.run([FF, '-v', 'error', '-i', src, '-vf', f'fps=30,scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}', '-q:v', '1', os.path.join(dd, '%04d.jpg')])
    return dd, len(os.listdir(dd))
def clip(img, k, t0, t, speed=1.0, start=0.0, end=None, fade=0.12):
    # plein écran : image du clip à l'instant (t - t0) x vitesse ; la dernière image reste si le clip est fini
    if t0 is None or t < t0: return
    dd, n = clip_frames(k)
    if not n: return
    last = n - 1 if end is None else min(n - 1, int(end * 30)); fi = max(0, min(last, int((start + (t - t0) * speed) * 30)))
    im = Image.open(os.path.join(dd, f'{fi + 1:04d}.jpg')).convert('RGBA').resize((W * SS, H * SS), Image.LANCZOS)
    a = since(t, t0, fade)
    if a < 0.99: im.putalpha(int(255 * a))
    img.alpha_composite(im)
# ---------- bonhomme bâton
def stick(d, x, y, s=1.0, pose='stand', mouth='flat', p=1.0, t=0, eyes=INK, look=0):
    # (x, y) = pieds ; tête ronde, yeux, bouche ; poses : stand, think, point, up, shrug
    if p <= 0: return
    r = 62 * s; hy = y - 360 * s; w = 7 * s
    circ(d, x, hy, r * ease(p / 0.4), INK, WHITE + (255,), w)
    if p < 0.4: return
    ex = 20 * s; ey = hy - 8 * s - (14 * s if pose == 'up' else 0)
    for sx in (-1, 1):
        if eyes == INK: circ(d, x + sx * ex + look * 6 * s, ey, 7 * s, None, INK + (255,))
        else: circ(d, x + sx * ex + look * 6 * s, ey, 11 * s, INK, eyes + (255,), 3 * s); circ(d, x + sx * ex + look * 6 * s, ey, 4 * s, None, INK + (255,))
    my = hy + 26 * s
    if mouth == 'smile': arc(d, x, my - 10 * s, 18 * s, 20, 160, INK, w * 0.7)
    elif mouth == 'o': circ(d, x, my, 9 * s, INK, None, w * 0.6)
    elif mouth == 'sad': arc(d, x, my + 12 * s, 16 * s, 200, 340, INK, w * 0.7)
    else: line(d, x - 13 * s, my, x + 13 * s, my, INK, w * 0.7)
    k = clamp((p - 0.4) / 0.6); ny = hy + r; hip = y - 140 * s
    line(d, x, ny, x, ny + (hip - ny) * k, INK, w)
    if k < 1: return
    line(d, x, hip, x - 55 * s, y, INK, w); line(d, x, hip, x + 55 * s, y, INK, w)
    sh = ny + 50 * s
    if pose == 'think': line(d, x, sh, x - 70 * s, sh + 90 * s, INK, w); line(d, x, sh, x + 50 * s, sh + 60 * s, INK, w); line(d, x + 50 * s, sh + 60 * s, x + 25 * s, hy + 50 * s, INK, w)
    elif pose == 'point': line(d, x, sh, x - 70 * s, sh + 100 * s, INK, w); line(d, x, sh, x + 110 * s, sh - 70 * s, INK, w)
    elif pose == 'up': line(d, x, sh, x - 100 * s, sh - 90 * s, INK, w); line(d, x, sh, x + 100 * s, sh - 90 * s, INK, w)
    elif pose == 'shrug': line(d, x, sh, x - 80 * s, sh + 20 * s, INK, w); line(d, x - 80 * s, sh + 20 * s, x - 100 * s, sh - 40 * s, INK, w); line(d, x, sh, x + 80 * s, sh + 20 * s, INK, w); line(d, x + 80 * s, sh + 20 * s, x + 100 * s, sh - 40 * s, INK, w)
    else: line(d, x, sh, x - 70 * s, sh + 110 * s, INK, w); line(d, x, sh, x + 70 * s, sh + 110 * s, INK, w)
def word(img, xy, s, size, col=INK, t=0, t0=None, font='A', rot=0):
    # mot-clé qui « tape » à l'écran (petit rebond)
    if t0 is None or t < t0 - 0.02: return
    k = clamp((t - t0) / 0.18); f = AF(size) if font == 'A' else HF(size)
    text(img, xy, s, f, col, k, rot=rot, scale=1.25 - 0.25 * back(k))
def gone(t, t1, d=0.15): return 1 - since(t, t1 - d, d) if t1 else 1
def sub(img, alpha, fn):
    if alpha <= 0.01: return
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); fn(lay, ImageDraw.Draw(lay))
    if alpha < 0.99: lay.putalpha(lay.getchannel('A').point(lambda v: int(v * alpha)))
    img.alpha_composite(lay)
# ---------- éléments de motion design (tout bouge en permanence)
PASTEL = [(150, 200, 250), (250, 200, 140), (170, 230, 190), (220, 190, 245), (255, 220, 120)]
def confetti(d, t, n=26, seed=3):
    # petits points pastel qui dérivent lentement en fond
    rs = np.random.RandomState(seed)
    for k in range(n):
        x0, y0, vx, vy, r = rs.uniform(0, W), rs.uniform(300, 1750), rs.uniform(-18, 18), rs.uniform(-30, -10), rs.uniform(6, 14)
        x = (x0 + vx * t) % W; y = 300 + (y0 - 300 + vy * t) % 1450
        circ(d, x, y, r * (0.8 + 0.2 * math.sin(t * 3 + k)), None, PASTEL[k % 5] + (150,))
def eyeicon(d, x, y, r, col=BLUE, look=0.0, blink=0.0):
    # petit œil : blanc, iris coloré, pupille, reflet ; blink ferme la paupière
    circ(d, x, y, r, INK, WHITE + (255,), max(2, r * 0.12))
    if blink > 0.85: line(d, x - r * 0.8, y, x + r * 0.8, y, INK, max(2, r * 0.14)); return
    ix = x + r * 0.18 * math.sin(look); circ(d, ix, y, r * 0.55, None, col + (255,)); circ(d, ix, y, r * 0.25, None, INK + (255,)); circ(d, ix - r * 0.15, y - r * 0.18, r * 0.1, None, WHITE + (255,))
def sun(d, cx, cy, r, t, p=1.0):
    if p <= 0: return
    for k in range(12):
        a = k * math.pi / 6 + t * 0.8; L = (34 + 14 * math.sin(t * 6 + k)) * ease(p)
        line(d, cx + (r + 16) * math.cos(a), cy + (r + 16) * math.sin(a), cx + (r + 16 + L) * math.cos(a), cy + (r + 16 + L) * math.sin(a), (240, 170, 20), 8)
    circ(d, cx, cy, r * back(p) * (1 + 0.04 * math.sin(t * 5)), INK, YEL + (255,), 6)
def globe(d, cx, cy, r, t, p=1.0):
    # Terre qui tourne : les continents glissent et sont coupés au bord du disque
    if p <= 0: return
    rr = r * back(p); circ(d, cx, cy, rr, INK, (90, 170, 235, 255), 7)
    for k, (lon, lat, s) in enumerate(((0.0, -0.3, 0.32), (1.4, 0.15, 0.38), (2.6, 0.45, 0.24), (3.9, -0.1, 0.3), (5.0, 0.35, 0.22))):
        a = lon + t * 0.9; xx = math.sin(a)
        if math.cos(a) < 0: continue
        cx2 = cx + xx * rr * 0.75; sx = max(0.15, math.cos(a)); s2 = s * rr
        d.ellipse([S(cx2 - s2 * sx), S(cy + lat * rr - s2 * 0.8), S(cx2 + s2 * sx), S(cy + lat * rr + s2 * 0.8)], fill=(90, 180, 90, 255))
    circ(d, cx, cy, rr, INK, None, 7)
def helix(d, cx, y0, y1, t, amp=120, glow=0.0, p=1.0):
    # ADN dessiné en « 3D » : deux brins sinusoïdaux qui tournent, barreaux, épaisseur selon la profondeur
    if p <= 0: return
    n = 26; yy = [y0 + (y1 - y0) * k / (n - 1) for k in range(int(n * clamp(p)) or 1)]
    for k, y in enumerate(yy):
        a = k * 0.55 + t * 2.2; xa, xb = cx + amp * math.sin(a), cx - amp * math.sin(a); depth = math.cos(a)
        cols = [(70, 150, 235), (245, 140, 50)]; mid = k == n // 2
        line(d, xa, y, xb, y, (255, 220, 60) if mid and glow > 0 else ((230, 120, 200) if k % 2 else (120, 210, 120)), 7)
        if mid and glow > 0: circ(d, cx, y, 26 + 10 * math.sin(t * 9), None, (90, 170, 255, int(140 * glow))); circ(d, cx, y, 14, None, BLUE + (255,))
        for x_, c_, dd in ((xa, cols[0], depth), (xb, cols[1], -depth)):
            circ(d, x_, y, 15 + 6 * dd, INK, c_ + (255,), 4)
def counter(img, xy, val, fmt, size, col):
    text(img, xy, fmt.format(val), AF(size), col)
def drop_(d, cx, cy, r, col, sq=0.0):
    # goutte de peinture avec écrasement/étirement (sq > 0 : écrasée)
    rx, ry = r * (1 + 0.25 * sq), r * (1 - 0.2 * sq)
    d.polygon([(S(cx - rx * 0.9), S(cy - ry * 0.4)), (S(cx), S(cy - ry * 2.1)), (S(cx + rx * 0.9), S(cy - ry * 0.4))], fill=col + (255,))
    d.ellipse([S(cx - rx), S(cy - ry), S(cx + rx), S(cy + ry)], fill=col + (255,), outline=INK, width=S(6))
    d.polygon([(S(cx - rx * 0.86), S(cy - ry * 0.45)), (S(cx), S(cy - ry * 2.05)), (S(cx + rx * 0.86), S(cy - ry * 0.45))], fill=col + (255,))
    line(d, cx - rx * 0.93, cy - ry * 0.38, cx, cy - ry * 2.1, INK, 6); line(d, cx + rx * 0.93, cy - ry * 0.38, cx, cy - ry * 2.1, INK, 6)
    circ(d, cx - rx * 0.35, cy - ry * 0.2, r * 0.18, None, (255, 255, 255, 170))
def wavy(d, x0, y0, ang, L, col, ph, w=7):
    # rayon ondulé (lumière bleue renvoyée)
    pts = [(x0 + s * math.cos(ang) - 14 * math.sin(s * 0.09 + ph) * math.sin(ang), y0 + s * math.sin(ang) + 14 * math.sin(s * 0.09 + ph) * math.cos(ang)) for s in np.linspace(0, L, 24)]
    poly(d, pts, col, w); arrow(d, *pts[-2], *pts[-1], col, w, 1, 26)
def bar(img, d, x, y, w, h, val, col, label):
    rect(d, x, y, x + w, y + h, INK, 6, 1, 14, fill=(240, 240, 240, 255))
    if val > 0.01: d.rounded_rectangle([S(x + 6), S(y + h - (h - 12) * val - 6), S(x + w - 6), S(y + h - 6)], S(10), fill=col + (255,))
    text(img, (x + w / 2, y + h + 40), label, AF(40), INK)
def stamp(img, xy, s, size, col, t, t0, rot=-8):
    # tampon : arrive gros puis s'écrase, avec secousse
    if t0 is None or t < t0: return
    k = clamp((t - t0) / 0.16); j = 10 * (1 - clamp((t - t0) / 0.35)) * math.sin(t * 80)
    text(img, (xy[0] + j, xy[1]), s, AF(size), col, k, rot=rot, scale=2.0 - ease(k))
# ---------- l'épisode : repères temporels, scènes, source, effets (dossier/scenes.py)
exec(open(os.path.join(DIR, 'scenes.py')).read())
if os.path.isdir(os.path.join(DIR, 'vid')):     # extraction des clips AVANT le travail en parallèle
    for f_ in sorted(os.listdir(os.path.join(DIR, 'vid'))):
        if f_.endswith('.mp4'): clip_frames(f_[:-4])
def camera(t, sc):
    # zoom lent continu + léger balancement + zooms d'impact et secousses
    a0, a1 = SC[sc], SC[sc + 1]; z = 1.0 + 0.045 * eio((t - a0) / max(0.5, a1 - a0)); rot = 0.6 * math.sin(t * 0.9)
    for t0, amp in PUNCH:
        if t0 and 0 <= t - t0 < 0.6: z += amp * math.exp(-(t - t0) * 7) * min(1, (t - t0) / 0.05)
    ox = oy = 0
    for t0, amp in SHAKE:
        if t0 and 0 <= t - t0 < 0.35: k = (1 - (t - t0) / 0.35) ** 2; ox += amp * k * math.sin((t - t0) * 95); oy += amp * k * math.cos((t - t0) * 83)
    return z, rot, ox, oy
# ---------- sous-titres : 3 mots max, mot actif qui « pop » (jaune), contour noir
GROUPS = []; cur = []
for k, w_ in enumerate(WORDS):
    cur.append(k)
    if len(cur) == 3 or re.search(r'[.,:!?…–]$', w_[0]): GROUPS.append(cur); cur = []
if cur: GROUPS.append(cur)
def caption(img, t):
    g = next((g for g in GROUPS if WORDS[g[0]][1] - 0.05 <= t < WORDS[g[-1]][2] + 0.25), None)
    if not g: return
    ws = [WORDS[k][0].strip('.,:!?„“"…').upper() for k in g]; base = 60 * K; cf = F('Poppins-ExtraBold.ttf', base)
    wd = [cf.getbbox(w)[2] for w in ws]; sp = 20 * K; tw_ = sum(wd) + sp * (len(ws) - 1)
    if tw_ > (W - 140) * K: base = int(base * (W - 140) * K / tw_); cf = F('Poppins-ExtraBold.ttf', base); wd = [cf.getbbox(w)[2] for w in ws]; tw_ = sum(wd) + sp * (len(ws) - 1)
    d = ImageDraw.Draw(img); x = W * K / 2 - tw_ / 2; y = 1715 * K
    for w, k, ww in zip(ws, g, wd):
        t0 = WORDS[k][1]
        if t >= t0 - 0.03:
            u = (t - t0) / 0.12; pop = 1 + 0.16 * math.sin(clamp(u) * math.pi) if u < 1 else 1
            active = t0 <= t < WORDS[k][2] + 0.05
            f2 = F('Poppins-ExtraBold.ttf', base * pop) if pop != 1 else cf
            d.text((x + ww / 2, y), w, font=f2, fill=YEL if (active or HOT.search(w)) else (255, 255, 255), anchor='mm', stroke_width=7 * K, stroke_fill=(0, 0, 0))
        x += ww + sp
def draw(t):
    sc = max(i for i in range(len(SC) - 1) if t >= SC[i])
    lay = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    confetti(d, t)
    scene(lay, d, sc, t)
    if SOURCE[1] <= t < SOURCE[2]: text(lay, (W / 2, 1810), SOURCE[0], HF(32), GREY, min(since(t, SOURCE[1], 0.3), 1 - since(t, SOURCE[2] - 0.3, 0.3)))
    tout = clamp((SC[sc + 1] - t) / 0.1) if sc < len(SC) - 2 else 1      # sortie très rapide, sur place
    if tout < 1: lay.putalpha(lay.getchannel('A').point(lambda v: int(v * tout)))
    img = Image.new('RGBA', (W * SS, H * SS), BG + (255,)); img.alpha_composite(lay)
    z, rot, ox, oy = camera(t, sc)
    if abs(rot) > 0.02: img = img.rotate(rot, resample=Image.BILINEAR, fillcolor=BG + (255,))
    cw_, ch_ = W * SS / z, H * SS / z; cx = min(max(W * SS / 2 + S(ox), cw_ / 2), W * SS - cw_ / 2); cy = min(max(H * SS * 0.5 + S(oy), ch_ / 2), H * SS - ch_ / 2)   # le cadre reste dans l'image
    out = img.convert('RGB').resize((W * K, H * K), Image.LANCZOS, box=(cx - cw_ / 2, cy - ch_ / 2, cx + cw_ / 2, cy + ch_ / 2))
    caption(out, t); return out
def frame_bytes(n): return draw(n / FPS).tobytes()
if __name__ == '__main__':
    if os.environ.get('PREVIEW'):
        for ts in os.environ['PREVIEW'].split(','): draw(float(ts)).resize((W, H), Image.LANCZOS).save(f'{OUT}_{ts}.jpg', quality=88)
        sys.exit(0)
    TMP = OUT + '_fr'; shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP); NF = int(DUR * FPS)
    N = int(DUR * SR); mix_ = np.zeros(N); mix_[:len(VOICE)] += VOICE
    def sfx(name, t0, g):
        if t0 is None: return
        w = wave.open(SFXD + name + '.wav'); s = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float) / 32768
        if w.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
        if w.getframerate() != SR: s = np.interp(np.arange(0, len(s), w.getframerate() / SR), np.arange(len(s)), s)
        i0 = int(max(0, t0) * SR); L = min(len(s), N - i0); mix_[i0:i0 + L] += s[:L] * g
    for t0 in SC[1:-1]: sfx('whoosh', t0 - 0.05, 0.12)
    SFX(sfx)
    # musique fournie : remontée, baissée sous la voix
    mu = np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', os.path.join(DIR, 'musique.mp3'), '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(float) / 32768
    mu = np.pad(mu, (0, max(0, N - len(mu))))[:N]; mu = mu / max(1e-6, np.sqrt(np.mean(mu[:int(20 * SR)] ** 2)))      # même niveau moyen
    vv = np.zeros(N); vv[:min(N, len(VOICE))] = np.abs(VOICE[:N]) > 0.03; env = np.convolve(vv, np.ones(int(0.25 * SR)) / int(0.25 * SR), 'same')
    mix_ += mu * 0.075 * (1 - 0.35 * np.clip(env * 3, 0, 1))
    fd = int(0.4 * SR); mix_[-fd:] *= np.linspace(1, 0, fd); mix_ = mix_ / max(1e-6, np.abs(mix_).max()) * 0.92
    wo = wave.open(f'{TMP}/a.wav', 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((mix_ * 32767).astype('<i2').tobytes()); wo.close()
    enc = subprocess.Popen([FF, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W * K}x{H * K}', '-r', str(FPS), '-i', '-', '-i', f'{TMP}/a.wav',
                            '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k',
                            '-af', 'pan=stereo|c0=c0|c1=c0,loudnorm=I=-14:TP=-1:LRA=11', '-ar', '44100', '-shortest', '-movflags', '+faststart', OUT], stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for n, b in enumerate(pool.imap(frame_bytes, range(NF), chunksize=4)):
            enc.stdin.write(b)
            if n % 600 == 0: print('images', n, '/', NF, flush=True)
    enc.stdin.close(); enc.wait(); shutil.rmtree(TMP); print('ok', OUT, round(DUR, 2), f'{W * K}x{H * K}')
