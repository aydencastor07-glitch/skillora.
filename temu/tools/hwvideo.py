# Vidéo diaporama Halloween (campagne coupon) : 4 photos, 6 modèles de mise en page / transitions différents.
# usage : hwvideo.py config.json out.mp4
# config = {"template": "vampire|zombie|witch|neon|patch|mummy", "slides": [{"img":..., "title":...}, ...],
#           "code_text":..., "code":..., "disclaimer":..., "music_seed":.., "bpm":.., "key":..}
import json, sys, os, math, subprocess, shutil, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
C = json.load(open(sys.argv[1])); OUT = sys.argv[2]; D = os.path.dirname(os.path.abspath(sys.argv[1]))
W, H, FPS = 1080, 1920, 30; SL = C.get('slide_dur', 3.6); TR = 0.5; TP = C['template']
FD = '/home/user/skillora./temu/fonts/'; SFX = '/home/user/skillora./motion/sfx/'
def F(name, sz):
    f = ImageFont.truetype(FD + name, sz)
    try: f.set_variation_by_axes([800])
    except Exception: pass
    return f
def ease(u): u = max(0, min(1, u)); return 1 - (1 - u) ** 3
def back(u): u = max(0, min(1, u)); c = 1.7; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2
LOGO = Image.open('/home/user/skillora./temu/temu_logo.png').convert('RGBA')
def logo(img, x, y, s=120):
    img.alpha_composite(LOGO.resize((s, s), Image.LANCZOS), (int(x - s / 2), int(y - s / 2)))
def logo_move(img, i, t, s=110):
    # logo qui change de place à chaque photo : glisse vers sa nouvelle position, rebondit et tourne un peu
    P = C['logo_path']; (x1, y1) = P[i % len(P)]; (x0, y0) = P[(i - 1) % len(P)] if i else (x1, y1)
    e = ease(t / 0.7); x = (x0 + (x1 - x0) * e) * W; y = (y0 + (y1 - y0) * e) * H
    sc = s * (0.85 + 0.15 * back(t / 0.5)); lg = LOGO.resize((int(sc), int(sc)), Image.LANCZOS).rotate(12 * (1 - e) * (1 if i % 2 else -1) + 3 * math.sin(t * 4), expand=True, resample=Image.BICUBIC)
    img.alpha_composite(lg, (int(x - lg.width / 2), int(y - lg.height / 2)))
CODE = C['code']; TXT = C['code_text']; i0 = TXT.index(CODE)
PRE, POST = TXT[:i0].strip(), TXT[i0 + len(CODE):].strip()          # « Search code » / « for $100 Coupon Bundle in TEMU app »
SRC = [Image.open(os.path.join(D, s['img'])).convert('RGB') for s in C['slides']]
N = len(SRC); DUR = N * SL
# ---- image de fond qui bouge doucement (Ken Burns), sens différent selon la photo
def bg(i, t):
    im = SRC[i]; z = 1.04 + 0.07 * (t / SL) if i % 2 == 0 else 1.11 - 0.07 * (t / SL)
    sw, sh = im.width / z, im.height / z; dx = (im.width - sw) * (0.5 + 0.3 * math.sin(i * 2.1) * (t / SL - 0.5)); dy = (im.height - sh) * (0.35 if i % 3 else 0.5)
    return im.resize((W, H), Image.BILINEAR, box=(dx, dy, dx + sw, dy + sh)).convert('RGBA')
# ---- transitions (une par modèle)
def transition(a, b, u, t_abs):
    if TP == 'vampire':   # fondu à travers un voile rouge sang
        r = Image.new('RGBA', (W, H), (110, 0, 15, 255))
        return Image.blend(a, r, min(1, u * 2) * 0.7) if u < 0.5 else Image.blend(b, r, (1 - u) * 2 * 0.7)
    if TP == 'zombie':    # la nouvelle photo pousse l'ancienne vers le haut
        e = ease(u); o = Image.new('RGBA', (W, H)); o.paste(a, (0, int(-H * e))); o.paste(b, (0, int(H * (1 - e)))); return o
    if TP == 'witch':     # cercle magique qui s'ouvre depuis le centre
        m = Image.new('L', (W, H), 0); R = ease(u) * 1150; ImageDraw.Draw(m).ellipse([W / 2 - R, H * 0.45 - R, W / 2 + R, H * 0.45 + R], fill=255)
        o = a.copy(); o.paste(b, (0, 0), m.filter(ImageFilter.GaussianBlur(14))); return o
    if TP == 'neon':      # coupure « glitch » : canaux décalés + tranches
        src = a if u < 0.45 else b; k = 1 - abs(u - 0.45) / 0.55; arr = np.asarray(src).copy(); o = int(40 * k)
        arr[..., 0] = np.roll(arr[..., 0], o, 1); arr[..., 2] = np.roll(arr[..., 2], -o, 1); rs = np.random.RandomState(int(t_abs * 60))
        for _ in range(8):
            y = rs.randint(0, H - 100); h = rs.randint(15, 100); arr[y:y + h] = np.roll(arr[y:y + h], int(rs.randint(-120, 120) * k), 1)
        return Image.fromarray(arr)
    if TP == 'patch':     # panoramique rapide (whip) avec flou de mouvement
        e = ease(u); o = Image.new('RGBA', (W, H)); o.paste(a, (int(-W * e), 0)); o.paste(b, (int(W * (1 - e)), 0))
        k = int(30 * math.sin(u * math.pi)); return o.filter(ImageFilter.BoxBlur(k)) if k > 1 else o
    if TP == 'mummy':     # zoom à travers : l'ancienne grossit et disparaît, la nouvelle se pose
        za = 1 + 0.6 * ease(u); zb = 1.25 - 0.25 * ease(u)
        A = a.resize((int(W * za), int(H * za)), Image.BILINEAR).crop((int((W * za - W) / 2), int((H * za - H) / 2), int((W * za - W) / 2) + W, int((H * za - H) / 2) + H))
        B = b.resize((int(W * zb), int(H * zb)), Image.BILINEAR).crop((int((W * zb - W) / 2), int((H * zb - H) / 2), int((W * zb - W) / 2) + W, int((H * zb - H) / 2) + H))
        return Image.blend(A, B, ease(u))
# ---- petits outils de texte
def wrap(txt, f, maxw):
    ls = [[]]
    for w in txt.split():
        if ls[-1] and f.getbbox(' '.join(ls[-1] + [w]))[2] > maxw: ls.append([])
        ls[-1].append(w)
    return [' '.join(l) for l in ls]
def disclaimer(img, col=(255, 255, 255), y=1862):
    f = F('Nunito.ttf', 23); d = ImageDraw.Draw(img)
    for k, l in enumerate(wrap(C['disclaimer'], f, W - 120)):
        d.text((W / 2, y + k * 28 - 14), l, font=f, fill=col, anchor='mm', stroke_width=2, stroke_fill=(0, 0, 0))
def shadow_text(img, xy, txt, f, fill, anchor='mm', sh=(0, 0, 0, 170), off=5, blur=6):
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); ImageDraw.Draw(lay).text((xy[0] + off, xy[1] + off), txt, font=f, fill=sh, anchor=anchor)
    img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(blur))); ImageDraw.Draw(img).text(xy, txt, font=f, fill=fill, anchor=anchor)
def code_lines(d, cx, y, fa, fb, ca, cb, lh):
    # « Search code alm148018 » (code en couleur) puis « for $100 Coupon Bundle in TEMU app »
    l1 = PRE + ' ' + CODE; x = cx - fa.getbbox(l1)[2] / 2
    d.text((x, y), PRE + ' ', font=fa, fill=ca, anchor='lm'); d.text((x + fa.getbbox(PRE + ' ')[2], y), CODE, font=fa, fill=cb, anchor='lm')
    d.text((cx, y + lh), POST, font=fa, fill=ca, anchor='mm')
# ---- les 6 modèles : titre + bloc code + logo + avertissement
def deco(img, i, t):
    s = C['slides'][i]; last = i == C.get('promo_slide', N - 1); u = (t - (TR if i else 0)) / 0.6; d = ImageDraw.Draw(img)
    if TP == 'vampire':
        g = (232, 192, 112); top = Image.new('RGBA', (W, 520), (0, 0, 0, 0)); a = np.linspace(200, 0, 520).astype('uint8')
        top.putalpha(Image.fromarray(np.repeat(a[:, None], W, 1))); img.alpha_composite(top)
        f = F('Cinzel.ttf', 84); ls = wrap(s['title'].upper(), f, W - 140)
        for k, l in enumerate(ls):
            lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); ImageDraw.Draw(lay).text((W / 2, 210 + k * 100), l, font=f, fill=g, anchor='mm')
            lay.putalpha(lay.getchannel('A').point(lambda v: int(v * ease(u - k * 0.3)))); img.alpha_composite(lay)
        w = 380 * ease(u); d.line([W / 2 - w, 120, W / 2 + w, 120], fill=g, width=3); d.line([W / 2 - w, 230 + len(ls) * 100 - 40, W / 2 + w, 230 + len(ls) * 100 - 40], fill=g, width=3)
        if last:
            f2 = F('Cinzel.ttf', 230); sc = 0.6 + 0.4 * back(u)
            shadow_text(img, (W / 2, 1050), '$100', F('Cinzel.ttf', int(230 * sc)), g); shadow_text(img, (W / 2, 1210), 'COUPON BUNDLE', F('Cinzel.ttf', 80), (255, 255, 255))
        y0 = 1560; d.rectangle([60, y0, W - 60, y0 + 220], fill=(70, 0, 12, 225)); d.rectangle([72, y0 + 12, W - 72, y0 + 208], outline=g, width=3)
        fa = F('Poppins-ExtraBold.ttf', 50); code_lines(d, W / 2, y0 + 80, fa, None, (255, 240, 220), g, 72)
        logo(img, W - 110, 330 + (len(ls) - 1) * 100, 110); disclaimer(img, (240, 220, 200))
    elif TP == 'zombie':
        gr = (130, 235, 70); f = F('Creepster.ttf', 120); ls = wrap(s['title'].upper(), f, W - 120)
        for k, l in enumerate(ls):
            j = 6 * math.sin(t * 23 + k) * (1 - ease(u)); y = (1450 if last else 1180) + k * 125 - (len(ls) - 1) * 62 + (1 - ease(u - k * 0.2)) * 400
            d.text((W / 2 + j, y), l, font=f, fill=gr, anchor='mm', stroke_width=8, stroke_fill=(10, 15, 5))
        if last:
            box = Image.new('RGBA', (760, 330), (0, 0, 0, 0)); bd = ImageDraw.Draw(box); bd.rounded_rectangle([0, 0, 759, 329], 30, fill=gr + (255,), outline=(10, 15, 5), width=10)
            bd.text((380, 120), '$100', font=F('Creepster.ttf', 170), fill=(10, 15, 5), anchor='mm'); bd.text((380, 262), 'COUPON BUNDLE', font=F('ArchivoBlack-Regular.ttf', 62), fill=(10, 15, 5), anchor='mm')
            box = box.rotate(4, expand=True, resample=Image.BICUBIC); s2 = max(0.05, 0.8 * back(u)); box = box.resize((int(box.width * s2), int(box.height * s2)))
            img.alpha_composite(box, (int(W / 2 - box.width / 2), int(1215 - box.height / 2)))
        cb = Image.new('RGBA', (980, 250), (0, 0, 0, 0)); cd = ImageDraw.Draw(cb); cd.rounded_rectangle([0, 0, 979, 249], 24, fill=(12, 16, 8, 235), outline=gr + (255,), width=6)
        cd.text((490, 70), 'CODE: ' + CODE, font=F('ArchivoBlack-Regular.ttf', 70), fill=gr, anchor='mm')
        cd.text((490, 160), PRE + ' ' + CODE, font=F('Poppins-ExtraBold.ttf', 38), fill=(255, 255, 255), anchor='mm'); cd.text((490, 208), POST, font=F('Poppins-ExtraBold.ttf', 38), fill=(255, 255, 255), anchor='mm')
        cb = cb.rotate(-2, expand=True, resample=Image.BICUBIC); img.alpha_composite(cb, (int(W / 2 - cb.width / 2), 1545))
        logo(img, 100, 110, 120); disclaimer(img)
    elif TP == 'witch':
        pu = (110, 40, 160); cr = (255, 246, 232)
        cb = Image.new('RGBA', (W - 80, 200), (0, 0, 0, 0)); cd = ImageDraw.Draw(cb); cd.rounded_rectangle([0, 0, W - 81, 199], 100, fill=pu + (240,))
        code_lines(cd, (W - 80) / 2, 70, F('Nunito.ttf', 50), None, (255, 255, 255), (255, 214, 90), 66)
        img.alpha_composite(cb, (40, int(70 - (1 - ease(t / 0.5 if i == 0 else 1)) * 300)))
        f = F('Pacifico.ttf', 88); ls = wrap(s['title'], f, W - 220); ch = 90 + len(ls) * 120
        card = Image.new('RGBA', (W - 120, ch), (0, 0, 0, 0)); kd = ImageDraw.Draw(card); kd.rounded_rectangle([0, 0, W - 121, ch - 1], 50, fill=cr + (245,), outline=pu + (255,), width=6)
        for k, l in enumerate(ls): kd.text(((W - 120) / 2, 75 + k * 120), l, font=f, fill=pu, anchor='mt')
        x = 60 - (1 - ease(u)) * (W + 100); img.alpha_composite(card, (int(x), int(1480 - ch / 2)))
        if last:
            st = Image.new('RGBA', (560, 560), (0, 0, 0, 0)); sd = ImageDraw.Draw(st)
            pts = [(280 + (270 if j % 2 == 0 else 220) * math.cos(j * math.pi / 12), 280 + (270 if j % 2 == 0 else 220) * math.sin(j * math.pi / 12)) for j in range(24)]
            sd.polygon(pts, fill=(255, 196, 40, 255)); sd.text((280, 240), '$100', font=F('Pacifico.ttf', 130), fill=pu, anchor='mm'); sd.text((280, 360), 'Coupon Bundle', font=F('Nunito.ttf', 56), fill=pu, anchor='mm')
            st = st.rotate(-10 + 10 * ease(u), resample=Image.BICUBIC); s2 = max(0.05, back(u)); st = st.resize((int(560 * s2), int(560 * s2)))
            img.alpha_composite(st, (int(W - 300 - st.width / 2), int(980 - st.height / 2)))
        logo(img, W - 100, 1750, 100); disclaimer(img)
    elif TP == 'neon':
        pk = (255, 60, 200); cy_ = (0, 235, 255); fl = 1 if u > 0.5 or int(t * 20) % 3 else 0.3
        f = F('Righteous.ttf', 104); ls = wrap(s['title'].upper(), f, W - 120)
        gl = Image.new('RGBA', img.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(gl); tp = Image.new('RGBA', img.size, (0, 0, 0, 0)); td = ImageDraw.Draw(tp)
        for k, l in enumerate(ls):
            y = 1150 + k * 115 - (len(ls) - 1) * 57
            gd.text((W / 2, y), l, font=f, fill=pk + (int(255 * fl),), anchor='mm', stroke_width=16, stroke_fill=pk + (int(255 * fl),)); td.text((W / 2, y), l, font=f, fill=(255, 255, 255, int(255 * min(1, u * 2))), anchor='mm')
        img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(18))); img.alpha_composite(tp)
        if last:
            g2 = Image.new('RGBA', img.size, (0, 0, 0, 0)); ImageDraw.Draw(g2).text((W / 2, 520), '$100', font=F('Righteous.ttf', 240), fill=cy_ + (255,), anchor='mm', stroke_width=14, stroke_fill=cy_ + (255,))
            img.alpha_composite(g2.filter(ImageFilter.GaussianBlur(20))); ImageDraw.Draw(img).text((W / 2, 520), '$100', font=F('Righteous.ttf', 240), fill=(255, 255, 255), anchor='mm')
            shadow_text(img, (W / 2, 690), 'COUPON BUNDLE', F('Righteous.ttf', 90), (255, 255, 255))
        cy0 = C.get('code_y', [1520] * N)[i]; bx = [70, cy0, W - 70, cy0 + 240]; g3 = Image.new('RGBA', img.size, (0, 0, 0, 0)); ImageDraw.Draw(g3).rounded_rectangle(bx, 40, outline=cy_ + (255,), width=14)
        img.alpha_composite(g3.filter(ImageFilter.GaussianBlur(14))); d = ImageDraw.Draw(img); d.rounded_rectangle(bx, 40, fill=(10, 5, 25, 200), outline=(220, 255, 255), width=4)
        code_lines(d, W / 2, cy0 + 70, F('Righteous.ttf', 54), None, (255, 255, 255), cy_, 82)
        (logo_move(img, i, t) if 'logo_path' in C else logo(img, W / 2, 110, 110)); disclaimer(img)
    elif TP == 'patch':
        org = (255, 132, 20)
        f = F('PermanentMarker.ttf', 82); ls = wrap(s['title'], f, W - 260); ph = 70 + len(ls) * 100
        pa = Image.new('RGBA', (W - 160, ph), (0, 0, 0, 0)); pd = ImageDraw.Draw(pa); pd.rectangle([0, 0, W - 161, ph - 1], fill=(255, 252, 244, 250))
        for k, l in enumerate(ls): pd.text(((W - 160) / 2, 40 + k * 100), l, font=f, fill=(25, 25, 25), anchor='mt')
        pd.rectangle([(W - 160) / 2 - 90, -10, (W - 160) / 2 + 90, 30], fill=(250, 220, 150, 200))
        pa = pa.rotate(3 if i % 2 else -3, expand=True, resample=Image.BICUBIC); y = C.get('title_y', [230] * N)[i] - (1 - back(u)) * 500
        img.alpha_composite(pa, (int(W / 2 - pa.width / 2), int(y)))
        if last:
            pu = Image.new('RGBA', (600, 600), (0, 0, 0, 0)); qd = ImageDraw.Draw(pu); qd.ellipse([20, 60, 580, 580], fill=org + (255,), outline=(120, 50, 0), width=8); qd.rectangle([275, 10, 325, 80], fill=(70, 110, 30))
            qd.text((300, 290), '$100', font=F('PermanentMarker.ttf', 150), fill=(255, 255, 255), anchor='mm'); qd.text((300, 430), 'Coupon Bundle', font=F('PermanentMarker.ttf', 56), fill=(255, 255, 255), anchor='mm')
            s2 = max(0.05, back(u)); pu = pu.resize((int(600 * s2), int(600 * s2))); img.alpha_composite(pu, (int(W / 2 - pu.width / 2), int(980 - pu.height / 2)))
        tg = Image.new('RGBA', (700, 330), (0, 0, 0, 0)); td = ImageDraw.Draw(tg)
        td.polygon([(60, 0), (699, 0), (699, 329), (60, 329), (0, 165)], fill=org + (255,)); td.ellipse([40, 145, 80, 185], fill=(255, 252, 244))
        td.text((390, 55), PRE, font=F('PermanentMarker.ttf', 46), fill=(255, 255, 255), anchor='mm'); td.text((390, 140), CODE, font=F('ArchivoBlack-Regular.ttf', 82), fill=(40, 20, 0), anchor='mm')
        for k, l in enumerate(wrap(POST, F('PermanentMarker.ttf', 40), 560)): td.text((390, 222 + k * 50), l, font=F('PermanentMarker.ttf', 40), fill=(255, 255, 255), anchor='mm')
        side, ty = C.get('tag_pos', [['r', 1440]] * N)[i]
        if side == 'l':
            tg = Image.new('RGBA', (700, 330), (0, 0, 0, 0)); td = ImageDraw.Draw(tg)
            td.polygon([(0, 0), (639, 0), (699, 165), (639, 329), (0, 329)], fill=org + (255,)); td.ellipse([619, 145, 659, 185], fill=(255, 252, 244))
            td.text((310, 55), PRE, font=F('PermanentMarker.ttf', 46), fill=(255, 255, 255), anchor='mm'); td.text((310, 140), CODE, font=F('ArchivoBlack-Regular.ttf', 82), fill=(40, 20, 0), anchor='mm')
            for k, l in enumerate(wrap(POST, F('PermanentMarker.ttf', 40), 560)): td.text((310, 222 + k * 50), l, font=F('PermanentMarker.ttf', 40), fill=(255, 255, 255), anchor='mm')
        tg = tg.rotate((6 if side == 'l' else -6) + 2 * math.sin(t * 3), expand=True, resample=Image.BICUBIC)
        img.alpha_composite(tg, (30 if side == 'l' else W - tg.width - 30, ty))
        (logo_move(img, i, t) if 'logo_path' in C else logo(img, 95, 105, 110)); disclaimer(img)
    elif TP == 'mummy':
        nv = (18, 26, 60); ye = (255, 205, 95)
        words = s['title'].upper().split(); f = F('RubikMono.ttf', 66); rows = []; cur = []
        for w in words:
            if cur and f.getbbox(' '.join(cur + [w]))[2] > W - 200: rows.append(' '.join(cur)); cur = []
            cur.append(w)
        rows.append(' '.join(cur))
        for k, r in enumerate(rows):
            tw = f.getbbox(r)[2] + 60; e = ease(u - k * 0.25); strip = Image.new('RGBA', (tw, 100), (0, 0, 0, 0)); sd = ImageDraw.Draw(strip)
            sd.rectangle([0, 0, tw - 1, 99], fill=(246, 240, 226, 250)); [sd.line([0, yy, tw, yy + 6], fill=(205, 195, 175), width=2) for yy in (18, 52, 80)]
            sd.text((tw / 2, 52), r, font=f, fill=nv, anchor='mm'); strip = strip.crop((0, 0, max(1, int(tw * e)), 100)).rotate((-2, 2, -1)[k % 3], expand=True, resample=Image.BICUBIC)
            img.alpha_composite(strip, (int(W / 2 - tw / 2), 150 + k * 112))
        if last:
            lay = Image.new('RGBA', (720, 300), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay); ld.rounded_rectangle([0, 0, 719, 299], 26, fill=ye + (250,))
            ld.text((360, 115), '$100', font=F('RubikMono.ttf', 140), fill=nv, anchor='mm'); ld.text((360, 240), 'COUPON BUNDLE', font=F('RubikMono.ttf', 50), fill=nv, anchor='mm')
            s2 = max(0.05, back(u)); lay = lay.resize((int(720 * s2), int(300 * s2))); img.alpha_composite(lay, (int(W / 2 - lay.width / 2), int(1250 - lay.height / 2)))
        d.rounded_rectangle([60, 1555, W - 60, 1775], 20, fill=nv + (235,), outline=ye, width=5)
        code_lines(d, W / 2, 1625, F('Nunito.ttf', 52), None, (255, 255, 255), ye, 76)
        logo(img, W - 100, 1450, 110); disclaimer(img)
# ---- rendu image par image
tmp = OUT + '_fr'; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
NF = int(DUR * FPS)
for n in range(NF):
    T = n / FPS; i = min(N - 1, int(T / SL)); t = T - i * SL
    img = bg(i, t)
    if i > 0 and t < TR: img = transition(bg(i - 1, SL + t), img, t / TR, T)
    deco(img, i, t)
    img.convert('RGB').save(f'{tmp}/f{n:05d}.jpg', quality=93)
# ---- son : musique + effet sonore à chaque transition
SR = 44100; mus = os.path.join(tmp, 'm.wav')
subprocess.run([sys.executable, '/home/user/skillora./temu/tools/popbeat.py', str(DUR), mus, str(C.get('music_seed', 1)), str(C.get('bpm', 110)), str(C.get('key', 57))], check=True, capture_output=True)
wm = wave.open(mus); m = np.frombuffer(wm.readframes(wm.getnframes()), '<i2').astype(float) / 32768; m = np.pad(m, (0, max(0, int(DUR * SR) - len(m))))[:int(DUR * SR)] * 0.55
sfx = {'vampire': 'whoosh', 'zombie': 'swish', 'witch': 'shine', 'neon': 'glitch', 'patch': 'whoosh', 'mummy': 'zoom1'}[TP]
ws = wave.open(SFX + sfx + '.wav'); s = np.frombuffer(ws.readframes(ws.getnframes()), '<i2').astype(float) / 32768
if ws.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
if ws.getframerate() != SR: s = np.interp(np.arange(0, len(s), ws.getframerate() / SR), np.arange(len(s)), s)
for k in range(1, N):
    a = int((k * SL - 0.05) * SR); L = min(len(s), len(m) - a); m[a:a + L] += s[:L] * 0.5
fade = int(0.6 * SR); m[-fade:] *= np.linspace(1, 0, fade); m = m / max(1e-6, np.abs(m).max()) * 0.9
wo = wave.open(os.path.join(tmp, 'a.wav'), 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((m * 32767).astype('<i2').tobytes()); wo.close()
subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/f%05d.jpg', '-i', os.path.join(tmp, 'a.wav'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
shutil.rmtree(tmp); print('ok', OUT, DUR)
