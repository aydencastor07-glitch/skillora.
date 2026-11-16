# Style « ticket + étiquette 0€ » (6e style Temu, compte alr391702, public européen), avec VARIANTES par carrousel :
# photo plein écran nette avec zoom lent ; titre sur la 1re image puis nom de chaque trouvaille ; code toujours sur fond plein, en gros.
# Clés de variante (config) :
#   head  : hl (bandes surlignées) | box (carte blanche) | stroke (texte blanc contour noir) | tape (ruban adhésif)
#   chip  : pill | tab (onglet sombre à gauche) | stroke | note (post-it incliné)
#   tick  : stub (ticket à talon) | band (bandeau noir) | sticker (autocollant jaune incliné) | pill2 (deux pilules)
#   tag   : price (étiquette qui se balance) | burst (étoile) | circle (macaron) | none
#   trans : swipe | up | zoom | flash        final : mosaic | blur | polaroid        bars : true/false
# usage : posterv6.py config.json out.mp4  [PREVIEW=t1,t2]
import json, sys, os, math, subprocess, shutil, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
C = json.load(open(sys.argv[1])); OUT = sys.argv[2]; D = os.path.dirname(os.path.abspath(sys.argv[1]))
W, H, FPS = 1080, 1920, 30; SL = C.get('slide_dur', 2.5); SW = 0.3
FD = '/home/user/skillora./temu/fonts/'; SFX = '/home/user/skillora./motion/sfx/'
ACC = tuple(C.get('acc', [251, 119, 1])); HL = tuple(C.get('hl', [255, 222, 60])); INK = (18, 18, 18); WH = (255, 255, 255)
CF = 'Poppins-ExtraBold.ttf'; TF = C.get('font', 'ArchivoBlack-Regular.ttf')
HEAD, CHIP, TICK_K, TAG_K = C.get('head', 'hl'), C.get('chip', 'pill'), C.get('tick', 'stub'), C.get('tag', 'price')
TRANS, FINAL_K, BARS = C.get('trans', 'swipe'), C.get('final', 'mosaic'), C.get('bars', True)
TY = C.get('tick_y', 1530); HY = C.get('head_y', 380)
CODE = C['code']; LINE2 = C.get('line2', 'for Gifts at 0€ in TEMU app')
DISC = C.get('disclaimer', "*T&Cs apply. The purchase required is determined by the gift(s)' value.")
LOGO = Image.open('/home/user/skillora./temu/temu_logo.png').convert('RGBA')
_fc = {}
def F(name, sz):
    k = (name, int(sz))
    if k not in _fc: _fc[k] = ImageFont.truetype(FD + name, max(8, int(sz)))
    return _fc[k]
def fit(txt, name, sz, maxw):
    f = F(name, sz)
    while f.getbbox(txt)[2] > maxw and sz > 18: sz -= 2; f = F(name, sz)
    return f
def clamp(u): return max(0.0, min(1.0, u))
def ease(u): u = clamp(u); return 1 - (1 - u) ** 3
def inout(u): u = clamp(u); return u * u * (3 - 2 * u)
def back(u): u = clamp(u); c = 1.7; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2
def put(img, lay, cx, cy, s=1.0, rot=0.0):
    if s <= 0.02: return
    if s != 1.0: lay = lay.resize((max(1, int(lay.width * s)), max(1, int(lay.height * s))), Image.BILINEAR)
    if rot: lay = lay.rotate(rot, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(lay, (int(cx - lay.width / 2), int(cy - lay.height / 2)))
def shadowed(lay, blur=12, op=0.45, off=(0, 10)):
    pad = 34; o = Image.new('RGBA', (lay.width + 2 * pad, lay.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new('RGBA', lay.size, (0, 0, 0, 0)); sh.putalpha(lay.getchannel('A').point(lambda v: int(v * op)))
    o.alpha_composite(sh, (pad + off[0], pad + off[1])); o = o.filter(ImageFilter.GaussianBlur(blur)); o.alpha_composite(lay, (pad, pad)); return o
def wrap(txt, f, maxw):
    lines, cur = [], ''
    for w_ in txt.split(' '):
        if cur and f.getbbox(cur + ' ' + w_)[2] > maxw: lines.append(cur); cur = w_
        else: cur = (cur + ' ' + w_).strip()
    return lines + [cur]
# ---- photos plein écran, nettes
Z = 1.07
def prep(path, fy):
    im = Image.open(path).convert('RGB'); tw, th = int(W * Z), int(H * Z)
    s = max(tw / im.width, th / im.height); im = im.resize((int(im.width * s + 0.5), int(im.height * s + 0.5)), Image.LANCZOS)
    x0 = (im.width - tw) // 2; y0 = int((im.height - th) * fy); im = im.crop((x0, y0, x0 + tw, y0 + th))
    return im.filter(ImageFilter.UnsharpMask(radius=2, percent=90, threshold=2))
SLIDES = C['slides']; NS = len(SLIDES); N = NS + 1; DUR = N * SL
PH = [prep(os.path.join(D, s['img']), s.get('fy', 0.5)) for s in SLIDES]
def photo(i, t):
    z = Z - (Z - 1.0) * 0.85 * clamp(t / SL) if i % 2 == 0 else 1.0 + (Z - 1.0) * 0.85 * clamp(t / SL)
    P = PH[i]; cw, ch = min(P.width, W * Z / z), min(P.height, H * Z / z); ox, oy = (P.width - cw) / 2, (P.height - ch) / 2
    return P.resize((W, H), Image.BICUBIC, box=(ox, oy, ox + cw, oy + ch))
# ---- fond de la dernière image
def background():
    if FINAL_K == 'mosaic':
        m = Image.new('RGB', (W, H), (240, 236, 228)); g = 14; cw, ch = (W - 3 * g) // 2, (H - 3 * g) // 2
        for k in range(min(4, NS)):
            p = PH[k]; s = max(cw / p.width, ch / p.height); p = p.resize((int(p.width * s) + 1, int(p.height * s) + 1), Image.LANCZOS)
            x0 = (p.width - cw) // 2; y0 = (p.height - ch) // 2; m.paste(p.crop((x0, y0, x0 + cw, y0 + ch)), (g + (k % 2) * (cw + g), g + (k // 2) * (ch + g)))
        return Image.blend(m, Image.new('RGB', (W, H), (0, 0, 0)), 0.35)
    base = PH[0].resize((W, H)).filter(ImageFilter.GaussianBlur(18)); base = Image.blend(base, Image.new('RGB', (W, H), (0, 0, 0)), 0.45)
    if FINAL_K == 'polaroid':
        base = base.convert('RGBA')
        for k, (cx, cy, r) in enumerate([(300, 420, -8), (780, 470, 7), (290, 1500, 6), (790, 1460, -7)][:NS]):
            p = PH[k].resize((int(W * Z * 0.36), int(H * Z * 0.36)), Image.LANCZOS); p = p.crop((0, (p.height - 470) // 2, p.width, (p.height - 470) // 2 + 470))
            fr = Image.new('RGBA', (p.width + 36, p.height + 100), WH + (255,)); fr.paste(p, (18, 18)); put(base, shadowed(fr, 10, 0.5), cx, cy, 1.0, r)
        return base.convert('RGB')
    return base
BG = background()
# ---- bloc du code (toujours sur fond plein)
def tick():
    if TICK_K == 'band':
        w, h = W - 60, 300; lay = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        d.rounded_rectangle([0, 0, w - 1, h - 1], 26, fill=INK + (255,)); lay.alpha_composite(LOGO.resize((160, 160), Image.LANCZOS), (30, 30))
        cx = 210 + (w - 230) / 2; d.text((cx, 52), 'SEARCH CODE', font=F(CF, 42), fill=HL, anchor='mm')
        d.text((cx, 142), CODE, font=fit(CODE, CF, 124, w - 260), fill=WH, anchor='mm')
        d.rounded_rectangle([30, 214, w - 30, 276], 31, fill=HL + (255,)); d.text((w / 2, 245), LINE2, font=fit(LINE2, CF, 42, w - 120), fill=INK, anchor='mm')
        return shadowed(lay, 14, 0.5)
    if TICK_K == 'sticker':
        w, h = 900, 400; lay = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        d.rounded_rectangle([0, 0, w - 1, h - 1], 40, fill=HL + (255,))
        for x in range(30, w - 30, 30): d.line([(x, 18), (x + 14, 18)], fill=INK, width=4); d.line([(x, h - 18), (x + 14, h - 18)], fill=INK, width=4)
        lay.alpha_composite(LOGO.resize((120, 120), Image.LANCZOS), (40, 40)); d.text((190, 100), 'SEARCH CODE', font=F(CF, 56), fill=INK, anchor='lm')
        d.text((w / 2, 225), CODE, font=fit(CODE, CF, 150, w - 80), fill=INK, anchor='mm')
        d.rounded_rectangle([40, 300, w - 40, 368], 34, fill=WH + (255,)); d.text((w / 2, 334), LINE2, font=fit(LINE2, CF, 44, w - 130), fill=INK, anchor='mm')
        return shadowed(lay, 14, 0.5).rotate(-3, expand=True, resample=Image.BICUBIC)
    if TICK_K == 'pill2':
        w = 980; lay = Image.new('RGBA', (w, 330), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        d.rounded_rectangle([0, 0, w - 1, 200], 100, fill=WH + (255,)); lay.alpha_composite(LOGO.resize((150, 150), Image.LANCZOS), (28, 25))
        d.text((200, 62), 'Search code', font=F(CF, 46), fill=(100, 100, 100), anchor='lm'); d.text((200, 140), CODE, font=fit(CODE, CF, 112, w - 260), fill=INK, anchor='lm')
        d.rounded_rectangle([60, 224, w - 60, 320], 48, fill=ACC + (255,)); d.text((w / 2, 272), LINE2, font=fit(LINE2, CF, 50, w - 190), fill=WH, anchor='mm')
        return shadowed(lay, 14, 0.5)
    w, h = 980, 330; lay = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); st = 250   # stub
    d.rounded_rectangle([0, 0, w - 1, h - 1], 30, fill=WH + (255,))
    d.rounded_rectangle([0, 0, st, h - 1], 30, fill=ACC + (255,)); d.rectangle([st - 30, 0, st, h - 1], fill=ACC + (255,))
    lay.alpha_composite(LOGO.resize((170, 170), Image.LANCZOS), (st // 2 - 85, h // 2 - 85))
    for y in range(14, h - 10, 26): d.ellipse([st - 5, y, st + 5, y + 10], fill=(0, 0, 0, 0))
    for cy in (0, h): d.ellipse([st - 22, cy - 22, st + 22, cy + 22], fill=(0, 0, 0, 0))
    cx = st + (w - st) / 2; mw = w - st - 60
    d.text((cx, 62), 'SEARCH CODE', font=F(CF, 44), fill=(110, 110, 110), anchor='mm'); d.text((cx, 158), CODE, font=fit(CODE, CF, 128, mw), fill=INK, anchor='mm')
    d.rounded_rectangle([st + 30, 236, w - 30, 300], 32, fill=HL + (255,)); d.text((cx, 268), LINE2, font=fit(LINE2, CF, 40, mw - 30), fill=INK, anchor='mm')
    return shadowed(lay, 14, 0.5)
def big():
    w, h = 900, 690; lay = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    dark = TICK_K == 'band'; bg = INK if dark else (HL if TICK_K == 'sticker' else WH); fg = WH if dark else INK; strip = WH if TICK_K == 'sticker' else HL
    d.rounded_rectangle([0, 0, w - 1, h - 1], 40, fill=bg + (255,), outline=ACC + (255,), width=10)
    lay.alpha_composite(LOGO.resize((160, 160), Image.LANCZOS), (w // 2 - 80, 40))
    d.text((w / 2, 262), 'Search code', font=F(CF, 66), fill=fg, anchor='mm'); d.text((w / 2, 380), CODE, font=fit(CODE, CF, 158, w - 90), fill=fg, anchor='mm')
    d.rounded_rectangle([50, 470, w - 50, 640], 40, fill=strip + (255,))
    d.text((w / 2, 516), 'for Gifts at 0€', font=F(CF, 66), fill=INK, anchor='mm'); d.text((w / 2, 596), 'in TEMU app', font=F(CF, 66), fill=INK, anchor='mm')
    return shadowed(lay, 16, 0.5)
TICK = tick(); BIG = big()
def tag():
    if TAG_K == 'burst':
        r = 120; lay = Image.new('RGBA', (2 * r + 20, 2 * r + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); c = r + 10
        d.polygon([(c + (r if j % 2 == 0 else r * 0.8) * math.cos(j * math.pi / 14), c + (r if j % 2 == 0 else r * 0.8) * math.sin(j * math.pi / 14)) for j in range(28)], fill=ACC + (255,))
        d.text((c, c - 14), '0€', font=F(CF, 96), fill=WH, anchor='mm'); d.text((c, c + 52), 'GIFTS', font=F(CF, 34), fill=WH, anchor='mm')
        return shadowed(lay, 8, 0.4, (0, 6))
    if TAG_K == 'circle':
        r = 115; lay = Image.new('RGBA', (2 * r + 10, 2 * r + 10), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); c = r + 5
        d.ellipse([5, 5, 2 * r + 5, 2 * r + 5], fill=WH + (255,), outline=ACC + (255,), width=14)
        d.text((c, c - 14), '0€', font=F(CF, 100), fill=ACC, anchor='mm'); d.text((c, c + 54), 'GIFTS', font=F(CF, 34), fill=INK, anchor='mm')
        return shadowed(lay, 8, 0.4, (0, 6))
    w, h = 210, 250; lay = Image.new('RGBA', (w, h + 90), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.line([(w / 2, 0), (w / 2, 92)], fill=(40, 40, 40, 255), width=4)
    d.polygon([(w / 2, 80), (w, 140), (w, 90 + h), (0, 90 + h), (0, 140)], fill=HL + (255,))
    d.rounded_rectangle([0, 130, w - 1, 90 + h - 1], 22, fill=HL + (255,)); d.ellipse([w / 2 - 14, 104, w / 2 + 14, 132], fill=(0, 0, 0, 0))
    d.text((w / 2, 225), '0€', font=F(CF, 104), fill=INK, anchor='mm'); d.text((w / 2, 300), 'GIFTS', font=F(CF, 40), fill=INK, anchor='mm')
    return shadowed(lay, 8, 0.4, (4, 8))
TAG = tag() if TAG_K != 'none' else None
def bars(img, T):
    d = ImageDraw.Draw(img); x0, x1, y = 70, W - 70, 236; g = 12; w = (x1 - x0 - g * (N - 1)) / N
    for k in range(N):
        a = x0 + k * (w + g); f = clamp((T - k * SL) / SL)
        d.rounded_rectangle([a, y, a + w, y + 10], 5, fill=(255, 255, 255, 110))
        if f > 0: d.rounded_rectangle([a, y, a + max(10, w * f), y + 10], 5, fill=(255, 255, 255, 255))
# ---- titre (1re image)
def headline(img, txt, t):
    if HEAD == 'box':
        k = back((t - 0.1) / 0.4)
        if k <= 0.02: return
        f = F(TF, 86); lines = wrap(txt, f, W - 240); lh = 104; w = max(f.getbbox(l)[2] for l in lines) + 100; h = lh * len(lines) + 70
        lay = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); d.rounded_rectangle([0, 0, w - 1, h - 1], 28, fill=WH + (255,))
        d.rectangle([50, h - 26, w - 50, h - 16], fill=ACC + (255,))
        for j, l in enumerate(lines): d.text((w / 2, 30 + lh * j + lh / 2), l, font=f, fill=INK, anchor='mm')
        put(img, shadowed(lay, 10, 0.4), W / 2, HY + h / 2 - 60, k); return
    if HEAD == 'stroke':
        f = F(TF, 104); lines = wrap(txt, f, W - 140); d = ImageDraw.Draw(img)
        for j, l in enumerate(lines):
            k = ease((t - 0.1 - 0.12 * j) / 0.3); a = int(255 * k)
            if a: d.text((W / 2, HY + j * 118 - 20 * (1 - k)), l, font=fit(l, TF, 104, W - 120), fill=WH + (a,), anchor='mm', stroke_width=10, stroke_fill=(0, 0, 0, a))
        return
    if HEAD == 'tape':
        f = F(TF, 76); lines = wrap(txt, f, W - 240)
        for j, l in enumerate(lines):
            k = back((t - 0.1 - 0.15 * j) / 0.35)
            if k <= 0.02: continue
            fl = fit(l, TF, 76, W - 220); tw = fl.getbbox(l)[2]; w, h = tw + 90, 120
            lay = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
            top = [(x, 6 + (x // 18 % 2) * 6) for x in range(0, w, 18)]; bot = [(x, h - 6 - (x // 18 % 2) * 6) for x in range(w - 1, 0, -18)]
            d.polygon(top + [(w, 6), (w - 8, h / 2), (w, h - 6)] + bot + [(0, h - 6), (8, h / 2)], fill=(242, 232, 205, 250))
            d.text((w / 2, h / 2 + 4), l, font=fl, fill=INK, anchor='mm')
            put(img, shadowed(lay, 6, 0.35, (0, 5)), W / 2, HY + j * 128, k, (-3, 2, -1)[j % 3])
        return
    f = F(TF, 84); lines = wrap(txt, f, W - 200)   # hl
    for j, l in enumerate(lines):
        k = ease((t - 0.1 - 0.12 * j) / 0.3)
        if k <= 0: continue
        fl = fit(l, TF, 84, W - 200); tw = fl.getbbox(l)[2]; lay = Image.new('RGBA', (tw + 60, 130), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        d.rectangle([0, 10, (tw + 60) * k, 120], fill=HL + (255,)); d.text((30, 66), l, font=fl, fill=INK + (int(255 * k),), anchor='lm')
        put(img, shadowed(lay, 8, 0.35, (0, 6)), W / 2, HY + j * 122, 1.0, -2 + (j % 2) * 1.5)
# ---- nom de la trouvaille (images suivantes)
def chip(img, num, txt, t):
    k = back((t - 0.15) / 0.35)
    if k <= 0.02: return
    if CHIP == 'tab':
        f = fit(txt, CF, 56, W - 330); tw = f.getbbox(txt)[2]; w, h = tw + 190, 116
        lay = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); d.rounded_rectangle([0, 0, w - 1, h - 1], 20, fill=INK + (235,))
        d.rounded_rectangle([14, 14, 102, 102], 16, fill=ACC + (255,)); d.text((58, 60), str(num), font=F(CF, 56), fill=WH, anchor='mm'); d.text((126, 60), txt, font=f, fill=WH, anchor='lm')
        lay = shadowed(lay, 10, 0.4, (0, 6)); put(img, lay, 40 + lay.width / 2 - (1 - min(1, k)) * 300, HY); return
    if CHIP == 'stroke':
        d = ImageDraw.Draw(img); s = f'{num}. {txt}'; f = fit(s, TF, 80, W - 120); a = int(255 * clamp(k))
        d.text((W / 2, HY), s, font=f, fill=WH + (a,), anchor='mm', stroke_width=9, stroke_fill=(0, 0, 0, a)); return
    if CHIP == 'note':
        f = F(CF, 50); lines = wrap(txt, f, 470); w, h = 560, 150 + 62 * len(lines)
        lay = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); d.rectangle([0, 0, w - 1, h - 1], fill=HL + (255,))
        d.rectangle([w / 2 - 80, 0, w / 2 + 80, 26], fill=(255, 255, 255, 170)); d.text((40, 72), f'#{num}', font=F(CF, 60), fill=ACC, anchor='lm')
        for j, l in enumerate(lines): d.text((40, 140 + 62 * j), l, font=f, fill=INK, anchor='lm')
        lay = shadowed(lay, 10, 0.45, (4, 8)); put(img, lay, W - 30 - lay.width / 2, HY + 60, k, 4); return
    f = fit(txt, CF, 54, W - 300); tw = f.getbbox(txt)[2]; w, h = tw + 170, 110   # pill
    lay = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 55, fill=WH + (255,)); d.ellipse([12, 12, 98, 98], fill=ACC + (255,))
    d.text((55, 57), str(num), font=F(CF, 52), fill=WH, anchor='mm'); d.text((122, 58), txt, font=f, fill=INK, anchor='lm')
    put(img, shadowed(lay, 10, 0.4, (0, 6)), W / 2, HY, k)
def slide(i, t):
    global HY
    img = photo(i, t).convert('RGBA'); HY = SLIDES[i].get('hy', C.get('head_y', 380))
    if i == 0: headline(img, C['title'], t)
    else: chip(img, i, SLIDES[i].get('item', ''), t)
    return img
def frame(T):
    k = min(N - 1, int(T / SL)); t = T - k * SL
    img = slide(k, t) if k < NS else BG.copy().convert('RGBA')
    if k > 0 and t < SW:
        u = inout(t / SW); prev = slide(k - 1, SL); out = Image.new('RGBA', (W, H))
        if TRANS == 'swipe': out.alpha_composite(prev, (int(-W * u), 0)); out.alpha_composite(img, (int(W * (1 - u)), 0)); img = out
        elif TRANS == 'up': out.alpha_composite(prev, (0, int(-H * u))); out.alpha_composite(img, (0, int(H * (1 - u)))); img = out
        elif TRANS == 'zoom':
            s = 1.25 - 0.25 * u; z = img.resize((int(W * s), int(H * s)), Image.BILINEAR); x0, y0 = (z.width - W) // 2, (z.height - H) // 2
            img = z.crop((x0, y0, x0 + W, y0 + H)); img.alpha_composite(Image.new('RGBA', (W, H), (255, 255, 255, int(200 * (1 - u)))))
        else:
            img.alpha_composite(Image.new('RGBA', (W, H), (255, 255, 255, int(255 * (1 - u) ** 2))))
            sh = int(14 * (1 - u)) * (1 if int(t * 60) % 2 else -1); img = img.transform(img.size, Image.AFFINE, (1, 0, sh, 0, 1, 0))
    if BARS: bars(img, T)
    if k < NS:
        ts = SLIDES[k].get('ts', 1.0); ty = SLIDES[k].get('ty', TY) + 6 * math.sin(T * 4); put(img, TICK, W / 2, ty, ts)
        if TAG is not None:
            ta = back((T - 0.35) / 0.4)
            if TAG_K == 'price': put(img, TAG, 905, ty - 300 * ts, ta * ts ** 0.5, 8 * math.sin(T * 2.6))
            elif TAG_K == 'circle': put(img, TAG, 905, ty - 290 * ts, ta * ts ** 0.5, 10 * math.sin(T * 2))
            else: put(img, TAG, 905, ty - 285 * ts, ts ** 0.5 * ta * (1 + 0.04 * math.sin(T * 8)), -12)
    else: put(img, BIG, W / 2, H * 0.48, back(t / 0.45))
    dy = 1745 if k >= NS or SLIDES[k].get('ty', TY) < 1600 else SLIDES[k]['ty'] + (TICK.height - 60) * SLIDES[k].get('ts', 1.0) / 2 + 14
    d = ImageDraw.Draw(img); f = fit(DISC, 'Nunito.ttf', 26, W - 120)
    d.text((W / 2, dy), DISC, font=f, fill=(255, 255, 255), anchor='mm', stroke_width=3, stroke_fill=(0, 0, 0))
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
    tsfx = {'swipe': 'swish', 'up': 'whoosh', 'zoom': 'zoom1', 'flash': 'snap'}[TRANS]
    for k in range(N):
        if k: sfx(tsfx, k * SL - 0.05, 0.4)
        sfx('pop' if k < NS else 'ding', k * SL + 0.2, 0.22)
    fd = int(0.6 * SR); m[-fd:] *= np.linspace(1, 0, fd); m = m / max(1e-6, np.abs(m).max()) * 0.9
    wo = wave.open(os.path.join(tmp, 'a.wav'), 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((m * 32767).astype('<i2').tobytes()); wo.close()
    subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/f%05d.jpg', '-i', os.path.join(tmp, 'a.wav'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
    shutil.rmtree(tmp); print('ok', OUT, DUR)
