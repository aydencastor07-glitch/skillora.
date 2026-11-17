# Visages « qui parlent » pour les personnages en blocs : yeux (n normal, w grands, a fâchés, s inquiets, b fermés)
# × bouche (c fermée, m entrouverte, o grande ouverte, sm sourire, so sourire ouvert, f triste).
# Fabriqués à partir des visages d'origine (face_BK_*.png, 256 px) → face_BK_<yeux>_<bouche>.png en 512 px.
# usage : faces_talk.py DOSSIER_PERSOS
import sys, os
from PIL import Image, ImageDraw
D = sys.argv[1]; K = 4; S = 256 * K; INK = (28, 28, 28, 255)
def src(n): return Image.open(os.path.join(D, f'face_BK_{n}.png')).convert('RGBA').resize((S, S), Image.LANCZOS)
def crop(im, y0, y1):
    o = Image.new('RGBA', (S, S), (0, 0, 0, 0)); o.paste(im.crop((0, y0 * K, S, y1 * K)), (0, y0 * K)); return o
EYES = {'n': crop(src('neutral'), 0, 145), 'w': crop(src('shock'), 0, 145), 'a': crop(src('strain'), 0, 145)}
def sad():
    o = crop(src('neutral'), 88, 145); d = ImageDraw.Draw(o)
    d.line([(67 * K, 86 * K), (106 * K, 74 * K)], fill=INK, width=9 * K); d.line([(150 * K, 74 * K), (189 * K, 86 * K)], fill=INK, width=9 * K); return o
def blink():
    o = crop(src('neutral'), 0, 90); d = ImageDraw.Draw(o)
    for x in (75, 155): d.arc([x * K, 100 * K, (x + 26) * K, 124 * K], 20, 160, fill=INK, width=6 * K)
    return o
EYES['s'] = sad(); EYES['b'] = blink()
def mouth(k):
    o = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(o)
    if k == 'c': return crop(src('neutral'), 145, 256)
    if k == 'sm': return crop(src('smile'), 145, 256)
    if k == 'f': d.arc([104 * K, 168 * K, 152 * K, 196 * K], 200, 340, fill=INK, width=8 * K); return o
    if k == 'm': d.rounded_rectangle([110 * K, 162 * K, 146 * K, 184 * K], radius=10 * K, fill=INK); d.ellipse([118 * K, 174 * K, 138 * K, 184 * K], fill=(200, 60, 70, 255)); return o
    if k == 'o': d.ellipse([111 * K, 152 * K, 145 * K, 198 * K], fill=INK); d.ellipse([117 * K, 180 * K, 139 * K, 196 * K], fill=(200, 60, 70, 255)); return o
    if k == 'so': d.chord([104 * K, 146 * K, 152 * K, 192 * K], 0, 180, fill=INK); d.chord([114 * K, 168 * K, 142 * K, 190 * K], 0, 180, fill=(200, 60, 70, 255)); return o
for e, ei in EYES.items():
    for m in ('c', 'm', 'o', 'sm', 'so', 'f'):
        im = Image.alpha_composite(ei, mouth(m)).resize((512, 512), Image.LANCZOS); im.save(os.path.join(D, f'face_BK_{e}_{m}.png'))
print('ok')
