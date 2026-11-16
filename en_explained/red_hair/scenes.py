# Épisode « Red hair » (série « Every hair on your head, explained ») : repères, scènes, source, mots en jaune, effets sonores
# (chargé par every_explained.py). 15 illustrations (img/1..15.jpg), la carte de série de Gray hair (img/16.jpg)
# et 5 clips plein écran générés directement en 1080p (vid/1..5.mp4) :
#   vid 1 = la foule et le seul roux · vid 2 = l'interrupteur (brun puis roux) · vid 3 = le dentiste
#   vid 4 = coup de soleil et crème solaire · vid 5 = l'arbre généalogique où le gène se cache
SHARPEN = 70
REDH = (232, 88, 30); ORANGE = (240, 120, 40); DARK = (90, 55, 35)
T = dict(explained=tw('explained'), red=tw('red'), hair=tw('hair', 1), only=tw('only'), hundred=tw('hundred'), heres=tw("here's"), why=tw('why'),
         remember=tw('remember'), workers=tw('workers'), root=tw('root'), they=tw('they'), colors=tw('colors'), dark=tw('dark'), red1=tw('red', 1),
         gene=tw('gene'), mc1r=tw('mc1r'), switch=tw('switch'), when=tw('when'), works=tw('works'), dark1=tw('dark', 1), broken=tw('broken'), red2=tw('red', 2),
         and1=tw('and', 1), crazy=tw('crazy'), two2=tw('two', 2), parents=tw('parents'), carry=tw('carry'), without=tw('without'),
         then=tw('then'), baby=tw('baby'), one2=tw('one', 2), four=tw('four'), that=tw('that'), same=tw('same'), feels=tw('feels'),
         y2004=tw('2004'), study=tw('study'), redheads=tw('redheads'), n20=tw('20'), anesthesia=tw('anesthesia'),
         scientists=tw('scientists'), pale=tw('pale'), vitamin=tw('vitamin'), cloudy=tw('cloudy'), like=tw('like'), scotland=tw('scotland'), ireland=tw('ireland'),
         where=tw('where'), n1=tw('1'), n10=tw('10'), but=tw('but'), burns=tw('burns'), sunscreen=tw('sunscreen'), optional=tw('optional'),
         and3=tw('and', 3), no=tw('no'), extinct=tw('extinct'), gene1=tw('gene', 1), hides=tw('hides'), so1=tw('so', 1), do=tw('do'), family=tw('family'))
for k, v in T.items():
    if v is None: print('mot introuvable :', k)
SC = [0, T['red'] - 0.1, T['only'] - 0.1, T['heres'] - 0.1, T['remember'] - 0.1, T['they'] - 0.1, T['gene'] - 0.25, T['when'] - 0.1,
      T['and1'] - 0.1, T['two2'] - 0.1, T['then'] - 0.1, T['that'] - 0.1, T['y2004'] - 0.45, T['redheads'] - 0.1, T['scientists'] - 0.1,
      T['like'] - 0.1, T['where'] - 0.1, T['but'] - 0.1, T['and3'] - 0.1, T['gene1'] - 0.25, T['so1'] - 0.1, DUR]
PUNCH = [(T['red'], 0.07), (T['mc1r'], 0.06), (T['broken'], 0.06), (T['crazy'], 0.07), (T['one2'], 0.06), (T['n20'], 0.06), (T['n1'], 0.05), (T['extinct'], 0.07)]
SHAKE = [(T['red'], 12), (T['broken'], 12), (T['crazy'], 14), (T['extinct'], 10)]
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
def after(t, k, d=0.1): return T[k] is not None and t > T[k] - d
def scene(img, d, sc, t):
    CX = W / 2
    if sc == 0:    # carte de série (même carte que Gray hair)
        word(img, (CX, 420), 'EVERY HAIR ON YOUR HEAD', 78, INK, t, 0.05); word(img, (CX, 525), 'EXPLAINED', 96, ORANGE, t, T['explained'] - 0.15)
        show(img, 16, CX, 1110, 900, 1100, 0.1, t, wob=1.2)
    elif sc == 1:  # le sujet
        show(img, 1, CX, 1150, 820, 1000, SC[1], t, wob=1.5)
        stamp(img, (CX, 450), 'RED HAIR', 170, REDH, t, T['red'] - 0.02, rot=-3)
    elif sc == 2:  # CLIP 1 : la foule, un seul roux
        clip(img, 1, SC[2], t, speed=1.85)
        if after(t, 'only'): ctag(img, d, (CX, 300), 'ONLY 1-2 IN 100', 110, REDH, t, T['only'] - 0.05, rot=0)
    elif sc == 3:  # « Here's why »
        show(img, 2, CX, 1130, 820, 1000, SC[3], t, wob=1, float_=6)
        word(img, (CX, 470), "Here's why", 140, INK, t, SC[3] + 0.05, font='H')
    elif sc == 4:  # l'usine de la racine (les ouvriers de l'épisode Gray hair)
        show(img, 3, CX, 1120, 860, 1150, SC[4], t, wob=1.2)
        word(img, (CX, 400), 'REMEMBER', 90, INK, t, T['remember'] - 0.05)
        if after(t, 'workers'): word(img, (CX, 510), 'THE TINY WORKERS?', 90, ORANGE, t, T['workers'] - 0.05)
    elif sc == 5:  # deux couleurs : foncée et rousse
        show(img, 4, CX, 1150, 980, 900, SC[5], t, wob=1.5)
        word(img, (CX, 420), '2 COLORS', 130, INK, t, T['colors'] - 0.1)
        if after(t, 'dark'): word(img, (CX - 230, 1520), 'DARK', 110, DARK, t, T['dark'] - 0.05)
        if after(t, 'red1'): word(img, (CX + 230, 1520), 'RED', 110, REDH, t, T['red1'] - 0.05)
    elif sc == 6:  # le gène MC1R = l'interrupteur
        show(img, 5, CX, 1150, 900, 1200, SC[6], t, wob=1.2)
        word(img, (CX, 330), 'A GENE CALLED', 80, INK, t, SC[6] + 0.05)
        if after(t, 'mc1r'): stamp(img, (CX, 450), 'MC1R', 150, BLUE, t, T['mc1r'] - 0.05, rot=-4)
        if after(t, 'switch'): ctag(img, d, (CX, 1700 - 140), 'THE SWITCH', 100, INK, t, T['switch'] - 0.05, rot=0)
    elif sc == 7:  # CLIP 2 : l'interrupteur marche (brun), puis il casse (roux)
        cut = T['broken'] - 0.15
        if t < cut: clip(img, 2, SC[7], t, speed=1.0, start=0.3)
        else: clip(img, 2, cut, t, speed=1.6, start=0.3 + (cut - SC[7]), fade=0.001)
        if after(t, 'works') and t < cut: ctag(img, d, (CX, 1500), 'WORKS = DARK', 110, DARK, t, T['works'] - 0.05, rot=0)
        if t >= cut: ctag(img, d, (CX, 1500), 'BROKEN = RED', 110, REDH, t, T['broken'] - 0.05, rot=0)
    elif sc == 8:  # « the crazy part »
        show(img, 6, CX, 1140, 800, 1000, SC[8], t, wob=2 + 4 * since(t, T['crazy'], 0.2))
        stamp(img, (CX, 460), 'THE CRAZY PART', 130, RED, t, T['crazy'] - 0.05, rot=-4)
    elif sc == 9:  # deux parents bruns, porteurs sans le savoir
        show(img, 7, CX, 1190, 900, 1000, SC[9], t, wob=1.2)
        word(img, (CX, 380), '2 DARK-HAIRED PARENTS', 90, DARK, t, T['two2'] - 0.05)
        if after(t, 'carry'): word(img, (CX, 490), 'BOTH CARRY IT', 90, REDH, t, T['carry'] - 0.05)
        if after(t, 'without'): stamp(img, (CX, 610), 'WITHOUT KNOWING', 90, INK, t, T['without'] - 0.05, rot=-3)
    elif sc == 10:  # 1 chance sur 4
        show(img, 8, CX, 1150, 1000, 800, SC[10], t, wob=1.2)
        word(img, (CX, 430), 'THEIR BABY', 100, INK, t, T['baby'] - 0.1)
        if after(t, 'one2'): stamp(img, (CX, 590), '1 IN 4 CHANCE', 140, REDH, t, T['one2'] - 0.05, rot=-3)
    elif sc == 11:  # le même interrupteur change ce que le corps ressent
        show(img, 9, CX, 1170, 860, 1050, SC[11], t, wob=1.5)
        word(img, (CX, 400), 'SAME SWITCH', 110, BLUE, t, T['same'] - 0.1)
        if after(t, 'feels'): word(img, (CX, 520), 'HOW YOUR BODY FEELS', 90, INK, t, T['feels'] - 0.2)
    elif sc == 12:  # l'étude de 2004
        show(img, 10, CX, 1120, 960, 900, SC[12], t, wob=1.2)
        stamp(img, (CX, 460), '2004 STUDY', 140, INK, t, T['y2004'] - 0.05, rot=-3)
    elif sc == 13:  # CLIP 3 : le dentiste, 20 % d'anesthésie en plus
        clip(img, 3, SC[13], t, speed=1.9)
        if after(t, 'n20'): ctag(img, d, (CX, 330), '+20% ANESTHESIA', 120, REDH, t, T['n20'] - 0.1, rot=0)
    elif sc == 14:  # peau pâle → vitamine D sous les nuages
        show(img, 11, CX, 1110, 1080, 1120, SC[14], t, wob=0.8, float_=5)
        if after(t, 'pale'): word(img, (CX, 380), 'PALE SKIN', 110, INK, t, T['pale'] - 0.05)
        if after(t, 'vitamin'): stamp(img, (CX, 500), '= MORE VITAMIN D', 100, ORANGE, t, T['vitamin'] - 0.05, rot=-3)
    elif sc == 15:  # Écosse et Irlande
        show(img, 12, CX, 1160, 1080, 1000, SC[15], t, wob=0.5, float_=4)
        word(img, (CX, 430), 'SCOTLAND', 130, BLUE, t, T['scotland'] - 0.05)
        if after(t, 'ireland'): word(img, (CX, 570), '& IRELAND', 120, GREEN, t, T['ireland'] - 0.05)
    elif sc == 16:  # plus d'1 sur 10
        show(img, 13, CX, 1130, 1020, 700, SC[16], t, wob=1)
        if after(t, 'n1'): stamp(img, (CX, 470), 'MORE THAN 1 IN 10', 120, REDH, t, T['n1'] - 0.1, rot=-3)
    elif sc == 17:  # CLIP 4 : coup de soleil, crème solaire
        clip(img, 4, SC[17], t, speed=1.75)
        if after(t, 'burns') and t < T['sunscreen'] - 0.1: ctag(img, d, (CX, 1500), 'BURNS FAST', 120, RED, t, T['burns'] - 0.05, rot=0)
        if after(t, 'sunscreen'): ctag(img, d, (CX, 1500), 'SUNSCREEN = A MUST', 110, ORANGE, t, T['sunscreen'] - 0.05, rot=0)
    elif sc == 18:  # le mythe de l'extinction
        show(img, 14, CX, 1200, 980, 1000, SC[18], t, wob=1.2)
        stamp(img, (CX, 390), 'MYTH', 150, RED, t, T['no'] - 0.05, rot=-6)
        if after(t, 'extinct'): stamp(img, (CX, 540), 'NOT GOING EXTINCT', 100, GREEN, t, T['extinct'] - 0.05, rot=-3)
    elif sc == 19:  # CLIP 5 : le gène se cache de génération en génération
        clip(img, 5, SC[19], t, speed=1.9, start=3.2)
        if after(t, 'hides'): ctag(img, d, (CX, 300), 'THE GENE JUST HIDES', 105, REDH, t, T['hides'] - 0.1, rot=0)
    elif sc == 20:  # la question finale
        show(img, 15, CX, 1060, 820, 1000, SC[20], t, wob=1.5, float_=8)
        bubble(img, d, CX, 240, 'Do you have a redhead in your family?', t, SC[20] + 0.05, 54)
SOURCE = ('Sources: Liem et al., Anesthesiology 2004 · MedlinePlus Genetics (MC1R)', T['y2004'] - 0.2, T['scientists'] - 0.3)
HOT = re.compile(r'(red|mc1r|switch|broken|dark|four|2004|20|anesthesia|vitamin|scotland|ireland|sunscreen|extinct|hides|crazy|pigment)', re.I)
def SFX(sfx):
    sfx('pop', T['explained'], 0.12); sfx('swish', T['red'], 0.15); sfx('hit', T['red'] + 0.02, 0.2); sfx('shine', T['hundred'], 0.1)
    sfx('swish', T['heres'] - 0.1, 0.1); sfx('pop', T['workers'], 0.12); sfx('pop', T['dark'], 0.1); sfx('pop', T['red1'], 0.12)
    sfx('hit', T['mc1r'] - 0.05, 0.22); sfx('click', T['works'] - 0.1, 0.25); sfx('glitch', T['broken'] - 0.05, 0.14); sfx('hit', T['crazy'] - 0.05, 0.25)
    sfx('pop', T['parents'], 0.1); sfx('ding', T['carry'], 0.1); sfx('shine', T['four'], 0.12); sfx('hit', T['one2'] - 0.05, 0.2)
    sfx('pop', T['same'], 0.1); sfx('hit', T['y2004'] - 0.05, 0.2); sfx('ding', T['n20'] - 0.05, 0.12); sfx('shine', T['vitamin'], 0.12)
    sfx('pop', T['scotland'], 0.1); sfx('pop', T['ireland'], 0.1); sfx('hit', T['n1'] - 0.1, 0.2); sfx('buzz', T['burns'], 0.05); sfx('ding', T['sunscreen'], 0.1)
    sfx('hit', T['no'] - 0.05, 0.25); sfx('ding', T['extinct'], 0.12); sfx('shine', T['hides'], 0.12); sfx('pop', T['so1'] - 0.1, 0.15)
