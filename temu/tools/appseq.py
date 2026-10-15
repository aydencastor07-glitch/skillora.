# Séquence « démonstration dans l'appli » : l'enregistrement d'écran dans un téléphone, sur le décor flouté de la vidéo.
# usage : appseq.py app.mp4 fond.png out.mp4 'json' ; json = {"segs":[[a,b,vitesse,"titre"],...],"accent":[r,g,b],"code_text":..,"code":..}
import sys, json, os, subprocess, shutil, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe(); app, bgp, out = sys.argv[1:4]; P = json.loads(sys.argv[4])
W, H, FPS = 1080, 1920, 30; ACC = tuple(P.get('accent', (255, 92, 150))); FD = '/home/user/skillora./temu/fonts/'
tmp = out + '_tmp'; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp + '/src'); os.makedirs(tmp + '/fr')
bg = Image.open(bgp).convert('RGB').resize((W, H)).filter(ImageFilter.GaussianBlur(28)); bg = ImageEnhance.Brightness(bg).enhance(1.15)
tint = Image.new('RGB', (W, H), ACC); bg = Image.blend(bg, tint, 0.18).convert('RGBA')
PW, PH = 600, 1334; PX, PY = (W - PW) // 2, 330
mask = Image.new('L', (PW, PH), 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, PW - 1, PH - 1], 60, fill=255)
shadow = Image.new('RGBA', (PW + 80, PH + 80), (0, 0, 0, 0)); ImageDraw.Draw(shadow).rounded_rectangle([40, 50, PW + 40, PH + 50], 70, fill=(0, 0, 0, 120)); shadow = shadow.filter(ImageFilter.GaussianBlur(25))
LOGO = Image.open('/home/user/skillora./temu/temu_logo.png').convert('RGBA').resize((150, 150), Image.LANCZOS)
ft = ImageFont.truetype(FD + 'Poppins-ExtraBold.ttf', 64); fc = ImageFont.truetype(FD + 'Poppins-ExtraBold.ttf', 40); fcode = ImageFont.truetype(FD + 'Poppins-ExtraBold.ttf', 58)
n = 0
def ease(u): u = max(0, min(1, u)); return 1 - (1 - u) ** 3
for si, (a, b, sp, title) in enumerate(P['segs']):
    d = (b - a) / sp; N = int(d * FPS)
    subprocess.run([FF, '-y', '-loglevel', 'error', '-ss', str(a), '-t', str(b - a), '-i', app, '-vf', f'setpts=PTS/{sp},fps={FPS},scale={PW}:{PH}', f'{tmp}/src/s{si}_%04d.png'], check=True)
    srcs = sorted(f for f in os.listdir(tmp + '/src') if f.startswith(f's{si}_'))
    for i in range(N):
        t = i / FPS; f = bg.copy(); dr = ImageDraw.Draw(f)
        k = ease(t / 0.35) if si == 0 else 1
        f.alpha_composite(shadow, (PX - 40, PY - 40 + int((1 - k) * 600)))
        sc = Image.open(f'{tmp}/src/{srcs[min(i, len(srcs) - 1)]}').convert('RGBA'); sc.putalpha(mask)
        f.alpha_composite(sc, (PX, PY + int((1 - k) * 600)))
        dr.rounded_rectangle([PX - 6, PY - 6 + int((1 - k) * 600), PX + PW + 6, PY + PH + 6 + int((1 - k) * 600)], 64, outline=(255, 255, 255), width=10)
        # titre de l'étape
        u = ease(t / 0.3); tw = ft.getbbox(title)[2] + 80; x0 = W / 2 - tw / 2; y0 = 120 - (1 - u) * 80
        dr.rounded_rectangle([x0, y0, x0 + tw, y0 + 120], 60, fill=ACC + (255,)); dr.text((W / 2, y0 + 60), title, font=ft, fill=(255, 255, 255), anchor='mm')
        # logo qui rebondit au début de chaque étape
        if t < 1.0:
            s = max(0.01, math.sin(min(1, t / 0.5) * math.pi / 2) * (1 - max(0, t - 0.7) / 0.3)); lg = LOGO.resize((int(150 * s) + 1, int(150 * s) + 1)); f.alpha_composite(lg, (int(W - 120 - lg.width / 2), int(PY + 90 - lg.height / 2)))
        # texte obligatoire en bas
        txt = P['code_text']; i1 = txt.index(P['code']) + len(P['code']); l1, l2 = txt[:i1], txt[i1:].strip()
        bw = max(fcode.getbbox(l1)[2], fc.getbbox(l2)[2]) + 80
        dr.rounded_rectangle([W / 2 - bw / 2, 1700, W / 2 + bw / 2, 1880], 34, fill=(255, 255, 255, 245), outline=ACC + (255,), width=7)
        pre = l1[:l1.index(P['code'])]; xx = W / 2 - fcode.getbbox(l1)[2] / 2
        dr.text((xx, 1755), pre, font=fcode, fill=(40, 30, 35), anchor='lm'); dr.text((xx + fcode.getbbox(pre)[2], 1755), P['code'], font=fcode, fill=ACC, anchor='lm')
        dr.text((W / 2, 1832), l2, font=fc, fill=(60, 50, 55), anchor='mm')
        f.convert('RGB').save(f'{tmp}/fr/f{n:05d}.jpg', quality=92); n += 1
subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/fr/f%05d.jpg', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-shortest', '-c:v', 'libx264', '-crf', '17', '-pix_fmt', 'yuv420p', '-c:a', 'aac', out], check=True)
shutil.rmtree(tmp); print('ok', out, n / FPS)
