# Vidéo « Gesetz Nr. X » : fond noir, bandeau rouge sombre, portrait ancien en bas à droite, mots qui apparaissent un à un
# (mots clés en jaune), titre d'ouverture avec glitch, nappe sonore grave. usage : gesetz.py dossier out.mp4
import sys, os, re, math, json, subprocess, shutil, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe(); DIR = sys.argv[1]; OUT = sys.argv[2]
C = json.load(open(os.path.join(DIR, 'config.json')))
W, H, FPS = 1080, 1920, 30; FD = '/home/user/skillora./temu/fonts/'
def F(n, s): return ImageFont.truetype(FD + n, s)
YEL = (255, 222, 30); PANEL = (52, 4, 6)
PX0, PY0, PX1, PY1 = 48, 680, 1032, 1240
# ---------- voix + calage
SR = 16000
def load16(f): return np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', os.path.join(DIR, f), '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(float)
DUR = len(load16(C['voice'])) / SR + 0.8
a = load16(C.get('align_voice', C['voice']))   # calage sur la voix sans la pause du marteau, décalé ensuite
e = np.array([np.sqrt(np.mean(a[i:i + 160] ** 2)) for i in range(0, len(a) - 160, 160)]); db = 20 * np.log10(e + 1); sp = db > db.max() - 33
gaps = []; i = 0
while i < len(sp):
    if not sp[i]:
        j = i
        while j < len(sp) and not sp[j]: j += 1
        if j - i >= 9 and i > 0 and j < len(sp): gaps.append(((i + j) / 200, (j - i) / 100))
        i = j
    else: i += 1
start = np.argmax(sp) / 100; end = (len(sp) - np.argmax(sp[::-1])) / 100
SENT = [s.strip().replace('Nr§', 'Nr.') for s in re.split(r'(?<=[.:!?–,])\s+', ' '.join(C['text']).replace('Nr.', 'Nr§')) if s.strip()]
def syl(w):
    w = re.sub('[^a-zäöüß0-9]', '', w.lower())
    if w.isdigit(): return 2
    return max(1, len(re.findall('[aeiouyäöü]+', w)))
wts = [sum(syl(w) + 0.35 for w in s.split()) for s in SENT]; tot = sum(wts); bounds = [start]; acc = 0
for k in range(len(SENT) - 1):
    acc += wts[k]; t = start + (end - start) * acc / tot
    near = [g for g in gaps if abs(g[0] - t) < 1.0 and g[0] > bounds[-1] + 0.3]
    bounds.append(min(near, key=lambda g: abs(g[0] - t) - g[1])[0] if near else t)
bounds.append(end); WORDS = []
for k, s in enumerate(SENT):
    t0, t1 = bounds[k] + (0.04 if k else 0), bounds[k + 1] - 0.06; ws = s.split(); ww = [syl(w) + 0.35 for w in ws]; tt = sum(ww); c = 0
    for w, q in zip(ws, ww): WORDS.append([w, t0 + (t1 - t0) * c / tt, t0 + (t1 - t0) * (c + q) / tt]); c += q
if C.get('gavel') and C.get('align_voice'):
    cut = C['gavel']['t'] - 0.2; sh = C['gavel']['dur']
    WORDS = [[w, t0 + (sh if t0 >= cut else 0), t1 + (sh if t0 >= cut else 0)] for w, t0, t1 in WORDS]; bounds = [b + (sh if b >= cut else 0) for b in bounds]
json.dump({'sent': SENT, 'bounds': bounds}, open(os.path.join(DIR, 'timing.json'), 'w'), ensure_ascii=False, indent=0)
# ---------- groupes de mots (max 4 lignes, retour à la ligne étroit, nouveau groupe à chaque fin de phrase)
TF = F('Poppins-ExtraBold.ttf', 62); MAXW = 560; LH = 84; TX, TY = 120, 790
NT = C.get('title_words', 3)          # les premiers mots (« Gesetz Nr. 10: ») = carte titre
HOT = re.compile(C['hot'], re.I)
groups = []; cur = []; lines = [[]]
def wlen(ws): return TF.getbbox(' '.join(WORDS[k][0] for k in ws))[2]
for k in range(NT, len(WORDS)):
    w = WORDS[k][0]
    if lines[-1] and wlen(lines[-1] + [k]) > MAXW: lines.append([])
    if len(lines) > 4: groups.append(cur); cur = []; lines = [[]]
    lines[-1].append(k); cur.append(k)
    if re.search(r'[.:!?]$', w): groups.append(cur); cur = []; lines = [[]]
if cur: groups.append(cur)
def layout(g):
    ls = [[]]
    for k in g:
        if ls[-1] and wlen(ls[-1] + [k]) > MAXW: ls.append([])
        ls[-1].append(k)
    pos = {}
    for li, l in enumerate(ls):
        x = TX
        for k in l: pos[k] = (x, TY + li * LH); x += TF.getbbox(WORDS[k][0] + ' ')[2]
    return pos
LAY = [layout(g) for g in groups]
# ---------- décor fixe
def ease(u): u = max(0, min(1, u)); return 1 - (1 - u) ** 3
base = Image.new('RGBA', (W, H), (0, 0, 0, 255))
pan = Image.new('RGBA', (PX1 - PX0, PY1 - PY0), PANEL + (255,)); ar = np.asarray(pan).astype(float)
yy, xx = np.mgrid[0:pan.height, 0:pan.width]; v = 1 - 0.55 * (((xx - pan.width / 2) / (pan.width / 2)) ** 2 * 0.6 + ((yy - pan.height / 2) / (pan.height / 2)) ** 2 * 0.4)
ar[..., :3] *= np.clip(v, 0.35, 1)[..., None]; pan = Image.fromarray(ar.astype('uint8'))
glow = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ImageDraw.Draw(glow).rounded_rectangle([PX0, PY0, PX1, PY1], 26, fill=(80, 6, 8, 160)); glow = glow.filter(ImageFilter.GaussianBlur(30))
base.alpha_composite(glow); m = Image.new('L', pan.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, pan.width - 1, pan.height - 1], 22, fill=255); base.paste(pan, (PX0, PY0), m)
por = Image.open(os.path.join(DIR, C['portrait'])).convert('RGBA'); ph = 400; por = por.resize((int(por.width * ph / por.height), ph), Image.LANCZOS)
base.alpha_composite(por, (PX1 - por.width - 10, PY1 - ph))
if C.get('handle'): ImageDraw.Draw(base).text((W / 2, PY1 + 50), C['handle'], font=F('Poppins-ExtraBold.ttf', 30), fill=(90, 70, 70), anchor='mm')
# ---------- marteau de juge (séquence détourée) pendant la pause
GV = C.get('gavel'); GIM = []
if GV:
    gi_ = json.load(open(os.path.join(DIR, 'gavel', 'info.json'))); GIM = [Image.open(os.path.join(DIR, 'gavel', f'g{k:02d}.png')).convert('RGBA') for k in range(gi_['n'])]
    gs = 520 / GIM[0].height; GIM = [im.resize((int(im.width * gs), int(im.height * gs)), Image.LANCZOS) for im in GIM]; G_IMP = GV['t'] + gi_['impact'] / FPS
def gavel_on(t): return GV and GV['t'] <= t < GV['t'] + GV['dur']
# ---------- images
T_TITLE_END = WORDS[NT][1] - 0.15
def frame(t):
    img = base.copy()
    if t < T_TITLE_END:   # carte titre : lettres qui entrent, puis glitch de sortie
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ttl = C['title']; sz = 150
        while True:
            f = F('Cinzel.ttf', sz); f.set_variation_by_axes([900])
            if f.getbbox(ttl)[2] < PX1 - PX0 - por.width - 40 or sz < 60: break
            sz -= 6
        d = ImageDraw.Draw(lay); sw = 1 - ease(t / 0.5)
        d.text(((PX0 + PX1 - por.width) / 2 + sw * 300, (PY0 + PY1) / 2), ttl, font=f, fill=(245, 240, 235, int(255 * ease(t / 0.3))), anchor='mm')
        k = (t - (T_TITLE_END - 0.35)) / 0.35
        if k > 0:
            arr = np.asarray(lay).copy(); rs = np.random.RandomState(int(t * 90))
            for _ in range(10):
                y = rs.randint(PY0, PY1 - 40); h = rs.randint(8, 40); arr[y:y + h] = np.roll(arr[y:y + h], int(rs.randint(-160, 160) * k), 1)
            lay = Image.fromarray(arr); lay.putalpha(lay.getchannel('A').point(lambda v: int(v * (1 - k))))
        img.alpha_composite(lay); return img.convert('RGB')
    if gavel_on(t):
        k = min(len(GIM) - 1, int((t - GV['t']) * FPS)); im = GIM[k]; tl = t - GV['t']
        al = min(1, tl / 0.08) * min(1, (GV['dur'] - tl) / 0.2); lay = im.copy(); lay.putalpha(lay.getchannel('A').point(lambda v: int(v * al)))
        img.alpha_composite(lay, (int((PX0 + PX1 - por.width) / 2 - im.width / 2 + 40), int(PY1 - 40 - im.height)))
        dt = t - G_IMP
        if 0 <= dt < 0.25:   # secousse + petit flash au moment du coup
            k2 = 1 - dt / 0.25; ox, oy = int(16 * k2 * math.sin(dt * 120)), int(12 * k2 * math.cos(dt * 95))
            img = Image.fromarray(np.roll(np.roll(np.asarray(img), oy, 0), ox, 1)); fl = Image.new('RGBA', (W, H), (255, 240, 220, int(35 * k2))); img.alpha_composite(fl)
        return img.convert('RGB')
    gi = max([i for i, g in enumerate(groups) if WORDS[g[0]][1] - 0.1 <= t] or [0]); g = groups[gi]
    nxt = WORDS[groups[gi + 1][0]][1] - 0.1 if gi + 1 < len(groups) else DUR
    out = ease((nxt - t) / 0.15) if gi + 1 < len(groups) else 1
    d = ImageDraw.Draw(img)
    for k in g:
        w, t0, t1 = WORDS[k]; u = (t - t0 + 0.04) / 0.18
        if u <= 0: continue
        al = ease(u) * out; x, y = LAY[gi][k]; col = YEL if HOT.search(re.sub(r'[^\wäöüß]', '', w)) else (255, 255, 255)
        d.text((x, y + (1 - ease(u)) * 14), w, font=TF, fill=tuple(int(c * al + PANEL[j] * 0.0 * (1 - al)) for j, c in enumerate(col)), anchor='la') if al >= 0.99 else None
        if al < 0.99:
            lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ImageDraw.Draw(lay).text((x, y + (1 - ease(u)) * 14), w, font=TF, fill=col + (int(255 * al),), anchor='la'); img.alpha_composite(lay)
    return img.convert('RGB')
tmp = OUT + '_fr'; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
for n in range(int(DUR * FPS)): frame(n / FPS).save(f'{tmp}/f{n:05d}.jpg', quality=92)
# ---------- son : voix + nappe grave (accords mineurs lents) + petit « whoosh » au glitch
SR2 = 44100; v = np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', os.path.join(DIR, C['voice']), '-ac', '1', '-ar', str(SR2), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(float) / 32768
N = int(DUR * SR2); tt = np.arange(N) / SR2; pad = np.zeros(N)
CH = [[57, 60, 64], [53, 57, 60], [55, 59, 62], [52, 55, 59]]; L = 4.0
for ci in range(int(DUR / L) + 1):
    for m_ in CH[ci % 4]:
        f0 = 440 * 2 ** ((m_ - 12 - 69) / 12); s0 = int(ci * L * SR2); s1 = min(N, int((ci + 1) * L * SR2 + 1.5 * SR2))
        if s0 >= N: continue
        x = tt[s0:s1] - ci * L; env = np.minimum(1, x / 1.2) * np.minimum(1, np.maximum(0, (L + 1.5 - x) / 1.5))
        pad[s0:s1] += (np.sin(2 * np.pi * f0 * x) + 0.3 * np.sin(2 * np.pi * f0 * 2 * x + 0.5)) * env
pad = np.convolve(pad, np.ones(40) / 40, 'same'); pad = pad / np.abs(pad).max() * 0.12
if C.get('music'):   # son fourni : en fond sous la voix, baissé quand elle parle
    mu = np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', os.path.join(DIR, C['music']), '-ac', '1', '-ar', str(SR2), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(float) / 32768
    mu = np.pad(mu, (0, max(0, N - len(mu))))[:N]; mu = mu / max(1e-6, np.abs(mu).max())
    vv = np.zeros(N); vv[:min(N, len(v))] = np.abs(v[:N]) > 0.03; env = np.convolve(vv, np.ones(int(0.3 * SR2)) / int(0.3 * SR2), 'same')
    pad = mu * C.get('music_gain', 0.22) * (1 - 0.45 * np.clip(env * 3, 0, 1))
mix = pad.copy(); mix[:len(v)] += v[:N]
w2 = wave.open('/home/user/skillora./motion/sfx/glitch.wav'); s = np.frombuffer(w2.readframes(w2.getnframes()), '<i2').astype(float) / 32768
if w2.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
i0 = int((T_TITLE_END - 0.35) * SR2); mix[i0:i0 + len(s)] += s[:N - i0] * 0.25
if GV:   # coup de marteau synthétisé : claquement bois + choc grave + petite réverbération
    n = int(1.2 * SR2); x = np.arange(n) / SR2; rs = np.random.RandomState(3)
    hit = sum(a_ * np.sin(2 * np.pi * f_ * x) * np.exp(-x / d_) for f_, a_, d_ in ((95, 1.0, 0.09), (190, 0.6, 0.06), (430, 0.55, 0.035), (870, 0.35, 0.02), (1650, 0.2, 0.012)))
    nz = rs.randn(n) * np.exp(-x / 0.006); nz = np.convolve(nz, np.ones(4) / 4, 'same'); hit = hit + 0.9 * nz
    rv = rs.randn(int(0.9 * SR2)) * np.exp(-np.arange(int(0.9 * SR2)) / SR2 / 0.25) * 0.02; hit = np.convolve(hit, np.r_[1, np.zeros(200), rv])[:n]
    hit = hit / np.abs(hit).max(); i0 = int(G_IMP * SR2); L = min(n, N - i0); mix[i0:i0 + L] += hit[:L] * 0.9
fd = int(0.8 * SR2); mix[-fd:] *= np.linspace(1, 0, fd); mix = mix / np.abs(mix).max() * 0.95
wo = wave.open(f'{tmp}/a.wav', 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR2); wo.writeframes((mix * 32767).astype('<i2').tobytes()); wo.close()
subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/f%05d.jpg', '-i', f'{tmp}/a.wav', '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
shutil.rmtree(tmp); print('ok', OUT, round(DUR, 2), [(round(b, 2), s) for b, s in zip(bounds, SENT)])
