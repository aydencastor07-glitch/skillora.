# Épisode « Freckles » (série « Every mark on your skin explained ») : repères, scènes, source, mots en jaune, effets sonores
# (chargé par every_explained.py). Une image par phrase, comme la référence : le personnage grandit (bébé → plage → été → hiver → vieux).
SKIN = (238, 170, 130); FRK = (170, 100, 55); ORANGE = (240, 120, 40)
T = dict(explained=tw('explained'), freckles=tw('freckles'), you=tw('you'), clear=tw('clear'), single=tw('single'), then=tw('then'), two=tw('two'),
         summer=tw('summer'), tiny=tw('tiny'), heres=tw("here's"), deep=tw('deep'), melanocytes=tw('melanocytes'), their=tw('their'), melanin=tw('melanin'),
         natural=tw('natural'), sunlight=tw('sunlight'), protect=tw('protect'), most=tw('most'), evenly=tw('evenly'), tan=tw('tan'), but=tw('but'),
         small=tw('small'), harder=tw('harder'), one=tw('one'), freckle2=tw('freckle', 1), reason=tw('reason'), dna=tw('dna'), gene=tw('gene'), mc1r=tw('mc1r'),
         certain=tw('certain'), tanning=tw('tanning'), freckling=tw('freckling'), thats2=tw("that's", 1), redheads=tw('redheads'), summer2=tw('summer', 1),
         overdrive=tw('overdrive'), darker=tw('darker'), winter=tw('winter'), fade=tw('fade'), disappear=tw('disappear'), but2=tw('but', 1), spots2=tw('spots', 1),
         years=tw('years'), stay=tw('stay'), so2=tw('so', 1), changes=tw('changes'), checked=tw('checked'), do2=tw('do', 1))
for k, v in T.items():
    if v is None: print('mot introuvable :', k)
SC = [0, T['freckles'] - 0.12, T['you'] - 0.1, T['then'] - 0.1, T['heres'] - 0.1, T['their'] - 0.1, T['most'] - 0.25, T['but'] - 0.1, T['one'] - 0.1,
      T['reason'] - 0.35, T['thats2'] - 0.1, T['summer2'] - 0.3, T['winter'] - 0.25, T['but2'] - 0.1, T['so2'] - 0.1, T['do2'] - 0.1, DUR]
PUNCH = [(T['freckles'], 0.07), (T['clear'], 0.05), (T['melanin'], 0.06), (T['harder'], 0.06), (T['mc1r'], 0.07), (T['overdrive'], 0.07), (T['spots2'], 0.05), (T['checked'], 0.05)]
SHAKE = [(T['freckles'], 12), (T['harder'], 12), (T['overdrive'], 14)]
def dots(d, cx, cy, n, r, t, t0, seed=1, col=FRK):
    # petites taches qui apparaissent une à une (pop)
    if t0 is None or t < t0: return
    rs = np.random.RandomState(seed)
    for j in range(n):
        x, y, rr = cx + rs.uniform(-r, r), cy + rs.uniform(-r * 0.6, r * 0.6), rs.uniform(5, 10)
        q = since(t, t0 + j * 0.05, 0.2)
        if q > 0: circ(d, x, y, rr * back(q), None, col + (230,))
def snow(d, t, n=30):
    rs = np.random.RandomState(8)
    for j in range(n):
        x0 = rs.uniform(0, W); sp = rs.uniform(60, 140); y = (rs.uniform(0, 1500) + sp * t) % 1450 + 330; x = x0 + 25 * math.sin(t * 1.4 + j)
        circ(d, x, y, rs.uniform(5, 10), None, (200, 215, 235, 220))
def bubble(img, d, cx, y, s, t, t0):
    if t0 is None or t < t0: return
    kk = since(t, t0, 0.3); bw = 380 * back(kk)
    d.rounded_rectangle([S(cx - bw), S(y), S(cx + bw), S(y + 110)], S(50), fill=(240, 240, 245, 255), outline=INK, width=S(5))
    d.polygon([(S(cx - 40), S(y + 108)), (S(cx - 10), S(y + 165)), (S(cx + 10), S(y + 108))], fill=(240, 240, 245, 255)); text(img, (cx, y + 55), s, HF(56), INK, kk)
def scene(img, d, sc, t):
    CX = W / 2; u0 = t - SC[sc]
    if sc == 0:   # carte de série
        word(img, (CX, 430), 'EVERY MARK ON YOUR SKIN', 80, INK, t, 0.05); word(img, (CX, 535), 'EXPLAINED', 96, ORANGE, t, T['explained'] - 0.15)
        show(img, 1, CX, 1100, 880, 1080, 0.1, t, wob=1.2)
    elif sc == 1:  # le sujet
        word(img, (CX, 470), 'FRECKLES', 160, FRK, t, SC[1] + 0.02)
        for k in range(3):
            q = ((u0 * 1.4 + k / 3) % 1)
            if u0 > 0.2: circ(d, CX, 1060, 200 + 260 * q, (230, 160, 110), None, 8 * (1 - q))
        show(img, 15, CX, 1060, 700, 900, SC[1], t, wob=3)
    elif sc == 2:  # bébé : peau parfaite, zéro tache
        show(img, 2, CX, 1060, 900, 800, SC[2], t, wob=1.5)
        word(img, (CX, 470), 'BORN WITH', 80, INK, t, SC[2] + 0.2); stamp(img, (CX, 580), 'CLEAR SKIN', 120, BLUE, t, T['clear'], rot=0)
        if T['single'] and t > T['single'] - 0.1: stamp(img, (CX, 1500), '0 FRECKLES', 96, INK, t, T['single'], rot=-4)
    elif sc == 3:  # 2 ans, premier été au soleil, les points apparaissent
        show(img, 3, CX, 1040, 860, 820, SC[3], t, wob=1.5)
        word(img, (CX, 470), 'AGE 2', 120, INK, t, T['two'] - 0.1); word(img, (CX, 590), 'FIRST SUMMER', 90, ORANGE, t, T['summer'])
        if T['tiny'] and t > T['tiny']:
            word(img, (CX, 1570), 'TINY DOTS APPEAR', 86, FRK, t, T['tiny'])
            dots(d, 340, 1060, 9, 45, t, T['tiny'] + 0.2, 3)
    elif sc == 4:  # « Here's why » puis la peau en coupe et ses mélanocytes
        if T['deep'] and t < T['deep'] - 0.1: word(img, (CX, 960), "Here's why", 150, INK, t, SC[4] + 0.05, font='H')
        if T['deep'] and t > T['deep'] - 0.15:
            show(img, 4, CX, 1030, 860, 900, T['deep'] - 0.15, t, wob=1, float_=5)
            word(img, (CX, 470), 'DEEP IN YOUR SKIN', 90, INK, t, T['deep'])
            if T['melanocytes'] and t > T['melanocytes'] - 0.1:
                stamp(img, (CX, 1580), 'MELANOCYTES', 110, BROWN, t, T['melanocytes'], rot=0); arrow(d, 760, 1510, 700, 1400, BROWN, 8, since(t, T['melanocytes'] + 0.2, 0.3))
    elif sc == 5:  # la mélanine = crème solaire naturelle
        show(img, 5, CX, 1100, 900, 1050, SC[5], t, wob=1, float_=5)
        word(img, (CX, 430), 'THEIR JOB:', 70, INK, t, SC[5] + 0.1, font='H'); stamp(img, (CX, 530), 'MELANIN', 130, BROWN, t, T['melanin'], rot=0)
        if T['natural'] and t > T['natural'] - 0.1: stamp(img, (CX, 1560), 'NATURAL SUNSCREEN', 92, ORANGE, t, T['natural'], rot=-3)
        sun(d, 900, 700, 55, t, since(t, T['sunlight'] - 0.2, 0.4))
    elif sc == 6:  # partout pareil = bronzage
        show(img, 6, CX, 1050, 900, 1100, SC[6], t, wob=2)
        word(img, (CX, 470), 'MOST PEOPLE', 90, INK, t, SC[6] + 0.15); stamp(img, (CX, 580), 'EVENLY', 120, ORANGE, t, T['evenly'], rot=0)
        if T['tan'] and t > T['tan'] - 0.1: stamp(img, (CX, 1520), "= A TAN", 110, (190, 120, 70), t, T['tan'], rot=-4)
    elif sc == 7:  # un petit groupe travaille beaucoup plus
        show(img, 7, CX, 1060, 940, 1080, SC[7], t, wob=1.5 + 6 * since(t, T['harder'], 0.2) * (1 - since(t, T['harder'] + 0.6, 0.3)))
        word(img, (CX, 470), 'A SMALL GROUP', 90, INK, t, T['small'] - 0.1)
        if T['harder'] and t > T['harder'] - 0.1: stamp(img, (CX, 590), 'WORKING HARDER', 110, RED, t, T['harder'], rot=0)
    elif sc == 8:  # 1 groupe = 1 tache
        show(img, 8, CX, 1050, 900, 1050, SC[8], t, wob=2)
        word(img, (CX, 470), '1 BUSY GROUP', 100, INK, t, SC[8] + 0.05); word(img, (CX, 580), '= 1 FRECKLE', 110, FRK, t, T['freckle2'] - 0.05)
    elif sc == 9:  # l'ADN : le gène MC1R ; mauvais pour bronzer, très bon pour les taches
        A = gone(t, T['certain'] - 0.1)
        def gene(lay, dl):
            word(lay, (CX, 470), 'WRITTEN IN YOUR', 80, INK, t, SC[9] + 0.15); word(lay, (CX, 575), 'DNA', 130, BLUE, t, T['dna'])
            helix(dl, CX, 720, 1400, t, 140, glow=since(t, T['gene'], 0.3), p=since(t, SC[9] + 0.2, 1.0))
            if T['mc1r'] and t > T['mc1r'] - 0.15: stamp(lay, (CX, 1520), 'MC1R', 150, RED, t, T['mc1r'] - 0.1, rot=0)
        sub(img, A, gene)
        if T['certain'] and t > T['certain'] - 0.15:
            show(img, 9, CX, 1050, 940, 1000, T['certain'] - 0.15, t, wob=1)
            word(img, (CX, 470), 'MC1R', 120, RED, t, T['certain'] - 0.1)
            if T['tanning'] and t > T['tanning'] - 0.2: word(img, (300, 1490), 'TANNING', 70, RED, t, T['tanning'] - 0.15)
            if T['freckling'] and t > T['freckling'] - 0.2: word(img, (760, 1490), 'FRECKLING', 70, GREEN, t, T['freckling'] - 0.2)
    elif sc == 10:  # les roux
        show(img, 10, CX, 1120, 760, 900, SC[10], t, wob=3)
        word(img, (CX, 470), 'THAT\'S WHY', 80, INK, t, SC[10] + 0.05, font='H'); stamp(img, (CX, 580), 'REDHEADS', 130, ORANGE, t, T['redheads'], rot=0)
    elif sc == 11:  # l'été : overdrive
        show(img, 11, CX, 1030, 860, 900, SC[11], t, wob=2); sun(d, 870, 640, 60, t, since(t, SC[11], 0.4))
        word(img, (CX, 470), 'SUMMER', 100, ORANGE, t, T['summer2']); stamp(img, (CX, 1580), 'OVERDRIVE', 140, RED, t, T['overdrive'], rot=-3)
        if T['darker'] and t > T['darker'] - 0.1: word(img, (CX, 590), 'DARKER', 80, FRK, t, T['darker'])
    elif sc == 12:  # l'hiver : elles s'effacent
        snow(d, t); show(img, 12, CX, 1030, 760, 880, SC[12], t, wob=1.5)
        word(img, (CX, 470), 'WINTER', 110, BLUE, t, T['winter'] - 0.05)
        if T['disappear'] and t > T['fade'] - 0.1: word(img, (CX, 1580), 'Almost disappear', 110, (120, 140, 170), t, T['fade'], font='H')
    elif sc == 13:  # pas toutes les taches : les taches solaires, après des années, toute l'année
        if T['spots2'] and t < T['spots2'] - 0.15:
            word(img, (CX, 900), 'Not every', 130, INK, t, SC[13] + 0.05, font='H'); word(img, (CX, 1040), 'brown spot', 130, FRK, t, SC[13] + 0.4, font='H')
        if T['spots2'] and t > T['spots2'] - 0.2:
            show(img, 13, CX, 1100, 760, 900, T['spots2'] - 0.2, t, wob=1.5)
            stamp(img, (CX, 470), 'SUN SPOTS', 130, FRK, t, T['spots2'] - 0.2, rot=0)
            if T['years'] and t > T['years'] - 0.2: word(img, (CX, 590), 'AFTER YEARS', 80, INK, t, T['years'] - 0.2)
            if T['stay'] and t > T['stay'] - 0.1: stamp(img, (CX, 1520), 'STAY ALL YEAR', 96, RED, t, T['stay'], rot=-3)
    elif sc == 14:  # une tache qui change → médecin
        show(img, 14, CX, 1040, 900, 900, SC[14], t, wob=1.5)
        word(img, (CX, 470), 'SPOT CHANGES?', 100, RED, t, T['changes'] - 0.3)
        if T['checked'] and t > T['checked'] - 0.15:
            stamp(img, (CX, 1580), 'GET IT CHECKED', 110, INK, t, T['checked'] - 0.1, rot=-3)
            k = back(since(t, T['checked'], 0.3)); x, y = 900, 650   # panneau attention
            if k > 0.02: pts = [(x, y - 70 * k), (x + 75 * k, y + 60 * k), (x - 75 * k, y + 60 * k)]; d.polygon([(S(a), S(b)) for a, b in pts], fill=YEL + (255,)); poly(d, pts, INK, 6, closed=True); text(img, (x, y + 20 * k), '!', AF(80 * k), INK)
    elif sc == 15:  # question finale
        show(img, 15, CX, 1000, 700, 900, SC[15], t, wob=3, float_=12)
        bubble(img, d, CX, 1420, 'Do you have freckles?', t, T['do2'])
SOURCE = ('Sources: American Academy of Dermatology · NIH (MC1R)', T['reason'] - 0.2, T['thats2'] - 0.2)
HOT = re.compile(r'(freckle|melanin|melanocyte|sunscreen|tan|harder|dna|mc1r|redhead|summer|overdrive|darker|winter|disappear|spot|checked|clear)', re.I)
def SFX(sfx):
    sfx('pop', T['explained'], 0.12); sfx('swish', T['freckles'], 0.15); sfx('hit', T['freckles'] + 0.02, 0.2); sfx('pop', T['clear'], 0.12); sfx('ding', T['single'], 0.1)
    sfx('shine', T['summer'], 0.1); sfx('pop', T['tiny'] + 0.2, 0.12); sfx('swish', T['deep'] - 0.1, 0.12); sfx('pop', T['melanocytes'], 0.15); sfx('hit', T['melanin'] - 0.03, 0.25)
    sfx('shine', T['natural'], 0.12); sfx('pop', T['evenly'], 0.12); sfx('ding', T['tan'], 0.1); sfx('hit', T['harder'] - 0.03, 0.25); sfx('pop', T['freckle2'], 0.12)
    sfx('zoom1', T['dna'] - 0.2, 0.12); sfx('hit', T['mc1r'] - 0.1, 0.3); sfx('tap', T['tanning'], 0.1); sfx('ding', T['freckling'], 0.12); sfx('pop', T['redheads'], 0.15)
    sfx('hit', T['overdrive'] - 0.03, 0.3); sfx('swish', T['winter'] - 0.1, 0.12); sfx('shine', T['fade'], 0.1); sfx('glitch', T['but2'], 0.15); sfx('pop', T['spots2'] - 0.2, 0.15)
    sfx('hit', T['stay'], 0.2); sfx('buzz', T['changes'], 0.06); sfx('hit', T['checked'] - 0.1, 0.25); sfx('pop', T['do2'], 0.15)
