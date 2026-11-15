# Statue de stégosaure « réaliste » construite dans Blender à partir de statue.json (exporté par jeu2/js/dino.js : window.statueSpec).
# Corps + pattes d'un seul bloc (modificateur Skin -> Subdivision -> Displace), plaques dorsales épaisses et biseautées,
# pointes de la queue, griffes, yeux ; peinture verte usée avec écailles et plis en relief (matériau procédural).
# La fente du dos est un vrai trou (Booléen), noir à l'intérieur. Vue en coupe : Booléen « coupe » activé image par image.
import bpy, bmesh, math, json, os
from mathutils import Vector, Euler, Matrix

P = lambda x, y, z: Vector((x, -z, y))   # three (y en haut) -> blender (z en haut)


def mat_skin(name, base=(0.085, 0.115, 0.055), dark=(0.03, 0.042, 0.022), light=(0.16, 0.19, 0.1), scale=38.0, bump=0.35, belly_=False):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; N = nt.nodes; L = nt.links
    bsdf = N['Principled BSDF']; bsdf.inputs['Roughness'].default_value = 0.62
    tc = N.new('ShaderNodeTexCoord'); mp = N.new('ShaderNodeMapping'); L.new(tc.outputs['Object'], mp.inputs['Vector'])
    vor = N.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = scale; vor.feature = 'DISTANCE_TO_EDGE'; L.new(mp.outputs[0], vor.inputs['Vector'])
    noi = N.new('ShaderNodeTexNoise'); noi.inputs['Scale'].default_value = 2.2; noi.inputs['Detail'].default_value = 9; noi.inputs['Roughness'].default_value = 0.62; L.new(mp.outputs[0], noi.inputs['Vector'])
    wr = N.new('ShaderNodeTexNoise'); wr.inputs['Scale'].default_value = 9; wr.inputs['Detail'].default_value = 4; L.new(mp.outputs[0], wr.inputs['Vector'])
    ramp = N.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color = (*dark, 1); ramp.color_ramp.elements[1].color = (*light, 1); ramp.color_ramp.elements.new(0.5).color = (*base, 1)
    L.new(noi.outputs['Fac'], ramp.inputs['Fac'])
    # creux des écailles plus sombres (saleté)
    sc = N.new('ShaderNodeMapRange'); sc.inputs['From Min'].default_value = 0.0; sc.inputs['From Max'].default_value = 0.08; L.new(vor.outputs['Distance'], sc.inputs['Value'])
    mul = N.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs['Factor'].default_value = 0.45
    L.new(ramp.outputs['Color'], mul.inputs[6]); cm = N.new('ShaderNodeCombineColor'); L.new(sc.outputs['Result'], cm.inputs[0]); L.new(sc.outputs['Result'], cm.inputs[1]); L.new(sc.outputs['Result'], cm.inputs[2])
    L.new(cm.outputs[0], mul.inputs[7])
    geo = N.new('ShaderNodeNewGeometry'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(geo.outputs['Normal'], sep.inputs[0]); belly = N.new('ShaderNodeMapRange'); belly.inputs['From Min'].default_value = -0.85; belly.inputs['From Max'].default_value = -0.2; L.new(sep.outputs['Z'], belly.inputs['Value'])
    inv = N.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0; L.new(belly.outputs['Result'], inv.inputs[1])
    bm_ = N.new('ShaderNodeMix'); bm_.data_type = 'RGBA'; bm_.blend_type = 'MIX'; L.new(inv.outputs[0], bm_.inputs['Factor']); L.new(mul.outputs[2], bm_.inputs[6]); bm_.inputs[7].default_value = (0.22, 0.2, 0.12, 1) if belly_ else (0, 0, 0, 1)
    if belly_: L.new(bm_.outputs[2], bsdf.inputs['Base Color'])
    else: L.new(mul.outputs[2], bsdf.inputs['Base Color'])
    b1 = N.new('ShaderNodeBump'); b1.inputs['Strength'].default_value = bump; b1.inputs['Distance'].default_value = 0.02; L.new(vor.outputs['Distance'], b1.inputs['Height'])
    b2 = N.new('ShaderNodeBump'); b2.inputs['Strength'].default_value = 0.25; b2.inputs['Distance'].default_value = 0.05; L.new(wr.outputs['Fac'], b2.inputs['Height']); L.new(b1.outputs['Normal'], b2.inputs['Normal'])
    L.new(b2.outputs['Normal'], bsdf.inputs['Normal'])
    return m


def obj_from_bm(name, bm, coll):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(name, me); coll.objects.link(o); return o


def build(spec_path, coll=None):
    S = json.load(open(spec_path)); coll = coll or bpy.context.scene.collection
    skinM = mat_skin('statue_skin', belly_=True); plateM = mat_skin('statue_plate', base=(0.2, 0.15, 0.07), dark=(0.08, 0.06, 0.03), light=(0.32, 0.25, 0.12), scale=22, bump=0.25)
    darkM = bpy.data.materials.new('statue_dark'); darkM.use_nodes = True; darkM.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.01, 0.01, 0.008, 1); darkM.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
    eyeM = bpy.data.materials.new('statue_eye'); eyeM.use_nodes = True; eyeM.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.02, 0.018, 0.012, 1); eyeM.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.15
    # --- corps + pattes en « metaballs » (sphères qui fusionnent) -> maillage lisse, sans couture
    mb = bpy.data.metaballs.new('STATUE_mb'); mb.resolution = 0.06; mb.render_resolution = 0.035; mb.threshold = 0.6
    mo = bpy.data.objects.new('STATUE_mbobj', mb); coll.objects.link(mo)
    def ball(c, r, sx=1.0, sy=1.0, sz=1.0, q=None):
        e = mb.elements.new(); e.co = c; e.radius = r * 1.4; e.stiffness = 2.0
        if sx != 1 or sy != 1 or sz != 1:
            e.type = 'ELLIPSOID'; e.size_x, e.size_y, e.size_z = sx, sy, sz; e.radius = r * 1.4
        if q is not None: e.rotation = q
    sp = S['spine']
    for (x0, y0, z0, ry0, rz0), (x1, y1, z1, ry1, rz1) in zip(sp, sp[1:]):
        for k in range(3):
            t = k / 3; x, y, z = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, z0 + (z1 - z0) * t; ry, rz = ry0 + (ry1 - ry0) * t, rz0 + (rz1 - rz0) * t
            if ry < 0.06: continue
            ball(P(x, y, z), max(ry, rz), sx=1.0, sy=rz / max(ry, rz), sz=ry / max(ry, rz))
    for L in S['legs']:
        top, knee, foot = Vector(L['top']), Vector(L['knee']), Vector(L['foot']); r0 = L['r0']; hind = r0 > 0.45
        kn = knee + Vector(((0.2 if hind else -0.08), 0, 0))
        pts = [(top + Vector((0, 0.12, 0)), r0 * 1.05), (top.lerp(kn, 0.35), r0 * 0.85), (top.lerp(kn, 0.7), r0 * 0.68), (kn, r0 * 0.58), (kn.lerp(foot, 0.4), r0 * 0.5), (kn.lerp(foot, 0.75), r0 * 0.48), (foot + Vector((0, 0.05, 0)), r0 * 0.52)]
        for (a_, ra), (b_, rb) in zip(pts, pts[1:]):
            for k in range(3):
                t = k / 3; ball(P(*(a_.lerp(b_, t))), ra + (rb - ra) * t)
        f = P(*foot); ball(f + Vector((0.14, 0, -f.z + 0.16)), r0 * 0.75, sx=1.25, sy=1.0, sz=0.42)   # pied large et plat
    # le cou / la tête : petites sphères supplémentaires pour la mâchoire
    hx, hy, hz = sp[-3][:3]; ball(P(hx + 0.05, hy - 0.08, hz), 0.24, sx=1.4, sy=0.85, sz=0.7)
    bpy.context.view_layer.objects.active = mo; mo.select_set(True); bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get(); me = bpy.data.meshes.new_from_object(mo.evaluated_get(dg)); body = bpy.data.objects.new('STATUE_body', me); coll.objects.link(body)
    bpy.data.objects.remove(mo)
    for pgn in body.data.polygons: pgn.use_smooth = True
    body.data.materials.append(skinM)
    s1 = body.modifiers.new('sub', 'SUBSURF'); s1.levels = 1; s1.render_levels = 1
    tex = bpy.data.textures.new('wrinkle', 'CLOUDS'); tex.noise_scale = 0.35; tex.noise_depth = 3
    tex2 = bpy.data.textures.new('folds', 'STUCCI'); tex2.noise_scale = 0.12; tex2.turbulence = 6
    d0 = body.modifiers.new('folds', 'DISPLACE'); d0.texture = tex2; d0.strength = 0.03; d0.texture_coords = 'GLOBAL'
    d = body.modifiers.new('disp', 'DISPLACE'); d.texture = tex; d.strength = 0.07; d.mid_level = 0.5; d.texture_coords = 'GLOBAL'
    # --- la fente : un vrai trou dans le dos (Booléen), noir à l'intérieur
    sx, sy, sz = S['slot']; slot = P(sx, sy, sz)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1, location=slot); cut = bpy.context.active_object; cut.name = 'STATUE_slotcut'
    cut.scale = (0.34, 0.2, 0.22); cut.rotation_euler = (0, -S['slotRot'], 0); cut.hide_render = True; cut.hide_viewport = True
    b = body.modifiers.new('slot', 'BOOLEAN'); b.object = cut; b.operation = 'DIFFERENCE'; b.solver = 'FAST'
    sol = body.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = 0.06; sol.offset = -1; sol.use_rim = True
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1, location=slot - Vector((0, 0, 0.35))); hole = bpy.context.active_object; hole.name = 'STATUE_holedark'; hole.scale = (0.32, 0.18, 0.3); hole.data.materials.append(darkM)
    # --- plaques dorsales (forme de cerf-volant arrondie, épaisses, biseautées)
    for i, pl in enumerate(S['plates']):
        bm = bmesh.new(); pts = []
        for k in range(24):
            t = k / 23; a = math.pi * t
            x = -0.5 * math.cos(a); yv = math.sin(a) ** 0.85 * (1.0 if 0.35 < t < 0.65 else 0.92)
            pts.append(bm.verts.new((x * 0.95, 0, yv)))
        f = bm.faces.new(pts); ext = bmesh.ops.extrude_face_region(bm, geom=[f]); vs = [e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, verts=vs, vec=(0, 0.08, 0)); bmesh.ops.translate(bm, verts=bm.verts, vec=(0, -0.04, 0))
        o = obj_from_bm(f'STATUE_plate{i}', bm, coll); o.data.materials.append(plateM)
        bv = o.modifiers.new('bev', 'BEVEL'); bv.width = 0.03; bv.segments = 3; o.modifiers.new('sub', 'SUBSURF').levels = 1
        sc = pl['scale']; o.scale = (sc[0], 1, sc[1]); px, py, pz = pl['pos']; o.location = P(px, py, pz)
        C = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))   # three -> blender
        Rt = Euler(tuple(pl['rot']), 'XYZ').to_matrix(); o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = (C @ Rt @ C.inverted()).to_quaternion()
        dd = o.modifiers.new('disp', 'DISPLACE'); dd.texture = tex; dd.strength = 0.015
    # --- pointes de la queue
    tail = [Vector(p[:3]) for p in S['spine'][:6]]
    for u, s in [(2, 1), (2, -1), (4, 1), (4, -1)]:
        c = P(*S['spine'][u][:3]); dirn = Vector((-1, -s * 0.75, 0.45)).normalized()
        bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=0.08, radius2=0.0, depth=0.8, location=c + dirn * 0.4)
        o = bpy.context.active_object; o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(dirn); o.data.materials.append(plateM)
        bpy.ops.object.shade_smooth()
    # --- griffes, yeux, narines
    for L in S['legs']:
        f = P(*L['foot']); r = L['r1']
        for k in (-1, 0, 1):
            bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.1, radius2=0.02, depth=0.3, location=f + Vector((r * 1.15 + 0.12, k * r * 0.55, -f.z + 0.06)))
            o = bpy.context.active_object; o.rotation_euler = (0, math.radians(100), 0); o.data.materials.append(plateM); bpy.ops.object.shade_smooth()
    for e in S['eyes']:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.055, location=P(*e)); o = bpy.context.active_object; o.data.materials.append(eyeM); bpy.ops.object.shade_smooth()
    hx, hy, hz = S['spine'][-1][:3]
    for s in (-1, 1):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.03, location=P(hx - 0.12, hy + 0.05, s * 0.07)); o = bpy.context.active_object; o.data.materials.append(darkM)
    return body


def cutaway(body, clip_by_frame):
    """Vue en coupe : un grand cube retire tout ce qui est devant le plan z(three) = clip (y_blender = -clip)."""
    bpy.ops.mesh.primitive_cube_add(size=1); c = bpy.context.active_object; c.name = 'STATUE_cutter'; c.hide_render = True; c.hide_viewport = True
    c.scale = (30, 10, 30)
    b = body.modifiers.new('cut', 'BOOLEAN'); b.object = c; b.operation = 'DIFFERENCE'; b.solver = 'FAST'
    body.modifiers.move(len(body.modifiers) - 1, len(body.modifiers) - 2)   # avant l'épaisseur (Solidify)
    for fr, clip in clip_by_frame:
        on = clip is not None
        b.show_render = on; b.show_viewport = on; b.keyframe_insert('show_render', frame=fr); b.keyframe_insert('show_viewport', frame=fr)
        if on: c.location = (0, -clip - 5.0, 0); c.keyframe_insert('location', frame=fr)
    return c
