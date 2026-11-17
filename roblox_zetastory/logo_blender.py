import bpy, sys, math, os
from mathutils import Vector
a = sys.argv[sys.argv.index('--') + 1:]; GLB, FACE, OUT = a[0], a[1], a[2]
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=GLB)
O = bpy.data.objects
# visage souriant (image retournée comme dans le pipeline vidéo)
im = bpy.data.images.load(FACE); w, h = im.size; px = list(im.pixels); rows = [px[r*w*4:(r+1)*w*4] for r in range(h)]
im.pixels = [v for r in reversed(rows) for v in r]
for m in bpy.data.materials:
    if m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE': n.image = im; m.blend_method = 'HASHED'
for m in bpy.data.materials:
    if m.name == 'Material_0' and m.use_nodes:   # sweat rouge vif
        b = [n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]; b.inputs['Base Color'].default_value = (0.85, 0.08, 0.06, 1); b.inputs['Roughness'].default_value = 0.6
    if m.name == 'Material_4' and m.use_nodes:   # pantalon bleu nuit
        b = [n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]; b.inputs['Base Color'].default_value = (0.03, 0.05, 0.18, 1)
tc = bpy.data.curves.new('Z', 'FONT'); tc.body = 'Z'; tc.extrude = 0.02; tc.align_x = 'CENTER'; tc.align_y = 'CENTER'; tc.size = 0.42
try: tc.font = bpy.data.fonts.load('/home/user/skillora./temu/fonts/ArchivoBlack-Regular.ttf')
except Exception as e: print('font', e)
zt = bpy.data.objects.new('Ztxt', tc); sc.collection.objects.link(zt); zt.parent = O['BK_upper']; zt.location = (0, -0.2, 0.36); zt.rotation_euler = (math.radians(90), 0, 0)
zm = bpy.data.materials.new('Zm'); zm.use_nodes = True; zb = zm.node_tree.nodes['Principled BSDF']; zb.inputs['Base Color'].default_value = (1, 0.78, 0.05, 1); zb.inputs['Roughness'].default_value = 0.35; tc.materials.append(zm)
def rot(name, x=0, y=0, z=0):
    o = O[name]; o.rotation_mode = 'XYZ'; o.rotation_euler = (math.radians(x), math.radians(y), math.radians(z))
rot('BK_root', z=-14); rot('BK_lArm', y=-148, x=-8); rot('BK_rArm', y=12, x=10); rot('BK_head', x=-4, y=-6, z=6)
cd = bpy.data.cameras.new('C'); cam = bpy.data.objects.new('C', cd); sc.collection.objects.link(cam); sc.camera = cam
cd.lens = 70; cam.location = (0.1, -4.4, 1.7)
tgt = Vector((0.15, 0, 1.62)); cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
def L(kind, loc, energy, size=1.0, color=(1, 1, 1)):
    l = bpy.data.lights.new(kind + str(len(O)), kind); l.energy = energy; l.color = color
    if kind == 'AREA': l.size = size
    o = bpy.data.objects.new(l.name, l); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector((0, 0, 1.4)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return o
L('AREA', (-2.0, -3.0, 3.0), 650, 2.5, (1, 0.96, 0.9)); L('AREA', (2.6, -1.5, 2.2), 260, 2.0, (0.75, 0.85, 1)); L('AREA', (0.5, 2.5, 3.0), 500, 1.5, (1, 0.75, 0.45))
wo = bpy.data.worlds.new('W'); sc.world = wo; wo.use_nodes = True; wo.node_tree.nodes['Background'].inputs[0].default_value = (0.55, 0.6, 0.7, 1); wo.node_tree.nodes['Background'].inputs[1].default_value = 0.6
sc.render.engine = 'BLENDER_EEVEE'; sc.eevee.taa_render_samples = 64; sc.eevee.use_gtao = True; sc.eevee.use_soft_shadows = True
sc.render.film_transparent = True; sc.render.resolution_x = sc.render.resolution_y = 1400
sc.view_settings.view_transform = 'Standard'; sc.view_settings.exposure = -0.55; sc.view_settings.look = 'Medium High Contrast'; sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
sc.render.filepath = OUT; bpy.ops.render.render(write_still=True)
