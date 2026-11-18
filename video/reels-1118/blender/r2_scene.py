"""リール2 v2 の 3D（Blender 4.5 / Cycles）。曜日×時限の「空き教室の数」を柱の高さにした街。
  ../../blendervenv/bin/python r2_scene.py preview 0.8,4.0,7.0,10.5
  ../../blendervenv/bin/python r2_scene.py render          # 0〜11.8秒（0〜354 フレーム）
数字は schedule_final.db の 2026年度・後期、駿河台キャンパス64室で、授業が入っていない教室の数（README）。
柱の上や列の位置（画面の中の座標）を frames2/anchors.json に書き出し、HTML の文字をそこに合わせる。"""
import bpy, colorsys, json, math, os, sys
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "frames2")
FPS = 30
F0, F1 = 198, 354                    # v3：3D は正解のあと（6.6〜11.8 秒）だけ
DAYS = "月火水木金"
GRID = {"月": [49, 40, 42, 46, 51, 61], "火": [43, 30, 29, 33, 52, 57], "水": [38, 31, 24, 28, 48, 59],
        "木": [51, 37, 41, 44, 52, 58], "金": [37, 33, 34, 37, 52, 55]}
STEP = 1.3
def XY(d, p): return ((p - 3.5) * STEP, d * STEP)      # 時限が左右、曜日が奥行き（月が手前）
def HGT(v): return v * 0.06

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene; sc.render.fps = FPS


def srgb_lin(c): return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)
def hex_lin(h): return srgb_lin([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)])
STOPS = [(24, "#f08a4b"), (34, "#c9708a"), (44, "#4f7df0"), (61, "#8fdcf2")]   # 少ない＝橙 → 青 → 多い＝水色
def heat(v):
    for (a, ca), (b, cb) in zip(STOPS, STOPS[1:]):
        if v <= b:
            k = (v - a) / (b - a); A = [int(ca[i:i + 2], 16) for i in (1, 3, 5)]; B = [int(cb[i:i + 2], 16) for i in (1, 3, 5)]
            return srgb_lin([(A[j] + (B[j] - A[j]) * k) / 255 for j in range(3)])
    return hex_lin(STOPS[-1][1])


def mat(name, color, rough=0.4, emit=None, strength=0.0, coat=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1); p.inputs["Roughness"].default_value = rough
    p.inputs["Coat Weight"].default_value = coat
    p.inputs["Emission Color"].default_value = (*(emit or color), 1); p.inputs["Emission Strength"].default_value = strength
    return m


# ── 床・空 ──
bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 150, 0)); floor = bpy.context.object
floor.data.materials.append(mat("floor", hex_lin("#0b1a3a"), rough=0.3, coat=0.3))
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (*hex_lin("#123070"), 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.5

# ── 柱（はじめに手前から順に床の下からせり上がる） ──
cols = {}
for d, day in enumerate(DAYS):
    for p in range(1, 7):
        v = GRID[day][p - 1]; h = HGT(v); x, y = XY(d, p)
        bpy.ops.mesh.primitive_cube_add(size=1); o = bpy.context.object; o.name = f"c_{day}{p}"
        o.data.transform(Matrix.Translation((0, 0, 0.5))); o.scale = (1.0, 1.0, h); bpy.ops.object.transform_apply(scale=True)
        md = o.modifiers.new("bevel", "BEVEL"); md.width = 0.1; md.segments = 5; bpy.ops.object.shade_smooth()
        m = mat(f"m_{day}{p}", heat(v), rough=0.32, coat=0.5, strength=0.06); o.data.materials.append(m)
        t0 = 6.6 + (d * 6 + p) * 0.02                           # 6.6〜7.2 秒で手前から順に（v3）
        o.location = (x, y, -h - 0.05); o.keyframe_insert("location", frame=0); o.keyframe_insert("location", frame=int(t0 * FPS))
        o.location.z = 0; o.keyframe_insert("location", frame=int((t0 + 0.45) * FPS))
        cols[(day, p)] = (o, m, v, h)

def emit_key(m, frame, strength, color=None):
    p = m.node_tree.nodes["Principled BSDF"]
    if color is not None:
        p.inputs["Emission Color"].default_value = (*color, 1); p.inputs["Emission Color"].keyframe_insert("default_value", frame=frame)
    p.inputs["Emission Strength"].default_value = strength; p.inputs["Emission Strength"].keyframe_insert("default_value", frame=frame)

ORANGE, CYAN = hex_lin("#ff8a3d"), hex_lin("#3ad1e0")
def base_key(m, frame, color):
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1); p.inputs["Base Color"].keyframe_insert("default_value", frame=frame)
def dim(c, k=0.1): return tuple(x * k for x in c)
F = lambda t: int(t * FPS)
# v3：全体が見えたまま、注目する柱だけを残してほかを暗くする
#   7.3〜9.3 秒：正解の水曜3限（橙に光る）  9.5〜11.8 秒：5限・6限（青緑に光る）
for (day, p), (o, m, v, h) in cols.items():
    c = heat(v); wed3 = (day, p) == ("水", 3); late = p >= 5
    base_key(m, F(7.2), c); emit_key(m, F(7.2), 0.06, c)
    if wed3:
        base_key(m, F(7.45), ORANGE); emit_key(m, F(7.45), 3.0, ORANGE); emit_key(m, F(7.9), 1.3, ORANGE); emit_key(m, F(9.2), 1.3, ORANGE)
        base_key(m, F(9.2), ORANGE); base_key(m, F(9.55), dim(c)); emit_key(m, F(9.55), 0.0, c)
    else:
        base_key(m, F(7.45), dim(c)); emit_key(m, F(7.45), 0.0, c); base_key(m, F(9.2), dim(c))
        if late:
            base_key(m, F(9.55), c); emit_key(m, F(9.2), 0.0, c); emit_key(m, F(9.7), 0.6, CYAN); emit_key(m, F(11.8), 0.5, CYAN)
        else:
            base_key(m, F(9.55), dim(c))

# ── 光 ──
def area(name, loc, energy, size, color, target=(0, 2.6, 1.5)):
    bpy.ops.object.light_add(type="AREA", location=loc); L = bpy.context.object; L.name = name
    L.data.energy = energy; L.data.size = size; L.data.color = color
    d = Vector(target) - Vector(loc); L.rotation_euler = d.to_track_quat("-Z", "Y").to_euler(); L.visible_glossy = False
    return L
area("key", (-6, -6, 10), 3200, 8, (1.0, 0.93, 0.86))
area("rim", (8, 10, 7), 2200, 6, (0.55, 0.7, 1.0))
area("fill", (5, -10, 6), 400, 10, (0.8, 0.85, 1.0))

# ── カメラ ──
cx, cy = 0.0, 2 * STEP
bpy.ops.object.empty_add(location=(cx, cy, 1.4)); focus = bpy.context.object
bpy.ops.object.camera_add(location=(6, -9, 9)); cam = bpy.context.object; sc.camera = cam
cam.data.lens = 34; cam.data.dof.use_dof = True; cam.data.dof.focus_object = focus
c = cam.constraints.new("TRACK_TO"); c.target = focus; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
wx, wy = XY(2, 3)                                         # 水曜3限
KEYS = [  # (時刻, カメラ, 注目点, 絞り)  v3：寄らずに全体を見せたまま、ゆっくり回り込む
    (6.6, (1.8, -8.8, 15.0), (cx, cy + 0.2, 0.6), 8.0),
    (9.3, (0.3, -8.4, 14.4), (cx, cy + 0.2, 0.7), 8.0),
    (11.8, (-1.3, -8.0, 13.8), (cx, cy + 0.2, 0.8), 8.0),
]
for t, cl, fl, fs in KEYS:
    f = int(t * FPS)
    cam.location = cl; cam.keyframe_insert("location", frame=f)
    focus.location = fl; focus.keyframe_insert("location", frame=f)
    cam.data.dof.aperture_fstop = fs; cam.data.dof.keyframe_insert("aperture_fstop", frame=f)

# ── 書き出しの設定 ──
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
sc.cycles.samples = 16; sc.cycles.adaptive_threshold = 0.05; sc.cycles.use_denoising = True; sc.cycles.denoiser = "OPENIMAGEDENOISE"
sc.cycles.max_bounces = 4; sc.cycles.glossy_bounces = 2; sc.cycles.transmission_bounces = 0
sc.render.use_persistent_data = True
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 720, 1280, 100
sc.render.image_settings.file_format = "PNG"
os.makedirs(OUT, exist_ok=True)


def proj(v):
    p = world_to_camera_view(sc, cam, Vector(v)); return [round(p.x, 4), round(1 - p.y, 4)]

def anchors():                              # 水曜3限の柱の上、曜日（左端の外）、時限（手前の外）
    out = {}
    for f in range(F0, F1 + 1):
        sc.frame_set(f)
        out[f] = {"wed3": proj((wx, wy, HGT(24) + 0.3)),
                  "days": [proj((XY(d, 1)[0] - 1.2, XY(d, 1)[1], 0.2)) for d in range(5)],
                  "periods": [proj((XY(0, p)[0], -1.1, 0.2)) for p in range(1, 7)],
                  "mon6": proj((XY(0, 6)[0], 0, HGT(61) + 0.3))}
    json.dump(out, open(os.path.join(OUT, "anchors.json"), "w"))


mode = sys.argv[1]
if mode == "preview":
    sc.render.resolution_percentage = 50; sc.cycles.samples = 8
    for t in [float(x) for x in sys.argv[2].split(",")]:
        sc.frame_set(int(t * FPS)); sc.render.filepath = os.path.join(OUT, f"pv_{t}.png"); bpy.ops.render.render(write_still=True)
    anchors()
elif mode == "render":
    anchors()
    for f in range(F0, F1 + 1):
        path = os.path.join(OUT, f"f{f:04d}.png")
        if os.path.exists(path): continue
        sc.frame_set(f); sc.render.filepath = path; bpy.ops.render.render(write_still=True)
        print("コマ", f, flush=True)
