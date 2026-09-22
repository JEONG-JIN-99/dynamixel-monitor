"""Four-bottle basket prototype. Geometry uses millimetres; run with Blender."""
import bpy
import bmesh
import math
import json
import struct
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
INNER_X, INNER_Y, INNER_Z = 175.0, 220.0, 175.0
WALL, FLOOR = 5.0, 5.0
OUTER_X, OUTER_Y, BODY_H = INNER_X + WALL * 2, INNER_Y + WALL * 2, INNER_Z + FLOOR
EYE_RADIUS, HOLE_RADIUS, EYE_THICKNESS = 11.0, 4.0, 10.0
EYE_Z = BODY_H + 11.0

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 0.001
scene.unit_settings.length_unit = 'MILLIMETERS'

def cube(name, size, pos):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj

def boolean(target, operand, operation):
    bpy.context.view_layer.objects.active = target
    mod = target.modifiers.new(operation, 'BOOLEAN')
    mod.operation = operation
    mod.solver = 'EXACT'
    mod.object = operand
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(operand, do_unlink=True)

body = cube('Basket_4_bottles_PRINT', (OUTER_X, OUTER_Y, BODY_H), (0, 0, BODY_H/2))
cavity = cube('Cavity', (INNER_X, INNER_Y, INNER_Z+10), (0, 0, FLOOR+(INNER_Z+10)/2))
boolean(body, cavity, 'DIFFERENCE')

def eye_tab(cx, cy):
    # Flush exterior; grow from the 5mm wall to a 10mm eye above the rim.
    outline = [(cx-EYE_RADIUS, BODY_H-20), (cx+EYE_RADIUS, BODY_H-20)]
    outline += [(cx+EYE_RADIUS, BODY_H), (cx+EYE_RADIUS, BODY_H+5)]
    outline += [(cx+EYE_RADIUS*math.cos(i*math.pi/48), EYE_Z+EYE_RADIUS*math.sin(i*math.pi/48)) for i in range(49)]
    outline += [(cx-EYE_RADIUS, BODY_H+5), (cx-EYE_RADIUS, BODY_H)]
    n = len(outline)
    # The extra thickness slopes inward only above the 175mm usable cavity.
    sign = 1 if cy > 0 else -1
    verts = [(x, sign*(INNER_Y/2-min(5.0,max(0.0,z-BODY_H))) if abs(y)<abs(cy) else y, z)
             for y in (cy-EYE_THICKNESS/2, cy+EYE_THICKNESS/2)
             for x,z in outline]
    # Split each face at the two slope transitions so every polygon is planar.
    face_sections = [(0,1,2,n-1), (n-1,2,3,n-2), tuple([n-2,3]+list(range(4,n-2)))]
    faces = [tuple(reversed(section)) for section in face_sections]
    faces += [tuple(i+n for i in section) for section in face_sections]
    faces += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
    mesh = bpy.data.meshes.new('EyeTabMesh')
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new('EyeTab', mesh)
    scene.collection.objects.link(obj)
    return obj

centres = []
for sx in (-1, 1):
    for sy in (-1, 1):
        cx, cy = sx*(OUTER_X/2-EYE_RADIUS-1.0), sy*(OUTER_Y/2-EYE_THICKNESS/2)
        boolean(body, eye_tab(cx, cy), 'UNION')
        centres.append((cx, cy))

def clean_mesh(obj):
    mesh_check = bmesh.new(); mesh_check.from_mesh(obj.data)
    bmesh.ops.remove_doubles(mesh_check, verts=list(mesh_check.verts), dist=0.0001)
    bmesh.ops.dissolve_limit(mesh_check, angle_limit=0.00001, verts=list(mesh_check.verts), edges=list(mesh_check.edges))
    bmesh.ops.recalc_face_normals(mesh_check, faces=list(mesh_check.faces))
    mesh_check.to_mesh(obj.data); mesh_check.free()

clean_mesh(body)
# Small edge rounding preserves the nominal flat-to-flat cavity dimensions.
bpy.context.view_layer.objects.active = body
bevel = body.modifiers.new('Rounded_edges_1mm', 'BEVEL')
bevel.width = 1.0
bevel.segments = 3
bevel.limit_method = 'ANGLE'
bpy.ops.object.modifier_apply(modifier=bevel.name)

for cx, cy in centres:
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=HOLE_RADIUS, depth=EYE_THICKNESS+6, location=(cx,cy,EYE_Z), rotation=(math.pi/2,0,0))
    boolean(body, bpy.context.object, 'DIFFERENCE')

clean_mesh(body)
bm = bmesh.new(); bm.from_mesh(body.data)
# Exact booleans can leave a collinear T-junction on a coplanar bevel edge.
# Split the spanning edge at the existing middle vertex, without changing shape.
boundary = [e for e in bm.edges if e.is_boundary]
if len(boundary) == 3:
    long_edge = max(boundary,key=lambda e:e.calc_length())
    verts = {v for e in boundary for v in e.verts}
    midpoints = verts-set(long_edge.verts)
    if len(midpoints)==1:
        middle = midpoints.pop()
        start, end = long_edge.verts
        segment = end.co-start.co
        fraction = (middle.co-start.co).dot(segment)/segment.length_squared
        distance = ((middle.co-start.co).cross(segment)).length/segment.length
        if 0 < fraction < 1 and distance < 0.0001:
            _, split_vertex = bmesh.utils.edge_split(long_edge,start,fraction)
            split_vertex.co = middle.co
            bmesh.ops.remove_doubles(bm,verts=[split_vertex,middle],dist=0.0001)
bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
bm.to_mesh(body.data); bm.free()
body.data.update()

def material(name, color, metallic=0.0, roughness=0.4):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color,1)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    return mat

body.data.materials.clear()
body.data.materials.append(material('Blue_gray_visual_only', (0.16,0.36,0.43), 0.12))
for p in body.data.polygons:
    p.material_index = 0
    p.use_smooth = False

# Export only the finished basket, in millimetres, independently of scene helpers.
body.data.calc_loop_triangles()
stl = OUT/'basket_4b_v2_mm.stl'
with stl.open('wb') as fh:
    fh.write(b'4 bottle basket prototype; millimetres'.ljust(80,b'\0'))
    fh.write(struct.pack('<I',len(body.data.loop_triangles)))
    for tri in body.data.loop_triangles:
        coords = [body.matrix_world @ body.data.vertices[i].co for i in tri.vertices]
        normal = (coords[1]-coords[0]).cross(coords[2]-coords[0]).normalized()
        fh.write(struct.pack('<12fH',*normal,*coords[0],*coords[1],*coords[2],0))

# Bottle envelopes are optional, hidden guides, not part of the STL.
guides = bpy.data.collections.new('REFERENCE_ONLY_85mm_x_215mm_bottles')
scene.collection.children.link(guides)
for x in (-43.75,43.75):
    for z in (48.75,136.25):
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=42.5, depth=215, location=(x,0,z), rotation=(math.pi/2,0,0))
        ob = bpy.context.object
        ob.name = 'Bottle_envelope_REFERENCE_ONLY'
        for col in list(ob.users_collection): col.objects.unlink(ob)
        guides.objects.link(ob)
        ob.display_type = 'WIRE'
        ob.hide_render = True
        ob.hide_set(True)

# Mesh acceptance checks: one closed connected solid, consistent orientation.
bm = bmesh.new(); bm.from_mesh(body.data)
nonmanifold = sum(not e.is_manifold for e in bm.edges)
bad_orientation = sum(not e.is_contiguous for e in bm.edges)
remaining = set(bm.verts)
components = 0
while remaining:
    components += 1
    pending = [remaining.pop()]
    while pending:
        vertex = pending.pop()
        for edge in vertex.link_edges:
            other = edge.other_vert(vertex)
            if other in remaining:
                remaining.remove(other); pending.append(other)
volume = bm.calc_volume(signed=True)
bm.free()
bounds = [body.matrix_world @ Vector(corner) for corner in body.bound_box]
extents = [max(p[i] for p in bounds)-min(p[i] for p in bounds) for i in range(3)]
report = {'units':'mm','internal_dimensions':[INNER_X,INNER_Y,INNER_Z], 'body_dimensions':[OUTER_X,OUTER_Y,BODY_H], 'overall_dimensions_with_eyes':extents, 'wall_mm':WALL, 'floor_mm':FLOOR, 'eye_hole_diameter_mm':HOLE_RADIUS*2, 'eye_thickness_mm':EYE_THICKNESS, 'nonmanifold_edges':nonmanifold, 'inconsistently_oriented_edges':bad_orientation, 'connected_components':components, 'signed_volume_mm3':volume, 'triangle_count':len(body.data.loop_triangles), 'sliced':False, 'physical_load_tested':False}
report['exterior_protrusion_xy_mm'] = [max(0.0,extents[0]-OUTER_X),max(0.0,extents[1]-OUTER_Y)]
report['three_baskets_side_by_side_dimensions_mm'] = [OUTER_X*3, OUTER_Y, extents[2]]
assert abs(extents[0]-OUTER_X)<0.001 and abs(extents[1]-OUTER_Y)<0.001, report
# Check the actual four cylindrical bottle envelopes against the finished mesh.
overlaps = []
for guide in guides.objects:
    probe = body.copy(); probe.data = body.data.copy(); scene.collection.objects.link(probe)
    operand = guide.copy(); operand.data = guide.data.copy(); scene.collection.objects.link(operand)
    operand.hide_set(False)
    boolean(probe,operand,'INTERSECT')
    check = bmesh.new(); check.from_mesh(probe.data)
    overlap = abs(check.calc_volume(signed=True)) if len(check.faces) else 0.0
    check.free(); bpy.data.objects.remove(probe,do_unlink=True)
    overlaps.append(overlap)
report['bottle_intersection_volumes_mm3'] = overlaps
assert all(v<0.01 for v in overlaps), report
(OUT/'validation_v2.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
assert nonmanifold == 0 and bad_orientation == 0 and components == 1 and volume > 0, report
assert all(v < 256 for v in extents), report

floor = cube('DISPLAY_ground_not_for_print', (1800,1800,2), (0,0,-2))
floor.data.materials.append(material('Ground',(0.82,0.85,0.87),0,0.8))
floor.hide_select = True
world = scene.world or bpy.data.worlds.new('Studio')
scene.world = world
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (0.65,0.72,0.8,1)
world.node_tree.nodes['Background'].inputs[1].default_value = 0.5

def aim(obj, at):
    obj.rotation_euler = (Vector(at)-obj.location).to_track_quat('-Z','Y').to_euler()

for name,loc,power,size in [('Key',(100,-250,450),4000000,300),('Fill',(-300,-80,250),2500000,250),('Rim',(60,350,350),4500000,200)]:
    data = bpy.data.lights.new(name,'AREA'); data.energy = power; data.shape='DISK'; data.size=size
    ob = bpy.data.objects.new(name,data); scene.collection.objects.link(ob); ob.location=loc; aim(ob,(0,0,85))
bpy.ops.object.camera_add(location=(390,-480,380))
cam = bpy.context.object
cam.name = 'Preview_camera'
aim(cam,(0,0,97))
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 390; cam.data.clip_end=5000
scene.camera = cam
scene.render.engine = 'CYCLES'
scene.cycles.samples = 32
scene.cycles.use_denoising = True
scene.render.resolution_x = 1100
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(OUT/'basket_4b_v2_preview.png')
scene.view_settings.view_transform = 'AgX'
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True); bpy.context.view_layer.objects.active=body
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.clip_end=10000
            area.spaces.active.region_3d.view_distance=450
            area.spaces.active.region_3d.view_location=Vector((0,0,90))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'basket_4b_v2.blend'))
bpy.ops.render.render(write_still=True)
# Illustration only: three separately printed baskets touching along their sides.
for offset in (-OUTER_X, OUTER_X):
    ob = body.copy(); ob.data=body.data.copy(); scene.collection.objects.link(ob)
    ob.name='ASSEMBLY_preview_only'; ob.location.x += offset
cam.location=(560,-800,610); aim(cam,(0,0,95)); cam.data.ortho_scale=760
scene.render.resolution_x=1440; scene.render.resolution_y=900
scene.render.filepath = str(OUT/'basket_4b_v2_three_preview.png')
bpy.ops.render.render(write_still=True)
print('BASKET_BUILD_OK',json.dumps(report))
