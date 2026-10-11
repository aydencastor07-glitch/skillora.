# « Count her YES » (≤ 30 s) : la voix est découpée en phrases, les silences raccourcis,
# et une courte pause YES/NO est ajoutée après chaque question.
import json, sys
SEG = json.loads(sys.argv[1]); out = sys.argv[2]
GAP, HOLD = 0.22, 0.9
# rôle de chaque phrase de la voix
ROLE = ['hook', 'hook', 'intro', 'intro',
        ('num', 5), ('q', 5), ('num', 4), ('q', 4), ('num', 3), ('q', 3), ('num', 2), ('q', 2), ('num', 1), ('q', 1),
        'end', 'end', 'end']
TEXT = ['Send this to your *girlfriend*…', 'if you *dare.*', '*5* questions.', 'Count her *YES.*',
        'Number five.', 'Would she go through your *phone?*', 'Number four.', 'Text her *ex* "happy birthday"?',
        'Number three.', 'Go on *vacation* without you?', 'Number two.', '*Lie* about where she is?',
        'Number one…', 'Would she still love you if you were *broke?*',
        '*3 YES* or more?', 'Comment your *score…*', 'and watch it *again* with her.']
IMG = {5: 'p_q5', 4: 'c_q4', 3: 'c_q3', 2: 'c_q2', 1: 'c_q1'}
t, clips, lines = 0.15, [], []
for i, (a, b) in enumerate(SEG):
    L = b - a
    clips.append({'src': [a, b], 'at': round(t, 3)})
    r = ROLE[i]
    lines.append({'t0': round(t, 3), 't1': round(t + L, 3), 'text': TEXT[i], 'role': r if isinstance(r, str) else r[0], 'n': r[1] if not isinstance(r, str) else None})
    t += L + GAP
    if isinstance(r, tuple) and r[0] == 'q':
        lines[-1]['yn'] = round(t - GAP + 0.05, 3); t += HOLD
dur = round(t + 0.6, 3)
json.dump({'pseudo': '@exxtory', 'bg': 'fond', 'hookImg': 'c_hook', 'img': {str(k): v for k, v in IMG.items()}, 'dur': dur,
           'lines': lines, 'clips': clips}, open(out, 'w'), indent=1, ensure_ascii=False)
print('durée', dur)
