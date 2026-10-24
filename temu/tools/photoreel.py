# Diaporama de photos déjà finies (texte compris dans l'image) → vidéo TikTok 1080×1920 avec mouvement :
# zoom/panoramique lent par photo, transitions variées (zoom, coup de fouet, flash, glissement vers le haut),
# musique pop générée (popbeat.py) + « whoosh » sur chaque transition.
# usage : photoreel.py config.json out.mp4
#   config : {"images": [...], "dur": [s, ...], "trans": ["zoom"|"whip"|"flash"|"up", ...], "music": [seed, bpm, tonalité], "pan": ["in"|"out"|"left"|"right"|"up", ...],
#             "titles": [texte par photo], "code": ["Search code", "xxx", "for Gifts at $0 in TEMU app"] (bandeau du code dessiné sur toute la vidéo)}
import sys, os, json, subprocess, shutil, wave, math
import numpy as np, imageio_ffmpeg
from PIL import Image, ImageFilter, ImageDraw, ImageFont
FF = imageio_ffmpeg.get_ffmpeg_exe(); FPS = 30; W, H = 1080, 1920; X = 0.4        # durée d'une transition (s)
C = json.load(open(sys.argv[1])); OUT = sys.argv[2]; base = os.path.dirname(os.path.abspath(sys.argv[1]))
def cover(im):   # remplit 1080×1920 (marge de 12 % pour le mouvement)
    s = max(W * 1.12 / im.width, H * 1.12 / im.height); return im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
IMS = [cover(Image.open(os.path.join(base, f)).convert('RGB')) for f in C['images']]
D = C['dur']; TR = C['trans']; PAN = C.get('pan', ['in', 'out', 'left', 'right', 'up'] * 4)
def ease(u): u = max(0, min(1, u)); return u * u * (3 - 2 * u)
def view(k, u, extra=1.0):
    im = IMS[k]; p = PAN[k % len(PAN)]; z = {'in': 1 + 0.05 * u, 'out': 1.05 - 0.05 * u}.get(p, 1.0) * extra
    hb = min(im.height, im.width * H / W) / 1.03; h = hb / z; w = h * W / H      # cadre visible (petite marge : le texte près des bords reste entier)
    cx, cy = im.width / 2, im.height / 2; mx, my = (im.width - w) / 2, (im.height - h) / 2
    if p == 'left': cx += mx * (0.8 - 1.6 * u)
    if p == 'right': cx -= mx * (0.8 - 1.6 * u)
    if p == 'up': cy += my * (0.8 - 1.6 * u)
    return im.resize((W, H), Image.BILINEAR, box=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
FD = os.path.join(os.path.dirname(__file__), '..', 'fonts'); ORANGE = (251, 119, 1)
def font(n, sz): return ImageFont.truetype(os.path.join(FD, n), int(sz))
def back(u): u = max(0, min(1, u)); c = 1.7; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2
def overlay(f, k, tl, tg):
    # textes posés par-dessus la photo (jamais générés dans l'image) : titre de la photo en haut, bandeau du code en bas
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    T = C.get('titles')
    if T and k < len(T) and T[k]:
        u = back(tl / 0.35); fs = 84
        while font('Poppins-ExtraBold.ttf', fs).getbbox(T[k])[2] > 900 and fs > 40: fs -= 4
        if u > 0.02:
            ft = font('Poppins-ExtraBold.ttf', fs * u); d.text((W / 2 - 40, 330), T[k], font=ft, fill=(255, 255, 255, 255), anchor='mm', stroke_width=max(1, int(9 * u)), stroke_fill=(0, 0, 0, 200))
    CD = C.get('code')
    if CD:   # « Search code » / code (grand, sur pastille blanche) / « for Gifts at $0 in TEMU app »
        pulse = 1 + 0.035 * math.sin(tg * 5.5); cx, cy = W / 2 - 40, 1300
        f1, f2, f3 = font('Poppins-ExtraBold.ttf', 50), font('Poppins-ExtraBold.ttf', 104 * pulse), font('Poppins-ExtraBold.ttf', 44)
        bw = max(d.textbbox((0, 0), CD[2], font=f3)[2], d.textbbox((0, 0), CD[1], font=f2)[2]) + 90
        d.rounded_rectangle([cx - bw / 2, cy - 175, cx + bw / 2, cy + 165], 46, fill=ORANGE + (240,))
        d.text((cx, cy - 125), CD[0], font=f1, fill=(255, 255, 255, 255), anchor='mm')
        cw = d.textbbox((0, 0), CD[1], font=f2)[2] + 60
        d.rounded_rectangle([cx - cw / 2, cy - 82, cx + cw / 2, cy + 62], 34, fill=(255, 255, 255, 255))
        d.text((cx, cy - 10), CD[1], font=f2, fill=(20, 20, 20, 255), anchor='mm')
        d.text((cx, cy + 112), CD[2], font=f3, fill=(255, 255, 255, 255), anchor='mm')
    g = f.convert('RGBA'); g.alpha_composite(lay); return g.convert('RGB')
fr = OUT + '_fr'; shutil.rmtree(fr, ignore_errors=True); os.makedirs(fr); n = 0; cuts = []
for k, d in enumerate(D):
    N = int(d * FPS); t0 = N - int(X * FPS)
    for i in range(N):
        f = view(k, i / N)
        if k < len(D) - 1 and i >= t0:
            a = (i - t0) / (X * FPS); tr = TR[k % len(TR)]
            if i == t0: cuts.append(n / FPS)
            if tr == 'zoom':      # l'image avance vers nous et se fond dans la suivante
                g = view(k, i / N, 1 + 0.35 * a * a); f = Image.blend(g, view(k + 1, 0), ease(a))
            elif tr == 'whip':    # coup de fouet horizontal flou
                c = Image.new('RGB', (W, H)); s = int(W * ease(a)); c.paste(f, (-s, 0)); c.paste(view(k + 1, 0), (W - s, 0))
                f = c.filter(ImageFilter.BoxBlur(int(28 * math.sin(math.pi * a))))
            elif tr == 'up':      # la suivante monte et recouvre
                c = f.copy(); s = int(H * (1 - ease(a))); c.paste(view(k + 1, 0), (0, s)); f = c
            else:                 # flash blanc
                g = f if a < 0.5 else view(k + 1, 0); w_ = 1 - abs(a - 0.5) * 2; f = Image.blend(g, Image.new('RGB', (W, H), (255, 255, 255)), 0.85 * w_)
        f = overlay(f, k, i / FPS if not (k < len(D) - 1 and i >= t0) else -1, n / FPS)
        f.save(f'{fr}/f{n:05d}.jpg', quality=93); n += 1
DUR = n / FPS; SR = 44100
seed, bpm, key = C.get('music', [7, 112, 60]); m = fr + '/m.wav'
subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'popbeat.py'), str(DUR + 0.5), m, str(seed), str(bpm), str(key)], check=True, capture_output=True)
w = wave.open(m); mu = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float) / 32768
if w.getnchannels() == 2: mu = mu.reshape(-1, 2).mean(1)
N = int(DUR * SR); mix = np.pad(mu, (0, max(0, N - len(mu))))[:N] * 0.55
ws = wave.open('/home/user/skillora./motion/sfx/whoosh.wav'); s = np.frombuffer(ws.readframes(ws.getnframes()), '<i2').astype(float) / 32768
if ws.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
for c in cuts: i0 = int(c * SR); L = min(len(s), N - i0); mix[i0:i0 + L] += s[:L] * 0.35
fi, fo = int(0.3 * SR), int(0.8 * SR); mix[:fi] *= np.linspace(0, 1, fi); mix[-fo:] *= np.linspace(1, 0, fo); mix = mix / np.abs(mix).max() * 0.9
wo = wave.open(fr + '/a.wav', 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((mix * 32767).astype('<i2').tobytes()); wo.close()
subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{fr}/f%05d.jpg', '-i', fr + '/a.wav', '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '192k', '-af', 'pan=stereo|c0=c0|c1=c0', '-shortest', '-movflags', '+faststart', OUT], check=True)
shutil.rmtree(fr); print('ok', OUT, round(DUR, 2), 's')
