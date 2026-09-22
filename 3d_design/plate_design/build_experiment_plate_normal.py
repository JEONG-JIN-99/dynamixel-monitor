"""FR12-S102K front-facing plate; all mesh/STL coordinates are millimetres."""
import bpy, bmesh, json, math, struct
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
NAME = 'experiment_plate_normal'
OUTLINE = [(0,0),(236,0),(236,70),(196,70),(196,100),(40,100),(40,70),(0,70)]
HOLES = [(x,y) for x in (112,124) for y in (69.5,93.5)]
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = .001
scene.unit_settings.length_unit = 'MILLIMETERS'
n = len(OUTLINE)
verts = [(x,y,z) for z in (0,20) for x,y in OUTLINE]
faces = [tuple(reversed(range(n))),tuple(range(n,2*n))]
faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
mesh = bpy.data.meshes.new(NAME)
mesh.from_pydata(verts,[],faces)
mesh.update()
body = bpy.data.objects.new(NAME,mesh)
scene.collection.objects.link(body)
for x,y in HOLES:
    # Cylinder extends beyond the top; pocket floor stays exactly z=5.
    bpy.ops.mesh.primitive_cylinder_add(vertices=128,radius=1.25,depth=16,location=(x,y,13))
    cutter = bpy.context.object
    bpy.context.view_layer.objects.active = body
    mod = body.modifiers.new('Blind_bore_D2p5_depth15','BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
bm = bmesh.new()
bm.from_mesh(body.data)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
bmesh.ops.triangulate(bm,faces=list(bm.faces))
assert all(e.is_manifold and e.is_contiguous for e in bm.edges)
assert bm.calc_volume(signed=True)>0
bm.to_mesh(body.data)
bm.free()
body.data.calc_loop_triangles()
with (OUT/(NAME+'.stl')).open('wb') as stream:
    stream.write(b'FR12-S102K front plate; mm; 4 blind bores D2.5 depth15'.ljust(80,b'\0'))
    stream.write(struct.pack('<I',len(body.data.loop_triangles)))
    for tri in body.data.loop_triangles:
        a,b,c = [body.matrix_world @ body.data.vertices[i].co for i in tri.vertices]
        normal = (b-a).cross(c-a).normalized()
        stream.write(struct.pack('<12fH',*normal,*a,*b,*c,0))

manifest = dict(file=NAME+'.stl',units='mm',dimensions=[236,100,20],outline=OUTLINE,
    frame_footprint=dict(x=[104,132],y=[63,100],width=28,length=37),
    motor_output_direction='+Y (front)',hole_centers_xy=HOLES,hole_diameter=2.5,
    hole_depth=15,hole_floor_z=5,hole_spacing_xy=[12,24],screw='FHS M2.5x14',
    screw_direction='From frame above down into printed plate',modeled_threads=False,
    physical_fit_tested=False,load_tested=False,sliced=False)
(OUT/(NAME+'_design.json')).write_text(json.dumps(manifest,indent=2),encoding='utf-8')

def material(name,color):
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=(*color,1)
    mat.use_nodes=True
    mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*color,1)
    mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.65
    return mat
body.data.materials.append(material('Plate_teal',(.045,.29,.36)))
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.8,.85,.9,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.65
def aim(obj,point):
    obj.rotation_euler=(Vector(point)-obj.location).to_track_quat('-Z','Y').to_euler()
for loc,power,size in [((50,160,300),1900000,230),((300,-50,180),1300000,180)]:
    data=bpy.data.lights.new('Softbox','AREA'); data.energy=power; data.size=size
    light=bpy.data.objects.new('Softbox',data);scene.collection.objects.link(light)
    light.location=loc;aim(light,(118,50,10))
bpy.ops.object.camera_add(location=(295,300,325))
camera=bpy.context.object
camera.data.type='ORTHO'; camera.data.ortho_scale=280;camera.data.clip_end=5000
aim(camera,(118,52,8));scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=1400;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.film_transparent=False
scene.render.filepath=str(OUT/(NAME+'_preview.png'))
bpy.ops.object.select_all(action='DESELECT');body.select_set(True);bpy.context.view_layer.objects.active=body
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(NAME+'.blend')))
bpy.ops.render.render(write_still=True)
print('BUILD_COMPLETE',str(OUT/(NAME+'.stl')))
