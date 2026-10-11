# Construit la chronologie d'une vidéo courte à partir des phrases de la voix off.
# plan.json : { pseudo, bg, banner?, lines: [{ segs:[i,...], text, role, ...options }] }
# Les silences sont raccourcis (GAP) et des pauses sont ajoutées selon le rôle.
import json, sys
plan = json.load(open(sys.argv[1])); SEG = json.loads(sys.argv[2]); out = sys.argv[3]
GAP = plan.get('gap', 0.2)
HOLD = {'q': 0.9, 'ask': 0.3, 'reveal': 0.55, 'punch': 0.35, 'verdict': 0.45}
t, clips, lines, scene = 0.15, [], [], 0
for ln in plan['lines']:
    a, b = SEG[ln['segs'][0]][0], SEG[ln['segs'][-1]][1]
    L = b - a
    if ln.get('newScene', ln['role'] in ('ask', 'num', 'end_start', 'intro_start')): scene += 1
    clips.append({'src': [a, b], 'at': round(t, 3)})
    o = {k: v for k, v in ln.items() if k not in ('segs', 'newScene')}
    o.update({'t0': round(t, 3), 't1': round(t + L, 3), 'scene': scene})
    t += L
    if ln['role'] == 'q': o['yn'] = round(t + 0.05, 3)
    t += GAP + HOLD.get(ln['role'], 0)
    lines.append(o)
dur = round(t + 0.5, 3)
cfg = {k: v for k, v in plan.items() if k != 'lines'}
cfg.update({'dur': dur, 'lines': lines, 'clips': clips})
json.dump(cfg, open(out, 'w'), indent=1, ensure_ascii=False)
print(out, 'durée', dur)
