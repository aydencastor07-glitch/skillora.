# Épisode « Brown eyes » : repères, scènes, source, mots en jaune, effets sonores (chargé par every_explained.py)
BROWN2 = (150, 90, 40)
T = dict(explained=tw('explained'), brown=tw('brown'), thing=tw('thing'), common=tw('common'), seven=tw('seven'), people=tw('people'), and0=tw('and', 1), africa=tw('africa'), everyone=tw('everyone'), truly=tw('truly'), very=tw('very'),
         melanin=tw('melanin'), front=tw('front'), packed=tw('packed'), soaks=tw('soaks'), bouncing=tw('bouncing'), looks=tw('looks'), more=tw('more'),
         darker=tw('darker'), black=tw('black'), but=tw('but'), learn=tw('learn'), deep=tw('deep'), layer=tw('layer', 1), even=tw('even'), blue1=tw('blue', 1),
         and1=tw('and', 2), melanin2=tw('melanin', 1), sunglasses=tw('sunglasses'), strong=tw('strong'), sunny=tw('sunny'), world=tw('world'), and2=tw('and', 3),
         better=tw('better'), history=tw('history'), single=tw('single'), had=tw('had'), blue2=tw('blue', 2), thousand=tw('thousand'), so1=tw('so', 1),
         original=tw('original'), do=tw('do'))
for k, v in T.items():
    if v is None: print('mot introuvable :', k)
SC = [0, T['brown'] - 0.12, T['thing'] - 0.1, T['and0'] - 0.1, T['more'] - 0.1, T['but'] - 0.1, T['and1'] - 0.1, T['and2'] - 0.1, T['so1'] - 0.1, DUR]
PUNCH = [(T['seven'], 0.06), (T['melanin'], 0.07), (T['black'], 0.06), (T['even'], 0.05), (T['sunglasses'], 0.05), (T['better'], 0.06), (T['original'], 0.07)]
SHAKE = [(T['melanin'], 12), (T['black'], 10), (T['better'], 14)]
def scene(img, d, sc, t):
    CX = W / 2; u0 = t - SC[sc]
    if sc == 0:   # carte de série, la tuile marron s'allume
        word(img, (CX, 470), 'EVERY EYE COLOR', 92, INK, t, 0.05); word(img, (CX, 580), 'EXPLAINED', 92, BROWN2, t, T['explained'] - 0.15)
        show(img, 1, CX, 1080, 880, 880, 0.1, t, wob=1.2)
        if u0 > 0.6: q = (u0 * 1.5) % 1; circ(d, 750, 875, 200 + 60 * q, BROWN2, None, 10 * (1 - q))
        for k, (lab, x, y) in enumerate((('BLUE', 330, 1095), ('BROWN', 750, 1095), ('GREEN', 330, 1505), ('TWO COLORS', 750, 1505))): word(img, (x, y), lab, 44, BROWN2 if lab == 'BROWN' else INK, t, 0.55 + k * 0.12)
    elif sc == 1:  # le sujet
        word(img, (CX, 470), 'BROWN EYES', 140, BROWN2, t, SC[1] + 0.02)
        for k in range(3):
            q = ((u0 * 1.4 + k / 3) % 1)
            if u0 > 0.2: circ(d, CX, 1010, 180 + 260 * q, (190, 130, 70), None, 8 * (1 - q))
        show(img, 2, CX, 1000, 860, 760, SC[1], t, wob=3)
    elif sc == 2:  # la plus répandue : 7 sur 10
        stamp(img, (CX, 470), '#1 MOST COMMON', 110, BROWN2, t, T['common'] - 0.05, rot=0)
        for j in range(10):
            x = 190 + (j % 5) * 175; y = 860 + (j // 5) * 230; q = since(t, SC[2] + 0.1 + j * 0.05, 0.3)
            br = since(t, T['seven'] + j * 0.08, 0.25) if j < 7 and T['seven'] else 0
            if T['africa'] and t > T['africa'] and j >= 7: br = since(t, T['africa'] + (j - 7) * 0.1, 0.25)
            col = tuple(int(a + (b - a) * br) for a, b in zip((120, 170, 220), BROWN2))
            if q > 0: eyeicon(d, x, y + 8 * math.sin(t * 3 + j), 70 * back(q), col, t * 2 + j, blink=((t + j * 0.37) % 3.1 > 2.95) * 1.0)
        if T['seven'] and t > T['seven'] - 0.05:
            if T['africa'] and t > T['africa'] - 0.05:
                word(img, (CX, 1330), 'AFRICA & ASIA', 100, BROWN2, t, T['africa']); stamp(img, (CX, 1450), 'ALMOST EVERYONE', 80, INK, t, T['everyone'], rot=-3)
            else:
                n = min(7, int(1 + 7 * since(t, T['seven'], 0.6))); counter(img, (CX, 1330), n, '{} OUT OF 10', 110, BROWN2)
                word(img, (CX, 1440), 'PEOPLE', 70, INK, t, T['people'])
    elif sc == 3:  # un mot : la mélanine ; la couche avant absorbe la lumière
        A = gone(t, T['front'] - 0.1)
        def jar(lay, dl):
            show(lay, 4, CX, 1000, 560, 560, SC[3] + 0.05, t, wob=6 + 10 * since(t, T['melanin'], 0.2) * (1 - since(t, T['melanin'] + 0.5, 0.3)))
            word(lay, (CX, 470), 'ONE WORD:', 80, INK, t, SC[3] + 0.2, font='H'); stamp(lay, (CX, 590), 'MELANIN', 140, BROWN2, t, T['melanin'], rot=0)
            rs = np.random.RandomState(4)
            for j in range(26):   # grains qui jaillissent du pot
                if t < T['melanin']: break
                q = ((t - T['melanin']) * 0.9 + j / 26) % 1; a = rs.uniform(-2.6, -0.5)
                circ(dl, CX + math.cos(a) * 420 * q, 760 + math.sin(a) * 300 * q + 500 * q * q, 9, None, BROWN2 + (int(255 * (1 - q)),))
        sub(img, A, jar)
        if T['front'] and t > T['front'] - 0.15:
            show(img, 3, 640, 1060, 660, 800, T['front'] - 0.15, t, wob=1, float_=5)
            word(img, (CX, 450), 'FRONT LAYER', 84, INK, t, T['front']); word(img, (CX, 545), 'PACKED WITH PIGMENT', 66, BROWN2, t, T['packed'])
            for j in range(9):   # photons qui entrent et s'éteignent dans la couche
                q = ((t * 0.9 + j / 9) % 1); x = 40 + 520 * q; y = 940 + 40 * math.sin(j * 1.7)
                circ(d, x, y, 14 * (1 - max(0, q - 0.6) / 0.4), None, (255, 225, 120, int(255 * (1 - max(0, q - 0.6) / 0.4))))
            if T['soaks'] and t > T['soaks'] - 0.05: stamp(img, (330, 1420), 'SOAKS UP LIGHT', 70, BROWN2, t, T['soaks'], rot=-4)
            if T['looks'] and t > T['looks'] - 0.05: word(img, (800, 1520), '= BROWN', 72, BROWN2, t, T['looks'])
    elif sc == 4:  # plus de mélanine = plus foncé ; presque noir
        A = gone(t, T['black'] - 0.12)
        def scale_(lay, dl):
            v = since(t, T['darker'] - 0.3, 1.4)
            col = tuple(int(a + (b - a) * v) for a, b in zip((205, 150, 80), (40, 22, 12)))
            eyeicon(dl, CX, 950, 260, col, math.sin(t * 2))
            rect(dl, 150, 1300, 930, 1360, INK, 6, 1, 28, fill=(240, 240, 240, 255)); dl.rounded_rectangle([S(156), S(1306), S(156 + 768 * v), S(1354)], S(24), fill=col + (255,))
            word(lay, (CX, 450), 'MORE MELANIN', 96, BROWN2, t, SC[4] + 0.05); word(lay, (CX, 560), '= DARKER EYES', 86, INK, t, T['darker'])
        sub(img, A, scale_)
        if T['black'] and t > T['black'] - 0.15:
            show(img, 5, CX, 1000, 860, 700, T['black'] - 0.15, t, wob=2); stamp(img, (CX, 500), 'ALMOST BLACK', 120, INK, t, T['black'], rot=0)
            if T['truly'] and t > T['truly'] - 0.05: stamp(img, (CX, 1400), 'NO TRULY BLACK EYES', 80, RED, t, T['truly'], rot=-4)
            if T['very'] and t > T['very'] - 0.05: word(img, (CX, 1510), 'JUST VERY DARK BROWN', 64, BROWN2, t, T['very'])
    elif sc == 5:  # tout au fond, chaque œil a une couche marron foncé, même les yeux bleus
        word(img, (CX, 440), 'DEEP INSIDE', 92, INK, t, T['deep'] - 0.05, font='H')
        show(img, 6, CX, 1000, 860, 820, T['deep'] - 0.2, t, wob=1, float_=6)
        word(img, (290, 1450), 'BROWN EYE', 60, BROWN2, t, T['deep']); word(img, (760, 1450), 'BLUE EYE', 60, BLUE, t, T['blue1'])
        if T['layer'] and t > T['layer'] - 0.1:
            k = since(t, T['layer'] - 0.1, 0.4); word(img, (CX, 555), 'SAME DARK BROWN LAYER', 66, BROWN2, t, T['layer'])
            arrow(d, 430, 600, 330, 800, BROWN2, 8, k); arrow(d, 650, 600, 760, 800, BROWN2, 8, k)
        if T['even'] and t > T['even'] - 0.05: stamp(img, (CX, 1560), 'EVEN BLUE ONES', 72, BLUE, t, T['even'], rot=-4)
    elif sc == 6:  # lunettes de soleil intégrées ; plus d'yeux marron là où il y a du soleil
        A = gone(t, T['sunny'] - 0.12)
        def shades(lay, dl):
            show(lay, 7, CX, 1000, 860, 860, SC[6] + 0.05, t, wob=4)
            word(lay, (CX, 440), 'BUILT-IN', 92, INK, t, T['sunglasses'] - 0.25); stamp(lay, (CX, 550), 'SUNGLASSES', 120, BROWN2, t, T['sunglasses'], rot=0)
            if T['strong'] and t > T['strong'] - 0.1: word(lay, (CX, 1500), 'SOAKS UP STRONG LIGHT', 64, INK, t, T['strong'])
        sub(img, A, shades)
        if T['sunny'] and t > T['sunny'] - 0.15:
            g = since(t, T['sunny'] - 0.15, 0.4); sun(d, 220, 520, 80, t, g)
            for k in range(6): line(d, 300 + 30 * k, 600 + 20 * k, CX - 120 + 40 * k, 900, (250, 200, 80), 6, g)
            globe(d, CX, 1050, 280, t, g)
            if g >= 1: d.rectangle([S(CX - 276), S(1020), S(CX + 276), S(1080)], fill=(255, 170, 60, 90))
            for j in range(5):
                a = t * 1.1 + j * 1.26; eyeicon(d, CX + 380 * math.cos(a), 1050 + 110 * math.sin(a), 34 * g, BROWN2, a) if math.sin(a) > 0 else None
            word(img, (CX, 470), 'SUNNY PLACES', 96, (230, 140, 30), t, T['sunny']); word(img, (CX, 1480), 'MORE BROWN EYES', 80, BROWN2, t, T['world'])
    elif sc == 7:  # encore mieux : tout le monde avait les yeux marron ; le bleu n'arrive qu'il y a ~10 000 ans
        A = gone(t, T['history'] - 0.1)
        def better(lay, dl):
            j = 6 * math.sin(t * 40) if t - T['and2'] < 0.4 else 0
            word(lay, (CX + j, 950), 'It gets even better', 120, INK, t, T['and2'] + 0.05, font='H')
        sub(img, A, better)
        if T['history'] and t > T['history'] - 0.15:
            B = gone(t, T['blue2'] - 0.1)
            def ancestors(lay, dl):
                show(lay, 8, CX, 1000, 900, 640, T['history'] - 0.15, t, wob=1.5)
                word(lay, (CX, 450), 'FOR MOST OF', 86, INK, t, T['history'] - 0.1); word(lay, (CX, 550), 'HUMAN HISTORY', 96, BROWN2, t, T['history'])
                if T['single'] and t > T['single'] - 0.1: stamp(lay, (CX, 1450), 'EVERYONE HAD BROWN EYES', 66, BROWN2, t, T['had'] or T['single'], rot=-3)
            sub(img, B, ancestors)
            if T['blue2'] and t > T['blue2'] - 0.15:   # frise : un long trait marron, un tout petit bout bleu
                k = since(t, T['blue2'] - 0.15, 0.8); x0, x1, y = 120, 960, 1000
                d.rounded_rectangle([S(x0), S(y - 40), S(x0 + (x1 - x0) * 0.95 * ease(k)), S(y + 40)], S(30), fill=BROWN2 + (255,))
                kb = since(t, T['blue2'] + 0.5, 0.4)
                if kb > 0: d.rounded_rectangle([S(x0 + (x1 - x0) * 0.95), S(y - 40), S(x0 + (x1 - x0) * (0.95 + 0.05 * ease(kb))), S(y + 40)], S(20), fill=BLUE + (255,)); arrow(d, 920, 1200, 940, 1060, BLUE, 8, kb)
                word(img, (CX, 470), 'BLUE ARRIVED', 100, BLUE, t, T['blue2']); word(img, (CX, 580), 'ONLY RECENTLY', 90, INK, t, T['blue2'] + 0.4)
                if T['thousand'] and t > T['thousand'] - 0.1: word(img, (760, 1280), '~10,000 YEARS AGO', 64, BLUE, t, T['thousand'])
                word(img, (300, 1110), 'BROWN', 60, BROWN2, t, T['blue2'])
    elif sc == 8:  # la couleur d'origine + question
        show(img, 2, CX, 1020, 760, 640, SC[8], t, wob=3, float_=12)
        k = since(t, T['original'] - 0.1, 0.4)
        if k > 0:   # couronne qui tombe sur l'œil
            y = 640 - 300 * (1 - back(k)); pts = [(CX - 150, y + 90), (CX - 150, y), (CX - 75, y + 50), (CX, y - 30), (CX + 75, y + 50), (CX + 150, y), (CX + 150, y + 90)]
            d.polygon([(S(x), S(y_)) for x, y_ in pts], fill=YEL + (255,)); poly(d, pts, INK, 6, closed=True)
        word(img, (CX, 430), 'THE ORIGINAL', 100, INK, t, T['original'] - 0.2); stamp(img, (CX, 540), 'HUMAN EYE COLOR', 96, BROWN2, t, T['original'], rot=0)
        if T['do'] and t > T['do'] - 0.05:
            kk = since(t, T['do'], 0.3); bw = 360 * back(kk)
            d.rounded_rectangle([S(CX - bw), S(1440), S(CX + bw), S(1545)], S(50), fill=(240, 240, 245, 255), outline=INK, width=S(5))
            d.polygon([(S(CX - 40), S(1543)), (S(CX - 10), S(1600)), (S(CX + 10), S(1543))], fill=(240, 240, 245, 255)); text(img, (CX, 1492), 'Do you have brown eyes?', HF(54), INK, kk)
SOURCE = ('Sources: American Academy of Ophthalmology · Eiberg et al. (2008)', T['history'] - 0.2, T['so1'] - 0.2)
HOT = re.compile(r'(brown|melanin|light|black|layer|blue|sunglasses|sunny|history|original|common|seven|pigment|darker)', re.I)
def SFX(sfx):
    sfx('pop', T['explained'], 0.12); sfx('swish', T['brown'], 0.15); sfx('hit', T['common'] - 0.05, 0.25); sfx('ding', T['seven'] + 0.6, 0.12); sfx('hit', T['melanin'] - 0.03, 0.3)
    sfx('swish', T['soaks'], 0.12); sfx('zoom1', T['darker'] - 0.2, 0.12); sfx('pop', T['black'], 0.15); sfx('hit', T['truly'], 0.2); sfx('pop', T['africa'], 0.12); sfx('pop', T['layer'], 0.12); sfx('pop', T['even'], 0.15)
    sfx('shine', T['sunglasses'] - 0.1, 0.15); sfx('swish', T['sunny'], 0.12); sfx('glitch', T['better'] - 0.1, 0.2); sfx('pop', T['single'], 0.12); sfx('ding', T['blue2'] + 0.5, 0.12)
    sfx('shine', T['original'] - 0.1, 0.18); sfx('pop', T['do'], 0.15)
