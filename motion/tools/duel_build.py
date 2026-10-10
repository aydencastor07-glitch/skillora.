# Construit motion/duel/video.json : scènes + sous-titres, à partir des phrases de la voix off
# (début/fin de chaque phrase détectés dans le MP3). Chaque phrase est replacée au début de sa scène.
import json, sys
SEG = json.loads(sys.argv[1])  # [[début, fin], ...] dans le MP3
out = sys.argv[2]
P = [  # (type, texte affiché, options)
    ('open', 'Do you *really* know your boyfriend?', {'img': 'ouverture', 'tag': 'Difficulty: IMPOSSIBLE', 'fx': 0.55, 'fy': 0.62}),
    ('say', 'If she makes more than *2 mistakes,* she owes you a *bl*wjob!* 🤭', {'img': 'pipe'}),
    ('q', 'Tight *or* loose clothes?', {'a': {'img': 'q1a', 'label': 'Tight'}, 'b': {'img': 'q1b', 'label': 'Loose'}}),
    ('q', 'Star Wars *or* Harry Potter?', {'a': {'img': 'q2a', 'label': 'Star Wars', 'logo': 'starwars_logo'}, 'b': {'img': 'q2b', 'label': 'Harry Potter'}}),
    ('skip', 'Lamborghini or Ferrari?', {}),  # pas d'images reçues : phrase retirée
    ('q', 'Beer *or* Whiskey?', {'a': {'img': 'q3a', 'label': 'Beer'}, 'b': {'img': 'q3b', 'label': 'Whiskey'}}),
    ('q', 'Burger King *or* McDonald\'s?', {'a': {'img': 'q4a', 'label': 'Burger King'}, 'b': {'img': 'q4b', 'label': "McDonald's"}}),
    ('q', 'Going out *or* gaming?', {'a': {'img': 'q5a', 'label': 'Going out'}, 'b': {'img': 'q5b', 'label': 'Gaming'}}),
    ('q', 'Who is his *future wife?*', {'a': {'img': 'mariage'}}),
    ('say', '*Tag* your partner to test her.', {'emoji': '👇'}),
    ('say', '*Subscribe* for more quizzes!', {'emoji': '🔔'}),
]
assert len(P) == len(SEG)
scenes, caps, clips = [], [], []
t = 0.0
for (typ, text, o), (a, b) in zip(P, SEG):
    if typ == 'skip':
        continue
    L = b - a
    if typ == 'open':
        at, d = 0.25, max(2.6, 0.25 + L + 0.6)
        s = {'type': 'open', 'title': text, 'd': d, **o}
    elif typ == 'say':
        at, d = 0.2, 0.2 + L + 0.45
        s = {'type': 'say', 'd': d, **o}
    else:
        at = 0.55
        cd = at + L + 0.25
        s = {'type': 'q', 'q': text, 'qv': [at, at + L], 'cd': cd, 'd': cd + 3.35, **o}
    s['t'] = round(t, 3)
    scenes.append(s)
    caps.append({'t0': round(t + at, 3), 't1': round(t + at + L, 3), 'text': text, 'scene': typ})
    clips.append({'src': [a, b], 'at': round(t + at, 3)})
    t += s['d']
json.dump({'pseudo': '@exxtory', 'voice': 'voix.mp3', 'bg': 'fond', 'colors': ['#9b59d0', '#d56bc4'], 'scenes': scenes,
           'captions': [c for c in caps if c['scene'] != 'q'], 'clips': clips}, open(out, 'w'), indent=1, ensure_ascii=False)
print('durée', round(t, 2), 's,', len(scenes), 'scènes')
