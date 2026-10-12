# Détourage fond vert -> PNG transparent (bords doux + suppression du reflet vert).
import sys
import numpy as np
from PIL import Image, ImageFilter
src, out = sys.argv[1:3]
scale = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
im = Image.open(src).convert('RGB')
if scale != 1: im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
a = np.asarray(im).astype(np.float32)
r, g, b = a[..., 0], a[..., 1], a[..., 2]
green = g - np.maximum(r, b)                      # « verdeur »
alpha = 1 - np.clip((green - 25) / 60, 0, 1)
al = Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
alpha = np.asarray(al).astype(np.float32) / 255
g2 = np.minimum(g, np.maximum(r, b) + 8)          # enlève le reflet vert sur les bords
o = np.dstack([r, g2, b, alpha * 255]).clip(0, 255).astype(np.uint8)
img = Image.fromarray(o, 'RGBA')
img.save(out); print('ok', out, img.size)
