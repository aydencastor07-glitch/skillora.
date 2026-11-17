# ZetaStory ép. 4 – « Les deux boutons » (Blender EEVEE, personnages en blocs). NOUVEAU STYLE :
#   - caméra qui bouge tout le temps, trajectoires continues (spline) : 4 grands plans-séquences, presque pas de coupes ;
#   - visages vivants : clignement des yeux, respiration, et la BOUCHE suit la voix quand le héros parle (env.json).
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
def hat(c, col1, col2):       # chapeau d'anniversaire (cône à rayures)
    h = cyl(0.2, 0.42, col1, 0, 0, 0.66, 20, r2=0.0, emit=0.15); h.parent = c.n['head']; c.objs.append(h)
    for k, z in enumerate((0.5, 0.58, 0.66)):
        rr = 0.2 * (1 - (z - 0.45) / 0.42); st = cyl(rr + 0.008, 0.035, col2, 0, 0, z, 20, emit=0.3); st.parent = c.n['head']; c.objs.append(st)
    p = ball(0.06, col2, 0, 0, 0.88, emit=0.4); p.parent = c.n['head']; c.objs.append(p)
HERO = Char('char_BK.glb', 'BK', shirt='#e8231c', pants='#1c2a5e', blink=0.3)
zt = text('Z', 0.42, '#ffcc11', 0, -0.2, 0.36, rot=(90, 0, 0), ext=0.02); zt.parent = HERO.n['upper']; HERO.objs.append(zt)
HATH = len(HERO.objs); hat(HERO, '#2f7bff', '#ffd23a'); HERO_HAT = HERO.objs[HATH:]
FRIEND = Char('char_M2.glb', 'M2', shirt='#27b36a', pants='#3b2c22', blink=1.7)
FH = len(FRIEND.objs); hat(FRIEND, '#ff4fa3', '#7ee8ff'); FRIEND_HAT = FRIEND.objs[FH:]
FMOM = Char('char_W.glb', 'W', shirt='#f2c230', pants='#33384a', hair='#3a2618', blink=0.9)
FDAD = Char('char_E1.glb', 'E1', shirt='#15161b', pants='#2a3b55', blink=2.4)
ALL = [HERO, FRIEND, FMOM, FDAD]
# ---------- la ville ----------
box(400, 400, 0.2, '#5fb24c', 0, 0, -0.1)
box(400, 7, 0.04, '#3b3f46', 0, -22, 0.02); box(7, 400, 0.04, '#3b3f46', 22, 0, 0.02); box(400, 7, 0.04, '#3b3f46', 0, -6, 0.021) if False else None
for x in range(-60, 61, 6): box(2.2, 0.25, 0.01, '#f4f1e8', x, -22, 0.045)
box(400, 2.0, 0.08, '#c9c4b8', 0, -17.6, 0.04); box(400, 2.0, 0.08, '#c9c4b8', 0, -26.4, 0.04)
def house(x, y, w, d, col, roof, yaw=0):
    b = box(w, d, 3.2, col, x, y, 1.6); r = box(w + 0.6, d + 0.6, 0.5, roof, x, y, 3.45); r2 = box(w * 0.7, d * 0.7, 1.0, roof, x, y, 4.1)
    for o in (b, r, r2): o.rotation_euler = (0, 0, R(yaw))
    dx, dy = -math.sin(R(yaw)) * (d / 2 + 0.06), -math.cos(R(yaw)) * (d / 2 + 0.06)
    dr = box(1.0, 0.1, 2.0, '#6a4128', x + dx, y + dy, 1.0); dr.rotation_euler = (0, 0, R(yaw))
    for k in (-1, 1):
        wi = box(1.0, 0.1, 0.9, '#bfe6ff', x + dx + math.cos(R(yaw)) * k * w * 0.3, y + dy - math.sin(R(yaw)) * k * w * 0.3, 2.0, rough=0.2); wi.rotation_euler = (0, 0, R(yaw))
COLS = ['#f2d8b0', '#cfe3f2', '#f5c9c9', '#d8efc9', '#efe6c9', '#d9d0f0']; ROOFS = ['#8a3b2e', '#3b4a6b', '#5a3a2a', '#2f5a3a']
for x in range(-52, 53, 13):
    for y, yaw in ((-33, 180), (-12 - 21, 180)):
        pass
for k, x in enumerate(range(-52, 53, 11)):
    if 11 < abs(x) and x < 28: house(x, -10.5 - (k % 2), 7, 6, COLS[k % 6], ROOFS[k % 4], 0)
    house(x + 3, -33.5, 7, 6, COLS[(k + 2) % 6], ROOFS[(k + 1) % 4], 180)
TREES = [(-12, -17), (12, -16.6), (-25, -16.8), (26, -27.6), (-8, -28), (5, -28.2), (-36, -27.8), (16, -38), (-18, -40), (34, -12), (-34, -3), (-16, 8), (14, 10), (0, 16)]
for (x, y) in TREES: cyl(0.35, 2.6, '#6b4630', x, y, 1.3, 8); ball(2.0, '#2f8f3c', x, y, 3.8); ball(1.4, '#3aa64a', x + 0.7, y + 0.4, 4.9)
# ---------- le bâtiment des boutons : hall (y -14 → -4) + salle (y -4 → 2.6) ----------
WALL = '#d6dde6'; TRIM = '#2f7bff'
box(14, 17, 0.1, '#b9c2cc', 0, -5.5, 0.05, rough=0.35)                                       # sol intérieur
box(5.9, 0.4, 5.0, WALL, -4.05, -14, 2.5); box(5.9, 0.4, 5.0, WALL, 4.05, -14, 2.5); box(2.2, 0.4, 2.2, WALL, 0, -14, 3.9)   # façade, porte 2,2 x 2,8
box(0.4, 17, 5.0, WALL, -7, -5.5, 2.5); box(0.4, 17, 5.0, WALL, 7, -5.5, 2.5); box(14, 0.4, 5.0, WALL, 0, 3.0, 2.5)
for z in (0.25, 4.75): box(14.2, 0.45, 0.25, TRIM, 0, -14.02, z, emit=0.4)
ROOF = box(14.4, 17.4, 0.3, '#c9ced6', 0, -5.5, 5.1)
SIGN = text('13', 1.6, '#ffd23a', 0, -14.35, 3.6, emit=3.0, ext=0.12); text('BUTTON DAY', 0.34, '#ffffff', 0, -14.25, 2.95, emit=1.5, ext=0.03)
# salle : mur avant (porte 1,6 x 2,5), plafond
box(3.2, 0.2, 3.6, WALL, -2.4, -4, 1.8); box(3.2, 0.2, 3.6, WALL, 2.4, -4, 1.8); box(1.6, 0.2, 1.1, WALL, 0, -4, 3.05)
box(0.2, 6.6, 3.6, '#e2e6ec', -4, -0.7, 1.8); box(0.2, 6.6, 3.6, '#e2e6ec', 4, -0.7, 1.8); box(8, 0.2, 3.6, '#e2e6ec', 0, 2.6, 1.8)
CEIL = box(8.2, 6.8, 0.15, '#ffffff', 0, -0.7, 3.65)
for x in (-3.85, 3.85): box(0.05, 6.4, 0.06, '#7ee8ff', x, -0.7, 3.3, emit=4)
DOOR = box(1.62, 0.07, 2.52, '#c9d3e0', 0, -4.14, 1.26, metal=0.6, rough=0.3); DLAMP_M, DLAMP = emat('#3dff7a', 3); box(0.5, 0.05, 0.12, '', 0, -4.16, 2.75, m=DLAMP_M)
DSIGN = text('BUTTON ROOM', 0.22, '#1c2a5e', 0, -4.13, 3.15, ext=0.02)
# hall : banc, plantes, affiche
box(2.6, 0.6, 0.12, '#b98654', 2.7, -4.55, 0.5); [box(0.1, 0.5, 0.45, '#5a5f66', 2.7 + sx * 1.15, -4.55, 0.22) for sx in (-1, 1)]
for x in (-5.8, 5.8): cyl(0.35, 0.6, '#e9e2d4', x, -13.2, 0.3, 16); ball(0.55, '#3aa64a', x, -13.2, 0.95)
box(1.4, 0.05, 1.9, '#ffffff', -3.0, -4.13, 1.7); text('YOUR\nCHOICE\nIS\nSECRET', 0.2, '#e8231c', -3.0, -4.17, 1.7, ext=0.01)
# console + boutons
box(1.7, 0.75, 0.98, '#2b2f37', 0, 0, 0.49, bevel=0.04, metal=0.5, rough=0.35)
box(1.75, 0.8, 0.05, '#1a1d22', 0, 0, 1.0, metal=0.4)
REDM, REDE = emat('#ff2a2a', 1.5); BLUEM, BLUEE = emat('#2f7bff', 1.5)
for x, mm in ((-0.42, REDM), (0.42, BLUEM)):
    cyl(0.26, 0.05, '#9aa3b0', x, 0, 1.04, 32, metal=0.8, rough=0.25); cyl(0.2, 0.12, '', x, 0, 1.1, 32, m=mm)
text('$1M', 0.12, '#ffffff', -0.42, -0.385, 0.75, ext=0.005, emit=1); text('$10M', 0.12, '#ffffff', 0.42, -0.385, 0.75, ext=0.005, emit=1)
text('YOU', 0.08, '#ff6a6a', -0.42, -0.385, 0.6, ext=0.005, emit=1); text('BEST FRIEND', 0.07, '#7eb0ff', 0.42, -0.385, 0.6, ext=0.005, emit=1)
# écran
box(2.9, 0.1, 1.6, '#0d0f14', 0, 2.47, 2.25, rough=0.2); SCRM, SCRE = emat('#05070c', 0.0); box(2.7, 0.02, 1.42, '', 0, 2.41, 2.25, m=SCRM)
STXT_M, STXT_E = emat('#ffffff', 2.5); RTXT_M, RTXT_E = emat('#ff2020', 4.0)
S1c = bpy.data.curves.new('s1', 'FONT'); S1c.size = 0.17; S1c.align_x = 'CENTER'; S1c.align_y = 'CENTER'; S1c.font = FONT; S1c.materials.append(STXT_M)
S1 = bpy.data.objects.new('s1', S1c); COL.objects.link(S1); S1.location = (0, 2.39, 2.38); S1.rotation_euler = (R(90), 0, 0)
S2c = bpy.data.curves.new('s2', 'FONT'); S2c.size = 0.19; S2c.align_x = 'CENTER'; S2c.align_y = 'CENTER'; S2c.font = FONT; S2c.materials.append(RTXT_M)
S2 = bpy.data.objects.new('s2', S2c); COL.objects.link(S2); S2.location = (0, 2.39, 2.1); S2.rotation_euler = (R(90), 0, 0)
# hologrammes d'argent au-dessus des boutons
MONM, MONE = emat('#3dff7a', 3.0)
M1 = text('$1,000,000', 0.13, '', -0.42, 0, 1.6, m=MONM, ext=0.01); M2 = text('$10,000,000', 0.13, '', 0.42, 0, 1.6, m=MONM, ext=0.01)
# ---------- la nouvelle maison de l'ami (x ≈ 42) ----------
MX, MY = 42, 9
box(15, 8, 5.4, '#fbf7ef', MX, MY, 2.7); box(16, 9, 0.4, '#3b3f46', MX, MY, 5.6); box(8, 6, 3.0, '#fbf7ef', MX, MY + 0.5, 7.2); box(9, 7, 0.4, '#3b3f46', MX, MY + 0.5, 8.9)
for x in (-5.5, -2.8, 2.8, 5.5):
    for z in (1.6, 4.0): box(1.6, 0.1, 1.3, '#9fd6ff', MX + x, MY - 4.02, z, rough=0.1, emit=0.15)
box(2.4, 0.12, 3.0, '#c79a3a', MX, MY - 4.05, 1.5, metal=0.6, rough=0.3)
for x in (-1.9, 1.9): cyl(0.22, 5.2, '#ffffff', MX + x, MY - 4.6, 2.6, 16)
box(5, 1.6, 0.25, '#ffffff', MX, MY - 4.9, 5.3)
cyl(1.4, 0.5, '#d9d9d9', MX - 5.5, MY - 8.0, 0.25, 32); cyl(1.2, 0.1, '#6fc8ff', MX - 5.5, MY - 8.0, 0.48, 32, rough=0.05); cyl(0.2, 1.2, '#d9d9d9', MX - 5.5, MY - 8.0, 0.9, 12)
box(6, 4.6, 0.03, '#d4cfc4', MX, MY - 7.5, 0.03)
box(0.12, 0.12, 1.6, '#6b4630', MX + 5.0, MY - 9.0, 0.8); box(1.6, 0.06, 0.9, '#e8231c', MX + 5.0, MY - 9.05, 1.65); text('SOLD', 0.36, '#ffffff', MX + 5.0, MY - 9.1, 1.65, ext=0.01)
TR = box(2.6, 6.0, 2.8, '#f4f1e8', MX + 9.5, MY - 13.0, 1.75); box(2.6, 1.8, 2.0, '#2f7bff', MX + 9.5, MY - 16.8, 1.35); text('MOVING', 0.5, '#2f7bff', MX + 8.18, MY - 13.0, 2.0, rot=(90, 0, -90), ext=0.01)
for yy in (-11.5, -15.5):
    for xx in (-1.3, 1.3): w_ = cyl(0.4, 0.3, '#16171a', MX + 9.5 + xx, MY + yy, 0.4, 16); w_.rotation_euler = (0, R(90), 0)
CAR = box(2.0, 4.2, 0.8, '#e8231c', MX + 7.0, MY - 7.0, 0.6, bevel=0.15, metal=0.4, rough=0.25); box(1.7, 2.0, 0.55, '#1a1d22', MX + 7.0, MY - 7.2, 1.2, bevel=0.12, rough=0.1)
for yy in (-1.3, 1.4):
    for xx in (-1.0, 1.0): w_ = cyl(0.36, 0.25, '#16171a', MX + 7.0 + xx, MY - 7.0 + yy, 0.36, 16); w_.rotation_euler = (0, R(90), 0)
# ---------- lumières ----------
SUN = light('SUN', (0, 0, 50), 3.2, (1, 0.95, 0.85)); SUN.rotation_euler = (R(46), 0, R(-28)); SUN.data.angle = R(2)
LROOM = light('AREA', (0, -0.8, 3.45), 260, (1, 1, 1), 4.0, tgt=(0, -0.8, 0)); LHALL = light('AREA', (0, -9, 4.7), 520, (1, 0.97, 0.92), 7.0, tgt=(0, -9, 0))
LRED = light('POINT', (-0.55, -0.45, 1.35), 0, (1, 0.12, 0.1), shadow=False); LBLUE = light('POINT', (0.55, -0.45, 1.35), 0, (0.15, 0.35, 1), shadow=False)
LSCR = light('AREA', (0, 2.2, 2.25), 0, (1, 0.15, 0.12), 2.5, tgt=(0, -1, 1.6))
KRED = light('POINT', (-1.3, -0.2, 1.9), 0, (1, 0.1, 0.08), shadow=False); KBLUE = light('POINT', (1.3, -0.2, 1.9), 0, (0.12, 0.3, 1), shadow=False)
# ---------- caméra : trajectoires continues ----------
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
LIGHTS = [o for o in bpy.data.objects if o.type == 'LIGHT']; LE = {o.name: o.data.energy for o in LIGHTS}
def reset():
    BG.inputs[1].default_value = 1.0
    for c in ALL: c.show(False); c.pose(); c.expr()
    for o in HERO_HAT + FRIEND_HAT: o.hide_render = True
    for o in LIGHTS: o.data.energy = LE[o.name]
    for o in (LRED, LBLUE, LSCR, KRED, KBLUE): o.data.energy = 0
    ROOF.hide_render = CEIL.hide_render = False; DOOR.location.x = 0; DLAMP_M.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = hexc('#3dff7a')
    REDE.default_value = 1.5; BLUEE.default_value = 1.5; M1.hide_render = M2.hide_render = True; S1c.body = 'PRESS ONE'; S2c.body = ' '; SCRE.default_value = 0
def door(open_):  DOOR.location.x = 1.75 * open_
# ---------- plan-séquence A (0 → 11,76) : la ville → le bâtiment → la porte → les deux boutons → vue du dessus ----------
KA = [(0.0, (-26, -60, 30), (0, -14, 3), 26), (1.5, (-10, -36, 11), (0, -14, 3.2), 28), (2.55, (-0.6, -21, 2.2), (0, -14, 1.8), 30),
      (3.25, (0, -13.2, 1.65), (0, -4, 1.4), 30), (3.95, (0, -4.7, 1.6), (0, 0, 1.1), 28), (4.8, (-1.3, -2.6, 1.6), (-0.3, 0, 1.2), 30),
      (5.9, (-2.6, -2.4, 1.8), (-0.42, 0, 1.45), 30), (6.5, (-1.0, -2.2, 1.6), (-0.1, 0, 1.35), 30), (7.5, (1.0, -2.2, 1.6), (0.3, 0, 1.4), 30),
      (8.6, (2.6, -2.4, 1.8), (0.42, 0, 1.5), 30), (9.4, (1.4, -2.4, 2.8), (0, -0.2, 1.0), 28), (10.6, (0.5, -2.6, 6.5), (0, -1.0, 0), 26), (11.8, (0.2, -2.0, 8.0), (0, -1.2, 0), 26)]
def seq_a(t, n):
    path(KA, t, 0.01 if t > 3.5 else 0.0); BG.inputs[1].default_value = lerp(1.0, 0.45, ss(2.8, 3.8, t))
    door(1 - ss(9.7, 10.5, t))
    if t > 10.3: DLAMP_M.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = hexc('#ff2020')
    if t > 9.1: ROOF.hide_render = CEIL.hide_render = True
    REDE.default_value = 1.5 + 5 * ss(3.9, 4.3, t) * (1 - ss(6.3, 6.7, t)); BLUEE.default_value = 1.5 + 5 * ss(6.4, 6.8, t) * (1 - ss(9.0, 9.5, t))
    LRED.data.energy = 60 * ss(3.9, 4.3, t) * (1 - ss(6.3, 6.7, t)); LBLUE.data.energy = 60 * ss(6.4, 6.8, t) * (1 - ss(9.0, 9.5, t))
    pop(M1, t, 5.1); pop(M2, t, 8.2)
    if t > 7.9: M1.hide_render = True
    if t > 9.6: M2.hide_render = True
    billboard(M1); billboard(M2)
# ---------- plan-séquence B (11,76 → 16,41) : le hall, l'anniversaire de l'ami ----------
KB = [(11.76, (5.5, -10.5, 2.3), (2.2, -4.8, 1.2), 28), (12.9, (3.8, -10.4, 2.0), (1.0, -4.4, 1.3), 28), (13.9, (2.2, -9.2, 1.8), (0.2, -4.3, 1.45), 28),
      (14.9, (-1.5, -8.6, 1.8), (0.6, -5.2, 1.5), 28), (15.7, (-3.4, -7.4, 1.75), (0.2, -5.8, 1.55), 30), (16.45, (-3.8, -7.0, 1.7), (-1.2, -6.6, 1.6), 34)]
def seq_b(t, n):
    path(KB, t, 0.012); BG.inputs[1].default_value = 0.45
    for o in FRIEND_HAT: o.hide_render = False
    door(ss(12.55, 12.95, t) * (1 - ss(13.25, 13.6, t)) + ss(13.85, 14.2, t))
    # l'ami : assis → se lève → entre dans la salle → ressort tête basse → passe devant le héros sans le regarder
    if t < 12.25: FRIEND.put(1.75, -4.55, 0, 0); FRIEND.sit(); FRIEND.expr('n', 'c')
    elif t < 13.45:
        u = walk_to(FRIEND, t, 12.25, 13.45, (1.75, -5.0), (0, -3.2), 1.3) if t > 12.6 else None
        if t <= 12.6: FRIEND.put(1.75, -4.85, 0, -40); FRIEND.pose(); FRIEND.expr('n', 'c')
        FRIEND.expr('w', 'c')
    elif t < 13.95: FRIEND.show(False)
    else:
        turn = ss(14.9, 15.3, t)
        if t < 14.7: walk_to(FRIEND, t, 13.95, 14.7, (0, -3.4), (0, -5.0), 0.9, head=(22, 0, 0))
        else: walk_to(FRIEND, t, 14.7, 16.6, (0, -5.0), (-1.8, -7.4), 0.9, head=(22, 0, -40 * turn))
        FRIEND.expr('s', 'f')
    # le héros : assis, sourit ; se lève et fait coucou quand l'ami ressort
    if t < 14.55: HERO.put(3.1, -4.55, 0, -10 if t < 13.4 else -30); HERO.sit(head=(0, 0, 0)); HERO.expr('n', 'sm')
    else:
        HERO.put(3.0, -4.95, 0, -40); w = ss(14.8, 15.0, t) * (1 - ss(15.9, 16.1, t))
        HERO.pose(rArm=(-150 * w, 0, -(20 + 14 * math.sin(t * 10)) * w), head=(0, 0, 0)); HERO.expr('n', 'sm' if t < 15.6 else 'c')
        if t > 15.8: HERO.expr('s', 'f')
# ---------- plan-séquence C (16,41 → 19,32) : deux jours plus tard, la nouvelle maison ----------
KC = [(16.41, (MX - 1.6, MY - 17.5, 1.6), (MX - 0.6, MY - 9, 1.9), 30), (17.6, (MX - 4.8, MY - 17.8, 3.6), (MX, MY - 6, 2.8), 30),
      (18.6, (MX - 7.5, MY - 18.5, 7.5), (MX, MY - 3, 3.0), 30), (19.4, (MX - 8.5, MY - 19.5, 9.5), (MX, MY - 2, 3.0), 30)]
def seq_c(t, n):
    path(KC, t, 0.015)
    HERO.put(MX - 1.0, MY - 15.6, 0, 172); HERO.pose(head=(-6, 0, 0)); HERO.expr('s', 'c')
    FRIEND.put(MX + 0.2, MY - 9.4, 0, -8); FRIEND.pose(rArm=(-150, 0, -(20 + 14 * math.sin(t * 9)))); FRIEND.expr('n', 'sm')
    FDAD.put(MX + 1.6, MY - 8.9, 0, -10, 1.08); FDAD.pose(lArm=(-40, 0, -10), rArm=(-40, 0, 10)); FDAD.expr('n', 'sm')
    FMOM.put(MX - 1.3, MY - 8.9, 0, 10); FMOM.pose(rArm=(-130, 0, -30)); FMOM.expr('n', 'sm')
# ---------- plan-séquence D (19,32 → fin) : mon tour → l'écran → le visage → les deux mains → la question ----------
HY = -0.78       # position du héros devant la console (il regarde vers +y : yaw 180)
KD = [(19.32, (0.7, -9.6, 2.0), (0, -4.6, 1.6), 30), (20.3, (0.5, -7.4, 1.95), (0, -3.0, 1.5), 30), (21.2, (1.0, -2.6, 2.5), (0, 0.4, 1.1), 30),
      (22.2, (0.9, -2.2, 2.45), (0, 1.5, 1.9), 30), (23.3, (0.5, -1.2, 2.3), (0, 2.4, 2.2), 30), (24.75, (0.12, -0.35, 2.2), (0, 2.4, 2.22), 24),
      (25.15, (0.15, 0.85, 1.75), (0, HY, 1.65), 34), (26.35, (0.25, 0.75, 1.72), (0, HY, 1.66), 40),
      (27.3, (1.25, 0.55, 1.35), (0.42, -0.05, 1.12), 32), (28.6, (1.05, 0.75, 1.5), (0.3, HY, 1.35), 30), (29.75, (0.6, 0.85, 1.55), (0.1, HY, 1.4), 30),
      (30.6, (-1.25, 0.55, 1.35), (-0.42, -0.05, 1.12), 32), (31.6, (-0.6, 0.8, 1.6), (0, HY, 1.62), 36), (32.6, (0.0, 0.85, 1.68), (0, HY, 1.66), 38),
      (34.2, (0.0, 0.4, 1.72), (0, HY, 1.72), 38)]
def seq_d(t, n):
    path(KD, t, 0.012); BG.inputs[1].default_value = 0.45
    for o in HERO_HAT: o.hide_render = False
    door(ss(19.45, 19.9, t))
    if t < 21.35: walk_to(HERO, t, 19.35, 21.35, (0, -6.0), (0, HY), 1.25); HERO.expr('n', 'sm')
    else:
        HERO.put(0, HY, 0, 180); HERO.expr('n', 'c')
        rb = ss(26.5, 27.1, t) * (1 - ss(29.7, 30.1, t))                # main droite au-dessus du bouton BLEU
        lr = ss(29.85, 30.4, t)                                             # main gauche au-dessus du bouton ROUGE
        hv = 3 * math.sin(t * 7)
        look = ss(32.55, 32.95, t)
        HERO.pose(rArm=(-72 * rb + hv * rb, 0, 6 * rb), lArm=(-72 * lr - hv * lr, 0, -6 * lr),
                  head=(lerp(lerp(-4, -22, ss(26.4, 27.0, t) * (1 - ss(31.0, 31.6, t))), 6, look), 0, 0))
        if t >= 24.85: HERO.expr('w' if t < 26.35 else 'a' if t < 29.8 else 's' if t < 32.55 else 'w', 'c', talk=True)
    # écran : curseur, puis le texte tapé mot par mot
    SCRE.default_value = 0.6 * ss(21.6, 22.0, t)
    if t > 21.75:
        S1c.body = '_' if int(t * 4) % 2 else ' '
        a = 'YOUR FRIEND'; b = 'PRESSED RED.'
        if t > 23.3: S1c.body = a[:max(0, min(len(a), int((t - 23.3) / 0.62 * len(a)) + 1))]
        if t > 23.95: S2c.body = b[:max(0, min(len(b), int((t - 23.95) / 0.65 * len(b)) + 1))]
        LSCR.data.energy = 140 * ss(24.0, 24.6, t)
    REDE.default_value = 1.5 + 4 * ss(29.9, 30.4, t); BLUEE.default_value = 1.5 + 4 * ss(26.5, 27.0, t) * (1 - ss(29.7, 30.1, t)) + 2 * ss(32.4, 32.9, t)
    LBLUE.data.energy = 70 * ss(26.5, 27.0, t) * (1 - ss(29.7, 30.1, t)); LRED.data.energy = 70 * ss(29.9, 30.4, t) * (1 - ss(32.4, 32.9, t))
    KBLUE.data.energy = 90 * ss(26.6, 27.2, t) * (1 - ss(29.7, 30.2, t)) + 260 * ss(31.6, 32.4, t); KRED.data.energy = 260 * ss(30.0, 30.8, t)
    LROOM.data.energy = 260 * (1 - 0.55 * ss(24.0, 25.0, t))
SEQ = [(0.0, seq_a), (11.76, seq_b), (16.41, seq_c), (19.32, seq_d), (99, None)]
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
