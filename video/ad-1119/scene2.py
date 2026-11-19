"""広告ふうの静止画 その2（2026-11-19、やり直し）。縦 1080×1350 の 3D 背景を Blender 4.5 / Cycles で描く。文字は compose.py で重ねる。
  python scene2.py <hero|door|room> [preview|final]
  hero：切れ目のない紺の背景に、本の束に立てかけたスマホ（アプリの実画面）を主役に置く（商品写真の構図）
  door：暗い廊下。半分開いた教室の扉から、あたたかい光が床にこぼれる
  room：夕方の教室。手前の机のスマホと、奥の窓から差す日の光
人物・実在のロゴは描かない。スマホは平らな金属の枠と黒いガラスだけ（ブランドの印なし）。時間割の紙は架空。"""
import bpy, math, os, random, sys
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "renders"); os.makedirs(OUT, exist_ok=True)
SCREEN = os.path.join(HERE, "assets", "screen.png")
SHEET = os.path.join(HERE, "assets", "timetable.png")
argv = sys.argv[1:]
MODE, Q = argv[0], (argv[1] if len(argv) > 1 else "preview")
random.seed(7)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def lin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


def mat(name, color, rough=0.5, metal=0.0, coat=0.0, emit=None, strength=0.0, sheen=0.0, bump=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links; p = n["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*lin(color), 1); p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal; p.inputs["Coat Weight"].default_value = coat; p.inputs["Sheen Weight"].default_value = sheen
    if emit:
        p.inputs["Emission Color"].default_value = (*lin(emit), 1); p.inputs["Emission Strength"].default_value = strength
    if bump:                                             # (細かさ, 強さ) のざらつき
        nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = bump[0]; nz.inputs["Detail"].default_value = 3
        b = n.new("ShaderNodeBump"); b.inputs["Strength"].default_value = bump[1]
        l.new(nz.outputs["Fac"], b.inputs["Height"]); l.new(b.outputs["Normal"], p.inputs["Normal"])
    return m


def box(name, size, loc, m, bevel=0.0, seg=3, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot); o = bpy.context.object; o.name = name
    o.scale = size; bpy.ops.object.transform_apply(scale=True)
    if bevel:
        md = o.modifiers.new("b", "BEVEL"); md.width = bevel; md.segments = seg
        bpy.ops.object.shade_smooth()
    o.data.materials.append(m); return o


def cyl(name, r, d, loc, m, rot=(0, 0, 0), verts=64, bevel=0.0):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d, vertices=verts, location=loc, rotation=rot); o = bpy.context.object; o.name = name
    if bevel:
        md = o.modifiers.new("b", "BEVEL"); md.width = bevel; md.segments = 3
    bpy.ops.object.shade_smooth(); o.data.materials.append(m); return o


def aim(o, target):
    o.rotation_euler = (Vector(target) - o.location).to_track_quat("-Z", "Y").to_euler()


def area(name, loc, target, energy, size, color=(1, 1, 1), sy=None, glossy=True):
    bpy.ops.object.light_add(type="AREA", location=loc); L = bpy.context.object; L.name = name
    L.data.energy = energy; L.data.size = size; L.data.color = color
    if sy: L.data.shape = "RECTANGLE"; L.data.size_y = sy
    aim(L, target); L.visible_glossy = glossy; return L


def spot(name, loc, target, energy, angle, blend=0.6, color=(1, 1, 1), soft=0.05):
    bpy.ops.object.light_add(type="SPOT", location=loc); L = bpy.context.object; L.name = name
    L.data.energy = energy; L.data.spot_size = math.radians(angle); L.data.spot_blend = blend; L.data.color = color; L.data.shadow_soft_size = soft
    aim(L, target); return L


def camera(loc, target, lens, fstop=None, focus=None):
    bpy.ops.object.camera_add(location=loc); c = bpy.context.object; sc.camera = c
    aim(c, target); c.data.lens = lens
    if fstop:
        c.data.dof.use_dof = True; c.data.dof.aperture_fstop = fstop
        c.data.dof.focus_distance = (Vector(focus or target) - Vector(loc)).length
    return c


def world(color, strength):
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (*lin(color), 1); w.node_tree.nodes["Background"].inputs[1].default_value = strength


def group(name, loc=(0, 0, 0)):
    bpy.ops.object.empty_add(location=loc); e = bpy.context.object; e.name = name; return e


def phone(parent=None, glow=2.4):
    """原点に寝かせた形で作る（画面は +Z 向き）。置き方は呼ぶ側で決める"""
    W, H, T = 0.0716, 0.147, 0.0078
    body = box("phone", (W, H, T), (0, 0, 0), mat("frame", "#a7acb4", rough=0.26, metal=1.0), bevel=0.0095, seg=8)
    glass = box("glass", (W - 0.0014, H - 0.0014, 0.0006), (0, 0, T / 2 + 0.0002), mat("glass", "#040507", rough=0.04, coat=1.0), bevel=0.0088, seg=8)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, T / 2 + 0.0006)); scr = bpy.context.object; scr.name = "screen"
    scr.scale = (W - 0.0044, H - 0.0044, 1); bpy.ops.object.transform_apply(scale=True)
    md = scr.modifiers.new("b", "BEVEL"); md.width = 0.0078; md.segments = 8; md.affect = "VERTICES"
    m = bpy.data.materials.new("screen"); m.use_nodes = True; n = m.node_tree.nodes; l = m.node_tree.links
    p = n["Principled BSDF"]; img = n.new("ShaderNodeTexImage"); img.image = bpy.data.images.load(SCREEN); img.interpolation = "Cubic"
    l.new(img.outputs["Color"], p.inputs["Base Color"]); l.new(img.outputs["Color"], p.inputs["Emission Color"])
    p.inputs["Emission Strength"].default_value = glow; p.inputs["Roughness"].default_value = 0.06; p.inputs["Coat Weight"].default_value = 1.0
    scr.data.materials.append(m)
    isl = box("island", (0.0185, 0.0054, 0.0004), (0, H / 2 - 0.0088, T / 2 + 0.0009), mat("isl", "#000000", rough=0.2), bevel=0.0026, seg=6)
    for o in (glass, scr, isl): o.parent = body
    # 側面のボタン（右に1つ、左に2つ）
    fm = bpy.data.materials["frame"]
    for (x, y, h) in ((W / 2 + 0.0004, 0.018, 0.016), (-W / 2 - 0.0004, 0.03, 0.009), (-W / 2 - 0.0004, 0.016, 0.009)):
        b = box("btn", (0.0012, h, 0.003), (x, y, 0), fm, bevel=0.0005); b.parent = body
    if parent: body.parent = parent
    return body


def book(name, w, d, h, loc, yaw, cover, parent=None):
    """背表紙が手前（-Y）を向く本。紙の束＋表紙2枚＋背"""
    g = group(name, loc); g.rotation_euler.z = yaw
    cm = mat(name + "c", cover, rough=0.62, sheen=0.3, bump=(260, 0.05)); pm = mat(name + "p", "#e4dfd2", rough=0.9, bump=(900, 0.1))
    for o in (box(name + "pages", (w - 0.006, d - 0.008, h - 0.005), (0, 0.003, h / 2), pm, bevel=0.0008),
              box(name + "top", (w, d, 0.0025), (0, 0, h - 0.00125), cm, bevel=0.001),
              box(name + "bot", (w, d, 0.0025), (0, 0, 0.00125), cm, bevel=0.001),
              box(name + "spine", (w, 0.003, h), (0, -d / 2 + 0.0015, h / 2), cm, bevel=0.0012)):
        o.parent = g
    if parent: g.parent = parent
    return g


def pencil(loc, yaw, parent=None):
    g = group("pencil", loc); g.rotation_euler.z = yaw
    L = 0.165
    body = cyl("pbody", 0.0036, L, (0, 0, 0.0036), mat("pyellow", "#e0a93a", rough=0.42, coat=0.4), rot=(0, math.radians(90), 0), verts=6)
    bpy.ops.mesh.primitive_cone_add(radius1=0.0036, radius2=0.0009, depth=0.011, vertices=24, location=(L / 2 + 0.0055, 0, 0.0036), rotation=(0, math.radians(90), 0))
    wood = bpy.context.object; wood.data.materials.append(mat("pwood", "#d9b78d", rough=0.7)); bpy.ops.object.shade_smooth()
    bpy.ops.mesh.primitive_cone_add(radius1=0.0009, radius2=0.0001, depth=0.003, vertices=16, location=(L / 2 + 0.0125, 0, 0.0036), rotation=(0, math.radians(90), 0))
    tip = bpy.context.object; tip.data.materials.append(mat("ptip", "#1b1b1f", rough=0.4))
    fer = cyl("pfer", 0.0038, 0.012, (-L / 2 - 0.004, 0, 0.0036), mat("pmetal", "#b9bcc2", rough=0.3, metal=1.0), rot=(0, math.radians(90), 0), verts=24)
    era = cyl("pera", 0.0036, 0.008, (-L / 2 - 0.013, 0, 0.0036), mat("pera", "#c8736b", rough=0.8), rot=(0, math.radians(90), 0), verts=24)
    for o in (body, wood, tip, fer, era): o.parent = g
    if parent: g.parent = parent
    return g


def mug(loc, parent=None, color="#e6e2d8"):
    g = group("mug", loc); cer = mat("cer", color, rough=0.2, coat=0.7)
    a = cyl("mugb", 0.039, 0.088, (0, 0, 0.044), cer, bevel=0.004)
    c = cyl("coffee", 0.0355, 0.002, (0, 0, 0.083), mat("coffee", "#24130a", rough=0.06, coat=1.0))
    bpy.ops.mesh.primitive_torus_add(major_radius=0.024, minor_radius=0.0062, major_segments=48, minor_segments=16, location=(-0.043, 0, 0.046), rotation=(math.radians(90), 0, 0))
    h = bpy.context.object; h.data.materials.append(cer); bpy.ops.object.shade_smooth()
    for o in (a, c, h): o.parent = g
    if parent: g.parent = parent
    return g


def sheet(loc, yaw, parent=None, size=(0.21, 0.297)):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=(0, 0, yaw)); s = bpy.context.object; s.name = "sheet"
    s.scale = (size[0], size[1], 1); bpy.ops.object.transform_apply(scale=True)
    m = bpy.data.materials.new("sheet"); m.use_nodes = True; n = m.node_tree.nodes; l = m.node_tree.links; p = n["Principled BSDF"]
    img = n.new("ShaderNodeTexImage"); img.image = bpy.data.images.load(SHEET)
    mx = n.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"; mx.inputs["Factor"].default_value = 1.0; mx.inputs[7].default_value = (0.5, 0.5, 0.54, 1)   # 白が強すぎないように紙を少し沈める
    l.new(img.outputs["Color"], mx.inputs[6]); l.new(mx.outputs[2], p.inputs["Base Color"]); p.inputs["Roughness"].default_value = 0.85
    s.data.materials.append(m)
    if parent: s.parent = parent
    return s


def cyclorama(m, y_front=-3.0, y_wall=1.5, r=0.9, height=3.2, half_w=4.0):
    """床から壁へ丸くつながる、切れ目のない背景（撮影用のホリゾント）"""
    prof = [(y_front, 0.0)] + [(y_wall - r + r * math.sin(math.pi / 2 * i / 32), r - r * math.cos(math.pi / 2 * i / 32)) for i in range(33)] + [(y_wall, height)]
    k = len(prof); verts = [(-half_w, y, z) for y, z in prof] + [(half_w, y, z) for y, z in prof]
    faces = [(i, k + i, k + i + 1, i + 1) for i in range(k - 1)]
    me = bpy.data.meshes.new("cyc"); me.from_pydata(verts, [], faces); me.update()
    for p in me.polygons: p.use_smooth = True
    o = bpy.data.objects.new("cyc", me); sc.collection.objects.link(o); o.data.materials.append(m); return o


# ════════════════════════ 場面 ════════════════════════
if MODE == "hero":
    world("#050a18", 0.35)
    cyclorama(mat("ground", "#07112a", rough=0.5, coat=0.25, sheen=0.15, bump=(700, 0.03)))
    g = group("cluster", (0.012, 0, 0)); g.rotation_euler.z = math.radians(-13)
    # 本の束（背表紙が手前）。上の本の角にスマホを立てかける
    hs = (0.031, 0.024, 0.03); z = 0.0
    cols = ("#22366a", "#d6cfbd", "#b5623c")
    offs = ((0.0, 0.0, 1.5), (0.006, 0.004, -2.5), (-0.004, 0.001, 2.0))
    Y0 = 0.0096 + 0.075                                       # 束の前の面が、スマホの背に当たる位置
    for i, h in enumerate(hs):
        book(f"book{i}", 0.215 - i * 0.012, 0.15, h, (offs[i][0], Y0 + offs[i][1], z), math.radians(offs[i][2]), cols[i], parent=g); z += h
    ph = phone(parent=g); ph.rotation_euler = (math.radians(72), 0, 0); ph.location = (0.0, 0.0, 0.0716)
    # 手前に時間割の紙と鉛筆、左奥にマグ
    sheet((0.088, -0.13, 0.0006), math.radians(-22), parent=g, size=(0.105, 0.148))      # 時間割のカード（A6）
    pencil((-0.035, -0.165, 0.001), math.radians(11), parent=g)
    mug((-0.15, 0.05, 0), parent=g, color="#1f2e55")
    # 光：左から低いあたたかい光、右奥から青い縁の光、背景にぼんやりした明るみ
    spot("key", (-0.75, -0.6, 0.46), (0.0, -0.01, 0.075), 52, 22, blend=0.9, color=(1.0, 0.78, 0.56), soft=0.05)
    area("rim", (0.5, 0.42, 0.34), (0.0, 0.02, 0.08), 9, 0.22, (0.42, 0.6, 1.0))
    gl = spot("glow", (0.0, 0.45, 2.7), (0.0, 1.0, 0.3), 1100, 50, blend=1.0, color=(0.24, 0.36, 0.9), soft=0.4); gl.visible_glossy = False   # 背景のぼんやりした明るみ（映り込みは出さない）
    camera((0.0, -0.98, 0.215), (0.0, 0.0, 0.172), 64, fstop=5.6, focus=(0.0, -0.02, 0.08))

elif MODE == "door":
    world("#03060d", 0.25)
    wallm = mat("wall", "#aeb0ad", rough=0.86, bump=(120, 0.04))
    floorm = mat("floor", "#4d5560", rough=0.16, coat=0.6, bump=(40, 0.012))
    xL, xR, DH, TH = -0.95, -0.05, 2.08, 0.16                 # 扉の開口（左端・右端・高さ）と壁の厚み
    box("floor", (14, 14, 0.05), (0, 0, -0.025), floorm)
    box("wallL", (6, TH, 9), (xL - 3, TH / 2, 4.5), wallm); box("wallR", (6, TH, 9), (xR + 3, TH / 2, 4.5), wallm)
    box("lintel", (xR - xL, TH, 9 - DH), ((xL + xR) / 2, TH / 2, DH + (9 - DH) / 2), wallm)
    box("base", (14, 0.012, 0.09), (0, -0.006, 0.045), mat("basem", "#2a2e35", rough=0.5))
    fr = mat("jamb", "#5b616b", rough=0.35, metal=0.6)
    box("jambL", (0.045, TH + 0.03, DH), (xL + 0.0225, TH / 2, DH / 2), fr, bevel=0.004); box("jambR", (0.045, TH + 0.03, DH), (xR - 0.0225, TH / 2, DH / 2), fr, bevel=0.004)
    box("jambT", (xR - xL, TH + 0.03, 0.045), ((xL + xR) / 2, TH / 2, DH - 0.0225), fr, bevel=0.004)
    # 扉（左が蝶番。部屋の内側へ開く）
    hinge = group("hinge", (xL + 0.05, TH - 0.02, 0)); LW = xR - xL - 0.1
    doorm = mat("doorm", "#8b99a8", rough=0.5, coat=0.2, bump=(200, 0.02))
    leaf = box("leaf", (LW, 0.04, DH - 0.06), (LW / 2, 0, (DH - 0.06) / 2 + 0.01), doorm, bevel=0.004)
    win = box("win", (0.13, 0.044, 0.95), (LW - 0.16, 0, 1.32), mat("frost", "#fff0d8", rough=0.35, emit="#ffc98a", strength=1.1), bevel=0.003)
    lever = box("lever", (0.13, 0.02, 0.022), (LW - 0.12, -0.05, 1.0), mat("lev", "#c9ccd2", rough=0.25, metal=1.0), bevel=0.006)
    rose = cyl("rose", 0.026, 0.012, (LW - 0.07, -0.026, 1.0), bpy.data.materials["lev"], rot=(math.radians(90), 0, 0))
    kick = box("kick", (LW - 0.02, 0.043, 0.22), (LW / 2, 0, 0.13), mat("kickm", "#6d7783", rough=0.35, metal=0.7), bevel=0.002)
    for o in (leaf, win, lever, rose, kick): o.parent = hinge
    hinge.rotation_euler.z = math.radians(66)
    # 教室の札（文字なし）
    box("plate", (0.26, 0.012, 0.085), (xL - 0.34, -0.02, 1.92), mat("platem", "#e9e6de", rough=0.5), bevel=0.004)
    # 教室の中（あたたかい明かり）
    roomw = mat("roomw", "#efe2cc", rough=0.9)
    box("rBack", (9, 0.1, 4), (0, 5.0, 2), roomw); box("rFloor", (9, 6, 0.04), (0, 2.6, -0.045), mat("rfloor", "#9a7b58", rough=0.4, coat=0.3))
    box("rCeil", (9, 4.8, 0.1), (0, 2.7, 3.0), roomw)
    area("roomTop", (-0.6, 2.6, 2.85), (-0.6, 2.6, 0), 170, 3.0, (1.0, 0.74, 0.48), glossy=False)
    spot("spill", (-1.34, 3.2, 2.0), (0.84, -2.5, 0.0), 5200, 34, blend=0.3, color=(1.0, 0.78, 0.52), soft=0.08)   # 開いたすき間を通って、廊下の床に落ちる光
    dtop = mat("dtop", "#b98f5f", rough=0.4, coat=0.3); dleg = mat("dleg", "#2f3238", rough=0.4, metal=0.8)
    for (dx, dy) in ((-0.55, 2.3), (-0.55, 3.6), (0.9, 2.9)):                      # 扉のすき間から見える机
        box("rd", (1.2, 0.45, 0.03), (dx, dy, 0.72), dtop, bevel=0.01)
        for lx in (-0.55, 0.55): box("rl", (0.03, 0.38, 0.7), (dx + lx, dy, 0.35), dleg)
    # 廊下のかすかな明かり（奥行きを出す）
    area("corr", (2.4, -2.8, 2.9), (0.6, 0, 1.2), 34, 2.4, (0.42, 0.56, 0.95), glossy=False)
    area("corrL", (-3.6, -1.6, 2.6), (-2.0, 0, 1.0), 10, 2.0, (0.42, 0.56, 0.95), glossy=False)
    # 廊下の空気（光のすじを見せる）
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -3.0, 2.0)); fog = bpy.context.object; fog.scale = (14, 6.2, 12); bpy.ops.object.transform_apply(scale=True)
    fm = bpy.data.materials.new("fog"); fm.use_nodes = True; n = fm.node_tree.nodes; l = fm.node_tree.links
    n.remove(n["Principled BSDF"]); vs = n.new("ShaderNodeVolumeScatter"); vs.inputs["Density"].default_value = 0.014; vs.inputs["Anisotropy"].default_value = 0.55
    l.new(vs.outputs["Volume"], n["Material Output"].inputs["Volume"]); fog.data.materials.append(fm)
    camera((0.62, -3.75, 1.12), (-0.22, 0.0, 1.5), 36, fstop=4.0, focus=(-0.5, 0.2, 1.1))

elif MODE == "room":
    world("#0c1426", 0.5)
    floorm = mat("floor", "#75654f", rough=0.38, coat=0.3, bump=(30, 0.015)); wallm = mat("wall", "#cbc3b4", rough=0.9)
    box("floor", (16, 20, 0.05), (0, 4, -0.025), floorm); box("ceil", (16, 20, 0.05), (0, 4, 3.1), wallm)
    box("back", (16, 0.1, 3.2), (0, 10.5, 1.6), wallm); box("right", (0.1, 20, 3.2), (4.2, 4, 1.6), wallm)
    box("sill", (0.14, 20, 0.95), (-4.2, 4, 0.475), wallm); box("head", (0.14, 20, 0.45), (-4.2, 4, 2.875), wallm)
    fr = mat("sash", "#3a3d44", rough=0.4, metal=0.5)
    for k in range(9):
        box(f"mull{k}", (0.07, 0.07, 1.75), (-4.2, -2.2 + k * 1.55, 1.82), fr)
    box("rail", (0.07, 20, 0.05), (-4.2, 4, 1.85), fr)
    box("board", (5.0, 0.05, 1.35), (0, 10.42, 1.6), mat("board", "#1f3b31", rough=0.85))
    top = mat("deskTop", "#94683f", rough=0.36, coat=0.35, bump=(60, 0.02)); leg = mat("leg", "#30333a", rough=0.35, metal=0.9); seat = mat("seat", "#41608f", rough=0.55)
    def desk(x, y, chair=True):
        box("d", (1.25, 0.45, 0.03), (x, y, 0.72), top, bevel=0.012)
        for dx in (-0.58, 0.58):
            box("l", (0.03, 0.38, 0.7), (x + dx, y, 0.35), leg)
        if chair:
            for dx in (-0.3, 0.3):
                box("s", (0.4, 0.38, 0.035), (x + dx, y - 0.5, 0.44), seat, bevel=0.02); box("b", (0.4, 0.03, 0.3), (x + dx, y - 0.69, 0.7), seat, bevel=0.012)
                for lx in (-0.17, 0.17):
                    box("cl", (0.02, 0.02, 0.44), (x + dx + lx, y - 0.5, 0.22), leg)
    for row in range(1, 6):
        for col in range(3):
            desk(-2.2 + col * 2.0, 1.2 + row * 1.5)
    desk(0.25, 1.2, chair=False)                                # 手前の机（主役を置く）
    g = group("onDesk", (0.06, 1.14, 0.735)); g.rotation_euler.z = math.radians(-12)
    b0 = book("bk", 0.2, 0.14, 0.028, (0.02, 0.085, 0), math.radians(3), "#22366a", parent=g)
    ph = phone(parent=g, glow=2.0); ph.rotation_euler = (math.radians(60), 0, 0); ph.location = (0.0, 0.0, 0.0655)
    pencil((0.16, -0.06, 0.0), math.radians(-28), parent=g)
    # 夕日（窓から低く）と空の明るみ、室内のかすかな明かり
    bpy.ops.object.light_add(type="SUN", location=(-9, 2, 3)); s = bpy.context.object
    s.data.energy = 7.0; s.data.color = (1.0, 0.62, 0.34); s.data.angle = math.radians(0.9); aim(s, (0.5, 2.6, 0.2))
    bpy.ops.mesh.primitive_plane_add(size=1, location=(-7, 4, 1.9), rotation=(0, math.radians(90), 0)); sky = bpy.context.object
    sky.scale = (3.4, 22, 1); sky.data.materials.append(mat("sky", "#000000", emit="#ffab68", strength=1.4)); sky.visible_shadow = False; sky.visible_diffuse = False
    area("fill", (1.5, -1.5, 2.6), (0, 4, 1.0), 260, 4, (0.36, 0.5, 1.0), glossy=False)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 4.5, 1.55)); fog = bpy.context.object; fog.scale = (8.2, 12, 3.0); bpy.ops.object.transform_apply(scale=True)
    fm = bpy.data.materials.new("fog"); fm.use_nodes = True; n = fm.node_tree.nodes; l = fm.node_tree.links
    n.remove(n["Principled BSDF"]); vs = n.new("ShaderNodeVolumeScatter"); vs.inputs["Density"].default_value = 0.012; vs.inputs["Anisotropy"].default_value = 0.6
    l.new(vs.outputs["Volume"], n["Material Output"].inputs["Volume"]); fog.data.materials.append(fm)
    camera((0.4, 0.5, 0.99), (-0.55, 4.4, 1.4), 30, fstop=2.2, focus=(0.06, 1.14, 0.8))

# ── 書き出し ──
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.use_denoising = True; sc.cycles.denoiser = "OPENIMAGEDENOISE"
sc.cycles.max_bounces = 6; sc.cycles.volume_bounces = 0; sc.cycles.volume_step_rate = 2.0
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - High Contrast"
sc.render.resolution_x, sc.render.resolution_y = 1080, 1350
if Q == "preview":
    sc.render.resolution_percentage = 40; sc.cycles.samples = 48
else:
    sc.render.resolution_percentage = 100; sc.cycles.samples = 256
sc.render.filepath = os.path.join(OUT, f"{MODE}2_{Q}.png"); bpy.ops.render.render(write_still=True)
print("書き出し", sc.render.filepath)
