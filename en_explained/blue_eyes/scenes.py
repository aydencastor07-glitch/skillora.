# Épisode « Blue eyes » : repères, scènes, source, mots en jaune, effets sonores (chargé par every_explained.py)
# ---------- repères temporels
T = dict(every=tw('every'), explained=tw('explained'), blue=tw('blue'), heres=tw("here's"), weird=tw('weird'), zero=tw('zero'), pigment=tw('pigment'), none=tw('none'),
         brown=tw('brown'), packed=tw('packed'), melanin=tw('melanin'), dark=tw('dark'), blue3=tw('blue', 2), almost=tw('almost'), so=tw('so'), where=tw('where'),
         light=tw('light'), when=tw('when'), iris=tw('iris'), fibers=tw('fibers'), scatter=tw('scatter'), back_=tw('back'), same=tw('same'), sky=tw('sky'),
         stranger=tw('stranger'), scientists=tw('scientists'), blueeyed=tw('blue-eyed'), earth=tw('earth'), one=tw('one'), single=tw('single'), ancestor=tw('ancestor'),
         one2=tw('one', 1), tiny2=tw('tiny', 1), mutation=tw('mutation'), six=tw('six'), years=tw('years'), copied=tw('copied'), hundreds=tw('hundreds'), millions=tw('millions'),
         so2=tw('so', 1), what=tw('what'), and_=tw('and'))
for k, v in T.items():
    if v is None: print('mot introuvable :', k)
SC = [0, T['blue'] - 0.12, T['heres'] - 0.1, T['brown'] - 0.12, T['so'] - 0.1, T['when'] - 0.1, T['and_'] - 0.08, T['one2'] - 0.1, T['so2'] - 0.1, DUR]
PUNCH = [(T['zero'], 0.08), (T['none'], 0.06), (T['light'], 0.06), (T['stranger'], 0.07), (T['ancestor'], 0.06), (T['millions'], 0.05), (T['blue'], 0.05)]
SHAKE = [(T['zero'], 14), (T['none'], 10), (T['stranger'], 16)]
# ---------- les scènes : beaucoup de mouvement, une idée = une image
def scene(img, d, sc, t):
    CX = W / 2; u0 = t - SC[sc]
    if sc == 0:   # carte de série : les 4 tuiles arrivent l'une après l'autre en tournant
        word(img, (CX, 470), 'EVERY EYE COLOR', 92, INK, t, 0.05); word(img, (CX, 580), 'EXPLAINED', 92, BLUE, t, T['explained'] - 0.15)
        show(img, 1, CX, 1080, 880, 880, 0.1, t, wob=1.2)
        for k, (lab, x, y) in enumerate((('BLUE', 330, 1095), ('BROWN', 750, 1095), ('GREEN', 330, 1505), ('TWO COLORS', 750, 1505))): word(img, (x, y), lab, 44, INK, t, 0.55 + k * 0.12)
    elif sc == 1:  # le sujet : l'œil arrive en tournant, anneaux qui pulsent autour de l'iris
        word(img, (CX, 470), 'BLUE EYES', 140, BLUE, t, SC[1] + 0.02)
        for k in range(3):
            q = ((u0 * 1.4 + k / 3) % 1); circ(d, CX, 1010, 180 + 260 * q, (90, 160, 240), None, 8 * (1 - q)) if u0 > 0.2 else None
        show(img, 2, CX, 1000, 860, 760, SC[1], t, wob=3)
    elif sc == 2:  # « here's the weird part » → la goutte bleue rebondit, puis explose : ZERO pigment
        if t < T['zero'] - 0.08: word(img, (CX, 470), "HERE'S THE WEIRD PART", 70, INK, t, T['heres'], font='H')
        if t < T['zero']:
            k = since(t, T['weird'] - 0.1, 0.6); y = 980 - 420 * (1 - k) ** 2 * abs(math.cos(k * 7)) if k < 1 else 980 + 8 * math.sin(t * 4)
            sq = max(0, math.sin(k * 7)) * (1 - k) if k < 1 else 0
            if k > 0: drop_(d, CX, y, 140, BLUE, sq)
        else:   # explosion en particules + compteur qui tombe à 0 %
            q = since(t, T['zero'], 0.5); rs = np.random.RandomState(5)
            for j in range(34):
                a = rs.uniform(0, 6.28); v = rs.uniform(180, 520); x = CX + math.cos(a) * v * ease(q); y = 940 + math.sin(a) * v * ease(q) + 300 * q * q
                circ(d, x, y, rs.uniform(8, 20) * (1 - 0.7 * q), None, BLUE + (int(255 * (1 - q * 0.8)),))
            pct = int(round(100 * (1 - since(t, T['zero'] + 0.05, 0.6))))
            counter(img, (CX, 940), pct, '{}%', 220, RED if pct == 0 else BLUE)
            stamp(img, (CX, 470), 'ZERO', 190, RED, t, T['zero'] - 0.03, rot=0); word(img, (CX, 1210), 'BLUE PIGMENT', 104, INK, t, T['pigment'] - 0.05)
        if T['none'] and t > T['none'] - 0.05: stamp(img, (CX, 1350), 'NONE.', 120, RED, t, T['none'], rot=-8)
    elif sc == 3:  # les deux iris glissent des côtés, la mélanine coule du pot dans l'iris marron, jauges
        k = since(t, T['brown'] - 0.1, 0.45); show(img, 3, CX - 600 * (1 - ease(k)), 950, 760, 600, T['brown'] - 0.1, t, wob=1.5)
        word(img, (330, 1310), 'BROWN', 76, BROWN, t, T['brown']); word(img, (750, 1310), 'BLUE', 76, BLUE, t, T['blue3'])
        if T['melanin'] and t > T['packed'] - 0.15:
            q = since(t, T['packed'] - 0.15, 0.4); jx, jy = 210, 470 + 20 * math.sin(t * 3)
            show(img, 4, jx, jy, 220, 220, T['packed'] - 0.15, t, wob=10)
            for j in range(18):   # grains qui tombent du pot vers l'iris marron
                ph = ((t - T['packed']) * 1.3 + j / 18) % 1
                if t > T['packed']: circ(d, jx + 60 + 80 * ph + 10 * math.sin(j), jy + 80 + 520 * ph * ph, 8, None, BROWN + (int(255 * (1 - ph)),))
            word(img, (620, 450), 'MELANIN', 100, BROWN, t, T['melanin']); word(img, (620, 545), 'a dark pigment', 56, GREY, t, T['dark'], font='H')
        if T['almost'] and t > T['blue3'] - 0.2:
            bar(img, d, 280, 1430, 100, 170, since(t, T['blue3'] - 0.2, 0.6), BROWN, ''); bar(img, d, 700, 1430, 100, 170, 0.05 * since(t, T['blue3'], 0.6), BLUE, '')
            word(img, (750, 1375), 'ALMOST NONE', 54, RED, t, T['almost'])
    elif sc == 4:  # d'où vient le bleu ? points d'interrogation en orbite, puis la lumière arrive
        show(img, 2, CX, 1000, 620, 560, SC[4], t, wob=4)
        for k in range(3):
            a = t * 2.2 + k * 2.09; x = CX + 360 * math.cos(a); y = 1000 + 150 * math.sin(a); s_ = 1 + 0.25 * math.sin(a)
            text(img, (x, y), '?', AF(110 * s_), INK, clamp(u0 / 0.3), rot=15 * math.sin(t * 5 + k))
        if t < T['light'] - 0.1: word(img, (CX, 470), 'WHERE DOES THE BLUE', 76, INK, t, T['where']); word(img, (CX, 570), 'COME FROM?', 80, BLUE, t, T['where'] + 0.3)
        if T['light'] and t > T['light'] - 0.15:
            q = since(t, T['light'] - 0.15, 0.4); d.polygon([(S(-100), S(300)), (S(220), S(300)), (S(CX + 200), S(1000)), (S(CX - 120), S(1000))], fill=(255, 235, 140, int(150 * q)))
            sun(d, 170, 380, 95, t, q); stamp(img, (CX, 1420), 'LIGHT', 150, (240, 170, 20), t, T['light'], rot=0)
    elif sc == 5:  # la lumière entre dans l'iris, le bleu rebondit (rayons animés) ; comme le ciel
        A = gone(t, T['same'] - 0.1)
        def iris(lay, dl):
            show(lay, 5, CX, 1000, 900, 980, SC[5], t, wob=1.0, float_=6)
            word(lay, (CX, 430), 'LIGHT ENTERS YOUR IRIS', 72, INK, t, T['iris'] - 0.3)
            for k in range(4):   # rayons bleus renvoyés, en boucle
                q = ((t * 0.9 + k / 4) % 1); a = math.radians(200 + 35 * k)
                wavy(dl, 330, 900 + 60 * (k - 1.5), a, 60 + 260 * q, (40, 110, 230), t * 8 + k, 7)
            if T['fibers'] and t > T['fibers'] - 0.1:
                word(lay, (800, 1500), 'TINY FIBERS', 66, INK, t, T['fibers']); arrow(dl, 790, 1450, 620, 1180, INK, 7, since(t, T['fibers'], 0.35))
            if T['scatter'] and t > T['scatter'] - 0.05: stamp(lay, (300, 560), 'BLUE BOUNCES BACK', 62, BLUE, t, T['scatter'], rot=-4)
        sub(img, A, iris)
        if T['same'] and t > T['same'] - 0.15:
            k = since(t, T['same'] - 0.15, 0.3); d.rectangle([S(0), S(330), S(W), S(330 + 1000 * ease(k))], fill=SKY + (255,))
            if k >= 1:
                sun(d, 840, 520, 85, t)
                for j, y in enumerate((640, 780, 560)):   # nuages qui dérivent
                    x = (120 + j * 330 + t * 40) % (W + 300) - 150
                    for dx, r in ((-50, 42), (0, 58), (50, 44)): circ(d, x + dx, y, r, None, WHITE + (255,))
                for j in range(3):   # oiseaux
                    x = (t * 120 + j * 260) % (W + 200) - 100; y = 700 + 40 * j; f = 20 * math.sin(t * 9 + j)
                    poly(d, [(x - 30, y - f), (x, y), (x + 30, y - f)], INK, 5)
                eyeicon(d, CX, 1080, 120, BLUE, look=math.sin(t * 2), blink=(t % 2.4 > 2.25) * 1.0)
            word(img, (CX, 1420), 'SAME REASON THE SKY IS BLUE', 66, INK, t, T['sky'] - 0.1)
    elif sc == 6:  # plus étrange : la Terre tourne avec des yeux bleus en orbite → un seul ancêtre
        A = gone(t, T['scientists'] - 0.08); B = gone(t, T['one'] - 0.1) if t > T['scientists'] - 0.2 else 0
        def strange(lay, dl):
            j = 6 * math.sin(t * 40) if t - T['and_'] < 0.4 else 0
            word(lay, (CX + j, 950), 'It gets stranger', 130, INK, t, T['and_'] + 0.05, font='H')
            for k in range(5): q = ((t * 0.7 + k / 5) % 1); text(lay, (CX - 300 + 150 * k, 760 - 120 * q), '?', AF(70), GREY, (1 - q) * 0.8)
        sub(img, A, strange)
        def world(lay, dl):
            word(lay, (CX, 450), 'SCIENTISTS BELIEVE', 76, INK, t, T['scientists'], font='H')
            g = since(t, T['blueeyed'] - 0.4, 0.4) if T['blueeyed'] else 0
            orbit = [(t * 1.3 + k * 0.785) for k in range(8)]
            for a in orbit:      # yeux derrière la Terre
                if math.sin(a) < 0 and g > 0: eyeicon(dl, CX + 400 * math.cos(a), 980 + 120 * math.sin(a), 30 * g, BLUE, a)
            globe(dl, CX, 980, 250, t, g)
            for a in orbit:      # yeux devant
                if math.sin(a) >= 0 and g > 0: eyeicon(dl, CX + 400 * math.cos(a), 980 + 120 * math.sin(a), 46 * g, BLUE, a)
            word(lay, (CX, 1420), 'EVERY BLUE-EYED PERSON', 72, BLUE, t, T['blueeyed'])
        sub(img, B, world)
        if T['one'] and t > T['one'] - 0.12:
            q = since(t, T['one'], 0.5)
            for k in range(14): a = k * math.pi / 7 + t * 0.6; line(d, CX + 330 * math.cos(a), 1010 + 330 * math.sin(a), CX + (330 + 120 * q) * math.cos(a), 1010 + (330 + 120 * q) * math.sin(a), (255, 210, 80), 10)
            show(img, 7, CX, 1010, 760, 760, T['one'] - 0.12, t, wob=2.5)
            word(img, (CX, 450), 'ONE SINGLE', 112, INK, t, T['one']); stamp(img, (CX, 570), 'ANCESTOR', 120, BLUE, t, T['ancestor'], rot=0)
    elif sc == 7:  # ADN en 3D qui tourne, compteur d'années, puis l'arbre qui se remplit d'yeux bleus
        A = gone(t, T['copied'] - 0.1)
        def dna(lay, dl):
            helix(dl, 300, 520, 1500, t, 120, glow=since(t, T['mutation'] - 0.1, 0.3), p=clamp(u0 / 0.5))
            word(lay, (760, 560), 'ONE TINY', 96, INK, t, T['tiny2']); stamp(lay, (760, 670), 'MUTATION', 100, BLUE, t, T['mutation'], rot=0)
            if T['six'] and t > T['six'] - 0.1:
                yrs = int(10000 * ease(since(t, T['six'] - 0.1, 1.0))); counter(lay, (760, 1010), yrs, '{:,}', 120, RED); word(lay, (760, 1120), 'YEARS AGO', 64, INK, t, T['years'])
        sub(img, A, dna)
        if T['copied'] and t > T['copied'] - 0.12:   # génération après génération : chaque œil donne deux yeux
            gens = 6; y0 = 450
            for r in range(gens):
                q = since(t, T['copied'] + r * 0.28, 0.25); n = 2 ** r; y = y0 + r * 150
                for j in range(n):
                    x = CX + (j - (n - 1) / 2) * (900 / n if n > 1 else 0)
                    if r > 0 and q > 0:
                        px = CX + (j // 2 - (n // 2 - 1) / 2) * (900 / (n // 2) if n > 2 else 0); line(d, px, y - 150 + 30, px + (x - px) * q, y - 150 + 30 + 100 * q, GREY, 4)
                    if q > 0: eyeicon(d, x, y + 30, max(6, 44 - r * 6) * back(q), BLUE, t * 2 + j)
            n_ = int(1 + (300_000_000 - 1) * ease(since(t, T['hundreds'] - 0.2, 1.4))) if T['hundreds'] else 1
            counter(img, (CX, 1400), n_, '{:,}', 96, BLUE); word(img, (CX, 1500), 'BLUE-EYED PEOPLE TODAY', 50, INK, t, T['millions'])
    elif sc == 8:  # question finale : les tuiles rebondissent, bulle de commentaire
        show(img, 1, CX, 1030, 760, 760, SC[8], t, wob=3, float_=14)
        word(img, (CX, 450), 'WHAT COLOR', 124, INK, t, T['what']); word(img, (CX, 570), 'ARE YOUR EYES?', 108, BLUE, t, T['what'] + 0.45)
        k = since(t, T['what'] + 0.7, 0.3)
        if k > 0:
            bw = 340 * back(k); d.rounded_rectangle([S(CX - bw), S(1440), S(CX + bw), S(1545)], S(50), fill=(240, 240, 245, 255), outline=INK, width=S(5))
            d.polygon([(S(CX - 40), S(1543)), (S(CX - 10), S(1600)), (S(CX + 10), S(1543))], fill=(240, 240, 245, 255)); text(img, (CX, 1492), 'Tell me in the comments 👇'.replace(' 👇', ''), HF(54), INK, k)
SOURCE = ('Source: Eiberg et al., University of Copenhagen (2008)', T['scientists'] - 0.2, T['so2'] - 0.2)
HOT = re.compile(r'(blue|zero|none|melanin|light|iris|sky|stranger|ancestor|mutation|millions|thousand|brown|pigment|color)', re.I)
def SFX(sfx):
    sfx('pop', T['explained'], 0.12); sfx('swish', T['blue'], 0.15); sfx('hit', T['zero'] - 0.03, 0.35); sfx('pop', T['none'], 0.2); sfx('pop', T['melanin'], 0.12); sfx('ding', T['almost'], 0.1)
    sfx('shine', T['light'] - 0.1, 0.2); sfx('swish', T['scatter'], 0.15); sfx('pop', T['sky'], 0.12); sfx('glitch', T['stranger'] - 0.1, 0.2); sfx('shine', T['ancestor'] - 0.1, 0.15)
    sfx('pop', T['mutation'], 0.15); sfx('tap', T['six'], 0.12); sfx('zoom1', T['copied'], 0.15); sfx('ding', T['millions'], 0.12); sfx('pop', T['what'], 0.15)
