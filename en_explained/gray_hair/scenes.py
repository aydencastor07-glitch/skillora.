# Épisode « Gray hair » (série « Every hair on your head, explained ») : repères, scènes, source, mots en jaune, effets sonores
# (chargé par every_explained.py). Mélange d'illustrations (img/n.jpg) et de 5 clips animés plein écran (vid/1..5.mp4) :
#   vid 1 = le miroir (image 3) · vid 2 = l'usine de couleur (image 5) · vid 3 = cellules coincées (image 9)
#   vid 4 = le stress qui blanchit (image 13) · vid 5 = le personnage qui parle (image 18)
HAIR = (80, 55, 40); SILVER = (150, 155, 165); ORANGE = (240, 120, 40)
T = dict(explained=tw('explained'), gray=tw('gray'), born=tw('born'), color=tw('color'), then=tw('then'), mirror=tw('mirror'), first=tw('first'),
         heres=tw("here's"), at=tw('at'), pigment=tw('pigment'), its=tw('its'), melanocytes=tw('melanocytes'), and1=tw('and', 0), inject=tw('inject'),
         every2=tw('every', 2), falls=tw('falls'), grows=tw('grows'), back=tw('back'), team=tw('team'), stem=tw('stem'), fresh=tw('fresh'),
         but=tw('but'), age=tw('age'), stuck=tw('stuck'), scientists=tw('scientists'), y2023=tw('2023'), stop=tw('stop'),
         no=tw('no'), no2=tw('no', 1), white=tw('white'), and_thing=tw('and', 2), thing=tw('thing'), doesnt=tw("doesn't"), exist=tw('exist'),
         its2=tw("it's"), mixed=tw('mixed'), so=tw('so'), stress=tw('stress'), in_mice=tw('mice'), signal=tw('signal'), burns=tw('burns'),
         few=tw('few'), days=tw('days'), but2=tw('but', 1), twist=tw('twist'), y2021=tw('2021'), color_back=tw('color', 3), down=tw('down'),
         and_no=tw('and', 3), pulling=tw('pulling'), two=tw('two'), one=tw('one', 1), root=tw('root'), one2=tw('one', 2), so2=tw('so', 1), when=tw('when'))
for k, v in T.items():
    if v is None: print('mot introuvable :', k)
MICE = T['in_mice'] - 0.2 if T['in_mice'] else None
SC = [0, T['gray'] - 0.12, T['born'] - 0.45, T['then'] - 0.1, T['heres'] - 0.1, T['at'] - 0.1, T['every2'] - 0.1, T['team'] - 0.15,
      T['but'] - 0.1, T['no'] - 0.1, T['and_thing'] - 0.1, T['so'] - 0.1, MICE, T['but2'] - 0.1, T['and_no'] - 0.1, T['one'] - 0.1, T['so2'] - 0.1, DUR]
PUNCH = [(T['gray'], 0.07), (T['first'], 0.06), (T['melanocytes'], 0.06), (T['stuck'], 0.07), (T['white'], 0.06), (T['exist'], 0.06), (T['stress'], 0.07), (T['twist'], 0.06), (T['two'], 0.05)]
SHAKE = [(T['gray'], 12), (T['stuck'], 14), (T['stress'], 12)]
def strand(d, x, y0, y1, t, white_p, w=16):
    # une mèche ondulée qui blanchit depuis la racine (bas) vers la pointe
    n = 40
    for k in range(n):
        u0, u1 = k / n, (k + 1) / n
        ya, yb = y1 + (y0 - y1) * u0, y1 + (y0 - y1) * u1
        xa, xb = x + 40 * math.sin(u0 * 6 + t * 2), x + 40 * math.sin(u1 * 6 + t * 2)
        col = (235, 235, 238) if u0 < white_p else HAIR
        line(d, xa, ya, xb, yb, INK, w + 8); line(d, xa, ya, xb, yb, col, w)
def bubble(img, d, cx, y, s, t, t0, size=50):
    if t0 is None or t < t0: return
    kk = since(t, t0, 0.3); bw = 500 * back(kk)
    d.rounded_rectangle([S(cx - bw), S(y), S(cx + bw), S(y + 120)], S(55), fill=(255, 255, 255, 245), outline=INK, width=S(5))
    d.polygon([(S(cx - 40), S(y + 118)), (S(cx - 5), S(y + 175)), (S(cx + 15), S(y + 118))], fill=(255, 255, 255, 245)); text(img, (cx, y + 60), s, HF(size), INK, kk)
def ctag(img, d, xy, s, size, col, t, t0, rot=-3):
    # texte posé sur un clip : bandeau blanc derrière, sinon illisible sur les fonds clairs
    if t0 is None or t < t0: return
    k = back(since(t, t0, 0.2)); f = AF(size); bw = (f.getbbox(s)[2] - f.getbbox(s)[0]) / SS / 2 + 34; bh = size * 0.62 + 16
    if k > 0.02: d.rounded_rectangle([S(xy[0] - bw * k), S(xy[1] - bh), S(xy[0] + bw * k), S(xy[1] + bh)], S(26), fill=(255, 255, 255, 235), outline=INK, width=S(5))
    stamp(img, xy, s, size, col, t, t0, rot=rot)
def scene(img, d, sc, t):
    CX = W / 2; u0 = t - SC[sc]
    if sc == 0:   # carte de série
        word(img, (CX, 420), 'EVERY HAIR ON YOUR HEAD', 78, INK, t, 0.05); word(img, (CX, 525), 'EXPLAINED', 96, ORANGE, t, T['explained'] - 0.15)
        show(img, 1, CX, 1110, 900, 1100, 0.1, t, wob=1.2)
    elif sc == 1:  # le sujet : une mèche qui blanchit
        word(img, (CX, 470), 'GRAY HAIR', 170, SILVER, t, SC[1] + 0.02)
        strand(d, CX, 700, 1450, t, ease(since(t, SC[1] + 0.2, 0.7)))
    elif sc == 2:  # né avec des cheveux colorés
        show(img, 2, CX, 1080, 800, 900, SC[2], t, wob=1.5)
        word(img, (CX, 470), 'BORN WITH', 80, INK, t, T['born'] - 0.1); stamp(img, (CX, 580), 'COLOR', 130, HAIR, t, T['color'], rot=0)
    elif sc == 3:  # CLIP 1 : le miroir, le premier cheveu blanc
        clip(img, 1, SC[3], t, speed=1.35)
        if T['first'] and t > T['first'] - 0.1: ctag(img, d, (CX, 1480), 'FIRST GRAY HAIR', 110, SILVER, t, T['first'] - 0.1, rot=0)
    elif sc == 4:  # « Here's what's actually happening » + la loupe
        show(img, 4, CX, 1150, 820, 900, SC[4], t, wob=1, float_=5)
        word(img, (CX, 470), "Here's what's", 120, INK, t, SC[4] + 0.05, font='H'); word(img, (CX, 600), 'actually happening', 110, INK, t, SC[4] + 0.4, font='H')
    elif sc == 5:  # l'usine de couleur (CLIP 2), les mélanocytes (image 6), puis la couleur injectée (suite du CLIP 2)
        a, b = T['its'] - 0.1, T['and1'] - 0.1
        if t < a:
            clip(img, 2, SC[5], t, speed=1.0)
            if T['pigment'] and t > T['pigment'] - 0.1: ctag(img, d, (CX, 1480), 'PIGMENT FACTORY', 110, HAIR, t, T['pigment'] - 0.1, rot=0)
        elif t < b:
            show(img, 6, CX, 1080, 980, 700, a, t, wob=1.5)
            word(img, (CX, 470), 'THE WORKERS', 90, INK, t, a + 0.05); stamp(img, (CX, 1500), 'MELANOCYTES', 120, HAIR, t, T['melanocytes'], rot=0)
        else:
            clip(img, 2, b, t, speed=1.0, start=3.6)
            if T['inject'] and t > T['inject'] - 0.1: ctag(img, d, (CX, 1480), 'INJECT COLOR', 110, HAIR, t, T['inject'] - 0.05, rot=0)
    elif sc == 6:  # le cheveu tombe et repousse
        show(img, 7, CX, 1060, 900, 1000, SC[6], t, wob=1.5)
        word(img, (CX, 470), 'FALLS OUT', 100, INK, t, T['falls'] - 0.05)
        if T['grows'] and t > T['grows'] - 0.1: word(img, (CX, 1560), 'GROWS BACK', 100, GREEN, t, T['grows'] - 0.05)
    elif sc == 7:  # les cellules souches envoient de nouveaux ouvriers
        show(img, 8, CX, 1090, 900, 1100, SC[7], t, wob=1.5)
        stamp(img, (CX, 470), 'STEM CELLS', 120, BLUE, t, T['stem'] - 0.05, rot=0)
        if T['fresh'] and t > T['fresh'] - 0.1: word(img, (CX, 590), 'FRESH WORKERS', 80, INK, t, T['fresh'] - 0.05)
    elif sc == 8:  # CLIP 3 : avec l'âge, les cellules souches restent coincées (découverte 2023)
        clip(img, 3, SC[8], t, speed=1.05)
        ctag(img, d, (CX, 1300), 'WITH AGE', 90, INK, t, T['age'] - 0.1, rot=0)
        if T['stuck'] and t > T['stuck'] - 0.1: ctag(img, d, (CX, 1500), 'STUCK', 150, RED, t, T['stuck'] - 0.05, rot=0)
        if T['y2023'] and t > T['y2023'] - 0.1: ctag(img, d, (CX, 300), 'DISCOVERED IN 2023', 90, BLUE, t, T['y2023'] - 0.1, rot=0)
    elif sc == 9:  # plus d'ouvriers, plus de couleur → blanc
        show(img, 10, CX, 1100, 900, 1100, SC[9], t, wob=1.5)
        word(img, (CX, 430), 'NO WORKERS', 100, INK, t, T['no'] - 0.05)
        if T['no2'] and t > T['no2'] - 0.1: word(img, (CX, 545), 'NO COLOR', 100, RED, t, T['no2'] - 0.05)
        if T['white'] and t > T['white'] - 0.1: stamp(img, (CX, 1600), 'COMPLETELY WHITE', 100, SILVER, t, T['white'] - 0.1, rot=-3)
    elif sc == 10:  # le gris n'existe pas : blanc + brun mélangés
        show(img, 11, CX + 40, 1080, 1000, 1100, SC[10], t, wob=1)
        if t < T['its2'] - 0.1:   # « le gris n'existe pas » (barré), puis remplacé par l'explication
            word(img, (CX, 430), 'GRAY HAIR', 110, SILVER, t, T['thing'])
            if T['doesnt'] and t > T['doesnt'] - 0.1:
                line(d, CX - 250, 430, CX - 250 + 500 * ease(since(t, T['doesnt'], 0.3)), 430, RED, 14); stamp(img, (CX, 560), "DOESN'T EXIST", 100, RED, t, T['exist'] - 0.1, rot=0)
        else:
            word(img, (CX, 430), 'WHITE + BROWN', 100, INK, t, T['its2'] - 0.05)
            if t > T['mixed']: word(img, (CX, 550), '= LOOKS GRAY', 90, SILVER, t, T['mixed'])
    elif sc == 11:  # et le stress ?
        show(img, 12, CX, 1110, 900, 1100, SC[11], t, wob=2 + 5 * since(t, T['stress'], 0.2))
        stamp(img, (CX, 470), 'STRESS?', 160, RED, t, T['stress'] - 0.05, rot=-4)
    elif sc == 12:  # chez la souris (image 14), puis le stress qui blanchit (CLIP 4)
        c = T['burns'] - 0.4 if T['burns'] else None
        if c is None or t < c:
            show(img, 14, CX, 1100, 700, 900, SC[12], t, wob=2, float_=8)
            word(img, (CX, 470), 'IN MICE', 120, INK, t, SC[12] + 0.1)
            if T['signal'] and t > T['signal'] - 0.1: word(img, (CX, 590), 'A STRESS SIGNAL', 90, RED, t, T['signal'] - 0.1)
        else:
            clip(img, 4, c, t, speed=1.3, end=6.4)
            if T['few'] and t > T['few'] - 0.1: ctag(img, d, (CX, 1480), 'IN A FEW DAYS', 110, RED, t, T['few'] - 0.1, rot=0)
    elif sc == 13:  # le retournement : la couleur revient quand le stress baisse (2021)
        show(img, 15, CX, 1080, 980, 900, SC[13], t, wob=2, float_=10)
        word(img, (CX, 430), 'THE TWIST', 110, ORANGE, t, T['twist'] - 0.1)
        if T['y2021'] and t > T['y2021'] - 0.1: word(img, (CX, 550), '2021 STUDY', 90, INK, t, T['y2021'] - 0.1)
        if T['color_back'] and t > T['color_back'] - 0.1: stamp(img, (CX, 1520), 'COLOR CAME BACK', 100, GREEN, t, T['color_back'] - 0.1, rot=-3)
    elif sc == 14:  # le mythe : en arracher un n'en fait pas pousser deux
        show(img, 16, CX, 1080, 860, 1150, SC[14], t, wob=1.5)
        stamp(img, (CX, 400), 'MYTH', 150, RED, t, SC[14] + 0.25, rot=-6)
        if T['two'] and t > T['two'] - 0.1: word(img, (CX, 1580), "2 WON'T GROW BACK", 90, INK, t, T['two'] - 0.1)
    elif sc == 15:  # une racine, un cheveu
        show(img, 17, CX, 1060, 900, 1000, SC[15], t, wob=1.5)
        word(img, (CX, 470), '1 ROOT', 130, INK, t, T['one'] - 0.05)
        if T['one2'] and t > T['one2'] - 0.1: word(img, (CX, 600), '= 1 HAIR', 110, GREEN, t, T['one2'] - 0.05)
    elif sc == 16:  # CLIP 5 : le personnage qui pose la question
        clip(img, 5, SC[16], t, speed=1.0)
        bubble(img, d, CX, 240, 'When did you find your first gray hair?', t, T['when'] - 0.2, 58)
SOURCE = ('Sources: Nature 2023 (NYU) · Nature 2020 (Harvard) · eLife 2021', T['scientists'] - 0.2, T['and_thing'] - 0.3)
HOT = re.compile(r'(gray|white|color|melanocyte|stem|stuck|stress|2023|2021|twist|root|exist|factory|pigment)', re.I)
def SFX(sfx):
    sfx('pop', T['explained'], 0.12); sfx('swish', T['gray'], 0.15); sfx('hit', T['gray'] + 0.02, 0.2); sfx('pop', T['color'], 0.12)
    sfx('glitch', T['first'] - 0.1, 0.12); sfx('swish', T['heres'] - 0.1, 0.1); sfx('pop', T['pigment'], 0.12); sfx('hit', T['melanocytes'], 0.2)
    sfx('shine', T['inject'], 0.1); sfx('pop', T['falls'], 0.1); sfx('ding', T['grows'], 0.1); sfx('pop', T['stem'], 0.12); sfx('hit', T['stuck'] - 0.05, 0.3)
    sfx('ding', T['y2023'], 0.1); sfx('buzz', T['no'], 0.05); sfx('hit', T['white'] - 0.1, 0.2); sfx('glitch', T['doesnt'], 0.12); sfx('hit', T['stress'] - 0.05, 0.25)
    sfx('pop', T['signal'], 0.1); sfx('hit', T['few'] - 0.1, 0.2); sfx('shine', T['twist'], 0.12); sfx('ding', T['color_back'], 0.12); sfx('hit', SC[14] + 0.25, 0.25)
    sfx('pop', T['one'], 0.12); sfx('ding', T['one2'], 0.12); sfx('pop', T['when'] - 0.2, 0.15)
