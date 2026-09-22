"""Independent STL reimport, topology and dimensional ray tests."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
NAME='experiment_plate_normal'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.wm.stl_import(filepath=str(OUT/(NAME+'.stl')))
obj=bpy.context.object
bm=bmesh.new();bm.from_mesh(obj.data)
remaining=set(bm.verts);components=0
while remaining:
    components+=1;queue=[remaining.pop()]
    while queue:
        v=queue.pop()
        for edge in v.link_edges:
            other=edge.other_vert(v)
            if other in remaining:remaining.remove(other);queue.append(other)
bounds=[[min(v.co[i] for v in bm.verts) for i in range(3)],
        [max(v.co[i] for v in bm.verts) for i in range(3)]]
report=dict(independently_reimported=True,connected_components=components,
    nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),
    inconsistent_edges=sum(not e.is_contiguous for e in bm.edges),
    degenerate_faces=sum(f.calc_area()<1e-9 for f in bm.faces),
    signed_volume_mm3=bm.calc_volume(signed=True),bounds_mm=bounds,
    triangles=len(bm.faces),dimensions_mm=[bounds[1][i]-bounds[0][i] for i in range(3)])
bm.free()
assert components==1 and report['signed_volume_mm3']>0
assert report['nonmanifold_edges']==report['inconsistent_edges']==report['degenerate_faces']==0
assert report['dimensions_mm']==[236,100,20],report
def cast(p,d):return obj.ray_cast(Vector(p),Vector(d),distance=500)
def near(a,b,tol=.002):assert abs(a-b)<tol,(a,b)
for x,y in [(2,2),(234,68),(41,99),(195,99),(118,80)]:
    hit,p,_,_=cast((x,y,25),(0,0,-1));assert hit;near(p.z,20)
for x,y in [(20,85),(216,85)]:assert not cast((x,y,25),(0,0,-1))[0]
# Confirm exact step positions and central tongue width.
for p,d,axis,value in [((39,85,10),(1,0,0),0,40),((197,85,10),(-1,0,0),0,196),
    ((20,80,10),(0,-1,0),1,70),((216,80,10),(0,-1,0),1,70),
    ((118,110,10),(0,-1,0),1,100)]:
    hit,point,_,_=cast(p,d);assert hit;near(point[axis],value)
holes=[]
for x in (112,124):
    for y in (69.5,93.5):
        for a in range(24):
            angle=a*2*math.pi/24+.013
            hit,p,_,_=cast((x+1.22*math.cos(angle),y+1.22*math.sin(angle),25),(0,0,-1))
            assert hit;near(p.z,5)
        diameters=[]
        for z in (6,12,19):
            for a in (.017,.6,1.2,2.1):
                dx,dy=math.cos(a),math.sin(a)
                hit,p1,_,_=cast((x,y,z),(dx,dy,0));assert hit
                hit,p2,_,_=cast((x,y,z),(-dx,-dy,0));assert hit
                near((p1-p2).length,2.5)
                near((p1.x+p2.x)/2,x);near((p1.y+p2.y)/2,y)
                diameters.append((p1-p2).length)
        hit,p,_,_=cast((x,y,-1),(0,0,1));assert hit;near(p.z,0)
        holes.append(dict(entry_center_mm=[x,y,20],depth_mm=15,remaining_floor_mm=5,
            diameter_measurements_mm=diameters,entrance_probe_count=24))
expected_volume=(236*100-2*40*30)*20-4*128*.5*1.25**2*math.sin(2*math.pi/128)*15
near(report['signed_volume_mm3'],expected_volume,.1)
report.update(file=NAME+'.stl',nominal_hole_diameter_mm=2.5,holes=holes,hole_spacing_xy_mm=[12,24],checks_passed=True,
    physical_fit_tested=False,load_tested=False,sliced=False)
# Compare all surfaces outside the enlarged bores with the previous plate.
old_path=OUT/'archive/plate_versions_before_normal_D2p5_20260922/s102_front/Motor_plate_S102K_236x100x20_D2p4.stl'
bpy.ops.wm.stl_import(filepath=str(old_path));old=bpy.context.object
max_error=0;probes=0
for source,target in ((old,obj),(obj,old)):
    for vertex in source.data.vertices:
        p=vertex.co
        if any(math.hypot(p.x-x,p.y-y)<1.3 and p.z>=4.99 for x in (112,124) for y in (69.5,93.5)):continue
        hit,point,_,_=target.closest_point_on_mesh(p);assert hit
        error=(point-p).length;assert error<.002
        max_error=max(max_error,error);probes+=1
report.update(unchanged_surface_probes=probes,unchanged_surface_max_error_mm=max_error)
(OUT/(NAME+'_validation.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ALL_CHECKS_PASSED',json.dumps(report))
