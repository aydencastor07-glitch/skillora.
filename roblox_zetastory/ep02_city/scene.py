# ZetaStory ép. 2 – « In my city, everyone has a number floating above their head » (Blender EEVEE, personnages en blocs).
# Rue (x=0), arrêt de bus (x=0, y=-30), parc (x=100). usage : blender -b -P scene.py -- CHARS_DIR OUT n0 n1 [W H]  (ONLY=…, TAA=8)
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
# ---------- personnages ----------
HERO = Char('char_BK.glb', 'BK', shirt='#e8231c', pants='#1c2a5e')
zt = text('Z', 0.42, '#ffcc11', 0, -0.2, 0.36, rot=(90, 0, 0), ext=0.02); zt.parent = HERO.n['upper']; HERO.objs.append(zt)
MOM = Char('char_W.glb', 'W', shirt='#3fa0c8', pants='#33384a')
FRIEND = Char('char_M2.glb', 'M2', shirt='#27b36a', pants='#3b2c22')
TEACH = Char('char_W.glb', 'W', shirt='#f4f1e8', pants='#3a3f4a', hair='#6b4a2f')
DRIVER = Char('char_E2.glb', 'E2', shirt='#2a4a8a', pants='#22262e')
PASS = [Char('char_E0.glb', 'E0', shirt='#ff8a2b', pants='#30343c'), Char('char_E3.glb', 'E3', shirt='#8e5bd9', pants='#22262e'), Char('char_E1.glb', 'E1', shirt='#f2c230', pants='#2a3b55')]
OLD = [Char(g, p, shirt=s, pants='#4a4a50', hair='#d6d6d0', skin='#e3c9a8') for g, p, s in
       [('char_E1.glb', 'E1', '#6b5a45'), ('char_E0.glb', 'E0', '#55606b'), ('char_E3.glb', 'E3', '#7a4a3a'), ('char_E2.glb', 'E2', '#4f5f45'), ('char_M2.glb', 'M2', '#6a5e70')]]
GIRL = Char('char_W.glb', 'W', shirt='#ff7ac0', pants='#5a4bb0', hair='#e0b050')
GMOM = Char('char_M2.glb', 'M2', shirt='#d9d2c4', pants='#30343c', hair='#3a2618')
ALL = [HERO, MOM, FRIEND, TEACH, DRIVER, GIRL, GMOM] + PASS + OLD
# ---------- nombres au-dessus des têtes (toujours face caméra) ----------
NUMS = {}
def num_obj(c):
    if c not in NUMS:
        cu = bpy.data.curves.new('n', 'FONT'); cu.size = 0.42; cu.align_x = 'CENTER'; cu.align_y = 'CENTER'; cu.extrude = 0.02; cu.font = FONT
        o = bpy.data.objects.new('n', cu); COL.objects.link(o); NUMS[c] = o
    return NUMS[c]
SHOWN = set()
def number(c, val, col='#5ff58a', size=1.0, emit=3.0):
    o = num_obj(c); o.data.body = val if isinstance(val, str) else f'{val:,}'; o.data.materials.clear(); o.data.materials.append(mat(col, emit=emit))
    r = c.n['root']; s = r.scale[0]; o.location = (r.location.x, r.location.y, r.location.z + (2.45 + 0.12 * math.sin(T * 2.5)) * s)
    o.scale = (s * size,) * 3; o.rotation_euler = cam.rotation_euler.copy(); o.hide_render = False; SHOWN.add(c)
# ---------- décor 1 : la rue (route le long de x, trottoirs, immeubles) ----------
box(400, 400, 0.2, '#5f6b5a', 0, 0, -0.1); box(120, 8, 0.03, '#33363d', 0, 0, 0.01); box(120, 4, 0.18, '#b8b3a8', 0, 6, 0.09); box(120, 4, 0.18, '#b8b3a8', 0, -6, 0.09)
for i in range(-14, 15): box(1.6, 0.2, 0.02, '#f2f2ea', i * 4, 0, 0.03)
BCOL = ['#c8553c', '#e0b45a', '#5a8fc8', '#d7d2c6', '#8a6fb5', '#5fae7a', '#c87a5a']
for side in (-1, 1):
    for i in range(-6, 7):
        h = 8 + rnd.random() * 22; w = 7.5; x = i * 8.4; y = side * 13
        box(w, 8, h, BCOL[(i * 3 + side) % len(BCOL)], x, y, h / 2)
        for wy in range(int(h // 3)):
            for wx in (-2.2, 0, 2.2): box(1.3, 0.2, 1.6, '#bfe6ff' if rnd.random() > 0.3 else '#ffe9a8', x + wx, y - side * 4.02, 2.2 + wy * 3, emit=0.4 if rnd.random() > 0.6 else 0.05, rough=0.2)
for x in range(-40, 41, 10): cyl(0.12, 4, '#3a3f46', x, 4.6, 2, 8); box(0.9, 0.3, 0.2, '#3a3f46', x, 4.2, 4.0)
for x in (-25, -9, 13, 31): cyl(0.3, 2.4, '#6b4630', x, -7.2, 1.2, 8); ball(1.6, '#3aa64a', x, -7.2, 3.4)
# bus jaune à l'arrêt (x = -18)
BUS = bpy.data.objects.new('BUS', None); COL.objects.link(BUS)
for o in [box(10, 2.8, 2.9, '#f2c230', 0, 0, 1.75, bevel=0.15), box(9.6, 2.85, 1.0, '#9ad1ff', 0, 0, 2.4, emit=0.15, rough=0.1), box(1.2, 2.9, 2.0, '#2a2f38', 3.6, 0, 1.4)] + \
         [cyl(0.55, 0.4, '#1a1a1e', x, y, 0.55, 16) for x in (-3.4, 3.4) for y in (-1.3, 1.3)]:
    if o.type == 'MESH' and o.dimensions.z < 1.2 and o.location.z < 0.7: o.rotation_euler = (R(90), 0, 0)
    o.parent = BUS
BUS.location = (-18, 2.2, 0)
SUN = light('SUN', (0, 0, 50), 3.0, (1, 0.95, 0.85)); SUN.rotation_euler = (R(50), 0, R(-30)); SUN.data.angle = R(2)
# ---------- décor 2 : le parc (x = 100), allée, bancs avec les vieux ----------
PX = 100
box(60, 60, 0.2, '#58b04a', PX, 0, -0.05); box(4, 60, 0.03, '#d8c9a0', PX, 0, 0.06)
BENCH = []
for i, y in enumerate((-9, -4.5, 0, 4.5, 9)):
    x = PX + (3.2 if i % 2 == 0 else -3.2); yaw = -90 if x > PX else 90
    b = bpy.data.objects.new('B', None); COL.objects.link(b); b.location = (x, y, 0); b.rotation_euler = (0, 0, R(yaw))
    for o in [box(2.2, 0.6, 0.1, '#8a5a35', 0, 0, 0.55), box(2.2, 0.08, 0.6, '#8a5a35', 0, 0.3, 0.95), box(0.1, 0.5, 0.55, '#2e2e33', -1.0, 0, 0.27), box(0.1, 0.5, 0.55, '#2e2e33', 1.0, 0, 0.27)]: o.parent = b
    BENCH.append((x, y, yaw))
for (x, y) in [(PX - 9, -12), (PX + 9, -6), (PX - 10, 3), (PX + 10, 8), (PX - 8, 13), (PX + 8, 16), (PX - 14, -3), (PX + 14, 0)]:
    cyl(0.4, 3, '#6b4630', x, y, 1.5, 8); ball(2.4, '#2f8f3c', x, y, 4.4); ball(1.7, '#3aa64a', x + 0.8, y + 0.5, 5.6)
for i in range(6): cyl(0.1, 3.4, '#2e2e33', PX + (-5.2 if i % 2 else 5.2), -12 + i * 5, 1.7, 8); ball(0.28, '#fff2c0', PX + (-5.2 if i % 2 else 5.2), -12 + i * 5, 3.5, emit=2)
# ---------- caméra, monde ----------
cd = bpy.data.cameras.new('C'); cam = bpy.data.objects.new('C', cd); COL.objects.link(cam); sc.camera = cam; cd.sensor_fit = 'VERTICAL'; cd.clip_start = 0.02; cd.clip_end = 600
wo = bpy.data.worlds.new('W'); sc.world = wo; wo.use_nodes = True; BG = wo.node_tree.nodes['Background']
def world(col, s=1.0): BG.inputs[0].default_value = hexc(col); BG.inputs[1].default_value = s
def camset(p, t, lens=35):
    cam.location = p; cam.rotation_euler = (Vector(t) - Vector(p)).to_track_quat('-Z', 'Y').to_euler(); cd.lens = lens
def camlerp(p0, t0, p1, t1, u, lens=35, lens1=None):
    camset(tuple(lerp(a, b, u) for a, b in zip(p0, p1)), tuple(lerp(a, b, u) for a, b in zip(t0, t1)), lerp(lens, lens1 if lens1 else lens, u))
def reset():
    for c in ALL: c.show(False); c.pose()
    for o in NUMS.values(): o.hide_render = True
    BUS.location = (-18, 2.2, 0)
def day(col='#7fc4ff', k=1.0): world(col, 1.0 * k); SUN.data.energy = 3.0 * k
def morning(): world('#ffc58a', 0.9); SUN.data.energy = 2.4; SUN.data.color = (1, 0.82, 0.6)
T = 0.0
def hero_num(v, flash=False):
    col = '#ff2a1a'; number(HERO, v, col, 1.25, 6 if (not flash or int(T * 8) % 2) else 1.0)
# ---------- les plans (temps : words.json) ----------
def s_city(t, u):        # « In my city, everyone has a number floating above their head. »
    day(); vals = [12000, 9000, 21430, 7310, 16200]
    for i, c in enumerate([MOM, FRIEND] + PASS):
        x = -8 + i * 4.2 - t * 0.9 * (1 if i % 2 else -1); c.put(x, 5.0 if i % 2 else -5.0, 0.18, -90 if i % 2 else 90); c.walk(t + i, 0.9); number(c, vals[i])
    camlerp((-24, -2.5, 8), (0, 0, 1.6), (-13, -3, 2.6), (0, -1, 2.4), ss(0, 1, u), 30)
def s_days(t, u):        # « It shows how many days you have left. »
    day(); c = PASS[1]; c.put(0, -5.0, 0.18, 0); c.pose(head=(0, 0, 10)); c.face('neutral'); number(c, 7310)
    camlerp((0.4, -7.9, 2.6), (0, -5.0, 2.4), (0.2, -7.6, 2.7), (0, -5.0, 2.6), u, 30, 36)
def s_mom(t, u):         # « My mom has twelve thousand. »
    day(); MOM.put(0, -5.0, 0.18, 0); MOM.pose(rArm=(-30, 0, -10)); MOM.face('smile'); number(MOM, '12,000'); HERO.put(1.2, -4.6, 0.18, 30); HERO.pose(head=(-15, 0, 0))
    camlerp((0.8, -7.9, 2.0), (0.4, -5.0, 2.2), (0.6, -7.7, 2.2), (0.3, -5.0, 2.4), u, 26)
def s_friend(t, u):      # « My best friend has nine thousand. »
    day(); FRIEND.put(-30, -5.0, 0.18, 20); FRIEND.pose(rArm=(-150, 0, 20 + 15 * math.sin(t * 9))); FRIEND.face('smile'); number(FRIEND, '9,000')
    camlerp((-31.2, -7.9, 1.8), (-30, -5.0, 2.1), (-30.6, -7.7, 2.0), (-30, -5.0, 2.3), u, 26)
def s_three(t, u):       # « I have three. »
    day(); HERO.put(0, -5.0, 0.18, 0); HERO.pose(head=(-25 * ss(0.2, 0.7, u), 0, 0)); HERO.face('shock' if u > 0.4 else 'neutral'); hero_num(3)
    camlerp((0, -7.9, 1.8), (0, -5.0, 1.7), (0, -7.4, 2.2), (0, -5.0, 2.5), ss(0, 1, u), 28, 32)
def s_stare(t, u):       # « People stare at me on the street. »
    day(); HERO.put(-6 + u * 4, -5.0, 0.18, 90); HERO.walk(t, 0.9); HERO.face('neutral'); hero_num(3)
    for i, c in enumerate(PASS + [FRIEND]):
        x = -4 + i * 3.0; c.put(x, -6.4 if i % 2 else 4.6, 0.18, 180 if i % 2 else 0); c.pose(head=(0, 0, 60 * (1 if x > HERO.n['root'].location.x else -1) * (-1 if i % 2 else 1))); c.face('shock'); number(c, [21430, 7310, 16200, 9000][i])
    camlerp((-14, -2, 4.5), (-3, -4, 1.4), (-10, -1.5, 3.2), (-2, -4.2, 1.4), u, 26)
def s_bus(t, u):         # « The bus driver lets me ride for free. »
    day(); BUS.location = (-18 + 6 * (1 - ss(0, 0.35, u)), 2.2, 0); DRIVER.put(-14.2, 1.6, 0.6, 0); DRIVER.pose(rArm=(-120, 0, 30 + 12 * math.sin(t * 8))); DRIVER.face('smile'); number(DRIVER, 15600)
    HERO.put(-13.6, -1.2 + 1.0 * ss(0.5, 1, u), 0.0, 180); HERO.walk(t, 0.8) if u > 0.5 else HERO.pose(); HERO.face('neutral'); hero_num(3)
    camlerp((-9, -6.5, 1.6), (-14, 1.5, 1.8), (-10.5, -5.5, 1.8), (-14, 1.6, 2.0), u, 28)
def s_teacher(t, u):     # « My teacher hugged me today and started crying. »
    day(); HERO.put(30, -5.0, 0.18, 180); HERO.pose(lArm=(-40, 0, 20), rArm=(-40, 0, -20)); HERO.face('neutral'); hero_num(3)
    TEACH.put(30, -4.4, 0.18, 0, 1.25); TEACH.pose(lArm=(-80, 0, 35), rArm=(-80, 0, -35), head=(-8, 0, 0), upper=(4, 0, 0)); TEACH.face('strain')
    camlerp((28.6, -7.8, 2.9), (30, -4.4, 2.5), (28.9, -7.6, 3.0), (30, -4.4, 2.55), u, 30)
def s_morning(t, u):     # « But this morning, something strange happened. »
    morning(); HERO.put(PX, -16 + u * 3, 0.06, 180); HERO.walk(t, 0.8); HERO.face('neutral'); hero_num(3)
    for i, c in enumerate(OLD): x, y, yaw = BENCH[i]; c.put(x + (0.25 if yaw > 0 else -0.25) * 0, y, 0, yaw); c.sit(); c.face('neutral'); number(c, [41200, 55800, 38900, 78000, 62300][i], '#b7f5c8')
    camlerp((PX + 10, -24, 9), (PX, 0, 1), (PX + 6, -22, 4), (PX, 0, 1.5), u, 26)
OM = 3   # le vieux à côté de qui le héros passe (banc 4, y = 9 ?) → on prend le banc d'indice 1 (y = -4.5, à gauche)
def old_bench(i, smile=False, look=None):
    x, y, yaw = BENCH[i]; c = OLD[i]; c.put(x, y, 0, yaw); c.sit(); c.face('smile' if smile else 'neutral')
    if look is not None: c.n['head'].rotation_euler = (0, 0, R(look))
    return c
def s_past(t, u):        # « I walked past an old man in the park… and my number went up. Four. »
    morning(); c = old_bench(1); number(c, 78000 - int(u * 40), '#b7f5c8')
    for i in (0, 2, 3, 4): old_bench(i)
    HERO.put(PX - 1.4, -9 + u * 4.0, 0.06, 180); HERO.walk(t, 0.8); HERO.face('shock' if u > 0.85 else 'neutral'); hero_num(4 if T >= 23.33 else 3)
    camlerp((PX + 1.5, -12, 1.6), (PX - 1.6, -5, 1.6), (PX + 1.0, -9, 1.6), (PX - 2.5, -4.5, 1.6), u, 26)
def s_closer(t, u):      # « I stepped closer. Five. Six. And his number went down. »
    morning(); c = old_bench(1, look=-30); v = 5 if T < 25.9 else 6; v = 4 if T < 25.06 else v
    number(c, 78000 - (v - 3) * 1000 - int(u * 300), '#b7f5c8')
    HERO.put(PX - 1.4 - 0.9 * ss(0, 0.3, u), -4.0, 0.06, -90); HERO.walk(t, 0.6) if u < 0.3 else HERO.pose(); HERO.face('shock'); hero_num(v)
    if u < 0.62: camlerp((PX + 0.5, -6.5, 1.3), (PX - 2.6, -4.2, 2.4), (PX + 0.2, -6.0, 1.2), (PX - 2.6, -4.2, 2.6), u / 0.62, 26)
    else: camlerp((PX - 0.6, -6.2, 1.9), (PX - 3.2, -4.5, 2.3), (PX - 0.8, -6.0, 2.0), (PX - 3.2, -4.5, 2.4), ss(0.62, 1, u), 26)
def s_smile(t, u):       # « He looked at me and smiled. » + « Take as many as you need… That's how I got mine. »
    morning(); c = old_bench(1, smile=u > 0.12, look=-20); number(c, 77996 - int(u * 3), '#b7f5c8'); HERO.put(PX - 1.9, -3.4, 0.06, -60); HERO.face('shock'); hero_num(6)
    camlerp((PX - 1.5, -5.4, 1.35), (PX - 3.2, -4.5, 1.2), (PX - 1.6, -4.8, 1.3), (PX - 3.2, -4.5, 1.2), u, 36)
def s_above(t, u):       # « I looked above his head. Seventy-eight thousand days. More than two hundred years. »
    morning(); c = old_bench(1, smile=True, look=-20); number(c, '78,000', '#ffd84a', 1.3, 6); HERO.put(PX - 1.9, -3.4, 0.06, -60); HERO.pose(head=(-25, 0, 0)); HERO.face('shock'); hero_num(6)
    camlerp((PX - 0.2, -6.0, 0.8), (PX - 3.2, -4.5, 1.3), (PX - 0.2, -6.4, 1.2), (PX - 3.2, -4.5, 2.6), ss(0, 0.7, u), 22, 26)
def s_all(t, u):         # « Then I noticed something. Every old man on the benches had the same smile. And they were all looking at me. »
    morning(); HERO.put(PX - 1.9, -3.4, 0.06, -60); HERO.face('shock'); hero_num(6)
    for i in range(5):
        c = old_bench(i, smile=u > 0.25); x, y, yaw = BENCH[i]
        c.n['head'].rotation_euler = (0, 0, R(55 * (1 if (x > PX) == (y > -4) else -1) * ss(0.45, 0.8, u))); number(c, [41200, 77990, 38900, 66000, 62300][i], '#b7f5c8')
    camlerp((PX, -11, 1.6), (PX, 4, 1.1), (PX, -6.0, 1.5), (PX, 8, 1.1), u, 28)
def s_stand(t, u):       # « One of them stood up. Then another. My number started dropping. »
    morning(); HERO.put(PX - 2.3, -4.0, 0.06, 90 + 20 * math.sin(t * 2)); HERO.pose(lArm=(0, -30, 0), rArm=(0, 30, 0)); HERO.face('shock'); hero_num(6 if u < 0.6 else 5 if u < 0.85 else 4)
    for i in range(5):
        c = old_bench(i, smile=True); x, y, yaw = BENCH[i]; up = ss(0.05 + i * 0.12, 0.25 + i * 0.12, u)
        if up > 0: c.pose(); tx, ty = lerp(x, PX - 2.3 + (1.6 if i % 2 == 0 else -0.9), up * 0.45), lerp(y, -4.0 + (i - 1) * 0.9, up * 0.45); c.put(tx, ty, 0, math.degrees(math.atan2(PX - 2.3 - tx, -(-4.0 - ty)))); c.walk(t + i, 0.5, 18)
        number(c, [41200, 77990, 38900, 66000, 62300][i] + int(up * 900), '#b7f5c8')
    camlerp((PX - 2.6, -6.9, 0.6), (PX - 2.3, -2, 1.8), (PX - 2.5, -7.4, 0.5), (PX - 2.3, -1, 2.0), u, 20)
def s_drop(t, u):        # « Two. One. »
    morning(); HERO.put(PX - 2.3, -4.0, 0.06, 0); HERO.pose(lArm=(-40, 0, 20), rArm=(-40, 0, -20), head=(-20, 0, 0)); HERO.face('strain'); hero_num(2 if T < 48.8 else 1, flash=True)
    for i in range(4): c = OLD[i]; a = R(i * 60); c.put(PX - 2.3 + 1.6 * math.cos(a), -4.0 + 1.6 * math.sin(a), 0, math.degrees(math.atan2(-math.cos(a), math.sin(a)))); c.pose(lArm=(-70, 0, 0), rArm=(-70, 0, 0)); c.face('smile')
    camlerp((PX - 2.3, -7.6, 2.4), (PX - 2.3, -4.0, 2.2), (PX - 2.3, -7.0, 2.5), (PX - 2.3, -4.0, 2.3), u, 30)
def s_girl(t, u):        # « And somewhere behind me, a little girl screamed: "Mommy… why is his number going UP?" »
    morning(); GIRL.put(PX + 2.2, -12, 0.06, 165, 0.62); GIRL.pose(rArm=(-95, 0, 25), head=(-10, 0, 0)); GIRL.face('shock'); GMOM.put(PX + 3.0, -12.4, 0.06, 170); GMOM.face('shock')
    HERO.put(PX - 2.3, -4.0, 0.06, 0); HERO.face('shock')
    v = 1 if u < 0.45 else int(1 + (u - 0.45) ** 2 * 900000); hero_num(f'{v:,}' if u >= 0.45 else 1, flash=u < 0.45)
    for i in range(4): c = OLD[i]; a = R(i * 60); c.put(PX - 2.3 + 1.6 * math.cos(a), -4.0 + 1.6 * math.sin(a), 0, math.degrees(math.atan2(-math.cos(a), math.sin(a)))); c.face('shock' if u > 0.6 else 'smile'); c.pose(head=(-20, 0, 0)); number(c, max(1, int(78000 * (1 - ss(0.5, 1, u)))), '#b7f5c8', 0.55)
    if u < 0.5: camlerp((PX + 1.9, -10.2, 1.0), (PX + 2.5, -12, 0.9), (PX + 2.0, -10.6, 1.0), (PX + 2.5, -12, 0.9), u / 0.5, 30)
    else: camlerp((PX - 2.3, -9.0, 2.4), (PX - 2.3, -4.0, 2.4), (PX - 2.3, -8.0, 2.6), (PX - 2.3, -4.0, 2.7), ss(0.5, 1, u), 30)
SHOTS = [(0.0, s_city), (3.5, s_days), (5.4, s_mom), (7.55, s_friend), (9.65, s_three), (10.85, s_stare), (12.58, s_bus), (14.62, s_teacher), (17.3, s_morning),
         (19.62, s_past), (23.85, s_closer), (28.08, s_smile), (33.2, s_above), (38.48, s_all), (44.48, s_stand), (48.15, s_drop), (49.35, s_girl), (54.62, None)]
def setup(n):
    global T
    T = t = n / FPS; i = max(k for k in range(len(SHOTS) - 1) if SHOTS[k][0] <= t); t0, f = SHOTS[i]; t1 = SHOTS[i + 1][0]
    reset(); SUN.data.color = (1, 0.95, 0.85); f(t, (t - t0) / (t1 - t0))
    for o in NUMS.values(): o.rotation_euler = cam.rotation_euler.copy()   # les nombres face à la caméra du plan
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
