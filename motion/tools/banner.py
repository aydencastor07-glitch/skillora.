# Bannière YouTube 2560×1440 : personnage à droite, cadre rouge qui passe DERRIÈRE lui,
# texte dans la zone visible partout (1546×423 au centre).
# usage : banner.py <personnage.png fond noir> <sortie.jpg> "<NOM>" "<slogan>" "<ligne 3>"
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy import ndimage
src, out, name, tag, sub = sys.argv[1:6]
FONT = __file__.replace('tools/banner.py', 'fonts/Montserrat.ttf')
W, H = 2560, 1440; SX, SY, SW, SH = (W - 1546) // 2, (H - 423) // 2, 1546, 423
img = Image.new('RGB', (W, H), 'black')
# cadre rouge (dessiné avant le personnage → il passe derrière)
ImageDraw.Draw(img).rectangle((SX, SY, SX + SW, SY + SH), outline=(230, 20, 30), width=5)
ch = Image.open(src).convert('RGB'); s = 1500 / ch.height
ch = ch.resize((int(ch.width * s), 1500), Image.LANCZOS)
# détourage : tout ce qui n'est pas noir + trous bouchés (cheveux sombres) + petite marge
a = np.asarray(ch).max(2) > 18
a = ndimage.binary_closing(a, iterations=6); a = ndimage.binary_fill_holes(a)
mask = Image.fromarray((a * 255).astype('uint8')).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(2))
img.paste(ch, (SX + SW - ch.width // 2 - 40, SY - 150), mask)
def font(sz, wt): f = ImageFont.truetype(FONT, sz); f.set_variation_by_axes([wt]); return f
def italic_text(txt, sz, wt, fill, x, y, maxw=1000):  # texte penché, réduit s'il est trop large
    while font(sz, wt).getlength(txt) > maxw: sz -= 2
    f = font(sz, wt); bb = f.getbbox(txt); tw, th = bb[2] + 40, bb[3] + 20
    lay = Image.new('L', (tw + th // 4, th)); ImageDraw.Draw(lay).text((th // 4, 0), txt, font=f, fill=255)
    lay = lay.transform(lay.size, Image.AFFINE, (1, 0.2, -th * 0.1, 0, 1, 0), Image.BICUBIC)
    img.paste(Image.new('RGB', lay.size, fill), (x, y), lay); return th
x, y = SX + 30, SY + 40
y += italic_text(name, 170, 850, (255, 255, 255), x, y) + 5
ImageDraw.Draw(img).rectangle((x + 8, y, x + 230, y + 8), fill=(255, 210, 63)); y += 30
y += italic_text(tag, 64, 700, (255, 210, 63), x, y) + 10
italic_text(sub, 40, 500, (170, 170, 170), x, y)
img.save(out, quality=92); print('ok', out)
