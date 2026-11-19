"""広告ふうの静止画（縦 1080×1350）の 3D 背景を Blender 4.5 / Cycles で描く。文字（キャッチコピー）は compose.py で重ねる。
  python r scene.py <still|room|door> [preview|final]
  still：暗い紺の地に、スマホ（アプリの実画面）・ノート・鉛筆・マグを低い光で（商品写真の構図）
  room ：夕方の誰もいない教室。窓から低い日が机の列に差す
  door ：暗い廊下で、少し開いた教室の扉から光がこぼれる
人物・実在のロゴは描かない。スマホは平らな金属の枠と黒いガラスだけ（ブランドの印なし）。"""
import bpy, math, os, random, sys
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "renders"); os.makedirs(OUT, exist_ok=True)
SCREEN = os.path.join(HERE, "assets", "screen.png")        # アプリの実画面（make_screen で切り出し）
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
MODE, Q = argv[0], (argv[1] if len(argv) > 1 else "preview")
random.seed(11)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def lin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


def mat(name, color, rough=0.5, metal=0.0, coat=0.0, emit=None, strength=0.0, sheen=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*lin(color), 1); p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal; p.inputs["Coat Weight"].default_value = coat
    p.inputs["Sheen Weight"].default_value = sheen
    if emit:
        p.inputs["Emission Color"].default_value = (*lin(emit), 1); p.inputs["Emission Strength"].default_value = strength
    return m


def box(name, size, loc, m, bevel=0.0, seg=3, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot); o = bpy.context.object; o.name = name
    o.scale = size; bpy.ops.object.transform_apply(scale=True)
    if bevel:
        md = o.modifiers.new("b", "BEVEL"); md.width = bevel; md.segments = seg; md.limit_method = "NONE"
        bpy.ops.object.shade_smooth()
    o.data.materials.append(m); return o


def cyl(name, r, d, loc, m, rot=(0, 0, 0), verts=64, bevel=0.0):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d, vertices=verts, location=loc, rotation=rot); o = bpy.context.object; o.name = name
    if bevel:
        md = o.modifiers.new("b", "BEVEL"); md.width = bevel; md.segments = 3
    bpy.ops.object.shade_smooth(); o.data.materials.append(m); return o


def area(name, loc, target, energy, size, color=(1, 1, 1), shape="RECTANGLE", sy=None, glossy=True):
    bpy.ops.object.light_add(type="AREA", location=loc); L = bpy.context.object; L.name = name
    L.data.energy = energy; L.data.shape = shape; L.data.size = size; L.data.color = color
    if sy: L.data.size_y = sy
    L.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler(); L.visible_glossy = glossy
    return L


def camera(loc, target, lens, fstop=None, focus=None):
    bpy.ops.object.camera_add(location=loc); c = bpy.context.object; sc.camera = c
    c.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler(); c.data.lens = lens
    if fstop:
        c.data.dof.use_dof = True; c.data.dof.aperture_fstop = fstop
        c.data.dof.focus_distance = (Vector(focus or target) - Vector(loc)).length
    return c


def world(color, strength):
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (*lin(color), 1); w.node_tree.nodes["Background"].inputs[1].default_value = strength


def phone(loc, rot_z, tilt=0.0, scale=1.0):
    """平らな金属の枠・黒いガラス・アプリの画面（発光）。ブランドの印なし"""
    W, H, T = 0.0716 * scale, 0.147 * scale, 0.0078 * scale
    body = box("phone", (W, H, T), (0, 0, 0), mat("frame", "#9ea3ab", rough=0.28, metal=1.0), bevel=0.009 * scale, seg=6)
    glass = box("glass", (W - 0.0012 * scale, H - 0.0012 * scale, 0.0006), (0, 0, T / 2 + 0.0002), mat("glass", "#050608", rough=0.05, coat=1.0), bevel=0.0085 * scale, seg=6)
    # 画面（アプリの実画面を貼り、少し光らせる）
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, T / 2 + 0.00055)); scr = bpy.context.object; scr.name = "screen"
    scr.scale = (W - 0.0042 * scale, H - 0.0042 * scale, 1); bpy.ops.object.transform_apply(scale=True)
    md = scr.modifiers.new("b", "BEVEL"); md.width = 0.008 * scale; md.segments = 6; md.affect = "VERTICES"
    m = bpy.data.materials.new("screen"); m.use_nodes = True; n = m.node_tree.nodes; l = m.node_tree.links
    p = n["Principled BSDF"]; img = n.new("ShaderNodeTexImage"); img.image = bpy.data.images.load(SCREEN); img.interpolation = "Cubic"
    l.new(img.outputs["Color"], p.inputs["Base Color"]); l.new(img.outputs["Color"], p.inputs["Emission Color"])
    p.inputs["Emission Strength"].default_value = 1.6; p.inputs["Roughness"].default_value = 0.08; p.inputs["Coat Weight"].default_value = 1.0
    scr.data.materials.append(m)
    # 上の黒い楕円
    isl = box("island", (0.018 * scale, 0.0052 * scale, 0.0004), (0, H / 2 - 0.0085 * scale, T / 2 + 0.0008), mat("isl", "#000000", rough=0.2), bevel=0.0025 * scale, seg=6)
    for o in (glass, scr, isl):
        o.parent = body
    body.location = loc; body.rotation_euler = (tilt, 0, rot_z)
    return body


def make_screen():
    """reels の実画面（駿河台校舎・水曜3限）の上の 390×844 を切り出す"""
    from PIL import Image
    src = os.path.join(HERE, "..", "reels-1118", "assets", "page0.png")
    if not os.path.exists(src):
        src = os.path.join(HERE, "..", "desk-3d", "assets", "page0.png")
    im = Image.open(src); k = im.width / 390
    im.crop((0, 0, im.width, int(844 * k))).resize((1170, 2532)).save(SCREEN)


# ════════════════════════ 場面 ════════════════════════
if MODE == "still":
    if not os.path.exists(SCREEN): os.makedirs(os.path.dirname(SCREEN), exist_ok=True); make_screen()
    world("#06102a", 0.18)
    # 地：紺の布張りの台（遠くは闇に溶ける）
    bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0.6, 0)); fl = bpy.context.object
    m = bpy.data.materials.new("cloth"); m.use_nodes = True; n = m.node_tree.nodes; l = m.node_tree.links; p = n["Principled BSDF"]
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 900; nz.inputs["Detail"].default_value = 2
    ramp = n.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].color = (*lin("#0a1734"), 1); ramp.color_ramp.elements[1].color = (*lin("#112450"), 1)
    l.new(nz.outputs["Fac"], ramp.inputs["Fac"]); l.new(ramp.outputs["Color"], p.inputs["Base Color"]); p.inputs["Roughness"].default_value = 0.9
    p.inputs["Sheen Weight"].default_value = 0.5
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.15; l.new(nz.outputs["Fac"], bump.inputs["Height"]); l.new(bump.outputs["Normal"], p.inputs["Normal"])
    fl.data.materials.append(m)
    bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 1.6, 1.0), rotation=(math.radians(90), 0, 0)); bpy.context.object.data.materials.append(m)
    # 時間割の紙（架空。A4 くらい）
    bpy.ops.mesh.primitive_plane_add(size=1, location=(-0.02, 0.01, 0.0008), rotation=(0, 0, math.radians(-9))); sheet = bpy.context.object
    sheet.scale = (0.21, 0.297, 1); bpy.ops.object.transform_apply(scale=True)
    m = bpy.data.materials.new("sheet"); m.use_nodes = True; n = m.node_tree.nodes; l = m.node_tree.links; p = n["Principled BSDF"]
    img = n.new("ShaderNodeTexImage"); img.image = bpy.data.images.load(os.path.join(HERE, "assets", "timetable.png"))
    l.new(img.outputs["Color"], p.inputs["Base Color"]); p.inputs["Roughness"].default_value = 0.85
    sheet.data.materials.append(m)
    # スマホ（紙の上に少し斜めに。主役）
    phone((0.06, -0.035, 0.0047), math.radians(-16), scale=1.0)
    # 鉛筆
    cyl("pencil", 0.0037, 0.17, (-0.12, -0.12, 0.0042), mat("pencil", "#e7b44a", rough=0.5), rot=(0, math.radians(90), math.radians(24)), verts=6)
    # マグ（左奥）
    cer = mat("cer", "#e9e6df", rough=0.22, coat=0.6)
    cyl("mug", 0.04, 0.09, (-0.17, 0.17, 0.045), cer, bevel=0.003)
    cyl("coffee", 0.036, 0.002, (-0.17, 0.17, 0.084), mat("coffee", "#2a170c", rough=0.08))
    bpy.ops.mesh.primitive_torus_add(major_radius=0.024, minor_radius=0.0065, location=(-0.125, 0.17, 0.048), rotation=(math.radians(90), 0, 0))
    bpy.context.object.data.materials.append(cer); bpy.ops.object.shade_smooth()
    # 光：左から低く差す暖かい光（長い影）、右奥から細い縁の光、上から弱い面光
    bpy.ops.object.light_add(type="SPOT", location=(-0.9, -0.3, 0.32)); k = bpy.context.object   # 左から低く、物だけに当たる光（長い影）
    k.data.energy = 30; k.data.color = (1.0, 0.8, 0.58); k.data.spot_size = math.radians(38); k.data.spot_blend = 0.9; k.data.shadow_soft_size = 0.06
    k.rotation_euler = (Vector((0.03, -0.02, 0)) - Vector((-0.9, -0.3, 0.32))).to_track_quat("-Z", "Y").to_euler()
    area("rim", (0.8, 1.0, 0.3), (0.05, 0, 0.02), 9, 0.4, (0.5, 0.65, 1.0))
    area("top", (0, -0.2, 1.4), (0, 0, 0), 0.6, 1.2, (0.8, 0.86, 1.0), glossy=False)
    camera((0.03, -0.44, 0.36), (0.0, 0.12, 0.0), 54, fstop=2.0, focus=(0.06, -0.035, 0.005))   # 物を画面の下に、大きく

elif MODE == "room":
    world("#0a0d16", 0.15)
    floor = mat("floor", "#8a7255", rough=0.5, coat=0.2)
    wallm = mat("wall", "#c9c0b0", rough=0.9)
    box("floor", (14, 14, 0.05), (0, 3, -0.025), floor)
    box("ceil", (14, 14, 0.05), (0, 3, 3.2), wallm)
    box("back", (14, 0.1, 3.4), (0, 9.5, 1.6), wallm)
    box("right", (0.1, 14, 3.4), (3.6, 3, 1.6), wallm)
    # 左の壁は窓（柱と腰壁だけ。外の夕日が入る）
    box("sill", (0.1, 14, 0.9), (-3.6, 3, 0.45), wallm)
    box("top", (0.1, 14, 0.5), (-3.6, 3, 2.95), wallm)
    for k in range(7):
        box(f"pillar{k}", (0.12, 0.28, 2.0), (-3.6, -2.0 + k * 1.9, 1.9), wallm)
    # 黒板（奥の壁）
    box("board", (4.5, 0.04, 1.3), (0, 9.42, 1.55), mat("board", "#1f3b31", rough=0.85))
    # 机と椅子の列（木の天板・金属の脚）
    top = mat("deskTop", "#b78b5c", rough=0.4, coat=0.3); leg = mat("leg", "#2d3036", rough=0.35, metal=0.9)
    seat = mat("seat", "#3a5a8c", rough=0.6)
    for row in range(5):
        for col in range(3):
            x = -1.9 + col * 1.9; y = 1.0 + row * 1.5
            box(f"desk{row}{col}", (1.3, 0.45, 0.03), (x, y, 0.72), top, bevel=0.01)
            for dx in (-0.6, 0.6):
                box(f"leg{row}{col}{dx}", (0.03, 0.4, 0.7), (x + dx, y, 0.36), leg)
            for dx in (-0.32, 0.32):
                box(f"seat{row}{col}{dx}", (0.42, 0.4, 0.04), (x + dx, y - 0.45, 0.44), seat, bevel=0.015)
                box(f"back{row}{col}{dx}", (0.42, 0.03, 0.32), (x + dx, y - 0.64, 0.68), seat, bevel=0.01)
    # 夕日（低く、窓から斜めに）と、部屋のかすかな明かり
    bpy.ops.object.light_add(type="SUN", location=(-8, 0, 3)); s = bpy.context.object
    s.data.energy = 14.0; s.data.color = (1.0, 0.66, 0.38); s.data.angle = math.radians(0.8)
    s.rotation_euler = (Vector((0, 3, 0.4)) - Vector((-8, 1.5, 2.6))).to_track_quat("-Z", "Y").to_euler()
    area("fill", (0, -2.5, 2.6), (0, 4, 1.0), 40, 4, (0.55, 0.65, 1.0), glossy=False)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(-6, 3, 1.8), rotation=(0, math.radians(90), 0)); sky = bpy.context.object
    sky.scale = (4, 16, 1); sky.data.materials.append(mat("sky", "#000000", emit="#ffb070", strength=0.9)); sky.visible_diffuse = False; sky.visible_shadow = False   # 夕日をさえぎらないように
    camera((1.4, -2.4, 1.15), (-0.6, 5.0, 0.95), 26, fstop=4.0, focus=(-0.2, 3.0, 0.8))

elif MODE == "door":
    world("#03050a", 0.1)
    wallm = mat("wallD", "#2b2f38", rough=0.85); floorm = mat("floorD", "#3a3d44", rough=0.25, coat=0.4)
    box("floor", (8, 8, 0.05), (0, 2, -0.025), floorm)
    box("wallL", (1.6, 0.15, 2.8), (-1.25, 0, 1.4), wallm)
    box("wallR", (1.6, 0.15, 2.8), (1.25, 0, 1.4), wallm)
    box("lintel", (0.9, 0.15, 0.7), (0, 0, 2.45), wallm)
    fr = mat("doorFrame", "#8a8f99", rough=0.35, metal=0.8)
    box("frameL", (0.05, 0.18, 2.1), (-0.47, 0, 1.05), fr); box("frameR", (0.05, 0.18, 2.1), (0.47, 0, 1.05), fr); box("frameT", (0.99, 0.18, 0.05), (0, 0, 2.1), fr)
    # 扉（少し内側へ開く。蝶番は右）
    bpy.ops.object.empty_add(location=(0.44, 0.0, 0)); hinge = bpy.context.object
    door = box("door", (0.88, 0.045, 2.05), (-0.44, 0.0, 1.03), mat("doorM", "#c9c3b6", rough=0.6), bevel=0.006)
    win = box("doorWin", (0.28, 0.05, 0.55), (-0.44, 0.0, 1.45), mat("doorGlass", "#ffd9a8", rough=0.1, emit="#ffd1a0", strength=1.8))
    handle = box("handle", (0.14, 0.03, 0.03), (-0.78, -0.05, 1.0), fr, bevel=0.008)
    for o in (door, win, handle): o.parent = hinge
    hinge.rotation_euler.z = math.radians(-24)
    plate = box("plate", (0.24, 0.02, 0.09), (0.75, -0.085, 1.85), mat("plateM", "#f2f0ea", rough=0.5), bevel=0.004)
    # 部屋の中の明るさ（扉の向こうの暖かい光）
    box("roomBack", (4, 0.1, 3), (0, 3.2, 1.5), mat("roomWall", "#e9dcc6", rough=0.9))
    area("roomLight", (0, 1.6, 2.6), (0, 1.6, 0), 900, 2.5, (1.0, 0.82, 0.6), glossy=False)
    area("corridor", (0, -3.5, 2.8), (0, 0, 1.0), 25, 2.0, (0.5, 0.6, 0.9))
    camera((-0.55, -3.1, 1.25), (0.05, 0.4, 1.0), 32, fstop=2.8, focus=(0.0, 0.0, 1.1))

# ── 書き出し ──
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.use_denoising = True; sc.cycles.denoiser = "OPENIMAGEDENOISE"
sc.cycles.max_bounces = 6
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - High Contrast"
sc.render.resolution_x, sc.render.resolution_y = 1080, 1350
if Q == "preview":
    sc.render.resolution_percentage = 40; sc.cycles.samples = 32
else:
    sc.render.resolution_percentage = 100; sc.cycles.samples = 160
sc.render.filepath = os.path.join(OUT, f"{MODE}_{Q}.png"); bpy.ops.render.render(write_still=True)
print("書き出し", sc.render.filepath)
