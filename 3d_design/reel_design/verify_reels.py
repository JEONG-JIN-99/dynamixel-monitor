"""Reimport STLs, measure all changed features and check preserved reel surfaces."""
import bpy,bmesh,json,math,hashlib
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
ARCHIVE=OUT/'archive/reel_cleanup_20260922_D2p5/reel_design'
reports=[]
def near(a,b,t=.004):assert abs(a-b)<t,(a,b)
def cast(obj,p,d,length=300):
    ok,pt,_,_=obj.ray_cast(Vector(p),Vector(d),distance=length)
    return pt if ok else None
for model,waist in [('w350',83.6),('w210',61.2)]:
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    name=f'Reel_{model}'
    bpy.ops.wm.stl_import(filepath=str(OUT/(name+'.stl')));body=bpy.context.object
    previous=ARCHIVE/'center_relief_D5_before_D2p5'/f'Rell_{model}_relief_D5_extended.stl'
    bpy.ops.wm.stl_import(filepath=str(previous));old=bpy.context.object
    bm=bmesh.new();bm.from_mesh(body.data)
    for e in bm.edges:
        if not (e.is_manifold and e.is_contiguous):print('BAD_EDGE',[tuple(v.co) for v in e.verts],len(e.link_faces),flush=True)
    assert all(e.is_manifold and e.is_contiguous for e in bm.edges)
    for f in bm.faces:
        if f.calc_area()<=1e-9:print('TINY_FACE',f.calc_area(),[tuple(v.co) for v in f.verts],flush=True)
    assert all(f.calc_area()>1e-9 for f in bm.faces)
    remaining=set(bm.verts);components=0
    while remaining:
        components+=1;pending=[remaining.pop()]
        while pending:
            v=pending.pop()
            for e in v.link_edges:
                w=e.other_vert(v)
                if w in remaining:remaining.remove(w);pending.append(w)
    assert components==1 and bm.calc_volume(signed=True)>0
    volume=bm.calc_volume(signed=True);bm.free()
    near(min(v.co.z for v in body.data.vertices),0)
    near(max(v.co.z for v in body.data.vertices),48.7)
    near(cast(body,(0,100,25.2),(0,-1,0)).y-cast(body,(0,-100,25.2),(0,1,0)).y,waist)
    # Same upper surfaces in both directions, including rope-hole/groove walls.
    max_error=0;probes=0
    for source,target in [(old,body),(body,old)]:
        for v in source.data.vertices:
            if v.co.z<=12.701:continue
            ok,pt,_,_=target.closest_point_on_mesh(v.co)
            assert ok
            err=(pt-v.co).length;max_error=max(max_error,err);probes+=1
            assert err<.005,('upper geometry changed',model,tuple(v.co),err)
    # Extended mount envelope below its top junction, matching the test coupon.
    near(cast(body,(100,0,6),(-1,0,0)).x,16.8)
    near(cast(body,(-100,0,6),(1,0,0)).x,-16.8)
    near(cast(body,(0,100,6),(0,-1,0)).y,23.8)
    near(cast(body,(0,-100,6),(0,1,0)).y,-23.8)
    for y in (-18,18):near(cast(body,(0,y,-2),(0,0,1)).z,0)
    holes=[]
    for sign in (-1,1):
        for y in (-11,11):
            end=cast(body,(sign*18,y,5),(-sign,0,0));near(end.x,sign*2.3)
            lo=cast(body,(sign*10,y,5),(0,0,-1));hi=cast(body,(sign*10,y,5),(0,0,1))
            a=cast(body,(sign*10,y,5),(0,-1,0));b=cast(body,(sign*10,y,5),(0,1,0))
            near(hi.z-lo.z,2.5);near(b.y-a.y,2.5);near((hi.z+lo.z)/2,5);near((a.y+b.y)/2,y)
            for k in range(32):
                angle=2*math.pi*k/32
                assert cast(body,(sign*17,y+1.22*math.cos(angle),5+1.22*math.sin(angle)),(-sign,0,0),14.2) is None
            holes.append({'center':[sign*16.8,y,5],'diameter':hi.z-lo.z,'depth':16.8-abs(end.x)})
    for k in range(32):
        a=(k+.17)*2*math.pi/32;c,s=math.cos(a),math.sin(a)
        near(cast(body,(2.0*c,2.0*s,-1),(0,0,1)).z,3)
        p=cast(body,(0,0,1.5),(c,s,0));q=cast(body,(0,0,1.5),(-c,-s,0));near((p-q).length,5.0)
    # Actual 2.1 mm envelopes through both drum rope holes and the stem hole.
    scale=waist/83.6
    for sign in (-1,1):
        for k in range(24):
            a=2*math.pi*k/24
            p=cast(body,(sign*47.8*scale+1.05*math.cos(a),1.05*math.sin(a),39),(0,0,-1))
            assert p is None or p.z<22.7,('blocked drum hole',model,p)
            assert cast(body,(sign*12,1.05*math.cos(a),40.2+1.05*math.sin(a)),(-sign,0,0),24) is None
    # Outside the four bore regions, both directions must match the previous final.
    preserved_mount_max_error=0;preserved_mount_probes=0
    for source_obj,target in [(old,body),(body,old)]:
        for v in source_obj.data.vertices:
            if v.co.z>12.701:continue
            if abs(v.co.x)>1.8 and abs(abs(v.co.y)-11)<1.9 and abs(v.co.z-5)<1.9:continue
            ok,pt,_,_=target.closest_point_on_mesh(v.co);assert ok
            err=(pt-v.co).length
            preserved_mount_max_error=max(preserved_mount_max_error,err);preserved_mount_probes+=1
            assert err<.005,('unrequested mount change',model,tuple(v.co),err)
    source=previous
    report={'file':name+'.stl','closed_components':components,'mesh_checks_passed':True,'volume_mm3':volume,
       'mount_mm':[33.6,47.6,12.7],'pocket_diameter_mm':5.0,'pocket_depth_mm':3,
       'side_holes':holes,'waist_diameter_mm':waist,'height_mm':48.7,
       'upper_surface_comparison_probes':probes,'max_upper_surface_deviation_mm':max_error,
       'preserved_mount_probes':preserved_mount_probes,'preserved_mount_max_error_mm':preserved_mount_max_error,
       'compared_to_previous_final':str(previous),'side_hole_nominal_diameter_mm':2.5,
       'rope_holes_clear':True,'physical_fit_tested':False,'load_tested':False,
       'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
    reports.append(report);print('REEL_VERIFIED',json.dumps(report),flush=True)
(OUT/'verification.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
