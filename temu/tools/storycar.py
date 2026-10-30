# Carrousel « histoire » façon créateur (pour passer le contrôle « non original » de Temu) : la photo en plein écran,
# UNE phrase naturelle différente par slide dans le style texte natif TikTok (boîte arrondie derrière chaque ligne),
# pas de « GIFT $0 » répété : le code n'apparaît que sur la dernière slide, dans une phrase. Emoji en couleur.
# Sorties : slide1.jpg … (mode photo TikTok) + diaporama .mp4 (fondus, sans musique : le son se met dans TikTok).
# usage : storycar.py config.json dossier_sortie
import json, sys, os, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
C = json.load(open(sys.argv[1])); OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True); D = os.path.dirname(os.path.abspath(sys.argv[1]))
W, H = 1080, 1920; FD = '/home/user/skillora./temu/fonts/'; FF = imageio_ffmpeg.get_ffmpeg_exe()
EMO = ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf', 109)
STYLE = C.get('style', 'white')    # white : boîte blanche, texte noir · dark : boîte noire, texte blanc · outline : texte blanc contour noir
FONT = ImageFont.truetype(FD + C.get('font', 'Poppins-ExtraBold.ttf'), C.get('size', 58))
def is_emoji(ch): return ord(ch) >= 0x2600
def emoji(ch, size):
    lay = Image.new('RGBA', (150, 150), (0, 0, 0, 0)); ImageDraw.Draw(lay).text((6, 6), ch, font=EMO, embedded_color=True)
    bb = lay.getbbox(); return lay.crop(bb).resize((size, size), Image.LANCZOS) if bb else None
def runs(line):   # découpe une ligne en morceaux texte / emoji
    out, cur = [], ''
    for ch in line:
        if is_emoji(ch) and ch not in '‍️':
            if cur: out.append(('t', cur)); cur = ''
            out.append(('e', ch))
        elif ch in '‍️': continue
        else: cur += ch
    if cur: out.append(('t', cur))
    return out
def width(line):
    es = int(FONT.size * 1.05); return sum(FONT.getlength(s) if k == 't' else es + 6 for k, s in runs(line))
def wrap(txt, maxw):
    lines, cur = [], ''
    for w in txt.split():
        t = (cur + ' ' + w).strip()
        if width(t) > maxw and cur: lines.append(cur); cur = w
        else: cur = t
    return lines + [cur]
def caption(im, txt, cy, style=STYLE, size=None):
    global FONT
    f0 = FONT
    if size: FONT = ImageFont.truetype(f0.path, size)
    d = ImageDraw.Draw(im); lines = []
    for part in txt.split('\n'): lines += wrap(part, W - 200)
    lh = int(FONT.size * 1.42); y = cy - lh * len(lines) / 2; es = int(FONT.size * 1.05)
    for ln in lines:
        w = width(ln); x = W / 2 - w / 2; pad = int(FONT.size * 0.36)
        if style in ('white', 'dark'):
            bg = (255, 255, 255, 245) if style == 'white' else (20, 20, 20, 225)
            d.rounded_rectangle([x - pad, y - pad * 0.55, x + w + pad, y + lh - pad * 0.55], int(FONT.size * 0.32), fill=bg)
        col = (15, 15, 15) if style == 'white' else (255, 255, 255)
        for k, s in runs(ln):
            if k == 't':
                d.text((x, y + lh * 0.42), s, font=FONT, fill=col, anchor='lm', **({'stroke_width': 6, 'stroke_fill': (0, 0, 0)} if style == 'outline' else {}))
                x += FONT.getlength(s)
            else:
                e = emoji(s, es)
                if e: im.alpha_composite(e, (int(x + 3), int(y + lh * 0.42 - es / 2)))
                x += es + 6
        y += lh
    FONT = f0
for k, s in enumerate(C['slides'], 1):
    im = Image.open(os.path.join(D, s['img'])).convert('RGB')
    r = max(W / im.width, H / im.height); im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
    im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H)).convert('RGBA')
    caption(im, s['text'], s.get('y', 330), s.get('style', STYLE))
    if s.get('code'):   # dernière slide : le code, dans une phrase, bien lisible
        caption(im, s['code'], s.get('code_y', s.get('y', 330) + 230), s.get('code_style', 'dark'), C.get('code_size', 52))
    im.convert('RGB').save(os.path.join(OUT, f'slide{k}.jpg'), quality=95); print('slide', k)
# diaporama : chaque slide reste SL s, fondu de 0,35 s
SL, TR, FPS = C.get('slide_dur', 2.6), 0.35, 30; n = len(C['slides'])
args = []
for k in range(1, n + 1): args += ['-loop', '1', '-t', str(SL + TR), '-i', os.path.join(OUT, f'slide{k}.jpg')]
fc = ''; last = '[0:v]'
for k in range(1, n):
    fc += f'{last}[{k}:v]xfade=transition=fade:duration={TR}:offset={round(k * SL, 3)}[v{k}];'; last = f'[v{k}]'
subprocess.run([FF, '-y', '-v', 'error'] + args + ['-filter_complex', fc + f'{last}format=yuv420p[o]', '-map', '[o]', '-r', str(FPS),
                '-c:v', 'libx264', '-crf', '18', '-movflags', '+faststart', os.path.join(OUT, C.get('video', 'carrousel.mp4'))], check=True)
print('ok', OUT)
