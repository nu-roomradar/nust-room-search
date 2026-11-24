"""クリスマスモードの「カミングスーン」予告（リール⑥）の 3D（Blender 4.5 / Cycles）。
参考にしたのは、季節の見た目の予告動画の作り方（暗闇に光る形 → 引くと画面の中だったと分かる → 雷のような音で場面が変わる →
最後に地面から何かが飛び出して暗転）。特定の会社の映像・ロゴ・曲は使わない。中身はクリスマスと RoomRadar に置きかえる。
  <blendervenv>/bin/python teaser.py night <preview|anim>   夜の教室。机のスマホ（クリスマスの見た目の画面）に寄ったところから引く（0〜5.5秒）
  <blendervenv>/bin/python teaser.py door  <preview|final>  夜の廊下。リースとサンタの帽子をつけた教室の扉（1枚。動きは HTML）
  <blendervenv>/bin/python teaser.py gift  <preview|anim>   雪の上。光る飾り玉の手前で、雪の中からプレゼントの箱が飛び出す（2秒）
ヘルパーは ../ad-1119/scene2.py の前半をそのまま使う（同じ質感にそろえるため）。"""
import os, sys, math, random
MYDIR = os.path.dirname(os.path.abspath(__file__))
HERE = MYDIR
AD = os.path.abspath(os.path.join(MYDIR, "..", "ad-1119"))
MODE, Q = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "preview")
src = open(os.path.join(AD, "scene2.py"), encoding="utf-8").read().split('\nif MODE == "hero":')[0]
_argv = sys.argv; sys.argv = [os.path.join(AD, "scene2.py"), "hero", "preview"]
exec(compile(src.replace('HERE = os.path.dirname(os.path.abspath(__file__))', f'HERE = {AD!r}'), "scene2_helpers", "exec"))
sys.argv = _argv
MODE, Q = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "preview")   # 上の exec が MODE・Q を書きかえるので、もう一度
import bpy
from mathutils import Vector
SCREEN = os.path.join(MYDIR, "assets", "xmas_screen.png")      # クリスマスの見た目の画面（capture.py の xmas.png の上から1画面）
OUT = os.path.join(MYDIR, "renders", MODE); os.makedirs(OUT, exist_ok=True)
FPS = 30
random.seed(5)


def emis(name, color, strength):
    return mat(name, color, rough=0.4, emit=color, strength=strength)


def sphere(name, r, loc, m, seg=32):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=seg, ring_count=seg // 2); o = bpy.context.object; o.name = name
    bpy.ops.object.shade_smooth(); o.data.materials.append(m); return o


def keycam(cam, focus, keys):
    for t, cl, fl in keys:
        f = int(round(t * FPS))
        cam.location = cl; cam.keyframe_insert("location", frame=f)
        focus.location = fl; focus.keyframe_insert("location", frame=f)


def track_cam(loc, target, lens, fstop):
    bpy.ops.object.empty_add(location=target); focus = bpy.context.object; focus.name = "focus"
    bpy.ops.object.camera_add(location=loc); cam = bpy.context.object; sc.camera = cam
    cam.data.lens = lens; cam.data.sensor_fit = "VERTICAL"; cam.data.sensor_height = 24; cam.data.clip_start = 0.002
    cam.data.dof.use_dof = True; cam.data.dof.focus_object = focus; cam.data.dof.aperture_fstop = fstop
    c = cam.constraints.new("TRACK_TO"); c.target = focus; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
    return cam, focus


if MODE == "night":
    F0, F1 = 0, 165
    world("#02040a", 0.25)
    floorm = mat("floor", "#4a4136", rough=0.4, coat=0.3, bump=(30, 0.015)); wallm = mat("wall", "#6f6a62", rough=0.9)
    box("floor", (16, 20, 0.05), (0, 4, -0.025), floorm); box("ceil", (16, 20, 0.05), (0, 4, 3.1), wallm)
    box("back", (16, 0.1, 3.2), (0, 10.5, 1.6), wallm); box("right", (0.1, 20, 3.2), (4.2, 4, 1.6), wallm)
    box("sill", (0.14, 20, 0.95), (-4.2, 4, 0.475), wallm); box("head", (0.14, 20, 0.45), (-4.2, 4, 2.875), wallm)
    fr = mat("sash", "#2a2d33", rough=0.4, metal=0.5)
    for k in range(9): box(f"mull{k}", (0.07, 0.07, 1.75), (-4.2, -2.2 + k * 1.55, 1.82), fr)
    box("board", (5.0, 0.05, 1.35), (0, 10.42, 1.6), mat("board", "#16291f", rough=0.85))
    top = mat("deskTop", "#7a5636", rough=0.36, coat=0.35, bump=(60, 0.02)); leg = mat("leg", "#24272d", rough=0.35, metal=0.9); seat = mat("seat", "#2c4166", rough=0.55)
    def desk(x, y, chair=True):
        box("d", (1.25, 0.45, 0.03), (x, y, 0.72), top, bevel=0.012)
        for dx in (-0.58, 0.58): box("l", (0.03, 0.38, 0.7), (x + dx, y, 0.35), leg)
        if chair:
            for dx in (-0.3, 0.3):
                box("s", (0.4, 0.38, 0.035), (x + dx, y - 0.5, 0.44), seat, bevel=0.02); box("b", (0.4, 0.03, 0.3), (x + dx, y - 0.69, 0.7), seat, bevel=0.012)
    for row in range(1, 6):
        for col in range(3): desk(-2.2 + col * 2.0, 1.2 + row * 1.5)
    desk(0.25, 1.2, chair=False)
    g = group("onDesk", (0.24, 1.06, 0.735)); g.rotation_euler.z = math.radians(-8)
    book("bk", 0.2, 0.14, 0.028, (0.02, 0.085, 0), math.radians(3), "#22366a", parent=g)
    ph = phone(parent=g, glow=2.6); ph.rotation_euler = (math.radians(60), 0, 0); ph.location = (0.0, 0.0, 0.0655)
    # 窓の外：月明かりの夜空と、降る雪
    bpy.ops.mesh.primitive_plane_add(size=1, location=(-7, 4, 1.9), rotation=(0, math.radians(90), 0)); sky = bpy.context.object
    sky.scale = (3.4, 22, 1); sky.data.materials.append(mat("sky", "#000000", emit="#1d3566", strength=0.9)); sky.visible_shadow = False
    snowm = emis("snow", "#e8f0ff", 1.6)
    flakes = []
    for k in range(260):
        o = sphere(f"fl{k}", random.uniform(0.008, 0.02), (random.uniform(-6.6, -4.4), random.uniform(-2, 10), random.uniform(0.2, 3.4)), snowm, seg=8)
        flakes.append((o, o.location.z, random.uniform(0.35, 0.8)))
    for f in range(F0, F1 + 1, 15):                                             # 雪は 0.5 秒ごとにキーを打つ（ゆっくり落ちる）
        for o, z0, v in flakes:
            o.location.z = (z0 - v * f / FPS) % 3.4 + 0.1; o.keyframe_insert("location", index=2, frame=f)
    for o, _, _ in flakes:
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points: kp.interpolation = "LINEAR"
    # 月明かり（窓から青く）と、黒板の上の小さな電球の飾り
    bpy.ops.object.light_add(type="SUN", location=(-9, 2, 4)); s = bpy.context.object
    s.data.energy = 2.6; s.data.color = (0.55, 0.68, 1.0); s.data.angle = math.radians(1.2); aim(s, (0.5, 2.6, 0.2))
    cols = ["#ff3b3b", "#ffcf4a", "#3bd16f", "#ffffff"]
    for k in range(26):
        x = -2.4 + k * 0.19
        sphere(f"bulb{k}", 0.022, (x, 10.33, 2.36 - 0.06 * math.sin(k * 0.55) ** 2), emis(f"bm{k}", cols[k % 4], 9.0), seg=12)
    area("fill", (1.5, -1.5, 2.6), (0, 4, 1.0), 120, 4, (0.36, 0.5, 1.0), glossy=False)
    area("warm", (-0.6, 9.6, 2.6), (0, 6, 1.0), 60, 3, (1.0, 0.7, 0.45), glossy=False)
    # スマホの画面の光が、机と本にあたる
    area("screenGlow", (0.24, 1.0, 0.86), (0.24, 1.15, 0.73), 2.2, 0.08, (0.9, 0.95, 1.0), glossy=False)
    bpy.context.view_layer.update()
    # 画面の中の星（ロゴの右上）の位置：画面の横 90%・上から 9%（撮った画面で測った）
    Wp, Hp = 0.0716 - 0.0044, 0.147 - 0.0044
    star = ph.matrix_world @ Vector(((0.90 - 0.5) * Wp, (0.5 - 0.092) * Hp, 0.0045))
    scr_c = ph.matrix_world @ Vector((0, 0, 0.0045))
    nrm = (ph.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
    cam, focus = track_cam(star + nrm * 0.05, star, 50, 2.8)
    keycam(cam, focus, [
        (0.0, star + nrm * 0.045, star),
        (1.6, star + nrm * 0.075 + Vector((0, 0, 0.004)), star),
        (3.3, scr_c + nrm * 0.24 + Vector((0.03, 0, 0.02)), scr_c),
        (5.5, scr_c + Vector((0.16, -0.42, 0.17)), scr_c + Vector((0.0, 0.05, 0.035))),
    ])
    for ob in (cam, focus):
        for fc in ob.animation_data.action.fcurves:
            for kp in fc.keyframe_points: kp.interpolation = "BEZIER"; kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
    cam.data.dof.aperture_fstop = 2.0

elif MODE == "door":
    F0 = F1 = 0
    world("#02040a", 0.2)
    wallm = mat("wall", "#7e807c", rough=0.86, bump=(120, 0.04)); floorm = mat("floor", "#2f353e", rough=0.14, coat=0.6, bump=(40, 0.012))
    xL, xR, DH, TH = -0.95, -0.05, 2.08, 0.16
    box("floor", (14, 14, 0.05), (0, 0, -0.025), floorm)
    box("wallL", (6, TH, 9), (xL - 3, TH / 2, 4.5), wallm); box("wallR", (6, TH, 9), (xR + 3, TH / 2, 4.5), wallm)
    box("lintel", (xR - xL, TH, 9 - DH), ((xL + xR) / 2, TH / 2, DH + (9 - DH) / 2), wallm)
    fr = mat("jamb", "#4b5059", rough=0.35, metal=0.6)
    box("jambL", (0.045, TH + 0.03, DH), (xL + 0.0225, TH / 2, DH / 2), fr, bevel=0.004); box("jambR", (0.045, TH + 0.03, DH), (xR - 0.0225, TH / 2, DH / 2), fr, bevel=0.004)
    box("jambT", (xR - xL, TH + 0.03, 0.045), ((xL + xR) / 2, TH / 2, DH - 0.0225), fr, bevel=0.004)
    hinge = group("hinge", (xL + 0.05, TH - 0.02, 0)); LW = xR - xL - 0.1
    doorm = mat("doorm", "#7d8a98", rough=0.5, coat=0.2, bump=(200, 0.02))
    leaf = box("leaf", (LW, 0.04, DH - 0.06), (LW / 2, 0, (DH - 0.06) / 2 + 0.01), doorm, bevel=0.004)
    win = box("win", (0.13, 0.044, 0.95), (LW - 0.16, 0, 1.32), mat("frost", "#ffe2c8", rough=0.35, emit="#ff9c6a", strength=1.2), bevel=0.003)
    lever = box("lever", (0.13, 0.02, 0.022), (LW - 0.12, -0.05, 1.0), mat("lev", "#c9ccd2", rough=0.25, metal=1.0), bevel=0.006)
    # 扉のリース（緑の輪に赤い実と、赤いリボン）
    bpy.ops.mesh.primitive_torus_add(major_radius=0.16, minor_radius=0.05, major_segments=48, minor_segments=16, location=(LW / 2 - 0.08, -0.05, 1.42), rotation=(math.radians(90), 0, 0))
    wr = bpy.context.object; wr.name = "wreath"; bpy.ops.object.shade_smooth(); wr.data.materials.append(mat("wreath", "#1f5a2c", rough=0.7, bump=(400, 0.4)))
    md = wr.modifiers.new("d", "DISPLACE"); tex = bpy.data.textures.new("n", "CLOUDS"); tex.noise_scale = 0.03; md.texture = tex; md.strength = 0.02
    for k in range(14):
        a = k / 14 * 2 * math.pi
        sphere(f"berry{k}", 0.014, (LW / 2 - 0.08 + math.cos(a) * 0.17, -0.09, 1.42 + math.sin(a) * 0.17), emis(f"bb{k}", "#d81e2a", 0.6) if k % 2 else mat(f"bb{k}", "#b8141e", rough=0.3, coat=0.8), seg=12)
    rib = mat("ribbon", "#c4141f", rough=0.35, coat=0.6, sheen=0.4)
    box("bowL", (0.09, 0.02, 0.06), (LW / 2 - 0.13, -0.1, 1.27), rib, bevel=0.01, rot=(0, math.radians(25), 0))
    box("bowR", (0.09, 0.02, 0.06), (LW / 2 - 0.03, -0.1, 1.27), rib, bevel=0.01, rot=(0, math.radians(-25), 0))
    for o in list(bpy.context.scene.objects):
        if o.name.startswith(("leaf", "win", "lever", "wreath", "berry", "bow")) and o.parent is None and o.name != "hinge": o.parent = hinge
    hinge.rotation_euler.z = math.radians(58)
    # 扉の枠の上にのったサンタの帽子（扉が仮装している）
    hatm = mat("hat", "#c3131d", rough=0.75, sheen=0.8, bump=(600, 0.2)); furm = mat("fur", "#f4f1ea", rough=0.95, sheen=1.0, bump=(900, 0.5))
    hx, hz = (xL + xR) / 2 - 0.05, DH + 0.02
    th, L = math.radians(28), 0.5                              # 右へ傾けた帽子。先にぽんぽん
    bpy.ops.mesh.primitive_cone_add(radius1=0.24, radius2=0.015, depth=L, vertices=48,
                                    location=(hx + L / 2 * math.sin(th), 0.02, hz + 0.03 + L / 2 * math.cos(th)), rotation=(0, th, 0)); hat = bpy.context.object
    bpy.ops.object.shade_smooth(); hat.data.materials.append(hatm)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.24, minor_radius=0.055, location=(hx, 0.02, hz + 0.03), rotation=(0, th, 0)); brim = bpy.context.object; bpy.ops.object.shade_smooth(); brim.data.materials.append(furm)
    sphere("pom", 0.06, (hx + L * math.sin(th), 0.02, hz + 0.03 + L * math.cos(th)), furm)
    # 扉の枠に沿った小さな電球
    cols = ["#ff3b3b", "#ffcf4a", "#3bd16f", "#ffffff"]
    for k in range(18):
        t = k / 17
        if t < 0.33: p = (xL - 0.06, -0.03, 0.3 + t / 0.33 * (DH - 0.2))
        elif t < 0.67: p = (xL - 0.06 + (t - 0.33) / 0.34 * (xR - xL + 0.12), -0.03, DH + 0.08 - 0.03 * math.sin((t - 0.33) / 0.34 * math.pi))
        else: p = (xR + 0.06, -0.03, DH - 0.2 - (t - 0.67) / 0.33 * (DH - 0.5))
        sphere(f"lb{k}", 0.018, p, emis(f"lbm{k}", cols[k % 4], 10.0), seg=12)
    # 教室の中（赤みのあるあたたかい明かり）と、こぼれる光
    roomw = mat("roomw", "#e9d4bd", rough=0.9)
    box("rBack", (9, 0.1, 4), (0, 5.0, 2), roomw); box("rFloor", (9, 6, 0.04), (0, 2.6, -0.045), mat("rfloor", "#8a6a48", rough=0.4, coat=0.3))
    box("rCeil", (9, 4.8, 0.1), (0, 2.7, 3.0), roomw)
    area("roomTop", (-0.6, 2.6, 2.85), (-0.6, 2.6, 0), 160, 3.0, (1.0, 0.62, 0.42), glossy=False)
    spot("spill", (-1.34, 3.2, 2.0), (0.84, -2.5, 0.0), 5200, 34, blend=0.3, color=(1.0, 0.6, 0.42), soft=0.08)
    area("corr", (2.4, -2.8, 2.9), (0.6, 0, 1.2), 70, 2.4, (0.42, 0.56, 0.95), glossy=False)
    area("hatkey", (0.6, -1.2, 2.8), (-0.5, 0.0, 2.2), 45, 1.0, (1.0, 0.85, 0.75), glossy=False)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -3.0, 2.0)); fog = bpy.context.object; fog.scale = (14, 6.2, 12); bpy.ops.object.transform_apply(scale=True)
    fm = bpy.data.materials.new("fog"); fm.use_nodes = True; n = fm.node_tree.nodes; l = fm.node_tree.links
    n.remove(n["Principled BSDF"]); vs = n.new("ShaderNodeVolumeScatter"); vs.inputs["Density"].default_value = 0.016; vs.inputs["Anisotropy"].default_value = 0.55
    l.new(vs.outputs["Volume"], n["Material Output"].inputs["Volume"]); fog.data.materials.append(fm)
    camera((0.3, -2.55, 1.3), (-0.42, 0.0, 1.55), 30, fstop=4.0, focus=(-0.5, 0.0, 1.5))

elif MODE == "gift":
    F0, F1 = 0, 66
    world("#0b1530", 0.5)
    # 雪の地面（でこぼこ）
    bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 1.6, 0)); gnd = bpy.context.object
    bpy.ops.object.modifier_add(type="SUBSURF"); gnd.modifiers[-1].levels = 8; gnd.modifiers[-1].render_levels = 8; gnd.modifiers[-1].subdivision_type = "SIMPLE"
    md = gnd.modifiers.new("d", "DISPLACE"); tex = bpy.data.textures.new("sn", "CLOUDS"); tex.noise_scale = 0.18; md.texture = tex; md.strength = 0.05
    gnd.data.materials.append(mat("snowg", "#c9d6ea", rough=0.92, sheen=0.8, bump=(80, 0.6))); bpy.ops.object.shade_smooth()
    # 奥に光る飾り玉が2つ（左右）
    for x, c in ((-0.21, "#ff3040"), (0.23, "#ffc640")):
        sphere(f"orn{x}", 0.08, (x, 1.0, 0.1), mat(f"om{x}", c, rough=0.15, metal=0.4, coat=1.0, emit=c, strength=2.2), seg=48)
        cyl(f"cap{x}", 0.022, 0.03, (x, 1.0, 0.19), mat(f"cm{x}", "#c8b58a", rough=0.3, metal=1.0))
        bpy.ops.object.light_add(type="POINT", location=(x, 0.92, 0.14)); L = bpy.context.object; L.data.energy = 18; L.data.color = [v for v in lin(c)]; L.data.shadow_soft_size = 0.1
    # プレゼントの箱（赤い箱に金のリボン）。雪の下から飛び出す
    g = group("gift", (0.0, 0.35, -0.32))
    boxm = mat("giftm", "#b5121c", rough=0.45, coat=0.5, sheen=0.3); ribm = mat("rib", "#e8c25a", rough=0.25, metal=0.8, coat=0.4)
    b0 = box("gbody", (0.26, 0.26, 0.22), (0, 0, 0.11), boxm, bevel=0.006)
    lid = box("glid", (0.28, 0.28, 0.06), (0, 0, 0.25), boxm, bevel=0.006)
    r1 = box("r1", (0.035, 0.265, 0.225), (0, 0, 0.11), ribm); r2 = box("r2", (0.265, 0.035, 0.225), (0, 0, 0.11), ribm)
    r3 = box("r3", (0.04, 0.285, 0.065), (0, 0, 0.25), ribm); r4 = box("r4", (0.285, 0.04, 0.065), (0, 0, 0.25), ribm)
    bw1 = box("bw1", (0.12, 0.03, 0.07), (-0.05, 0, 0.31), ribm, bevel=0.012, rot=(0, math.radians(30), 0))
    bw2 = box("bw2", (0.12, 0.03, 0.07), (0.05, 0, 0.31), ribm, bevel=0.012, rot=(0, math.radians(-30), 0))
    for o in (b0, lid, r1, r2, r3, r4, bw1, bw2): o.parent = g
    for f, z, rot in ((0, -0.32, 0), (22, -0.32, 0), (30, 0.10, -6), (36, 0.03, 4), (41, 0.0, -2), (46, 0.0, 0), (66, 0.0, 0)):
        g.location.z = z; g.keyframe_insert("location", index=2, frame=f)
        g.rotation_euler.y = math.radians(rot); g.keyframe_insert("rotation_euler", index=1, frame=f)
    # 飛び散る雪
    snowm = mat("puff", "#eef3ff", rough=0.8, sheen=0.6)
    for k in range(70):
        o = sphere(f"pf{k}", random.uniform(0.004, 0.011), (0, 0.35, -0.1), snowm, seg=14)
        a = random.uniform(0, 2 * math.pi); r = random.uniform(0.12, 0.5); up = random.uniform(0.15, 0.55)
        o.scale = (0.001,) * 3; o.keyframe_insert("scale", frame=24)
        o.scale = (1, 1, 1); o.keyframe_insert("scale", frame=26)
        o.location = (0, 0.35, 0.0); o.keyframe_insert("location", frame=25)
        o.location = (math.cos(a) * r * 0.6, 0.35 + math.sin(a) * r * 0.4, up); o.keyframe_insert("location", frame=33)
        o.location = (math.cos(a) * r, 0.35 + math.sin(a) * r * 0.6, 0.01); o.keyframe_insert("location", frame=46 + random.randint(0, 10))
    # 月明かりと、降る雪
    bpy.ops.object.light_add(type="SUN", location=(-3, -2, 5)); s = bpy.context.object
    s.data.energy = 0.45; s.data.color = (0.6, 0.72, 1.0); s.data.angle = math.radians(2); aim(s, (0, 0.5, 0))
    area("rimG", (0.8, 1.6, 0.8), (0, 0.35, 0.15), 12, 0.8, (1.0, 0.8, 0.6))
    fallm = emis("fall", "#e8f0ff", 1.2)
    falls = []
    for k in range(120):
        o = sphere(f"fs{k}", random.uniform(0.003, 0.008), (random.uniform(-0.9, 0.9), random.uniform(-0.2, 2.0), random.uniform(0, 1.6)), fallm, seg=8)
        falls.append((o, o.location.z, random.uniform(0.2, 0.5)))
    for f in (F0, F1):
        for o, z0, v in falls:
            o.location.z = (z0 - v * f / FPS) % 1.6; o.keyframe_insert("location", index=2, frame=f)
    for o, _, _ in falls:
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points: kp.interpolation = "LINEAR"
    cam, focus = track_cam((0.05, -0.75, 0.22), (0.0, 0.4, 0.14), 34, 2.8)
    keycam(cam, focus, [(0.0, (0.05, -0.75, 0.22), (0.0, 0.4, 0.1)), (2.2, (0.03, -0.66, 0.24), (0.0, 0.38, 0.16))])

# ── 書き出し ──
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.use_denoising = True; sc.cycles.denoiser = "OPENIMAGEDENOISE"
sc.cycles.max_bounces = 5; sc.cycles.volume_bounces = 0; sc.cycles.volume_step_rate = 2.0
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - High Contrast"
sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
sc.render.use_persistent_data = True
if Q == "preview":
    sc.render.resolution_percentage = 33; sc.cycles.samples = 24
    frames = [F0] if F0 == F1 else [F0, (F0 + F1) // 2, F1] if MODE == "night" else [0, 26, 31, 40]
elif Q == "final":
    sc.render.resolution_percentage = 100; sc.cycles.samples = 128; frames = [F0]
else:                                                         # anim：720×1280・少ないサンプル＋ノイズ除去（CPU のため）
    sc.render.resolution_percentage = 67; sc.cycles.samples = 20; frames = list(range(F0, F1 + 1))
for f in frames:
    path = os.path.join(OUT, f"{'pv_' if Q == 'preview' else ''}f{f:04d}.png")
    if Q == "anim" and os.path.exists(path): continue
    sc.frame_set(f); sc.render.filepath = path; bpy.ops.render.render(write_still=True)
    print("書き出し", path, flush=True)
