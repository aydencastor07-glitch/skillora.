# Détourage fond vert (couleur du fond estimée sur les bords, marche pour tous les verts) + alignement optionnel.
# usage : keyset.py <src.jpg> <out.png> [--align ref.png]   (sortie 1075×1075 RGBA)
import sys
import numpy as np, cv2
from PIL import Image, ImageFilter
src, out = sys.argv[1:3]; S = 1075
im = Image.open(src).convert('RGB').resize((S, S), Image.LANCZOS)
a = np.asarray(im).astype(np.float32); r, g, b = a[..., 0], a[..., 1], a[..., 2]
green = g - np.maximum(r, b)
bd = np.concatenate([green[:20].ravel(), green[-20:].ravel(), green[:, :20].ravel(), green[:, -20:].ravel()])
G0 = max(30.0, float(np.median(bd)))                # « verdeur » du fond
alpha = 1 - np.clip((green - 0.30 * G0) / (0.45 * G0), 0, 1)
al = Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
alpha = np.asarray(al).astype(np.float32) / 255
g2 = np.minimum(g, np.maximum(r, b) + 8)            # enlève le reflet vert
o = np.dstack([r, g2, b, alpha * 255]).clip(0, 255).astype(np.uint8)
if '--align' in sys.argv:  # recale sur la réf. par les appuis au sol (bas de la silhouette : pieds, barres, chaise…)
    ref = np.asarray(Image.open(sys.argv[sys.argv.index('--align') + 1]).convert('RGBA'))
    def base(x):
        m = x[..., 3] > 128; ys = np.nonzero(m.any(1))[0]; y1 = ys.max(); band = m[int(y1 - 0.06 * (y1 - ys.min())):y1 + 1]
        xs = np.nonzero(band.any(0))[0]; return xs.min(), xs.max(), y1
    ax0, ax1, ay = base(ref); bx0, bx1, by = base(o)
    k = (ax1 - ax0) / max(1, bx1 - bx0); k = k if 0.6 < k < 1.6 else 1.0
    M = np.float32([[k, 0, ax0 - k * bx0], [0, k, ay - k * by]])
    print('échelle', round(k, 3), 'décalage', round(float(M[0, 2])), round(float(M[1, 2])))
    o = cv2.warpAffine(o, M, (S, S), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
Image.fromarray(o, 'RGBA').save(out); print('ok', out)
