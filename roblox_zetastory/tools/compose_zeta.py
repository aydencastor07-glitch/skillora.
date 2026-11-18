# Montage ZetaStory : images Blender (720p) agrandies en 1080x1920, sous-titres UN mot à la fois (jaune-vert fluo, contour noir,
# à 65 % de la hauteur, comme les vidéos de référence), voix + musique en boucle. La vidéo s'arrête net après le dernier mot.
# usage : compose_zeta.py dossier_episode dossier_frames sortie.mp4     (episode : voix_clean.mp3, words.json, musique.mp3)
# SUBS=ember : style « braise » (ép. 6, ambiance sombre) : petits groupes de 1 à 3 mots en blanc, le mot prononcé en orange braise #ff5a1f.
import sys, os, json, re, subprocess
from multiprocessing import Pool
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe(); EP, FR, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
W, H, FPS = 1080, 1920, 30
WORDS = json.load(open(os.path.join(EP, 'words.json')))
FONT = '/home/user/skillora./temu/fonts/Poppins-ExtraBold.ttf'; COLOR = (233, 255, 68); Y = int(H * 0.65)
files = sorted(f for f in os.listdir(FR) if f.endswith('.jpg')); NF = len(files); TMP = OUT + '_tmp'; os.makedirs(TMP, exist_ok=True)
def mot(t):
    for i, (w, a, b) in enumerate(WORDS):
        fin = WORDS[i + 1][1] if i + 1 < len(WORDS) else b + 0.25
        if a - 0.03 <= t < min(fin, b + 0.5) - 0.03: return re.sub(r'[“”"«»…:.,;!?—–]', '', w).strip().lower(), t - a
    return None, 0
_f = {}
def font(s):
    if s not in _f: _f[s] = ImageFont.truetype(FONT, s)
    return _f[s]
STYLE = os.environ.get('SUBS', 'neon'); EMBER = (255, 90, 31)
def clean(w): return re.sub(r'[“”"«»…:.,;!?—–]', '', w).strip()
GROUPS = []; _g = []
for i, (w, a, b) in enumerate(WORDS):
    _g.append(i)
    if len(_g) == 3 or re.search(r'[.,!?:…]["”]?$', w) or i == len(WORDS) - 1: GROUPS.append(_g); _g = []
def groupe(t):
    for gi, g in enumerate(GROUPS):
        a = WORDS[g[0]][1]; fin = WORDS[GROUPS[gi + 1][0]][1] if gi + 1 < len(GROUPS) else WORDS[g[-1]][2] + 0.25
        fin = min(fin, WORDS[g[-1]][2] + 0.6)
        if a - 0.03 <= t < fin - 0.03:
            cur = max([i for i in g if WORDS[i][1] - 0.03 <= t] or [g[0]]); return g, cur, t - a
    return None, None, 0
def ember(im, t):
    g, cur, dt = groupe(t)
    if not g: return
    ws = [clean(WORDS[i][0]).upper() for i in g]; size = 84; f = font(size); sp = f.getlength(' ')
    while sum(f.getlength(w) for w in ws) + sp * (len(ws) - 1) > W - 170: size -= 4; f = font(size); sp = f.getlength(' ')
    fs = [font(int(size * 1.08)) if i == cur else f for i in g]; tot = sum(F.getlength(w) for F, w in zip(fs, ws)) + sp * 1.3 * (len(ws) - 1)
    d = ImageDraw.Draw(im); x = W / 2 - tot / 2
    for i, w, ff in zip(g, ws, fs):
        wl = ff.getlength(w); col = EMBER if i == cur else (255, 255, 255)
        d.text((x + wl / 2 + 4, Y + 6), w, font=ff, fill=(0, 0, 0), anchor='mm', stroke_width=10, stroke_fill=(0, 0, 0))
        d.text((x + wl / 2, Y), w, font=ff, fill=col, anchor='mm', stroke_width=10, stroke_fill=(12, 8, 6)); x += wl + sp * 1.3
def render(n):
    im = Image.open(os.path.join(FR, files[n])).convert('RGB').resize((W, H), Image.LANCZOS).filter(ImageFilter.UnsharpMask(1.2, 60, 2))
    w, dt = mot(n / FPS) if STYLE != 'ember' else (None, 0)
    if STYLE == 'ember': ember(im, n / FPS)
    if w:
        k = 1.18 - 0.18 * min(1, max(0, dt + 0.03) / 0.09); size = int(96 * k)
        f = font(size)
        while f.getlength(w) > W - 160: size -= 6; f = font(size)
        d = ImageDraw.Draw(im); d.text((W / 2 + 5, Y + 7), w, font=f, fill=(0, 0, 0), anchor='mm', stroke_width=11, stroke_fill=(0, 0, 0))
        d.text((W / 2, Y), w, font=f, fill=COLOR, anchor='mm', stroke_width=11, stroke_fill=(10, 10, 10))
    im.save(os.path.join(TMP, f'g{n:05d}.jpg'), quality=93)
if __name__ == '__main__':
    with Pool(4) as p: p.map(render, range(NF), chunksize=20)
    dur = NF / FPS; mus = os.path.join(EP, 'musique.mp3')
    # Musique : niveau FIXE quel que soit le fichier (avant : volume 0.16 → la musique virale, déjà faible, devenait inaudible).
    # Voix ≈ -14 LUFS, musique ramenée à MUS_LUFS (-21 par défaut) : bien audible, la voix reste devant.
    ML = float(os.environ.get('MUS_LUFS', -21))
    cmd = [FF, '-y', '-v', 'error', '-framerate', str(FPS), '-i', os.path.join(TMP, 'g%05d.jpg'), '-i', os.path.join(EP, 'voix_clean.mp3'), '-stream_loop', '-1', '-i', mus,
           '-filter_complex', f'[2:a]loudnorm=I={ML}:TP=-3:LRA=11,afade=t=in:d=0.4[m];[1:a][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]', '-map', '0:v', '-map', '[a]',
           '-t', f'{dur:.3f}', '-c:v', 'libx264', '-preset', 'slow', '-crf', '19', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', OUT]
    subprocess.run(cmd, check=True)
    for f in os.listdir(TMP): os.remove(os.path.join(TMP, f))
    os.rmdir(TMP); print('ok', OUT, round(dur, 2), 'musique', ML, 'LUFS')
