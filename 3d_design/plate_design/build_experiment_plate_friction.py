"""Integrated S102K friction plate. All geometry in mm; references excluded from STL."""
import bpy,bmesh,math,struct,json
from pathlib import Path
from mathutils import Vector,Matrix
OUT=Path(__file__).resolve().parent
NAME='experiment_plate_friction'
CX,CY=118.,22.
AXIS_H=91.
# S102K outer web -> side-hole center8.5; XM lower case-hole -> axis40-8=32.
TOP=AXIS_H-(8.5+32.)
B=CX+17+2.2+1.5+2 # original nominal horn/frame/surrounding-head stack
G=B+25.2
GY,GZ=90.,36.
scene=bpy.context.scene
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.001;scene.unit_settings.length_unit='MILLIMETERS'

def mesh(name,verts,faces):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
    ob=bpy.data.objects.new(name,me);scene.collection.objects.link(ob)
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
    return ob
def prism(name,poly,lo,hi,axis=2):
    other=[i for i in range(3) if i!=axis];verts=[]
    for level in (lo,hi):
        for a,b in poly:
            p=[0.,0.,0.];p[axis]=level;p[other[0]]=a;p[other[1]]=b;verts.append(p)
    n=len(poly)
    return mesh(name,verts,[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)])
def cube(name,size,loc):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);ob=bpy.context.object;ob.name=name;ob.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);return ob
def cyl(name,a,b,r,n=128):
    a,b=Vector(a),Vector(b)
    bpy.ops.mesh.primitive_cylinder_add(vertices=n,radius=r,depth=(b-a).length,location=(a+b)/2)
    ob=bpy.context.object;ob.name=name;ob.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();return ob
def boolean(ob,tool,operation='UNION'):
    bpy.context.view_layer.objects.active=ob
    mod=ob.modifiers.new(operation,'BOOLEAN');mod.solver='MANIFOLD';mod.operation=operation;mod.object=tool
    bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(tool,do_unlink=True)
outline=[(0,0),(236,0),(236,70),(196,70),(196,100),(40,100),(40,70),(0,70)]
body=prism(NAME,outline,0,20)
boolean(body,cube('Raised_S102K_support',(44,36,TOP-19.8),(CX,CY,(TOP+19.8)/2)))
# Low X braces stay below the large rim's global lowest height39.2.
for sign in (-1,1):
    e=CX+sign*22
    boolean(body,prism('X_brace',[(e-sign*.3,19.8),(e+sign*18,19.8),(e-sign*.3,36)],CY-5,CY+5,axis=1))
# Front brace lies entirely to the left of the rotating reel assembly.
boolean(body,prism('Front_brace',[(39.7,19.8),(58,19.8),(39.7,43)],CX-5,CX+5,axis=0))
for x in (106,130):
    for y in (16,28):boolean(body,cyl('D2p5_depth15',(x,y,TOP+1),(x,y,TOP-15),1.25),'DIFFERENCE')

# Fixed guide: same U-shaped contact groove as the earlier friction plates.
profile=[(-8,10),(-1.6,10)]
for i in range(49):
    a=math.pi*i/48;profile.append((-1.6*math.cos(a),9.6-1.6*math.sin(a)))
profile += [(1.6,10),(8,10)]
n=192
verts=[(G+dx,GY+r*math.cos(2*math.pi*j/n),GZ+r*math.sin(2*math.pi*j/n)) for dx,r in profile for j in range(n)]
faces=[tuple(reversed(range(n))),tuple(range((len(profile)-1)*n,len(profile)*n))]
faces += [(i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j) for i in range(len(profile)-1) for j in range(n)]
guide=mesh('Fixed_guide_U_groove',verts,faces)
boolean(body,cube('Guide_foot',(28,40,6.2),(G,80,22.9))) # Z19.8 to26
boolean(body,cube('Lower_saddle',(16,15,8.4),(G,87.5,30))) # frontY95
support=[(80,25.8),(100,25.8),(99.7,35.7),(80,35.7)]
for sign in (-1,1):
    lo,hi=sorted((G+sign*2.8,G+sign*8))
    boolean(body,prism('Guide_side_support',support,lo,hi,axis=0))
boolean(body,guide)
# Clear the vertical rope below the guide; includes the foot and the full plate.
boolean(body,cube('Front_rope_exit',(8,6,28),(G,99,-1+14)),'DIFFERENCE') # Y96..102 Z-1..27
bm=bmesh.new();bm.from_mesh(body.data)
for _ in range(2):
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-4)
    bmesh.ops.dissolve_degenerate(bm,dist=1e-4,edges=list(bm.edges))
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
assert all(e.is_manifold and e.is_contiguous for e in bm.edges)
assert bm.calc_volume(signed=True)>0
bm.to_mesh(body.data);bm.free();body.data.calc_loop_triangles()
with (OUT/(NAME+'.stl')).open('wb') as f:
    f.write(b'Integrated S102K friction plate; mm; D2.5 depth15'.ljust(80,b'\0'))
    f.write(struct.pack('<I',len(body.data.loop_triangles)))
    for tri in body.data.loop_triangles:
        a,b,c=[body.matrix_world@body.data.vertices[i].co for i in tri.vertices]
        normal=(b-a).cross(c-a).normalized();f.write(struct.pack('<12fH',*normal,*a,*b,*c,0))

manifest=dict(file=NAME+'.stl',units='mm',plate_body=[236,100,20],overall_dimensions=[236,100,TOP],
    type='integrated_fixed_guide',mount_center=[CX,CY],mount_footprint=[44,36],mount_top_z=TOP,
    mount_above_plate=TOP-20,frame='FR12-S102K',hole_centers_xy=[[x,y] for x in (106,130) for y in (16,28)],
    hole_diameter=2.5,hole_depth=15,hole_spacing_xy=[24,12],screw='FHS M2.5x14',
    axis_height=AXIS_H,frame_to_axis_stack=[8.5,32],motor_bottom_to_axis=35.25,
    reel_base_x=B,reel_base_stack=[CX,17,2.2,1.5,2],guide_groove_x=G,guide_center_yz=[GY,GZ],
    guide_outer_radius=10,guide_top_z=46,groove_width=3.2,groove_depth=2,groove_root_radius=8,
    rope_diameter=2,rope_drop_center=[G,99],exit_notch_width=8,exit_notch_depth=4,
    waist_to_guide_clearance_w350=3.2,outer_rim_floor_clearance_w350=19.2,
    physical_fit_tested=False,load_tested=False,sliced=False,
    assumptions=['S102K side holes fasten to the lower front/rear motor case holes; outer web contacts printed support',
        'XM430 lower case-hole to output-axis distance is32mm (40mm case-hole pitch minus8mm top-hole-to-axis)',
        'Original surrounding screw-head offset2mm remains in reel base stack; central relief remains D5 depth3',
        'No extra shims; nominal drawing assembly rather than physical metrology'])
(OUT/(NAME+'_design.json')).write_text(json.dumps(manifest,indent=2),encoding='utf-8')

def material(name,color):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1)
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*color,1)
    m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.55;return m
def paint(ob,mat):
    ob.data.materials.clear();ob.data.materials.append(mat)
    for p in ob.data.polygons:p.material_index=0
paint(body,material('Plate_teal',(.06,.29,.36)))
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.7,.76,.82,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.45
def aim(ob,p):ob.rotation_euler=(Vector(p)-ob.location).to_track_quat('-Z','Y').to_euler()
for loc,power,size in [((0,260,350),1800000,220),((320,-150,250),1400000,180)]:
    data=bpy.data.lights.new('Softbox','AREA');data.energy=power;data.size=size
    ob=bpy.data.objects.new('Softbox',data);scene.collection.objects.link(ob);ob.location=loc;aim(ob,(118,45,35))
bpy.ops.object.camera_add(location=(340,300,250));camera=bpy.context.object
camera.data.type='ORTHO';camera.data.ortho_scale=285;camera.data.clip_end=5000;aim(camera,(118,48,25));scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=1400;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(OUT/(NAME+'_preview.png'))
bpy.ops.render.render(write_still=True)
# Assembly references are for understanding and clearance checks, never printed.
refs=[];dark=material('Reference_motor',(.065,.075,.085));metal=material('Reference_metal',(.48,.5,.53))
motor=cube('REFERENCE_motor',(34,28.5,46.5),(CX,CY,AXIS_H-35.25+23.25));paint(motor,dark);refs.append(motor)
web=cube('REFERENCE_S102K_web',(37,28,1.5),(CX,CY,TOP+.75));paint(web,metal);refs.append(web)
for sign in (-1,1):
    ear=cube('REFERENCE_S102K_ear',(1.5,28,10.1),(CX+sign*17.75,CY,TOP+6.45));paint(ear,metal);refs.append(ear)
bpy.ops.wm.stl_import(filepath=str(OUT.parent/'reel_design/Reel_w350.stl'))
reel=bpy.context.object;reel.name='REFERENCE_Reel_w350_NOT_EXPORTED'
reel.matrix_world=Matrix.Translation((B,CY,AXIS_H))@Matrix.Rotation(math.pi/2,4,'Y');paint(reel,metal);refs.append(reel)
R,r=42.8,9.;phi=math.atan2(GZ-AXIS_H,GY-CY)+math.acos((R-r)/math.hypot(GY-CY,GZ-AXIS_H))
points=[(G,CY+R*math.cos(phi),AXIS_H+R*math.sin(phi)),(G,GY+r*math.cos(phi),GZ+r*math.sin(phi))]
points += [(G,GY+r*math.cos(phi*(1-i/32)),GZ+r*math.sin(phi*(1-i/32))) for i in range(1,33)]
points += [(G,99,-8)]
curve=bpy.data.curves.new('Reference_rope','CURVE');curve.dimensions='3D';curve.bevel_depth=1;curve.bevel_resolution=4
sp=curve.splines.new('POLY');sp.points.add(len(points)-1)
for p,co in zip(sp.points,points):p.co=(*co,1)
rope=bpy.data.objects.new('REFERENCE_rope_NOT_EXPORTED',curve);scene.collection.objects.link(rope)
rope.data.materials.append(material('Rope_orange',(.9,.3,.035)));refs.append(rope)
camera.location=(365,305,245);camera.data.ortho_scale=320;aim(camera,(118,40,50))
scene.render.filepath=str(OUT/(NAME+'_assembly.png'));bpy.ops.render.render(write_still=True)
for ob in refs:ob.hide_render=True;ob.hide_set(True)
camera.location=(340,300,250);camera.data.ortho_scale=285;aim(camera,(118,48,25))
scene.render.filepath=str(OUT/(NAME+'_preview.png'))
bpy.ops.object.select_all(action='DESELECT');body.select_set(True);bpy.context.view_layer.objects.active=body
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(NAME+'.blend')))
print('FRICTION_BUILD_COMPLETE',json.dumps(manifest))
