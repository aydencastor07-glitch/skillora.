# Colle le vrai logo TEMU sur les étiquettes blanches des boîtes orange d'une photo générée :
# repère chaque étiquette (zone blanche presque rectangulaire entourée d'orange), prend ses 4 coins, et y déforme le logo
# (perspective) avec une petite marge blanche, comme un autocollant.  usage : logo_box.py entrée.jpg sortie.jpg
import sys
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
from scipy import ndimage
LOGO = Image.open('/home/user/skillora./temu/temu_logo.png').convert('RGBA')
def coeffs(dst, src):
    # coefficients de Image.transform(PERSPECTIVE) qui envoient les points src (logo) sur dst (photo)
    A = []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    return np.linalg.solve(np.array(A, float), np.array([c for p in src for c in p], float))
def labels(im):
    a = np.asarray(im.convert('RGB')).astype(int); r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = np.max(a, 2), np.min(a, 2); white = (mx > 150) & ((mx - mn) / np.maximum(mx, 1) < 0.3)   # clair et peu coloré (la lumière teinte l'étiquette)
    orange = (r > 165) & (g > 55) & (g < 195) & (b < 135) & (r - b > 80)
    lab, n = ndimage.label(ndimage.binary_opening(white, iterations=2)); out = []
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k); area = len(xs)
        if area < 0.0012 * a.shape[0] * a.shape[1]: continue
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max(); fill = area / ((x1 - x0 + 1) * (y1 - y0 + 1))
        if fill < 0.75 or not 0.45 < (x1 - x0 + 1) / (y1 - y0 + 1) < 2.6: continue   # étiquette : à peu près carrée ou rectangulaire, pas une bande
        if x0 <= 2 or y0 <= 2 or x1 >= a.shape[1] - 3 or y1 >= a.shape[0] - 3 or area > 0.05 * a.shape[0] * a.shape[1]: continue   # fenêtres, murs : pas des étiquettes
        m = max(8, int(0.15 * (x1 - x0))); big = orange[max(0, y0 - m):y1 + m, max(0, x0 - m):x1 + m]; inner = orange[y0:y1 + 1, x0:x1 + 1]
        ring = (big.sum() - inner.sum()) / max(1, big.size - inner.size)   # bord autour de l'étiquette : surtout orange
        if ring < 0.25: continue
        s, d = xs + ys, xs - ys
        out.append([(xs[s.argmin()], ys[s.argmin()]), (xs[d.argmax()], ys[d.argmax()]), (xs[s.argmax()], ys[s.argmax()]), (xs[d.argmin()], ys[d.argmin()])])
    return out
def paste(im, quads, inset=0.12):
    im = im.convert('RGBA')
    for q in quads:
        c = np.mean(q, 0); q2 = [tuple(c + (np.array(p) - c) * (1 - 2 * inset)) for p in q]   # marge blanche autour du logo
        L = LOGO.resize((600, 600), Image.LANCZOS); src = [(0, 0), (600, 0), (600, 600), (0, 600)]
        w = L.transform(im.size, Image.PERSPECTIVE, tuple(coeffs(q2, src)), Image.BICUBIC)
        # même éclairage que l'étiquette : couleur moyenne de l'étiquette (sans le logo) / blanc pur, puis léger flou comme la photo
        m = Image.new('L', im.size, 0); ImageDraw.Draw(m).polygon([tuple(map(float, p)) for p in q], fill=255)
        lab = np.asarray(im.convert('RGB')).astype(float)[np.asarray(m) > 0]; k = np.clip(np.percentile(lab, 70, 0) / 245, 0.4, 1.05)
        arr = np.asarray(w).astype(float); arr[..., :3] = np.clip(arr[..., :3] * k, 0, 255); w = Image.fromarray(arr.astype('uint8')).filter(ImageFilter.GaussianBlur(0.6))
        im.alpha_composite(w)
    return im.convert('RGB')
if __name__ == '__main__':
    im = Image.open(sys.argv[1]); q = labels(im); print(sys.argv[1], len(q), 'étiquette(s)', [tuple(map(int, p[0])) for p in q])
    paste(im, q).save(sys.argv[2], quality=95)
