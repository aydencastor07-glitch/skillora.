# Montage « Ich bin's. Mach auf. » : images 3D (frames/f%05d.jpg) + grain/vignette + sous-titres style JEU VIDÉO
# (petits, une phrase entière, bandeau sombre, nom « PAPA » en ambre pour ses messages), carte de chapitre façon jeu,
# + voix, coups à la porte, battements de cœur, vibration du téléphone, nappe grave. Fin coupée pile sur le dernier mot.
# usage : compose_papa.py dossier_episode dossier_frames sortie.mp4
import sys, os, json, re, subprocess, shutil, wave
import numpy as np
from multiprocessing import Pool
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
EP, FR, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
W, H, FPS, SR = 1080, 1920, 30, 44100
FD = '/home/user/skillora./temu/fonts/'; SFX = '/home/user/skillora./motion/sfx/'
CFG = json.load(open(os.path.join(EP, 'compose.json')))
NF = len([f for f in os.listdir(FR) if f.endswith('.jpg')]); DUR = NF / FPS
def F(n, s): return ImageFont.truetype(FD + n, s)
yy, xx = np.mgrid[0:H, 0:W]; VIG = (1 - 0.45 * (((xx - W / 2) / (W / 2)) ** 2 * 0.7 + ((yy - H / 2) / (H / 2)) ** 2 * 0.55)).clip(0.45, 1)[..., None].astype(np.float32); del yy, xx
def clamp(u): return max(0.0, min(1.0, u))
def sub(img, t):
    for s in CFG['subs']:   # {t0, t1, who?, txt}
        if not (s['t0'] - 0.05 <= t < s['t1']): continue
        k = clamp((t - s['t0'] + 0.05) / 0.15) * clamp((s['t1'] - t) / 0.12); a = int(255 * k)
        f = F('Nunito.ttf', 50); fb = F('Poppins-ExtraBold.ttf', 40); who = s.get('who')
        lab = (who + '  ') if who else ''; lw = fb.getbbox(lab)[2] if who else 0; tw = f.getbbox(s['txt'])[2]
        tot = lw + tw; x0 = W / 2 - tot / 2; y = CFG.get('sub_y', 1395)
        d = ImageDraw.Draw(img, 'RGBA'); d.rounded_rectangle([x0 - 26, y - 44, x0 + tot + 26, y + 40], 10, fill=(0, 0, 0, int(150 * k)))
        if who: d.text((x0, y), lab, font=fb, fill=(255, 184, 72, a), anchor='lm')
        d.text((x0 + lw, y), s['txt'], font=f, fill=(240, 240, 236, a), anchor='lm')
def chapter(img, t):
    c = CFG.get('chapter')
    if not c or not (c['t0'] <= t < c['t1']): return
    k = clamp((t - c['t0']) / 0.4) * clamp((c['t1'] - t) / 0.4); a = int(255 * k); d = ImageDraw.Draw(img, 'RGBA')
    y = c.get('y', 470); d.text((W / 2, y), c['top'], font=F('Nunito.ttf', 34), fill=(210, 210, 205, a), anchor='mm')
    w = int(260 * clamp((t - c['t0']) / 0.6)); d.rectangle([W / 2 - w, y + 32, W / 2 + w, y + 34], fill=(255, 184, 72, a))
    d.text((W / 2, y + 92), c['title'], font=F('PlayfairDisplay-Italic.ttf', 84), fill=(245, 242, 235, a), anchor='mm')
def render(n):
    t = n / FPS
    a = np.asarray(Image.open(f'{FR}/f{n:05d}.jpg').convert('RGB')).astype(np.float32)
    a = a * VIG + np.random.RandomState(n).normal(0, 3.0, (H, W, 1))
    for fl in CFG.get('flash', []):
        if fl <= t < fl + 0.1: a = a * 0.3 + 160
    img = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert('RGBA')
    chapter(img, t); sub(img, t)
    img.convert('RGB').save(f'{TMP}/g{n:05d}.jpg', quality=93)
# ---------- son
def load(f):
    return np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', f, '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(np.float32) / 32768
def lp(x, k): c = np.cumsum(np.concatenate([np.zeros(k), x])); return ((c[k:] - c[:-k]) / k).astype(np.float32)
def put(m, s, t0, g):
    a0 = int(t0 * SR); L = min(len(s), len(m) - a0)
    if L > 0 and a0 >= 0: m[a0:a0 + L] += s[:L] * g
def knock(seed):
    n = int(0.25 * SR); tt = np.arange(n) / SR; r = np.random.RandomState(seed)
    body = np.sin(2 * np.pi * 95 * tt) * np.exp(-tt * 28) + 0.5 * np.sin(2 * np.pi * 180 * tt) * np.exp(-tt * 40)
    click = lp(r.normal(0, 1, n).astype(np.float32), 6) * np.exp(-tt * 120) * 2.5
    return (body + click).astype(np.float32)
def beat():
    n = int(0.18 * SR); tt = np.arange(n) / SR; return (np.sin(2 * np.pi * 52 * tt) * np.exp(-tt * 22)).astype(np.float32)
def wavf(name):
    ws = wave.open(SFX + name + '.wav'); s = np.frombuffer(ws.readframes(ws.getnframes()), '<i2').astype(np.float32) / 32768
    if ws.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
    if ws.getframerate() != SR: s = np.interp(np.arange(0, len(s), ws.getframerate() / SR), np.arange(len(s)), s).astype(np.float32)
    return s
def audio(path):
    n = int(DUR * SR); m = np.zeros(n, np.float32)
    v = load(os.path.join(EP, 'voix_clean.mp3'))[:n]; v = np.pad(v, (0, n - len(v)))
    tt = np.arange(n) / SR
    drone = (np.sin(2 * np.pi * 41 * tt) * 0.6 + np.sin(2 * np.pi * 61.5 * tt) * 0.3) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.13 * tt))
    hiss = lp(np.random.RandomState(9).normal(0, 1, n).astype(np.float32), 60); hiss /= np.abs(hiss).max() + 1e-9
    fx = np.zeros(n, np.float32)
    for i, k in enumerate(CFG['knocks']): put(fx, knock(i), k, 0.9)
    for st in CFG.get('stingers', []):   # coup grave + souffle à la révélation
        d = int(1.6 * SR); s_ = np.arange(d) / SR; put(fx, (np.sin(2 * np.pi * np.cumsum(np.linspace(70, 30, d)) / SR) * np.exp(-s_ * 2.2)).astype(np.float32), st, 0.9)
        put(fx, lp(np.random.RandomState(3).normal(0, 1, d).astype(np.float32), 3) * np.exp(-s_ * 3), st, 0.18)
    t = CFG['heart'][0]
    while t < CFG['heart'][1]: put(fx, beat(), t, 0.7); put(fx, beat(), t + 0.2, 0.45); t += 0.62
    for b in CFG.get('buzz', []): put(fx, wavf('buzz') * 0.6, b, 0.5)
    for b in CFG.get('msg', []): put(fx, wavf('tap'), b, 0.5)
    ve = lp(np.abs(v), 4410); duck = 1 - 0.4 * np.clip(ve / (ve.max() * 0.25 + 1e-9), 0, 1)
    out = v * 1.0 + (drone * 0.05 + hiss * 0.02) * duck + fx
    out = out / max(1e-6, np.abs(out).max()) * 0.95
    wo = wave.open(path, 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((out * 32767).astype('<i2').tobytes()); wo.close()
TMP = OUT + '_tmp'
if __name__ == '__main__':
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
    with Pool(4) as p: p.map(render, range(NF), chunksize=20)
    audio(f'{TMP}/a.wav')
    subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{TMP}/g%05d.jpg', '-i', f'{TMP}/a.wav', '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
    shutil.rmtree(TMP); print('ok', OUT, round(DUR, 2))
