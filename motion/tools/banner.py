# Bannière YouTube 2560×1440 : personnage à droite, texte dans la zone visible partout (1546×423 au centre).
# usage : banner.py <personnage.png> <sortie.jpg> "<NOM>" "<slogan>" "<ligne 3>" [--guide]
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
src, out, name, tag, sub = sys.argv[1:6]
FONT = __file__.replace('tools/banner.py', 'fonts/Montserrat.ttf')
W, H = 2560, 1440; SX, SY, SW, SH = (W - 1546) // 2, (H - 423) // 2, 1546, 423
img = Image.new('RGB', (W, H), 'black')
ch = Image.open(src).convert('RGB'); s = 1250 / ch.height
ch = ch.resize((int(ch.width * s), 1250), Image.LANCZOS)
cx = SX + SW - ch.width // 2 - 60      # personnage collé à droite de la zone sûre
img.paste(ch, (cx, SY - 110))           # tête + torse dans la bande visible sur téléphone
def font(sz, wt): f = ImageFont.truetype(FONT, sz); f.set_variation_by_axes([wt]); return f
def italic_text(txt, sz, wt, fill, x, y):  # texte penché comme dans les vidéos
    f = font(sz, wt); bb = f.getbbox(txt); tw, th = bb[2] + 40, bb[3] + 20
    lay = Image.new('L', (tw + th // 4, th)); ImageDraw.Draw(lay).text((th // 4, 0), txt, font=f, fill=255)
    lay = lay.transform(lay.size, Image.AFFINE, (1, 0.2, -th * 0.1, 0, 1, 0), Image.BICUBIC)
    img.paste(Image.new('RGB', lay.size, fill), (x, y), lay); return th
x, y = SX + 30, SY + 45
y += italic_text(name, 140, 850, (255, 255, 255), x, y) + 5
d = ImageDraw.Draw(img); d.rectangle((x + 8, y, x + 230, y + 8), fill=(255, 210, 63)); y += 26
y += italic_text(tag, 52, 700, (255, 210, 63), x, y) + 10
italic_text(sub, 34, 500, (170, 170, 170), x, y)
if '--guide' in sys.argv: ImageDraw.Draw(img).rectangle((SX, SY, SX + SW, SY + SH), outline=(255, 0, 0), width=4)
img.save(out, quality=92); print('ok', out)
