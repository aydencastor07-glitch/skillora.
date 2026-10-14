# Short vertical (9:16) tiré d'une vidéo longue : on garde les scènes des lignes a..b du script, puis une carte de fin.
# usage : short_build.py plan_long.json lines.json a b out_plan.json "texte de fin"
import json, sys
plan = json.load(open(sys.argv[1])); L = json.load(open(sys.argv[2])); a, b = int(sys.argv[3]), int(sys.argv[4])
keep = {sg for l in L[a:b + 1] for sg in l['segs']}
sc = [dict(s) for s in plan['scenes'] if s['segs'] and set(s['segs']) <= keep]
for s in sc:
    for k in ('slide', 'x', 'next', 'subscribe'): s.pop(k, None)
    if s.get('enter') in ('left', 'right'): s['enter'] = 'fade'
sc.append({'card': sys.argv[6], 'segs': [], 'dur': 2.2, 'instant': False})
json.dump({'png': plan['png'], 'vertical': True, 'scenes': sc}, open(sys.argv[5], 'w'), indent=1, ensure_ascii=False)
print(len(sc), 'scènes')
