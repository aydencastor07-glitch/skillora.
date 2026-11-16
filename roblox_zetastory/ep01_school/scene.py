# ZetaStory ép. 1 – « In my school, your grades decide your height » : toute la vidéo dans Blender (EEVEE), personnages en blocs.
# Décors : cour + école (x=0), classe (x=100), couloir (x=200), bureau du directeur (x=300). Chaque plan règle tout à chaque image.
# usage : blender -b -P scene.py -- CHARS_DIR OUT n0 n1 [W H]     (ONLY=12,340 : seulement ces images ; TAA=8)
import bpy, sys, os, math, random
from mathutils import Vector, Euler
argv = sys.argv[sys.argv.index('--') + 1:]
CH, OUT, n0, n1 = argv[0], argv[1], int(argv[2]), int(argv[3])
W = int(argv[4]) if len(argv) > 4 else 720; H = int(argv[5]) if len(argv) > 5 else 1280
FPS = 30; rnd = random.Random(7)
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene; COL = sc.collection
R = math.radians
def ss(a, b, x):
    u = max(0.0, min(1.0, (x - a) / (b - a))) if b != a else 1.0; return u * u * (3 - 2 * u)
def lerp(a, b, u): return a + (b - a) * u
def hexc(h): h = h.lstrip('#'); return tuple(((int(h[i:i + 2], 16) / 255) ** 2.2) for i in (0, 2, 4)) + (1,)
MATS = {}
def mat(col, rough=0.7, emit=0.0, alpha=1.0, metal=0.0):
    k = (col, rough, emit, alpha, metal)
    if k in MATS: return MATS[k]
    m = bpy.data.materials.new('m'); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = hexc(col); b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    if emit: b.inputs['Emission Color'].default_value = hexc(col); b.inputs['Emission Strength'].default_value = emit
    if alpha < 1: b.inputs['Alpha'].default_value = alpha; m.blend_method = 'BLEND'; m.shadow_method = 'NONE'; b.inputs['Roughness'].default_value = 0.05
    MATS[k] = m; return m
def box(w, d, h, col, x, y, z, parent=None, bevel=0.0, **kw):
    bpy.ops.mesh.primitive_cube_add(size=1); o = bpy.context.object; o.scale = (w, d, h); o.location = (x, y, z); o.data.materials.append(mat(col, **kw))
    if bevel: md = o.modifiers.new('b', 'BEVEL'); md.width = bevel; md.segments = 3
    if parent: o.parent = parent
    return o
def cyl(r, h, col, x, y, z, seg=16, **kw):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, vertices=seg); o = bpy.context.object; o.location = (x, y, z); o.data.materials.append(mat(col, **kw)); bpy.ops.object.shade_smooth(); return o
def ball(r, col, x, y, z, **kw):
    bpy.ops.mesh.primitive_ico_sphere_add(radius=r, subdivisions=2); o = bpy.context.object; o.location = (x, y, z); o.data.materials.append(mat(col, **kw)); return o
FONT = bpy.data.fonts.load('/home/user/skillora./temu/fonts/ArchivoBlack-Regular.ttf')
def text(s, size, col, x, y, z, rot=(90, 0, 0), emit=0.0, ext=0.01):
    c = bpy.data.curves.new('t', 'FONT'); c.body = s; c.size = size; c.align_x = 'CENTER'; c.align_y = 'CENTER'; c.extrude = ext; c.font = FONT
    o = bpy.data.objects.new('t', c); COL.objects.link(o); o.location = (x, y, z); o.rotation_euler = tuple(R(v) for v in rot); c.materials.append(mat(col, emit=emit)); return o
def light(kind, loc, energy, col=(1, 1, 1), size=1.0, tgt=None, shadow=True):
    l = bpy.data.lights.new('L', kind); l.energy = energy; l.color = col; l.use_shadow = shadow
    if kind == 'AREA': l.size = size
    if kind == 'SPOT': l.spot_size = R(size); l.spot_blend = 0.5
    o = bpy.data.objects.new('L', l); COL.objects.link(o); o.location = loc
    if tgt is not None: o.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    o['e'] = energy; return o
# ---------- personnages ----------
FACES = {}
def face_img(k):
    if k not in FACES:
        im = bpy.data.images.load(os.path.join(CH, f'face_BK_{k}.png')); w, h = im.size; px = list(im.pixels); rows = [px[r * w * 4:(r + 1) * w * 4] for r in range(h)]
        im.pixels = [v for r in reversed(rows) for v in r]; FACES[k] = im
    return FACES[k]
class Char:
    def __init__(s, glb, pre, shirt=None, pants=None, hair=None, skin=None):
        before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=os.path.join(CH, glb)); s.objs = [o for o in bpy.data.objects if o not in before]
        s.n = {}
        for o in s.objs:
            k = o.name.split('.')[0]
            if k.startswith(pre + '_'): s.n[k[len(pre) + 1:]] = o; o.rotation_mode = 'XYZ'
        s.base = {k: o.location.copy() for k, o in s.n.items()}
        s.tex = None; seen = {}
        for o in s.objs:
            for sl in getattr(o, 'material_slots', []):
                m = sl.material
                if not m: continue
                if m.name not in seen:
                    m2 = m.copy(); seen[m.name] = m2; base = m.name.split('.')[0]
                    b = [x for x in m2.node_tree.nodes if x.type == 'BSDF_PRINCIPLED'][0]; t = [x for x in m2.node_tree.nodes if x.type == 'TEX_IMAGE']
                    if t: s.tex = t[0]; m2.blend_method = 'HASHED'
                    c = {'Material_0': shirt, 'Material_4': pants, 'Material_2': hair, 'Material_1': skin}.get(base)
                    if c and not t: b.inputs['Base Color'].default_value = hexc(c)
                sl.material = seen[m.name]
        s.face('neutral')
    def face(s, k):
        if s.tex: s.tex.image = face_img(k)
    def show(s, v=True):
        for o in s.objs: o.hide_render = not v
    def put(s, x, y, z=0, yaw=0, scale=1, pitch=0, roll=0):
        r = s.n['root']; r.location = (x, y, z); r.rotation_euler = (R(pitch), R(roll), R(yaw)); r.scale = (scale,) * 3; s.show(True)
    def pose(s, lArm=(0, 0, 0), rArm=(0, 0, 0), lLeg=0, rLeg=0, head=(0, 0, 0), upper=(0, 0, 0), hipz=0):
        s.n['lArm'].rotation_euler = tuple(R(v) for v in lArm); s.n['rArm'].rotation_euler = tuple(R(v) for v in rArm)
        s.n['lLeg'].rotation_euler = (R(lLeg), 0, 0); s.n['rLeg'].rotation_euler = (R(rLeg), 0, 0)
        s.n['head'].rotation_euler = tuple(R(v) for v in head); s.n['upper'].rotation_euler = tuple(R(v) for v in upper)
        s.n['hip'].location = s.base['hip'] + Vector((0, 0, hipz))
    def walk(s, t, sp=1.0, amp=32):
        a = math.sin(t * 6.5 * sp) * amp; s.pose(lArm=(a, 0, 0), rArm=(-a, 0, 0), lLeg=-a, rLeg=a, head=(0, 0, 0))
    def sit(s): s.pose(lLeg=-88, rLeg=-88, lArm=(-35, 0, 0), rArm=(-35, 0, 0), hipz=-0.28)
HERO = Char('char_BK.glb', 'BK', shirt='#e8231c', pants='#1c2a5e')
# « Z » doré sur le sweat du héros (comme le logo)
zt = text('Z', 0.42, '#ffcc11', 0, -0.2, 0.36, rot=(90, 0, 0), ext=0.02); zt.parent = HERO.n['upper']; HERO.objs.append(zt)
STU = [Char('char_E0.glb', 'E0', shirt='#2f7bff', pants='#30343c'), Char('char_W.glb', 'W', shirt='#ff7ac0', pants='#5a4bb0'),
       Char('char_M2.glb', 'M2', shirt='#27b36a', pants='#3b2c22'), Char('char_E1.glb', 'E1', shirt='#f2c230', pants='#2a3b55'),
       Char('char_E2.glb', 'E2', shirt='#8e5bd9', pants='#22262e'), Char('char_E3.glb', 'E3', shirt='#ff8a2b', pants='#1e3a2a')]
JAR = [Char('char_E0.glb', 'E0', shirt='#2f7bff', pants='#30343c'), Char('char_W.glb', 'W', shirt='#ff7ac0', pants='#5a4bb0'), Char('char_M2.glb', 'M2', shirt='#27b36a', pants='#3b2c22'),
       Char('char_E1.glb', 'E1', shirt='#f2c230', pants='#2a3b55'), Char('char_E3.glb', 'E3', shirt='#ff8a2b', pants='#1e3a2a')]
TEACH = Char('char_W.glb', 'W', shirt='#f4f1e8', pants='#3a3f4a', hair='#6b4a2f')
BOSS = Char('char_E1.glb', 'E1', shirt='#15161b', pants='#0d0e12', hair='#1a1a1e', skin='#c9b9a6')
tie = box(0.1, 0.03, 0.42, '#a01218', 0, -0.2, 0.42); tie.parent = BOSS.n['upper']; BOSS.objs.append(tie)
ALL = [HERO, TEACH, BOSS] + STU + JAR
# ---------- décor 1 : la cour et l'école ----------
box(150, 260, 0.2, '#58b04a', 0, 0, -0.1); box(10, 60, 0.02, '#c9c2b2', 0, -8, 0.01)
box(46, 12, 15, '#c8553c', 0, 26, 7.5); box(48, 13, 0.8, '#7a2f22', 0, 26, 15.4); box(12, 1.2, 18, '#d8674c', 0, 19.6, 9)
for ix in range(-4, 5):
    for iz in range(3):
        if abs(ix) <= 1: continue
        box(2.6, 0.3, 2.6, '#bfe6ff', ix * 4.6, 19.9, 3.2 + iz * 4.3, emit=0.25, rough=0.2); box(3.0, 0.2, 3.0, '#f1ece1', ix * 4.6, 19.95, 3.2 + iz * 4.3)
box(4.2, 0.4, 5.2, '#5a3a25', 0, 19.0, 2.6); box(5.0, 0.5, 0.5, '#f1ece1', 0, 18.95, 5.5)
text('SCHOOL', 2.3, '#ffffff', 0, 18.85, 13.2, ext=0.15); box(11, 0.3, 3.4, '#1c2a5e', 0, 18.95, 13.2)
for (x, y) in [(-16, 6), (17, 4), (-22, -8), (24, -10), (-13, -18), (14, -20), (-30, 12), (31, 13)]:
    cyl(0.5, 3, '#6b4630', x, y, 1.5, 8); ball(2.6, '#2f8f3c', x, y, 4.6); ball(1.9, '#3aa64a', x + 1, y + 0.6, 6.0)
for i in range(7): ball(3 + rnd.random() * 2, '#ffffff', -60 + i * 20 + rnd.random() * 8, 70, 30 + rnd.random() * 12, emit=0.6).scale = (2.2, 1, 0.7)
SUN = light('SUN', (0, 0, 50), 3.2, (1, 0.96, 0.88)); SUN.rotation_euler = (R(52), 0, R(-38)); SUN.data.angle = R(2)
# ---------- décor 2 : la classe (x = 100) ----------
CX = 100
box(14, 12, 0.2, '#c79b63', CX, 0, -0.1); box(14, 0.3, 6, '#e9dfc9', CX, 6, 3); box(14, 0.3, 6, '#dfd4bb', CX, -6, 3); box(0.3, 12, 6, '#dfd4bb', CX - 7, 0, 3); box(0.3, 12, 6, '#dfd4bb', CX + 7, 0, 3)
box(8, 0.12, 2.6, '#1f4d3a', CX, 5.82, 2.7); box(8.3, 0.1, 2.9, '#7a5a3a', CX, 5.86, 2.7)
BOARD1 = text('GRADES = HEIGHT', 0.55, '#f4f4ee', CX, 5.74, 3.2, emit=0.4); BOARD2 = text('GRADUATED EARLY :)', 0.55, '#f4f4ee', CX, 5.74, 2.9, emit=0.4)
for ix in (-1, 0, 1):
    for iy in (0, 1, 2):
        x, y = CX + ix * 3.4, 1.6 - iy * 2.6; box(1.5, 0.9, 0.08, '#b98654', x, y, 0.95, bevel=0.02)
        for dx in (-0.65, 0.65):
            for dy in (-0.35, 0.35): box(0.07, 0.07, 0.95, '#6f6f76', x + dx, y + dy, 0.475)
for x in (CX - 6.84,):
    for y in (-3, 1): box(0.1, 2.4, 2.2, '#bfe6ff', x, y, 3.2, emit=1.2)
PAPER = box(0.5, 0.64, 0.01, '#d9d9d4', CX, -1.05, 1.0); PF = text('F', 0.5, '#e01515', 0, 0, 0.02, rot=(0, 0, 0)); PF.parent = PAPER; PF.scale = (1 / 0.5, 1 / 0.64, 100)
PA = box(0.5, 0.64, 0.01, '#d9d9d4', CX - 3.4, -1.05, 1.0); PAt = text('A+', 0.38, '#15a03a', 0, 0, 0.02, rot=(0, 0, 0)); PAt.parent = PA; PAt.scale = (1 / 0.5, 1 / 0.64, 100)
PF2 = box(0.5, 0.64, 0.01, '#d9d9d4', CX + 3.4, -1.05, 1.0); PF2t = text('F', 0.5, '#e01515', 0, 0, 0.02, rot=(0, 0, 0)); PF2t.parent = PF2; PF2t.scale = (1 / 0.5, 1 / 0.64, 100)
CL1 = light('AREA', (CX, -1, 5.6), 1000, (1, 0.97, 0.9), 9, tgt=(CX, 0, 0)); CL2 = light('AREA', (CX - 4, 3, 3.5), 350, (0.8, 0.9, 1), 5, tgt=(CX, 0, 1.5), shadow=False)
# ---------- décor 3 : le couloir (x = 200), porte du directeur au fond (y = 6) ----------
KX = 200
box(5, 26, 0.2, '#8f9aa6', KX, -6, -0.1); box(0.3, 26, 5, '#d9d3c3', KX - 2.5, -6, 2.5); box(0.3, 26, 5, '#d9d3c3', KX + 2.5, -6, 2.5); box(5, 26, 0.2, '#cfc9ba', KX, -6, 5.1)
box(1.9, 0.3, 5, '#d9d3c3', KX - 1.55, 6, 2.5); box(1.9, 0.3, 5, '#d9d3c3', KX + 1.55, 6, 2.5); box(1.2, 0.3, 2.6, '#d9d3c3', KX, 6, 3.7)
DOOR = box(1.2, 0.1, 2.3, '#5a3823', KX, 5.95, 1.25, bevel=0.02); box(0.9, 0.05, 0.26, '#c9a544', KX, 5.86, 1.85, metal=0.8, rough=0.3); text('PRINCIPAL', 0.13, '#1a1408', KX, 5.82, 1.85)
cyl(0.05, 0.08, '#c9a544', KX + 0.45, 5.86, 1.15, 12, metal=0.9, rough=0.25).rotation_euler = (R(90), 0, 0)
GAP = box(1.2, 0.12, 0.09, '#ffd98a', KX, 5.95, 0.045, emit=2.2)
for i in range(9):
    for sx in (-1, 1): box(0.5, 1.0, 2.1, ['#3d6fb5', '#c9483b', '#3a9a62'][i % 3], KX + sx * 2.1, -17 + i * 2.3, 1.05, bevel=0.03)
KL = [light('POINT', (KX, y, 4.6), 900, (1, 0.96, 0.85), shadow=(y == 2)) for y in (-14, -6, 2)]; KN = light('POINT', (KX, 0, 4.4), 160, (0.45, 0.6, 1.0))
# ---------- décor 4 : le bureau du directeur (x = 300), étagères de bocaux au fond (y = 4) ----------
OX = 300
box(12, 12, 0.2, '#3a2a22', OX, 0, -0.1); box(12, 0.3, 9, '#2b2530', OX, 4.6, 4.5); box(0.3, 12, 9, '#2b2530', OX - 6, 0, 4.5); box(0.3, 12, 9, '#2b2530', OX + 6, 0, 4.5)
box(3.2, 1.5, 0.12, '#4a2f1f', OX - 2.5, -1.5, 1.0, bevel=0.03); box(3.0, 1.3, 1.0, '#3a2418', OX - 2.5, -1.5, 0.5)
JPOS = []
for iz in range(5):
    box(9.5, 0.7, 0.08, '#5a3a25', OX, 4.1, 0.9 + iz * 0.75)
    for ix in range(13):
        x = OX - 4.2 + ix * 0.7; z = 0.94 + iz * 0.75; JPOS.append((x, 4.05, z))
        cyl(0.2, 0.46, '#bfe9ff', x, 4.05, z + 0.23, 14, alpha=0.12); cyl(0.17, 0.05, '#8a6a3a', x, 4.05, z + 0.48, 12)
        if (ix * 7 + iz * 3) % 4: b = box(0.07, 0.05, 0.16, ['#2f7bff', '#ff7ac0', '#27b36a', '#f2c230', '#ff8a2b'][(ix + iz) % 5], x + (rnd.random() - 0.5) * 0.12, 4.05, z + 0.09); b['wig'] = rnd.random() * 6
WIG = [o for o in bpy.data.objects if 'wig' in o.keys()]
OD = light('POINT', (OX, -1, 3.0), 60, (0.4, 0.55, 1.0)); OJ = light('AREA', (OX, 2.0, 3.0), 500, (0.6, 0.9, 1.0), 6, tgt=(OX, 4.1, 2.5), shadow=False)
OT = light('SPOT', (OX, -2, 8.5), 0, (1, 0.95, 0.85), 80, tgt=(OX, 1.5, 0)); OR = light('POINT', (OX, 2.5, 2.5), 0, (1, 0.1, 0.05), shadow=False)
OB = light('POINT', (OX + 0.8, 3.2, 4.5), 500, (1, 0.9, 0.8), shadow=False)
RUNT = text('RUN', 0.2, '#ff2a1a', OX, 3.6, 2.6, emit=8)
# ---------- caméra, monde ----------
cd = bpy.data.cameras.new('C'); cam = bpy.data.objects.new('C', cd); COL.objects.link(cam); sc.camera = cam; cd.sensor_fit = 'VERTICAL'; cd.clip_start = 0.01; cd.clip_end = 600
wo = bpy.data.worlds.new('W'); sc.world = wo; wo.use_nodes = True; BG = wo.node_tree.nodes['Background']
def world(col, s=1.0): BG.inputs[0].default_value = hexc(col); BG.inputs[1].default_value = s
def camset(p, t, lens=35, roll=0):
    cam.location = p; q = (Vector(t) - Vector(p)).to_track_quat('-Z', 'Y'); e = q.to_euler(); cam.rotation_euler = e; cam.rotation_euler.rotate_axis('Z', R(roll)); cd.lens = lens
def camlerp(p0, t0, p1, t1, u, lens=35, lens1=None):
    camset(tuple(lerp(a, b, u) for a, b in zip(p0, p1)), tuple(lerp(a, b, u) for a, b in zip(t0, t1)), lerp(lens, lens1 if lens1 else lens, u))
LIGHTS = [o for o in bpy.data.objects if o.type == 'LIGHT']
def reset():
    for c in ALL: c.show(False); c.pose()
    for l in LIGHTS: l.data.energy = 0
    for o in (PAPER, PA, PF2, BOARD1, BOARD2, RUNT, PF, PAt, PF2t): o.hide_render = True
    GAP.hide_render = True; DOOR.rotation_euler = (0, 0, 0)
def on(*ls, k=1.0):
    for l in ls: l.data.energy = l['e'] * k
def day(): world('#7fc4ff', 1.0); on(SUN)
# ---------- les plans ----------
def s_school(t, u):      # 0 : « In my school, your grades decide your height. »
    day(); camlerp((3, -34, 1.2), (0, 10, 9), (1.5, -20, 1.6), (0, 14, 8), u, 22, 26)
    sizes = [0.35, 1.0, 2.6, 5.5, 0.6, 8.5]
    for i, c in enumerate(STU):
        x = [-7, -3.2, 6, -12, 2.5, 13][i]; y = [-6, -2, 2, 9, -9, 12][i]; c.put(x + math.sin(t * 0.8 + i) * 0.3, y - t * (0.5 if i % 2 else -0.4), 0, 180 if i % 2 else 0, sizes[i]); c.walk(t + i, 0.8 / max(0.6, sizes[i] ** 0.5)); c.face('smile' if sizes[i] > 2 else 'neutral')
def s_grow(t, u):        # « Get an A, you grow. »
    world('#bcd8ee', 0.6); on(CL1, CL2); BOARD1.hide_render = False; PA.hide_render = PAt.hide_render = False
    k = 1 + 1.6 * ss(0.25, 0.9, u); c = STU[2]; c.put(CX - 3.4, -1.9, 0, 180, k); c.pose(lArm=(-150, 0, 0), rArm=(-150, 0, 0)); c.face('smile')
    camlerp((CX - 2.2, 2.6, 1.5), (CX - 3.4, -1.7, 1.3), (CX - 1.6, 4.4, 1.9), (CX - 3.4, -1.7, 2.5), ss(0.2, 1, u), 30)
def s_shrink(t, u):      # « Get an F, you shrink. »
    world('#bcd8ee', 0.6); on(CL1, CL2); BOARD1.hide_render = False; PF2.hide_render = PF2t.hide_render = False
    k = 1 - 0.68 * ss(0.3, 0.9, u); c = STU[1]; c.put(CX + 3.4, -1.9, 0, 180, k); c.pose(lArm=(-20, 0, -25), rArm=(-20, 0, 25), head=(18, 0, 0)); c.face('shock')
    camlerp((CX + 2.2, 2.6, 1.5), (CX + 3.4, -1.7, 1.2), (CX + 2.9, 0.9, 1.25), (CX + 3.4, -1.8, 0.75), ss(0.2, 1, u), 30)
def s_fail(t, u):        # « I just failed my third test in a row. »
    world('#bcd8ee', 0.6); on(CL1, CL2); BOARD1.hide_render = False; PAPER.hide_render = PF.hide_render = False
    PAPER.location = (CX, -1.05, 1.0 + 0.9 * (1 - ss(0.0, 0.14, u))); HERO.put(CX, -1.9, 0, 180, 1); HERO.pose(lArm=(-55, 0, 18), rArm=(-55, 0, -18), head=(22 * ss(0.1, 0.3, u), 0, 0)); HERO.face('shock' if u > 0.14 else 'neutral')
    for i, c in enumerate((STU[0], STU[4])): c.put(CX + (-3.4, 3.4)[i], -1.9, 0, 180 + (-35, 35)[i], 1.25); c.pose(head=(0, 0, (35, -35)[i])); c.face('smile')
    if u < 0.42: camlerp((CX, -1.3, 3.2), (CX, -1.05, 1.0), (CX, -1.25, 2.0), (CX, -1.05, 1.0), ss(0, 0.4, u), 35)
    else: camlerp((CX + 0.9, 0.6, 1.75), (CX, -1.9, 1.5), (CX + 0.5, 0.1, 1.65), (CX, -1.9, 1.55), ss(0.42, 1, u), 40)
def s_shoe(t, u):        # « Now I'm the size of a shoe. »
    world('#bcd8ee', 0.6); on(CL1, CL2); k = lerp(1.0, 0.16, ss(0.0, 0.45, u))
    HERO.put(CX + 0.1, -4.0, 0, 200, k); HERO.pose(lArm=(0, -40, 0), rArm=(0, 40, 0), head=(-25, 0, 0)); HERO.face('shock')
    STU[0].put(CX + 0.75, -3.8, 0, 160, 1.25); STU[0].pose()
    camlerp((CX - 1.6, -6.4, 1.1), (CX + 0.1, -4.0, 0.9), (CX - 0.25, -4.9, 0.12), (CX + 0.35, -3.9, 0.17), ss(0.05, 0.6, u), 32, 26)
def s_tall(t, u):        # « The straight-A students are as tall as buildings. »
    day(); c = STU[5]; c.put(13, 10, 0, 195, 9.2); c.walk(t, 0.25, 14); c.face('smile'); STU[3].put(-13, 12, 0, 170, 8.6); STU[3].walk(t + 2, 0.25, 14); STU[3].face('smile')
    HERO.put(1.5, -9, 0, 20, 0.16); HERO.pose(head=(-35, 0, 0)); HERO.face('shock')
    camlerp((2.2, -10.5, 0.35), (4, 0, 3.0), (2.4, -10.9, 0.3), (10, 8, 13.5), ss(0.1, 0.9, u), 20)
def s_step(t, u):        # « They step over us like we're ants. »
    day(); c = STU[5]; x = lerp(-9, 9, u); c.put(x, -7.2, 0, -90, 8.0); a = math.sin(u * math.pi * 2.0) * 34; c.pose(lLeg=-a, rLeg=a, lArm=(a, 0, 0), rArm=(-a, 0, 0)); c.face('smile')
    HERO.put(0.2, -7.2, 0, 0, 0.16); HERO.pose(lArm=(-150, 0, 20), rArm=(-150, 0, -20), head=(-30, 0, 0), upper=(8, 0, 0)); HERO.face('strain')
    for i, c2 in enumerate((STU[0], STU[1])): c2.put(-0.6 + i * 1.5, -7.6 - i * 0.5, 0, -40 + i * 80, 0.2); c2.walk(t * 2 + i, 2.2); c2.face('shock')
    camlerp((0.75, -9.0, 0.1), (0.2, -7.2, 0.3), (0.9, -9.4, 0.09), (0.2, -7.0, 1.3), u, 15)
def s_nobody(t, u):      # « But nobody talks about this: »
    world('#c9d2dd', 0.5); on(*KL, k=0.9); HERO.put(KX - 0.2, -8, 0, 0, 0.16); HERO.pose(head=(0, 0, 55 * math.sin(u * 5)), lArm=(-12, 0, 0), rArm=(-12, 0, 0)); HERO.face('neutral')
    for i, c in enumerate(STU[:4]): c.put(KX + (-1.2, 1.3, -0.9, 1.0)[i], -4 + i * 3.2 - t * 0.5, 0, 180, (1.5, 2.2, 1.2, 1.9)[i]); c.walk(t + i * 1.7, 0.7); c.face('neutral')
    camlerp((KX - 0.5, -8.75, 0.3), (KX - 0.2, -8.0, 0.26), (KX - 0.42, -8.5, 0.29), (KX - 0.2, -8.0, 0.265), u, 34)
def s_called(t, u):      # « Every month, the tallest student gets called to the principal's office… and disappears. »
    dark = ss(0.74, 0.8, u); world('#c9d2dd', 0.5 * (1 - 0.8 * dark)); on(*KL, k=0.9 * (1 - 0.93 * dark) * (0.35 if (0.62 < u < 0.74 and int(t * 14) % 2) else 1)); on(KN, k=dark)
    c = STU[5]; y = lerp(-13, 3.0, ss(0.0, 0.6, u)); c.put(KX, y, 0, 180, 2.55); c.walk(t, 0.55, 22); c.pose(lArm=(math.sin(t * 3.6) * 22, 0, 0), rArm=(-math.sin(t * 3.6) * 22, 0, 0), lLeg=-math.sin(t * 3.6) * 22, rLeg=math.sin(t * 3.6) * 22, head=(14, 0, 0), upper=(10, 0, 0)); c.face('neutral')
    DOOR.rotation_euler = (0, 0, R(-80 * ss(0.42, 0.56, u) * (1 - ss(0.66, 0.72, u)))); DOOR.location = (KX - 0.6 + 0.6 * math.cos(DOOR.rotation_euler.z), 5.95 + 0.6 * math.sin(DOOR.rotation_euler.z), 1.25)
    if u > 0.6: c.show(False)
    HERO.put(KX + 1.3, -9.5, 0, 180, 0.16); HERO.pose(head=(-20, 0, 0)); HERO.face('shock' if u > 0.7 else 'neutral')
    if u < 0.45: camlerp((KX + 1.5, -10.4, 0.3), (KX, lerp(-6, 2, u / 0.45), 3.2), (KX + 1.4, -10.0, 0.3), (KX, 2, 3.4), u / 0.45, 22)
    else: camlerp((KX, -7, 1.6), (KX, 6, 1.5), (KX, -1.5, 1.5), (KX, 6, 1.45), ss(0.45, 1, u), 30, 40)
def s_teacher(t, u):     # « The teachers say he graduated early. Nobody asks questions. »
    world('#bcd8ee', 0.6); on(CL1, CL2); BOARD2.hide_render = False
    TEACH.put(CX + 3.2, 4.4, 0, -25, 1.9); TEACH.pose(rArm=(-120, 0, 30 + 8 * math.sin(t * 5)), lArm=(0, 0, 0), head=(0, 0, -15)); TEACH.face('smile')
    for i, c in enumerate(STU[:5]): c.put(CX + (-3.4, 0, 3.4, -3.4, 3.4)[i], (-0.3, -0.3, -0.3, -2.9, -2.9)[i], 0, 180, (1.4, 0.8, 1.9, 0.55, 1.1)[i]); c.pose(head=(-12 if u < 0.55 else 20, 0, 0)); c.face('neutral')
    HERO.put(CX, -2.9, 0, 180, 0.16)
    if u < 0.55: camlerp((CX - 1.2, -5.5, 2.3), (CX + 0.6, 5.8, 2.6), (CX - 0.6, -3.6, 2.5), (CX + 0.6, 5.8, 2.8), u / 0.55, 24)
    else: camlerp((CX - 3.6, 3.9, 2.0), (CX + 0.4, -1.0, 1.0), (CX - 2.4, 4.2, 1.8), (CX + 0.6, -1.0, 0.9), ss(0.55, 1, u), 26)
def s_night(t, u):       # « Last night, I got so small I could slip under the principal's door. So I did. »
    world('#0a1226', 0.35); on(KN); GAP.hide_render = False; k = lerp(0.16, 0.035, ss(0.05, 0.4, u))
    y = lerp(1.5, 5.55, ss(0.3, 0.86, u)); z = 0; pitch = 0
    if u > 0.86: v = ss(0.86, 1, u); y = lerp(5.55, 6.4, v); pitch = 0
    HERO.put(KX, y, z, 0, k, pitch); HERO.walk(t, 2.0 if 0.3 < u < 0.86 else 0, 30) if 0.3 < u else HERO.pose(lArm=(0, -30, 0), rArm=(0, 30, 0), head=(20, 0, 0)); HERO.face('shock' if u < 0.3 else 'strain')
    if u > 0.86: HERO.pose(upper=(-70, 0, 0), head=(60, 0, 0), lArm=(-160, 0, 0), rArm=(-160, 0, 0))
    if u < 0.32: camlerp((KX + 0.5, 0.3, 0.42), (KX, 1.5, 0.2), (KX + 0.22, 1.0, 0.1), (KX, 1.5, 0.04), ss(0, 0.32, u), 30)
    elif u < 0.8: camlerp((KX - 0.1, 0.9, 0.035), (KX, 6, 0.4), (KX - 0.05, 4.6, 0.03), (KX, 6, 0.12), ss(0.32, 0.8, u), 18)
    else: camlerp((KX + 0.22, 5.3, 0.03), (KX, 5.9, 0.03), (KX + 0.16, 5.5, 0.025), (KX, 5.95, 0.03), ss(0.8, 1, u), 24)
def jar_kids(t, hit=0.0, sc=0.055):
    for i, c in enumerate(JAR):
        x, y, z = JPOS[13 * 1 + 4 + i]; c.put(x, y - 0.02, z + 0.01, 20 * math.sin(t * 2 + i * 2), sc); a = -110 - 40 * abs(math.sin(t * 7 + i * 1.3))
        c.pose(lArm=(a, 0, 0), rArm=(-110 - 40 * abs(math.sin(t * 7 + i * 1.3 + 1.2)), 0, 0)); c.face('shock')
    for o in WIG: o.rotation_euler = (0, 0, math.sin(t * 5 + o['wig']) * 0.5); o.location.z += 0  # petites silhouettes qui bougent
HS = 0.1
def office_dark(k=1.0): world('#03040a', 0.2); on(OD, k=k); on(OJ, k=0.45 * k)
HX, HY = OX + 0.9, 3.25      # le héros au pied des étagères
def s_dark(t, u):        # « Inside, it was dark. »
    office_dark(0.6); HERO.put(OX + 0.6, -2.5 + u * 0.6, 0, 0, HS); HERO.walk(t, 1.2, 20); HERO.face('shock')
    camlerp((OX + 0.85, -3.1, 0.2), (OX + 0.4, 4, 1.6), (OX + 0.8, -2.8, 0.22), (OX + 0.2, 4, 2.4), u, 16)
def s_jars(t, u):        # « Hundreds of glass jars on his shelf. And inside every jar… something was moving. »
    office_dark(1.2); jar_kids(t); [c.show(False) for c in JAR] if u < 0.55 else None
    if u < 0.55: camlerp((OX - 3.6, 1.2, 1.6), (OX - 2.5, 4.1, 2.2), (OX + 3.2, 1.6, 3.4), (OX + 2.0, 4.1, 3.0), ss(0, 0.55, u), 24)
    else: x, y, z = JPOS[13 + 6]; camlerp((x - 0.5, y - 1.5, z + 0.35), (x, y, z + 0.2), (x - 0.12, y - 0.62, z + 0.24), (x, y, z + 0.2), ss(0.55, 1, u), 40)
def s_climb(t, u):       # « I climbed closer. It was them. »
    office_dark(1.3); jar_kids(t); x, y, z = JPOS[13 + 6]
    if u < 0.5: HERO.put(x + 0.35, 3.72, lerp(0.2, z, u / 0.5), 0, HS, 0); a = math.sin(t * 12) * 50; HERO.pose(lArm=(-150 + a, 0, 0), rArm=(-150 - a, 0, 0), lLeg=-30 - a * 0.5, rLeg=-30 + a * 0.5); HERO.face('strain'); camlerp((x + 0.9, 2.9, 0.5), (x + 0.35, 3.7, 0.6), (x + 0.7, 3.1, z + 0.1), (x + 0.35, 3.7, z), u / 0.5, 30)
    else: HERO.put(x + 0.33, 3.85, z + 0.005, 35, HS); HERO.pose(head=(-10, 0, 0)); HERO.face('shock'); camlerp((x + 0.42, 3.72, z + 0.165), (x, y, z + 0.13), (x + 0.3, 3.6, z + 0.1), (x, y, z + 0.13), ss(0.5, 1, u), 30)
def s_them(t, u):        # « The missing students. The smartest kids in school — now smaller than my finger. »
    office_dark(1.5); jar_kids(t); x, y, z = JPOS[13 + 6]
    HERO.put(x + 0.33, 3.85, z + 0.005, 35, HS); HERO.pose(rArm=(-95, 0, -30), head=(-8, 0, 0)); HERO.face('shock')
    if u < 0.4: camlerp((x - 1.3, y - 1.7, z + 0.25), (x - 1.0, y, z + 0.1), (x + 1.0, y - 1.7, z + 0.25), (x + 1.2, y, z + 0.1), u / 0.4, 30)
    else: camlerp((x - 0.62, y - 0.95, z + 0.14), (x - 0.7, y, z + 0.07), (x - 0.68, y - 0.6, z + 0.1), (x - 0.7, y, z + 0.06), ss(0.4, 1, u), 50)
def s_hit(t, u):         # « One of them hit the glass. He screamed something. I couldn't hear him. So I read his lips. He said: RUN. »
    red = ss(0.84, 0.88, u); office_dark(1.5); OR.data.energy = 220 * red * (0.6 + 0.4 * math.sin(t * 22)); jar_kids(t)
    i = 2; x, y, z = JPOS[13 + 6]; c = JAR[i]; c.put(x, y - 0.1, z + 0.01, 0, 0.06); h = abs(math.sin(t * 9)); c.pose(lArm=(-95 - 25 * h, 0, 0), rArm=(-95 - 25 * (1 - h), 0, 0), head=(0, 0, 0)); c.face('shock' if int(t * 6) % 2 else 'strain')
    HERO.put(x + 0.33, 3.85, z + 0.005, 35, HS); HERO.face('shock'); HERO.pose(head=(-8, 0, 0))
    if u < 0.3: camlerp((x - 0.25, y - 0.7, z + 0.16), (x, y, z + 0.1), (x - 0.1, y - 0.5, z + 0.14), (x, y, z + 0.1), u / 0.3, 45)
    elif u < 0.62: camlerp((x + 0.36, 3.5, z + 0.17), (x + 0.33, 3.85, z + 0.155), (x + 0.35, 3.62, z + 0.165), (x + 0.33, 3.85, z + 0.155), ss(0.3, 0.62, u), 50)
    else: camlerp((x - 0.02, y - 0.5, z + 0.1), (x, y - 0.1, z + 0.095), (x - 0.01, y - 0.33, z + 0.097), (x, y - 0.1, z + 0.093), ss(0.62, 0.9, u), 60)
def s_under(t, u):       # « That's when I understood. Our principal is the tallest man I've ever seen. »
    world('#1a2a5c', 1.0); on(SUN, k=0.3)
    BOSS.put(0, 6, 0, 180, 9.6); BOSS.pose(lArm=(0, 0, -6), rArm=(0, 0, 6), head=(18, 0, 0)); BOSS.face('neutral')
    for i, c in enumerate(STU[:5]): c.put(-6 + i * 3, -6 - (i % 2) * 2, 0, 0, (0.5, 1.1, 2.0, 0.8, 1.5)[i]); c.pose(head=(-25, 0, 0)); c.face('neutral')
    camlerp((1.5, -22, 0.8), (0, 4, 5), (0.8, -15, 0.8), (0, 5.5, 14.5), ss(0.15, 1, u), 20)
def s_grows(t, u):       # « Because he doesn't teach us. He grows us. »
    world('#bcd8ee', 0.5); on(CL1, CL2, k=0.9); BOARD1.hide_render = False
    BOSS.put(CX + 0.5, 4.3, 0, 180, 2.9); BOSS.pose(lArm=(-40, 0, -18), rArm=(-40, 0, 18), head=(26, 0, 0), upper=(14, 0, 0)); BOSS.face('smile')
    g = ss(0.45, 0.95, u)
    for i, c in enumerate(STU): c.put(CX + (-3.4, 0, 3.4, -3.4, 0, 3.4)[i], (-0.3, -0.3, -0.3, -2.9, -2.9, -2.9)[i], 0, 0, (0.7, 0.9, 0.6, 0.8, 0.7, 0.9)[i] * (1 + 0.9 * g)); c.pose(head=(-28, 0, 0)); c.face('neutral')
    camlerp((CX - 0.5, -5.5, 1.2), (CX + 0.2, 2, 2.2), (CX - 0.2, -5.0, 1.0), (CX + 0.4, 3.5, 4.4), ss(0.1, 1, u), 20)
def s_lights(t, u):      # « Then the lights turned on. And a giant voice said: »
    onk = 1.0 if u > 0.1 else 0.0; world('#1a1620' if onk else '#03040a', 0.5); on(OD, OJ, k=1.0); OT.data.energy = 9000 * onk; OB.data.energy = 500 * onk; jar_kids(t)
    x, y, z = JPOS[13 + 6]; HERO.put(x + 0.33, 3.85, z + 0.005, 35 + 145 * ss(0.3, 0.5, u), HS); HERO.pose(lArm=(0, -35, 0), rArm=(0, 35, 0), head=(-20 * ss(0.4, 0.7, u), 0, 0)); HERO.face('shock')
    BOSS.put(OX + 0.8, 0.6, 0, 180, 2.6); BOSS.pose(head=(30, 0, 0), upper=(12, 0, 0)); BOSS.face('neutral')
    if u < 0.5: camlerp((x + 0.36, 3.5, z + 0.16), (x + 0.33, 3.85, z + 0.155), (x + 0.4, 3.56, z + 0.165), (x + 0.33, 3.85, z + 0.155), u / 0.5, 45)
    else: camlerp((x + 0.36, 4.0, z + 0.165), (OX + 0.8, 0.6, 2.2), (x + 0.36, 4.0, z + 0.2), (OX + 0.8, 0.6, 3.6), ss(0.5, 1, u), 24)
def s_strange(t, u):     # « Strange. I don't remember shrinking you yet. »
    world('#1a1620', 0.5); on(OD, OJ); OT.data.energy = 9000; OB.data.energy = 500; jar_kids(t); x, y, z = JPOS[13 + 6]
    HERO.put(x + 0.33, 3.85, z + 0.005, 180, HS); HERO.pose(lArm=(0, -35, 0), rArm=(0, 35, 0), head=(-30, 0, 0)); HERO.face('shock')
    d = ss(0.0, 1.0, u); BOSS.put(OX + 0.8, lerp(0.6, 2.3, d), 0, 180, 2.6); BOSS.pose(head=(34, 0, 0), upper=(lerp(12, 34, d), 0, 0), rArm=(lerp(0, -105, ss(0.45, 1, u)), 0, 0)); BOSS.face('smile' if u > 0.35 else 'neutral')
    camlerp((x + 0.36, 4.0, z + 0.2), (OX + 0.8, 1.2, 3.9), (x + 0.36, 4.0, z + 0.2), (OX + 0.8, 2.3, 3.5), u, 28, 44)
SHOTS = [(0.0, s_school), (2.86, s_grow), (4.46, s_shrink), (6.3, s_fail), (8.76, s_shoe), (10.58, s_tall), (13.28, s_step), (15.2, s_nobody), (17.08, s_called), (21.95, s_teacher),
         (25.86, s_night), (30.74, s_dark), (32.5, s_jars), (37.9, s_climb), (39.98, s_them), (44.68, s_hit), (50.76, s_under), (55.1, s_grows), (57.9, s_lights), (60.86, s_strange), (63.95, None)]
def setup(n):
    t = n / FPS; i = max(k for k in range(len(SHOTS) - 1) if SHOTS[k][0] <= t); t0, f = SHOTS[i]; t1 = SHOTS[i + 1][0]
    reset(); f(t, (t - t0) / (t1 - t0))
    hl = 0.004 * (cam.location - Vector((0, 0, 0))).length * 0  # (pas de tremblement)
sc.render.engine = 'BLENDER_EEVEE'; ee = sc.eevee; ee.taa_render_samples = int(os.environ.get('TAA', 8)); ee.use_gtao = True; ee.gtao_distance = 1.0; ee.use_soft_shadows = True
ee.shadow_cube_size = '512'; ee.shadow_cascade_size = '2048'; ee.use_bloom = True; ee.bloom_intensity = 0.05; ee.use_ssr = False
sc.render.resolution_x = W; sc.render.resolution_y = H; sc.render.resolution_percentage = 100
sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'Medium High Contrast'; sc.view_settings.exposure = float(os.environ.get('EXPO', -0.3))
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 92
FR = [int(x) for x in os.environ['ONLY'].split(',')] if os.environ.get('ONLY') else range(n0, n1)
os.makedirs(OUT, exist_ok=True)
for n in FR:
    setup(n); sc.frame_set(n + 1); sc.render.filepath = os.path.join(OUT, f'f{n:05d}.jpg'); bpy.ops.render.render(write_still=True)
print('DONE', n0, n1)
