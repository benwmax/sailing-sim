import bpy, sys, math, os
from mathutils import Vector
out = sys.argv[sys.argv.index("--")+1]
bpy.ops.wm.read_factory_settings(use_empty=True)
for n in ("SM_J22_Hull","SM_J22_Mast","SM_J22_Boom","SM_J22_Rudder"):
    bpy.ops.import_scene.fbx(filepath=f"/Users/ben/myProjects/sailing-sim/Artifacts/models/{n}.fbx")
cols = {"Topsides":(0.9,0.9,0.88,1),"Bootstripe":(0.02,0.05,0.25,1),"CoveStripe":(0.02,0.05,0.25,1),"Antifouling":(0.04,0.06,0.12,1),"Keel":(0.04,0.06,0.12,1),
        "Deck":(0.88,0.88,0.85,1),"NonSkid":(0.75,0.75,0.72,1),"CabinWindow":(0.03,0.03,0.04,1),"Stainless":(0.8,0.8,0.82,1),"Aluminium":(0.7,0.7,0.72,1),
        "BlackPlastic":(0.02,0.02,0.02,1),"Wood":(0.45,0.28,0.12,1),"Graphics":(0.7,0.05,0.05,1),"Rubrail":(0.1,0.1,0.1,1)}
for m in bpy.data.materials:
    base = m.name.split(".")[0]
    if base in cols: m.diffuse_color = cols[base]
# place parts: mast/boom/rudder were exported about their origin: put them back
import json
s = json.load(open("/Users/ben/myProjects/sailing-sim/Artifacts/models/J22_sockets.json"))["sockets"]
def ue(p): return Vector((p[0]/100, -p[1]/100, p[2]/100))
for o in bpy.data.objects:
    if o.name.startswith("SM_J22_Mast"): o.location = ue(s["MastStep"]) - Vector((0,0,0.03))
    if o.name.startswith("SM_J22_Boom"): o.location = Vector((0.95,0,1.45))
    if o.name.startswith("SM_J22_Rudder"): o.location = Vector((ue(s["RudderStock"]).x,0,0))
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "MATERIAL"
sc.display.shading.show_cavity = True
sc.render.resolution_x, sc.render.resolution_y = 1200, 800
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 35
views = {"stbd_bow": ((6.5,-6.0,2.6),(0.5,0,0.6)), "cockpit": ((-5.0,-2.2,2.6),(-0.5,0,0.5)), "profile": ((0,-13,0.6),(0,0,2.0)), "deck": ((0.5,-0.01,9),(0.2,0,0))}
for name,(pos,tgt) in views.items():
    cam.location = pos
    d = Vector(tgt)-Vector(pos); cam.rotation_euler = d.to_track_quat('-Z','Y').to_euler()
    if name=="profile": cam.data.lens = 24
    elif name=="deck": cam.data.lens=28
    else: cam.data.lens=35
    sc.render.filepath = os.path.join(out, f"j22_{name}.png"); bpy.ops.render.render(write_still=True)
