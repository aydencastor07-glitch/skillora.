# Montage UGC Temu : coupe les silences (jump cuts + zoom), sous-titres mot à mot, badges animés,
# petit logo, code promo, effets sonores.  usage : montage.py config.json out.mp4
import json, sys, os, subprocess, wave, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
C = json.load(open(sys.argv[1])); OUT = sys.argv[2]; D = os.path.dirname(os.path.abspath(sys.argv[1]))
W, H, FPS, SR = 1080, 1920, 30, 44100
TMP = os.path.join(D, 'tmp'); os.makedirs(TMP, exist_ok=True)
FONT = '/home/user/skillora./motion/fonts/Montserrat.ttf'
def font(sz, wt=800, path=None):
    f = ImageFont.truetype(path or FONT, sz)
    if not path: f.set_variation_by_axes([wt])
    return f
FD = '/home/user/skillora./temu/fonts/'
# ---- 1. morceaux gardés (clip, début, fin, zoom) → base vidéo + nouvelle timeline des mots
parts = C['parts']; words = []; t = 0; flt = []; ins = []
for k, p in enumerate(parts):
    src = os.path.join(D, p['clip']); ins += ['-i', src]
    z = p.get('zoom', 1.0); cx = p.get('cx', 0.5); cy = p.get('cy', 0.45)
    flt.append(f"[{k}:v]trim={p['a']}:{p['b']},setpts=PTS-STARTPTS,scale={int(W*z)}:{int(H*z)},crop={W}:{H}:{int((W*z-W)*cx)}:{int((H*z-H)*cy)},fps={FPS},setsar=1[v{k}];"
               f"[{k}:a]atrim={p['a']}:{p['b']},asetpts=PTS-STARTPTS,aresample={SR},aformat=channel_layouts=mono[a{k}];")
    for w in C['words'][p['clip']]:
        if p['a'] - 0.05 <= w[1] < p['b']: words.append([w[0], t + w[1] - p['a'], t + min(w[2], p['b']) - p['a']])
    p['t'] = t; t += p['b'] - p['a']
DUR = t
flt.append(''.join(f'[v{k}][a{k}]' for k in range(len(parts))) + f'concat=n={len(parts)}:v=1:a=1[v][a]')
base = os.path.join(TMP, 'base.mp4')
subprocess.run([FF, '-y', '-loglevel', 'error'] + ins + ['-filter_complex', ''.join(flt), '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-crf', '14', '-preset', 'fast', '-c:a', 'pcm_s16le', base.replace('.mp4', '.mkv')], check=True)
base = base.replace('.mp4', '.mkv')
# ---- 2. image par image : on dessine les calques
fr = os.path.join(TMP, 'fr'); os.makedirs(fr, exist_ok=True)
for f in os.listdir(fr): os.remove(os.path.join(fr, f))
subprocess.run([FF, '-y', '-loglevel', 'error', '-i', base, '-q:v', '2', os.path.join(fr, 'f%05d.jpg')], check=True)
frames = sorted(os.listdir(fr))
ORANGE = (251, 119, 1); EV = []
ST = C.get('style', {}); ACC = tuple(ST.get('accent', ORANGE))
EMO = ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf', 109)
def emoji(ch, size):
    lay = Image.new('RGBA', (140, 140), (0, 0, 0, 0)); ImageDraw.Draw(lay).text((6, 6), ch, font=EMO, embedded_color=True)
    bb = lay.getbbox() or (0, 0, 1, 1); return lay.crop(bb).resize((size, size), Image.LANCZOS)
def card(img, txt, cx, cy, u, emo=None, out=1.0):
    # étiquette « carte » : fond sombre translucide, barre de couleur, émoji, arrive en glissant depuis la droite
    if u <= 0: return
    f = font(54, 800); tw = f.getbbox(txt)[2]; ew = 76 if emo else 0; w = tw + ew + 90; h = 112
    lay = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 26, fill=tuple(ST.get('card_bg', (20, 24, 38))) + (225,))
    d.rounded_rectangle([0, 0, 16, h - 1], 8, fill=ACC + (255,))
    if emo: lay.alpha_composite(emoji(emo, 62), (36, (h - 62) // 2))
    d.text((36 + ew, h / 2), txt, font=f, fill=(255, 255, 255), anchor='lm')
    e = ease(u * 1.2); x = cx - w / 2 + (1 - e) * (W - cx + w)
    if out < 1: lay.putalpha(lay.getchannel('A').point(lambda v: int(v * out)))
    img.alpha_composite(lay, (int(x), int(cy - h / 2)))
def ease(u): u = max(0, min(1, u)); return 1 - (1 - u) ** 3
def back(u): u = max(0, min(1, u)); c = 1.7; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2
def sticker(img, txt, cx, cy, u, bg=ORANGE, fg=(255, 255, 255), sz=64, rot=-4, icon=None):
    if u <= 0: return
    f = font(sz, 900); tw = f.getbbox(txt)[2]; pad = 34
    lay = Image.new('RGBA', (tw + 2 * pad + 20, sz + 2 * pad + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([10, 10, 10 + tw + 2 * pad, 10 + sz + 2 * pad - 10], 28, fill=bg + (255,), outline=(255, 255, 255, 255), width=5)
    d.text((10 + pad, 10 + pad - sz * 0.12), txt, font=f, fill=fg)
    s = 0.4 + 0.6 * back(u); lay = lay.rotate(rot, expand=True, resample=Image.BICUBIC)
    lay = lay.resize((max(1, int(lay.width * s)), max(1, int(lay.height * s))), Image.LANCZOS)
    sh = Image.new('RGBA', lay.size, (0, 0, 0, 0)); sh.putalpha(lay.getchannel('A').point(lambda v: v * 0.45)); sh = sh.filter(ImageFilter.GaussianBlur(10))
    img.alpha_composite(sh, (int(cx - lay.width / 2) + 8, int(cy - lay.height / 2) + 12)); img.alpha_composite(lay, (int(cx - lay.width / 2), int(cy - lay.height / 2)))
def stars(img, val, n_rev, cx, cy, u):
    if u <= 0: return
    a = ease(u); lay = Image.new('RGBA', (760, 250), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([0, 0, 759, 249], 40, fill=(255, 255, 255, 235))
    for i in range(5):
        x0, y0, R = 95 + i * 135, 95, 52; fill = min(1, max(0, (u * 1.6 - i * 0.18) / 0.3)) * (min(1, val - i) if val - i < 1 else 1)
        pts = [(x0 + R * (1 if j % 2 == 0 else 0.45) * math.sin(j * math.pi / 5), y0 - R * (1 if j % 2 == 0 else 0.45) * math.cos(j * math.pi / 5)) for j in range(10)]
        d.polygon(pts, fill=(225, 225, 225))
        if fill > 0:
            m = Image.new('L', lay.size, 0); ImageDraw.Draw(m).polygon(pts, fill=255)
            m2 = Image.new('L', lay.size, 0); ImageDraw.Draw(m2).rectangle([x0 - R, 0, x0 - R + 2 * R * fill, 250], fill=255)
            gold = Image.new('RGBA', lay.size, (255, 184, 0, 255)); gold.putalpha(Image.fromarray(np.minimum(np.asarray(m), np.asarray(m2)))); lay.alpha_composite(gold)
    f = font(56, 900); d.text((380, 200), f'{val}  ·  {n_rev} reviews', font=f, fill=(30, 30, 30), anchor='mm')
    s = 0.5 + 0.5 * back(u); lay = lay.resize((int(760 * s), int(250 * s)), Image.LANCZOS); lay.putalpha(lay.getchannel('A').point(lambda v: v * a))
    img.alpha_composite(lay, (int(cx - lay.width / 2), int(cy - lay.height / 2)))
LOGO = Image.open(C.get('logo', '/home/user/skillora./temu/temu_logo.png')).convert('RGBA').resize((110, 110), Image.LANCZOS)
def logo(img):
    lp = C.get('logo_pos', 'tl'); x = 48 if lp[1] == 'l' else W - 158; y = 150 if lp[0] == 't' else H - 330
    img.alpha_composite(LOGO, (x, y))
CODE_Y = C.get('code_y') or {'top': 0.2, 'middle': 0.56, 'bottom': 0.84}[C.get('code_pos', 'bottom')]
def codebar(img, u, big):
    # texte obligatoire du programme (exact), coupé en 2 lignes, + étiquette « MY CODE » qui pointe dessus
    if u <= 0: return
    full = C['code_text']; code = C['code']; i = full.index(code) + len(code)
    l1, l2 = full[:i].strip(), full[i:].strip()
    f1 = font(64, 900); f2 = font(44, 700)
    w = max(f1.getbbox(l1)[2], f2.getbbox(l2)[2]) + 80; h = 190
    lay = Image.new('RGBA', (w, h + 90), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    BX = tuple(ST.get('box_bg', (255, 255, 255))); TX = tuple(ST.get('box_fg', (30, 30, 30)))
    d.rounded_rectangle([0, 90, w - 1, 90 + h - 1], 32, fill=BX + (245,), outline=ACC + (255,), width=8)
    pre = l1[:l1.index(code)]; xx = w / 2 - f1.getbbox(l1)[2] / 2
    d.text((xx, 90 + 62), pre, font=f1, fill=TX, anchor='lm'); d.text((xx + f1.getbbox(pre)[2], 90 + 62), code, font=f1, fill=ACC, anchor='lm')
    d.text((w / 2, 90 + 140), l2, font=f2, fill=TX, anchor='mm')
    # étiquette « USE MY CODE » au-dessus de l'encadré
    tag = C.get('code_tag', 'USE MY CODE'); ft = font(40, 900); tw = ft.getbbox(tag)[2] + 50
    d.rounded_rectangle([w / 2 - tw / 2, 8, w / 2 + tw / 2, 74], 22, fill=ACC + (255,))
    d.polygon([(w / 2 - 18, 72), (w / 2 + 18, 72), (w / 2, 92)], fill=ACC + (255,))
    d.text((w / 2, 41), tag, font=ft, fill=(255, 255, 255), anchor='mm')
    s = (0.6 + 0.4 * back(u)) * ((C.get('code_big', 1.12) + 0.03 * math.sin(T * 6)) if big else C.get('code_small', 0.82))
    lay = lay.resize((int(lay.width * s), int(lay.height * s)), Image.LANCZOS)
    if lay.width > W - 50: r = (W - 50) / lay.width; lay = lay.resize((W - 50, int(lay.height * r)), Image.LANCZOS)
    img.alpha_composite(lay, (int(W / 2 - lay.width / 2), int(H * CODE_Y - lay.height / 2)))
def caption(img, T):
    if ST.get('caption') == 'pill': return caption_pill(img, T)
    if ST.get('caption') == 'pop': return caption_pop(img, T)
    return caption_stroke(img, T)
def caption_pill(img, T):
    # 3-4 mots en minuscules sur une bulle blanche, le mot dit est surligné (couleur d'accent)
    cur = [i for i, w in enumerate(words) if w[1] <= T + 0.05]
    if not cur: return
    i = cur[-1]
    if T > words[i][2] + 0.6: return
    n = 4; g0 = i - (i % n); grp = words[g0:g0 + n]; f = font(66, 800)
    txts = [w[0].replace('Timu', 'Temu') for w in grp]; ws = [f.getbbox(x)[2] for x in txts]; sp = 22; tot = sum(ws) + sp * (len(ws) - 1)
    if tot > W - 140: f = font(int(66 * (W - 140) / tot), 800); ws = [f.getbbox(x)[2] for x in txts]; tot = sum(ws) + sp * (len(ws) - 1)
    y = H * C.get('cap_y', 0.66); x0 = W / 2 - tot / 2; d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0 - 34, y - 62, x0 + tot + 34, y + 62], 40, fill=(255, 255, 255, 240))
    x = x0
    for k, (tx, wd) in enumerate(zip(txts, ws)):
        act = (g0 + k) == i; said = grp[k][1] <= T + 0.05
        if act: d.rounded_rectangle([x - 12, y - 46, x + wd + 12, y + 46], 18, fill=ACC + (255,))
        d.text((x, y), tx, font=f, fill=(255, 255, 255) if act else ((25, 25, 35) if said else (170, 170, 180)), anchor='lm')
        x += wd + sp
def caption_pop(img, T):
    # un seul mot à la fois, énorme, qui rebondit (police Anton), mots-clés en couleur
    cur = [i for i, w in enumerate(words) if w[1] <= T + 0.05]
    if not cur: return
    i = cur[-1]; w = words[i]
    if T > w[2] + 0.5: return
    tx = w[0].replace('Timu', 'Temu').upper().strip('.,!?')
    k = (T - w[1]) / 0.14; sc = 0.7 + 0.3 * back(k)
    f = font(int(150 * sc), path=FD + ST.get('cap_font', 'Anton-Regular.ttf'))
    if f.getbbox(tx)[2] > W - 120: f = font(int(150 * sc * (W - 120) / f.getbbox(tx)[2]), path=FD + ST.get('cap_font', 'Anton-Regular.ttf'))
    hot = any(h in tx for h in ST.get('hot', [])) or i % 4 == 0
    d = ImageDraw.Draw(img); y = H * C.get('cap_y', 0.66)
    d.text((W / 2 + 8, y + 10), tx, font=f, fill=(0, 0, 0), anchor='mm')
    d.text((W / 2, y), tx, font=f, fill=ACC if hot else (255, 255, 255), anchor='mm', stroke_width=7, stroke_fill=(0, 0, 0))
def bubble(img, txt, cx, cy, u, emo=None):
    # bulle de BD jaune, police Bangers, petite queue, apparaît en tournant
    if u <= 0: return
    f = font(70, path=FD + 'Bangers-Regular.ttf'); tw = f.getbbox(txt)[2]; ew = 84 if emo else 0; w = tw + ew + 80; h = 130
    lay = Image.new('RGBA', (w + 20, h + 60), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    bg = tuple(ST.get('bubble_bg', (255, 221, 0)))
    d.rounded_rectangle([4, 4, w + 4, h + 4], 60, fill=(0, 0, 0, 255)); d.rounded_rectangle([0, 0, w, h], 60, fill=bg + (255,), outline=(0, 0, 0), width=6)
    d.polygon([(w * 0.25, h - 4), (w * 0.25 + 50, h - 4), (w * 0.22, h + 50)], fill=bg + (255,), outline=(0, 0, 0))
    if emo: lay.alpha_composite(emoji(emo, 66), (34, (h - 66) // 2))
    d.text((34 + ew, h / 2 + 4), txt, font=f, fill=(0, 0, 0), anchor='lm')
    s2 = 0.3 + 0.7 * back(u); lay = lay.rotate((1 - ease(u)) * 25 - 3, expand=True, resample=Image.BICUBIC)
    lay = lay.resize((max(1, int(lay.width * s2)), max(1, int(lay.height * s2))), Image.LANCZOS)
    img.alpha_composite(lay, (int(cx - lay.width / 2), int(cy - lay.height / 2)))
PRODS = {}
def product(img, path, cx, cy, size, u, T, spin=0, card=None, label=None):
    # vrai produit détouré : arrive en grand avec contour blanc + ombre, flotte doucement
    if u <= 0: return
    if path not in PRODS:
        im = Image.open(os.path.join(D, path)).convert('RGBA'); a = im.getchannel('A')
        o = Image.new('RGBA', im.size, (255, 255, 255, 0)); o.putalpha(a.filter(ImageFilter.MaxFilter(15)))
        pad = Image.new('RGBA', im.size, (0, 0, 0, 0)); pad.alpha_composite(o); pad.alpha_composite(im); PRODS[path] = pad
    if card:   # carte blanche derrière (cache le produit déformé de la vidéo)
        cw, ch = card; k = 0.5 + 0.5 * back(u); cw, ch = int(cw * k), int(ch * k)
        cl = Image.new('RGBA', (cw + 40, ch + 40), (0, 0, 0, 0)); dc = ImageDraw.Draw(cl)
        dc.rounded_rectangle([20, 20, cw + 20, ch + 20], 44, fill=(0, 0, 0, 90)); cl = cl.filter(ImageFilter.GaussianBlur(12))
        ImageDraw.Draw(cl).rounded_rectangle([10, 10, cw + 10, ch + 10], 44, fill=(255, 255, 255, 250), outline=ACC + (255,), width=10)
        img.alpha_composite(cl, (int(cx - cw / 2 - 10), int(cy - ch / 2 - 10)))
        if label:
            f = font(56, path=FD + 'Bangers-Regular.ttf'); ImageDraw.Draw(img).text((cx, cy + ch / 2 - 60), label, font=f, fill=(20, 20, 20), anchor='mm')
    im = PRODS[path]; s2 = size * (0.4 + 0.6 * back(u)) / max(im.size)
    lay = im.resize((max(1, int(im.width * s2)), max(1, int(im.height * s2))), Image.LANCZOS).rotate(-T * 360 * spin if spin else 4 * math.sin(T * 2), expand=True, resample=Image.BICUBIC)
    sh = Image.new('RGBA', lay.size, (0, 0, 0, 0)); sh.putalpha(lay.getchannel('A').point(lambda v: v * 0.5)); sh = sh.filter(ImageFilter.GaussianBlur(18))
    y = cy + 12 * math.sin(T * 2.5)
    img.alpha_composite(sh, (int(cx - lay.width / 2) + 14, int(y - lay.height / 2) + 22)); img.alpha_composite(lay, (int(cx - lay.width / 2), int(y - lay.height / 2)))
def caption_stroke(img, T):
    # groupe de 2-3 mots en cours, mot actif en orange
    cur = [i for i, w in enumerate(words) if w[1] <= T + 0.05]
    if not cur: return
    i = cur[-1]
    if T > words[i][2] + 0.6: return
    g0 = i - (i % 3); grp = words[g0:g0 + 3]; f = font(84, 900)
    txts = [w[0].upper().replace('TIMU', 'TEMU') for w in grp]; ws = [f.getbbox(x)[2] for x in txts]; sp = 24; tot = sum(ws) + sp * (len(ws) - 1)
    if tot > W - 80: f = font(int(84 * (W - 80) / tot), 900); ws = [f.getbbox(x)[2] for x in txts]; tot = sum(ws) + sp * (len(ws) - 1)
    x = W / 2 - tot / 2; y = H * C.get('cap_y', 0.66); d = ImageDraw.Draw(img)
    for k, (tx, wd) in enumerate(zip(txts, ws)):
        if grp[k][1] > T + 0.05: break
        act = (g0 + k) == i; pop = 1 + 0.12 * max(0, 1 - (T - grp[k][1]) / 0.15) if act else 1
        ff = f if pop == 1 else font(int(f.size * pop), 900)
        d.text((x + wd / 2, y), tx, font=ff, fill=ORANGE if act else (255, 255, 255), anchor='mm', stroke_width=9, stroke_fill=(0, 0, 0))
        x += wd + sp
def at_word(key, n=0):
    m = [w for w in words if key.lower() in w[0].lower()]; return m[n][1] if len(m) > n else None
OV = []
for o in C['overlays']:
    t0 = at_word(o['word'], o.get('n', 0)) if 'word' in o else o['t']
    if t0 is None: print('mot introuvable', o); continue
    o = dict(o); o['t0'] = t0 + o.get('dt', 0); o['t1'] = o['t0'] + o.get('dur', 2.0); OV.append(o)
    EV.append((o['t0'], o.get('sfx', 'pop')))
for p in parts[1:]: EV.append((p['t'] - 0.02, ST.get('cut_sfx', 'cut1')))
code_big_t = at_word(C.get('code_word', 'code')) or DUR - 2.5
for k, fn in enumerate(frames):
    T = k / FPS; img = Image.open(os.path.join(fr, fn)).convert('RGBA')
    # petit flash blanc à chaque coupe
    for p in parts[1:]:
        dt = T - p['t']
        if ST.get('cut') == 'shake':
            if 0 <= dt < 0.2:
                k = 1 - dt / 0.2; ox, oy = int(28 * k * math.sin(dt * 90)), int(18 * k * math.cos(dt * 70))
                z = 1.06; cw, ch = int(W / z), int(H / z); x0, y0 = (W - cw) // 2 + ox, (H - ch) // 2 + oy
                img = img.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.BILINEAR)
        elif ST.get('cut') == 'zoom':
            if 0 <= dt < 0.22:
                z = 1 + 0.09 * (1 - ease(dt / 0.22)); cw, ch = int(W / z), int(H / z)
                img = img.crop(((W - cw) // 2, (H - ch) // 2, (W - cw) // 2 + cw, (H - ch) // 2 + ch)).resize((W, H), Image.BILINEAR)
        elif 0 <= dt < 0.12: fl = Image.new('RGBA', img.size, (255, 255, 255, int(120 * (1 - dt / 0.12)))); img.alpha_composite(fl)
    logo(img)
    if ST.get('bar'): ImageDraw.Draw(img).rectangle([0, 0, int(W * T / DUR), 12], fill=ACC + (255,))
    for o in OV:
        if not (o['t0'] <= T <= o['t1'] + 0.25): continue
        u = (T - o['t0']) / 0.35; out = 1 - max(0, (T - o['t1']) / 0.25)
        lay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        if o['type'] == 'stars': stars(lay, o['val'], o['reviews'], W / 2, H * o.get('y', 0.2), u)
        elif o['type'] == 'sticker' and ST.get('sticker') == 'bubble': bubble(lay, o['text'], W * o.get('x', 0.5), H * o.get('y', 0.25), u, o.get('emoji'))
        elif o['type'] == 'product': product(lay, o['img'], W * o.get('x', 0.5), H * o.get('y', 0.5), o.get('size', 600), u, T, o.get('spin', 0), o.get('card'), o.get('label'))
        elif o['type'] == 'sticker' and ST.get('sticker') == 'card': card(lay, o['text'], W * o.get('x', 0.5), H * o.get('y', 0.25), u, o.get('emoji'))
        elif o['type'] == 'sticker': sticker(lay, o['text'], W * o.get('x', 0.5), H * o.get('y', 0.25), u, rot=o.get('rot', -4), bg=tuple(o.get('bg', ORANGE)))
        elif o['type'] == 'arrow_up':
            yy = H * 0.1 - 30 * math.sin(T * 8); d = ImageDraw.Draw(lay); cx = W * o.get('x', 0.5)
            d.polygon([(cx, yy - 90), (cx - 70, yy), (cx - 25, yy), (cx - 25, yy + 80), (cx + 25, yy + 80), (cx + 25, yy), (cx + 70, yy)], fill=ORANGE, outline=(255, 255, 255), width=6)
            sticker(lay, o.get('text', 'LINK IN BIO'), min(cx, W - 230), yy + 170, u, rot=0)
        if out < 1: lay.putalpha(lay.getchannel('A').point(lambda v: int(v * out)))
        img.alpha_composite(lay)
    codebar(img, (T - min(code_big_t, 1.0)) / 0.4 if T < code_big_t else (T - code_big_t) / 0.4, T >= code_big_t)
    caption(img, T)
    img.convert('RGB').save(os.path.join(fr, fn), quality=92)
# ---- 3. son : voix + effets
w = wave.open(os.path.join(TMP, 'a.wav'), 'wb') if False else None
subprocess.run([FF, '-y', '-loglevel', 'error', '-i', base, '-vn', '-ac', '1', '-ar', str(SR), os.path.join(TMP, 'v.wav')], check=True)
wv = wave.open(os.path.join(TMP, 'v.wav')); v = np.frombuffer(wv.readframes(wv.getnframes()), '<i2').astype(float) / 32768
mix = v.copy()
SFX = '/home/user/skillora./motion/sfx/'
GAIN = {'pop': 0.35, 'ding': 0.3, 'cut1': 0.25, 'click': 0.3, 'shine': 0.3, 'tap': 0.3}
for t0, name in EV:
    p = SFX + name + '.wav'
    if not os.path.exists(p): continue
    ws = wave.open(p); s = np.frombuffer(ws.readframes(ws.getnframes()), '<i2').astype(float) / 32768
    if ws.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
    if ws.getframerate() != SR: s = np.interp(np.arange(0, len(s), ws.getframerate() / SR), np.arange(len(s)), s)
    i = int(max(0, t0) * SR); n = min(len(s), len(mix) - i)
    if n > 0: mix[i:i + n] += s[:n] * GAIN.get(name, 0.3)
if C.get('music'):
    wm = wave.open(os.path.join(D, C['music'])); m = np.frombuffer(wm.readframes(wm.getnframes()), '<i2').astype(float) / 32768
    m = np.pad(m, (0, max(0, len(mix) - len(m))))[:len(mix)]
    envv = np.convolve(np.abs(v) > 0.03, np.ones(int(0.3 * SR)) / int(0.3 * SR), 'same')
    mix += m * C.get('music_gain', 0.12) * (1 - 0.5 * np.clip(envv * 3, 0, 1))
mix = mix / max(1e-6, np.abs(mix).max()) * 0.95
wo = wave.open(os.path.join(TMP, 'mix.wav'), 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((mix * 32767).astype('<i2').tobytes()); wo.close()
subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', os.path.join(fr, 'f%05d.jpg'), '-i', os.path.join(TMP, 'mix.wav'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '19', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
print('ok', OUT, round(DUR, 2), 's')
