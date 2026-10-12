# Short fitness (9:16) : chaque scène = une phrase du script (un ou plusieurs morceaux de voix)
# + ce qu'on montre. Les silences sont raccourcis (GAP).
import json, sys
plan = json.load(open(sys.argv[1])); SEG = json.loads(sys.argv[2]); out = sys.argv[3]
GAP = 0.3
t, clips, scenes = 0.2, [], []
for sc in plan['scenes']:
    parts = []
    for i in sc['segs']:
        a, b = SEG[i]
        clips.append({'src': [a, b], 'at': round(t, 3)})
        parts.append([round(t, 3), round(t + b - a, 3)])
        t += b - a + GAP
    s = {k: v for k, v in sc.items() if k != 'segs'}
    s.update({'t0': parts[0][0], 't1': parts[-1][1], 'parts': parts})
    t += sc.get('hold', 0)
    scenes.append(s)
cfg = {k: v for k, v in plan.items() if k != 'scenes'}
cfg.update({'dur': round(t + 0.6, 3), 'scenes': scenes, 'clips': clips})
json.dump(cfg, open(out, 'w'), indent=1, ensure_ascii=False)
print('durée', cfg['dur'])
