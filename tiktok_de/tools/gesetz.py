# Vidéo « Gesetz Nr. X » : fond noir, bandeau rouge sombre, portrait ancien en bas à droite, mots qui apparaissent un à un
# (mots clés en jaune), titre d'ouverture avec glitch, nappe sonore grave. usage : gesetz.py dossier out.mp4
import sys, os, re, math, json, subprocess, shutil, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe(); DIR = sys.argv[1]; OUT = sys.argv[2]
C = json.load(open(os.path.join(DIR, 'config.json')))
HOTC = tuple(C.get('hot_color', (255, 222, 30)))   # couleur des mots clés des sous-titres
W, H, FPS = 1080, 1920, 30; FD = '/home/user/skillora./temu/fonts/'
def F(n, s): return ImageFont.truetype(FD + n, s)
YEL = (255, 222, 30); PANEL = (52, 4, 6)
PX0, PY0, PX1, PY1 = 48, 680, 1032, 1240
# ---------- voix + calage
SR = 16000
def load16(f): return np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', os.path.join(DIR, f), '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(float)
DUR = len(load16(C['voice'])) / SR + C.get('tail', 0.8)
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
SENT = [s.strip().replace('Nr§', 'Nr.') for s in re.split(r'(?<=[.:!?–,“])\s+', ' '.join(C['text']).replace('Nr.', 'Nr§')) if s.strip()]
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
SEGT = None
if C.get('segments'):   # calage manuel : [texte, début, fin] par morceau de phrase
    SENT = [x[0] for x in C['segments']]; SEGT = [(x[1], x[2]) for x in C['segments']]; bounds = [x[1] for x in C['segments']] + [C['segments'][-1][2]]
for k, s in enumerate(SENT):
    t0, t1 = SEGT[k] if SEGT else (bounds[k] + (0.04 if k else 0), bounds[k + 1] - 0.06); ws = s.split(); ww = [syl(w) + 0.35 for w in ws]; tt = sum(ww); c = 0
    for w, q in zip(ws, ww): WORDS.append([w, t0 + (t1 - t0) * c / tt, t0 + (t1 - t0) * (c + q) / tt]); c += q
if C.get('word_align'):   # temps exacts de chaque mot (align_tts.py) au lieu de la répartition par syllabes
    AW = json.load(open(os.path.join(DIR, C['word_align']))); j = 0
    for k, (w, _, _) in enumerate(WORDS):
        if not re.sub(r'[^\wäöüß]', '', w): WORDS[k][1:] = WORDS[k - 1][1:] if k else [0, 0]; continue   # « – » : suit le mot d'avant
        WORDS[k][1], WORDS[k][2] = AW[j][1], AW[j][2]; j += 1
if C.get('gavel') and C.get('align_voice'):
    cut = C['gavel']['t'] - 0.2; sh = C['gavel']['dur']
    WORDS = [[w, t0 + (sh if t0 >= cut else 0), t1 + (sh if t0 >= cut else 0)] for w, t0, t1 in WORDS]; bounds = [b + (sh if b >= cut else 0) for b in bounds]
json.dump({'sent': SENT, 'bounds': bounds}, open(os.path.join(DIR, 'timing.json'), 'w'), ensure_ascii=False, indent=0)
if os.environ.get('ALIGN_ONLY'): sys.exit(0)
# mots de la citation (entre „ et “) : couleur crème
QUOTE = set(); inq = False
for k, (w, _, _) in enumerate(WORDS):
    if '„' in w: inq = True
    if inq: QUOTE.add(k)
    if '“' in w or '"' in w: inq = False
QC = (242, 204, 150)
if C.get('quote_align') and QUOTE:   # citation : temps de chaque mot pris dans l'alignement (align_tts.py), pour le soulignement
    AW = json.load(open(os.path.join(DIR, C['quote_align']))); qk = sorted(QUOTE); aw = AW[-len(qk):]
    for k, (_, a0, a1) in zip(qk, aw):
        s_ = C['gavel']['dur'] if C.get('gavel') and a0 >= C['gavel']['t'] - 0.2 else 0; WORDS[k][1], WORDS[k][2] = a0 + s_, a1 + s_
# ---------- groupes de mots (max 4 lignes, retour à la ligne étroit, nouveau groupe à chaque fin de phrase)
TF = F('Poppins-ExtraBold.ttf', 62); MAXW = 560; LH = 84; TX, TY = 120, 790
NT = C.get('title_words', 3)          # les premiers mots (« Gesetz Nr. 10: ») = carte titre
HOT = re.compile(C['hot'], re.I)
groups = []; cur = []; lines = [[]]
def wlen(ws): return TF.getbbox(' '.join(WORDS[k][0] for k in ws))[2]
for k in range(NT, len(WORDS)):
    w = WORDS[k][0]
    if lines[-1] and wlen(lines[-1] + [k]) > MAXW: lines.append([])
    if len(lines) > 4 and not (C.get('quote_poem') and k in QUOTE): groups.append(cur); cur = []; lines = [[]]   # la citation reste entière
    lines[-1].append(k); cur.append(k)
    if re.search(r'[.:!?][“"]?$', w): groups.append(cur); cur = []; lines = [[]]
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
SUBS2 = C.get('subs') == 'v2'
if SUBS2:   # une page = plusieurs phrases tant qu'elles tiennent sur 4 lignes ; la citation commence toujours une nouvelle page
    SUBF = C.get('sub_font', 'Poppins-ExtraBold.ttf')   # police des sous-titres (changer de style d'une vidéo à l'autre)
    TF = F(SUBF, C.get('font', 66)); LH = int(TF.size * (1.12 if 'Bebas' in SUBF else 1.32)); MAXW = C.get('maxw', 480)
    def wrap(ws):   # lignes d'une page ; une nouvelle phrase commence toujours sur une nouvelle ligne
        ls = [[]]
        for k in ws:
            if ls[-1] and (wlen(ls[-1] + [k]) > MAXW or re.search(r'[.:!?][“"]?$', WORDS[ls[-1][-1]][0])): ls.append([])
            ls[-1].append(k)
        return ls
    def nlines(ws): return len(wrap(ws))
    def layout(g):
        pos = {}
        for li, l in enumerate(wrap(g)):
            x = TX
            for k in l: pos[k] = (x, TY + li * LH); x += TF.getbbox(WORDS[k][0] + ' ')[2]
        return pos
    MAXL = C.get('max_lines', 4)
    units = []; cur = []   # morceaux de phrase : coupés aux virgules, deux-points, tirets et fins de phrase
    for k in range(NT, len(WORDS)):
        if not re.sub(r'[^\wäöüß]', '', WORDS[k][0]): continue   # tiret « – » seul : pas affiché
        if '„' in WORDS[k][0] and cur: units.append(cur); cur = []
        cur.append(k)
        if re.search(r'[.,:;!?–][“"]?$', WORDS[k][0]) or '“' in WORDS[k][0]: units.append(cur); cur = []   # le tiret « – » reste collé au mot d'avant
    if cur: units.append(cur)
    split = []
    for un in units:   # un morceau trop long pour une page : coupé en mots
        while nlines(un) > MAXL:
            n = len(un)
            while nlines(un[:n]) > MAXL: n -= 1
            split.append(un[:n]); un = un[n:]
        split.append(un)
    groups = []; pg = []
    for un in split:
        newq = '„' in WORDS[un[0]][0]
        if pg and (newq or nlines(pg + un) > MAXL or any('“' in WORDS[k][0] for k in pg)): groups.append(pg); pg = []
        pg = pg + un
    if pg: groups.append(pg)
LAY = [layout(g) for g in groups]
if SUBS2:   # bloc centré verticalement dans le bandeau
    for gi_, g in enumerate(groups):
        n = nlines(g); y0 = (PY0 + PY1) / 2 - n * LH / 2 + 4
        LAY[gi_] = {k: (x, y0 + (y - TY)) for k, (x, y) in LAY[gi_].items()}
# ---------- décor fixe
def ease(u): u = max(0, min(1, u)); return 1 - (1 - u) ** 3
base = Image.new('RGBA', (W, H), (0, 0, 0, 255))
pan = Image.new('RGBA', (PX1 - PX0, PY1 - PY0), PANEL + (255,)); ar = np.asarray(pan).astype(float)
yy, xx = np.mgrid[0:pan.height, 0:pan.width]; v = 1 - 0.55 * (((xx - pan.width / 2) / (pan.width / 2)) ** 2 * 0.6 + ((yy - pan.height / 2) / (pan.height / 2)) ** 2 * 0.4)
ar[..., :3] *= np.clip(v, 0.35, 1)[..., None]; pan = Image.fromarray(ar.astype('uint8'))
glow = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ImageDraw.Draw(glow).rounded_rectangle([PX0, PY0, PX1, PY1], 26, fill=(80, 6, 8, 160)); glow = glow.filter(ImageFilter.GaussianBlur(30))
base.alpha_composite(glow); m = Image.new('L', pan.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, pan.width - 1, pan.height - 1], 22, fill=255); base.paste(pan, (PX0, PY0), m)
por = Image.open(os.path.join(DIR, C['portrait'])).convert('RGBA'); ph = C.get('portrait_h', 400); por = por.resize((int(por.width * ph / por.height), ph), Image.LANCZOS)
POR_XY = (PX1 - por.width - 10, PY1 - ph)
SWAP = C.get('cta', {}).get('swap') or bool(C.get('book'))   # la statue doit pouvoir sortir quand le livre arrive
if not SWAP: base.alpha_composite(por, POR_XY)
PMASK = Image.new('L', (W, H), 0); ImageDraw.Draw(PMASK).rounded_rectangle([PX0, PY0, PX1, PY1], 22, fill=255)   # rien ne dépasse du bandeau
BK = C.get('book')   # carte « livre » de fin : le livre remplace la statue pendant la phrase sur le livre, avec « Link in Bio »
if BK:
    BKIM = Image.open(os.path.join(DIR, BK.get('image', '../../livre/livre_3d.png'))).convert('RGBA'); bh = PY1 - PY0 - 40
    BKIM = BKIM.resize((int(BKIM.width * bh / BKIM.height), bh), Image.LANCZOS)
    BKGLOW = Image.new('RGBA', (BKIM.width + 240, BKIM.height + 120), (0, 0, 0, 0))
    ImageDraw.Draw(BKGLOW).ellipse([60, 30, BKGLOW.width - 60, BKGLOW.height - 30], fill=(230, 180, 90, 110)); BKGLOW = BKGLOW.filter(ImageFilter.GaussianBlur(45))
def draw_link(img, t):
    # « LINK IN BIO » DANS le bandeau (là où s'écrivent tous les textes), à gauche du livre : bouton doré qui arrive,
    # respire et reçoit un reflet ; petite flèche qui monte vers le profil. Remplace les sous-titres de la dernière phrase.
    u = t - BK['link_t']; k = min(1, max(0, u / 0.35)); e = 1 + 2.7 * (k - 1) ** 3 + 1.7 * (k - 1) ** 2
    if k <= 0: return
    cx = (PX0 + PX1 - BKIM.width - 30) / 2 + 10; cy = (PY0 + PY1) / 2
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    f1 = F('Poppins-ExtraBold.ttf', 44); d.text((cx, cy - 120), 'Alle 21 Gesetze', font=f1, fill=(245, 240, 235, int(255 * k)), anchor='mm')
    sc = e * (1 + 0.03 * math.sin(u * 5)); bw, bh_ = 220 * sc, 62 * sc
    d.rounded_rectangle([cx - bw - 6, cy - bh_ - 6, cx + bw + 6, cy + bh_ + 6], int(bh_ + 6), fill=(120, 80, 30, int(200 * k)))
    d.rounded_rectangle([cx - bw, cy - bh_, cx + bw, cy + bh_], int(bh_), fill=(222, 178, 92, int(255 * k)))
    ph = (u % 1.6) / 0.6
    if 0 <= ph <= 1:   # reflet sur le bouton
        sh = Image.new('L', (W, H), 0); sx = cx - bw + ph * 2 * bw
        ImageDraw.Draw(sh).polygon([(sx, cy - bh_), (sx + 40, cy - bh_), (sx - 20, cy + bh_), (sx - 60, cy + bh_)], fill=150)
        m = Image.new('L', (W, H), 0); ImageDraw.Draw(m).rounded_rectangle([cx - bw, cy - bh_, cx + bw, cy + bh_], int(bh_), fill=255)
        wl = Image.new('RGBA', (W, H), (255, 250, 230, 0)); wl.putalpha(Image.fromarray(np.minimum(np.asarray(sh.filter(ImageFilter.GaussianBlur(6))), np.asarray(m)))); lay.alpha_composite(wl)
    f2 = F('Poppins-ExtraBold.ttf', int(54 * sc)); d.text((cx + 22 * sc, cy + 2), 'LINK IN BIO', font=f2, fill=(30, 20, 10, int(255 * k)), anchor='mm')
    ax = cx - bw + 48 * sc; ay = cy + 18 * sc - 10 * abs(math.sin(u * 4))   # flèche qui monte
    d.polygon([(ax, ay - 34 * sc), (ax - 20 * sc, ay - 8 * sc), (ax - 7 * sc, ay - 8 * sc), (ax - 7 * sc, ay + 18 * sc), (ax + 7 * sc, ay + 18 * sc), (ax + 7 * sc, ay - 8 * sc), (ax + 20 * sc, ay - 8 * sc)], fill=(30, 20, 10, int(255 * k)))
    f3 = F('Poppins-ExtraBold.ttf', 36); d.text((cx, cy + 115), 'im Profil', font=f3, fill=(222, 178, 92, int(255 * min(1, max(0, (u - 0.3) / 0.3)))), anchor='mm')
    img.alpha_composite(lay)
def draw_book(img, t):
    if not BK or t < BK['t']: return
    t1 = CTA['t'] if CTA else DUR; u_in = min(1, (t - BK['t']) / 0.5); u_out = min(1, max(0, (t - t1) / 0.5))
    if u_out >= 1: return
    x = PX1 - BKIM.width - 30 + (W - PX1 + BKIM.width) * ((1 - u_in) ** 2 + u_out ** 2)
    y = PY0 + 20 + 8 * math.sin(t * 2.2)
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    gl = BKGLOW.copy(); gl.putalpha(BKGLOW.getchannel('A').point(lambda v: int(v * (0.75 + 0.25 * math.sin(t * 3)) * u_in)))   # halo doré qui respire
    lay.alpha_composite(gl, (int(x + BKIM.width / 2 - gl.width / 2), int(y + BKIM.height / 2 - gl.height / 2)))
    bk = BKIM.copy(); ph = ((t - BK['t'] - 0.6) % 2.2) / 0.7   # reflet qui balaie la couverture toutes les 2,2 s
    if 0 <= ph <= 1:
        sh = Image.new('L', bk.size, 0); sx = -bk.width * 0.5 + ph * bk.width * 2
        ImageDraw.Draw(sh).polygon([(sx, 0), (sx + 70, 0), (sx - 90, bk.height), (sx - 160, bk.height)], fill=120)
        sh = Image.fromarray(np.minimum(np.asarray(sh.filter(ImageFilter.GaussianBlur(12))), np.asarray(bk.getchannel('A'))))
        wl = Image.new('RGBA', bk.size, (255, 248, 225, 0)); wl.putalpha(sh); bk.alpha_composite(wl)
    lay.alpha_composite(bk.rotate(2 * math.sin(t * 1.4), resample=Image.BICUBIC, expand=False), (int(x), int(y)))
    lay.putalpha(Image.fromarray(np.minimum(np.asarray(lay.getchannel('A')), np.asarray(PMASK)))); img.alpha_composite(lay)
    a = min(1, max(0, (t - BK['t'] - 0.4) / 0.3)) * (1 - u_out)   # ancienne pastille sous le bandeau : DÉSACTIVÉE par défaut (écrite dans la bande noire → 10 vues)
    if BK.get('pill') and a > 0.01:
        d = ImageDraw.Draw(img); f = F('Poppins-ExtraBold.ttf', 50); txt = BK.get('label', 'Das Buch: Link in Bio'); tw = f.getbbox(txt)[2]; by = PY1 + 95 + 6 * math.sin(t * 5)
        d.rounded_rectangle([W / 2 - tw / 2 - 40, by - 50, W / 2 + tw / 2 + 40, by + 50], 50, fill=(201, 162, 90, int(255 * a)))
        d.text((W / 2, by), txt, font=f, fill=(25, 18, 10, int(255 * a)), anchor='mm')
def draw_portrait(img, t):
    if not SWAP: return
    dx = 0
    t_out = BK['t'] if BK else (CTA['t'] if CTA else None)
    if t_out is not None and t > t_out: u = (t - t_out) / 0.6; dx = (W - POR_XY[0]) * (min(1, max(0, u)) ** 2)   # glisse vers la droite et sort
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); lay.alpha_composite(por, (int(POR_XY[0] + dx), POR_XY[1]))
    lay.putalpha(Image.fromarray(np.minimum(np.asarray(lay.getchannel('A')), np.asarray(PMASK)))); img.alpha_composite(lay)
if C.get('handle'): ImageDraw.Draw(base).text((W / 2, PY1 + 50), C['handle'], font=F('Poppins-ExtraBold.ttf', 30), fill=(90, 70, 70), anchor='mm')
# ---------- marteau de juge (séquence détourée) pendant la pause
GV = C.get('gavel'); GIM = []
if GV:
    gi_ = json.load(open(os.path.join(DIR, 'gavel', 'info.json'))); GIM = [Image.open(os.path.join(DIR, 'gavel', f'g{k:02d}.png')).convert('RGBA') for k in range(gi_['n'])]
    GSPD = max(1.0, (gi_['n'] / FPS) / GV['dur'])     # pause plus courte que l'animation : on la joue plus vite
    gs = 520 / GIM[0].height; GIM = [im.resize((int(im.width * gs), int(im.height * gs)), Image.LANCZOS) for im in GIM]; G_IMP = GV['t'] + gi_['impact'] / FPS / GSPD
def gavel_on(t): return GV and GV['t'] <= t < GV['t'] + GV['dur']
# ---------- bouton d'abonnement animé
CTA = C.get('cta')
def cta_button(img, t):
    # style TikTok : avatar rond bord blanc + pastille rose « + » qui devient une coche au clic, onde au toucher
    if not CTA or t < CTA['t']: return
    u = t - CTA['t']; tc = CTA.get('click', 1.2); clicked = u > tc
    k = min(1, u / 0.35); sc = max(0.05, 1 + 2.7 * (k - 1) ** 3 + 1.7 * (k - 1) ** 2)
    R = int(CTA.get('r', 125) * sc); cx, cy = CTA.get('x', W / 2), CTA.get('y', PY1 + 190)
    if CTA.get('swap'):
        R = CTA.get('r', 125); k2 = min(1, max(0, (u - 0.15) / 0.6)); e2 = 1 + 2.7 * (k2 - 1) ** 3 + 1.7 * (k2 - 1) ** 2
        cx = (W + R + 20) + (cx - (W + R + 20)) * e2
    av = Image.open(os.path.join(DIR, CTA.get('avatar', C['portrait']))).convert('RGBA'); s0 = min(av.size); av = av.crop(((av.width - s0) // 2, 0, (av.width + s0) // 2, s0)).resize((2 * R, 2 * R), Image.LANCZOS)
    bgc = Image.new('RGBA', av.size, (40, 40, 45, 255)); bgc.alpha_composite(av); m = Image.new('L', av.size, 0); ImageDraw.Draw(m).ellipse([0, 0, 2 * R - 1, 2 * R - 1], fill=255)
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.ellipse([cx - R - 7, cy - R - 7, cx + R + 7, cy + R + 7], fill=(255, 255, 255, 255)); lay.paste(bgc, (int(cx - R), int(cy - R)), m)
    pr = int(42 * sc); px, py = cx, cy + R
    if clicked and u - tc < 0.5:   # onde du toucher
        q = (u - tc) / 0.5; rr = pr + 70 * q; d.ellipse([px - rr, py - rr, px + rr, py + rr], outline=(255, 255, 255, int(200 * (1 - q))), width=5)
    press = 0.85 if clicked and u - tc < 0.12 else 1.0; pr = int(pr * press)
    if not clicked:
        d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=(254, 44, 85, 255))
        d.line([px - pr * 0.45, py, px + pr * 0.45, py], fill=(255, 255, 255), width=max(2, int(7 * sc))); d.line([px, py - pr * 0.45, px, py + pr * 0.45], fill=(255, 255, 255), width=max(2, int(7 * sc)))
    else:
        d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=(255, 255, 255, 255))
        d.line([px - pr * 0.45, py + 2, px - pr * 0.1, py + pr * 0.35], fill=(254, 44, 85), width=7); d.line([px - pr * 0.1, py + pr * 0.35, px + pr * 0.5, py - pr * 0.35], fill=(254, 44, 85), width=7)
    if u > 0.3:
        lab = 'Gefolgt' if clicked else 'Folgen'; al = int(255 * min(1, (u - 0.3) / 0.3))
        d.text((cx, py + pr + 45), lab, font=F('Poppins-ExtraBold.ttf', 46), fill=(255, 255, 255, al), anchor='mm')
    img.alpha_composite(lay)
# ---------- citation en « poème » : phrase entière en italique, un trait jaune souligne chaque mot pendant qu'il est dit
QF = F('PlayfairDisplay-Italic.ttf', 66); QF.set_variation_by_axes([500]); QLH = 92
def quote_poem(img, g, t):
    ws = [WORDS[k][0] for k in g]; ls = [[]]
    for k in g:
        if ls[-1] and QF.getbbox(" ".join(WORDS[j][0] for j in ls[-1] + [k]))[2] > MAXW - 20: ls.append([])
        ls[-1].append(k)
    t0 = WORDS[g[0]][1] - 0.25; u = ease((t - t0) / 0.5); y0 = (PY0 + PY1) / 2 - len(ls) * QLH / 2 + (1 - u) * 20
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for li, l in enumerate(ls):
        x = TX - 20; y = y0 + li * QLH
        for k in l:
            w, a0, a1 = WORDS[k]; ww = QF.getbbox(w)[2]; p = min(1, max(0, (t - a0) / max(0.05, a1 - a0)))
            d.text((x, y), w, font=QF, fill=QC + (int(255 * u),), anchor='la')
            if p > 0:   # trait : vif sous le mot dit, plus discret une fois passé
                bx0 = x + 4; bx1 = bx0 + (ww - 8) * p; by = y + 78; al = 255 if p < 1 or t < a1 + 0.15 else 110
                d.line([bx0, by, bx1, by], fill=YEL + (al,), width=6); d.ellipse([bx1 - 3, by - 3, bx1 + 3, by + 3], fill=YEL + (al,))
            x += ww + QF.getbbox(' ')[2] + 4
    img.alpha_composite(lay)
# ---------- images
T_TITLE_END = WORDS[NT][1] - 0.15
def frame(t):
    img = base.copy(); draw_portrait(img, t); draw_book(img, t)
    if t < T_TITLE_END:   # carte titre : lettres qui entrent, puis glitch de sortie
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ttl = C['title']; sz = 150
        while True:
            f = F('Cinzel.ttf', sz); f.set_variation_by_axes([900])
            if f.getbbox(ttl)[2] < PX1 - PX0 - por.width * C.get('title_overlap', 1.0) - 40 or sz < 60: break
            sz -= 6
        d = ImageDraw.Draw(lay); sw = 1 - ease(t / 0.5)
        d.text(((PX0 + PX1 - por.width * C.get('title_overlap', 1.0)) / 2 + sw * 300, (PY0 + PY1) / 2), ttl, font=f, fill=(245, 240, 235, int(255 * ease(t / 0.3))), anchor='mm')
        k = (t - (T_TITLE_END - 0.35)) / 0.35
        if k > 0:
            arr = np.asarray(lay).copy(); rs = np.random.RandomState(int(t * 90))
            for _ in range(10):
                y = rs.randint(PY0, PY1 - 40); h = rs.randint(8, 40); arr[y:y + h] = np.roll(arr[y:y + h], int(rs.randint(-160, 160) * k), 1)
            lay = Image.fromarray(arr); lay.putalpha(lay.getchannel('A').point(lambda v: int(v * (1 - k))))
        img.alpha_composite(lay); return img.convert('RGB')
    if gavel_on(t):
        k = min(len(GIM) - 1, int((t - GV['t']) * FPS * GSPD)); im = GIM[k]; tl = t - GV['t']
        al = min(1, tl / 0.08) * min(1, (GV['dur'] - tl) / 0.2); lay = im.copy(); lay.putalpha(lay.getchannel('A').point(lambda v: int(v * al)))
        img.alpha_composite(lay, (int((PX0 + PX1 - por.width) / 2 - im.width / 2 + 40), int(PY1 - 40 - im.height)))
        dt = t - G_IMP
        if 0 <= dt < 0.25:   # secousse + petit flash au moment du coup
            k2 = 1 - dt / 0.25; ox, oy = int(16 * k2 * math.sin(dt * 120)), int(12 * k2 * math.cos(dt * 95))
            img = Image.fromarray(np.roll(np.roll(np.asarray(img), oy, 0), ox, 1)); fl = Image.new('RGBA', (W, H), (255, 240, 220, int(35 * k2))); img.alpha_composite(fl)
        return img.convert('RGB')
    cta_button(img, t)
    if CTA and CTA.get('hide_text') and t >= CTA['t']: return img.convert('RGB')
    if BK and BK.get('link_t') and t >= BK['link_t'] - 0.05: draw_link(img, t); return img.convert('RGB')
    gi = max([i for i, g in enumerate(groups) if WORDS[g[0]][1] - 0.1 <= t] or [0]); g = groups[gi]
    if C.get('quote_poem') and all(k in QUOTE for k in g): quote_poem(img, g, t); return img.convert('RGB')
    if SUBS2:
        nxt = WORDS[groups[gi + 1][0]][1] - 0.02 if gi + 1 < len(groups) else DUR
        out = min(1, max(0, (nxt - t) / 0.08)) if gi + 1 < len(groups) else 1
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        for k in g:
            w, t0, t1 = WORDS[k]; u = (t - t0 + 0.03) / 0.12
            if u <= 0: continue
            x, y = LAY[gi][k]; col = HOTC if HOT.search(re.sub(r'[^\wäöüß]', '', w)) else (QC if k in QUOTE else (255, 255, 255))
            if C.get('sub_anim') == 'rise':   # le mot monte doucement en apparaissant (au lieu du « pop »)
                k2 = ease(min(1, u)); dl.text((x, y + (1 - k2) * 22), w, font=TF, fill=col + (int(255 * k2 * out),), anchor='la')
                if col == HOTC and k2 >= 1:   # trait sous les mots clés
                    ww = TF.getbbox(w.rstrip('.,:;!?“'))[2]; dl.rectangle([x, y + TF.size * 0.98, x + ww * min(1, (t - t0) / 0.25), y + TF.size * 0.98 + 5], fill=HOTC + (int(200 * out),))
                continue
            sc_ = 1 + 0.12 * math.sin(min(1, u) * math.pi) if u < 1 else 1; f_ = TF if sc_ == 1 else F(SUBF, int(TF.size * sc_))
            ww = TF.getbbox(w)[2]; dw = (f_.getbbox(w)[2] - ww) / 2
            dl.text((x - dw, y - (f_.size - TF.size) / 2), w, font=f_, fill=col + (int(255 * min(1, u) * out),), anchor='la')
        img.alpha_composite(lay); return img.convert('RGB')
    nxt = WORDS[groups[gi + 1][0]][1] - 0.1 if gi + 1 < len(groups) else DUR
    out = ease((nxt - t) / 0.15) if gi + 1 < len(groups) else 1
    d = ImageDraw.Draw(img)
    for k in g:
        w, t0, t1 = WORDS[k]; u = (t - t0 + 0.04) / 0.18
        if u <= 0: continue
        al = ease(u) * out; x, y = LAY[gi][k]; col = YEL if HOT.search(re.sub(r'[^\wäöüß]', '', w)) else (QC if k in QUOTE else (255, 255, 255))
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
    if C.get('gavel_sfx'):   # vrai son de marteau fourni
        w3 = wave.open(os.path.join(DIR, C['gavel_sfx'])); hit = np.frombuffer(w3.readframes(w3.getnframes()), '<i2').astype(float) / 32768; n = len(hit)
    hit = hit / np.abs(hit).max(); i0 = int(G_IMP * SR2); L = min(n, N - i0); mix[i0:i0 + L] += hit[:L] * 0.9
if CTA:   # petit clic sur le bouton
    w4 = wave.open('/home/user/skillora./motion/sfx/click.wav'); ck = np.frombuffer(w4.readframes(w4.getnframes()), '<i2').astype(float) / 32768
    if w4.getnchannels() == 2: ck = ck.reshape(-1, 2).mean(1)
    i0 = int((CTA['t'] + CTA.get('click', 1.2)) * SR2); L = min(len(ck), N - i0); mix[i0:i0 + L] += ck[:L] * 0.4
fd = int(0.8 * SR2); mix[-fd:] *= np.linspace(1, 0, fd); mix = mix / np.abs(mix).max() * 0.95
wo = wave.open(f'{tmp}/a.wav', 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR2); wo.writeframes((mix * 32767).astype('<i2').tobytes()); wo.close()
subprocess.run([FF, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/f%05d.jpg', '-i', f'{tmp}/a.wav', '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', OUT], check=True)
shutil.rmtree(tmp); print('ok', OUT, round(DUR, 2), [(round(b, 2), s) for b, s in zip(bounds, SENT)])
