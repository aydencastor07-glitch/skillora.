# Rendu Blender (Cycles) d'une scène exportée de three.js (jeu2/js/*.js : window.exportScene / exportBlocky / bake).
# usage : blender -b -P blender_render.py -- DIR OUT_FRAMES n0 n1 [W H SAMPLES]
#   DIR : scene.glb, blocky.glb, phone.glb, face_*.png, anim.json      OUT_FRAMES : dossier des images f00000.png
import bpy, sys, json, os, math, shutil
from mathutils import Quaternion
argv = sys.argv[sys.argv.index('--') + 1:]
D, OUT, n0, n1 = argv[0], argv[1], int(argv[2]), int(argv[3])
W = int(argv[4]) if len(argv) > 4 else 1080; H = int(argv[5]) if len(argv) > 5 else 1920; SPP = int(argv[6]) if len(argv) > 6 else 48
A = json.load(open(os.path.join(D, 'anim.json')))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
def imp(f):
    before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=os.path.join(D, f)); return [o for o in bpy.data.objects if o not in before]
env = imp('scene.glb'); bk = imp('blocky.glb'); ph = imp('phone.glb')
O = {o.name.split('.')[0]: o for o in bk}
PHONE = [o for o in ph if o.parent is None][0]
# three (y en haut) -> blender (z en haut)
P = lambda x, y, z: (x, -z, y)
Qc = lambda w, x, y, z: (w, x, -z, y)
for o in list(O.values()) + [PHONE]: o.rotation_mode = 'QUATERNION'
# visage : séquence d'images (une par image de la vidéo)
fdir = os.path.join(OUT, '_face'); os.makedirs(fdir, exist_ok=True)
face_mat = None
for o in bk:
    for s in getattr(o, 'material_slots', []):
        m = s.material
        if m and m.use_nodes and any(n.type == 'TEX_IMAGE' for n in m.node_tree.nodes): face_mat = m
FL = {}
for k in ['neutral', 'smile', 'shock', 'strain']:
    im = bpy.data.images.load(os.path.join(D, f'face_{k}.png')); w, h = im.size; px = list(im.pixels); rows = [px[r * w * 4:(r + 1) * w * 4] for r in range(h)]
    im.pixels = [v for r in reversed(rows) for v in r]; dst = os.path.join(fdir, f'_{k}.png'); im.filepath_raw = dst; im.file_format = 'PNG'; im.save(); FL[k] = dst
for i, f in enumerate(A): shutil.copyfile(FL[f['face'] or 'neutral'], os.path.join(fdir, f'face{i + 1:04d}.png'))
if face_mat:
    tn = [n for n in face_mat.node_tree.nodes if n.type == 'TEX_IMAGE'][0]
    img = bpy.data.images.load(os.path.join(fdir, 'face0001.png')); img.source = 'SEQUENCE'; tn.image = img
    tn.image_user.frame_duration = len(A); tn.image_user.frame_start = 1; tn.image_user.frame_offset = 0; tn.image_user.use_auto_refresh = True
    face_mat.blend_method = 'HASHED'
# caméra
cd = bpy.data.cameras.new('CAM'); cam = bpy.data.objects.new('CAM', cd); sc.collection.objects.link(cam); sc.camera = cam; cam.rotation_mode = 'QUATERNION'; cd.sensor_fit = 'VERTICAL'
# lumière : ciel physique + soleil bas (fin de journée), petite lumière du téléphone
wo = bpy.data.worlds.new('W'); sc.world = wo; wo.use_nodes = True; nt = wo.node_tree; bg = nt.nodes['Background']
sky = nt.nodes.new('ShaderNodeTexSky'); sky.sky_type = 'NISHITA'; sky.sun_elevation = math.radians(16); sky.sun_rotation = math.radians(215); sky.air_density = 1.6; sky.dust_density = 2.5
nt.links.new(sky.outputs[0], bg.inputs[0]); bg.inputs[1].default_value = 0.55
sd = bpy.data.lights.new('SUN', 'SUN'); sd.energy = 3.2; sd.angle = math.radians(2.5); sd.color = (1.0, 0.9, 0.78); sun = bpy.data.objects.new('SUN', sd); sc.collection.objects.link(sun)
sun.rotation_euler = (math.radians(74), 0, math.radians(215 - 180))
pl = bpy.data.lights.new('PHL', 'POINT'); pl.energy = 0; pl.color = (0.75, 0.82, 1.0); pl.shadow_soft_size = 0.05; phl = bpy.data.objects.new('PHL', pl); sc.collection.objects.link(phl)
# images clés
for i, f in enumerate(A):
    fr = i + 1
    c = f['cam']; cam.location = P(*c[:3]); cam.rotation_quaternion = Quaternion((math.cos(math.pi / 4), math.sin(math.pi / 4), 0, 0)) @ Quaternion(c[3:7]); cd.angle = math.radians(c[7])
    cd.clip_start = 0.05
    if f.get('clip') is not None:   # vue en coupe : on coupe tout ce qui est devant le plan z = clip (three)
        cd.clip_start = max(0.05, (c[2] - f['clip']) * 0.97)
    cam.keyframe_insert('location', frame=fr); cam.keyframe_insert('rotation_quaternion', frame=fr); cd.keyframe_insert('lens', frame=fr); cd.keyframe_insert('clip_start', frame=fr)
    if f['bk']:
        for k, v in f['bk'].items():
            o = O.get(k)
            if not o: continue
            o.location = P(*v[:3]); o.rotation_quaternion = Qc(*v[3:7]); o.keyframe_insert('location', frame=fr); o.keyframe_insert('rotation_quaternion', frame=fr)
    root = O['BK_root']; vis = f['bk'] is not None
    for o in [root] + list(root.children_recursive): o.hide_render = not vis; o.keyframe_insert('hide_render', frame=fr)
    if f['phone']:
        p = f['phone']; PHONE.location = P(*p[:3]); PHONE.rotation_quaternion = Qc(*p[3:7]); PHONE.hide_render = False
        phl.location = (PHONE.location[0], PHONE.location[1], PHONE.location[2] + 0.25); pl.energy = 12 if f.get('clip') is not None else 0
    else: PHONE.hide_render = True; pl.energy = 0
    for o in [PHONE] + list(PHONE.children_recursive): o.hide_render = PHONE.hide_render; o.keyframe_insert('hide_render', frame=fr)
    PHONE.keyframe_insert('location', frame=fr); PHONE.keyframe_insert('rotation_quaternion', frame=fr); phl.keyframe_insert('location', frame=fr); pl.keyframe_insert('energy', frame=fr)
# toutes les clés en « constant » (une image = un état exact)
for a in bpy.data.actions:
    for fc in a.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'CONSTANT'
# rendu
ENGINE = os.environ.get('ENGINE', 'CYCLES')
if ENGINE == 'EEVEE':
    sc.render.engine = 'BLENDER_EEVEE'; ee = sc.eevee; ee.taa_render_samples = int(os.environ.get('TAA', 16)); ee.use_gtao = True; ee.gtao_distance = 1.2; ee.use_soft_shadows = True; ee.shadow_cube_size = '1024'; ee.shadow_cascade_size = '2048'; ee.use_bloom = False; ee.use_ssr = True
    sd.angle = math.radians(1.5)
else: sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'; sc.cycles.samples = SPP; sc.cycles.use_denoising = False; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
try: pass
except Exception: pass
sc.cycles.max_bounces = 4; sc.render.resolution_x = W; sc.render.resolution_y = H; sc.render.resolution_percentage = 100
sc.view_settings.view_transform = os.environ.get('VT', 'Standard')
sc.view_settings.look = 'None'; sc.view_settings.exposure = float(os.environ.get('EXPO', -0.45)); sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 92
for n in range(n0, n1):
    sc.frame_set(n + 1); sc.render.filepath = os.path.join(OUT, f'f{n:05d}.jpg'); bpy.ops.render.render(write_still=True)
print('DONE', n0, n1)
