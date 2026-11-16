# Rendu Blender (EEVEE) de toute la scène exportée par export_blender_all.js (personnages en blocs, statue réaliste, jour / nuit).
# usage : ENGINE=EEVEE TAA=16 blender -b -P blender_render_all.py -- DIR OUT n0 n1 [W H]
import bpy, sys, json, os, math, shutil
from mathutils import Quaternion, Vector, Matrix
argv = sys.argv[sys.argv.index('--') + 1:]
D, OUT, n0, n1 = argv[0], argv[1], int(argv[2]), int(argv[3])
W = int(argv[4]) if len(argv) > 4 else 720; H = int(argv[5]) if len(argv) > 5 else 1280
A = json.load(open(os.path.join(D, 'anim.json'))); CH = json.load(open(os.path.join(D, 'chars.json')))
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
P = lambda x, y, z: (x, -z, y)
Qn = lambda w, x, y, z: (w, x, -z, y)                       # nœuds importés (axes convertis)
QC = Quaternion((math.cos(math.pi / 4), math.sin(math.pi / 4), 0, 0))   # caméra / objets créés dans Blender
def imp(f):
    before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=os.path.join(D, f)); return [o for o in bpy.data.objects if o not in before]
imp('scene.glb')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import blender_statue
STATUE = blender_statue.build(os.path.join(D, 'statue.json'))
blender_statue.cutaway(STATUE, [(i + 1, f.get('clip')) for i, f in enumerate(A)])
# personnages
NODES = {}; FACE = {}
fdir = os.path.join(OUT, '_faces'); os.makedirs(fdir, exist_ok=True)
def flipped(src, dst):
    im = bpy.data.images.load(src); w, h = im.size; px = list(im.pixels); rows = [px[r * w * 4:(r + 1) * w * 4] for r in range(h)]
    im.pixels = [v for r in reversed(rows) for v in r]; im.filepath_raw = dst; im.file_format = 'PNG'; im.save(); return dst
for c in CH:
    objs = imp(f'char_{c}.glb')
    for o in objs:
        k = o.name.split('.')[0]
        if k.startswith(c + '_'): NODES[k] = o; o.rotation_mode = 'QUATERNION'
    # matériau du visage -> séquence d'images (une par image de la vidéo)
    fm = None
    for o in objs:
        for s in getattr(o, 'material_slots', []):
            if s.material and s.material.use_nodes and any(n.type == 'TEX_IMAGE' for n in s.material.node_tree.nodes): fm = s.material
    if fm:
        cdir = os.path.join(fdir, c); os.makedirs(cdir, exist_ok=True); FL = {}
        for k in ['neutral', 'smile', 'shock', 'strain', 'disgust', 'dead']: FL[k] = flipped(os.path.join(D, f'face_{c}_{k}.png'), os.path.join(cdir, f'_{k}.png'))
        for i, f in enumerate(A): shutil.copyfile(FL.get(f['face'].get(c, 'neutral'), FL['neutral']), os.path.join(cdir, f'f{i + 1:04d}.png'))
        tn = [n for n in fm.node_tree.nodes if n.type == 'TEX_IMAGE'][0]; img = bpy.data.images.load(os.path.join(cdir, 'f0001.png')); img.source = 'SEQUENCE'; tn.image = img
        tn.image_user.frame_duration = len(A); tn.image_user.frame_start = 1; tn.image_user.use_auto_refresh = True; fm.blend_method = 'HASHED'
    FACE[c] = objs
OBJ = {}
for n in ['phone', 'wphone', 'torch', 'memorial']:
    objs = imp(f'{n}.glb'); OBJ[n] = [o for o in objs if o.parent is None][0]; OBJ[n].rotation_mode = 'QUATERNION'
    OBJ[n + '_all'] = objs
# caméra
cd = bpy.data.cameras.new('CAM'); cam = bpy.data.objects.new('CAM', cd); sc.collection.objects.link(cam); sc.camera = cam; cam.rotation_mode = 'QUATERNION'; cd.sensor_fit = 'VERTICAL'
# monde : ciel physique ; soleil ; lampadaires ; lampe torche ; bougies ; lumière du téléphone
wo = bpy.data.worlds.new('W'); sc.world = wo; wo.use_nodes = True; nt = wo.node_tree; bg = nt.nodes['Background']
sky = nt.nodes.new('ShaderNodeTexSky'); sky.sky_type = 'NISHITA'; sky.sun_elevation = math.radians(16); sky.sun_rotation = math.radians(215); sky.air_density = 1.6; sky.dust_density = 2.5
nt.links.new(sky.outputs[0], bg.inputs[0])
sd = bpy.data.lights.new('SUN', 'SUN'); sd.angle = math.radians(1.5); sd.color = (1.0, 0.9, 0.78); sun = bpy.data.objects.new('SUN', sd); sc.collection.objects.link(sun); sun.rotation_euler = (math.radians(74), 0, math.radians(35))
def light(name, kind, color, size=0.1):
    l = bpy.data.lights.new(name, kind); l.color = color; l.shadow_soft_size = size; o = bpy.data.objects.new(name, l); sc.collection.objects.link(o); return o, l
LAMPS = []
for i, p in enumerate(json.load(open(os.path.join(D, 'lamps.json')))):
    o, l = light(f'LAMP{i}', 'POINT', (1.0, 0.78, 0.48), 0.25); o.location = P(*p); l.use_shadow = False; LAMPS.append(l)
tor, tl = light('TORCH', 'SPOT', (1.0, 0.97, 0.88), 0.03); tl.spot_size = math.radians(34); tl.spot_blend = 0.45; tor.rotation_mode = 'QUATERNION'
can, cl = light('CANDLE', 'POINT', (1.0, 0.62, 0.3), 0.3); cl.use_shadow = False
phl, pl = light('PHL', 'POINT', (0.75, 0.82, 1.0), 0.05); pl.use_shadow = False
mf = A[0]
for i, f in enumerate(A):
    fr = i + 1
    c = f['cam']; cam.location = P(*c[:3]); cam.rotation_quaternion = QC @ Quaternion(c[3:7]); cd.angle = math.radians(c[7])
    for prop in ('location', 'rotation_quaternion'): cam.keyframe_insert(prop, frame=fr)
    cd.keyframe_insert('lens', frame=fr)
    for k, o in NODES.items():
        px = k.split('_')[0]; vis = px in f['ch']
        if vis and k in f['ch'][px]:
            v = f['ch'][px][k]; o.location = P(*v[:3]); o.rotation_quaternion = Qn(*v[3:7]); o.keyframe_insert('location', frame=fr); o.keyframe_insert('rotation_quaternion', frame=fr)
    for px, objs in FACE.items():
        vis = px in f['ch']
        for o in objs: o.hide_render = not vis; o.keyframe_insert('hide_render', frame=fr)
    for n in ['phone', 'wphone', 'torch']:
        v = f.get(n); o = OBJ[n]
        if v: o.location = P(*v[:3]); o.rotation_quaternion = Qn(*v[3:7]); o.keyframe_insert('location', frame=fr); o.keyframe_insert('rotation_quaternion', frame=fr)
        for x in OBJ[n + '_all']: x.hide_render = not v; x.keyframe_insert('hide_render', frame=fr)
    for x in OBJ['memorial_all']: x.hide_render = not f['memorial']; x.keyframe_insert('hide_render', frame=fr)
    # jour / nuit
    nt_ = f['night']; dusk = max(0, 1 - abs(nt_ - 0.45) / 0.25) * 0.8
    sd.energy = 2.6 * (1 - nt_) ** 1.5 + 0.02; sd.keyframe_insert('energy', frame=fr)
    sky.sun_elevation = math.radians(16 - 22 * nt_); sky.keyframe_insert('sun_elevation', frame=fr)
    bg.inputs[1].default_value = 0.55 * (1 - nt_) + 0.03; bg.inputs[1].keyframe_insert('default_value', frame=fr)
    for l in LAMPS: l.energy = 450 * max(0, min(1, (nt_ - 0.35) / 0.2)); l.keyframe_insert('energy', frame=fr)
    if f['torch']: v = f['torch']; tor.location = P(*v[:3]); tor.rotation_quaternion = QC @ Quaternion(v[3:7]) @ Quaternion((0, 0, 1, 0)); tl.energy = 160 * min(1, v[7] / 40)
    else: tl.energy = 0
    tor.keyframe_insert('location', frame=fr); tor.keyframe_insert('rotation_quaternion', frame=fr); tl.keyframe_insert('energy', frame=fr)
    mem = OBJ['memorial']; can.location = (-1.0, -1.68, 0.3); cl.energy = 60 * (1 + 0.15 * math.sin(fr * 2.3)) if f['memorial'] else 0; cl.keyframe_insert('energy', frame=fr)
    if f['phone']: v = f['phone']; phl.location = (v[0], -v[2], v[1] + 0.25)
    pl.energy = 5 * f['phoneL']; phl.keyframe_insert('location', frame=fr); pl.keyframe_insert('energy', frame=fr)
for a in bpy.data.actions:
    for fc in a.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'CONSTANT'
for ng in [bpy.data.worlds['W'].node_tree]:
    if ng.animation_data and ng.animation_data.action:
        for fc in ng.animation_data.action.fcurves:
            for kp in fc.keyframe_points: kp.interpolation = 'CONSTANT'
sc.render.engine = 'BLENDER_EEVEE'; ee = sc.eevee; ee.taa_render_samples = int(os.environ.get('TAA', 16)); ee.use_gtao = True; ee.gtao_distance = 1.2; ee.use_soft_shadows = True
ee.shadow_cube_size = '512'; ee.shadow_cascade_size = '2048'; ee.use_ssr = False; ee.use_bloom = True; ee.bloom_intensity = 0.04
sc.render.resolution_x = W; sc.render.resolution_y = H; sc.render.resolution_percentage = 100
sc.view_settings.view_transform = 'Standard'; sc.view_settings.exposure = float(os.environ.get('EXPO', -0.7))
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 92
FR = [int(x) for x in os.environ['ONLY'].split(',')] if os.environ.get('ONLY') else range(n0, n1)
for n in FR:
    sc.frame_set(n + 1); sc.render.filepath = os.path.join(OUT, f'f{n:05d}.jpg'); bpy.ops.render.render(write_still=True)
print('DONE', n0, n1)
