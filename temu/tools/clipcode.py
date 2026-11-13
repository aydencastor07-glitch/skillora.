# Style « clip + bulles de texte TikTok » (style approuvé repéré par l'utilisateur) :
# une seule vidéo (ou photo animée) plein écran, et par-dessus des bulles de texte comme celles de l'éditeur TikTok
# (rectangle arrondi plein, texte centré), qui changent toutes les ~3 s et changent de place (haut / milieu / bas).
# Claude pose lui-même le logo Temu, le code et le « 0€ » (jamais dans les images IA).
# usage : clipcode.py config.json sortie.mp4   [PREVIEW=t1,t2]
# config : {src: clip.mp4 | photo.jpg, speed: 0.75, dur: 12, code, style: 0..3, seq: [{t0, t1, boxes: [{txt, y, kind: a|b|c, size}], logo: [x, y]}]}
import json, sys, os, math, subprocess, shutil, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
C = json.load(open(sys.argv[1])); OUT = sys.argv[2]; D = os.path.dirname(os.path.abspath(sys.argv[1]))
W, H, FPS = 1080, 1920, 30
FONT = '/usr/share/fonts/opentype/inter/Inter-SemiBold.otf'
if not os.path.exists(FONT): FONT = '/usr/share/fonts/opentype/inter/Inter-Bold.otf'
LOGO = Image.open('/home/user/skillora./temu/temu_logo.png').convert('RGBA')
# palettes de bulles (fond, texte) : a = principale, b = secondaire, c = troisième ; une palette par vidéo
PAL = [
    {'a': ((14, 84, 72), (255, 226, 60)), 'b': ((255, 214, 232), (20, 20, 20)), 'c': ((255, 246, 176), (20, 20, 20))},   # vert / rose / crème (comme la vidéo approuvée)
    {'a': ((255, 255, 255), (20, 20, 20)), 'b': ((250, 108, 30), (255, 255, 255)), 'c': ((20, 20, 20), (255, 255, 255))},  # blanc / orange / noir
    {'a': ((28, 52, 110), (255, 255, 255)), 'b': ((255, 236, 120), (20, 20, 20)), 'c': ((214, 236, 255), (20, 20, 20))},   # bleu / jaune / bleu clair
    {'a': ((120, 30, 40), (255, 236, 200)), 'b': ((240, 240, 236), (20, 20, 20)), 'c': ((255, 200, 120), (20, 20, 20))},   # bordeaux / blanc cassé / abricot
]
P = PAL[C.get('style', 0) % len(PAL)]
_fc = {}
def F(s):
    if s not in _fc: _fc[s] = ImageFont.truetype(FONT, s)
    return _fc[s]
def clamp(u): return max(0.0, min(1.0, u))
def wrap(txt, f, maxw):
    out = []
    for para in txt.split('\n'):
        cur = ''
        for w in para.split(' '):
            if cur and f.getbbox(cur + ' ' + w)[2] > maxw: out.append(cur); cur = w
            else: cur = (cur + ' ' + w).strip()
        out.append(cur)
    return out
_bx = {}
def bubble(txt, kind, size):
    """Bulle façon éditeur TikTok : un rectangle arrondi par ligne, collés, texte centré."""
    key = (txt, kind, size)
    if key in _bx: return _bx[key]
    bg, fg = P[kind]; f = F(size); lines = wrap(txt, f, W - 220); lh = int(size * 1.18); pad = int(size * 0.32)
    widths = [f.getbbox(l)[2] - f.getbbox(l)[0] for l in lines]; bw = max(widths) + 2 * pad; bh = lh * len(lines) + pad
    lay = Image.new('RGBA', (bw + 20, bh + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for i, (l, w) in enumerate(zip(lines, widths)):
        x0 = 10 + (bw - (w + 2 * pad)) / 2; y0 = 10 + i * lh
        d.rounded_rectangle([x0, y0, x0 + w + 2 * pad, y0 + lh + pad], int(size * 0.32), fill=bg + (255,))
    for i, l in enumerate(lines): d.text((10 + bw / 2, 10 + i * lh + (lh + pad) / 2), l, font=f, fill=fg + (255,), anchor='mm')
    _bx[key] = lay; return lay
# ---- source : vidéo (ralentie) ou photo (zoom lent)
SRC = os.path.join(D, C['src']); IS_VID = SRC.lower().endswith(('.mp4', '.mov', '.webm'))
TMP = OUT + '_tmp'
def prep():
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
    if IS_VID:
        sp = C.get('speed', 0.75)
        subprocess.run([FF, '-v', 'error', '-i', SRC, '-vf', f'setpts=PTS/{sp},fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}', '-q:v', '2', f'{TMP}/s%05d.jpg'], check=True)
        return sorted(f for f in os.listdir(TMP) if f.startswith('s'))
    return None
def frame_src(n, srcs):
    if srcs: return Image.open(f'{TMP}/{srcs[min(n, len(srcs) - 1)]}').convert('RGB')
    im = Image.open(SRC).convert('RGB'); s = max(W / im.width, H / im.height) * 1.12; im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    u = n / (C['dur'] * FPS); z = 1.0 + 0.1 * u; cw, ch = W * 1.12 / z, H * 1.12 / z
    x0 = min(max(0, (im.width - cw) / 2 + 30 * math.sin(u * 3)), im.width - cw); y0 = (im.height - ch) / 2
    return im.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
def render(n, srcs):
    t = n / FPS; img = frame_src(n, srcs).convert('RGBA')
    for sg in C['seq']:
        if not (sg['t0'] <= t < sg['t1']): continue
        k = clamp((t - sg['t0']) / 0.12)
        for b in sg['boxes']:
            lay = bubble(b['txt'], b.get('kind', 'a'), b.get('size', 50))
            if k < 1: lay = lay.copy(); lay.putalpha(lay.getchannel('A').point(lambda v: int(v * k)))
            img.alpha_composite(lay, (int(W / 2 - lay.width / 2 + b.get('x', 0)), int(b['y'] - lay.height / 2)))
        if sg.get('logo'):
            L = LOGO.resize((sg.get('logo_s', 170),) * 2, Image.LANCZOS)
            if k < 1: L.putalpha(L.getchannel('A').point(lambda v: int(v * k)))
            img.alpha_composite(L, (int(sg['logo'][0] - L.width / 2), int(sg['logo'][1] - L.height / 2)))
    return img.convert('RGB')
if __name__ == '__main__':
    srcs = prep(); NF = int(C['dur'] * FPS)
    if os.environ.get('PREVIEW'):
        for ts in os.environ['PREVIEW'].split(','): render(int(float(ts) * FPS), srcs).save(f'{OUT}_{ts}.jpg', quality=90)
        shutil.rmtree(TMP); sys.exit(0)
    for n in range(NF): render(n, srcs).save(f'{TMP}/g{n:05d}.jpg', quality=94)
    # son : celui du clip (ralenti) s'il existe, sinon musique douce générée
    SR = 44100; a = os.path.join(TMP, 'a.wav')
    r = subprocess.run([FF, '-v', 'error', '-y', '-i', SRC, '-vn', '-af', f"atempo={C.get('speed', 0.75)}", '-ac', '1', '-ar', str(SR), a], capture_output=True) if IS_VID else None
    if not (IS_VID and r.returncode == 0 and os.path.exists(a) and os.path.getsize(a) > 10000) or C.get('music'):
        subprocess.run([sys.executable, '/home/user/skillora./temu/tools/popbeat.py', str(C['dur']), a, str(C.get('music_seed', 1)), str(C.get('bpm', 100)), str(C.get('key', 57))], check=True, capture_output=True)
    subprocess.run([FF, '-y', '-v', 'error', '-framerate', str(FPS), '-i', f'{TMP}/g%05d.jpg', '-i', a, '-af', f"afade=t=out:st={C['dur'] - 0.6}:d=0.6", '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '160k', '-ac', '2', '-t', str(C['dur']), '-movflags', '+faststart', OUT], check=True)
    shutil.rmtree(TMP); print('ok', OUT)
