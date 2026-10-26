# Vidéo « Is your girlfriend allowed to…? » : une image par question.
# La voix dit « Is she allowed to … » ; à l'écran on n'écrit que l'action (après PREFIX secondes).
import json, sys
SEG = json.loads(sys.argv[1]); out = sys.argv[2]
PREFIX = 0.75
P = [  # (type, texte à l'écran, phrases de la voix utilisées, options)
    ('open', 'Is your girlfriend *allowed* to…?', [0], {'img': 'p_open', 'tag': 'HARD EDITION 🔥', 'fx': 0.5, 'fy': 0.4}),
    ('q', 'Go *clubbing* without you?', [1], {'a': {'img': 'p_q1'}}),
    ('q', 'Stay friends with her *ex* on Instagram?', [2], {'a': {'img': 'p_q2'}}),
    ('q', 'Like *another guy\'s* photos?', [3], {'a': {'img': 'p_q3'}}),
    ('q', 'Sleep over at a guy friend\'s place… *alone?*', [4, 5], {'a': {'img': 'p_q4'}}),
    ('say', 'Wait… the *last question* changes everything.', [6], {'emoji': '⚠️'}),
    ('q', 'Read your *messages* without asking?', [7], {'a': {'img': 'p_q5'}}),
    ('q', 'Know your phone *password?*', [8], {'a': {'img': 'p_q6'}}),
    ('say', ['So, how many *yes?*', 'Drop your *score* in the comments.'], [9, 10], {'emoji': '👇'}),
    ('say', '*Send this* to your girlfriend and see her answers!', [11], {'emoji': '📲'}),
]
scenes, caps, clips = [], [], []
t = 0.0
for typ, text, idx, o in P:
    a, b = SEG[idx[0]][0], SEG[idx[-1]][1]
    L = b - a
    if typ == 'open':
        at = 0.25; d = max(2.8, at + L + 0.7)
        s = {'type': 'open', 'title': text, 'd': d, **o}
        caps.append({'t0': round(t + at, 3), 't1': round(t + at + L, 3), 'text': text})
    elif typ == 'say':
        at = 0.2; d = at + L + 0.55
        s = {'type': 'say', 'd': d, **o}
        texts = text if isinstance(text, list) else [text]
        for k, i in enumerate(idx):
            caps.append({'t0': round(t + at + SEG[i][0] - a, 3), 't1': round(t + at + SEG[i][1] - a, 3), 'text': texts[min(k, len(texts) - 1)]})
    else:
        at = 0.5; cd = at + L + 0.25
        s = {'type': 'q', 'q': text, 'qv': [at + min(PREFIX, L * 0.4), at + L], 'cd': cd, 'd': cd + 3.35, **o}
    s['t'] = round(t, 3)
    scenes.append(s)
    clips.append({'src': [a, b], 'at': round(t + at, 3)})
    t += s['d']
json.dump({'pseudo': '@exxtory', 'voice': 'voix2.mp3', 'music': 'musique.mp3', 'bg': 'fond', 'scenes': scenes, 'captions': caps, 'clips': clips},
          open(out, 'w'), indent=1, ensure_ascii=False)
print('durée', round(t, 2), 's')
