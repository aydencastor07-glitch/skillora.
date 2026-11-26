#!/usr/bin/env python3
"""Montage des vidéos cartoon (style low-poly, narration « you »).

Usage : python3 compose_cartoon.py <dossier_video>
Le dossier contient : images/01.jpg…, voix_complete.flac, mots_horodates.json, plans.json
plans.json = [{"img": "01.jpg", "t": 0.0, "crop": [x, y, w, h] (optionnel), "fx": "punch" (optionnel)}, ...]
Sous-titres : majuscules blanches contour noir, mot prononcé sur fond rouge, dans la zone centrale.
La vidéo s'arrête net 0,1 s après le dernier mot.
"""
import json, math, os, random, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
FONT = ImageFont.truetype('/usr/share/fonts/opentype/inter/InterDisplay-Black.otf', 76)
RED = (226, 24, 45)
SUB_Y = 1330          # centre vertical du bloc de sous-titres (zone centrale, au-dessus de l'interface TikTok)
CENSURE = {'FUCKING': 'F*CKING', 'FUCK': 'F*CK'}

d = sys.argv[1]
plans = json.load(open(os.path.join(d, 'plans.json')))
mots = [m for m in json.load(open(os.path.join(d, 'mots_horodates.json')))['words'] if m['type'] == 'word']
FIN = mots[-1]['end'] + 0.1
NF = int(math.ceil(FIN * FPS))

# ---------- sous-titres : groupes de 1 à 3 mots ----------
def propre(t):
    t = re.sub(r'["“”]', '', t).upper()
    nu = re.sub(r'[^A-Z*]', '', t)
    return t.replace(nu, CENSURE[nu]) if nu in CENSURE else t

groupes, cur = [], []
for m in mots:
    cur.append(m)
    fin_phrase = m['text'].rstrip('"”').endswith(('.', '!', '?'))
    virgule = m['text'].rstrip('"”').endswith(',')
    if fin_phrase or len(cur) == 3 or (virgule and len(cur) >= 2) or sum(len(x['text']) for x in cur) > 16:
        groupes.append(cur); cur = []
if cur: groupes.append(cur)
for i, g in enumerate(groupes):
    g_deb = g[0]['start']
    g_fin = groupes[i + 1][0]['start'] if i + 1 < len(groupes) else FIN
    for j, m in enumerate(g):
        m['hl_fin'] = g[j + 1]['start'] if j + 1 < len(g) else g_fin
    groupes[i] = (g_deb, g_fin, g)

def dessine_sous_titre(img, t):
    g = next((x for x in groupes if x[0] <= t < x[1]), None)
    if not g: return
    _, _, ms = g
    textes = [propre(m['text']) for m in ms]
    esp = FONT.getlength(' ')
    larg = [FONT.getlength(x) for x in textes]
    # 1 ou 2 lignes
    lignes = [list(range(len(ms)))]
    if sum(larg) + esp * (len(ms) - 1) > 900 and len(ms) > 1:
        coupe = max(1, len(ms) // 2)
        lignes = [list(range(coupe)), list(range(coupe, len(ms)))]
    dr = ImageDraw.Draw(img)
    hl = 92
    y0 = SUB_Y - hl * len(lignes) / 2
    for li, idx in enumerate(lignes):
        tot = sum(larg[k] for k in idx) + esp * (len(idx) - 1)
        x = (W - tot) / 2
        y = y0 + li * hl
        for k in idx:
            m = ms[k]
            if m['start'] <= t < m['hl_fin']:
                dr.rounded_rectangle([x - 12, y + 2, x + larg[k] + 12, y + 86], radius=10, fill=RED)
                dr.text((x, y), textes[k], font=FONT, fill='white')
            else:
                dr.text((x, y), textes[k], font=FONT, fill='white', stroke_width=7, stroke_fill='black')
            x += larg[k] + esp

# ---------- images ----------
cache = {}
def source(p):
    key = (p['img'], tuple(p.get('crop') or ()))
    if key not in cache:
        im = Image.open(os.path.join(d, 'images', p['img'])).convert('RGB')
        if p.get('crop'):
            x, y, w, h = p['crop']; im = im.crop((x, y, x + w, y + h))
        s = max(W / im.width, H / im.height)
        im = im.resize((round(im.width * s) + 2, round(im.height * s) + 2), Image.LANCZOS)
        cache[key] = im
    return cache[key]

for i, p in enumerate(plans):
    p['fin'] = plans[i + 1]['t'] if i + 1 < len(plans) else FIN

def image_a(t):
    i = max(k for k, p in enumerate(plans) if p['t'] <= t)
    p = plans[i]
    src = source(p)
    u = (t - p['t']) / max(0.01, p['fin'] - p['t'])
    if p.get('fx') == 'punch':           # coup de zoom + secousse (freinage)
        z = 1.18 - 0.12 * min(1, u * 3)
        r = random.Random(int(t * FPS))
        dx, dy = (r.uniform(-14, 14), r.uniform(-14, 14)) if u < 0.35 else (0, 0)
    else:                                # zoom lent, une fois avant / une fois arrière
        z = 1.0 + 0.07 * (u if i % 2 == 0 else 1 - u)
        dx = dy = 0
    cw, ch = W / z, H / z
    cx = src.width / 2 + dx; cy = src.height / 2 + dy
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    return src.resize((W, H), Image.BICUBIC, box=box)

sortie = os.path.join(d, 'video_finale.mp4')
cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
       '-i', os.path.join(d, 'voix_complete.flac'),
       '-filter:a', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-t', f'{FIN:.3f}',
       '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
       '-movflags', '+faststart', sortie]
pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
for f in range(NF):
    t = f / FPS
    im = image_a(t)
    dessine_sous_titre(im, t)
    pr.stdin.write(im.tobytes())
pr.stdin.close(); pr.wait()
print('OK', sortie, f'{FIN:.2f}s', len(groupes), 'groupes de sous-titres')
