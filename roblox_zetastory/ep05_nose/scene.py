# ZetaStory ép. 5 – « Le nez rouge » (Blender EEVEE, personnages en blocs, style Roblox : mains sans doigts).
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
HERO = Char('char_BK.glb', 'BK', shirt='#2f6fd6', pants='#2a2f3a', blink=0.3)          # sans le Z
FRIEND = Char('char_M2.glb', 'M2', shirt='#ff8a2b', pants='#2a3b55', blink=1.7)
TEACH = Char('char_W.glb', 'W', shirt='#f4f1e8', pants='#3a3f4a', hair='#6b4a2f', blink=0.9)
MOM = Char('char_W.glb', 'W', shirt='#3fa0c8', pants='#33384a', blink=2.2)
KID = Char('char_E0.glb', 'E0', shirt='#f2c230', pants='#30343c', blink=1.1)
DAD = Char('char_E1.glb', 'E1', shirt='#5a6b7a', pants='#2a2f3a', blink=2.6)
LIL = Char('char_M2.glb', 'M2', shirt='#ff8a2b', pants='#2a3b55', blink=0.5)            # l'ami, petit (flashback)
MAN = Char('char_E2.glb', 'E2', shirt='#26262b', pants='#151518', hair='#6b6b6b', skin='#d8cdbd', blink=3.1)
WALK = [Char('char_E3.glb', 'E3', shirt='#8e5bd9', pants='#22262e', blink=0.2), Char('char_E1.glb', 'E1', shirt='#27b36a', pants='#3b2c22', blink=1.4),
        Char('char_W.glb', 'W', shirt='#ff7ac0', pants='#5a4bb0', hair='#e0b050', blink=2.0)]
ALL = [HERO, FRIEND, TEACH, MOM, KID, DAD, LIL, MAN] + WALK
for c in ALL: roblox(c)
# ---------- décors ----------
box(600, 600, 0.2, '#5fb24c', 0, 0, -0.1)
COLS = ['#f2d8b0', '#cfe3f2', '#f5c9c9', '#d8efc9', '#efe6c9', '#d9d0f0']; ROOFS = ['#8a3b2e', '#3b4a6b', '#5a3a2a', '#2f5a3a']
def house(x, y, w, d, col, roof, yaw=0, door='#6a4128'):
    g = bpy.data.objects.new('h', None); COL.objects.link(g); g.location = (x, y, 0); g.rotation_euler = (0, 0, R(yaw))
    for o in (box(w, d, 3.2, col, 0, 0, 1.6), box(w + 0.6, d + 0.6, 0.5, roof, 0, 0, 3.45), box(w * 0.7, d * 0.7, 1.0, roof, 0, 0, 4.1),
              box(1.0, 0.1, 2.0, door, 0, -d / 2 - 0.06, 1.0)) + tuple(box(1.0, 0.1, 0.9, '#bfe6ff', k * w * 0.3, -d / 2 - 0.06, 2.0, rough=0.2) for k in (-1, 1)):
        o.parent = g
    return g
def tree(x, y, s=1.0, dead=False):
    cyl(0.32 * s, 2.6 * s, '#5a3a26' if dead else '#6b4630', x, y, 1.3 * s, 8)
    if dead:
        for a in (0, 2.1, 4.2):
            b = box(0.12, 0.12, 1.4, '#4a3020', x + 0.4 * math.cos(a), y + 0.4 * math.sin(a), 2.8 * s); b.rotation_euler = (R(35) * math.sin(a), R(35) * math.cos(a), 0)
    else: ball(1.9 * s, '#2f8f3c', x, y, 3.7 * s); ball(1.3 * s, '#3aa64a', x + 0.7, y + 0.4, 4.7 * s)
def road_x(x0, x1, y):       # route le long de x
    box(x1 - x0, 6, 0.04, '#3b3f46', (x0 + x1) / 2, y, 0.02); box(x1 - x0, 1.8, 0.08, '#c9c4b8', (x0 + x1) / 2, y - 4, 0.04); box(x1 - x0, 1.8, 0.08, '#c9c4b8', (x0 + x1) / 2, y + 4, 0.04)
    for xx in range(int(x0), int(x1), 6): box(2.2, 0.22, 0.01, '#f4f1e8', xx, y, 0.045)
def road_y(y0, y1, x):       # route le long de y
    box(6, y1 - y0, 0.04, '#3b3f46', x, (y0 + y1) / 2, 0.02); box(1.8, y1 - y0, 0.08, '#c9c4b8', x - 4, (y0 + y1) / 2, 0.04); box(1.8, y1 - y0, 0.08, '#c9c4b8', x + 4, (y0 + y1) / 2, 0.04)
    for yy in range(int(y0), int(y1), 6): box(0.22, 2.2, 0.01, '#f4f1e8', x, yy, 0.045)
# A : la rue du début (autour de l'origine)
road_x(-40, 40, 0)
for k, x in enumerate(range(-36, 37, 10)):
    house(x, 11, 7, 6, COLS[k % 6], ROOFS[k % 4], 0); house(x + 4, -11, 7, 6, COLS[(k + 3) % 6], ROOFS[(k + 1) % 4], 180)
for x in (-24, -8, 8, 24): tree(x, 6.5); tree(x + 5, -6.5)
# B : l'école (x ≈ 60)
SX = 60
box(26, 18, 0.06, '#b9b3a6', SX + 2, 4, 0.03)
box(24, 8, 9, '#c8553c', SX + 2, 16, 4.5); box(25, 9, 0.6, '#7a2f22', SX + 2, 16, 9.3)
for ix in (-8, -4, 4, 8):
    for z in (2.6, 6.4): box(2.4, 0.2, 2.2, '#bfe6ff', SX + 2 + ix, 11.9, z, emit=0.2, rough=0.2)
box(3.2, 0.3, 3.4, '#5a3a25', SX + 2, 11.95, 1.7); box(10, 0.3, 1.8, '#1c2a5e', SX + 2, 11.8, 7.9); text('SCHOOL', 1.25, '#ffffff', SX + 2, 11.6, 7.9, ext=0.08)
for i in range(6): box(0.08, 0.6, 0.9, '#9aa3b0', SX + 5 + i * 0.5, 4.5, 0.45, metal=0.7, rough=0.3)
box(3.0, 0.08, 0.08, '#9aa3b0', SX + 6.25, 4.5, 0.9, metal=0.7)
cyl(0.08, 7, '#d9d9d9', SX - 7, 9, 3.5, 8); FLAG = box(1.6, 0.04, 1.0, '#e8231c', SX - 6.2, 9, 6.4)
road_x(SX - 30, SX + 30, -8)
for x in (SX - 12, SX + 14): tree(x, 2)
# vélo neuf
BIKE = bpy.data.objects.new('bike', None); COL.objects.link(BIKE)
def bpart(o): o.parent = BIKE; return o
WHEELS = []
for wy in (-0.55, 0.55):
    bpy.ops.mesh.primitive_torus_add(major_radius=0.34, minor_radius=0.045, major_segments=32, minor_segments=8); w = bpy.context.object
    w.location = (0, wy, 0.38); w.rotation_euler = (0, R(90), 0); w.data.materials.append(mat('#141416', rough=0.6)); bpart(w); WHEELS.append(w)
    sp = cyl(0.03, 0.62, '#c9ced6', 0, wy, 0.38, 8, metal=0.8, rough=0.3); sp.rotation_euler = (R(90), 0, 0); bpart(sp)
for (ax, ay, az, l, rx) in ((0, -0.1, 0.62, 1.0, 70), (0, 0.35, 0.62, 0.62, -30), (0, -0.42, 0.62, 0.55, 20)):
    t = cyl(0.035, l, '#e8231c', ax, ay, az, 8, metal=0.5, rough=0.2); t.rotation_euler = (R(rx), 0, 0); bpart(t)
bpart(box(0.12, 0.26, 0.05, '#141416', 0, -0.32, 0.92)); bpart(box(0.55, 0.04, 0.04, '#141416', 0, 0.48, 1.0)); bpart(cyl(0.03, 0.42, '#c9ced6', 0, 0.48, 0.8, 8, metal=0.8))
# C : maison du flashback (x ≈ -60)
FX = -60
house(FX, 8, 8, 6, '#cfe3f2', '#3b4a6b', 0, door='#2f4a7a'); road_x(FX - 20, FX + 20, -4); tree(FX - 7, 4.5)
TAXI = bpy.data.objects.new('taxi', None); COL.objects.link(TAXI); TAXI.location = (FX + 4.5, -3, 0); TAXI.rotation_euler = (0, 0, R(90))
for o in (box(1.9, 4.2, 0.8, '#f2c230', 0, 0, 0.62, bevel=0.14, metal=0.3, rough=0.3), box(1.7, 2.2, 0.6, '#1a1d22', 0, -0.1, 1.25, bevel=0.1, rough=0.1),
          box(0.6, 0.25, 0.22, '#ffffff', 0, -0.1, 1.68, emit=1.5)):
    o.parent = TAXI
for yy in (-1.3, 1.4):
    for xx in (-0.95, 0.95): w_ = cyl(0.36, 0.25, '#16171a', xx, yy, 0.36, 16); w_.rotation_euler = (0, R(90), 0); w_.parent = TAXI
SUIT = box(0.5, 0.18, 0.4, '#6b4630', 0, 0, 0)
FLAMP = light('POINT', (FX + 0.9, 4.2, 2.4), 0, (1, 0.75, 0.45), shadow=False)
# D/E : la rue de la vieille maison (x ≈ 120, route le long de y)
OX = 120
road_y(-20, 28, OX + 5)
box(1.4, 4.0, 0.06, '#8d8577', OX, 28.5, 0.03)                                                  # allée
for k, y in enumerate((-12, 0, 12)):
    house(OX - 8, y, 6, 7, COLS[k % 6], ROOFS[k % 4], -90); house(OX + 18, y, 6, 7, COLS[(k + 2) % 6], ROOFS[(k + 3) % 4], 90)
for y in (6, 14): tree(OX + 2.6, y)
box(1.0, 2.2, 1.25, '#2f7a3a', OX + 2.4, 21.6, 0.62, bevel=0.25)   # haie où le héros se cache
# la vieille maison (façade y = 31, porte en x = OX)
OLD = bpy.data.objects.new('old', None); COL.objects.link(OLD); OLD.location = (OX, 35, 0); OLD.rotation_euler = (0, 0, R(1.5))
for o in (box(10, 8, 6.4, '#5d5246', 0, 0, 3.2, rough=0.9), box(10.8, 8.8, 0.5, '#2a2622', 0, 0, 6.6), box(7.5, 6.5, 2.4, '#2a2622', 0, 0, 7.8),
          box(3.4, 1.6, 0.2, '#4a4036', 0, -4.8, 0.1), box(3.6, 0.3, 0.2, '#3a3028', 0, -4.9, 2.9),
          box(1.6, 0.1, 1.3, '#141416', -3.0, -4.06, 1.8), box(1.6, 0.1, 1.3, '#141416', 3.0, -4.06, 1.8), box(1.6, 0.1, 1.3, '#141416', -3.0, -4.06, 4.6), box(1.6, 0.1, 1.3, '#d9a440', 3.0, -4.06, 4.6, emit=0.8),
          box(1.9, 0.08, 0.16, '#6b5a44', -3.0, -4.12, 1.8), box(1.9, 0.08, 0.16, '#6b5a44', 3.0, -4.12, 4.6), box(1.4, 0.12, 2.4, '#0a0a0c', 0, -4.03, 1.2)):
    o.parent = OLD
for x in (-1.6, 1.6): cyl(0.1, 2.8, '#3a3028', OX + x, 30.3, 1.4, 8)
DOORP = bpy.data.objects.new('dp', None); COL.objects.link(DOORP); DOORP.location = (OX - 0.7, 30.92, 0)
ODOOR = box(1.4, 0.08, 2.4, '#3a2a1e', 0.7, 0, 1.2); ODOOR.parent = DOORP
for x in range(-7, 8):
    if abs(x) > 1: p = box(0.12, 0.08, 1.0 + 0.15 * math.sin(x * 2.3), '#4a4036', OX + x * 0.62, 27.0, 0.5); p.rotation_euler = (0, R(6 * math.sin(x * 1.7)), 0)
tree(OX + 6.5, 29, 1.15, dead=True); tree(OX - 6, 30, 1.0, dead=True)
DLIGHT = light('POINT', (OX, 30.0, 2.7), 0, (1, 0.7, 0.35), shadow=False)
NLIGHT = light('POINT', (OX, 29.6, 1.8), 0, (1, 0.05, 0.05), shadow=False)
# ---------- lumières ----------
SUN = light('SUN', (0, 0, 50), 3.0, (1, 0.95, 0.85)); SUN.rotation_euler = (R(46), 0, R(-28)); SUN.data.angle = R(2)
FILL = light('AREA', (0, 0, 4), 0, (1, 1, 1), 3.0, shadow=False)
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
LIGHTS = [o for o in bpy.data.objects if o.type == 'LIGHT']; LE = {o.name: o.data.energy for o in LIGHTS}
KIDS = 0.85      # le héros et son ami sont des enfants
def reset():
    for c in ALL: c.show(False); c.pose(); c.expr(); nez(c, 0)
    for o in LIGHTS: o.data.energy = LE[o.name]
    BG.inputs[0].default_value = hexc('#8fcfff'); BG.inputs[1].default_value = 1.0
    SUN.data.color = (1, 0.95, 0.85); SUN.rotation_euler = (R(46), 0, R(-28)); SUN.data.energy = 3.0
    BIKE.hide_render = False; SUIT.hide_render = True; DOORP.rotation_euler = (0, 0, 0)
    for o in BIKE.children: o.hide_render = False
def bike_at(x, y, yaw_char, show=True):
    BIKE.location = (x, y, 0); BIKE.rotation_euler = (0, 0, R(yaw_char + 180))
    for o in BIKE.children_recursive: o.hide_render = not show
# ---------- A (0 → 6,66) : la ville, la règle du nez rouge ----------
KA = [(0.0, (3, -40, 24), (2, -3, 1), 26), (1.6, (3, -20, 9), (2.2, -4, 1.0), 28), (2.5, (3, -10, 3.0), (2.2, -4.6, 1.1), 30), (3.3, (2.95, -5.8, 1.32), (2.15, -4.6, 1.15), 30),
      (4.4, (2.9, -5.6, 1.34), (2.15, -4.6, 1.17), 34), (4.95, (2.0, -6.8, 2.7), (5, -1, 1.2), 30), (5.6, (2.9, -6.2, 4.5), (12, 0, 1.2), 28), (6.75, (6, -3.2, 5.5), (20, 1, 1.2), 26)]
def seq_a(t, n):
    path(KA, t, 0.01); bike_at(0, 0, 0, False)
    KID.put(2.0, -4.6, 0, 90, 0.72); MOM.put(3.3, -4.6, 0, -90)
    caught = ss(2.9, 3.4, t); nez(KID, caught)
    KID.pose(head=(8 * caught, 0, 0), lArm=(-20 * caught, 0, 0)); KID.expr('w' if t > 3.0 else 'n', 'c' if t > 3.0 else 'sm')
    MOM.pose(lArm=(0, 0, 22 * ss(3.1, 3.6, t)), rArm=(0, 0, -22 * ss(3.1, 3.6, t)), head=(10, 0, 0)); MOM.expr('a' if t > 3.2 else 'n', 'f' if t > 3.2 else 'sm')
    for c, (x0, x1, y) in zip(WALK, ((-6, 12, 4.6), (20, 6, 4.0), (9, 18, -3.8))):
        walk_to(c, t, 0, 6.7, (x0, y), (x1, y), 1.1); c.expr('n', 'sm')
# ---------- B (6,66 → 16,07) : l'école, le vélo neuf ----------
F = (SX + 1.3, 2.4); T = (SX + 1.8, 4.3); HB = (SX + 3.3, 1.6)
B0, B1 = (SX - 8, -3), (SX + 0.5, 2.5)
def bp(t): u = max(0, min(1, (t - 6.66) / (9.9 - 6.66))); u = u * (2 - u); return (lerp(B0[0], B1[0], u), lerp(B0[1], B1[1], u))
BYAW = yawto(B0[0], B0[1], B1[0], B1[1])
def _k(t, off, lens, tz=0.9):
    x, y = bp(t); return (t, (x + off[0], y + off[1], off[2]), (x, y, tz), lens)
KB = [_k(6.66, (1.5, -3.5, 0.9), 26), _k(8.0, (1.8, -3.2, 1.0), 26), _k(9.4, (2.2, -2.6, 1.2), 28, 1.0),
      (10.3, (SX + 0.0, 0.2, 1.8), (SX + 1.8, 4.3, 1.5), 30), (11.3, (SX + 0.5, 3.3, 1.7), (SX + 1.8, 4.3, 1.66), 36), (12.5, (SX + 0.6, 3.25, 1.7), (SX + 1.8, 4.3, 1.66), 36),
      (12.85, (SX + 2.4, 3.3, 1.45), (F[0], F[1], 1.39), 34), (14.45, (SX + 2.25, 3.2, 1.43), (F[0] + 0.02, F[1] + 0.05, 1.39), 38),
      (15.2, (SX + 1.85, 3.15, 1.42), (F[0] + 0.02, F[1] + 0.1, 1.385), 42), (16.1, (SX + 1.78, 3.1, 1.41), (F[0] + 0.02, F[1] + 0.1, 1.385), 46)]
def seq_b(t, n):
    path(KB, t, 0.012)
    if t < 9.9:
        x, y = bp(t); bike_at(x, y, BYAW); FRIEND.put(x, y, 0.2, BYAW, KIDS); a = 25 * math.sin(t * 9)
        FRIEND.pose(lLeg=-55 + a, rLeg=-55 - a, lArm=(-55, 0, 0), rArm=(-55, 0, 0)); FRIEND.expr('n', 'sm')
    else:
        bike_at(B1[0], B1[1], BYAW); u = ss(9.9, 10.3, t)
        FRIEND.put(lerp(B1[0] + 0.5, F[0], u), lerp(B1[1], F[1], u), 0, lerp(BYAW, yawto(F[0], F[1], T[0], T[1]), u), KIDS); FRIEND.pose(); FRIEND.expr('n', 'sm')
        say(FRIEND, t, 13.23, 14.45)
        if t > 14.5: FRIEND.expr('n', 'sm')
    if t < 8.6: TEACH.put(SX + 2, 11.0, 0, 0)
    elif t < 10.4: walk_to(TEACH, t, 8.6, 10.4, (SX + 2, 11.0), T, 1.0)
    else: TEACH.put(T[0], T[1], 0, yawto(T[0], T[1], F[0], F[1])); lean = ss(14.5, 15.2, t); TEACH.pose(upper=(14 * lean, 0, 0), head=(10 * lean, 0, 0))
    TEACH.expr('n', 'c'); say(TEACH, t, 11.40, 12.5, 'n', 'c')
    if t > 14.5: TEACH.expr('a', 'c')
    HERO.put(HB[0], HB[1], 0, yawto(HB[0], HB[1], F[0], F[1]), KIDS); HERO.expr('n', 'sm' if t < 14.5 else 'c')
# ---------- C (16,07 → 18,27) : il y a deux ans… (souvenir, au crépuscule) ----------
KC = [(16.07, (FX - 3.2, -1.5, 1.3), (FX + 0.2, 2.2, 1.1), 30), (18.3, (FX - 3.6, -0.6, 1.55), (FX + 1.0, 1.0, 1.1), 30)]
def seq_c(t, n):
    path(KC, t, 0.008); bike_at(0, 0, 0, False)
    BG.inputs[0].default_value = hexc('#3a4a72'); BG.inputs[1].default_value = 0.9
    SUN.data.color = (1, 0.6, 0.35); SUN.data.energy = 2.2; SUN.rotation_euler = (R(78), 0, R(-60)); FLAMP.data.energy = 80
    u = walk_to(DAD, t, 16.1, 18.3, (FX, 4.2), (FX + 3.2, -1.6), 0.9); DAD.expr('n', 'c')
    yw = R(DAD.n['root'].rotation_euler.z if False else yawto(FX, 4.2, FX + 3.2, -1.6)); x, y, _ = DAD.n['root'].location
    SUIT.hide_render = False; SUIT.location = (x - 0.6 * math.cos(yw), y - 0.6 * math.sin(yw), 0.42); SUIT.rotation_euler = (0, 0, yw)
    LIL.put(FX - 0.9, 4.0, 0, yawto(FX - 0.9, 4.0, x, y), 0.62); LIL.pose(rArm=(-40 * ss(17.0, 17.6, t), 0, 0)); LIL.expr('s', 'f')
# ---------- D + E (18,27 → fin) : je le suis… la vieille maison (un seul plan-séquence) ----------
KD = [(18.27, (OX + 4.6, 9.6, 1.6), (OX + 1, 16, 1.1), 28), (19.5, (OX + 4.4, 11.2, 1.8), (OX + 1, 19, 1.1), 28), (20.1, (OX + 4.5, 12.5, 2.5), (OX + 0.8, 24, 1.5), 28),
      (21.3, (OX + 6.0, 16.5, 7.0), (OX, 32, 3.2), 26), (22.6, (OX + 4.5, 21.5, 3.4), (OX, 30.5, 1.8), 28), (23.6, (OX + 1.6, 26.0, 2.0), (OX, 30.8, 1.75), 30),
      (24.25, (OX + 1.25, 30.45, 1.5), (OX, 29.75, 1.39), 34), (25.4, (OX + 1.05, 30.4, 1.45), (OX, 29.78, 1.385), 40), (26.2, (OX + 0.85, 30.3, 1.42), (OX, 29.8, 1.385), 44),
      (26.9, (OX + 1.7, 28.4, 2.0), (OX, 30.2, 1.6), 30), (27.9, (OX + 1.45, 28.75, 1.95), (OX, 29.95, 1.76), 34), (29.1, (OX + 1.25, 28.9, 1.92), (OX, 29.95, 1.76), 38),
      (30.2, (OX + 1.05, 29.0, 1.9), (OX, 29.92, 1.755), 42), (31.5, (OX + 0.85, 29.1, 1.88), (OX, 29.92, 1.76), 46), (33.1, (OX + 0.75, 29.15, 1.87), (OX, 29.92, 1.77), 48)]
def seq_d(t, n):
    path(KD, t, 0.012)
    BG.inputs[0].default_value = hexc('#9fb2cc'); BG.inputs[1].default_value = 0.8; SUN.data.color = (1, 0.78, 0.55); SUN.data.energy = 2.2; SUN.rotation_euler = (R(68), 0, R(-35))
    # l'ami pousse son vélo jusqu'à la vieille maison
    if t < 21.4:
        u = walk_to(FRIEND, t, 18.27, 21.0, (OX + 1, 12), (OX + 1, 26.6), 1.0) if t < 21.0 else None
        if t >= 21.0: walk_to(FRIEND, t, 21.0, 21.4, (OX + 1, 26.6), (OX, 27.2), 0.9)
        x, y, _ = FRIEND.n['root'].location; bike_at(x + 0.6, y + 0.3, 180) if t < 21.0 else bike_at(OX + 1.3, 26.8, 170)
        FRIEND.n['lArm'].rotation_euler = (R(-35), 0, 0)
    elif t < 23.8:
        bike_at(OX + 1.3, 26.8, 170); walk_to(FRIEND, t, 22.9, 23.8, (OX, 27.2), (OX, 29.6), 0.9) if t > 22.9 else FRIEND.put(OX, 27.2, 0, 180)
    else:
        bike_at(OX + 1.3, 26.8, 170); FRIEND.put(OX, 29.6, 0, 180)
        hug = ss(26.5, 27.1, t); FRIEND.pose(lArm=(-70 * hug, 0, 25 * hug), rArm=(-70 * hug, 0, -25 * hug), head=(-10 * hug, 0, 0))
    FRIEND.n['root'].scale = (KIDS,) * 3; FRIEND.expr('n', 'sm'); say(FRIEND, t, 24.80, 25.30)
    # le héros se cache derrière les arbres
    if t < 20.6: HERO.put(OX + 3.0, 12.9, 0, 180, KIDS); HERO.pose(upper=(0, -12, 0), head=(0, 0, -15))
    elif t < 21.6: walk_to(HERO, t, 20.6, 21.6, (OX + 3.0, 12.9), (OX + 3.0, 21.0), 1.4)
    else: HERO.put(OX + 3.0, 21.0, 0, 180, KIDS); HERO.pose(upper=(0, -12, 0), head=(0, 0, -15))
    HERO.n['root'].scale = (KIDS,) * 3; HERO.expr('w' if t > 26.5 else 'n', 'c')
    # la porte s'ouvre, l'homme sort
    DOORP.rotation_euler = (0, 0, R(100 * ss(22.7, 23.3, t)))
    if t > 22.7:
        DLIGHT.data.energy = 60; hugm = ss(26.4, 27.0, t)
        MAN.put(OX, lerp(lerp(31.6, 30.55, ss(22.9, 23.8, t)), 30.15, hugm), 0, 0, 1.08)
        look = ss(31.6, 32.1, t)
        MAN.pose(lArm=(-48 * hugm, 0, -38 * hugm), rArm=(-48 * hugm, 0, 38 * hugm), head=(lerp(14 * hugm, -2, look), 0, 18 * hugm + 14 * look), upper=(8 * hugm * (1 - look), 0, 0))
        MAN.expr('a' if t > 31.6 else 'n', 'sm' if t > 26.4 else 'c'); say(MAN, t, 27.92, 29.03, 'n', 'sm')
        red = ss(30.17, 31.06, t); nez(MAN, red); NLIGHT.data.energy = 5 * red; NLIGHT.location = (OX + 0.4, 29.55, 1.7); DLIGHT.data.energy = 60 - 35 * red
SEQ = [(0.0, seq_a), (6.66, seq_b), (16.07, seq_c), (18.27, seq_d), (99, None)]
def setup(n):
    t = n / FPS; i = max(k for k in range(len(SEQ) - 1) if SEQ[k][0] <= t); reset(); SEQ[i][1](t, n)
    for c in ALL: c.life(t, n)
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
