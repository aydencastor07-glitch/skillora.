# Carrousel TikTok (1080×1920) : une image + un seul message par slide, code bien lisible, petit logo Temu.
# usage : carousel.py config.json outdir
import json, sys, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
C = json.load(open(sys.argv[1])); OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True); D = os.path.dirname(os.path.abspath(sys.argv[1]))
W, H = 1080, 1920; FD = '/home/user/skillora./temu/fonts/'
EMO = ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf', 109)
LOGO = Image.open('/home/user/skillora./temu/temu_logo.png').convert('RGBA').resize((120, 120), Image.LANCZOS)
ACC = tuple(C.get('accent', (255, 122, 0))); DARK = tuple(C.get('dark', (28, 12, 40)))
def F(name, sz): return ImageFont.truetype(FD + name, sz)
def emoji(ch, size):
    lay = Image.new('RGBA', (140, 140), (0, 0, 0, 0)); ImageDraw.Draw(lay).text((6, 6), ch, font=EMO, embedded_color=True)
    return lay.crop(lay.getbbox()).resize((size, size), Image.LANCZOS)
def fit(txt, name, sz, maxw):
    f = F(name, sz)
    while f.getbbox(txt)[2] > maxw and sz > 30: sz -= 4; f = F(name, sz)
    return f
def wrap(txt, f, maxw):
    lines, cur = [], ''
    for w in txt.split():
        t = (cur + ' ' + w).strip()
        if f.getbbox(t)[2] > maxw and cur: lines.append(cur); cur = w
        else: cur = t
    return lines + [cur]
for k, s in enumerate(C['slides'], 1):
    im = Image.open(os.path.join(D, s['img'])).convert('RGB')
    r = max(W / im.width, H / im.height); im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
    im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H)).convert('RGBA')
    d = ImageDraw.Draw(im)
    # dégradé sombre derrière le texte (haut ou bas)
    pos = s.get('pos', 'top'); grad = Image.new('RGBA', (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(grad)
    for y in range(760):
        a = int(200 * (1 - y / 760) ** 1.4); yy = y if pos == 'top' else H - 1 - y
        gd.line([(0, yy), (W, yy)], fill=DARK + (a,))
    im.alpha_composite(grad)
    y0 = 190 if pos == 'top' else H - 800
    # titre
    tf = F(C.get('title_font', 'Bangers-Regular.ttf'), s.get('title_size', 120)); lines = wrap(s['title'], tf, W - 140)
    y = y0
    for ln in lines:
        d.text((W / 2 + 6, y + 8), ln, font=tf, fill=(0, 0, 0, 200), anchor='mt')
        d.text((W / 2, y), ln, font=tf, fill=tuple(s.get('title_color', (255, 255, 255))), anchor='mt', stroke_width=4, stroke_fill=(0, 0, 0))
        y += int(tf.size * 1.05)
    if s.get('emoji'):
        e = emoji(s['emoji'], 120); im.alpha_composite(e, (W // 2 - 60, y + 10)); y += 150
    # encadré du code
    if s.get('code'):
        y += 20; cf = F('Anton-Regular.ttf', 110); lab = F('Poppins-ExtraBold.ttf', 40); sub = F('Poppins-ExtraBold.ttf', 36)
        code = 'CODE: ' + s['code']; bw = cf.getbbox(code)[2] + 100; bh = 190
        x0 = (W - bw) // 2
        d.rounded_rectangle([x0 + 8, y + 10, x0 + bw + 8, y + bh + 10], 36, fill=(0, 0, 0, 160))
        d.rounded_rectangle([x0, y, x0 + bw, y + bh], 36, fill=ACC + (255,), outline=(255, 255, 255), width=6)
        d.text((W / 2, y + bh / 2 + 4), code, font=cf, fill=(255, 255, 255), anchor='mm', stroke_width=3, stroke_fill=(0, 0, 0))
        y += bh + 30
        for ln in wrap(s['sub'], sub, W - 160):
            d.text((W / 2, y), ln, font=sub, fill=(255, 255, 255), anchor='mt', stroke_width=5, stroke_fill=(0, 0, 0)); y += 50
    elif s.get('sub'):
        sub = F('Poppins-ExtraBold.ttf', 46); y += 10
        for ln in wrap(s['sub'], sub, W - 160):
            d.text((W / 2, y), ln, font=sub, fill=(255, 255, 255), anchor='mt', stroke_width=5, stroke_fill=(0, 0, 0)); y += 62
    if s.get('disclaimer'):
        df = F('Poppins-ExtraBold.ttf', 30); y += 20
        for ln in wrap(s['disclaimer'], df, W - 140):
            d.text((W / 2, y), ln, font=df, fill=(235, 235, 235), anchor='mt', stroke_width=4, stroke_fill=(0, 0, 0)); y += 40
    lx, ly = (W - 170, 70) if pos == 'bottom' else (W - 170, H - 230)
    im.alpha_composite(LOGO, (lx, ly))
    if s.get('swipe'):
        sf = F('Poppins-ExtraBold.ttf', 40); d.text((W / 2, H - 150), s['swipe'], font=sf, fill=(255, 255, 255), anchor='mm', stroke_width=5, stroke_fill=(0, 0, 0))
    im.convert('RGB').save(os.path.join(OUT, f'slide{k}.jpg'), quality=95); print('slide', k)
