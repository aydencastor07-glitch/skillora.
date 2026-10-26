# Fond blanc -> fond noir : remplissage depuis les bords (le corps entouré de traits reste blanc).
import sys
import numpy as np
from PIL import Image
from scipy import ndimage
src, out = sys.argv[1:3]
im = Image.open(src).convert('RGB'); a = np.asarray(im).astype(np.int16)
lum = a.mean(2); sat = a.max(2) - a.min(2)
light = (lum > 200) & (sat < 40)              # zones blanches / grises très claires
lab, n = ndimage.label(light)
edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
bg = np.isin(lab, list(edge))
bg = ndimage.binary_dilation(bg, iterations=1) & (lum > 150) & (sat < 60)
o = a.copy(); o[bg] = 0
# halos gris clair restants autour du dessin -> assombris
soft = (~bg) & (lum > 170) & (sat < 30) & ndimage.binary_dilation(bg, iterations=3)
o[soft] = (o[soft] * 0.15).astype(np.int16)
Image.fromarray(o.clip(0, 255).astype(np.uint8)).save(out, quality=92)
print('ok', bg.mean().round(2))
