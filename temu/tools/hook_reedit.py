# Remontage d'une vidéo Temu refusée pour « Missing a Strong Hook in the First 3 Seconds » :
# le plan le plus accrocheur passe en premier (zoom d'impact + flash), une grosse question à l'écran dès la 1re image,
# le reste accéléré, et des effets sonores (la vidéo source est muette).
# usage : hook_reedit.py source.mp4 sortie.mp4
import sys, math, subprocess, wave
import numpy as np, imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont
FF = imageio_ffmpeg.get_ffmpeg_exe(); SRC, OUT = sys.argv[1], sys.argv[2]
W, H, FPS = 1080, 1920, 30; FD = '/home/user/skillora./temu/fonts/'; SFXD = '/home/user/skillora./motion/sfx/'
# (début, fin, vitesse) dans la source : fauteuil gonflable d'abord, puis tout le déballage plus vite, puis la fin
PLAN = [(8.0, 9.8, 1.0), (0.0, 8.0, 1.3), (9.8, 11.2, 1.0)]
src = np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', SRC, '-vf', f'fps={FPS},scale={W}:{H}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                                   capture_output=True).stdout, np.uint8).reshape(-1, H, W, 3)
seq = []
for a, b, v in PLAN:
    n = int((b - a) / v * FPS)
    seq += [min(len(src) - 1, int((a + k * v / FPS) * FPS)) for k in range(n)]
DUR = len(seq) / FPS
def ease(u): u = max(0.0, min(1.0, u)); return 1 - (1 - u) ** 3
def back(u): u = max(0.0, min(1.0, u)); c = 1.7; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2
def label(s, size, col, stroke=10):
    f = ImageFont.truetype(FD + 'Anton-Regular.ttf', size); bb = f.getbbox(s, stroke_width=stroke)
    im = Image.new('RGBA', (bb[2] - bb[0] + 20, bb[3] - bb[1] + 20), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10 - bb[0], 10 - bb[1]), s, font=f, fill=col, stroke_width=stroke, stroke_fill=(0, 0, 0)); return im
L1 = label("IS TEMU'S $0 GIFT", 120, (255, 255, 255)); L2 = label('A SCAM?', 190, (255, 60, 60), 12); L3 = label("LET ME SHOW YOU...", 92, (255, 230, 40))
def put(img, lab, cy, k, a=1.0):
    if k <= 0.01 or a <= 0.01: return
    s = max(0.05, k); im = lab.resize((max(1, int(lab.width * s)), max(1, int(lab.height * s))), Image.LANCZOS)
    if a < 1: im.putalpha(im.getchannel('A').point(lambda v: int(v * a)))
    img.alpha_composite(im, (W // 2 - im.width // 2, int(cy - im.height / 2)))
# --- son : whoosh + pop + hit au début, swish à chaque changement de plan (la source est muette)
SR = 44100; N = int(DUR * SR) + SR; mix = np.zeros(N)
def sfx(name, t0, g):
    w = wave.open(SFXD + name + '.wav'); s = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float) / 32768
    if w.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
    if w.getframerate() != SR: s = np.interp(np.arange(0, len(s), w.getframerate() / SR), np.arange(len(s)), s)
    i0 = int(t0 * SR); L = min(len(s), N - i0); mix[i0:i0 + L] += s[:L] * g
sfx('whoosh', 0.0, 0.5); sfx('hit', 0.05, 0.6); sfx('pop', 0.55, 0.5); sfx('hit', 0.95, 0.7); sfx('ding', 1.9, 0.4)
t = 0
for a, b, v in PLAN[:-1]: t += (b - a) / v; sfx('swish', t - 0.05, 0.5)
mix = mix[:int(DUR * SR)]; mix = mix / max(1e-6, np.abs(mix).max()) * 0.9
wo = wave.open(OUT + '.wav', 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((mix * 32767).astype('<i2').tobytes()); wo.close()
enc = subprocess.Popen([FF, '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-i', OUT + '.wav',
                        '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', OUT],
                       stdin=subprocess.PIPE)
for n, fi in enumerate(seq):
    t = n / FPS; img = Image.fromarray(src[fi]).convert('RGBA')
    z = 1.0 + 0.18 * (1 - ease(t / 0.5)) + 0.06 * max(0, 1 - abs(t - 0.95) / 0.25)        # zoom d'impact au début et sur « SCAM »
    if z > 1.001:
        cw, ch = W / z, H / z; img = img.resize((W, H), Image.LANCZOS, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2))
    if t < 2.0:   # la question, en plein centre (hors bandes) dès la 1re image
        a = 1 - max(0, (t - 1.8) / 0.2)
        put(img, L1, 700, back(t / 0.3), a); put(img, L2, 880, back((t - 0.9) / 0.25) * (1 + 0.04 * math.sin(t * 18)), a)
    elif t < 3.6:
        put(img, L3, 800, back((t - 2.0) / 0.25), 1 - max(0, (t - 3.4) / 0.2))
    if t < 0.12: img.alpha_composite(Image.new('RGBA', (W, H), (255, 255, 255, int(255 * (1 - t / 0.12)))))
    enc.stdin.write(img.convert('RGB').tobytes())
enc.stdin.close(); enc.wait(); import os; os.remove(OUT + '.wav'); print('ok', OUT, round(DUR, 2), 's')
