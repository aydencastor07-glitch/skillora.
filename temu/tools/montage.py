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
def font(sz, wt=800):
    f = ImageFont.truetype(FONT, sz); f.set_variation_by_axes([wt]); return f
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
    x = 48 if C.get('logo_pos', 'tl') == 'tl' else W - 158
    img.alpha_composite(LOGO, (x, 150))
CODE_Y = {'top': 0.2, 'middle': 0.56, 'bottom': 0.84}[C.get('code_pos', 'bottom')]
def codebar(img, u, big):
    # texte obligatoire du programme (exact), coupé en 2 lignes, + étiquette « MY CODE » qui pointe dessus
    if u <= 0: return
    full = C['code_text']; code = C['code']; i = full.index(code) + len(code)
    l1, l2 = full[:i].strip(), full[i:].strip()
    f1 = font(64, 900); f2 = font(44, 700)
    w = max(f1.getbbox(l1)[2], f2.getbbox(l2)[2]) + 80; h = 190
    lay = Image.new('RGBA', (w, h + 90), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([0, 90, w - 1, 90 + h - 1], 32, fill=(255, 255, 255, 245), outline=ORANGE + (255,), width=8)
    pre = l1[:l1.index(code)]; xx = w / 2 - f1.getbbox(l1)[2] / 2
    d.text((xx, 90 + 62), pre, font=f1, fill=(30, 30, 30), anchor='lm'); d.text((xx + f1.getbbox(pre)[2], 90 + 62), code, font=f1, fill=ORANGE, anchor='lm')
    d.text((w / 2, 90 + 140), l2, font=f2, fill=(50, 50, 50), anchor='mm')
    # étiquette « USE MY CODE » au-dessus de l'encadré
    tag = C.get('code_tag', 'USE MY CODE'); ft = font(40, 900); tw = ft.getbbox(tag)[2] + 50
    d.rounded_rectangle([w / 2 - tw / 2, 8, w / 2 + tw / 2, 74], 22, fill=ORANGE + (255,))
    d.polygon([(w / 2 - 18, 72), (w / 2 + 18, 72), (w / 2, 92)], fill=ORANGE + (255,))
    d.text((w / 2, 41), tag, font=ft, fill=(255, 255, 255), anchor='mm')
    s = (0.6 + 0.4 * back(u)) * ((1.12 + 0.03 * math.sin(T * 6)) if big else 0.82)
    lay = lay.resize((int(lay.width * s), int(lay.height * s)), Image.LANCZOS)
    if lay.width > W - 50: r = (W - 50) / lay.width; lay = lay.resize((W - 50, int(lay.height * r)), Image.LANCZOS)
    img.alpha_composite(lay, (int(W / 2 - lay.width / 2), int(H * CODE_Y - lay.height / 2)))
def caption(img, T):
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
for p in parts[1:]: EV.append((p['t'] - 0.02, 'cut1'))
code_big_t = at_word(C.get('code_word', 'code')) or DUR - 2.5
for k, fn in enumerate(frames):
    T = k / FPS; img = Image.open(os.path.join(fr, fn)).convert('RGBA')
    # petit flash blanc à chaque coupe
    for p in parts[1:]:
        dt = T - p['t']
        if 0 <= dt < 0.12: fl = Image.new('RGBA', img.size, (255, 255, 255, int(120 * (1 - dt / 0.12)))); img.alpha_composite(fl)
    logo(img)
    for o in OV:
        if not (o['t0'] <= T <= o['t1'] + 0.25): continue
        u = (T - o['t0']) / 0.35; out = 1 - max(0, (T - o['t1']) / 0.25)
        lay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        if o['type'] == 'stars': stars(lay, o['val'], o['reviews'], W / 2, H * o.get('y', 0.2), u)
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
mix = mix / max(1e-6, np.abs(mix).max()) * 0.95
wo = wave.open(os.path.join(TMP, 'mix.wav'), 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((mix * 32767).astype('<i2').tobytes()); wo.close()
subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', os.path.join(fr, 'f%05d.jpg'), '-i', os.path.join(TMP, 'mix.wav'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '19', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
print('ok', OUT, round(DUR, 2), 's')
