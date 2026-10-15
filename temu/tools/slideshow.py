# Carrousel → vidéo TikTok (1080×1920). usage : slideshow.py dossier_slides out.mp4 [fade|push|zoomout]
import sys, os, subprocess, imageio_ffmpeg, shutil
from PIL import Image
src, out, mode = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else 'fade')
FF = imageio_ffmpeg.get_ffmpeg_exe(); FPS = 30; W, H = 1080, 1920; X = 0.45
S = [Image.open(os.path.join(src, f)).convert('RGB') for f in sorted(os.listdir(src)) if f.startswith('slide')]
D = [2.6, 3.4, 3.4, 4.6][:len(S)]
fr = out + '_fr'; shutil.rmtree(fr, ignore_errors=True); os.makedirs(fr)
def view(im, u):
    z = 1 + 0.06 * u if mode != 'zoomout' else 1.08 - 0.08 * u
    w, h = int(W / z), int(H / z); return im.crop(((W - w) // 2, (H - h) // 2, (W - w) // 2 + w, (H - h) // 2 + h)).resize((W, H), Image.BILINEAR)
n = 0
for k, (im, d) in enumerate(zip(S, D)):
    N = int(d * FPS)
    for i in range(N):
        f = view(im, i / N); t0 = N - int(X * FPS)
        if k < len(S) - 1 and i > t0:
            a = (i - t0) / (X * FPS); a = a * a * (3 - 2 * a); nx = view(S[k + 1], 0)
            if mode == 'push':
                c = Image.new('RGB', (W, H)); c.paste(f, (-int(W * a), 0)); c.paste(nx, (W - int(W * a), 0)); f = c
            else: f = Image.blend(f, nx, a)
        f.save(f'{fr}/f{n:05d}.jpg', quality=92); n += 1
subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{fr}/f%05d.jpg', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-movflags', '+faststart', out], check=True)
shutil.rmtree(fr); print('ok', out, n / FPS, 's')
