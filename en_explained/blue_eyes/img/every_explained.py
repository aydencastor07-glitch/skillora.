def gone(t, t1, d=0.15): return 1 - since(t, t1 - d, d) if t1 else 1
def sub(img, alpha, fn):
    if alpha <= 0.01: return
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); fn(lay, ImageDraw.Draw(lay))
    if alpha < 0.99: lay.putalpha(lay.getchannel('A').point(lambda v: int(v * alpha)))
    img.alpha_composite(lay)
def sun(d, cx, cy, r, t, p=1.0):
    if p <= 0: return
    circ(d, cx, cy, r * back(p), INK, YEL + (255,), 6)
    for k in range(10): a = k * math.pi / 5 + t * 0.4; line(d, cx + (r + 18) * math.cos(a), cy + (r + 18) * math.sin(a), cx + (r + 18 + 34 * ease(p)) * math.cos(a), cy + (r + 18 + 34 * ease(p)) * math.sin(a), (240, 170, 20), 7)
def globe(d, cx, cy, r, p=1.0):
    if p <= 0: return
    circ(d, cx, cy, r * back(p), INK, (90, 170, 235, 255), 7)
    for (dx, dy, rr) in ((-0.35, -0.3, 0.33), (0.3, 0.1, 0.38), (-0.2, 0.42, 0.22)): circ(d, cx + dx * r * back(p), cy + dy * r * back(p), rr * r * back(p), None, (90, 180, 90, 255))
    circ(d, cx, cy, r * back(p), INK, None, 7)
def drop_(d, cx, cy, r, col):
    d.ellipse([S(cx - r), S(cy - r), S(cx + r), S(cy + r)], fill=col + (255,), outline=INK, width=S(6))
    d.polygon([(S(cx - r * 0.9), S(cy - r * 0.4)), (S(cx), S(cy - r * 2.1)), (S(cx + r * 0.9), S(cy - r * 0.4))], fill=col + (255,)); line(d, cx - r * 0.93, cy - r * 0.38, cx, cy - r * 2.1, INK, 6); line(d, cx + r * 0.93, cy - r * 0.38, cx, cy - r * 2.1, INK, 6)
def calendar(img, d, cx, cy, l1, l2, p):
    if p <= 0: return
    s = back(p); w, h = 420 * s, 260 * s
    d.rounded_rectangle([S(cx - w / 2), S(cy - h / 2), S(cx + w / 2), S(cy + h / 2)], S(18), fill=WHITE + (255,), outline=INK, width=S(7))
    d.rectangle([S(cx - w / 2 + 4), S(cy - h / 2 + 4), S(cx + w / 2 - 4), S(cy - h / 2 + 60 * s)], fill=RED + (255,))
    for k in (-1, 1): line(d, cx + k * 120 * s, cy - h / 2 - 22 * s, cx + k * 120 * s, cy - h / 2 + 22 * s, INK, 10)
    text(img, (cx, cy + 10 * s), l1, AF(64 * s), INK); text(img, (cx, cy + 85 * s), l2, AF(40 * s), INK)
# ---------- repères temporels
T = dict(every=tw('every'), explained=tw('explained'), blue=tw('blue'), heres=tw("here's"), weird=tw('weird'), zero=tw('zero'), pigment=tw('pigment'), none=tw('none'),
         brown=tw('brown'), packed=tw('packed'), melanin=tw('melanin'), dark=tw('dark'), blue3=tw('blue', 2), almost=tw('almost'), so=tw('so'), where=tw('where'),
         light=tw('light'), when=tw('when'), iris=tw('iris'), fibers=tw('fibers'), scatter=tw('scatter'), back_=tw('back'), same=tw('same'), sky=tw('sky'),
         stranger=tw('stranger'), scientists=tw('scientists'), blueeyed=tw('blue-eyed'), earth=tw('earth'), one=tw('one'), single=tw('single'), ancestor=tw('ancestor'),
         one2=tw('one', 1), mutation=tw('mutation'), six=tw('six'), years=tw('years'), copied=tw('copied'), hundreds=tw('hundreds'), millions=tw('millions'),
         so2=tw('so…') or tw('so', 1), what=tw('what'), eyes_end=WORDS[-1][1], and_=tw('and'))
for k, v in T.items():
    if v is None: print('mot introuvable :', k)
SC = [0, T['blue'] - 0.15, T['heres'] - 0.12, T['brown'] - 0.15, T['so'] - 0.12, T['when'] - 0.12, T['and_'] - 0.1, T['one2'] - 0.12, T['so2'] - 0.12, DUR]
PUNCH = [(T['zero'], 0.07), (T['none'], 0.05), (T['light'], 0.05), (T['stranger'], 0.06), (T['ancestor'], 0.05), (T['millions'], 0.04)]
def camera(t, sc):
    a0, a1 = SC[sc], SC[sc + 1]; z = 1.0 + 0.03 * eio((t - a0) / max(1, a1 - a0))
    for t0, amp in PUNCH:
        if t0 and 0 <= t - t0 < 0.6: z += amp * math.exp(-(t - t0) * 7) * min(1, (t - t0) / 0.05)
    return z
# ---------- les scènes (fond blanc, une idée = une image)
def scene(img, d, sc, t):
    CX = W / 2; u0 = t - SC[sc]
    if sc == 0:   # carte de série
        word(img, (CX, 470), 'EVERY EYE COLOR', 92, INK, t, SC[0] + 0.05); word(img, (CX, 580), 'EXPLAINED', 92, INK, t, T['explained'] - 0.1)
        show(img, 1, CX, 1080, 880, 880, 0.1, t)
        if u0 > 0.8:
            for k, (lab, x, y) in enumerate((('BLUE', 330, 1095), ('BROWN', 750, 1095), ('GREEN', 330, 1505), ('TWO COLORS', 750, 1505))): word(img, (x, y), lab, 44, INK, t, 0.8 + k * 0.08)
    elif sc == 1:  # sujet + mascotte
        word(img, (CX, 470), 'BLUE EYES', 130, BLUE, t, SC[1] + 0.05); show(img, 2, CX, 1000, 860, 760, SC[1], t)
    elif sc == 2:  # aucun pigment bleu
        word(img, (CX, 470), "HERE'S THE WEIRD PART", 66, INK, t, T['heres'], font='H') if t < T['zero'] - 0.1 else None
        k = since(t, T['weird'], 0.35); drop_(d, CX, 960, 140 * back(k), BLUE) if k > 0 else None
        if t > T['zero'] - 0.05:
            word(img, (CX, 470), 'ZERO', 180, RED, t, T['zero'] - 0.03); word(img, (CX, 1260), 'BLUE PIGMENT', 104, INK, t, T['pigment'] - 0.05)
        if T['none'] and t > T['none'] - 0.05: cross(d, CX, 880, 210, since(t, T['none'] - 0.05, 0.3), RED, 18); word(img, (CX, 1400), 'NONE.', 96, RED, t, T['none'])
    elif sc == 3:  # iris marron plein de mélanine, iris bleu presque vide
        show(img, 3, CX, 1020, 820, 760, T['brown'] - 0.1, t)
        word(img, (310, 1440), 'BROWN', 80, BROWN, t, T['brown']); word(img, (770, 1440), 'BLUE', 80, BLUE, t, T['blue3'])
        if T['melanin'] and t > T['melanin'] - 0.15:
            show(img, 4, 230, 520, 240, 240, T['melanin'] - 0.15, t); word(img, (560, 480), 'MELANIN', 96, BROWN, t, T['melanin']); word(img, (560, 570), 'a dark pigment', 54, GREY, t, T['dark'], font='H')
        if T['almost'] and t > T['almost'] - 0.05: word(img, (770, 1530), 'ALMOST NONE', 64, RED, t, T['almost'])
    elif sc == 4:  # d'où vient le bleu ? la lumière
        stick(d, 380, 1380, 1.25, 'think', 'o', clamp(u0 / 0.4), t)
        k = since(t, T['where'], 0.3)
        if k > 0: text(img, (560, 760), '?', AF(200), INK, k, rot=8 * math.sin(t * 6))
        word(img, (CX, 470), 'WHERE DOES THE BLUE', 76, INK, t, T['where']); word(img, (CX, 570), 'COME FROM?', 76, BLUE, t, T['where'] + 0.3)
        if T['light'] and t > T['light'] - 0.15: sun(d, 790, 820, 110, t, since(t, T['light'] - 0.15, 0.35)); word(img, (790, 1080), 'LIGHT', 130, (240, 170, 20), t, T['light'])
    elif sc == 5:  # la lumière se diffuse dans les fibres de l'iris ; comme le ciel
        A = gone(t, T['same'] - 0.12)
        def iris(lay, dl):
            show(lay, 5, CX, 1000, 900, 980, SC[5] + 0.05, t)
            word(lay, (CX, 440), 'LIGHT ENTERS YOUR IRIS', 70, INK, t, T['iris'] - 0.3)
            if T['fibers'] and t > T['fibers'] - 0.1: word(lay, (800, 1460), 'TINY FIBERS', 64, INK, t, T['fibers']); arrow(dl, 800, 1410, 640, 1180, INK, 7, since(t, T['fibers'], 0.35))
            if T['scatter'] and t > T['scatter'] - 0.05: word(lay, (300, 540), 'BLUE BOUNCES BACK', 64, BLUE, t, T['scatter'])
        sub(img, A, iris)
        if T['same'] and t > T['same'] - 0.15:
            k = since(t, T['same'] - 0.15, 0.35); d.rectangle([S(0), S(360), S(W), S(360 + 900 * ease(k))], fill=SKY + (255,))
            if k >= 1:
                sun(d, 830, 520, 80, t); [circ(d, x, 640 + 20 * math.sin(t + x), 46, None, WHITE + (255,)) for x in (220, 280, 340)]
                d.rectangle([S(0), S(1260), S(W), S(1300)], fill=(120, 200, 110, 255)); stick(d, CX, 1270, 1.2, 'up', 'smile', 1, t, eyes=BLUE)
            word(img, (CX, 1420), 'SAME REASON THE SKY IS BLUE', 66, INK, t, T['sky'] - 0.1)
    elif sc == 6:  # ça devient plus étrange : un seul ancêtre
        A = gone(t, T['scientists'] - 0.1); B = gone(t, T['one'] - 0.12) if t > T['scientists'] - 0.2 else 0
        sub(img, A, lambda lay, dl: word(lay, (CX, 900), 'It gets stranger', 120, INK, t, T['and_'] + 0.1, font='H'))
        def world(lay, dl):
            word(lay, (CX, 470), 'SCIENTISTS BELIEVE', 74, INK, t, T['scientists'], font='H')
            globe(dl, CX, 960, 230, since(t, T['blueeyed'] - 0.3, 0.4) if T['blueeyed'] else 0)
            for j in range(8):
                a = j * math.pi / 4 + 0.2; q = since(t, T['blueeyed'] + j * 0.08, 0.3) if T['blueeyed'] else 0
                if q > 0: stick(dl, CX + 370 * math.cos(a), 960 + 340 * math.sin(a) + 120, 0.42, 'stand', 'smile', q, t, eyes=BLUE)
            word(lay, (CX, 1440), 'EVERY BLUE-EYED PERSON', 70, BLUE, t, T['blueeyed'])
        sub(img, B, world)
        if T['one'] and t > T['one'] - 0.15:
            show(img, 7, CX, 1000, 780, 780, T['one'] - 0.15, t); word(img, (CX, 470), 'ONE SINGLE', 110, INK, t, T['one']); word(img, (CX, 590), 'ANCESTOR', 110, BLUE, t, T['ancestor'])
    elif sc == 7:  # une mutation il y a 6 000–10 000 ans, copiée des centaines de millions de fois
        A = gone(t, T['copied'] - 0.12)
        def dna(lay, dl):
            show(lay, 6, 300, 1000, 380, 980, SC[7] + 0.05, t)
            word(lay, (740, 600), 'ONE TINY', 96, INK, t, T['tiny'] if 'tiny' in T else T['one2'] + 0.3); word(lay, (740, 710), 'MUTATION', 96, BLUE, t, T['mutation'])
            calendar(lay, dl, 740, 1100, '6,000–10,000', 'YEARS AGO', since(t, T['six'] - 0.1, 0.4) if T['six'] else 0)
        sub(img, A, dna)
        if T['copied'] and t > T['copied'] - 0.15:   # arbre : chaque génération copie la mutation
            rows = 6
            for r in range(rows):
                n = 2 ** r if r < 5 else 24; y = 520 + r * 150; q = since(t, T['copied'] + r * 0.32, 0.3)
                for j in range(n):
                    x = CX + (j - (n - 1) / 2) * min(150, 980 / max(1, n)); s = 0.32 if r < 4 else 0.22
                    if q > 0: stick(d, x, y + 360 * s, s, 'stand', 'smile', q, t, eyes=BLUE)
            word(img, (CX, 1440), 'HUNDREDS OF MILLIONS', 76, BLUE, t, T['hundreds'])
    elif sc == 8:  # question finale
        show(img, 1, CX, 1050, 760, 760, SC[8] + 0.05, t)
        word(img, (CX, 470), 'WHAT COLOR', 120, INK, t, T['what']); word(img, (CX, 590), 'ARE YOUR EYES?', 104, BLUE, t, T['what'] + 0.5)
        k = since(t, T['what'] + 0.8, 0.3)
        if k > 0: d.rounded_rectangle([S(CX - 330), S(1460), S(CX + 330), S(1560)], S(50), fill=(240, 240, 245, int(255 * k)), outline=INK, width=S(5)); text(img, (CX, 1510), 'Tell me in the comments', HF(52), INK, k)
SOURCE = (T['scientists'] - 0.2, T['so2'] - 0.2)
def draw(t):
    sc = max(i for i in range(len(SC) - 1) if t >= SC[i])
    lay = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    scene(lay, d, sc, t)
    if SOURCE[0] <= t < SOURCE[1]: text(lay, (W / 2, 1700), 'Source: Eiberg et al., University of Copenhagen (2008)', HF(34), GREY, min(since(t, SOURCE[0], 0.3), 1 - since(t, SOURCE[1] - 0.3, 0.3)))
    tout = clamp((SC[sc + 1] - t) / 0.12) if sc < len(SC) - 2 else 1      # coupe nette : l'image s'efface sur place
    if tout < 1: lay.putalpha(lay.getchannel('A').point(lambda v: int(v * tout)))
    img = Image.new('RGBA', (W * SS, H * SS), BG + (255,)); img.alpha_composite(lay)
    z = camera(t, sc); cw_, ch_ = W * SS / z, H * SS / z; cx, cy = W * SS / 2, H * SS * 0.5
    return img.convert('RGB').resize((W * K, H * K), Image.LANCZOS, box=(cx - cw_ / 2, cy - ch_ / 2, cx + cw_ / 2, cy + ch_ / 2))
def frame_bytes(n): return draw(n / FPS).tobytes()
if __name__ == '__main__':
    if os.environ.get('PREVIEW'):
        for ts in os.environ['PREVIEW'].split(','): draw(float(ts)).resize((W, H), Image.LANCZOS).save(f'{OUT}_{ts}.jpg', quality=88)
        sys.exit(0)
    TMP = OUT + '_fr'; shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP); NF = int(DUR * FPS)
    N = int(DUR * SR); mix_ = np.zeros(N); mix_[:len(VOICE)] += VOICE
    def sfx(name, t0, g):
        if t0 is None: return
        w = wave.open(SFXD + name + '.wav'); s = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float) / 32768
        if w.getnchannels() == 2: s = s.reshape(-1, 2).mean(1)
        if w.getframerate() != SR: s = np.interp(np.arange(0, len(s), w.getframerate() / SR), np.arange(len(s)), s)
        i0 = int(max(0, t0) * SR); L = min(len(s), N - i0); mix_[i0:i0 + L] += s[:L] * g
    for t0 in SC[1:-1]: sfx('swish', t0, 0.08)
    sfx('pop', T['explained'], 0.1); sfx('hit', T['zero'] - 0.03, 0.3); sfx('pop', T['none'], 0.15); sfx('pop', T['melanin'], 0.1); sfx('pop', T['almost'], 0.1)
    sfx('shine', T['light'] - 0.1, 0.15); sfx('swish', T['scatter'], 0.12); sfx('pop', T['sky'], 0.1); sfx('zoom1', T['stranger'] - 0.2, 0.15); sfx('ding', T['ancestor'], 0.12)
    sfx('pop', T['mutation'], 0.12); sfx('tap', T['six'], 0.1); sfx('shine', T['hundreds'], 0.12); sfx('pop', T['what'], 0.12)
    fd = int(0.3 * SR); mix_[-fd:] *= np.linspace(1, 0, fd); mix_ = mix_ / max(1e-6, np.abs(mix_).max()) * 0.92
    wo = wave.open(f'{TMP}/a.wav', 'wb'); wo.setnchannels(1); wo.setsampwidth(2); wo.setframerate(SR); wo.writeframes((mix_ * 32767).astype('<i2').tobytes()); wo.close()
    enc = subprocess.Popen([FF, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W * K}x{H * K}', '-r', str(FPS), '-i', '-', '-i', f'{TMP}/a.wav',
                            '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k',
                            '-af', 'pan=stereo|c0=c0|c1=c0', '-shortest', '-movflags', '+faststart', OUT], stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for n, b in enumerate(pool.imap(frame_bytes, range(NF), chunksize=4)):
            enc.stdin.write(b)
            if n % 600 == 0: print('images', n, '/', NF, flush=True)
    enc.stdin.close(); enc.wait(); shutil.rmtree(TMP); print('ok', OUT, round(DUR, 2), f'{W * K}x{H * K}')
