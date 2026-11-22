"""リール1 v3「空きコマあるある」の 3D（Blender 4.5 / Cycles）。校舎の廊下と教室のドア、壁の時計、空いている教室。
  <blendervenv>/bin/python r1_corridor.py preview 0.9,2.6,3.9,5.2,6.6     # 下書き（小さく・少ないサンプル）
  <blendervenv>/bin/python r1_corridor.py render                           # 本番（720×1280。frames1/。止めても続きから）
  <blendervenv>/bin/python r1_corridor.py room                             # 空いている教室の1枚（frames1/room.png）
リールの時刻 t（秒）＝ フレーム t×30。3D を描くのは 0〜7.2 秒（0〜216 フレーム）。
  0〜1.9 秒   廊下を進む（つかみの文字は HTML で重ねる）
  1.9〜5.9 秒 ドアを3つ回る（S503・S602・142。「授業中」のはんこは HTML。位置は frames1/anchors.json）
  5.95〜7.2 秒 壁の時計（休み時間が終わる）
教室の名前は実在するが、「授業中」は演出。人・大学のロゴ・実在の会社のロゴは置かない。"""
import bpy, json, math, os, sys
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "frames1")
FONT = os.path.join(HERE, "..", "fonts", "NotoSansCJKjp-Black.otf")
FPS = 30
F0, F1 = 0, 216
ROOMS = ["S503", "S602", "142"]
DY = [8.0, 12.0, 16.0]                 # 主役のドア3つ（左の壁）
W, HGT, LEN = 2.8, 2.75, 40.0          # 廊下の幅・高さ・長さ
XL, XR = -W / 2, W / 2

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS


def srgb(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


def mat(name, color, rough=0.5, emit=None, strength=0.0, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1); p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal; p.inputs["Coat Weight"].default_value = coat
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1); p.inputs["Emission Strength"].default_value = strength
    return m


def box(name, size, loc, m, bevel=0.0, rot=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object; o.name = name; o.scale = size
    if rot: o.rotation_euler = rot
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        md = o.modifiers.new("bevel", "BEVEL"); md.width = bevel; md.segments = 3
    o.data.materials.append(m)
    return o


M_FLOOR = mat("floor", srgb("#8f9aa6"), rough=0.14, coat=0.6)
M_WALL = mat("wall", srgb("#cfcabf"), rough=0.8)
M_WAIN = mat("wain", srgb("#3f5878"), rough=0.55)
M_CEIL = mat("ceil", srgb("#d9d8d2"), rough=0.9)
M_DOOR = mat("door", srgb("#9a6a3c"), rough=0.38, coat=0.3)          # 木目調の明るい茶
M_FRAME = mat("frame", srgb("#39424f"), rough=0.4, metal=0.6)
M_METAL = mat("metal", srgb("#d5d9de"), rough=0.25, metal=1.0)
M_PLATE = mat("plate", srgb("#ffffff"), rough=0.4, emit=srgb("#ffffff"), strength=0.05)
M_INK = mat("ink", srgb("#0b1730"), rough=0.6)
M_GLASS_ON = mat("glass_on", srgb("#ffe9c2"), rough=0.5, emit=srgb("#ffc77a"), strength=2.2)   # 授業中＝中の明かりがついている
M_GLASS_OFF = mat("glass_off", srgb("#3a4658"), rough=0.2, coat=0.6)
M_PANEL = mat("panel", srgb("#ffffff"), rough=0.6, emit=srgb("#fff6e6"), strength=2.5)
M_BOARD = mat("pin", srgb("#b58c5a"), rough=0.9)
M_PAPER = mat("paper", srgb("#f4f1ea"), rough=0.8)

# ── 廊下 ──
box("floor", (W, LEN, 0.1), (0, LEN / 2 - 2, -0.05), M_FLOOR)
box("ceil", (W, LEN, 0.1), (0, LEN / 2 - 2, HGT + 0.05), M_CEIL)
for x, nm in ((XL - 0.05, "wallL"), (XR + 0.05, "wallR")):
    box(nm, (0.1, LEN, HGT), (x, LEN / 2 - 2, HGT / 2), M_WALL)
    s = 1 if x < 0 else -1
    box(nm + "_wain", (0.02, LEN, 0.95), (x + s * 0.06, LEN / 2 - 2, 0.475), M_WAIN)     # 腰壁
    box(nm + "_rail", (0.03, LEN, 0.04), (x + s * 0.065, LEN / 2 - 2, 0.97), M_FRAME)
box("end", (W, 0.1, HGT), (0, LEN - 2, HGT / 2), M_WALL)
box("endwin", (1.4, 0.02, 1.3), (0, LEN - 2.06, 1.6), mat("endwin", srgb("#cfe4ff"), emit=srgb("#cfe4ff"), strength=2.0))   # つきあたりの窓
box("back", (W, 0.1, HGT), (0, -2, HGT / 2), M_WALL)

# 天井の明かり（3m おき）
for k in range(13):
    y = 1.0 + k * 3.0
    box(f"panel{k}", (0.5, 1.3, 0.02), (0, y, HGT - 0.012), M_PANEL)
    bpy.ops.object.light_add(type="AREA", location=(0, y, HGT - 0.06)); L = bpy.context.object
    L.data.shape = "RECTANGLE"; L.data.size = 0.5; L.data.size_y = 1.3; L.data.energy = 30; L.data.color = (1.0, 0.95, 0.88)


def text(name, s, loc, size, rot, m):
    bpy.ops.object.text_add(location=loc, rotation=rot); o = bpy.context.object; o.name = name
    o.data.body = s; o.data.font = bpy.data.fonts.load(FONT, check_existing=True)
    o.data.size = size; o.data.align_x = "CENTER"; o.data.align_y = "CENTER"; o.data.extrude = 0.002
    o.data.materials.append(m)
    return o


def door(y, side, label=None, lit=True, hero=False):
    """side=-1 は左の壁、+1 は右の壁。ドアは壁の面から少しへこませる"""
    x = (XL if side < 0 else XR)
    s = -side                                   # 廊下の内側へ向かう向き
    xf = x + s * 0.012
    box("dframe", (0.06, 1.06, 2.16), (x + s * 0.03, y, 1.08), M_FRAME, bevel=0.008)
    box("dleaf", (0.05, 0.92, 2.05), (x + s * 0.05, y, 1.035), M_DOOR, bevel=0.006)
    box("dwin", (0.012, 0.3, 0.95), (x + s * 0.078, y + 0.22 * side * -1, 1.45), M_GLASS_ON if lit else M_GLASS_OFF, bevel=0.004)
    box("dwinf", (0.016, 0.36, 1.01), (x + s * 0.074, y + 0.22 * side * -1, 1.45), M_FRAME, bevel=0.004)
    box("dkick", (0.012, 0.92, 0.22), (x + s * 0.077, y, 0.13), M_METAL)
    # レバーハンドル
    hy = y - 0.36 * side * -1
    box("hbase", (0.015, 0.05, 0.2), (x + s * 0.082, hy, 1.0), M_METAL, bevel=0.004)
    box("hlever", (0.02, 0.14, 0.022), (x + s * 0.13, hy + 0.05 * side * -1, 1.02), M_METAL, bevel=0.008)
    box("hneck", (0.05, 0.02, 0.02), (x + s * 0.105, hy, 1.02), M_METAL)
    if label:
        # 教室の札（ドアの上の白い板と、壁から突き出た札）
        box("plate", (0.02, 0.78, 0.34), (x + s * 0.02, y, 2.36), M_PLATE, bevel=0.006)
        rz = math.radians(90) if side < 0 else math.radians(-90)
        text("ptext", label, (x + s * 0.034, y, 2.345), 0.3, (math.radians(90), 0, rz), M_INK)
    return Vector((x + s * 0.09, y, 1.45))


anchors_pts = []
for y, nm in zip(DY, ROOMS):
    anchors_pts.append((door(y, -1, nm, lit=True, hero=True), Vector((XL + 0.04, y, 2.36))))
# 脇役のドア（札なし）。明かりのついた窓が奥まで続く
for y in (4.0, 20.0, 24.0, 28.0, 32.0):
    door(y, -1, None, lit=True)
for y in (6.0, 10.0, 14.0, 22.0, 26.0, 30.0):
    door(y, +1, None, lit=(y not in (14.0,)))

# 掲示板（右の壁。紙は白紙。文字やロゴは置かない）
box("pinboard", (0.03, 1.5, 1.0), (XR - 0.02, 18.0, 1.55), M_BOARD, bevel=0.01)
for k, (dy, dz, w, h) in enumerate([(-0.5, 0.2, 0.3, 0.42), (-0.1, 0.18, 0.3, 0.42), (0.35, 0.22, 0.42, 0.3), (-0.3, -0.25, 0.42, 0.3), (0.3, -0.2, 0.3, 0.42)]):
    box(f"paper{k}", (0.004, w, h), (XR - 0.04, 18.0 + dy, 1.55 + dz), M_PAPER)

# ── 壁の時計（右の壁。13:20＝3限が始まる時刻へ） ──
CY, CZ = 3.0, 1.95
cx = XR - 0.02
bpy.ops.mesh.primitive_cylinder_add(radius=0.24, depth=0.05, vertices=64, location=(cx - 0.02, CY, CZ), rotation=(0, math.radians(90), 0))
rim = bpy.context.object; rim.data.materials.append(mat("rim", srgb("#2a3140"), rough=0.35, coat=0.3)); bpy.ops.object.shade_smooth()
bpy.ops.mesh.primitive_cylinder_add(radius=0.215, depth=0.052, vertices=64, location=(cx - 0.022, CY, CZ), rotation=(0, math.radians(90), 0))
face = bpy.context.object; face.data.materials.append(mat("face", srgb("#fbfaf6"), rough=0.5, emit=srgb("#ffffff"), strength=0.03)); bpy.ops.object.shade_smooth()
for k in range(12):
    a = math.radians(k * 30); r = 0.175
    big = k % 3 == 0
    d = 0.03 if big else 0.018                  # 目盛りは四角い点（回さない）
    box(f"tick{k}", (0.006, d, d), (cx - 0.052, CY + math.sin(a) * r, CZ + math.cos(a) * r), M_INK)


def hand(name, length, width, m):
    bpy.ops.object.empty_add(location=(cx - 0.052, CY, CZ)); piv = bpy.context.object; piv.name = name + "_piv"
    o = box(name, (0.004, width, length), (cx - 0.052, CY, CZ + length / 2 - 0.02), m, bevel=0.001)
    o.parent = piv; o.matrix_parent_inverse = piv.matrix_world.inverted()
    return piv


hh = hand("hour", 0.11, 0.016, M_INK); mh = hand("min", 0.165, 0.011, M_INK)
sh = hand("sec", 0.17, 0.004, mat("red", srgb("#e5484d"), rough=0.5))
# 右の壁にあるので、カメラから見て時計回り＝ X 軸まわりに正の回転
def clock_at(frame, minutes, seconds):
    hrs = 13 + minutes / 60
    hh.rotation_euler = (math.radians(hrs * 30), 0, 0); hh.keyframe_insert("rotation_euler", frame=frame)
    mh.rotation_euler = (math.radians(minutes * 6), 0, 0); mh.keyframe_insert("rotation_euler", frame=frame)
    sh.rotation_euler = (math.radians(seconds * 6), 0, 0); sh.keyframe_insert("rotation_euler", frame=frame)


clock_at(178, 19.0, 48); clock_at(204, 19.95, 59.5); clock_at(207, 20.0, 60); clock_at(216, 20.0, 61)

# ── カメラ ──
bpy.ops.object.empty_add(location=(0, 10, 1.4)); focus = bpy.context.object; focus.name = "focus"
bpy.ops.object.camera_add(location=(0, 0, 1.5)); cam = bpy.context.object; sc.camera = cam
cam.data.sensor_fit = "VERTICAL"; cam.data.sensor_height = 36; cam.data.lens = 26
cam.data.dof.use_dof = True; cam.data.dof.focus_object = focus; cam.data.dof.aperture_fstop = 2.8
c = cam.constraints.new("TRACK_TO"); c.target = focus; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
KEYS = [(0.0, (0.15, -0.6, 1.5), (-0.2, 14, 1.35), 26),
        (1.85, (0.25, 3.4, 1.5), (-0.5, 14, 1.35), 26)]
for i, y in enumerate(DY):
    t0 = 2.0 + i * 1.3
    KEYS.append((t0 + 0.27, (0.95, y - 1.05, 1.52), (XL, y - 0.02, 1.52), 30))
    KEYS.append((t0 + 1.22, (0.78, y - 0.9, 1.52), (XL, y - 0.02, 1.52), 30))
for t, cl, fl, lens in KEYS:
    f = int(round(t * FPS))
    cam.location = cl; cam.keyframe_insert("location", frame=f)
    focus.location = fl; focus.keyframe_insert("location", frame=f)
    cam.data.lens = lens; cam.data.keyframe_insert("lens", frame=f)
# 時計のカット（178〜216）。その場で切り替える（前のコマとの間をなめらかにしない）
for f, cl in ((177, None), (178, (-0.55, CY - 0.75, 1.62)), (216, (-0.42, CY - 0.62, 1.64))):
    if cl is None:
        cam.keyframe_insert("location", frame=f); focus.keyframe_insert("location", frame=f); cam.data.keyframe_insert("lens", frame=f); continue
    cam.location = cl; cam.keyframe_insert("location", frame=f)
    focus.location = (cx, CY + 0.02, 1.62); focus.keyframe_insert("location", frame=f)
    cam.data.lens = 38; cam.data.keyframe_insert("lens", frame=f)
for ob in (cam, focus, cam.data):
    ad = ob.animation_data
    if not ad or not ad.action: continue
    for fc in ad.action.fcurves:
        for kp in fc.keyframe_points:
            if int(kp.co.x) in (177, 178):
                kp.interpolation = "CONSTANT"
            else:
                kp.interpolation = "BEZIER"; kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"

# ── 空いている教室（廊下とは別の場所に置く。room モードで1枚だけ描く） ──
RX = 60.0
def classroom():
    m_desk = mat("desk", srgb("#d9c3a0"), rough=0.4, coat=0.2); m_leg = mat("leg", srgb("#6b7686"), rough=0.4, metal=0.7)
    box("rfloor", (9, 11, 0.1), (RX, 5, -0.05), mat("rfloor", srgb("#c9c2b4"), rough=0.3, coat=0.3))
    box("rceil", (9, 11, 0.1), (RX, 5, 3.05), M_CEIL)
    box("rwallF", (9, 0.1, 3), (RX, 10.5, 1.5), M_WALL); box("rwallB", (9, 0.1, 3), (RX, -0.5, 1.5), M_WALL)
    box("rwallR", (0.1, 11, 3), (RX + 4.5, 5, 1.5), M_WALL)
    box("rwallL_low", (0.1, 11, 0.9), (RX - 4.5, 5, 0.45), M_WALL); box("rwallL_top", (0.1, 11, 0.5), (RX - 4.5, 5, 2.75), M_WALL)
    for k in range(4):                                         # 窓の柱
        box(f"mull{k}", (0.12, 0.14, 1.7), (RX - 4.5, 0.5 + k * 3.2, 1.7), M_FRAME)
    box("sky", (0.05, 11, 1.7), (RX - 4.9, 5, 1.7), mat("sky", srgb("#dcecff"), emit=srgb("#dcecff"), strength=2.2))
    box("board", (4.6, 0.04, 1.25), (RX, 10.43, 1.55), mat("bb", srgb("#1f4a3a"), rough=0.7))
    box("boardf", (4.76, 0.03, 1.4), (RX, 10.45, 1.55), M_FRAME); box("tray", (4.6, 0.09, 0.03), (RX, 10.38, 0.9), M_METAL)
    box("lectern", (0.9, 0.5, 1.0), (RX + 2.6, 9.3, 0.5), m_desk, bevel=0.01)
    for r in range(4):
        for cidx in range(3):
            x, y = RX - 2.5 + cidx * 2.5, 2.2 + r * 1.75
            box("dtop", (1.7, 0.5, 0.035), (x, y, 0.72), m_desk, bevel=0.006)
            for sx in (-0.78, 0.78):
                box("dleg", (0.035, 0.42, 0.7), (x + sx, y, 0.35), m_leg)
            for sx in (-0.42, 0.42):
                box("seat", (0.4, 0.38, 0.03), (x + sx, y - 0.48, 0.43), mat("seat", srgb("#4f6fae"), rough=0.6), bevel=0.01)
                box("sback", (0.4, 0.03, 0.34), (x + sx, y - 0.67, 0.68), bpy.data.materials["seat"], bevel=0.01)
                box("sleg", (0.03, 0.03, 0.43), (x + sx, y - 0.5, 0.215), m_leg)
    for k in range(3):
        bpy.ops.object.light_add(type="AREA", location=(RX, 2 + k * 3.2, 2.95)); L = bpy.context.object
        L.data.shape = "RECTANGLE"; L.data.size = 1.2; L.data.size_y = 0.4; L.data.energy = 45; L.data.color = (1.0, 0.97, 0.92)
    bpy.ops.object.light_add(type="AREA", location=(RX - 4.4, 5, 1.8), rotation=(0, math.radians(-90), 0)); L = bpy.context.object
    L.data.shape = "RECTANGLE"; L.data.size = 1.6; L.data.size_y = 10; L.data.energy = 260; L.data.color = (0.9, 0.95, 1.0)


# ── 書き出しの設定 ──
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (*srgb("#30405c"), 1); w.node_tree.nodes["Background"].inputs[1].default_value = 0.2
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
sc.cycles.samples = 16; sc.cycles.adaptive_threshold = 0.05; sc.cycles.use_denoising = True; sc.cycles.denoiser = "OPENIMAGEDENOISE"
sc.cycles.max_bounces = 5; sc.cycles.diffuse_bounces = 3; sc.cycles.glossy_bounces = 3; sc.cycles.transmission_bounces = 0
sc.cycles.sample_clamp_indirect = 6.0
sc.render.use_persistent_data = True
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"; sc.view_settings.exposure = -0.2
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 720, 1280, 75
sc.render.image_settings.file_format = "PNG"
os.makedirs(OUT, exist_ok=True)


def anchors():
    """主役のドア3つの、窓のまん中と札の位置（画面の割合。左上が 0,0）。カメラより後ろなら null"""
    out = {}
    for f in range(F0, F1 + 1):
        sc.frame_set(f); row = []
        for win, plate in anchors_pts:
            pw = world_to_camera_view(sc, cam, win); pp = world_to_camera_view(sc, cam, plate)
            row.append(None if pw.z <= 0 else [round(pw.x, 4), round(1 - pw.y, 4), round(pp.x, 4), round(1 - pp.y, 4), round(pw.z, 3)])
        out[f] = row
    json.dump(out, open(os.path.join(OUT, "anchors.json"), "w"))


mode = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else sys.argv[1]
if mode == "preview":
    ts = [float(x) for x in sys.argv[-1].split(",")]
    sc.render.resolution_percentage = 50; sc.cycles.samples = 12
    for t in ts:
        sc.frame_set(int(round(t * FPS))); sc.render.filepath = os.path.join(OUT, f"pv_{t}.png"); bpy.ops.render.render(write_still=True)
    anchors()
elif mode == "render":
    anchors()
    for f in range(F0, F1 + 1):
        path = os.path.join(OUT, f"f{f:04d}.png")
        if os.path.exists(path): continue
        sc.frame_set(f); sc.render.filepath = path; bpy.ops.render.render(write_still=True)
        print("コマ", f, flush=True)
elif mode in ("room", "roompv"):
    classroom()
    bpy.ops.object.empty_add(location=(RX - 0.3, 7.5, 1.1)); rf = bpy.context.object
    bpy.ops.object.camera_add(location=(RX + 3.3, 0.4, 1.55)); rc = bpy.context.object; sc.camera = rc
    rc.data.sensor_fit = "VERTICAL"; rc.data.sensor_height = 36; rc.data.lens = 24
    k = rc.constraints.new("TRACK_TO"); k.target = rf; k.track_axis = "TRACK_NEGATIVE_Z"; k.up_axis = "UP_Y"
    sc.cycles.samples = 16 if mode == "roompv" else 96
    sc.render.resolution_percentage = 50 if mode == "roompv" else 100
    sc.frame_set(1); sc.render.filepath = os.path.join(OUT, "room_pv.png" if mode == "roompv" else "room.png"); bpy.ops.render.render(write_still=True)
