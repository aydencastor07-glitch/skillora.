# ZetaStory ép. 3 – « In my family, we take one photo every year on my birthday » (Blender EEVEE, personnages en blocs).
# Un seul décor : le jardin de la maison (jour / nuit). Les « photos » : cadre blanc collé à la caméra. usage : blender -b -P scene.py -- CHARS_DIR OUT n0 n1 [W H]
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
DAD = Char('char_E1.glb', 'E1', shirt='#4a7a3a', pants='#3b2c22')
SIS = Char('char_W.glb', 'W', shirt='#ff7ac0', pants='#5a4bb0', hair='#e0b050')
STR = Char('char_E0.glb', 'E0', shirt='#141518', pants='#0c0d10', hair='#0a0a0c', skin='#d9d9d2')           # l'inconnu
IMP = Char('char_E0.glb', 'E0', shirt='#e8231c', pants='#1c2a5e', hair='#0a0a0c', skin='#b9c4d6')           # l'inconnu avec MES habits
zi = text('Z', 0.42, '#ffcc11', 0, -0.2, 0.36, rot=(90, 0, 0), ext=0.02); zi.parent = IMP.n['upper']; IMP.objs.append(zi)
ALL = [HERO, MOM, DAD, SIS, STR, IMP]
# ---------- décor : jardin, maison au fond (y = 16), arbres, clôture, table + gâteau ----------
box(120, 120, 0.2, '#58b04a', 0, 0, -0.1)
box(16, 8, 6, '#e9dcc0', 0, 18, 3); box(17, 9, 0.5, '#8a3b2e', 0, 18, 6.25); box(13, 7, 2.2, '#9c4636', 0, 18, 7.4)
box(1.4, 0.2, 2.4, '#5a3823', 0, 13.95, 1.2)
WIN = [box(1.8, 0.2, 1.6, '#bfe6ff', x, 13.95, 3.6 if k else 1.9, rough=0.2) for x in (-5, -2.6, 2.6, 5) for k in (0, 1)]
for x in range(-20, 21, 2): box(0.3, 0.15, 1.3, '#f1ece1', x, 24, 0.65)
box(41, 0.1, 0.15, '#f1ece1', 0, 24, 1.0)
for sx in (-1, 1):
    for y in range(-8, 25, 2): box(0.15, 0.3, 1.3, '#f1ece1', sx * 20, y, 0.65)
TREES = [(-9, 11), (9, 12), (-13, 4), (13, 5), (-6, 20), (6.5, 21)]
for (x, y) in TREES: cyl(0.45, 3.2, '#6b4630', x, y, 1.6, 8); ball(2.7, '#2f8f3c', x, y, 4.8); ball(1.9, '#3aa64a', x + 0.9, y + 0.5, 6.2)
box(1.8, 1.0, 0.08, '#b98654', 0, -2.4, 0.8); [box(0.08, 0.08, 0.8, '#6f5a40', sx * 0.8, -2.4 + sy * 0.4, 0.4) for sx in (-1, 1) for sy in (-1, 1)]
cyl(0.32, 0.22, '#fff4e0', 0, -2.4, 0.95); cyl(0.33, 0.06, '#ff7ac0', 0, -2.4, 1.07)
CANDLES = [ball(0.035, '#ffd060', 0.18 * math.cos(a), -2.4 + 0.18 * math.sin(a), 1.2, emit=12) for a in [i * math.pi / 3 for i in range(6)]]
for a in [i * math.pi / 3 for i in range(6)]: cyl(0.012, 0.1, '#ffffff', 0.18 * math.cos(a), -2.4 + 0.18 * math.sin(a), 1.14, 6)
BULBS = [ball(0.09, ['#ffd060', '#ff7a7a', '#7ac8ff', '#9aff9a'][i % 4], -7 + i * 1.0, 3.2, 3.2 - 0.5 * math.sin(i / 14 * math.pi), emit=6) for i in range(15)]
BIN = cyl(0.4, 0.9, '#3a4046', 6.5, -2.0, 0.45, 12); CAMOBJ = box(0.32, 0.16, 0.22, '#17181c', 0, 0, 0); cl = cyl(0.07, 0.1, '#2a2c33', 0, -0.1, 0, 12); cl.rotation_euler = (R(90), 0, 0); cl.parent = CAMOBJ
PHOTO = box(0.3, 0.012, 0.36, '#f4f1ea', 0, 0, 0, emit=0.6)
SUN = light('SUN', (0, 0, 50), 3.0, (1, 0.95, 0.85)); SUN.rotation_euler = (R(48), 0, R(-30)); SUN.data.angle = R(2)
NH = light('POINT', (0.4, -2.9, 1.9), 150, (1, 0.85, 0.7), shadow=False)
NL = light('AREA', (0, -3.5, 4.5), 1400, (1, 0.8, 0.55), 6, tgt=(0, 0, 1)); NF = light('POINT', (0, -6, 2.5), 250, (0.6, 0.7, 1.0), shadow=False)
# ---------- caméra, monde, cadre photo ----------
cd = bpy.data.cameras.new('C'); cam = bpy.data.objects.new('C', cd); COL.objects.link(cam); sc.camera = cam; cd.sensor_fit = 'VERTICAL'; cd.clip_start = 0.02; cd.clip_end = 600
wo = bpy.data.worlds.new('W'); sc.world = wo; wo.use_nodes = True; BG = wo.node_tree.nodes['Background']
def world(col, s=1.0): BG.inputs[0].default_value = hexc(col); BG.inputs[1].default_value = s
def camset(p, t, lens=35):
    cam.location = p; cam.rotation_euler = (Vector(t) - Vector(p)).to_track_quat('-Z', 'Y').to_euler(); cd.lens = lens
def camlerp(p0, t0, p1, t1, u, lens=35, lens1=None):
    camset(tuple(lerp(a, b, u) for a, b in zip(p0, p1)), tuple(lerp(a, b, u) for a, b in zip(t0, t1)), lerp(lens, lens1 if lens1 else lens, u))
# cadre blanc de la photo : collé devant la caméra (objectif 35), légende dans la marge du bas
FRAME = bpy.data.objects.new('F', None); COL.objects.link(FRAME); FRAME.parent = cam; FRAME.location = (0, 0, -1.0)
hh = 12 / 35; hw = hh * 9 / 16; wm = mat('#f4f1ea', emit=1.0)
def fbox(w, h, x, y):
    bpy.ops.mesh.primitive_plane_add(size=1); o = bpy.context.object; o.scale = (w, h, 1); o.location = (x, y, 0); o.data.materials.append(wm); o.parent = FRAME; return o
FPARTS = [fbox(2 * hw, 0.05, 0, 0.265), fbox(2 * hw, 0.12, 0, -0.23), fbox(0.03, 0.6, -hw + 0.015, 0), fbox(0.03, 0.6, hw - 0.015, 0),
          fbox(2 * hw, hh, 0, 0.29 + hh / 2), fbox(2 * hw, hh, 0, -0.29 - hh / 2)]
FPARTS[4].data.materials.clear(); FPARTS[4].data.materials.append(mat('#0c0c0e')); FPARTS[5].data.materials.clear(); FPARTS[5].data.materials.append(mat('#0c0c0e'))
CAPc = bpy.data.curves.new('cap', 'FONT'); CAPc.size = 0.045; CAPc.align_x = 'CENTER'; CAPc.align_y = 'CENTER'; CAPc.font = bpy.data.fonts.load('/home/user/skillora./temu/fonts/PermanentMarker.ttf')
CAP = bpy.data.objects.new('cap', CAPc); COL.objects.link(CAP); CAP.parent = FRAME; CAP.location = (0, -0.23, 0.002); CAPc.materials.append(mat('#1a1a1e'))
def photo(caption=''):
    for o in FPARTS: o.hide_render = False
    CAP.hide_render = not caption; CAPc.body = caption or ' '; cd.lens = 35
LIGHTS = [o for o in bpy.data.objects if o.type == 'LIGHT']
def reset():
    for c in ALL: c.show(False); c.pose()
    for o in FPARTS + [CAP, CAMOBJ, PHOTO]: o.hide_render = True
    for l in LIGHTS: l.data.energy = 0
    for b in BULBS + CANDLES: b.hide_render = True
def day(k=1.0): world('#7fc4ff', 1.0 * k); SUN.data.energy = 3.0 * k
def night(flash=0.0):
    world('#0a1230', 0.6 + 8 * flash); SUN.data.energy = 0.15 + 6 * flash; NL.data.energy = 1400; NF.data.energy = 250
    for b in BULBS + CANDLES: b.hide_render = False
# la famille qui pose (face à la caméra, -y) ; hs = taille du héros (âge)
def family(hs=1.0, hero=True, smile=True):
    MOM.put(-1.15, 0, 0, 8); DAD.put(1.15, 0, 0, -8, 1.08); SIS.put(0.5, -0.45, 0, 0, 0.55 * min(1, hs + 0.25))
    MOM.pose(rArm=(0, 0, 14)); DAD.pose(lArm=(0, 0, -14))
    for c in (MOM, DAD, SIS): c.face('smile' if smile else 'neutral')
    if hs < 0.6: SIS.show(False)
    if hero: HERO.put(-0.25, -0.35, 0, 0, hs); HERO.face('smile')
PC = ((0, -7.2, 1.5), (0, 0, 1.25))    # appareil photo : position, cible
def stranger(x, y, yaw=0, smile=True, sc_=1.12):
    STR.put(x, y, 0, yaw, sc_); STR.pose(); STR.face('smile' if smile else 'neutral')
# ---------- les plans ----------
def s_intro(t, u):       # « In my family, we take one photo every year on my birthday. »
    day(); family(); HERO.pose(rArm=(-150, 0, -20 - 12 * math.sin(t * 8)))
    camlerp((-7, -11, 4.5), (0, 0, 1.2), (-2.5, -6.5, 1.8), (0, 0, 1.3), ss(0, 1, u), 28)
def s_extra(t, u):       # « And every year, there's one extra person in it. »
    day(); family(); stranger(3.4, 2.2); photo('my birthday')
    camlerp(PC[0], PC[1], (1.6, -3.2, 1.6), (3.0, 2.2, 1.6), ss(0.3, 1, u))
def s_nobody(t, u):      # « Nobody remembers who it is. Nobody remembers taking the picture with them. »
    day(); MOM.put(-0.55, -3.6, 0, 12); DAD.put(0.6, -3.6, 0, -12, 1.08); sh = 30 * math.sin(t * 7)
    MOM.pose(lArm=(-55, 0, 10), rArm=(-55, 0, -10), head=(18, 0, sh if u < 0.5 else 0)); DAD.pose(lArm=(0, -25, 0), rArm=(0, 25, 0), head=(10, 0, sh if u >= 0.5 else 0)); MOM.face('neutral'); DAD.face('neutral')
    PHOTO.hide_render = False; PHOTO.location = (-0.55, -4.22, 1.12); PHOTO.rotation_euler = (R(-35), 0, R(12))
    camlerp((-0.2, -7.2, 1.7), (0, -3.6, 1.45), (0.3, -6.6, 1.75), (0, -3.6, 1.5), u, 34)
def s_five(t, u):        # « On my fifth birthday, he was standing far away, behind the trees. »
    day(); family(0.5); stranger(-8.1, 10.6, 20); photo('5'); camlerp(PC[0], PC[1], (-2.6, -1.5, 1.7), (-8.0, 10.6, 1.9), ss(0.35, 1, u))
def s_ten(t, u):         # « On my tenth, he was at the end of the garden. »
    day(); family(0.72); stranger(4.2, 7.5, -10); photo('10'); camlerp(PC[0], PC[1], (1.2, -3.5, 1.7), (4.0, 7.5, 1.8), ss(0.3, 1, u))
def s_fifteen(t, u):     # « On my fifteenth, he was right behind my dad. »
    day(); family(0.95); stranger(1.75, 0.75, -10); photo('15'); camlerp(PC[0], PC[1], (0.9, -3.4, 1.8), (1.6, 0.6, 1.9), ss(0.35, 1, u))
def s_smiling(t, u):     # « Smiling. »
    day(); family(0.95); stranger(1.75, 0.75, -10); camlerp((1.3, -1.6, 2.0), (1.75, 0.75, 1.9), (1.4, -1.1, 2.0), (1.75, 0.75, 1.9), u, 45)
def s_glitch(t, u):      # « My parents say it's a glitch in the camera. They threw the camera away. »
    day(); DAD.put(5.0, -2.2, 0, -70, 1.08); MOM.put(3.6, -1.6, 0, -40); MOM.pose(lArm=(0, -30, 0), rArm=(0, 30, 0)); MOM.face('neutral'); DAD.face('neutral'); CAMOBJ.hide_render = False
    v = ss(0.55, 0.8, u); DAD.pose(rArm=(-70 - 40 * math.sin(v * math.pi), 0, 0), lArm=(-60 * (1 - v), 0, 0))
    CAMOBJ.location = (lerp(5.45, 6.5, v), lerp(-2.55, -2.0, v), lerp(1.25, 0.75, v) + 0.9 * math.sin(v * math.pi)); CAMOBJ.rotation_euler = (v * 6, 0, R(-70))
    if v >= 1: CAMOBJ.hide_render = True
    camlerp((3.2, -6.5, 1.7), (5.2, -2.2, 1.2), (4.2, -6.0, 1.5), (5.8, -2.1, 1.0), u, 30)
def s_still(t, u):       # « The next year, he was still there. »
    day(); family(1.0); stranger(0.45, 0.55, 0); STR.pose(rArm=(-35, 0, 25)); photo(' '); camlerp(PC[0], PC[1], (0.2, -4.2, 1.7), (0.4, 0.4, 1.8), ss(0.2, 1, u))
def s_tonight(t, u):     # « Tonight is my sixteenth birthday. »
    night(); HERO.put(0, -3.3, 0, 180); HERO.pose(head=(18, 0, 0)); HERO.face('smile'); NH.data.energy = 150; NH.location = (0.5, -2.2, 1.8)
    camlerp((1.6, -1.2, 1.9), (0, -2.9, 1.3), (0.8, -1.1, 1.7), (0, -3.0, 1.35), u, 32)
def s_closer(t, u):      # « Mom said: "Everyone, get closer!" »
    night(); g = ss(0.3, 1, u); MOM.put(lerp(-2.6, -1.15, g), 0, 0, 8); MOM.pose(rArm=(-140, 0, -25 - 18 * math.sin(t * 9))); MOM.face('smile')
    DAD.put(lerp(2.8, 1.15, g), 0, 0, -8, 1.08); DAD.walk(t, 0.8) if g < 1 else None; SIS.put(lerp(2.2, 0.5, g), lerp(-2.2, -0.45, g), 0, 0, 0.55); SIS.walk(t, 1.5); HERO.put(-0.25, -0.35, 0, 0); HERO.face('smile')
    camlerp((-1.6, -6.4, 1.6), (0, 0, 1.3), (-0.6, -6.9, 1.5), (0, 0, 1.3), u, 30)
def s_flash(t, u):       # « The flash went off. »
    f = max(0, 1 - abs(u - 0.32) / 0.14); night(f); family(); camlerp(PC[0], PC[1], (0, -6.9, 1.5), PC[1], u, 35)
def s_look(t, u):        # « I looked at the photo. »
    night(); HERO.put(0, -4.6, 0, 0); HERO.pose(lArm=(-60, 0, 14), rArm=(-60, 0, -14), head=(24 * ss(0, 0.5, u), 0, 0)); HERO.face('smile' if u < 0.6 else 'neutral')
    PHOTO.hide_render = False; PHOTO.location = (0, -5.22, 1.14); PHOTO.rotation_euler = (R(-40), 0, 0)
    camlerp((0.9, -7.2, 1.7), (0, -4.8, 1.4), (0.5, -6.8, 1.75), (0, -4.8, 1.45), u, 34)
def fam_night():
    MOM.put(-1.15, 0, 0, 8); DAD.put(1.15, 0, 0, -8, 1.08); SIS.put(0.5, -0.45, 0, 0, 0.55); MOM.pose(rArm=(0, 0, 14)); DAD.pose(lArm=(0, 0, -14))
    for c in (MOM, DAD, SIS): c.face('smile')
    IMP.put(-0.25, -0.35, 0, 0); IMP.face('smile')
def s_mdsis(t, u):       # « Mom. Dad. My little sister. »
    night(0.12); fam_night(); IMP.show(False); photo('16')
    tg = [(-1.15, 0, 1.55), (1.15, 0, 1.65), (0.5, -0.45, 0.85)]; i = 0 if T < 34.0 else 1 if T < 34.55 else 2; x, y, z = tg[i]; camset((x * 0.9, -3.1, z + 0.05), (x, y, z), 35)
def s_him(t, u):         # « And him. Standing exactly where I was standing. Wearing my clothes. »
    night(0.12); fam_night(); photo('16')
    if u < 0.2: camset((-0.2, -3.0, 1.6), (-0.25, -0.35, 1.5), 35)
    elif u < 0.68: camlerp(PC[0], PC[1], (-0.1, -4.6, 1.5), (-0.25, -0.35, 1.3), ss(0.2, 0.68, u))
    else: camlerp((-0.1, -4.6, 1.5), (-0.25, -0.35, 1.3), (-0.2, -3.7, 1.45), (-0.25, -0.35, 1.25), ss(0.68, 1, u))
def s_wasnt(t, u):       # « I wasn't in the picture. »
    night(); HERO.put(0, -4.6, 0, 0); HERO.pose(lArm=(-60, 0, 14), rArm=(-60, 0, -14), head=(24 - 30 * ss(0.5, 1, u), 0, 0)); HERO.face('shock')
    PHOTO.hide_render = False; PHOTO.location = (0, -5.22, 1.14); PHOTO.rotation_euler = (R(-40), 0, 0); camlerp((0.3, -6.6, 1.6), (0, -4.6, 1.55), (0.15, -6.1, 1.62), (0, -4.6, 1.6), u, 40)
def hug(t):
    IMP.put(0, 0, 0, 0); IMP.face('smile'); MOM.put(-0.62, 0.05, 0, -75); MOM.pose(lArm=(-80, 0, 20), rArm=(-80, 0, -20), head=(10, 0, 0), upper=(8, 0, 0))
    DAD.put(0.68, 0.05, 0, 75, 1.08); DAD.pose(lArm=(-75, 0, 20), rArm=(-75, 0, -20), head=(12, 0, 0)); SIS.put(0.1, -0.5, 0, 180, 0.55); SIS.pose(lArm=(-100, 0, 20), rArm=(-100, 0, -20))
    MOM.face('strain'); DAD.face('smile'); SIS.face('smile')
def s_hug(t, u):         # « I looked up. My family was hugging him. »
    night(); hug(t); HERO.put(0.5, -4.6, 0, 180); HERO.pose(lArm=(0, -20, 0), rArm=(0, 20, 0)); HERO.face('shock')
    camlerp((1.3, -6.6, 1.9), (0, 0, 1.3), (1.0, -6.0, 1.8), (0, 0, 1.35), u, 30)
def s_happy(t, u):       # « My mom was crying: "Happy birthday, sweetheart." »
    night(); hug(t); camlerp((-0.9, -2.2, 1.6), (-0.3, 0, 1.55), (-0.5, -1.8, 1.62), (-0.2, 0, 1.6), u, 40)
def s_scream(t, u):      # « I screamed: "Mom, that's not me!" »
    night(); HERO.put(0.5, -4.6, 0, 180); a = 8 * math.sin(t * 20); HERO.pose(lArm=(-70 + a, 0, 40), rArm=(-70 - a, 0, -40), upper=(10, 0, 0)); HERO.face('shock' if int(t * 6) % 2 else 'strain')
    hug(t); NH.data.energy = 50; NH.location = (0.2, -3.0, 1.9); camlerp((0.3, -2.2, 1.6), (0.5, -4.6, 1.45), (0.35, -2.6, 1.62), (0.5, -4.6, 1.5), u, 36)
def s_turn(t, u):        # « She turned around. She looked right at me… »
    night(); hug(t); v = ss(0.1, 0.55, u); MOM.put(-0.62 - 0.25 * v, 0.05 - 0.45 * v, 0, lerp(-75, 0, v)); MOM.pose(head=(0, 0, 0)); MOM.face('neutral')
    camlerp((0.3, -3.6, 1.6), (-0.6, -0.2, 1.5), (-0.3, -2.6, 1.6), (-0.85, -0.4, 1.55), u, 36, 44)
def s_sorry(t, u):       # « and said: "Sorry… do we know you?" »
    night(); hug(t); MOM.put(-0.87, -0.4, 0, 0); MOM.pose(head=(0, 0, 8 * ss(0.3, 0.6, u))); MOM.face('neutral'); IMP.pose(head=(0, 0, 25)); IMP.face('smile')
    camlerp((-0.3, -2.6, 1.6), (-0.85, -0.4, 1.55), (-0.45, -2.0, 1.6), (-0.6, -0.3, 1.55), u, 44)
SHOTS = [(0.0, s_intro), (4.05, s_extra), (7.2, s_nobody), (11.1, s_five), (15.15, s_ten), (17.55, s_fifteen), (20.62, s_smiling), (21.3, s_glitch), (24.95, s_still), (27.05, s_tonight),
         (29.1, s_closer), (31.1, s_flash), (32.42, s_look), (33.47, s_mdsis), (35.5, s_him), (40.3, s_wasnt), (41.62, s_hug), (44.02, s_happy), (47.05, s_scream), (49.82, s_turn), (52.2, s_sorry), (54.55, None)]
T = 0.0
def setup(n):
    global T
    T = t = n / FPS; i = max(k for k in range(len(SHOTS) - 1) if SHOTS[k][0] <= t); t0, f = SHOTS[i]; t1 = SHOTS[i + 1][0]
    reset(); f(t, (t - t0) / (t1 - t0))
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
