# Vidéo « affiches animées » (suite de posterv.py) : chaque photo devient une affiche, mais tout bouge :
# titre qui s'écrit lettre par lettre, pastilles « $0 GIFTS » qui sautent et se balancent, petites bulles « $0 » qui flottent,
# CODE qui glisse et pulse, logo TEMU qui apparaît, description du post écrite dans l'image (mise en page E).
# Le code est toujours affiché en entier (jamais tapé lettre par lettre) pour qu'on ne lise jamais un code incomplet.
# usage : posterv2.py config.json out.mp4
import json, sys, os, math, subprocess, shutil, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
C = json.load(open(sys.argv[1])); OUT = sys.argv[2]; D = os.path.dirname(os.path.abspath(sys.argv[1]))
W, H, FPS = 1080, 1920, 30; SL = C['slide_dur']; TR = 0.45
FD = '/home/user/skillora./temu/fonts/'; SFX = '/home/user/skillora./motion/sfx/'
P = C['palette']; C1, C2, DK, ACC = [tuple(P[k]) for k in ('c1', 'c2', 'dark', 'acc')]; HF = C['font']; CF = 'Poppins-ExtraBold.ttf'   # CF : code et phrases (minuscules exactes)
_fc = {}
def F(name, sz):
    k = (name, int(sz))
    if k not in _fc: _fc[k] = ImageFont.truetype(FD + name, max(8, int(sz)))
    return _fc[k]
CODE = C['code']; TXT = C['code_text']; i0 = TXT.index(CODE); PRE, POST = TXT[:i0].strip(), TXT[i0 + len(CODE):].strip()
LOGO = Image.open('/home/user/skillora./temu/temu_logo.png').convert('RGBA')
DISC = C.get('disclaimer', '*T&Cs apply. The purchase required is determined by the gift(s)\' value.')
DESC = C.get('desc', ["These Temu finds can't be missed!", f"Search my code [{CODE}] to unlock $0 gifts with qualifying orders on Temu!", "T&Cs apply."])
TAGS = C.get('tags', '#temu #temufinds #temucreator #musthaves')
def clamp(u): return max(0.0, min(1.0, u))
def ease(u): u = clamp(u); return 1 - (1 - u) ** 3
def back(u): u = clamp(u); c = 1.7; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2
def comp(img, lay, xy):
    x, y = int(xy[0]), int(xy[1]); cx0, cy0 = max(0, -x), max(0, -y)
    if cx0 >= lay.width or cy0 >= lay.height or x >= img.width or y >= img.height: return
    img.alpha_composite(lay.crop((cx0, cy0, min(lay.width, img.width - x), min(lay.height, img.height - y))), (x + cx0, y + cy0))
def put(img, lay, cx, cy, s=1.0, rot=0.0, a=1.0):
    # pose un calque centré en (cx, cy) avec échelle, rotation et transparence
    if s <= 0.02 or a <= 0.01: return
    if s != 1.0: lay = lay.resize((max(1, int(lay.width * s)), max(1, int(lay.height * s))), Image.BILINEAR)
    if rot: lay = lay.rotate(rot, expand=True, resample=Image.BICUBIC)
    if a < 0.99: lay = lay.copy(); lay.putalpha(lay.getchannel('A').point(lambda v: int(v * a)))
    comp(img, lay, (cx - lay.width / 2, cy - lay.height / 2))
def fit(txt, name, sz, maxw):
    f = F(name, sz)
    while f.getbbox(txt)[2] > maxw and sz > 20: sz -= 4; f = F(name, sz)
    return f
def shadow(img, fn):
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); fn(ImageDraw.Draw(lay))
    sh = Image.new('RGBA', img.size, (0, 0, 0, 0)); sh.putalpha(lay.getchannel('A').point(lambda v: v * 0.6)); sh = sh.filter(ImageFilter.GaussianBlur(8))
    img.alpha_composite(sh, (4, 6)); img.alpha_composite(lay)
def typed(lines, t, t0, cps=26):
    # texte qui s'écrit : renvoie les lignes coupées au nombre de lettres déjà tapées
    n = int(max(0, t - t0) * cps); out = []
    for l in lines: out.append(l[:max(0, n)]); n -= len(l)
    return out
def logo(img, x, y, s, t, t0):
    k = back((t - t0) / 0.35); put(img, LOGO.resize((s, s), Image.LANCZOS), x, y, k, 8 * math.sin(t * 3))
def sentence(d, cx, y, f, col, ccol, lh):
    # phrase officielle, code en couleur : « Search code alq393258 for » / « Gifts at $0 in TEMU app »
    l1 = PRE + ' ' + CODE + ' ' + POST.split(' ')[0]; rest = ' '.join(POST.split(' ')[1:])
    x = cx - f.getbbox(l1)[2] / 2; d.text((x, y), PRE + ' ', font=f, fill=col, anchor='lm'); x += f.getbbox(PRE + ' ')[2]
    d.text((x, y), CODE, font=f, fill=ccol, anchor='lm'); x += f.getbbox(CODE + ' ')[2]; d.text((x, y), POST.split(' ')[0], font=f, fill=col, anchor='lm')
    d.text((cx, y + lh), rest, font=f, fill=col, anchor='mm')
def disclaimer(img, t, y=1872):
    f = F('Nunito.ttf', 26); d = ImageDraw.Draw(img); a = int(255 * clamp(t / 0.4))
    d.text((W / 2, y), DISC, font=fit(DISC, 'Nunito.ttf', 26, W - 100), fill=(255, 255, 255, a), anchor='mm', stroke_width=3, stroke_fill=(0, 0, 0, a))
# ---- pastilles de l'offre (dessinées une fois, puis animées)
_bc = {}
def round_badge(r):
    if ('r', r) in _bc: return _bc[('r', r)]
    lay = Image.new('RGBA', (2 * r + 20, 2 * r + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); c = r + 10
    d.ellipse([c - r, c - r, c + r, c + r], fill=ACC + (255,), outline=(255, 255, 255), width=8)
    d.text((c, c - r * 0.18), '$0', font=fit('$0', CF, int(r * 0.95), int(r * 1.5)), fill=(255, 255, 255), anchor='mm')
    d.text((c, c + r * 0.5), 'GIFTS', font=fit('GIFTS', CF, int(r * 0.34), int(r * 1.3)), fill=(255, 255, 255), anchor='mm')
    _bc[('r', r)] = lay; return lay
def burst_badge(r):
    if ('b', r) in _bc: return _bc[('b', r)]
    lay = Image.new('RGBA', (2 * r + 40, 2 * r + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); c = r + 20
    pts = [(c + (r if j % 2 == 0 else r * 0.82) * math.cos(j * math.pi / 14), c + (r if j % 2 == 0 else r * 0.82) * math.sin(j * math.pi / 14)) for j in range(28)]
    d.polygon(pts, fill=C2 + (255,)); d.text((c, c - r * 0.2), '$0', font=fit('$0', CF, int(r * 0.8), int(r * 1.2)), fill=DK, anchor='mm')
    d.text((c, c + r * 0.38), 'GIFTS', font=fit('GIFTS', CF, int(r * 0.3), int(r * 1.1)), fill=DK, anchor='mm')
    _bc[('b', r)] = lay; return lay
def ticket():
    if 't' in _bc: return _bc['t']
    tk = Image.new('RGBA', (520, 280), (0, 0, 0, 0)); td = ImageDraw.Draw(tk); td.rounded_rectangle([0, 0, 519, 279], 24, fill=ACC + (255,))
    for yy in (60, 140, 220): td.ellipse([-30, yy - 30, 30, yy + 30], fill=(0, 0, 0, 0)); td.ellipse([490, yy - 30, 550, yy + 30], fill=(0, 0, 0, 0))
    td.rectangle([40, 20, 479, 259], outline=(255, 255, 255), width=4); td.text((260, 110), '$0', font=F(CF, 130), fill=(255, 255, 255), anchor='mm')
    td.text((260, 215), 'GIFTS IN THE APP', font=fit('GIFTS IN THE APP', CF, 44, 400), fill=(255, 255, 255), anchor='mm')
    _bc['t'] = tk; return tk
def bubbles(img, t, k, n=6):
    # petites bulles « $0 » qui montent en se balançant
    rs = np.random.RandomState(40 + k); d = ImageDraw.Draw(img)
    for j in range(n):
        x0 = rs.uniform(90, W - 160); sp = rs.uniform(110, 190); r = rs.uniform(34, 52); ph = rs.uniform(0, 6.28); y = (rs.uniform(500, 1500) - sp * t) % 1300 + 420
        x = x0 + 26 * math.sin(t * 2 + ph); a = int(200 * clamp(t / 0.5)); col = (C2 if j % 2 else C1) + (a,)
        d.ellipse([x - r, y - r, x + r, y + r], fill=col, outline=(255, 255, 255, a), width=3)
        d.text((x, y), '$0', font=F(CF, int(r * 0.85)), fill=DK + (a,), anchor='mm')
def code_pill(img, cx, cy, t, t0, maxw=760, from_x=None):
    # « CODE: alq393258 » : glisse depuis le bord puis pulse légèrement
    txt = 'CODE: ' + CODE; f = fit(txt, CF, 100, maxw); tw = f.getbbox(txt)[2]
    lay = Image.new('RGBA', (tw + 110, 150), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); d.rounded_rectangle([0, 0, tw + 109, 149], 75, fill=C2 + (255,))
    d.text(((tw + 110) / 2, 76), txt, font=f, fill=DK, anchor='mm')
    u = ease((t - t0) / 0.4); x = (from_x if from_x is not None else -W / 2) * (1 - u) + cx * u
    put(img, lay, x, cy, 1 + 0.03 * math.sin(t * 6) * u)
def lines_of(t): return t.split('|')
# ---- mises en page animées
def layout_A(img, title, k, t):   # bandeau phrase en haut, titre empilé à droite qui s'écrit, pastille ronde, CODE en bas
    bubbles(img, t, k)
    d = ImageDraw.Draw(img); d.rounded_rectangle([60, 120, W - 60, 300], 40, fill=DK + (190,)); sentence(d, W / 2, 175, fit(PRE + ' ' + CODE + ' for', CF, 60, W - 180), (255, 255, 255), C2, 72)
    ls = lines_of(title); sz = 128; ty = typed(ls, t, 0.15)
    shadow(img, lambda dd: [dd.text((W - 70, 380 + j * sz * 1.02), l, font=fit(ls[j], HF, sz, W - 380), fill=C1 if j % 2 == 0 else C2, anchor='ra') for j, l in enumerate(ty)])
    put(img, round_badge(165), 230, 1350, back((t - 0.5) / 0.4), -6 + 7 * math.sin(t * 4))
    code_pill(img, 420, 1610, t, 0.8); logo(img, W - 140, 1380, 170, t, 1.0); disclaimer(img, t)
def layout_B(img, title, k, t):   # CODE en bloc couleur en haut à gauche, titre sur blocs penchés qui arrivent, bannière $0 en bas
    bubbles(img, t, k, 5); d = ImageDraw.Draw(img)
    u = ease(t / 0.35); x0 = -520 * (1 - u)
    d.rectangle([x0, 150, x0 + 520, 400], fill=C2 + (255,)); d.text((x0 + 50, 215), 'CODE:', font=F(CF, 70), fill=DK, anchor='lm'); d.text((x0 + 50, 325), CODE, font=fit(CODE, CF, 96, 440), fill=DK, anchor='lm')
    ls = lines_of(title); y = 470
    for j, l in enumerate(ls):
        tj = 0.25 + 0.22 * j; q = ease((t - tj) / 0.35)
        if q <= 0: continue
        f = fit(l, HF, 120, 760); tw = f.getbbox(l)[2]; blk = Image.new('RGBA', (tw + 70, 160), (0, 0, 0, 0)); bd = ImageDraw.Draw(blk)
        bd.rectangle([0, 0, tw + 69, 159], fill=DK + (235,)); bd.text((35, 80), l, font=f, fill=C1 if j % 2 == 0 else C2, anchor='lm')
        blk = blk.rotate(9, expand=True, resample=Image.BICUBIC); xe = W - blk.width - 40 - j * 25; comp(img, blk, (xe + (W - xe) * (1 - q), y)); y += 150
    logo(img, 160, 1040, 170, t, 0.9)
    d = ImageDraw.Draw(img); d.rounded_rectangle([90, 1340, W - 90, 1520], 20, fill=DK + (235,), outline=C2, width=5)
    sentence(d, W / 2, 1395, fit(PRE + ' ' + CODE + ' for', CF, 62, W - 260), (255, 255, 255), C2, 75)
    q = back((t - 0.7) / 0.4)
    if q > 0.02:
        ban = Image.new('RGBA', (W - 180, 160), (0, 0, 0, 0)); bd = ImageDraw.Draw(ban); bd.rounded_rectangle([0, 0, W - 181, 159], 18, fill=(255, 255, 255)); bd.rectangle([290, 0, W - 181, 159], fill=C2)
        bd.text((145, 80), '$0', font=F(CF, 110), fill=ACC, anchor='mm'); bd.text((290 + (W - 470) / 2, 80), 'GIFTS IN THE APP', font=fit('GIFTS IN THE APP', CF, 70, W - 520), fill=DK, anchor='mm')
        put(img, ban, W / 2, 1640, q)
    disclaimer(img, t)
def layout_C(img, title, k, t):   # titre centré qui s'écrit, ticket $0 qui se balance, pilule CODE + phrase
    bubbles(img, t, k)
    ls = lines_of(title); ty = typed(ls, t, 0.1)
    shadow(img, lambda dd: [dd.text((W / 2, 170 + j * 132), l, font=fit(ls[j], HF, 136, W - 140), fill=C1 if j % 2 == 0 else C2, anchor='ma', stroke_width=6, stroke_fill=DK) for j, l in enumerate(ty)])
    logo(img, 110, 90, 120, t, 0.2)
    put(img, ticket(), W - 300, C['slides'][k].get('tk_y', 1180), back((t - 0.55) / 0.45), -8 + 6 * math.sin(t * 3.2))
    code_pill(img, W / 2, 1540, t, 0.9, from_x=W * 1.5)
    shadow(img, lambda dd: sentence(dd, W / 2, 1680, F(CF, 54), (255, 255, 255), C1, 64)); disclaimer(img, t)
def layout_D(img, title, k, t):   # dégradé sombre en bas, titre à gauche qui s'écrit, étoile $0 qui tourne, CODE souligné
    g = Image.new('RGBA', (W, 900), (0, 0, 0, 0)); a = np.linspace(0, 215, 900).astype('uint8'); g.putalpha(Image.fromarray(np.repeat(a[:, None], W, 1)))
    dk = Image.new('RGBA', (W, 900), DK + (255,)); dk.putalpha(g.getchannel('A')); img.alpha_composite(dk, (0, H - 900))
    bubbles(img, t, k, 5)
    d = ImageDraw.Draw(img); d.rectangle([0, 90, W, 230], fill=DK + (200,)); sentence(d, W / 2, 132, fit(PRE + ' ' + CODE + ' for', CF, 52, W - 140), (255, 255, 255), C2, 60)
    put(img, burst_badge(190), W - 220, 480, back((t - 0.3) / 0.45), 8 + t * 25)
    ls = lines_of(title); y0 = 1480 - len(ls) * 120; ty = typed(ls, t, 0.2)
    shadow(img, lambda dd: [dd.text((70, y0 + j * 120), l, font=fit(ls[j], HF, 124, W - 140), fill=C1 if j % 2 == 0 else C2, anchor='la') for j, l in enumerate(ty)])
    d = ImageDraw.Draw(img); f = fit('CODE: ' + CODE, CF, 96, 700); a_ = int(255 * clamp((t - 0.7) / 0.3)); d.text((70, 1620), 'CODE: ' + CODE, font=f, fill=(255, 255, 255, a_), anchor='lm')
    d.rectangle([70, 1690, 70 + f.getbbox('CODE: ' + CODE)[2] * ease((t - 0.9) / 0.5), 1702], fill=C2); logo(img, W - 140, 1630, 150, t, 1.0); disclaimer(img, t)
def layout_E(img, title, k, t):   # la description du post écrite dans une carte blanche, code surligné, hashtags
    bubbles(img, t, k, 4); u = back(t / 0.4)
    cw = 900; f = F(CF, 50); lines = []
    for para in DESC:   # coupe la description en lignes qui tiennent dans la carte
        cur = ''
        for w in para.split():
            if cur and f.getbbox(cur + ' ' + w)[2] > cw - 100: lines.append(cur); cur = w
            else: cur = (cur + ' ' + w).strip()
        lines.append(cur); lines.append('')
    ch = 170 + sum(68 if l else 24 for l in lines) + 70
    card = Image.new('RGBA', (cw, ch), (0, 0, 0, 0)); d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, cw - 1, ch - 1], 44, fill=(255, 255, 255, 240)); d.rounded_rectangle([0, 0, cw - 1, 120], 44, fill=DK + (255,)); d.rectangle([0, 80, cw - 1, 120], fill=DK + (255,))
    card.alpha_composite(LOGO.resize((84, 84), Image.LANCZOS), (30, 18)); d.text((136, 60), '#ad  Temu finds', font=F(CF, 46), fill=(255, 255, 255), anchor='lm')
    ty = typed(lines, t, 0.25, 140); y = 170
    for full, l in zip(lines, ty):
        if not full: y += 24; continue
        x = 50
        for w in l.split(' '):   # le code (et $0) en couleur, le reste en foncé
            col = ACC if (CODE in w or '$0' in w) else DK
            d.text((x, y), w, font=f, fill=col, anchor='lm'); x += f.getbbox(w + ' ')[2]
        y += 68
    d.text((50, ch - 60), TAGS, font=fit(TAGS, CF, 36, cw - 100), fill=C2 if sum(C2) < 600 else ACC, anchor='lm')
    put(img, card, W / 2, 900, u, -2 + 1.5 * math.sin(t * 2))
    put(img, round_badge(110), W - 130, 420, back((t - 0.9) / 0.4), 10 * math.sin(t * 4))
    code_pill(img, W / 2, 1530, t, 1.0); disclaimer(img, t)
LAY = {'A': layout_A, 'B': layout_B, 'C': layout_C, 'D': layout_D, 'E': layout_E}
# ---- photos (fond) et images
PH = [Image.open(os.path.join(D, s['img'])).convert('RGB') for s in C['slides']]
def cover(im):
    s = max(W / im.width, H / im.height); im = im.resize((int(im.width * s + 0.5), int(im.height * s + 0.5)), Image.LANCZOS)
    return im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))
PH = [cover(p) for p in PH]; N = len(PH); DUR = N * SL
def frame(i, t):
    q = min(1, t / SL); z = 1 + 0.05 * (q if i % 2 == 0 else 1 - q) + 0.002; cw, ch = W / z, H / z
    img = PH[i].resize((W, H), Image.BILINEAR, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2)).convert('RGBA')
    s = C['slides'][i]; LAY[s['layout']](img, s.get('title', ''), i, t); return img.convert('RGB')
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
    if TP == 'blinds':
        o = a.copy(); n = 8; sw = W // n
        for j in range(n):
            uj = ease((u - j * 0.05) / 0.6); w = int(sw * uj)
            if w > 0: o.paste(b.crop((j * sw, 0, j * sw + w, H)), (j * sw, 0))
        return o
    return Image.blend(a, b, e)
if __name__ == '__main__':
    if os.environ.get('PREVIEW'):
        for ts in os.environ['PREVIEW'].split(','):
            T = float(ts); i = min(N - 1, int(T / SL)); frame(i, T - i * SL).save(f'{OUT}_{ts}.jpg', quality=88)
        sys.exit(0)
    NF = int(DUR * FPS); tmp = OUT + '_fr'; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    for n in range(NF):
        T = n / FPS; i = min(N - 1, int(T / SL)); t = T - i * SL; img = frame(i, t)
        if i > 0 and t < TR: img = trans(frame(i - 1, SL + t), img, t / TR, T)
        img.save(f'{tmp}/f{n:05d}.jpg', quality=93)
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
        if k: sfx(C.get('sfx', 'whoosh'), k * SL - 0.05, 0.45)
        sfx('pop', k * SL + 0.5, 0.18); sfx('ding', k * SL + 0.85, 0.08)
    fd = int(0.6 * SR); m[-fd:] *= np.linspace(1, 0, fd); m = m / max(1e-6, np.abs(m).max()) * 0.9
    wo = wave.open(os.path.join(tmp, 'a.wav'), 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((m * 32767).astype('<i2').tobytes()); wo.close()
    subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/f%05d.jpg', '-i', os.path.join(tmp, 'a.wav'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
    shutil.rmtree(tmp); print('ok', OUT, DUR)
