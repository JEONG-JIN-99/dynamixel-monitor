import bpy,bmesh,math,json
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent;NAME='experiment_plate_mount_test_D2p5_D2p6_D2p7'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.wm.stl_import(filepath=str(OUT/(NAME+'.stl')));ob=bpy.context.object
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.separate(type='LOOSE');bpy.ops.object.mode_set(mode='OBJECT')
parts=sorted(bpy.context.selected_objects,key=lambda p:min(v.co.x for v in p.data.vertices));assert len(parts)==3
def near(a,b,t=.003):assert abs(a-b)<t,(a,b)
def cast(ob,p,d):
    hit,point,_,_=ob.ray_cast(Vector(p),Vector(d),distance=100);assert hit,(p,d);return point
reports=[]
for index,(part,diameter) in enumerate(zip(parts,(2.5,2.6,2.7))):
    bm=bmesh.new();bm.from_mesh(part.data)
    assert all(e.is_manifold and e.is_contiguous for e in bm.edges)
    assert all(f.calc_area()>1e-9 for f in bm.faces);assert bm.calc_volume(signed=True)>0
    low=[min(v.co[i] for v in bm.verts) for i in range(3)];high=[max(v.co[i] for v in bm.verts) for i in range(3)]
    bm.free()
    for a,b in zip(low+high,[54*index,0,0,54*index+44,36,20]):near(a,b)
    measurements=[]
    for x0,y in ((10,12),(10,24),(34,12),(34,24)):
        x=54*index+x0
        near(cast(part,(x,y,25),(0,0,-1)).z,5)
        ds=[]
        for z in (6,12,19):
            for a in (.017,.7,1.4,2.2):
                c,s=math.cos(a),math.sin(a)
                p=cast(part,(x,y,z),(c,s,0));q=cast(part,(x,y,z),(-c,-s,0))
                near((p-q).length,diameter);near((p.x+q.x)/2,x);near((p.y+q.y)/2,y);ds.append((p-q).length)
        for i in range(24):
            a=i*2*math.pi/24+.01;r=diameter/2-.03
            near(cast(part,(x+r*math.cos(a),y+r*math.sin(a),25),(0,0,-1)).z,5)
        measurements.append(dict(center=[x,y,20],depth_mm=15,measured_diameters_mm=ds))
    # Letter recess exists and does not turn into a disconnected loose piece.
    engraved=[v.co.z for v in part.data.vertices if 54*index+14<v.co.x<54*index+30 and v.co.y<9 and 19<v.co.z<19.99]
    assert engraved;near(min(engraved),19.4)
    reports.append(dict(diameter_mm=diameter,closed_solid=True,bounds_mm=[low,high],holes=measurements,label_depth_mm=.6))
report=dict(file=NAME+'.stl',independent_STL_reimport=True,closed_components=3,dimensions_mm=[152,36,20],
    coupon_gap_mm=10,tests=reports,all_checks_passed=True,physical_fit_tested=False)
(OUT/(NAME+'_validation.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
print('THREE_COUPONS_VERIFIED',json.dumps(report))
