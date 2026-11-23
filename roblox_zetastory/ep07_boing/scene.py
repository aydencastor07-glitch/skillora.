# ZetaStory ép. 7 – « BOING » (Blender EEVEE, personnages en blocs style Roblox, mains sans doigts). Inspiré de la recette « HUSS » :
# 1 lieu = 1 blague, chaque plan finit sur BOING!, caméra qui bouge tout le temps. Temps calés sur words.json (voix finale 31,45 s).
# usage : blender -b -P scene.py -- CHARS_DIR OUT n0 n1 [W H]     (ONLY=12,340 : seulement ces images ; TAA=8)
import bpy, sys, os, math, random, json
from mathutils import Vector
argv = sys.argv[sys.argv.index('--') + 1:]
CH, OUT, n0, n1 = argv[0], argv[1], int(argv[2]), int(argv[3])
W = int(argv[4]) if len(argv) > 4 else 720; H = int(argv[5]) if len(argv) > 5 else 1280
FPS = 30; rnd = random.Random(4); HERE = os.path.dirname(os.path.abspath(__file__))
ENV = json.load(open(os.path.join(HERE, 'env.json')))
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
    if alpha < 1: b.inputs['Alpha'].default_value = alpha; m.blend_method = 'BLEND'; m.shadow_method = 'NONE'
    MATS[k] = m; return m
def emat(col, s):     # matériau émissif réglable image par image
    m = bpy.data.materials.new('e'); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = hexc(col); b.inputs['Emission Color'].default_value = hexc(col); b.inputs['Emission Strength'].default_value = s; b.inputs['Roughness'].default_value = 0.3
    return m, b.inputs['Emission Strength']
def box(w, d, h, col, x, y, z, parent=None, bevel=0.0, **kw):
    bpy.ops.mesh.primitive_cube_add(size=1); o = bpy.context.object; o.scale = (w, d, h); o.location = (x, y, z); o.data.materials.append(kw.pop('m') if 'm' in kw else mat(col, **kw))
    if bevel: md = o.modifiers.new('b', 'BEVEL'); md.width = bevel; md.segments = 3
    if parent: o.parent = parent
    return o
def cyl(r, h, col, x, y, z, seg=24, r2=None, m=None, **kw):
    if r2 is None: bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, vertices=seg)
    else: bpy.ops.mesh.primitive_cone_add(radius1=r, radius2=r2, depth=h, vertices=seg)
    o = bpy.context.object; o.location = (x, y, z); o.data.materials.append(m or mat(col, **kw)); bpy.ops.object.shade_smooth(); return o
def ball(r, col, x, y, z, **kw):
    bpy.ops.mesh.primitive_ico_sphere_add(radius=r, subdivisions=2); o = bpy.context.object; o.location = (x, y, z); o.data.materials.append(mat(col, **kw)); return o
FONT = bpy.data.fonts.load('/home/user/skillora./temu/fonts/ArchivoBlack-Regular.ttf')
def text(s, size, col, x, y, z, rot=(90, 0, 0), emit=0.0, ext=0.01, m=None):
    c = bpy.data.curves.new('t', 'FONT'); c.body = s; c.size = size; c.align_x = 'CENTER'; c.align_y = 'CENTER'; c.extrude = ext; c.font = FONT
    o = bpy.data.objects.new('t', c); COL.objects.link(o); o.location = (x, y, z); o.rotation_euler = tuple(R(v) for v in rot); c.materials.append(m or mat(col, emit=emit)); return o
def light(kind, loc, energy, col=(1, 1, 1), size=1.0, tgt=None, shadow=True):
    l = bpy.data.lights.new('L', kind); l.energy = energy; l.color = col; l.use_shadow = shadow
    if kind == 'AREA': l.size = size
    if kind == 'SPOT': l.spot_size = R(size); l.spot_blend = 0.5
    o = bpy.data.objects.new('L', l); COL.objects.link(o); o.location = loc
    if tgt is not None: o.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o
# ---------- personnages : visages vivants ----------
FACES = {}
def face_img(k):
    if k not in FACES:
        im = bpy.data.images.load(os.path.join(CH, f'face_BK_{k}.png')); w, h = im.size; px = list(im.pixels); rows = [px[r * w * 4:(r + 1) * w * 4] for r in range(h)]
        im.pixels = [v for r in reversed(rows) for v in r]; FACES[k] = im
    return FACES[k]
class Char:
    def __init__(s, glb, pre, shirt=None, pants=None, hair=None, skin=None, blink=0.0):
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
        s.bph = blink; s.expr('n', 'c')
    def expr(s, eyes='n', mouth='c', talk=False): s.ey, s.mo, s.talk = eyes, mouth, talk
    def show(s, v=True):
        for o in s.objs: o.hide_render = not v
        s.vis = v
    def put(s, x, y, z=0, yaw=0, scale=1, pitch=0, roll=0):
        r = s.n['root']; r.location = (x, y, z); r.rotation_euler = (R(pitch), R(roll), R(yaw)); r.scale = (scale,) * 3; s.show(True)
    def pose(s, lArm=(0, 0, 0), rArm=(0, 0, 0), lLeg=0, rLeg=0, head=(0, 0, 0), upper=(0, 0, 0), hipz=0):
        s.n['lArm'].rotation_euler = tuple(R(v) for v in lArm); s.n['rArm'].rotation_euler = tuple(R(v) for v in rArm)
        s.n['lLeg'].rotation_euler = (R(lLeg), 0, 0); s.n['rLeg'].rotation_euler = (R(rLeg), 0, 0)
        s.n['head'].rotation_euler = tuple(R(v) for v in head); s.n['upper'].rotation_euler = tuple(R(v) for v in upper)
        s.n['hip'].location = s.base['hip'] + Vector((0, 0, hipz))
    def walk(s, t, sp=1.0, amp=32, head=(0, 0, 0)):
        a = math.sin(t * 6.5 * sp) * amp; s.pose(lArm=(a, 0, 0), rArm=(-a, 0, 0), lLeg=-a, rLeg=a, head=head, hipz=0.03 * abs(math.cos(t * 6.5 * sp)))
    def sit(s, **kw): s.pose(lLeg=-88, rLeg=-88, lArm=(-35, 0, 0), rArm=(-35, 0, 0), hipz=-0.28, **kw)
    def life(s, t, n):
        """après la pose : respiration, petits mouvements de tête, clignement, bouche synchronisée sur la voix."""
        if not s.vis: return
        up = s.n['upper'].rotation_euler; up.x += R(1.6 * math.sin(t * 2.3 + s.bph))
        hd = s.n['head'].rotation_euler; hd.x += R(2.0 * math.sin(t * 1.3 + s.bph * 2)); hd.z += R(2.5 * math.sin(t * 0.9 + s.bph))
        eyes = 'b' if ((t + s.bph) % 3.4) < 0.11 else s.ey; mouth = s.mo
        if s.talk:
            e = ENV[min(n, len(ENV) - 1)]
            if e < 0.12: mouth = s.mo if s.mo in ('sm', 'f') else 'c'
            elif s.mo in ('sm', 'so'): mouth = 'so'
            else: mouth = 'm' if e < 0.45 else 'o'
            hd.x += R(5 * e * math.sin(t * 9)); hd.z += R(3 * e * math.sin(t * 5.3))       # la tête accompagne la parole
        if s.tex: s.tex.image = face_img(f'{eyes}_{mouth}')
# ---------- style Roblox : mains en bloc (pas de doigts) + nez qui peut devenir rouge ----------
def roblox(c):
    for o in list(c.objs):
        p = o.parent
        if o.type == 'MESH' and p is not None and p.name.split('.')[0] == 'hand':
            if abs(o.location.x) < 0.01 and abs(o.location.z + 0.09) < 0.01: o.scale = (1.3, 1.3, 1.45)     # la paume devient un bloc
            else: c.objs.remove(o); bpy.data.objects.remove(o, do_unlink=True)                              # doigts et pouce retirés
    skin = None
    for o in c.objs:
        if o.type == 'MESH' and o.parent == c.n['head'] and o.material_slots and o.material_slots[0].material and 'Material_1' in o.material_slots[0].material.name:
            skin = o.material_slots[0].material; break
    m = skin.copy() if skin else mat('#f2c79a').copy()
    b = [x for x in m.node_tree.nodes if x.type == 'BSDF_PRINCIPLED'][0]
    c.nose_base = tuple(b.inputs['Base Color'].default_value); c.nose_b = b
    bpy.ops.mesh.primitive_cube_add(size=1); n = bpy.context.object; n.scale = (0.07, 0.05, 0.06); n.location = (0, -0.235, 0.165)
    md = n.modifiers.new('b', 'BEVEL'); md.width = 0.012; md.segments = 3
    n.data.materials.append(m); n.parent = c.n['head']; c.objs.append(n); c.nose = n
    c.red = 0.0
def nez(c, k):      # 0 = normal, 1 = rouge vif
    b = c.nose_b; r = (1.0, 0.02, 0.02, 1)
    b.inputs['Base Color'].default_value = tuple(lerp(a, r[i], k) for i, a in enumerate(c.nose_base))
    b.inputs['Emission Color'].default_value = (1.0, 0.02, 0.02, 1); b.inputs['Emission Strength'].default_value = 1.6 * k
def wmat(col='#ffcf7a'):
    m_, e_ = emat(col, 0.0); m_.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = hexc('#1d2026'); WINS.append(e_); return m_
def house(x, y, w, d, col, roof, yaw=0, door=True):
    g = bpy.data.objects.new('h', None); COL.objects.link(g); g.location = (x, y, 0); g.rotation_euler = (0, 0, R(yaw))
    for o in (box(w, d, 3.2, col, 0, 0, 1.6), box(w + 0.6, d + 0.6, 0.5, roof, 0, 0, 3.45), box(w * 0.7, d * 0.7, 1.0, roof, 0, 0, 4.1)):
        o.parent = g
    if door: box(1.0, 0.1, 2.0, '#4a2f20', 0, -d / 2 - 0.06, 1.0).parent = g
    for k in (-1, 1): box(1.0, 0.1, 0.9, '', k * w * 0.3, -d / 2 - 0.06, 2.0, m=wmat()).parent = g
    return g
cd = bpy.data.cameras.new('C'); cam = bpy.data.objects.new('C', cd); COL.objects.link(cam); sc.camera = cam; cd.sensor_fit = 'VERTICAL'; cd.clip_start = 0.03; cd.clip_end = 800
wo = bpy.data.worlds.new('W'); sc.world = wo; wo.use_nodes = True; BG = wo.node_tree.nodes['Background']; BG.inputs[0].default_value = hexc('#8fcfff'); BG.inputs[1].default_value = 1.0
def cr(p0, p1, p2, p3, u):
    return tuple(0.5 * (2 * b + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u + (-a + 3 * b - 3 * c + d) * u ** 3) for a, b, c, d in zip(p0, p1, p2, p3))
def path(keys, t, shake=0.012):
    """keys = [(temps, position, cible, focale)] ; spline Catmull-Rom (position + cible + focale) + léger tremblé « caméra à la main »."""
    if t <= keys[0][0]: i, u = 0, 0.0
    elif t >= keys[-1][0]: i, u = len(keys) - 2, 1.0
    else:
        i = max(k for k in range(len(keys) - 1) if keys[k][0] <= t); u = (t - keys[i][0]) / (keys[i + 1][0] - keys[i][0])
    g = lambda j: keys[max(0, min(len(keys) - 1, j))]
    P = cr(g(i - 1)[1], g(i)[1], g(i + 1)[1], g(i + 2)[1], u); T = cr(g(i - 1)[2], g(i)[2], g(i + 1)[2], g(i + 2)[2], u); L = lerp(g(i)[3], g(i + 1)[3], u * u * (3 - 2 * u))
    T = (T[0] + shake * math.sin(t * 1.7) + shake * 0.6 * math.sin(t * 4.1 + 1), T[1], T[2] + shake * math.sin(t * 2.3 + 2) + shake * 0.5 * math.sin(t * 5.2))
    cam.location = P; cam.rotation_euler = (Vector(T) - Vector(P)).to_track_quat('-Z', 'Y').to_euler(); cd.lens = L
def billboard(o):
    d = cam.location - o.location; o.rotation_euler = (R(90), 0, math.atan2(d.x, -d.y))
def pop(o, t, t0, s=1.0):
    k = ss(t0, t0 + 0.18, t); o.hide_render = k <= 0; o.scale = (s * k * (1 + 0.25 * math.sin(k * math.pi)),) * 3
def walk_to(c, t, t0, t1, p0, p1, sp=1.2, head=(0, 0, 0)):
    """marche de p0 à p1 entre t0 et t1, tournée dans le sens de la marche (yaw 0 = regarde vers -y)."""
    u = ss(t0, t1, t) if False else max(0.0, min(1.0, (t - t0) / (t1 - t0))); x, y = lerp(p0[0], p1[0], u), lerp(p0[1], p1[1], u)
    yaw = math.degrees(math.atan2(p1[0] - p0[0], -(p1[1] - p0[1]))); c.put(x, y, 0, yaw)
    if 0 < u < 1: c.walk(t, sp, head=head)
    else: c.pose(head=head)
    return u
def yawto(ax, ay, bx, by): return math.degrees(math.atan2(bx - ax, -(by - ay)))
def say(c, t, t0, t1, eyes='n', mouth='sm'):
    if t0 <= t < t1: c.expr(eyes, mouth, talk=True)
def sky(col, s): BG.inputs[0].default_value = hexc(col); BG.inputs[1].default_value = s
# ======================================================================= ÉPISODE 7 : BOING
def night(v):
    for e in WINS: e.default_value = 2.8 * v
    for L in LAMPS: L.data.energy = 240 * v
def fill(e):
    FILL.location = cam.location; FILL.rotation_euler = cam.rotation_euler; FILL.data.energy = e
def day(s=3.4):
    sky('#8fcfff', 1.0); SUN.data.energy = s; SUN.data.color = (1, 0.96, 0.9); SUN.rotation_euler = (R(-50), 0, R(25)); night(0)
def dark():
    sky('#16224a', 0.55); SUN.data.energy = 0.55; SUN.data.color = (0.55, 0.65, 1); SUN.rotation_euler = (R(-35), 0, R(-30)); night(1)
SUN = light('SUN', (0, 0, 50), 3.4, (1, 0.96, 0.9)); SUN.data.angle = R(4)
FILL = light('AREA', (0, 0, 20), 0, (1, 0.95, 0.9), 3.0, shadow=False)
GROUND = box(2600, 600, 0.2, '#6fa04a', 500, 0, -0.1)
COLS = ['#f3d9b8', '#c9e3f3', '#f2b8b0', '#c4e3b8', '#f7e3a4', '#d8c8f0']; ROOFS = ['#b8402f', '#2f4a8a', '#7a4a2f', '#2f7a4a']
WINS = []; LAMPS = []
# ---------- personnages ----------
HERO = Char('char_BK.glb', 'BK', shirt='#3a3f4a', pants='#1c2230', blink=0.3)            # sans le Z
BAKER = Char('char_E0.glb', 'E0', shirt='#f4f4f4', pants='#d9d9d9', blink=0.9)
TEACH = Char('char_W.glb', 'W', shirt='#8e5bd9', pants='#33384a', hair='#3a2618', blink=1.7)
BRIDE = Char('char_W.glb', 'W', shirt='#ffffff', pants='#ffffff', hair='#e0b050', blink=2.3)
GROOM = Char('char_M2.glb', 'M2', shirt='#1d1f24', pants='#1d1f24', blink=0.5)
PRIEST = Char('char_E1.glb', 'E1', shirt='#141416', pants='#141416', blink=1.1)
MAYOR = Char('char_E2.glb', 'E2', shirt='#1f2a44', pants='#1c2230', hair='#ececec', skin='#d8b894', blink=2.7)
CROWD = [Char(g, p, shirt=sh, pants=pa, hair=hr, blink=k * 0.37) for k, (g, p, sh, pa, hr) in enumerate((
    ('char_W.glb', 'W', '#ff7ac0', '#5a4bb0', '#e0b050'), ('char_E0.glb', 'E0', '#27b36a', '#30343c', None), ('char_M2.glb', 'M2', '#e8231c', '#2a3b55', None),
    ('char_E1.glb', 'E1', '#3fa0c8', '#22262e', None), ('char_W.glb', 'W', '#f2c230', '#33384a', '#3a2618'), ('char_C1.glb', 'C1', '#ff8a2b', '#2a3b55', None),
    ('char_C2.glb', 'C2', '#9b5de5', '#30343c', None), ('char_E3.glb', 'E3', '#2f7bff', '#22262e', None)))]
ALL = [HERO, BAKER, TEACH, BRIDE, GROOM, PRIEST, MAYOR] + CROWD
for c in ALL: roblox(c)
SCALE = {id(HERO): 0.85, id(CROWD[5]): 0.68, id(CROWD[6]): 0.7}
def acc(c, o): o.parent = c.n['head']; c.objs.append(o); return o
HZ = float(os.environ.get('HZ', 0.43))     # haut de la tête (repère de la tête)
def hat_chef(c):
    acc(c, cyl(0.16, 0.16, '#ffffff', 0, 0, HZ + 0.06, 20)); b = acc(c, ball(0.2, '#ffffff', 0, 0, HZ + 0.22)); b.scale = (1.15, 1.15, 0.8)
def hat_top(c):
    acc(c, cyl(0.25, 0.03, '#111114', 0, 0, HZ + 0.01, 24)); acc(c, cyl(0.15, 0.32, '#111114', 0, 0, HZ + 0.17, 24)); acc(c, cyl(0.155, 0.06, '#b8231c', 0, 0, HZ + 0.06, 24))
hat_chef(BAKER); hat_top(MAYOR)
SASH = box(0.06, 0.02, 0.62, '#c0281f', 0, -0.13, 0); SASH.parent = MAYOR.n['upper']; SASH.location = (0.02, -0.135, 0.3); SASH.rotation_euler = (0, R(35), 0); MAYOR.objs.append(SASH)
VEIL = box(0.42, 0.02, 0.7, '#ffffff', 0, 0, 0, alpha=0.75); VEIL.rotation_mode = 'XYZ'; BRIDE.objs.append(VEIL)
CROWN = acc(BRIDE, cyl(0.17, 0.05, '#f6e7a8', 0, 0, HZ + 0.01, 20, emit=0.3))
# ---------- chiens en blocs ----------
class Dog:
    def __init__(s, col, ear, sc=1.0):
        s.root = bpy.data.objects.new('d', None); COL.objects.link(s.root); s.root.rotation_mode = 'XYZ'; s.parts = []
        def emp(par, loc):
            e = bpy.data.objects.new('p', None); COL.objects.link(e); e.parent = par; e.location = loc; e.rotation_mode = 'XYZ'; return e
        def bx(par, w, d, h, loc, cc=col, **kw):
            o = box(w, d, h, cc, *loc, bevel=0.03, **kw); o.parent = par; s.parts.append(o); return o
        s.body = emp(s.root, (0, 0, 0.5)); bx(s.body, 0.42, 0.8, 0.4, (0, 0, 0))
        s.head = emp(s.body, (0, -0.42, 0.26)); bx(s.head, 0.38, 0.36, 0.34, (0, 0, 0)); bx(s.head, 0.22, 0.18, 0.16, (0, -0.24, -0.06))
        bx(s.head, 0.08, 0.05, 0.06, (0, -0.34, -0.02), '#1a1a1a'); s.mouth = bx(s.head, 0.16, 0.02, 0.05, (0, -0.335, -0.12), '#4a1416')
        for x in (-0.1, 0.1): bx(s.head, 0.06, 0.02, 0.06, (x, -0.185, 0.06), '#141414')
        for x in (-0.17, 0.17): bx(s.head, 0.08, 0.1, 0.22, (x, 0.02, 0.2), ear)
        s.legs = [emp(s.body, (x, y, -0.18)) for x, y in ((-0.14, -0.3), (0.14, -0.3), (-0.14, 0.3), (0.14, 0.3))]
        for L in s.legs: bx(L, 0.12, 0.12, 0.34, (0, 0, -0.17))
        s.tail = emp(s.body, (0, 0.4, 0.12)); bx(s.tail, 0.07, 0.07, 0.3, (0, 0.05, 0.13))
        s.m0 = tuple(s.mouth.scale); s.sc = sc; s.show(False)
    def show(s, v=True):
        for o in s.parts: o.hide_render = not v
    def put(s, x, y, z=0, yaw=0, t=0, jump=0.0):
        s.root.location = (x, y, z); s.root.rotation_euler = (0, 0, R(yaw)); s.root.scale = (s.sc,) * 3; s.show(True)
        s.tail.rotation_euler = (R(-30), R(35 * math.sin(t * 14)), 0)
        for k, L in enumerate(s.legs): L.rotation_euler = (R(jump * (35 if k < 2 else -35)), 0, 0)
        s.head.rotation_euler = (R(-15 * jump), 0, 0); s.mouth.scale = (s.m0[0], s.m0[1], s.m0[2] * (1 + 2.5 * jump))
DOGS = [Dog('#5a3a24', '#3a2416', 1.0), Dog('#f3f0ea', '#d8d0c4', 0.9), Dog('#d99a48', '#a86a2a', 1.05)]
# ---------- gestes ----------
def jump(c, t, t0, x, y, yaw, h=1.3, dur=0.75, z0=0.0):
    """saute à t0 (accroupi juste avant), bras en l'air, crie (bouche synchronisée)."""
    u = (t - t0) / dur
    if u < -0.25 or u > 1.25: c.put(x, y, z0, yaw); return False
    if u < 0: k = (u + 0.25) / 0.25; c.put(x, y, z0 - 0.12 * k, yaw); c.pose(lArm=(30 * k, 0, 0), rArm=(30 * k, 0, 0), lLeg=-25 * k, rLeg=-25 * k); return True
    if u > 1: k = 1 - (u - 1) / 0.25; c.put(x, y, z0 - 0.1 * k, yaw); c.pose(lLeg=-20 * k, rLeg=-20 * k); return True
    z = z0 + h * 4 * u * (1 - u); c.put(x, y, z, yaw)
    c.pose(lArm=(-165, 0, 18), rArm=(-165, 0, -18), lLeg=-35 + 25 * u, rLeg=-15 - 20 * u, head=(-12, 0, 0)); c.expr('w', 'o', talk=True); return True
def cheer(c, t, k=0.0):
    a = 0.5 + 0.5 * math.sin(t * 9 + k); c.pose(lArm=(-160 + 20 * a, 0, 15), rArm=(-160 + 20 * (1 - a), 0, -15), head=(-8, 0, 0))
# ---------- A / G / J : la rue (x 0) ----------
box(300, 6, 0.04, '#3a3d44', 0, 0, 0.02); box(300, 1.8, 0.08, '#c9c3b6', 0, -4, 0.04); box(300, 1.8, 0.08, '#c9c3b6', 0, 4, 0.04)
for xx in range(-140, 140, 6): box(2.2, 0.22, 0.01, '#f0eadc', xx, 0, 0.045)
for k, x in enumerate(range(-50, 51, 10)):
    house(x, 9, 7, 6, COLS[k % 6], ROOFS[k % 4], 0); house(x + 4, -9, 7, 6, COLS[(k + 3) % 6], ROOFS[(k + 1) % 4], 180)
for x in (-35, -15, 5, 25, 45):
    cyl(0.3, 2.4, '#6a4a30', x, 5.2, 1.2, 8); ball(1.3, '#4f9a3f', x, 5.2, 3.2)
for x in (-30, -14, 2, 18, 34):
    cyl(0.09, 4.2, '#2a2c31', x, 3.4, 2.1, 8); box(0.6, 0.35, 0.2, '#2a2c31', x, 3.1, 4.25); ball(0.18, '#fff2c0', x, 3.1, 4.1, emit=3)
    LAMPS.append(light('POINT', (x, 3.0, 4.0), 0, (1, 0.75, 0.45), shadow=False))
for k in range(6): box(1.2, 0.1, 0.8, '#ffffff', -20 + k * 9, -11.7, 2.8)     # (petits panneaux)
# ---------- B : terrain de basket (x 200) ----------
BX = 200
box(16, 28, 0.06, '#3f6fd0', BX, 0, 0.03); box(10, 16, 0.07, '#e88a3a', BX, 2, 0.035)
cyl(1.8, 0.08, '#f2f2f2', BX, 2, 0.05, 40); cyl(1.65, 0.09, '#e88a3a', BX, 2, 0.055, 40)
cyl(0.12, 3.6, '#c8c8c8', BX, 10.8, 1.8, 12); box(1.9, 0.1, 1.2, '#ffffff', BX, 10.3, 3.6); box(0.6, 0.12, 0.45, '#e8231c', BX, 10.24, 3.4)
bpy.ops.mesh.primitive_torus_add(major_radius=0.36, minor_radius=0.04); RING = bpy.context.object; RING.location = (BX, 9.85, 3.05); RING.data.materials.append(mat('#ff6a1a'))
for r in range(4):
    box(18, 1.4, 0.5 + 0.6 * r, '#9aa3b2', BX, 14 + 1.4 * r, 0.25 + 0.3 * r)
text('FINAL', 1.4, '#ffd400', BX, 19.5, 6.2, ext=0.08, emit=0.6); box(9, 0.3, 2.4, '#1d2a5a', BX, 19.8, 6.2)
BBALL = ball(0.2, '#e8591c', BX, 0, 0.2)
# ---------- C : boulangerie (x 300) ----------
PX = 300
box(12, 10, 0.05, '#f1e4cc', PX, 0, 0.03); box(12, 0.3, 6, '#f6eadb', PX, 5, 3); box(0.3, 10, 6, '#efe1cd', PX - 6, 0, 3); box(0.3, 10, 6, '#efe1cd', PX + 6, 0, 3)
text('BAKERY', 1.0, '#b8402f', PX, 4.8, 4.6, ext=0.06)
box(5, 1.2, 1.1, '#a8744a', PX, 0.8, 0.55); box(5.2, 1.4, 0.1, '#e8d8b8', PX, 0.8, 1.15)
OVM, OVE = emat('#ffb347', 3.0); box(2.4, 1.2, 2.2, '#5a5f68', PX + 3.4, 4.2, 1.1); box(1.6, 0.05, 0.9, '', PX + 3.4, 3.58, 1.3, m=OVM)
for k in range(4): box(1.6, 0.6, 0.06, '#c9b08a', PX - 4.2, 4.5, 1.2 + 0.7 * k)
BREAD = [box(0.42, 0.22, 0.18, '#d98a3a', PX - 1.6 + 0.55 * k, 0.8 + (k % 2) * 0.25, 1.3, bevel=0.06) for k in range(6)]
BREAD0 = [b.location.copy() for b in BREAD]
# ---------- D : classe (x 400) ----------
SX = 400
box(14, 12, 0.05, '#c79a6a', SX, 0, 0.03); box(14, 0.3, 6, '#e9e2cf', SX, 5, 3); box(0.3, 12, 6, '#e3dcc8', SX - 7, 0, 3); box(0.3, 12, 6, '#e3dcc8', SX + 7, 0, 3)
box(6, 0.12, 2.4, '#2f5a3a', SX, 4.82, 2.6); box(6.3, 0.1, 2.7, '#8a6a4a', SX, 4.86, 2.6)
text('TEST', 0.6, '#ffffff', SX, 4.74, 3.3, ext=0.01); text('2 + 2 = ?', 0.45, '#ffffff', SX, 4.74, 2.4, ext=0.01)
cyl(0.35, 0.05, '#ffffff', SX + 4.5, 4.8, 4.4, 24).rotation_euler = (R(90), 0, 0)
box(2.2, 1.0, 1.0, '#8a5a3a', SX - 2.5, 3.2, 0.5)
DESKS = [(SX - 2.6, -0.5), (SX, -0.5), (SX + 2.6, -0.5), (SX - 1.3, -2.8), (SX + 1.3, -2.8)]
for (x, y) in DESKS: box(1.3, 0.8, 0.08, '#c9a06a', x, y - 0.45, 0.8); box(0.08, 0.08, 0.8, '#6a6a6a', x, y - 0.45, 0.4); box(0.7, 0.7, 0.08, '#4a6ab0', x, y + 0.3, 0.45)
PAPERS = [box(0.3, 0.42, 0.01, '#ffffff', x, y - 0.45, 0.85) for (x, y) in DESKS]
# ---------- E : mariage (x 500) ----------
EX = 500
box(1.6, 7, 0.03, '#f4f4f4', EX, -2, 0.02)
for x in (-1.4, 1.4): cyl(0.1, 3, '#ffffff', EX + x, 2, 1.5, 12)
for k in range(15):
    a = math.pi * k / 14; ball(0.22, ('#ff9ec9', '#ffffff', '#ffc2dc')[k % 3], EX + 1.4 * math.cos(a), 2, 3 + 1.3 * math.sin(a))
for x, y in ((-4, 5), (4, 5), (-6, 1), (6, 1)): cyl(0.25, 2, '#6a4a30', EX + x, y, 1, 8); ball(1.4, '#4f9a3f', EX + x, y, 2.8)
for r in range(2):
    for k in range(3): box(0.6, 0.6, 0.5, '#ffffff', EX - 3.2 + k * 0.9 + (0 if k < 3 else 0), -3 - r * 1.5, 0.25); box(0.6, 0.6, 0.5, '#ffffff', EX + 1.4 + k * 0.9, -3 - r * 1.5, 0.25)
# ---------- F : les chiens (x 600) ----------
FX = 600
house(FX, 7, 8, 6, '#f2b8b0', '#2f4a8a', 0)
for k in range(12): box(0.2, 0.1, 1.0, '#ffffff', FX - 6 + k * 1.1, 3.4, 0.5)
box(13, 0.1, 0.12, '#ffffff', FX, 3.4, 0.85); box(13, 0.1, 0.12, '#ffffff', FX, 3.4, 0.45)
DBALL = ball(0.18, '#e8591c', FX + 2.2, -0.6, 0.18)
# ---------- H : la chambre (x 700) ----------
HX = 700
box(6, 6, 0.05, '#3a4a7a', HX, 0, 0.03); box(6, 0.3, 4, '#2a3560', HX, 3, 2); box(0.3, 6, 4, '#25305a', HX - 3, 0, 2); box(0.3, 6, 4, '#25305a', HX + 3, 0, 2)
box(1.4, 2.4, 0.5, '#6a4a30', HX, 1.5, 0.25); box(1.3, 2.3, 0.25, '#e9e9f2', HX, 1.5, 0.6); box(1.0, 0.5, 0.2, '#ffffff', HX, 2.4, 0.78); BLANK = box(1.34, 1.5, 0.12, '#d8463a', HX, 1.0, 0.76)
LAMPM, LAMPE = emat('#ffd27a', 0.0); box(0.5, 0.5, 0.6, '#5a4030', HX + 1.4, 2.4, 0.3); cyl(0.2, 0.3, '', HX + 1.4, 2.4, 0.85, 16, m=LAMPM)
ROOML = light('POINT', (HX + 1.2, 1.8, 2.2), 0, (1, 0.75, 0.45), shadow=True)
# ---------- I : réunion de la ville (x 800) ----------
MX = 800
box(14, 6, 6, '#e9e0cc', MX, 8, 3); box(15, 6.6, 0.6, '#8a3a2a', MX, 8, 6.3)
for x in (-4.5, -1.5, 1.5, 4.5): cyl(0.3, 5.4, '#ffffff', MX + x, 4.8, 2.7, 16)
box(8, 0.2, 1.4, '#1d3a8a', MX, 4.6, 4.6); text('TOWN MEETING', 0.62, '#ffd400', MX, 4.48, 4.6, ext=0.03)
box(1.4, 0.8, 1.3, '#6a4228', MX, 2.6, 0.65); box(1.6, 1.0, 0.1, '#8a5a3a', MX, 2.6, 1.32); cyl(0.02, 0.5, '#222222', MX + 0.55, 2.3, 1.6, 8); ball(0.06, '#222222', MX + 0.55, 2.3, 1.88)
box(4, 3, 0.3, '#b9b3a6', MX, 3, 0.15)
# ---------- K / L : la maison du maire (x 900), la nuit ----------
KX = 900
box(40, 1.8, 0.08, '#8a8578', KX, -2.2, 0.04); box(40, 6, 0.04, '#2e3138', KX, -6, 0.02)
for x in (-14, -7, 7, 14): house(KX + x, 3.5, 6, 5, COLS[int(x) % 6], ROOFS[int(x) % 4], 0)
# façade avec une grande fenêtre (ouverture) + chambre derrière
box(2.6, 0.3, 4.4, '#d8c8a8', KX - 2.7, 1, 2.2); box(2.6, 0.3, 4.4, '#d8c8a8', KX + 2.7, 1, 2.2); box(2.8, 0.3, 0.9, '#d8c8a8', KX, 1, 0.45); box(2.8, 0.3, 0.8, '#d8c8a8', KX, 1, 4.0)
box(8.6, 6.6, 0.6, '#5a2f26', KX, 3.6, 4.7); box(3.0, 0.12, 0.12, '#ffffff', KX, 0.83, 0.92)
box(7, 0.3, 4.4, '#c9b7e0', KX, 6.2, 2.2); box(0.3, 5.2, 4.4, '#c9b7e0', KX - 3.85, 3.6, 2.2); box(0.3, 5.2, 4.4, '#c9b7e0', KX + 3.85, 3.6, 2.2); box(7, 5.2, 0.05, '#8a6a4a', KX, 3.6, 0.03)
box(2.0, 2.6, 0.5, '#6a4a30', KX, 4.3, 0.25); box(1.9, 2.5, 0.3, '#ffffff', KX, 4.3, 0.62); box(1.4, 0.5, 0.22, '#f4f4f4', KX, 5.3, 0.86); box(1.94, 1.6, 0.14, '#2f7bff', KX, 3.7, 0.8)
box(1.0, 0.1, 1.4, '#ffd87a', KX + 2.2, 6.04, 2.6, emit=0.4); text('MAYOR', 0.25, '#3a2a1a', KX + 2.2, 5.98, 2.6, ext=0.01)
BEDL = light('POINT', (KX + 1.5, 3.4, 3.4), 0, (1, 0.78, 0.5), shadow=True)
cyl(0.09, 4.2, '#2a2c31', KX + 3.8, -1.2, 2.1, 8); ball(0.2, '#fff2c0', KX + 3.8, -1.5, 4.1, emit=3); LAMPS.append(light('POINT', (KX + 3.8, -1.6, 3.9), 0, (1, 0.75, 0.45), shadow=False)); LAMPS.append(light('POINT', (KX - 5, -4.0, 3.0), 0, (0.6, 0.7, 1.0), shadow=False))
FRAMEW = box(2.0, 0.05, 2.0, '', KX, 1.1, 2.2, m=wmat('#ffe0a0')); FRAMEW.hide_render = True
# ======================================================================= SÉQUENCES (temps = voix finale)
def reset():
    for c in ALL: c.show(False); c.pose(); c.expr()
    for d in DOGS: d.show(False)
    VEIL.hide_render = True; FILL.data.energy = 0; LAMPE.default_value = 0; ROOML.data.energy = 0; BEDL.data.energy = 0
    for b, p in zip(BREAD, BREAD0): b.location = p; b.rotation_euler = (0, 0, 0)
    for p_, (x, y) in zip(PAPERS, DESKS): p_.location = (x, y - 0.45, 0.85); p_.rotation_euler = (0, 0, 0)
# A (0 → 1,88) : « In my town, everybody copies me. »  gros plan du héros dans la rue, la foule passe derrière, la caméra recule
KA = [(0.0, (0.0, -1.3, 1.25), (0.0, 0.5, 1.2), 30), (1.0, (0.4, -2.6, 1.3), (0.0, 0.5, 1.15), 28), (1.88, (1.4, -4.2, 1.8), (0.0, 0.8, 1.1), 26)]
def seq_a(t, n):
    path(KA, t); day(); fill(25)
    HERO.put(0, 0, 0, 0); HERO.expr('n', 'sm'); say(HERO, t, 0.05, 1.69, 'n', 'sm'); HERO.pose(head=(-4, 0, 0))
    for k, c in enumerate(CROWD[:6]):
        y = 2.6 + (k % 2) * 0.9; x0 = -9 + k * 3.2 + t * (1.2 if k % 2 else -1.2)
        c.put(x0, y, 0, 90 if k % 2 else -90); c.walk(t + k, 1.0); c.expr('n', 'sm')
# B (1,88 → 5,90) : la finale de basket… il marque, saute : BOING!
KB = [(1.88, (BX - 5.5, -6.5, 2.4), (BX, 4, 1.6), 24), (3.0, (BX - 2.5, -3.5, 1.2), (BX, 6, 2.2), 24), (4.0, (BX + 1.6, -1.6, 0.7), (BX, 3, 2.4), 22),
      (4.9, (BX + 1.4, -1.8, 0.5), (BX, 3.2, 3.2), 20), (5.9, (BX + 3.2, -2.6, 1.0), (BX, 3, 2.0), 22)]
def seq_b(t, n):
    path(KB, t); day(3.0); fill(30)
    jx, jy = BX, 3.2
    if t < 3.9:
        walk_to(HERO, t, 1.88, 3.9, (BX - 1.5, -1.0), (jx, jy), 1.4); u = (t - 1.88) * 3.2
        BBALL.location = (HERO.n['root'].location.x + 0.35, HERO.n['root'].location.y - 0.3, 0.2 + 0.7 * abs(math.sin(u * 2)))
    elif t < 4.6:
        HERO.put(jx, jy, 0, 180); k = ss(3.9, 4.3, t); HERO.pose(lArm=(-150 * k, 0, 10), rArm=(-150 * k, 0, -10), head=(-25 * k, 0, 0))
        u = ss(4.25, 4.75, t); BBALL.location = (jx, lerp(jy + 0.3, 9.85, u), lerp(2.2, 3.1, u) + 1.6 * 4 * u * (1 - u))
    else:
        jump(HERO, t, 4.79, jx, jy, 0, 1.6, 1.0); BBALL.location = (BX, 9.85, max(0.2, 3.0 - 9 * (t - 4.75) ** 2))
    HERO.expr('n', 'sm') if t < 4.79 else None
    for k, c in enumerate(CROWD):
        r = k // 4; x = BX - 6 + (k % 4) * 3.6 + r * 1.5; y = 14.2 + 1.4 * r; z = 0.5 + 0.6 * r
        c.put(x, y, z, 0); c.expr('n', 'so' if t > 4.4 else 'sm')
        if t > 4.4: cheer(c, t, k)
# C (5,90 → 8,39) : le boulanger… BOING! les pains volent
KC = [(5.9, (PX - 3.5, -4.5, 2.4), (PX, 1.5, 1.4), 24), (7.0, (PX - 1.2, -3.0, 1.5), (PX, 1.6, 1.7), 26), (7.4, (PX - 0.8, -2.4, 0.9), (PX, 1.6, 2.4), 22), (8.39, (PX + 2.0, -3.2, 1.4), (PX, 1.6, 1.6), 24)]
def seq_c(t, n):
    path(KC, t); day(2.6); fill(70)
    if not jump(BAKER, t, 7.35, PX, 1.7, 0, 1.2, 0.8): BAKER.pose(lArm=(-60 + 15 * math.sin(t * 8), 0, 10), rArm=(-60 - 15 * math.sin(t * 8), 0, -10), head=(-15, 0, 0))
    if t < 7.35: BAKER.expr('n', 'sm')
    for k, (b, p) in enumerate(zip(BREAD, BREAD0)):
        u = max(0, t - 7.45); b.location = (p.x + (k - 2.5) * 0.5 * u, p.y - 0.6 * u, max(p.z, p.z + 4.2 * u - 6 * u * u)); b.rotation_euler = (u * (3 + k), u * 2, u * (k - 2))
# D (8,39 → 11,19) : la maîtresse, au milieu du contrôle… BOING!
KD = [(8.39, (SX - 4.5, -6.0, 3.2), (SX, 2.5, 1.4), 24), (9.5, (SX - 4.6, -3.2, 2.4), (SX + 0.4, 2.8, 1.6), 24), (10.2, (SX + 3.6, 0.2, 1.3), (SX + 0.5, 2.9, 2.2), 22), (11.19, (SX + 4.4, -1.6, 1.8), (SX + 0.4, 2.8, 1.8), 24)]
def seq_d(t, n):
    path(KD, t); day(2.6); fill(60)
    if not jump(TEACH, t, 10.13, SX + 0.6, 2.9, 0, 1.3, 0.8): TEACH.pose(rArm=(-80, 0, -10), head=(-10, 0, 0))
    if t < 10.13: TEACH.expr('n', 'c')
    for k, (c, (x, y)) in enumerate(zip(CROWD[:5], DESKS)):
        c.put(x, y, 0, 180 + 0 * k); c.sit(head=(-20, 0, 0)); c.expr('w' if t > 10.3 else 'n', 'o' if t > 10.3 else 'c')
        c.n['root'].rotation_euler.z = R(0)
    for k, (p_, (x, y)) in enumerate(zip(PAPERS, DESKS)):
        u = max(0, t - 10.25); p_.location = (x + 0.3 * math.sin(k + u * 3) * u, y - 0.45 + 0.4 * u, 0.85 + 3.0 * u - 2.2 * u * u if u < 1.3 else 0.85 + 3.0 * 1.3 - 2.2 * 1.69 - 0.3 * (u - 1.3))
        p_.rotation_euler = (u * 2 + k, u * 3, u * (k - 2))
# E (11,19 → 13,76) : la mariée, à son propre mariage… BOING!
KE = [(11.19, (EX - 1.2, -6.8, 2.2), (EX, 2, 1.6), 24), (12.3, (EX - 0.3, -4.4, 1.5), (EX, 1.2, 1.5), 26), (12.8, (EX - 0.4, -4.2, 1.1), (EX - 0.4, 1.2, 2.2), 20), (13.76, (EX + 0.6, -4.4, 1.6), (EX, 1.4, 1.7), 24)]
def seq_e(t, n):
    path(KE, t); day(); fill(25)
    PRIEST.put(EX, 2.3, 0, 0); PRIEST.expr('n', 'sm'); PRIEST.pose(lArm=(-50, 0, 0), rArm=(-50, 0, 0))
    GROOM.put(EX + 0.55, 1.2, 0, -90); GROOM.expr('n' if t < 12.9 else 'w', 'sm' if t < 12.9 else 'o')
    jumping = jump(BRIDE, t, 12.74, EX - 0.55, 1.2, 90, 1.5, 0.85)
    if t < 12.74: BRIDE.put(EX - 0.55, 1.2, 0, 90); BRIDE.expr('n', 'sm')
    hd = BRIDE.n['head'].matrix_world.translation if False else BRIDE.n['root'].location
    VEIL.hide_render = False; u = max(0, t - 12.9)
    VEIL.location = (hd.x + 0.22 + 0.8 * u, hd.y - 0.02 + 0.5 * u, (hd.z + 1.25 if u == 0 else hd.z + 1.25 + 2.6 * u - 0.9 * u * u)); VEIL.rotation_euler = (R(10 + 60 * u), R(-90 + 40 * u), R(30 * u))
    for k, c in enumerate(CROWD[:6]):
        x = EX + (-3.6 + (k % 3) * 0.9 if k < 3 else 1.8 + (k % 3) * 0.9); c.put(x, -2.6, 0.15, 180); c.sit(head=(-5, 0, 0)); c.expr('n', 'sm' if t < 12.9 else 'so')
# F (13,76 → 15,70) : même les chiens… BOING!
KF = [(13.76, (FX - 2.5, -4.5, 1.6), (FX, 1.0, 0.6), 24), (14.7, (FX - 0.8, -3.0, 0.35), (FX, 1.0, 1.3), 22), (15.7, (FX + 2.4, -3.2, 0.7), (FX, 1.0, 0.9), 24)]
def seq_f(t, n):
    path(KF, t); day(); fill(25)
    for k, d in enumerate(DOGS):
        x = FX - 1.4 + 1.4 * k; u = (t - 14.71 - 0.05 * k) / 0.7
        z = 1.2 * 4 * u * (1 - u) if 0 <= u <= 1 else 0
        d.put(x, 1.0, z, 0, t + k, 1.0 if 0 <= u <= 1 else 0.0)
        if os.environ.get('DBG'):
            bpy.context.view_layer.update()
            for o in d.parts[:4] + d.parts[-3:]: print('PART', k, tuple(round(v, 2) for v in o.matrix_world.translation), tuple(round(v, 2) for v in o.dimensions))
# G (15,70 → 19,23) : toute la nuit… BOING! BOING! BOING!  (des groupes différents sautent devant les maisons)
KG = [(15.7, (-5, -6, 2.5), (-1, 6, 1.5), 22), (16.66, (-2.5, -2.0, 1.4), (-2.5, 6, 2.0), 22), (17.39, (1.5, -2.0, 1.4), (3.5, 6, 2.0), 22), (18.14, (6.5, -2.2, 1.6), (7.5, 6, 2.0), 22), (19.23, (5, -12, 12), (4, 4, 1.0), 22)]
GPOS = [(-4, 6.0), (-2.5, 6.4), (-1, 5.8), (2.5, 6.2), (4, 5.6), (5.5, 6.4), (7.5, 5.9), (9, 6.3)]
def seq_g(t, n):
    path(KG, t); dark(); fill(20)
    for k, (c, (x, y)) in enumerate(zip(CROWD, GPOS)):
        t0 = (16.61, 17.34, 18.09)[k % 3] + 0.03 * k
        if not jump(c, t, t0, x, y, 0, 1.2, 0.6): c.expr('n', 'sm')
    for k, (c, (x, y)) in enumerate(((BAKER, (0.5, 5.6)), (TEACH, (11, 5.8)))):
        if not jump(c, t, (17.34, 18.09)[k], x, y, 0, 1.1, 0.6): c.expr('n', 'sm')
# H (19,23 → 20,32) : personne ne pouvait dormir.  (le héros dans son lit, les yeux grands ouverts, la chambre tremble)
KH = [(19.23, (HX + 0.6, 0.2, 3.3), (HX, 2.0, 0.95), 24), (20.32, (HX + 0.3, 0.8, 2.8), (HX, 2.1, 0.95), 30)]
def seq_h(t, n):
    path(KH, t, 0.05 + 0.04 * abs(math.sin(t * 9))); dark(); LAMPE.default_value = 4; ROOML.data.energy = 120; fill(10)
    HERO.put(HX, 0.75, 0.86, 0, pitch=-90); HERO.expr('w', 'c'); HERO.pose(head=(0, 0, 4 * math.sin(t * 7)))
    BLANK.location = (HX, 1.0, 1.02 + 0.01 * math.sin(t * 30))
# I (20,32 → 23,73) : le maire convoque la ville : « From today, BOING is forbidden! »  (coup de poing sur le pupitre sur BOING)
KI = [(20.32, (MX - 5, -8, 3.4), (MX, 3, 1.8), 24), (21.6, (MX - 2.2, -2.6, 2.3), (MX, 3.1, 1.9), 26), (22.55, (MX - 0.8, -0.6, 2.1), (MX, 3.1, 2.0), 30), (23.73, (MX + 0.4, -0.2, 2.15), (MX, 3.1, 2.1), 34)]
def seq_i(t, n):
    path(KI, t, 0.02 if t < 22.55 else 0.02 + 0.06 * max(0, 1 - (t - 22.55) * 3)); day(3.0); fill(30)
    MAYOR.put(MX, 3.1, 0, 0); MAYOR.expr('a', 'c'); say(MAYOR, t, 21.80, 23.70, 'a', 'o')
    k = ss(22.4, 22.6, t) * (1 - ss(22.9, 23.2, t)); MAYOR.pose(rArm=(-100 + 60 * k, 0, -10), lArm=(-40, 0, 0), head=(-6, 0, 0), upper=(8 * k, 0, 0))
    for k2, c in enumerate(CROWD):
        x = MX - 4.2 + (k2 % 4) * 2.8; y = -1.5 - (k2 // 4) * 1.6; c.put(x, y, 0, 180); c.pose(head=(-12, 0, 0)); c.expr('w' if t > 22.6 else 'n', 'o' if t > 22.6 else 'c')
    HERO.put(MX + 4.6, -0.8, 0, 160); HERO.expr('w', 'c')
# J (23,73 → 25,79) : silence… pour la première fois depuis des semaines  (survol lent de la rue au matin, tout le monde immobile)
KJ = [(23.73, (-14, -14, 9), (2, 4, 1), 22), (25.79, (12, -16, 14), (4, 4, 1), 22)]
def seq_j(t, n):
    path(KJ, t, 0.006); day(2.6); sky('#bfe4ff', 1.0); fill(20)
    for k, (c, (x, y)) in enumerate(zip(CROWD, GPOS)): c.put(x, y - 1.2, 0, 0); c.pose(head=(-10, 0, 0)); c.expr('n', 'c')
# K (25,79 → 29,25) : cette nuit-là, je passe devant la maison du maire… à travers la fenêtre
KK = [(25.79, (KX - 9.5, -5.4, 1.5), (KX - 6.5, -2.0, 1.1), 26), (27.1, (KX - 6.0, -5.2, 1.5), (KX - 3.0, -1.8, 1.2), 26), (27.91, (KX - 3.4, -4.8, 1.7), (KX - 0.5, 0.5, 1.7), 24),
      (28.8, (KX + 0.3, -2.4, 2.0), (KX, 3.8, 1.7), 24), (29.25, (KX - 0.1, -1.8, 2.1), (KX, 4.3, 1.9), 24)]
def seq_k(t, n):
    path(KK, t); dark(); BEDL.data.energy = 260; fill(40)
    walk_to(HERO, t, 25.79, 28.0, (KX - 7.5, -2.4), (KX - 2.4, -2.4), 1.2) if t < 28.0 else HERO.put(KX - 2.4, -2.4, 0, 205)
    if t >= 28.0: HERO.pose(head=(-8, 0, 0)); HERO.expr('w', 'c')
    else: HERO.expr('n', 'c')
    MAYOR.put(KX, 4.3, 0.75, 0); MAYOR.pose(head=(-10, 0, 0)); MAYOR.expr('n', 'sm')
# L (29,25 → fin) : le maire, seul… saute sur son lit.  …boing.  (zoom sur son sourire)
KL = [(29.25, (KX - 0.1, -1.8, 2.1), (KX, 4.3, 1.9), 24), (30.3, (KX + 0.1, -1.0, 2.2), (KX, 4.3, 2.2), 26), (30.9, (KX + 0.05, -0.3, 2.5), (KX, 4.3, 2.7), 34), (31.6, (KX, 0.4, 2.7), (KX, 4.3, 2.8), 50)]
def seq_l(t, n):
    path(KL, t); dark(); BEDL.data.energy = 300; fill(30)
    u = ((t - 29.53) / 0.62) % 1 if t > 29.53 else 0; z = 0.75 + 0.7 * 4 * u * (1 - u) if t < 30.85 else 0.75 + 0.3 * ss(30.85, 31.2, t)
    MAYOR.put(KX, 4.3, z, 0)
    if 29.53 < t < 30.85: MAYOR.pose(lArm=(-165, 0, 18), rArm=(-165, 0, -18), lLeg=-30, rLeg=-20); MAYOR.expr('w', 'so')
    else: MAYOR.pose(lArm=(-40, 0, 0), rArm=(-40, 0, 0)); MAYOR.expr('n', 'sm'); say(MAYOR, t, 30.9, 31.33, 'n', 'sm')
SEQ = [(0.0, seq_a), (1.88, seq_b), (5.90, seq_c), (8.39, seq_d), (11.19, seq_e), (13.76, seq_f), (15.70, seq_g), (19.23, seq_h), (20.32, seq_i), (23.73, seq_j), (25.79, seq_k), (29.25, seq_l), (99, None)]
def setup(n):
    t = n / FPS; i = max(k for k in range(len(SEQ) - 1) if SEQ[k][0] <= t); reset(); SEQ[i][1](t, n)
    for c in ALL:
        if id(c) in SCALE: c.n['root'].scale = (SCALE[id(c)],) * 3
        c.life(t, n)
sc.render.engine = 'BLENDER_EEVEE'; ee = sc.eevee; ee.taa_render_samples = int(os.environ.get('TAA', 8)); ee.use_gtao = True; ee.gtao_distance = 1.0; ee.use_soft_shadows = True
ee.shadow_cube_size = '512'; ee.shadow_cascade_size = '2048'; ee.use_bloom = True; ee.bloom_intensity = 0.05; ee.use_ssr = False
sc.render.resolution_x = W; sc.render.resolution_y = H; sc.render.resolution_percentage = 100
sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'Medium High Contrast'; sc.view_settings.exposure = float(os.environ.get('EXPO', -0.3))
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 92
FR = [int(x) for x in os.environ['ONLY'].split(',')] if os.environ.get('ONLY') else range(n0, n1)
os.makedirs(OUT, exist_ok=True)
for n in FR:
    setup(n)
    if os.environ.get('DBG'):
        bpy.context.view_layer.update(); cl = cam.location
        for o in bpy.data.objects:
            if o.type == 'MESH' and not o.hide_render and (o.matrix_world.translation - cl).length < 3.5: print('NEAR', o.name, tuple(round(v, 2) for v in o.matrix_world.translation), tuple(round(v, 2) for v in o.dimensions), o.parent.name if o.parent else '')
    sc.frame_set(n + 1); sc.render.filepath = os.path.join(OUT, f'f{n:05d}.jpg'); bpy.ops.render.render(write_still=True)
print('DONE', n0, n1)
