"""リール3 v2 の 3D（Blender 4.5 / Cycles）。「空きコマ、みんな何してる？」の棒が床の下からせり上がる。
  ../../blendervenv/bin/python r3_scene.py preview 2.5,4.0,6.4,8.0      # 下書き（小さく・少ないサンプル）
  ../../blendervenv/bin/python r3_scene.py render                        # 本番（720×1280・16サンプル。約9秒/コマ）
リールの時刻 t（秒）＝ フレーム t×30。3D を描くのは 1.9〜8.6 秒（57〜258 フレーム）。
棒の上の位置（画面の中の座標）を frames3/anchors.json に書き出し、HTML の文字をそこに合わせる。
数字はアプリの匿名の質問「何に使う？」の回答140件（個人学習57・休憩19・グループワーク11・打合せ9・その他4%）。"""
import bpy, bmesh, json, math, os, random, sys
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "frames3")
FPS = 30
F0, F1 = 57, 258                       # 3D を描く範囲
PCT = [57, 19, 11, 9, 4]               # 1位〜5位
REVEAL = {5: 2.2, 4: 3.0, 3: 3.8, 2: 4.6, 1: 5.9}   # 棒が上がりはじめる時刻（HTML と同じ）
X = [-3.2, -1.6, 0.0, 1.6, 3.2]       # 1位が左、5位が右
H = [p * 0.075 for p in PCT]           # 高さ（57% → 4.3）
random.seed(3)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS


def mat(name, color, rough=0.45, emit=None, strength=0.0, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1); p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal; p.inputs["Coat Weight"].default_value = coat
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1); p.inputs["Emission Strength"].default_value = strength
    return m


def srgb(h):                            # '#ff8a3d' → 線形の色
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


def rounded_box(name, size, bevel=0.08, origin_bottom=True):
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.object; o.name = name
    o.data.transform(__import__("mathutils").Matrix.Translation((0, 0, 0.5 if origin_bottom else 0)))
    o.scale = size; bpy.ops.object.transform_apply(scale=True)
    md = o.modifiers.new("bevel", "BEVEL"); md.width = bevel; md.segments = 5
    bpy.ops.object.shade_smooth()
    return o


# ── 床と奥の壁（ひとつながりの紺の背景） ──
bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 150, 0)); floor = bpy.context.object
floor.data.materials.append(mat("floor", srgb("#0b1a3a"), rough=0.32, coat=0.3))
# 奥の壁は置かない（床と壁の境目の線が見えるため）。奥は空の色（紺）に溶かす
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (*srgb("#123070"), 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.55

# ── 棒（床の下からせり上がる。拡大で角の丸みがゆがまないよう、位置だけを動かす） ──
blue, orange = srgb("#3d74ff"), srgb("#ff8a3d")
bars = []
for i, (x, h) in enumerate(zip(X, H)):
    rank = i + 1
    b = rounded_box(f"bar{rank}", (1.05, 1.05, h), bevel=0.12)
    col = orange if rank == 1 else blue
    b.data.materials.append(mat(f"bar{rank}", col, rough=0.3, coat=0.6, emit=col, strength=0.15 if rank == 1 else 0.05))
    b.location = (x, 0, -h - 0.05)
    t = REVEAL[rank]; up = 0.9 if rank == 1 else 0.55
    b.keyframe_insert("location", frame=1); b.keyframe_insert("location", frame=int(t * FPS))
    b.location.z = 0.0; b.keyframe_insert("location", frame=int((t + up) * FPS))
    bars.append(b)

# ── 棒の上の小物（それぞれの使い方） ──
def parent(o, b, h):
    o.parent = b; o.location = (o.location.x, o.location.y, o.location.z + h)


def books(b, h):                        # 個人学習：本を3冊
    cols = ["#e8eef8", "#4f8cff", "#f6a35c"]
    for k in range(3):
        o = rounded_box(f"book{k}", (0.8 - k * 0.06, 0.58, 0.14), bevel=0.02)
        o.data.materials.append(mat(f"book{k}", srgb(cols[k]), rough=0.55))
        o.location = (0.02 * k, 0, 0.145 * k); o.rotation_euler.z = math.radians([-8, 6, -3][k]); parent(o, b, h)


def cup(b, h):                          # 休憩：マグカップ
    bpy.ops.mesh.primitive_cylinder_add(radius=0.26, depth=0.42, vertices=48); o = bpy.context.object
    o.location = (0, 0, 0.21); o.data.materials.append(mat("cup", srgb("#f4f1ea"), rough=0.25, coat=0.5)); bpy.ops.object.shade_smooth(); parent(o, b, h)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.22, depth=0.02, vertices=48); c = bpy.context.object
    c.location = (0, 0, 0.405); c.data.materials.append(mat("coffee", srgb("#3a2414"), rough=0.15)); parent(c, b, h)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.13, minor_radius=0.035, location=(0.29, 0, 0.22), rotation=(math.radians(90), 0, 0))
    t = bpy.context.object; t.data.materials.append(bpy.data.materials["cup"]); bpy.ops.object.shade_smooth(); parent(t, b, h)


def people(b, h):                       # グループワーク：3人（顔の無い駒）
    for k, (dx, dy) in enumerate([(-0.25, 0.1), (0.25, 0.1), (0, -0.2)]):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.13, depth=0.26, vertices=32, location=(dx, dy, 0.13)); o = bpy.context.object
        md = o.modifiers.new("bevel", "BEVEL"); md.width = 0.06; md.segments = 4; bpy.ops.object.shade_smooth()
        o.data.materials.append(mat(f"p{k}", srgb(["#e8eef8", "#9fc1ff", "#ffd5ad"][k]), rough=0.5)); parent(o, b, h)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1, location=(dx, dy, 0.36)); s = bpy.context.object; bpy.ops.object.shade_smooth()
        s.data.materials.append(bpy.data.materials[f"p{k}"]); parent(s, b, h)


def bubbles(b, h):                      # 打合せ：ふきだし2つ
    for k, (dx, z, c) in enumerate([(-0.15, 0.25, "#e8eef8"), (0.2, 0.55, "#9fc1ff")]):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.26, depth=0.1, vertices=48, location=(dx, 0, z), rotation=(math.radians(90), 0, 0)); o = bpy.context.object
        md = o.modifiers.new("bevel", "BEVEL"); md.width = 0.04; md.segments = 4; bpy.ops.object.shade_smooth()
        o.data.materials.append(mat(f"bub{k}", srgb(c), rough=0.4)); parent(o, b, h)


def star(b, h):                         # その他：きらっとした粒
    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.2, subdivisions=1, location=(0, 0, 0.3)); o = bpy.context.object
    o.data.materials.append(mat("star", srgb("#ffe08a"), rough=0.2, emit=srgb("#ffd36b"), strength=1.5)); parent(o, b, h)


for fn, b, h in zip([books, cup, people, bubbles, star], bars, H):
    fn(b, h)

# ── 1位の紙ふぶき ──
conf_cols = ["#ff8a3d", "#ffd5ad", "#4f8cff", "#3ad1e0", "#ffffff"]
for k in range(70):
    bpy.ops.mesh.primitive_plane_add(size=0.12); o = bpy.context.object
    o.data.materials.append(mat(f"cf{k}", srgb(conf_cols[k % 5]), rough=0.5, emit=srgb(conf_cols[k % 5]), strength=0.4))
    a = random.uniform(0, 2 * math.pi); r = random.uniform(0.2, 2.6)
    start = Vector((X[0] + math.cos(a) * 0.3, math.sin(a) * 0.3, H[0] + 0.6))
    end = Vector((X[0] + math.cos(a) * r, math.sin(a) * r * 0.6, random.uniform(0.0, H[0] * 0.6)))
    f0 = int(5.95 * FPS); f1 = f0 + random.randint(45, 80)
    o.location = start; o.scale = (0.001,) * 3; o.keyframe_insert("location", frame=f0 - 1); o.keyframe_insert("scale", frame=f0 - 1)
    o.scale = (1, 1, 1); o.keyframe_insert("scale", frame=f0)
    peak = start.lerp(end, 0.35); peak.z = start.z + random.uniform(0.6, 1.4)
    o.location = peak; o.keyframe_insert("location", frame=f0 + 10)
    o.location = end; o.keyframe_insert("location", frame=f1)
    o.rotation_euler = (0, 0, 0); o.keyframe_insert("rotation_euler", frame=f0)
    o.rotation_euler = (random.uniform(3, 9), random.uniform(3, 9), random.uniform(0, 6)); o.keyframe_insert("rotation_euler", frame=f1)

# ── 光 ──
def area(name, loc, energy, size, color, target=(0, 0, 1.5)):
    bpy.ops.object.light_add(type="AREA", location=loc); L = bpy.context.object; L.name = name
    L.data.energy = energy; L.data.size = size; L.data.color = color
    d = Vector(target) - Vector(loc); L.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    L.visible_glossy = False          # 床に光の四角が映り込まないように
    return L


area("key", (-5, -7, 8), 2600, 6, (1.0, 0.92, 0.85))
area("rim", (6, 6, 6), 1800, 5, (0.55, 0.7, 1.0))
area("fill", (3, -9, 6), 260, 10, (0.8, 0.85, 1.0))

# ── カメラ（5位から1位へ横に動き、最後に引いて全体） ──
bpy.ops.object.empty_add(location=(X[4], 0, 0.6)); focus = bpy.context.object; focus.name = "focus"
bpy.ops.object.camera_add(location=(X[4] + 1.5, -6.5, 1.6)); cam = bpy.context.object; sc.camera = cam
cam.data.lens = 42; cam.data.dof.use_dof = True; cam.data.dof.focus_object = focus; cam.data.dof.aperture_fstop = 2.2
c = cam.constraints.new("TRACK_TO"); c.target = focus; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
KEYS = [  # (時刻, カメラ位置, 注目する点)
    (1.9, (X[4] + 1.8, -6.6, 1.5), (X[4], 0, 0.4)),
    (2.9, (X[4] + 0.6, -6.4, 1.6), (X[4] - 0.4, 0, 0.6)),
    (3.7, (X[3] + 0.6, -6.6, 1.8), (X[3], 0, 0.7)),
    (4.5, (X[2] + 0.4, -6.8, 2.0), (X[2], 0, 0.9)),
    (5.3, (X[1] + 0.4, -7.0, 2.4), (X[1], 0, 1.3)),
    (6.1, (X[0] + 1.2, -7.6, 2.2), (X[0], 0, 2.6)),
    (7.0, (X[0] + 2.4, -11.0, 3.6), (X[0] + 1.4, 0, 2.3)),
    (8.6, (0.3, -19.5, 6.2), (0.0, 0, 2.0)),
]
for t, cl, fl in KEYS:
    cam.location = cl; cam.keyframe_insert("location", frame=int(t * FPS))
    focus.location = fl; focus.keyframe_insert("location", frame=int(t * FPS))

# ── 書き出しの設定 ──
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
sc.cycles.samples = 16; sc.cycles.adaptive_threshold = 0.05; sc.cycles.use_denoising = True; sc.cycles.denoiser = "OPENIMAGEDENOISE"
sc.cycles.max_bounces = 4; sc.cycles.glossy_bounces = 2; sc.cycles.transmission_bounces = 0
sc.render.use_persistent_data = True
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 720, 1280, 100
sc.render.image_settings.file_format = "PNG"
os.makedirs(OUT, exist_ok=True)


def anchors():                          # 棒の上（小物の少し上）の画面の座標。左上が (0,0)
    out = {}
    for f in range(F0, F1 + 1):
        sc.frame_set(f); row = []
        for b, h in zip(bars, H):
            p = world_to_camera_view(sc, cam, b.matrix_world @ Vector((0, 0, h + 0.95)))
            row.append([round(p.x, 4), round(1 - p.y, 4), round(p.z, 3)])
        out[f] = row
    json.dump(out, open(os.path.join(OUT, "anchors.json"), "w"))


mode = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else sys.argv[1]
if mode == "preview":
    ts = [float(x) for x in sys.argv[-1].split(",")]
    sc.render.resolution_percentage = 50; sc.cycles.samples = 8
    for t in ts:
        sc.frame_set(int(t * FPS)); sc.render.filepath = os.path.join(OUT, f"pv_{t}.png"); bpy.ops.render.render(write_still=True)
    anchors()
elif mode == "render":
    anchors()
    for f in range(F0, F1 + 1):
        path = os.path.join(OUT, f"f{f:04d}.png")
        if os.path.exists(path): continue                 # 止めても続きから
        sc.frame_set(f); sc.render.filepath = path; bpy.ops.render.render(write_still=True)
        print("コマ", f, flush=True)
