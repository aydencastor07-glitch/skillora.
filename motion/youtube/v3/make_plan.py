# Plan de la vidéo « abdos » : chaque scène = une ou plusieurs lignes du script (lignes → morceaux de voix via lines.json).
import json, sys
LINES = json.load(open(sys.argv[1]))
AX, AY = 0.47, 0.345                                   # abdos (coord. image de base.png)
ABS = [1.0, 0.5, 0.5, 2.3, 0.5, 0.36]                  # zoom sur les abdos
def tg(at=0.25): return [{'name': 'Abs', 'color': 'red', 'x': AX, 'y': AY, 'style': 'dash', 'at': at, 'len': 300}]
def rep(a, b, per, cam=None, **k): return dict(img=a, alt=b, period=per, cam=cam or [1.2, 0.5, 0.55, 1.3, 0.5, 0.55], **k)
FLOOR = [1.15, 0.5, 0.6, 1.25, 0.5, 0.6]
S = [
 ([0], dict(img='fat', enter='up', cam=[1.3, 0.5, 0.45, 1.75, 0.5, 0.45], say='a big *belly*', spoken=LINES[0]['text'], sayFrom=3, sayY=0.82)),
 ([1], dict(card="here's the truth nobody tells you")),
 ([2], dict(img='fat_situp', enter='fade', cam=[1.0, 0.5, 0.55, 1.1, 0.5, 0.55], icons=[{'kind': 'x', 'at': 0.6}])),
 ([3], dict(img='fat_situp', cam=[1.1, 0.5, 0.55, 1.3, 0.45, 0.5], text="sit-ups won't burn it", textY=0.15, textX=0.5)),
 ([4], dict(img='base', hl='hl_abs', hlAt=0.3, cam=ABS, tags=tg(0.4))),
 ([5], dict(img='fat_neutral', enter='fade', cam=[1.4, 0.5, 0.42, 1.8, 0.5, 0.45], text='hidden under fat', textAt=0.4)),
 ([6], dict(card='you need two things')),
 ([7], dict(img='fat_neutral', enter='fade', cam=[1.0, 0.5, 0.48, 1.05, 0.5, 0.48], slide={'to': 0.3, 'at': 0.05}, text='lose the fat')),
 ([8], dict(img='base', hl='hl_abs', hlAt=0.2, enter='fade', cam=[1.0, 0.5, 0.48, 1.05, 0.5, 0.48], slide={'to': 0.7, 'at': 0.05}, text='build the muscle')),
 ([9], dict(img='fat_side', enter='right', cam=[1.0, 0.5, 0.48, 1.15, 0.5, 0.45])),
 ([10], dict(img='fat_neutral', cam=[1.0, 0.5, 0.48, 1.1, 0.5, 0.46], label='#1. Eat a little less')),
 ([11], dict(card='not a crazy diet')),
 ([12], dict(reps='-300 to -500 calories a day', sets=0)),
 ([13], dict(img='p_soda', enter='fade', cam=[1.2, 0.53, 0.52, 1.35, 0.53, 0.52], icons=[{'kind': 'x', 'at': 0.55}])),
 ([14], dict(img='fat_side', cam=[1.05, 0.5, 0.48, 1.2, 0.5, 0.45], text='that alone changes everything', textAt=0.2)),
 ([15], dict(img='p_food', enter='fade', cam=[1.15, 0.5, 0.54, 1.3, 0.5, 0.54], label='#2. More protein')),
 ([16], dict(img='p_food', cam=[1.3, 0.5, 0.54, 1.45, 0.5, 0.54], text='chicken · eggs · fish · yogurt', textY=0.12, textX=0.5)),
 ([17], dict(img='base', hl='hl_abs', hlAt=0.5, cam=[1.0, 0.5, 0.48, 1.4, 0.5, 0.4], text='keeps you full', textAt=0.15, icons=[{'kind': 'v', 'at': 0.8}])),
 ([18], dict(img='fat_walk', enter='left', cam=[1.0, 0.45, 0.5, 1.05, 0.45, 0.5], label='#3. Walk every day')),
 ([19], dict(reps='8,000 – 10,000 steps', sets=0)),
 ([20], dict(img='fat_walk', cam=[1.0, 0.45, 0.5, 1.05, 0.45, 0.5], slide={'to': 0.32, 'at': 0.05}, text='simple, but it works')),
 ([21], dict(img='base', hl='hl_abs', hlAt=0.2, cam=[1.0, 0.5, 0.5, 2.3, 0.5, 0.36], tags=tg(0.35))),
 ([22], dict(img='base', hl='hl_abs', hlAt=0.0, cam=[2.3, 0.5, 0.36, 2.5, 0.5, 0.36], say='a *muscle*', spoken=LINES[22]['text'], sayY=0.12)),
 ([23], dict(img='base', hl='hl_abs', hlAt=0.0, cam=[2.5, 0.5, 0.36, 2.6, 0.5, 0.36], text='thicker = visible', textAt=0.4)),
 ([24], dict(card='3 exercises are enough')),
 ([25], dict(medal='p_bar', name='Hanging Leg Raises', medalZoom=1.1)),
 ([26], dict(img='hang_down', enter='up', cam=[1.0, 0.5, 0.5, 1.05, 0.5, 0.5])),
 ([27], rep('hang_down', 'hang_up', 1.4, cam=[1.0, 0.55, 0.5, 1.05, 0.55, 0.5], text='no swinging', textAt=0.5, textX=0.82)),
 ([28], rep('hang_down', 'hang_up', 1.8, cam=[1.05, 0.55, 0.5, 1.1, 0.55, 0.5])),
 ([29], dict(reps='8-12 reps')),
 ([30], dict(card='no bar at home?')),
 ([31], dict(medal='p_mat', name='Lying Leg Raises', medalZoom=1.2, medalDy=-120)),
 ([32], dict(img='lie_down', enter='right', cam=[1.2, 0.5, 0.62, 1.25, 0.5, 0.62])),
 ([33], rep('lie_down', 'lie_up', 1.5, cam=[1.1, 0.5, 0.55, 1.15, 0.5, 0.55], text="don't touch the floor", textAt=0.55, textY=0.15, textX=0.5)),
 ([34], dict(reps='12-15 reps')),
 ([35], dict(medal='p_mat', name='The Crunch', medalZoom=1.2, medalDy=-120)),
 ([36], dict(card='done right')),
 ([37], dict(img='crunch_down', enter='right', cam=FLOOR)),
 ([38], rep('crunch_down', 'crunch_up', 1.4, cam=[1.25, 0.5, 0.58, 1.35, 0.45, 0.56], text='squeeze 1s at the top', textAt=0.5, textY=0.2, textX=0.5)),
 ([39], dict(img='crunch_up', cam=[2.0, 0.25, 0.52, 2.2, 0.25, 0.52], icons=[{'kind': 'x', 'at': 0.3}], text="don't pull your neck", textAt=0.2)),
 ([40], dict(img='base', hl='hl_abs', hlAt=0.3, cam=[1.6, 0.5, 0.36, 2.4, 0.5, 0.36], say='the *six-pack*', spoken=LINES[40]['text'], sayY=0.12)),
 ([41], dict(reps='15 reps')),
 ([42], dict(medal='p_timer', name='Plank', medalZoom=1.05)),
 ([43], dict(img='plank', enter='right', cam=[1.15, 0.5, 0.48, 1.2, 0.5, 0.48], text='one straight line', textAt=0.6, textY=0.18, textX=0.5)),
 ([44], dict(img='plank', cam=[1.2, 0.5, 0.48, 1.6, 0.55, 0.45], text='squeeze', textAt=0.4, textY=0.18, textX=0.5)),
 ([45], dict(img='plank', cam=[1.6, 0.55, 0.45, 1.65, 0.55, 0.45], text='30-60s', textAt=0.3, textY=0.18, textX=0.5)),
 ([46], dict(img='fat_side', cam=[1.05, 0.5, 0.48, 1.15, 0.5, 0.45], seq=[{'at': 0.55, 'img': 'base', 'hl': 'hl_abs'}], text='a flatter stomach', textAt=0.6)),
 ([47], dict(reps='30-60s')),
 ([48], dict(card='3 mistakes that keep your belly big')),
 ([49], dict(img='fat_situp', cam=[1.0, 0.5, 0.55, 1.1, 0.5, 0.55], label='#1. Only doing abs', icons=[{'kind': 'x', 'at': 0.3}], text='diet + walking', textAt=0.6, textY=0.15, textX=0.5)),
 ([50], rep('crunch_down', 'crunch_up', 0.35, cam=FLOOR, label='#2. Abs every day', icons=[{'kind': 'x', 'at': 0.3}], text='they need rest', textAt=0.6, textY=0.2, textX=0.5)),
 ([51], dict(img='fat_neutral', cam=[1.0, 0.5, 0.48, 1.1, 0.5, 0.45], label='#3. Giving up too soon', icons=[{'kind': 'x', 'at': 0.25}], text='slow at first, then fast', textAt=0.6)),
 ([52], dict(card='your plan')),
 ([53], dict(img='fat_walk', enter='left', cam=[1.0, 0.45, 0.5, 1.05, 0.45, 0.5], text='walk · eat less · protein', textAt=0.3)),
 ([54], dict(img='hang_up', cam=[1.0, 0.55, 0.5, 1.0, 0.55, 0.5], seq=[{'at': 0.38, 'img': 'lie_up'}, {'at': 0.7, 'img': 'crunch_up'}])),
 ([55], dict(reps='each')),
 ([56], dict(card='three months')),
 ([57], dict(img='fat_neutral', enter='fade', cam=[1.0, 0.5, 0.48, 1.15, 0.5, 0.45])),
 ([58, 59], dict(img='fat_neutral', cam=[1.0, 0.5, 0.48, 1.0, 0.5, 0.48], seq=[{'at': 0.3, 'img': 'base', 'hl': 'hl_abs'}], slide={'to': 0.3, 'at': 0.45}, text='your abs will show')),
 ([60], dict(img='base', hl='hl_abs', hlAt=0.0, enter='fade', cam=[1.0, 0.5, 0.48, 1.1, 0.5, 0.45], text='your whole body looks complete', textAt=0.5)),
 ([61], dict(img='base', hl='hl_all', hlAt=0.2, cam=[1.3, 0.5, 0.4, 2.3, 0.5, 0.27], say='a strong *chest*', spoken=LINES[61]['text'])),
 ([62, 63], dict(img='flex', x=0.2, cam=[0.85, 0.5, 0.5, 0.9, 0.5, 0.5], next={'img': 'thumb_chest', 'title': 'How Skinny Guys Build a Chest (3 Parts Most Ignore)'})),
 ([64, 65], dict(subscribe=True, clickAt=0.25, text='new videos every Tuesday & Saturday', hold=1.5)),
]
scenes = []
for lines, d in S:
    d = dict(d); d['segs'] = [sg for l in lines for sg in LINES[l]['segs']]
    d['voice'] = ' '.join(LINES[l]['text'] for l in lines)
    scenes.append(d)
json.dump({'png': 'png_kai', 'scenes': scenes}, open(sys.argv[2], 'w'), indent=1, ensure_ascii=False)
print(len(scenes), 'scènes')
