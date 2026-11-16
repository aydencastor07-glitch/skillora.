# Montage ZetaStory : images Blender (720p) agrandies en 1080x1920, sous-titres UN mot à la fois (jaune-vert fluo, contour noir,
# à 65 % de la hauteur, comme les vidéos de référence), voix + musique en boucle. La vidéo s'arrête net après le dernier mot.
# usage : compose_zeta.py dossier_episode dossier_frames sortie.mp4     (episode : voix_clean.mp3, words.json, musique.mp3)
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
def render(n):
    im = Image.open(os.path.join(FR, files[n])).convert('RGB').resize((W, H), Image.LANCZOS).filter(ImageFilter.UnsharpMask(1.2, 60, 2))
    w, dt = mot(n / FPS)
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
    cmd = [FF, '-y', '-v', 'error', '-framerate', str(FPS), '-i', os.path.join(TMP, 'g%05d.jpg'), '-i', os.path.join(EP, 'voix_clean.mp3'), '-stream_loop', '-1', '-i', mus,
           '-filter_complex', f'[2:a]volume=0.16,afade=t=in:d=0.4[m];[1:a][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]', '-map', '0:v', '-map', '[a]',
           '-t', f'{dur:.3f}', '-c:v', 'libx264', '-preset', 'slow', '-crf', '19', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', OUT]
    subprocess.run(cmd, check=True)
    for f in os.listdir(TMP): os.remove(os.path.join(TMP, f))
    os.rmdir(TMP); print('ok', OUT, round(dur, 2))
