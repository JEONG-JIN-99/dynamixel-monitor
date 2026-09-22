"""Three independent labeled S102K coupons in one STL, dimensions in millimetres."""
import bpy,bmesh,json,math,struct,hashlib,sys
from pathlib import Path
from mathutils import Vector,Matrix
OUT=Path(__file__).resolve().parent;NAME='experiment_plate_mount_test_D2p5_D2p6_D2p7'
SOURCE=OUT.parent/'experiment_plate_friction.stl'
scene=bpy.context.scene
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.001;scene.unit_settings.length_unit='MILLIMETERS'
def boolean(ob,tool,op='DIFFERENCE',solver='MANIFOLD'):
    bpy.context.view_layer.objects.active=ob
    mod=ob.modifiers.new(op,'BOOLEAN');mod.operation=op;mod.solver=solver;mod.object=tool
    bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(tool,do_unlink=True)
def box(size,loc):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);ob=bpy.context.object;ob.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);return ob
coupons=[];metadata=[]
for index,diameter in enumerate((2.5,2.6,2.7)):
    bpy.ops.wm.stl_import(filepath=str(SOURCE));body=bpy.context.object;body.name=f'Test_D{diameter:.1f}'
    boolean(body,box((44,36,20),(118,22,40.5)),'INTERSECT')
    body.data.transform(Matrix.Translation((-96,-4,-30.5)))
    if diameter>2.5:
        for x,y in ((10,12),(10,24),(34,12),(34,24)):
            bpy.ops.mesh.primitive_cylinder_add(vertices=128,radius=diameter/2,depth=16,location=(x,y,13))
            boolean(body,bpy.context.object)
    # Shallow recess clear of all bores; no protrusions affecting print orientation.
    # Blender text extrusion extends both ways:20.1 +/- .7 -> floor19.4.
    bpy.ops.object.text_add(location=(22,4,20.1))
    label=bpy.context.object;label.data.body=f'D{diameter:.1f}'
    label.data.size=4;label.data.align_x='CENTER';label.data.extrude=.7
    bpy.ops.object.convert(target='MESH');label=bpy.context.object
    boolean(body,label,solver='EXACT')
    bm=bmesh.new();bm.from_mesh(body.data)
    for _ in range(2):
        bmesh.ops.triangulate(bm,faces=list(bm.faces))
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-4)
        bmesh.ops.dissolve_degenerate(bm,dist=1e-4,edges=list(bm.edges))
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(body.data);bm.free()
    body.data.transform(Matrix.Translation((54*index,0,0)));body.data.update()
    coupons.append(body)
    metadata.append(dict(label=f'D{diameter:.1f}',diameter_mm=diameter,
        bounds_xy=[[54*index,0],[54*index+44,36]],hole_depth_mm=15,hole_spacing_mm=[24,12]))
triangles=[]
for body in coupons:
    body.data.calc_loop_triangles()
    for tri in body.data.loop_triangles:
        a,b,c=[body.data.vertices[i].co for i in tri.vertices]
        normal=(b-a).cross(c-a).normalized();triangles.append(struct.pack('<12fH',*normal,*a,*b,*c,0))
with (OUT/(NAME+'.stl')).open('wb') as f:
    f.write(b'S102K test set; mm; three separate coupons D2.5 D2.6 D2.7'.ljust(80,b'\0'))
    f.write(struct.pack('<I',len(triangles)));f.writelines(triangles)
(OUT/(NAME+'_design.json')).write_text(json.dumps(dict(file=NAME+'.stl',units='mm',
    dimensions_mm=[152,36,20],coupon_dimensions_mm=[44,36,20],gap_mm=10,
    coupons=metadata,source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),physical_fit_tested=False),indent=2))
for index,body in enumerate(coupons):
    mat=bpy.data.materials.new(body.name);mat.use_nodes=True
    mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.06,.3,.36,1)
    body.data.materials.clear();body.data.materials.append(mat)
    for p in body.data.polygons:p.material_index=0
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.8,.84,.9,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.45
data=bpy.data.lights.new('Softbox','AREA');data.energy=550000;data.size=170
lamp=bpy.data.objects.new('Softbox',data);scene.collection.objects.link(lamp);lamp.location=(70,-50,200)
bpy.ops.object.camera_add(location=(185,-185,270));camera=bpy.context.object;camera.data.type='ORTHO';camera.data.ortho_scale=195
camera.rotation_euler=(Vector((76,18,10))-camera.location).to_track_quat('-Z','Y').to_euler();scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=1400;scene.render.resolution_y=800;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(OUT/(NAME+'_preview.png'))
bpy.ops.object.select_all(action='DESELECT')
for body in coupons:body.select_set(True)
bpy.context.view_layer.objects.active=coupons[0];bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(NAME+'.blend')))
bpy.ops.render.render(write_still=True)
print('THREE_COUPONS_BUILT',str(OUT/(NAME+'.stl')))
