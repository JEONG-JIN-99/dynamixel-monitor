"""Apply the extended mounting coupon to both existing reel meshes (millimetres)."""
import bpy,bmesh,math,struct,json,hashlib
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
ROOT=OUT.parent
scene=bpy.context.scene
ARCHIVE=OUT/'archive/reel_cleanup_20260922_D2p5/reel_design'
exec((OUT/'reel_geometry_helpers.py').read_text(),globals())
def boolean(target,operand,operation='DIFFERENCE'):
    bpy.context.view_layer.objects.active=target
    mod=target.modifiers.new(operation,'BOOLEAN');mod.operation=operation
    mod.solver='MANIFOLD';mod.object=operand
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(operand,do_unlink=True)
reports=[]
for model in ('w350','w210'):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.001
    scene.unit_settings.length_unit='MILLIMETERS'
    source=ARCHIVE/f'Rell_{model}.stl'
    bpy.ops.wm.stl_import(filepath=str(source));reel=bpy.context.object
    name=f'Reel_{model}';reel.name=name
    # Remove the old lower block first to avoid coincident bore surfaces.
    # Replace the full old mounting block up to the drum underside at Z12.7.
    boolean(reel,cube('Remove_old_mount',(150,150,14.7),(0,0,5.35)))
    # The tested coupon, without the identifying top engraving.
    # Hidden 0.05 mm overlap into the drum avoids coincident joining faces.
    x=16.8;h=12.75;c=1.6
    outline=[(-x+c,0),(x-c,0),(x,c),(x,h),(-x,h),(-x,c)]
    verts=[(xx,yy,zz) for yy in (-23.8,23.8) for xx,zz in outline]
    n=len(outline)
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mount=mesh_object('Extended_mount',verts,faces)
    for y in (-11,11):
        for sign in (-1,1):
            boolean(mount,cylinder_between('Pilot',(sign*17.8,y,5),(sign*2.3,y,5),1.25))
    cleanup(mount)
    bpy.context.view_layer.objects.active=mount
    bevel=mount.modifiers.new('Coupon_edge_rounding','BEVEL')
    bevel.width=.3;bevel.segments=3;bevel.limit_method='ANGLE';bevel.angle_limit=.52
    bpy.ops.object.modifier_apply(modifier=bevel.name);cleanup(mount)
    # Union preserves the existing reel/drum geometry and original attachment root.
    boolean(reel,mount,'UNION')
    boolean(reel,cylinder_between('Central_blind_relief',(0,0,-1),(0,0,3),2.5,segments=128))
    bm=bmesh.new();bm.from_mesh(reel.data)
    for _ in range(2):
        bmesh.ops.triangulate(bm,faces=list(bm.faces))
        # Boolean intersections at the retained root can create sub-micron slivers.
        # Weld at 0.0001 mm, far below the 0.004 mm dimensional verification limit.
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-4)
        bmesh.ops.dissolve_degenerate(bm,dist=1e-4,edges=list(bm.edges))
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(reel.data);bm.free()
    report=mesh_report(reel)
    assert report['nonmanifold_edges']==report['inconsistent_edges']==0,report
    assert report['connected_components']==1 and report['signed_volume_mm3']>0,report
    export_stl(reel,OUT/(name+'.stl'))
    report.update(file=name+'.stl',source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        mount_dimensions_mm=[33.6,47.6,12.7],pocket_diameter_mm=5.0,pocket_depth_mm=3,
        side_hole_diameter_mm=2.5,side_hole_center_z_mm=5,side_hole_depth_mm=14.5,
        physical_fit_tested=False,load_tested=False)
    reports.append(report)
    reel.data.materials.clear();reel.data.materials.append(material('Reel_blue',(.08,.27,.35)))
    for p in reel.data.polygons:p.material_index=0
    scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.65,.7,.8,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.5
    for loc,power,size in [((150,-180,250),1800000,180),((-160,-100,-130),1500000,150),((20,150,210),2300000,150)]:
        data=bpy.data.lights.new('Studio','AREA');data.energy=power;data.size=size
        light=bpy.data.objects.new('Studio',data);scene.collection.objects.link(light);light.location=loc;aim(light,(0,0,20))
    bpy.ops.object.camera_add(location=(130,-180,-115));camera=bpy.context.object
    camera.data.type='ORTHO';camera.data.ortho_scale=145 if model=='w350' else 115
    aim(camera,(0,0,23));scene.camera=camera
    scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True
    scene.render.resolution_x=1200;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.filepath=str(OUT/(name+'_underside.png'))
    bpy.ops.object.select_all(action='DESELECT');reel.select_set(True);bpy.context.view_layer.objects.active=reel
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(name+'.blend')))
    bpy.ops.render.render(write_still=True)
    print('REEL_BUILT',json.dumps(report),flush=True)
(OUT/'design.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
