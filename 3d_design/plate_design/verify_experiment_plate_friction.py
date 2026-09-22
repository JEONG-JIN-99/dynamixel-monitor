"""Independent exported STL audit and conservative full-rotation envelope checks."""
import bpy,bmesh,json,math,hashlib
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
OUT=Path(__file__).resolve().parent;NAME='experiment_plate_friction'
m=json.loads((OUT/(NAME+'_design.json')).read_text())
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.wm.stl_import(filepath=str(OUT/(NAME+'.stl')));body=bpy.context.object
def near(a,b,t=.004):assert abs(a-b)<t,(a,b)
bm=bmesh.new();bm.from_mesh(body.data)
bad=sum(not e.is_manifold for e in bm.edges);orient=sum(not e.is_contiguous for e in bm.edges)
zero=sum(f.calc_area()<1e-9 for f in bm.faces);volume=bm.calc_volume(signed=True)
assert bad==orient==zero==0,(bad,orient,zero);assert volume>0
remaining=set(bm.verts);parts=0
while remaining:
    parts+=1;queue=[remaining.pop()]
    while queue:
        v=queue.pop()
        for e in v.link_edges:
            w=e.other_vert(v)
            if w in remaining:remaining.remove(w);queue.append(w)
assert parts==1
bounds=[[min(v.co[i] for v in bm.verts) for i in range(3)],[max(v.co[i] for v in bm.verts) for i in range(3)]]
bm.free()
dims=[bounds[1][i]-bounds[0][i] for i in range(3)]
for a,b in zip(dims,[236,100,50.5]):near(a,b)
def cast(p,d,length=500):
    ok,pt,_,_=body.ray_cast(Vector(p),Vector(d),distance=length)
    return pt if ok else None
def zhit(x,y,start,want):
    p=cast((x,y,start),(0,0,-1));assert p is not None;near(p.z,want)
zhit(118,22,60,50.5)
for x,y in [(2,2),(234,68),(41,99),(195,99),(60,50)]:zhit(x,y,60,20)
for x,y in [(20,85),(216,85)]:assert cast((x,y,60),(0,0,-1)) is None
holes=[]
for x,y in m['hole_centers_xy']:
    zhit(x,y,60,35.5)
    for i in range(32):
        a=2*math.pi*i/32+.01;zhit(x+1.22*math.cos(a),y+1.22*math.sin(a),60,35.5)
    diameters=[]
    for z in (36,42,50):
        for a in (.017,.7,1.4,2.2):
            c,s=math.cos(a),math.sin(a)
            p=cast((x,y,z),(c,s,0));q=cast((x,y,z),(-c,-s,0));assert p is not None and q is not None
            near((p-q).length,2.5);near((p.x+q.x)/2,x);near((p.y+q.y)/2,y)
            diameters.append((p-q).length)
    holes.append(dict(center=[x,y,50.5],depth=15,diameters_mm=diameters))
G=m['guide_groove_x'];GY,GZ=m['guide_center_yz']
guide=[]
for a in (.02,.15,.3,.5,.8,1.2,1.55):
    c,s=math.cos(a),math.sin(a)
    p=cast((G,GY+20*c,GZ+20*s),(0,-c,-s));assert p is not None
    radius=math.hypot(p.y-GY,p.z-GZ);near(radius,8,.006);guide.append(radius)
zhit(G+4,GY,60,46)
# A 2mm descending rope clears the plate and foot below the guide.
for i in range(48):
    a=2*math.pi*i/48
    assert cast((G+math.cos(a),99+math.sin(a),27),(0,0,-1),30) is None
for z in (5,15,25):
    p=cast((G,105,z),(0,-1,0));assert p is not None;near(p.y,96)

body.data.calc_loop_triangles()
tri_boxes=[]
for tri in body.data.loop_triangles:
    vs=[body.data.vertices[i].co for i in tri.vertices]
    tri_boxes.append(([min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]))
def bvh(ob):
    ob.data.calc_loop_triangles()
    return BVHTree.FromPolygons([ob.matrix_world@v.co for v in ob.data.vertices],[t.vertices[:] for t in ob.data.loop_triangles],all_triangles=True)
plate_bvh=bvh(body);reels=[]
for model,waist in [('w350',83.6),('w210',61.2)]:
    path=OUT.parent/'reel_design'/f'Reel_{model}.stl'
    bpy.ops.wm.stl_import(filepath=str(path));reel=bpy.context.object
    # Radial envelope encloses every vertex and every triangle at every rotation.
    radius=max(math.hypot(v.co.x,v.co.y) for v in reel.data.vertices)
    zmin=min(v.co.z for v in reel.data.vertices);zmax=max(v.co.z for v in reel.data.vertices)
    base=m['reel_base_x'];cy=m['mount_center'][1];h=m['axis_height']
    low=[base+zmin,cy-radius,h-radius];high=[base+zmax,cy+radius,h+radius]
    overlaps=[]
    for i,(lo,hi) in enumerate(tri_boxes):
        if all(lo[j]<=high[j]+1e-5 and hi[j]>=low[j]-1e-5 for j in range(3)):overlaps.append(i)
    # No printed triangle may enter the entire conservative swept bounding box.
    assert not overlaps,('swept envelope intersects plate',model,len(overlaps))
    # Representative positions also checked directly using the actual final mesh.
    for angle in (0,math.pi/2,math.pi,3*math.pi/2):
        reel.matrix_world=Matrix.Translation((base,cy,h))@Matrix.Rotation(math.pi/2,4,'Y')@Matrix.Rotation(angle,4,'Z')
        assert not plate_bvh.overlap(bvh(reel)),('actual reel triangle overlap',model,angle)
    waist_clear=h-waist/2-(GZ+10);assert waist_clear>3
    R=waist/2+1;r=9
    phi=math.atan2(GZ-h,GY-cy)+math.acos((R-r)/math.hypot(GY-cy,GZ-h))
    a=Vector((G,cy+R*math.cos(phi),h+R*math.sin(phi)))
    b=Vector((G,GY+r*math.cos(phi),GZ+r*math.sin(phi)))
    direction=b-a
    # Free rope span lies outside the printed part until designated contact.
    assert cast(a,direction.normalized(),direction.length-.05) is None
    reels.append(dict(file=path.name,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        max_radius_mm=radius,waist_diameter_mm=waist,waist_min_z=h-waist/2,
        waist_above_guide_mm=waist_clear,rim_min_z=h-radius,rim_above_plate_mm=h-radius-20,
        full_rotation_swept_envelope_clear=True,swept_envelope_bounds=[low,high],
        actual_mesh_intersections_at_quarter_turns=0,nominal_contact_angle_deg=math.degrees(phi)))
    bpy.data.objects.remove(reel,do_unlink=True)
report=dict(file=NAME+'.stl',independent_STL_reimport=True,closed_components=parts,
    nonmanifold_edges=bad,inconsistent_edges=orient,degenerate_faces=zero,volume_mm3=volume,
    bounds_mm=bounds,dimensions_mm=dims,motor_mount_holes=holes,guide_root_radius_samples_mm=guide,
    rope_drop_clear=True,reels=reels,all_checks_passed=True,physical_fit_tested=False,
    load_tested=False,sliced=False,assembly_basis=m['assumptions'])
(OUT/(NAME+'_validation.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ALL_FRICTION_CHECKS_PASSED',json.dumps(report))
