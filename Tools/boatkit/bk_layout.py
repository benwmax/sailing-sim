"""Place kit parts on a boat from a layout file, then dress it from its character sheet.

A layout (Tools/boatkit/layouts/<boat>.json) lists placements. Each placement names a kit part and where it goes:
  "at":   a socket in the boat's sockets file (Unreal cm, Y to starboard; converted here to Blender metres, Y to port),
  "pos":  or a position in Blender metres (X forward, Y to port, Z up from the design waterline),
  "offset": metres added to the position (boat frame),
  "z", "x": the part's up (mount normal) and forward axes in the boat frame (defaults: up, forward; "yaw" in degrees
            turns the part about its up axis),
  "snap": cast a ray from 0.5 m back along "snap_dir" (default -z) onto the hull mesh so the part sits on the moulding,
  "mirror": also place a copy reflected to the other side (Y negated, socket names _S <-> _P),
  "on":   {"part": <id of an earlier placement>, "socket": <its socket>, "attach": <this part's socket>} stacks a part
          onto another (a cam cleat on its riser, an outboard on its bracket),
  "opts": keyword options for the part builder (length, size),
  "id":   a name other placements can stack on.

The result is a list of placed objects, a placements.json (kit name, matrix) for instanced placement in Unreal, and
the merged kit mesh per boat for preview renders.
"""
import json
import math
import os

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

import bk_parts as P


def load_sockets(path):
    d = json.load(open(path))
    return {k: Vector((v[0] / 100.0, -v[1] / 100.0, v[2] / 100.0)) for k, v in d["sockets"].items()}


def _mirror_name(s):
    if s.endswith("_S"):
        return s[:-2] + "_P"
    if s.endswith("_P"):
        return s[:-2] + "_S"
    return s


def _basis(z, x, yaw):
    z = Vector(z).normalized()
    x = Vector(x)
    x = (x - z * x.dot(z))
    if x.length < 1e-6:
        x = Vector((0, 0, 1)) - z * z.z
    x.normalize()
    if yaw:
        x = Matrix.Rotation(math.radians(yaw), 3, z) @ x
    y = z.cross(x)
    return Matrix((x, y, z)).transposed()


def bvh_of(objs):
    import bmesh
    bm = bmesh.new()
    for o in objs:
        me = o.data.copy()
        me.transform(o.matrix_world)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


def _socket_world(ob, name):
    for c in ob.children:
        if c.name.split(".")[0] == f"SOCKET_{name}":
            return ob.matrix_world @ c.location
    raise KeyError(f"{ob.name} has no socket {name}")


def place(layout, sockets, hull_bvh, log=print):
    placed = {}
    records = []
    for entry in layout["parts"]:
        variants = [(entry, False)]
        if entry.get("mirror"):
            variants.append((entry, True))
        for e, mirrored in variants:
            pid = e.get("id", e["kit"]) + ("_mirror" if mirrored else "")
            ob = P.build(e["kit"], **e.get("opts", {}))
            ob.name = f"{pid}"
            flip = Vector((1, -1, 1)) if mirrored else Vector((1, 1, 1))
            zax = Vector(e.get("z", (0, 0, 1))) * flip
            xax = Vector(e.get("x", (1, 0, 0))) * flip
            yaw = e.get("yaw", 0.0) * (-1 if mirrored else 1)
            R = _basis(zax, xax, yaw)
            if "on" in e:
                on = e["on"]
                parent = placed[on["part"] + ("_mirror" if mirrored else "")]
                target = _socket_world(parent, on["socket"])
                M = R.to_4x4()
                local = Vector([c.location for c in ob.children if c.name.split(".")[0] == f"SOCKET_{on['attach']}"][0])
                M.translation = target - R @ local
                ob.matrix_world = M
            else:
                if "at" in e:
                    s = e["at"]
                    if mirrored:
                        s = _mirror_name(s)
                    pos = sockets[s].copy()
                    if mirrored and s == e["at"]:
                        pos.y = -pos.y
                else:
                    pos = Vector(e["pos"]) * flip
                pos += Vector(e.get("offset", (0, 0, 0))) * flip
                if e.get("snap", True) and hull_bvh is not None:
                    d = Vector(e.get("snap_dir", -zax)) * (flip if "snap_dir" in e else Vector((1, 1, 1)))
                    d.normalize()
                    hit, nrm, _, dist = hull_bvh.ray_cast(pos - d * 0.5, d, 1.5)
                    if hit is None:
                        log(f"Layout: {pid}: no hull under {tuple(round(c, 3) for c in pos)}, left unsnapped")
                    else:
                        pos = hit
                        if e.get("follow_normal", True) and "z" not in e:
                            R = _basis(nrm, xax, yaw)
                pos += R @ Vector((0, 0, e.get("lift", 0.0)))
                M = R.to_4x4()
                M.translation = pos
                ob.matrix_world = M
            placed[pid] = ob
            records.append({"id": pid, "kit": e["kit"], "opts": e.get("opts", {}),
                            "matrix": [list(r) for r in ob.matrix_world]})
    return placed, records


def write_placements(records, path):
    json.dump({"units": "blender metres, X forward, Y port, Z up", "placements": records}, open(path, "w"), indent=1)
