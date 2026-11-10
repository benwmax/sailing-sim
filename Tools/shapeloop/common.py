"""Shared helpers for the shape loop (docs/shape-loop). Runs inside Blender's Python (pip bpy or blender -b -P)."""
import json
import os

import bpy


def load_scene(path):
    """Opens a .blend, or imports an .fbx into an empty scene (the fleet boats: build_fleet.py writes fbx only)."""
    if path.endswith(".blend"):
        bpy.ops.wm.open_mainfile(filepath=path)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        for f in sorted(os.listdir(path)) if os.path.isdir(path) else [path]:
            f = os.path.join(path, f) if os.path.isdir(path) else f
            if f.lower().endswith(".fbx"):
                bpy.ops.import_scene.fbx(filepath=f)
    return bpy.context.scene


def load_sections(path):
    return json.load(open(path))


def section_of(name, sections):
    """First section whose object prefixes match the name; Blender's '.001' duplicates match their base name."""
    base = name.split(".")[0]
    for sec, spec in sections["sections"].items():
        if any(base == p or base.startswith(p) for p in spec["objects"]):
            return sec
    return "other"


def matches(name, prefix):
    base = name.split(".")[0]
    return base == prefix or base.startswith(prefix)


def mesh_objects(scene):
    return [o for o in scene.objects if o.type in ("MESH", "CURVE", "FONT") and o.visible_get() is not None]


def evaluated_mesh(o, dg):
    """World-space vertices and triangles of an object as evaluated (modifiers, curve bevels)."""
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    mw = o.matrix_world
    verts = [tuple(mw @ v.co) for v in me.vertices]
    tris = [tuple(t.vertices) for t in me.loop_triangles]
    ev.to_mesh_clear()
    return verts, tris
