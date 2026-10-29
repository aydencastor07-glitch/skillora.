# Vidéo Temu générée (IA, souvent 720p et muette) → version à publier : 1080x1920 net (Lanczos + accentuation),
# accroche en gros dans les 2,4 premières secondes (zoom d'impact + flash), puis « GIFT TEMU $0 » et le cadre du code,
# le cadre du code sur le pull (entre le visage et le carton) : il ne cache ni le logo ni les produits ;
# effets sonores. Le code, le $0 et les titres sont toujours posés ici, jamais générés par l'IA.
# usage : ugc_overlay.py source.mp4 sortie.mp4 ["LIGNE 1|LIGNE 2"]
import sys, math, subprocess, wave, os
import numpy as np, imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageFilter
FF = imageio_ffmpeg.get_ffmpeg_exe(); SRC, OUT = sys.argv[1], sys.argv[2]
HOOK = (sys.argv[3] if len(sys.argv) > 3 else "IS TEMU'S $0 GIFT|A SCAM?").split('|')
CODE = 'alq393258'; W, H, FPS = 1080, 1920, 30
FD = '/home/user/skillora./temu/fonts/'; SFXD = '/home/user/skillora./motion/sfx/'
raw = subprocess.run([FF, '-v', 'error', '-i', SRC, '-vf', f'fps={FPS},scale={W}:{H}:flags=lanczos,unsharp=5:5:0.8:5:5:0.0', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                     capture_output=True).stdout
src = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3); NF = len(src); DUR = NF / FPS
def ease(u): u = max(0.0, min(1.0, u)); return 1 - (1 - u) ** 3
def back(u): u = max(0.0, min(1.0, u)); c = 1.7; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2
def label(s, size, col, stroke=10, font='Anton-Regular.ttf'):
    f = ImageFont.truetype(FD + font, size); bb = f.getbbox(s, stroke_width=stroke)
    im = Image.new('RGBA', (bb[2] - bb[0] + 24, bb[3] - bb[1] + 24), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((12 - bb[0], 12 - bb[1]), s, font=f, fill=col, stroke_width=stroke, stroke_fill=(0, 0, 0)); return im
def card(lines, size, fg, bg, pad=22, radius=22, font='Anton-Regular.ttf'):
    f = ImageFont.truetype(FD + font, size); ws = [f.getbbox(l) for l in lines]; lh = size * 1.12
    w = int(max(b[2] - b[0] for b in ws) + 2 * pad); h = int(lh * len(lines) + 2 * pad - size * 0.12)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im); d.rounded_rectangle([0, 0, w - 1, h - 1], radius, fill=bg)
    for k, l in enumerate(lines): d.text((w / 2, pad + k * lh + size * 0.5), l, font=f, fill=fg, anchor='mm')
    return im
H1 = label(HOOK[0], 104, (255, 255, 255)); H2 = label(HOOK[1], 150, (255, 60, 60), 12) if len(HOOK) > 1 else None
GIFT = card(['GIFT TEMU $0'], 74, (20, 20, 20), (255, 214, 10, 255)); CODEC = card([f'Search code {CODE} for', 'Gifts at $0 in TEMU app'], 54, (255, 255, 255), (124, 58, 237, 255))
def put(img, lab, cx, cy, k, a=1.0):
    if lab is None or k <= 0.01 or a <= 0.01: return
    im = lab.resize((max(1, int(lab.width * k)), max(1, int(lab.height * k))), Image.LANCZOS) if abs(k - 1) > 0.01 else lab
    if a < 0.99: im = im.copy(); im.putalpha(im.getchannel('A').point(lambda v: int(v * a)))
    img.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))
HOOK_END = 2.4
# --- son (la vidéo IA est muette) : whoosh + impacts sur l'accroche, pop à l'arrivée du code
SR = 44100; N = int(DUR * SR); mix = np.zeros(N + SR)
def sfx(name, t0, g):
    w = wave.open(SFXD + name + '.wav'); s = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float) / 32768
    if w.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
    if w.getframerate() != SR: s = np.interp(np.arange(0, len(s), w.getframerate() / SR), np.arange(len(s)), s)
    i0 = int(t0 * SR); L = min(len(s), len(mix) - i0); mix[i0:i0 + L] += s[:L] * g
sfx('whoosh', 0.0, 0.5); sfx('hit', 0.05, 0.6); sfx('pop', 0.4, 0.45); sfx('hit', 0.9, 0.7); sfx('swish', HOOK_END - 0.1, 0.45); sfx('pop', HOOK_END + 0.1, 0.5); sfx('ding', HOOK_END + 0.35, 0.35)
mix = mix[:N]; mix = mix / max(1e-6, np.abs(mix).max()) * 0.9
wo = wave.open(OUT + '.wav', 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((mix * 32767).astype('<i2').tobytes()); wo.close()
enc = subprocess.Popen([FF, '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-i', OUT + '.wav',
                        '-c:v', 'libx264', '-crf', '16', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', OUT],
                       stdin=subprocess.PIPE)
for n in range(NF):
    t = n / FPS; img = Image.fromarray(src[n]).convert('RGBA')
    z = 1.0 + 0.14 * (1 - ease(t / 0.5)) + 0.05 * max(0, 1 - abs(t - 0.9) / 0.25)      # zoom d'impact au début et sur la 2e ligne
    if z > 1.001:
        cw, ch = W / z, H / z; img = img.resize((W, H), Image.LANCZOS, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2))
    if t < HOOK_END:   # accroche au-dessus de la tête (le logo Temu du carton reste visible)
        a = 1 - max(0, (t - HOOK_END + 0.2) / 0.2)
        put(img, H1, W / 2, 250, back(t / 0.3), a); put(img, H2, W / 2, 390, back((t - 0.8) / 0.25) * (1 + 0.04 * math.sin(t * 18)), a)
    else:
        put(img, GIFT, W / 2, 270, back((t - HOOK_END) / 0.3)); put(img, CODEC, W / 2, 900, back((t - HOOK_END - 0.15) / 0.3))
    if t < 0.12: img.alpha_composite(Image.new('RGBA', (W, H), (255, 255, 255, int(255 * (1 - t / 0.12)))))
    enc.stdin.write(img.convert('RGB').tobytes())
enc.stdin.close(); enc.wait(); os.remove(OUT + '.wav'); print('ok', OUT, round(DUR, 2), 's')
