def mesh_object(name, verts, faces):
    mesh = bpy.data.meshes.new(name + '_mesh')
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    return obj

def boolean(target, operand, operation='DIFFERENCE'):
    bpy.context.view_layer.objects.active = target
    mod = target.modifiers.new(operation, 'BOOLEAN')
    mod.operation = operation
    mod.solver = 'EXACT'
    mod.object = operand
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(operand, do_unlink=True)

def cube(name, dimensions, location):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj

def cylinder_between(name, a, b, r, segments=64):
    a, b = (Vector(a), Vector(b))
    bpy.ops.mesh.primitive_cylinder_add(vertices=segments, radius=r, depth=(b - a).length, location=(a + b) / 2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = (b - a).to_track_quat('Z', 'Y').to_euler()
    return obj

def cleanup(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-05)
    boundary = [e for e in bm.edges if e.is_boundary]
    if len(boundary) == 3 and len({v for e in boundary for v in e.verts}) == 3:
        bmesh.ops.holes_fill(bm, edges=boundary, sides=3)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

def mesh_report(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    remaining = set(bm.verts)
    components = 0
    while remaining:
        components += 1
        pending = [remaining.pop()]
        while pending:
            v = pending.pop()
            for e in v.link_edges:
                other = e.other_vert(v)
                if other in remaining:
                    remaining.remove(other)
                    pending.append(other)
    bounds = [[min((v.co[i] for v in bm.verts)) for i in range(3)], [max((v.co[i] for v in bm.verts)) for i in range(3)]]
    result = {'nonmanifold_edges': sum((not e.is_manifold for e in bm.edges)), 'inconsistent_edges': sum((not e.is_contiguous for e in bm.edges)), 'connected_components': components, 'signed_volume_mm3': bm.calc_volume(signed=True), 'bounds_mm': bounds, 'dimensions_mm': [bounds[1][i] - bounds[0][i] for i in range(3)]}
    bm.free()
    obj.data.calc_loop_triangles()
    result['triangles'] = len(obj.data.loop_triangles)
    return result

def export_stl(obj, path):
    obj.data.calc_loop_triangles()
    with path.open('wb') as stream:
        stream.write(b'Reel height test; units mm; FR12-S102-K'.ljust(80, b'\x00'))
        stream.write(struct.pack('<I', len(obj.data.loop_triangles)))
        for tri in obj.data.loop_triangles:
            a, b, c = [obj.matrix_world @ obj.data.vertices[i].co for i in tri.vertices]
            normal = (b - a).cross(c - a).normalized()
            stream.write(struct.pack('<12fH', *normal, *a, *b, *c, 0))

def material(name, color, roughness=0.4, metallic=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    return mat

def aim(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat('-Z', 'Y').to_euler()