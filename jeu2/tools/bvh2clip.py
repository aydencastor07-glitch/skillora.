# Convertit un BVH CMU (version cgspeed) en clip de mouvement pour rig.js (même format que mocap/*.json) :
# orientations absolues de 20 os par rapport à la pose en T, dans le repère du personnage, hanche relative.
# usage : bvh2clip.py fichier.bvh sortie.json debut_s fin_s [--loop] [--inplace]   (voir CONV plus bas)
import sys, json, re, numpy as np
from scipy.spatial.transform import Rotation as Rot
MAP = {'pelvis': 'Hips', 'sp0': 'LowerBack', 'sp1': 'Spine', 'sp2': 'Spine1', 'neck': 'Neck', 'head': 'Head',
       'lClav': 'LeftShoulder', 'lUp': 'LeftArm', 'lFore': 'LeftForeArm', 'lHand': 'LeftHand',
       'rClav': 'RightShoulder', 'rUp': 'RightArm', 'rFore': 'RightForeArm', 'rHand': 'RightHand',
       'lThigh': 'LeftUpLeg', 'lCalf': 'LeftLeg', 'lFoot': 'LeftFoot', 'rThigh': 'RightUpLeg', 'rCalf': 'RightLeg', 'rFoot': 'RightFoot'}
NAMES = list(MAP)
def parse(path):
    txt = open(path).read(); head, mot = txt.split('MOTION')
    joints, stack, cur = [], [], None
    for tok in re.findall(r'(ROOT|JOINT|End Site|OFFSET|CHANNELS|\{|\})[ \t]*([^\n]*)', head):
        k, rest = tok
        if k in ('ROOT', 'JOINT'):
            cur = {'name': rest.strip(), 'parent': stack[-1] if stack else None, 'ch': []}; joints.append(cur)
        elif k == 'End Site': cur = {'name': None, 'parent': stack[-1], 'ch': []}
        elif k == 'OFFSET': cur['off'] = np.array(list(map(float, rest.split())))
        elif k == 'CHANNELS': cur['ch'] = rest.split()[1:]
        elif k == '{': stack.append(cur['name'] if cur['name'] else stack[-1])
        elif k == '}': stack.pop()
    lines = mot.strip().split('\n'); ft = float(lines[1].split(':')[1]); data = np.array([list(map(float, l.split())) for l in lines[2:] if l.strip()])
    return joints, ft, data
def world_rots(joints, data):
    n = len(data); R = {}; P = {}; col = 0
    for j in joints:
        ch = j['ch']; vals = data[:, col:col + len(ch)]; col += len(ch)
        rch = [c for c in ch if c.endswith('rotation')]; idx = [ch.index(c) for c in rch]
        order = ''.join(c[0] for c in rch)
        loc = Rot.from_euler(order.upper(), vals[:, idx], degrees=True)   # intrinsèque, ordre des canaux
        if j['parent'] is None:
            R[j['name']] = loc; pi = [ch.index(c) for c in ('Xposition', 'Yposition', 'Zposition')]; P['root'] = vals[:, pi]
        else: R[j['name']] = R[j['parent']] * loc
    return R, P
def rest_hip(joints):
    by = {j['name']: j for j in joints if j['name']}
    h = 0; n = 'LeftFoot'
    while by[n]['parent']: h += -by[n]['off'][1] if n != 'Hips' else 0; n = by[n]['parent']
    return h * 1.115   # hauteur de la hanche debout (jambe + pied jusqu'au sol)
def analyse(path):
    joints, ft, data = parse(path); R, P = world_rots(joints, data); hh = rest_hip(joints); p = P['root']; fps = 1 / ft
    for s in range(0, int(len(data) * ft)):
        a, b = int(s * fps), min(len(data) - 1, int((s + 1) * fps))
        v = np.linalg.norm(p[b, [0, 2]] - p[a, [0, 2]]) / hh; print(f'{s:3d}s  hanche {p[a,1]/hh:5.2f}  vitesse {v:4.2f}')
def convert(path, out, t0, t1, loop=False, inplace=True, fps_out=30, heading=None, legfix=True):
    joints, ft, data = parse(path); hh = rest_hip(joints)
    i0, i1 = int(t0 / ft), int(t1 / ft); step = max(1, int(round(1 / fps_out / ft)))
    d = data[i0:i1:step]; R, P = world_rots(joints, d); p = P['root']
    # cap : direction du déplacement (si assez de mouvement) sinon orientation moyenne du bassin, ramenée vers +Z
    if heading is None:
        mv = p[-1, [0, 2]] - p[0, [0, 2]]
        if np.linalg.norm(mv) / hh > 0.5 * (len(d) / fps_out): heading = np.arctan2(mv[0], mv[1])
        else:
            fwd = R['Hips'].apply([0, 0, 1]); heading = np.arctan2(fwd[:, 0].mean(), fwd[:, 2].mean())
    Y = Rot.from_euler('y', -heading)
    # jambes : au repos, le squelette CMU a les cuisses et les tibias écartés (~20°) alors que le personnage les a verticaux ;
    # sans correction les pieds se croisent devant. On compose avec la rotation « vertical -> direction de repos du BVH ».
    by = {j['name']: j for j in joints if j['name']}; child = {j['parent']: j['name'] for j in joints if j['name'] and j['parent']}
    FIX = {}
    if legfix:
        for n in ('lThigh', 'rThigh', 'lCalf', 'rCalf'):
            off = by[child[MAP[n]]]['off']; dv = off / np.linalg.norm(off); dv = np.array([dv[0], dv[1], 0]); dv /= np.linalg.norm(dv)
            FIX[n] = Rot.align_vectors([dv], [[0, -1, 0]])[0]
    q = np.stack([((Y * R[MAP[n]] * FIX[n]) if n in FIX else (Y * R[MAP[n]])).as_quat() for n in NAMES], 1)
    for b in range(q.shape[1]):                     # continuité des quaternions
        for f in range(1, len(q)):
            if np.dot(q[f, b], q[f - 1, b]) < 0: q[f, b] *= -1
    rel = Y.apply(np.c_[p[:, 0] - p[0, 0], p[:, 1] * 0, p[:, 2] - p[0, 2]]) / hh
    pp = np.c_[rel[:, 0], (p[:, 1] - hh) / hh, rel[:, 2]]
    dur = len(d) / fps_out; speed = float(np.linalg.norm(rel[-1, [0, 2]]) / dur)
    if inplace: pp[:, 0] = 0; pp[:, 2] = 0
    o = {'fps': fps_out, 'names': NAMES, 'hipH': hh, 'frames': len(d), 'q': [round(float(x), 4) for x in q.reshape(-1)],
         'p': [round(float(x), 4) for x in pp.reshape(-1)], 'loop': loop, 'speed': speed}
    json.dump(o, open(out, 'w')); print(out, len(d), 'images', round(dur, 2), 's', 'vitesse', round(speed, 3), 'hipH/s')
def cycle(path, t0, tmin=0.45, tmax=1.3):
    # cherche la fin de cycle (pose la plus proche de celle de t0) pour une boucle propre
    joints, ft, data = parse(path); R, _ = world_rots(joints, data)
    i0 = int(t0 / ft); best = None
    for i in range(i0 + int(tmin / ft), min(len(data) - 1, i0 + int(tmax / ft))):
        e = sum(R[MAP[n]][i0].inv().__mul__(R[MAP[n]][i]).magnitude() for n in ('lThigh', 'rThigh', 'lCalf', 'rCalf', 'lUp', 'rUp') for _ in [0] if True)
        if best is None or e < best[0]: best = (e, i)
    return best[1] * ft
if __name__ == '__main__':
    a = sys.argv
    if a[1] == 'analyse': analyse(a[2])
    else: convert(a[1], a[2], float(a[3]), float(a[4]), loop='--loop' in a, inplace='--root' not in a, legfix='--nolegfix' not in a)
