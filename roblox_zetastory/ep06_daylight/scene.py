# ZetaStory ép. 6 – « Le jour » (Blender EEVEE, personnages en blocs, style Roblox : mains sans doigts).
# Caméra : plans continus et rapides quand les personnages sont proches, coupe seulement quand on change de lieu.
# Chaque réplique est dite à l'écran par le personnage, bouche synchronisée sur la voix (env.json).
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
HERO = Char('char_BK.glb', 'BK', shirt='#3a3f4a', pants='#1c2230', blink=0.3)          # sans le Z, sweat sombre
BRO = Char('char_C1.glb', 'C1', shirt='#f2c230', pants='#2a3b55', blink=1.3)
OLD = Char('char_E2.glb', 'E2', shirt='#6b4630', pants='#3a3028', hair='#ececec', skin='#d8b894', blink=2.1)
VICT = Char('char_E3.glb', 'E3', shirt='#2f7bff', pants='#22262e', blink=0.7)          # l'homme enlevé au début… retrouvé vivant
CROWD = [Char(g, p, shirt=sh, pants=pa, hair=hr, blink=k * 0.37) for k, (g, p, sh, pa, hr) in enumerate((
    ('char_W.glb', 'W', '#ff7ac0', '#5a4bb0', '#e0b050'), ('char_E0.glb', 'E0', '#27b36a', '#30343c', None), ('char_M2.glb', 'M2', '#e8231c', '#2a3b55', None),
    ('char_E1.glb', 'E1', '#8e5bd9', '#22262e', None), ('char_W.glb', 'W', '#3fa0c8', '#33384a', '#3a2618'), ('char_E1.glb', 'E1', '#f2c230', '#2a3b55', None),
    ('char_C2.glb', 'C2', '#ff8a2b', '#30343c', None), ('char_E0.glb', 'E0', '#d9d0f0', '#3b2c22', None)))]
ALL = [HERO, BRO, OLD, VICT] + CROWD
for c in ALL: roblox(c)
SCALE = {id(HERO): 0.85, id(BRO): 0.62, id(CROWD[6]): 0.7}
SKIN = '#2c3036'
class Giant:
    def __init__(s, eye='#ffb347'):
        s.root = bpy.data.objects.new('g', None); COL.objects.link(s.root); s.root.rotation_mode = 'XYZ'; s.parts = []
        def emp(par, loc):
            e = bpy.data.objects.new('p', None); COL.objects.link(e); e.parent = par; e.location = loc; e.rotation_mode = 'XYZ'; return e
        def bx(par, w, d, h, loc, col=SKIN, **kw):
            o = box(w, d, h, col, *loc, bevel=0.35, rough=0.85, **kw); o.parent = par; s.parts.append(o); return o
        s.legL = emp(s.root, (-2.6, 0, 14)); s.legR = emp(s.root, (2.6, 0, 14))
        for L in (s.legL, s.legR): bx(L, 3.4, 3.6, 14, (0, 0, -7)); bx(L, 3.8, 5.0, 1.4, (0, -0.6, -13.4))
        s.body = emp(s.root, (0, 0, 14)); bx(s.body, 11, 6.5, 13.5, (0, 0, 6.6)); bx(s.body, 12.4, 7, 2.2, (0, 0, 13.2))
        s.armL = emp(s.body, (-7.4, 0, 12.2)); s.armR = emp(s.body, (7.4, 0, 12.2))
        for A in (s.armL, s.armR): bx(A, 3.0, 3.2, 15, (0, 0, -7.2)); bx(A, 4.2, 4.2, 4.0, (0, 0, -16.2))
        s.head = emp(s.body, (0, 0, 14.4)); bx(s.head, 8, 7.4, 7.2, (0, 0, 3.6))
        s.eyes = [bx(s.head, 1.8, 0.3, 0.9, (x, -3.72, 4.4), col=eye, emit=6) for x in (-1.9, 1.9)]
        bx(s.head, 3.2, 0.3, 0.35, (0, -3.72, 2.0), col='#101114')
        s.show(False)
    def show(s, v=True):
        for o in s.parts: o.hide_render = not v
    def put(s, x, y, z=0, yaw=0, sc=1.0):
        s.root.location = (x, y, z); s.root.rotation_euler = (0, 0, R(yaw)); s.root.scale = (sc,) * 3; s.show(True)
    def pose(s, t=0, walk=0.0, armL=0, armR=0, head=(0, 0, 0), lean=0):
        a = math.sin(t * 2.2) * 22 * walk
        s.legL.rotation_euler = (R(a), 0, 0); s.legR.rotation_euler = (R(-a), 0, 0)
        s.armL.rotation_euler = (R(-a + armL), 0, 0); s.armR.rotation_euler = (R(a + armR), 0, 0)
        s.head.rotation_euler = tuple(R(v) for v in head); s.body.rotation_euler = (R(lean), 0, 0)
        s.body.location = (0, 0, 14 + 0.4 * abs(math.cos(t * 2.2)) * walk)
GIANTS = [Giant(), Giant(), Giant()]
# la grande main qui descend du ciel : paume + 4 gros doigts + bras qui monte très haut
HAND = bpy.data.objects.new('hand', None); COL.objects.link(HAND); HAND.rotation_mode = 'XYZ'; HPARTS = []
def hb(par, w, d, h, loc):
    o = box(w, d, h, SKIN, *loc, bevel=0.25, rough=0.85); o.parent = par; HPARTS.append(o); return o
hb(HAND, 5.0, 4.4, 1.6, (0, 0, 0)); hb(HAND, 3.4, 3.4, 120, (0, 1.0, 60.5))
FING = []
for x in (-1.8, -0.6, 0.6, 1.8):
    p = bpy.data.objects.new('f', None); COL.objects.link(p); p.parent = HAND; p.location = (x, -2.2, 0); p.rotation_mode = 'XYZ'; hb(p, 1.05, 3.0, 1.05, (0, -1.5, 0)); FING.append(p)
def hand_at(x, y, z, curl=0.0, yaw=0):
    HAND.location = (x, y, z); HAND.rotation_euler = (0, 0, R(yaw))
    for f in FING: f.rotation_euler = (R(95 * curl), 0, 0)
    for o in HPARTS: o.hide_render = False
def held(c, x, y, z, yaw, t, k=0.0):
    """personnage tenu par la main : bras en l'air, jambes qui gigotent."""
    c.put(x, y, z, yaw); a = math.sin(t * 11 + k) * 25
    c.pose(lArm=(-165, 0, 12), rArm=(-165, 0, -12), lLeg=a, rLeg=-a, head=(-12, 0, 0))
# ---------- la ville (rue le long de x, y = 0) ----------
GROUND = box(600, 600, 0.2, '#6f7a4a', 0, 0, -0.1)
COLS = ['#d9c4a8', '#c9d3dc', '#d8b5b0', '#c4d3b8', '#d9d0b4', '#c8c0d8']; ROOFS = ['#6a2f26', '#2f3a52', '#4a3226', '#2f4a36']
WINS = []
def wmat(col='#ffcf7a'):
    m_, e_ = emat(col, 0.0); m_.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = hexc('#1d2026'); WINS.append(e_); return m_
def house(x, y, w, d, col, roof, yaw=0, door=True):
    g = bpy.data.objects.new('h', None); COL.objects.link(g); g.location = (x, y, 0); g.rotation_euler = (0, 0, R(yaw))
    for o in (box(w, d, 3.2, col, 0, 0, 1.6), box(w + 0.6, d + 0.6, 0.5, roof, 0, 0, 3.45), box(w * 0.7, d * 0.7, 1.0, roof, 0, 0, 4.1)):
        o.parent = g
    if door: box(1.0, 0.1, 2.0, '#4a2f20', 0, -d / 2 - 0.06, 1.0).parent = g
    for k in (-1, 1): box(1.0, 0.1, 0.9, '', k * w * 0.3, -d / 2 - 0.06, 2.0, m=wmat()).parent = g
    return g
box(300, 6, 0.04, '#34373d', 0, 0, 0.02); box(300, 1.8, 0.08, '#b9b3a6', 0, -4, 0.04); box(300, 1.8, 0.08, '#b9b3a6', 0, 4, 0.04)
for xx in range(-140, 140, 6): box(2.2, 0.22, 0.01, '#e8e2d6', xx, 0, 0.045)
for k, x in enumerate(range(-60, 61, 10)):
    if x not in (20, 30): house(x, 9, 7, 6, COLS[k % 6], ROOFS[k % 4], 0, door=(x != -10))
    if x not in (0, 10): house(x + 4, -9, 7, 6, COLS[(k + 3) % 6], ROOFS[(k + 1) % 4], 180)
# la porte de notre maison (x = -10, côté nord) s'ouvre
box(1.0, 0.02, 2.0, '#120c08', -10, 5.955, 1.0)
FDOOR = bpy.data.objects.new('fd', None); COL.objects.link(FDOOR); FDOOR.location = (-10.5, 5.89, 0); FDOOR.rotation_mode = 'XYZ'
box(1.0, 0.1, 2.0, '#4a2f20', 0.5, 0, 1.0).parent = FDOOR
for x in (-35, -15, 5, 45):
    cyl(0.3, 2.4, '#4a3324', x, 5.2, 1.2, 8); ball(1.3, '#3f6b33', x, 5.2, 3.2)
LAMPS = []
for x in (-30, -14, 2, 18, 34):
    cyl(0.09, 4.2, '#2a2c31', x, 3.4, 2.1, 8); box(0.6, 0.35, 0.2, '#2a2c31', x, 3.1, 4.25)
    LAMPS.append(light('POINT', (x, 3.0, 4.0), 0, (1, 0.72, 0.4), shadow=False))
# école (la nuit) : x 25, horloge 12:00
box(16, 8, 7, '#7a4a3c', 25, 13, 3.5); box(17, 9, 0.6, '#3a2420', 25, 13, 7.2)
for ix in (-5, -2.5, 2.5, 5):
    for z in (2.0, 5.0): box(1.6, 0.1, 1.4, '', 25 + ix, 8.94, z, m=wmat('#ffd98a'))
box(2.4, 0.2, 2.6, '#3a2420', 25, 8.95, 1.3); text('SCHOOL', 0.8, '#ffffff', 25, 8.85, 6.3, ext=0.05)
box(16, 0.2, 2.6, '#7a4a3c', 25, 9.0, 8.4); CLK_M, CLK_E = emat('#fff4d6', 0.0)
cyl(1.0, 0.15, '', 25, 8.85, 9.0, 32, m=CLK_M).rotation_euler = (R(90), 0, 0); text('12:00', 0.55, '#141416', 25, 8.74, 9.0, ext=0.02)
# magasin ouvert la nuit : x 5, côté sud (regarde vers +y)
box(10, 7, 4.5, '#cfd6dc', 5, -12, 2.25); SHOP_M, SHOP_E = emat('#bff3ff', 0.0); box(7, 0.1, 2.6, '', 5, -8.44, 1.5, m=SHOP_M)
SIGN_M, SIGN_E = emat('#ff4fa3', 0.0); text('OPEN', 0.8, '', 3.2, -8.36, 3.65, rot=(90, 0, 180), ext=0.05, m=SIGN_M)
DIG_M, DIG_E = emat('#58ff7a', 0.0); box(2.6, 0.08, 0.8, '#101214', 7.4, -8.42, 3.65); text('3:00 AM', 0.5, '', 7.4, -8.36, 3.65, rot=(90, 0, 180), ext=0.02, m=DIG_M)
BALL = ball(0.3, '#e8591c', -6.2, -1.5, 0.3)
BAG = box(0.5, 0.3, 0.45, '#7a5232', -9.4, -3.0, 0.25, bevel=0.05)
# ---------- la grotte (x = 600) ----------
CX = 600
box(60, 60, 0.4, '#3a2c22', CX, 0, -0.2, rough=1)
for (w, d, h, x, y) in ((60, 2, 16, 0, 25), (60, 2, 16, 0, -25), (2, 60, 16, 25, 0), (2, 60, 16, -25, 0)):
    box(w, d, h, '#4a3a2e', CX + x, y, h / 2, rough=1)
for (w, d, x, y) in ((60, 21, 0, 14.5), (60, 21, 0, -14.5), (21, 8, 14.5, 0), (21, 8, -14.5, 0)):
    box(w, d, 1.5, '#3a2c22', CX + x, y, 16, rough=1)                       # plafond avec un trou au centre (8 x 8)
for k in range(40):
    a = rnd.random() * 6.28; r = 12 + rnd.random() * 10; box(1 + rnd.random() * 3, 1 + rnd.random() * 3, 0.5 + rnd.random() * 3, '#5a4636', CX + r * math.cos(a), r * math.sin(a), 0.5, rough=1)
for (w, d, x, y) in ((10, 1, 0, 4.5), (10, 1, 0, -4.5), (1, 10, 4.5, 0), (1, 10, -4.5, 0)):
    box(w, d, 40, '#4a3a2e', CX + x, y, 37, rough=1)                        # le puits au-dessus du trou
for (w, d, x, y) in ((900, 400, 0, 204.5), (900, 400, 0, -204.5), (400, 9, 204.5, 0), (400, 9, -204.5, 0)):
    box(w, d, 1, '#4a2418', CX + x, y, 56.5, rough=1)                      # la surface, tout en haut
TORCH = []
for (x, y) in ((-10, 9), (10, 9), (-13, -4), (13, -4), (0, 13), (-6, -11), (7, -11)):
    cyl(0.12, 1.6, '#3a2618', CX + x, y, 0.8, 8); ball(0.22, '#ffb347', CX + x, y, 1.7, emit=8)
    TORCH.append(light('POINT', (CX + x, y, 2.2), 0, (1, 0.55, 0.22), shadow=False))
SHAFT = light('SPOT', (CX, 0, 15), 0, (1, 0.3, 0.15), 60, tgt=(CX, 0, 0)); SHAFT2 = light('POINT', (CX, 0, 30), 0, (1, 0.3, 0.15), shadow=False)
# ---------- soleil (disque) + lumières ----------
SUNM, SUNE = emat('#ff3a14', 0.0); SUNB = SUNM.node_tree.nodes['Principled BSDF']
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=32, ring_count=16); SUNDISC = bpy.context.object; SUNDISC.data.materials.append(SUNM)
SUN = light('SUN', (0, 0, 50), 0, (1, 0.45, 0.25)); SUN.data.angle = R(3)
FILL = light('AREA', (0, 0, 20), 0, (1, 0.9, 0.8), 3.0, shadow=False)
# ---------- caméra ----------
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
def sun_disc(loc, sc, col, s):
    SUNDISC.hide_render = False; SUNDISC.location = loc; SUNDISC.scale = (sc,) * 3
    SUNB.inputs['Base Color'].default_value = hexc(col); SUNB.inputs['Emission Color'].default_value = hexc(col); SUNE.default_value = s
def night(v):
    for e in WINS: e.default_value = 2.6 * v
    for L in LAMPS: L.data.energy = 260 * v
    CLK_E.default_value = 2.2 * v; SHOP_E.default_value = 0.7 * v; SIGN_E.default_value = 7 * v; DIG_E.default_value = 6 * v
def fill(e):
    FILL.location = cam.location; FILL.rotation_euler = cam.rotation_euler; FILL.data.energy = e
def reset():
    SHAFT2.data.energy = 0
    for c in ALL: c.show(False); c.pose(); c.expr()
    for g in GIANTS: g.show(False)
    for o in HPARTS: o.hide_render = True
    night(0); SUNDISC.hide_render = True; SHAFT.data.energy = 0; FILL.data.energy = 0
    for L in TORCH: L.data.energy = 0
    FDOOR.rotation_euler = (0, 0, 0); BALL.location = (-6.2, -1.5, 0.3); BAG.hide_render = True
def day():
    sky('#ff7444', 0.55); SUN.data.energy = 3.6; SUN.data.color = (1, 0.5, 0.3); SUN.rotation_euler = (R(-50), 0, R(15))
# ---------- A (0 → 10,75) : la ville vide le jour, les géants, un homme enlevé ----------
KA = [(0.0, (-40, -6, 34), (-6, 0, 1), 24), (1.4, (-26, -3, 12), (-4, 0, 1), 24), (2.6, (-15, -1.2, 1.3), (0, 0, 1.6), 24),
      (3.6, (-14, -1.0, 0.7), (20, 0, 12), 20), (5.1, (-12, -1.0, 0.8), (14, 0, 22), 20), (6.3, (-6, -13, 16), (14, 0, 22), 22),
      (7.3, (-15, -2.0, 6), (-8, -3, 2), 24), (8.0, (-17, -1.6, 2.2), (-9.6, -3.4, 2.4), 26), (8.8, (-17, -1.6, 2.8), (-9.8, -3.4, 5.5), 24),
      (9.6, (-17, -1.8, 3.2), (-9.8, -3.4, 10), 22), (10.75, (-12.6, -2.2, 1.1), (-9.6, -3.2, 0.25), 30)]
def seq_a(t, n):
    path(KA, t, 0.012); day(); fill(30)
    g = GIANTS[0]; x = lerp(60, 14, ss(2.0, 7.5, t) * 0 + max(0, min(1, (t - 2.0) / 5.5))) if t < 7.5 else lerp(14, 8, (t - 7.5) / 3.25)
    g.put(x, 0, 0, -90); g.pose(t, 1.0 if t < 7.5 else 0.5)
    g2 = GIANTS[1]; g2.put(lerp(46, 22, t / 10.75), 27, 0, -90); g2.pose(t + 1.1, 1.0)
    g3 = GIANTS[2]; g3.put(lerp(70, 52, t / 10.75), -30, 0, -80, 0.9); g3.pose(t + 0.4, 1.0)
    # l'homme qui court… la main descend du ciel
    VICT.expr('w', 'o')
    if t < 8.35:
        walk_to(VICT, t, 7.0, 8.35, (-1.5, -3.6), (-9.8, -3.4), 1.9); VICT.n['head'].rotation_euler.z += R(35 * ss(7.3, 7.7, t))
        hz = lerp(70, 2.9, ss(7.55, 8.35, t)); hand_at(-9.8, -3.4, hz, 0.0, 90)
        if t < 7.0: VICT.show(False)
    else:
        cu = ss(8.35, 8.6, t); hz = lerp(2.9, 3.6, cu) + 40 * ss(8.55, 9.9, t) ** 1.4; hand_at(-9.8, -3.4, hz, cu, 90)
        held(VICT, -9.8, -3.4, hz - 2.9, -90, t)
        BAG.hide_render = False; BAG.location = (-9.4, -3.0, lerp(1.0, 0.23, ss(8.4, 8.6, t)))
# ---------- B (10,75 → 14,63) : la nuit, la vie continue ----------
KB = [(10.75, (-24, -18, 16), (2, 2, 1), 24), (11.9, (8, -12, 6), (18, 4, 2.5), 24), (12.6, (19, -4.5, 1.7), (25, 9, 5.5), 22),
      (13.24, (19.5, -3.5, 1.8), (25, 9, 6), 24), (13.85, (13, 0.5, 2.0), (5, -8.5, 2.6), 26), (14.63, (10, -2.6, 1.8), (5, -8.5, 2.2), 30)]
def seq_b(t, n):
    path(KB, t, 0.012); sky('#0b1430', 0.35); night(1); fill(25)
    SUN.data.energy = 0.35; SUN.data.color = (0.5, 0.6, 1); SUN.rotation_euler = (R(-35), 0, R(-30))
    sun_disc((90, 300, 150), 10, '#e8eeff', 3)
    for c in (HERO, BRO): c.expr('n', 'sm')
    walk_to(HERO, t, 10.75, 13.3, (16.5, -2.2), (23.6, 7.6), 1.2); walk_to(BRO, t, 10.75, 13.3, (17.8, -2.6), (24.8, 7.4), 1.5)
    for c, p0, p1 in ((CROWD[3], (-12, 4.2), (6, 4.2)), (CROWD[4], (8, 3.8), (-10, 3.8)), (CROWD[2], (-2, -4.0), (14, -4.0)), (CROWD[1], (5.5, -7.8), (12, -4.4))):
        walk_to(c, t, 10.75, 14.63, p0, p1, 1.1); c.expr('n', 'sm')
    CROWD[0].put(3.6, -7.6, 0, 160); CROWD[0].pose(lArm=(-30, 0, 0)); CROWD[0].expr('n', 'sm')
    CROWD[5].put(6.6, -7.4, 0, -150); CROWD[5].expr('n', 'so'); say(CROWD[5], t, 99, 99)
# ---------- C (14,63 → 19,92) : midi, mon petit frère sort… ----------
KC = [(14.63, (-7.5, -1.5, 1.4), (-10, 6, 1.2), 30), (15.4, (-7.6, -2.0, 1.3), (-10, 5.5, 1.0), 30), (16.3, (-3.5, -5.4, 1.2), (-7, -0.5, 0.7), 28),
      (17.1, (-3.0, -5.5, 1.3), (-8, 1.5, 1.0), 28), (17.9, (-2.6, -5.6, 1.3), (-6, -1.2, 1.1), 26), (18.5, (-2.8, -5.6, 0.9), (-5.8, -1.2, 9), 18),
      (19.0, (-2.8, -5.6, 1.1), (-5.8, -1.2, 2.5), 20), (19.92, (-2.4, -5.6, 3.0), (-5.8, -1.2, 7.0), 18)]
HX, HY = -5.7, -0.6
def seq_c(t, n):
    path(KC, t, 0.014); day(); fill(30)
    FDOOR.rotation_euler = (0, 0, R(-105 * ss(14.85, 15.25, t)))
    if t < 18.95:
        if t >= 15.15: walk_to(BRO, t, 15.15, 16.4, (-10, 5.5), (-6.6, -1.1), 2.0)
        if t >= 16.4: BRO.put(-6.6, -1.1, 0, yawto(-6.6, -1.1, -5.4, -1.1) if t > 17.6 else 10); BRO.pose(lArm=(-40, 0, 0), rArm=(-40, 0, 0), head=(-25 * ss(18.1, 18.4, t), 0, 0))
        BALL.location = (lerp(-6.2, -6.5, ss(16.2, 16.5, t)), lerp(-1.5, -1.7, ss(16.2, 16.5, t)), 0.3)
        if t >= 16.95: walk_to(HERO, t, 16.95, 17.95, (-10, 5.5), (-5.4, -1.1), 2.0)
        if t >= 17.95:
            HERO.put(-5.4, -1.1, 0, -60); hug = ss(17.95, 18.3, t)
            HERO.pose(lArm=(-60 * hug, 0, 30 * hug), rArm=(-60 * hug, 0, -10 * hug), head=(-25 * ss(18.1, 18.4, t), 0, 0))
        u = max(0, min(1, (t - 17.8) / 1.15)); hz = lerp(32, 2.75, 1 - (1 - u) ** 2); hand_at(HX, HY, hz, 0, -90)
        if t > 18.05: BALL.location = (-6.5, -1.7, 0.3)
    else:
        cu = ss(18.95, 19.25, t); hz = lerp(2.75, 3.4, cu) + 6.6 * ss(19.2, 19.92, t); hand_at(HX, HY, hz, cu, -90)
        held(HERO, HX + 0.3, HY - 0.5, hz - 2.75, -15, t); held(BRO, HX - 0.9, HY - 0.5, hz - 2.4, 10, t, 1.3)
    HERO.expr('w' if t > 17.0 else 'n', 'o' if t > 18.1 else 'c'); BRO.expr('w' if t > 18.2 else 'n', 'o' if t > 18.2 else 'sm')
# ---------- D + E (19,92 → 33,82) : la grotte… puis on remonte vers le soleil (un seul plan) ----------
KD = [(19.92, (CX + 3.5, -10, 1.4), (CX, 0, 11), 22), (21.0, (CX + 3.2, -8.5, 1.5), (CX - 0.2, -0.6, 5), 24), (21.9, (CX + 2.6, -6.5, 1.6), (CX - 0.3, -0.9, 1.3), 26),
      (22.7, (CX + 1.5, -6.5, 3.5), (CX, 2, 1.4), 24), (23.4, (CX + 0.5, -8, 5.5), (CX, 5, 1.2), 24), (24.3, (CX + 5.5, -0.5, 2.0), (CX + 3.2, 4.2, 1.6), 30),
      (25.2, (CX + 3.4, -1.8, 1.9), (CX + 1.2, 4.0, 1.5), 28), (26.4, (CX + 1.6, -2.4, 1.75), (CX + 0.3, 1.7, 1.62), 32), (27.6, (CX + 1.3, -1.6, 1.72), (CX + 0.3, 1.7, 1.64), 34),
      (29.4, (CX + 0.95, -0.5, 1.7), (CX + 0.3, 1.7, 1.65), 38), (29.9, (CX + 1.6, -1.6, 1.4), (CX + 0.3, 1.7, 2.4), 26), (30.6, (CX + 1.5, -1.4, 1.3), (CX + 0.2, 1.4, 4.2), 22), (31.2, (CX + 0.9, -0.8, 2.6), (CX + 0.1, 0.5, 12), 22),
      (31.9, (CX + 0.4, -0.4, 10), (CX, 0.3, 40), 20), (32.7, (CX + 0.2, -0.3, 40), (CX, 1.5, 70), 22), (33.4, (CX, -1.5, 61), (CX, 420, 190), 24), (33.82, (CX, -2.5, 63), (CX, 420, 186), 26)]
CPOS = [(-5.5, 5.2), (-3.0, 6.8), (-1.2, 5.8), (2.0, 7.0), (4.8, 6.2), (6.8, 4.0), (-7.2, 2.5), (1.4, 8.6)]
def seq_d(t, n):
    path(KD, t, 0.012); out = ss(31.3, 32.6, t)
    BG.inputs[0].default_value = tuple(lerp(a, b, out) for a, b in zip(hexc('#5a2a18'), hexc('#ff4a1a'))); BG.inputs[1].default_value = lerp(0.6, 0.8, out)
    SHAFT.data.energy = 40000; SHAFT2.data.energy = 6000; fill(120 * (1 - out))
    for L in TORCH: L.data.energy = 900
    SUN.data.energy = 3.0 * out; SUN.data.color = (1, 0.35, 0.2); SUN.rotation_euler = (R(-73), 0, 0)
    red = ss(33.2, 33.5, t); sun_disc((CX, 420, 190), 34, '#ff2a10', 4 + 6 * red)
    for k, g in enumerate(GIANTS):
        g.put(CX + (-30, 2, 32)[k], (150, 175, 160)[k], 56.5, (10, 0, -12)[k], 1.6); g.pose(t, 0, -150, -150, (20, 0, 0), 10)
    # la main descend par le puits, dépose les deux enfants puis remonte
    hx, hy = CX, 0.3
    if t < 21.6:
        u = max(0, min(1, (t - 19.92) / 1.68)); hz = lerp(19, 2.75, 1 - (1 - u) ** 2); hand_at(hx, hy, hz, 1, -90)
        held(HERO, hx + 0.3, hy - 0.5, hz - 2.75, -15, t); held(BRO, hx - 0.9, hy - 0.5, hz - 2.4, 10, t, 1.3)
    else:
        op = ss(21.6, 21.95, t); hz = 2.75 + 60 * ss(22.0, 23.4, t) ** 1.5; hand_at(hx, hy, hz, 1 - op, -90)
        if t < 23.6: HAND.hide_render = False
        else:
            for o in HPARTS: o.hide_render = True
        turn = ss(22.6, 23.1, t)
        HERO.put(hx + 0.3 - 1.0 * ss(25.5, 26.2, t), hy - 0.5 - 0.6 * ss(25.5, 26.2, t), lerp(0, 0, op), lerp(-15, yawto(-0.7, -0.8, 0.3, 1.7), turn))
        BRO.put(hx - 0.9 + 1.0 * ss(25.5, 26.2, t), hy - 0.5 - 0.7 * ss(25.5, 26.2, t), max(0, 0.35 * (1 - op)), lerp(10, 175, turn))
        up = ss(30.0, 30.6, t); HERO.pose(head=(-30 * up, 0, 0)); BRO.pose(head=(-35 * up, 0, 0), lArm=(-20, 0, 0))
    HERO.expr('w', 'o' if t < 23.6 else 'c'); BRO.expr('w', 'o' if t < 23.6 else 'c')
    if t > 24.9: HERO.expr('w', 'sm'); BRO.expr('n', 'so')
    # la foule : tous les disparus, vivants
    look = ss(22.4, 23.0, t)
    for c, (x, y) in zip(CROWD, CPOS):
        c.put(CX + x, y, 0, lerp(0, yawto(x, y, -0.2, -0.9), look)); c.expr('n', 'sm')
        if t > 30.1: c.pose(head=(-30 * ss(30.1, 30.7, t), 0, 0))
    VICT.put(CX + 3.2, 4.2, 0, yawto(3.2, 4.2, -0.2, -0.9)); VICT.expr('n', 'so')
    w = ss(23.6, 23.9, t) * (1 - ss(25.3, 25.6, t)); VICT.pose(rArm=(-160 * w, 0, -20 * w + 18 * w * math.sin(t * 11)))
    # le vieil homme s'avance, parle, montre le ciel
    if t < 25.7: OLD.put(CX + 0.6, 4.6, 0, yawto(0.6, 4.6, -0.2, -0.9))
    else: walk_to(OLD, t, 25.7, 26.7, (CX + 0.6, 4.6), (CX + 0.3, 1.7), 0.8)
    if t >= 26.7: OLD.put(CX + 0.3, 1.7, 0, -8)
    pt = ss(29.75, 30.2, t)
    if t >= 26.7: OLD.pose(rArm=(-178 * pt, 0, 0), head=(-28 * ss(30.0, 30.5, t), 0, 0))
    OLD.expr('n', 'sm'); say(OLD, t, 27.41, 29.51, 'n', 'sm')
# ---------- F (33,82 → fin) : les géants nous protègent… on joue dehors ----------
KF = [(33.82, (2, -48, 5), (0, 16, 24), 24), (35.4, (10, -30, 22), (0, 12, 22), 24), (36.9, (8, -16, 12), (0, 4, 8), 24),
      (37.9, (4.5, -8, 2.2), (0, 0, 1.1), 26), (39.0, (3.0, -5.5, 1.4), (-0.2, 0.2, 1.1), 28), (40.48, (2.0, -4.3, 1.1), (-0.2, 0.4, 1.9), 24)]
KIDS = [(HERO, (-1.4, 0.4)), (BRO, (1.0, -0.2)), (CROWD[6], (0.1, 1.9))]
def seq_f(t, n):
    path(KF, t, 0.012); sky('#ff7444', 0.6); fill(45)
    SUN.data.energy = 3.6; SUN.data.color = (1, 0.45, 0.25); SUN.rotation_euler = (R(-55), 0, 0)
    sun_disc((0, 420, 294), 34, '#ff2a10', 8)
    for k, g in enumerate(GIANTS):
        g.put((-14, 0, 14)[k], 18 + (1.5, 0, 1.5)[k], 0, (8, 0, -8)[k]); sw = 4 * math.sin(t * 0.9 + k)
        g.pose(t, 0, -172 + sw, -172 - sw, (22, 0, 0), 6)
    # le ballon passe d'un enfant à l'autre
    seg = (t - 33.82) / 0.95; i = int(seg) % 3; u = seg - int(seg)
    a = KIDS[i][1]; b = KIDS[(i + 1) % 3][1]
    BALL.location = (lerp(a[0], b[0], u), lerp(a[1], b[1], u), 0.3 + 1.1 * 4 * u * (1 - u))
    if t > 39.3: BALL.location = (0.75, -0.55, 0.3)
    for k, (c, (x, y)) in enumerate(KIDS):
        hop = 0.12 * abs(math.sin(t * 5 + k)); yb = yawto(x, y, BALL.location[0], BALL.location[1])
        c.put(x, y, hop, lerp(yb, 15 - 10 * k, ss(39.3, 39.7, t)) if t > 39.3 else yb)
        c.pose(lArm=(-40, 0, 25 * math.sin(t * 5 + k)), rArm=(-40, 0, -25 * math.sin(t * 5 + k)), head=(-10, 0, 0)); c.expr('n', 'so')
    for c, (x, y, yaw) in ((CROWD[0], (-4.2, -3.8, 20)), (CROWD[3], (3.8, 4.0, 170)), (VICT, (-3.0, 4.1, 200)), (OLD, (4.8, -3.7, -30))):
        c.put(x, y, 0, yaw); c.expr('n', 'sm'); c.pose(head=(-6, 0, 0))
    w = 0.5 + 0.5 * math.sin(t * 9); VICT.pose(rArm=(-165, 0, -10 + 15 * w), head=(-25, 0, 0))
SEQ = [(0.0, seq_a), (10.75, seq_b), (14.63, seq_c), (19.92, seq_d), (33.82, seq_f), (99, None)]
def setup(n):
    t = n / FPS; i = max(k for k in range(len(SEQ) - 1) if SEQ[k][0] <= t); reset(); SEQ[i][1](t, n)
    for c in ALL:
        if id(c) in SCALE: c.n['root'].scale = (SCALE[id(c)],) * 3
        c.life(t, n)
sc.render.engine = 'BLENDER_EEVEE'; ee = sc.eevee; ee.taa_render_samples = int(os.environ.get('TAA', 8)); ee.use_gtao = True; ee.gtao_distance = 1.0; ee.use_soft_shadows = True
ee.shadow_cube_size = '512'; ee.shadow_cascade_size = '2048'; ee.use_bloom = True; ee.bloom_intensity = 0.06; ee.use_ssr = False
sc.render.resolution_x = W; sc.render.resolution_y = H; sc.render.resolution_percentage = 100
sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'Medium High Contrast'; sc.view_settings.exposure = float(os.environ.get('EXPO', -0.3))
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 92
FR = [int(x) for x in os.environ['ONLY'].split(',')] if os.environ.get('ONLY') else range(n0, n1)
os.makedirs(OUT, exist_ok=True)
for n in FR:
    setup(n); sc.frame_set(n + 1); sc.render.filepath = os.path.join(OUT, f'f{n:05d}.jpg'); bpy.ops.render.render(write_still=True)
print('DONE', n0, n1)
