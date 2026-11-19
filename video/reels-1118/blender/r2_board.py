"""リール2 v4 の背景：昼間の教室の黒板（Blender 4.5 / Cycles）。静止画を2枚描く。
  ../../blendervenv/bin/python r2_board.py preview      # 小さく試す
  ../../blendervenv/bin/python r2_board.py render       # 本番（board.png 1080×1920・eraser.png 背景透明）
  ../../blendervenv/bin/python r2_board.py eraser       # 黒板消しだけ描き直す
動きと文字はすべて HTML（r2d.html）で重ねる。3本目（紺のスタジオ）と雰囲気を変えるため、窓から日が差す明るい教室にする。"""
import bpy, math, os, random, sys
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets")
random.seed(5)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def lin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


def node_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    return m, m.node_tree.nodes, m.node_tree.links, m.node_tree.nodes["Principled BSDF"]


def simple(name, color, rough=0.5, metal=0.0):
    m, n, l, p = node_mat(name)
    p.inputs["Base Color"].default_value = (*lin(color), 1); p.inputs["Roughness"].default_value = rough; p.inputs["Metallic"].default_value = metal
    return m


def box(name, size, loc, mat, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.object; o.name = name
    o.scale = size; bpy.ops.object.transform_apply(scale=True)
    if bevel:
        md = o.modifiers.new("b", "BEVEL"); md.width = bevel; md.segments = 3
    o.data.materials.append(mat); return o


# ── 黒板（深い緑。消したあとの白いむらと、細かいざらつき） ──
m, n, l, p = node_mat("board")
tex = n.new("ShaderNodeTexNoise"); tex.inputs["Scale"].default_value = 2.2; tex.inputs["Detail"].default_value = 6
tex2 = n.new("ShaderNodeTexNoise"); tex2.inputs["Scale"].default_value = 60; tex2.inputs["Detail"].default_value = 2
ramp = n.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].position = 0.45; ramp.color_ramp.elements[1].position = 0.75
ramp.color_ramp.elements[0].color = (*lin("#14302a"), 1); ramp.color_ramp.elements[1].color = (*lin("#2b4b41"), 1)   # 消し跡の白っぽいむら
mix = n.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"; mix.inputs["Factor"].default_value = 0.25
gray = n.new("ShaderNodeRGBToBW"); l.new(tex2.outputs["Color"], gray.inputs["Color"])
l.new(tex.outputs["Fac"], ramp.inputs["Fac"]); l.new(ramp.outputs["Color"], mix.inputs[6])
l.new(gray.outputs["Val"], mix.inputs[7]); l.new(mix.outputs[2], p.inputs["Base Color"])
p.inputs["Roughness"].default_value = 0.85
bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.08; l.new(tex2.outputs["Fac"], bump.inputs["Height"]); l.new(bump.outputs["Normal"], p.inputs["Normal"])
board = box("board", (6.0, 0.04, 3.4), (0, 0, 1.9), m)
alu = simple("alu", "#b9bcc1", rough=0.35, metal=1.0)
for z in (0.2 - 0.03, 3.6 + 0.03):
    box("frameH", (6.12, 0.08, 0.06), (0, -0.01, z), alu, 0.01)
for x in (-3.03, 3.03):
    box("frameV", (0.06, 0.08, 3.52), (x, -0.01, 1.9), alu, 0.01)
# 粉受け
tray = box("tray", (6.1, 0.18, 0.04), (0, -0.1, 0.16), alu, 0.01)
box("lip", (6.1, 0.02, 0.05), (0, -0.19, 0.19), alu, 0.005)
# チョーク（白・赤・黄）と粉
chalk_cols = ["#f4f2ea", "#f4f2ea", "#e05a4f", "#f2cf4a", "#f4f2ea"]
for k, c in enumerate(chalk_cols):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.012, depth=random.uniform(0.07, 0.11), vertices=16,
                                        location=(0.6 + k * 0.13 + random.uniform(-0.02, 0.02), -0.11, 0.19), rotation=(0, math.radians(90), math.radians(random.uniform(-15, 15))))
    bpy.context.object.data.materials.append(simple(f"chalk{k}", c, rough=0.95))
# 黒板消し（粉受けの上）
felt = simple("felt", "#2f6aa6", rough=0.95); top = simple("etop", "#d9d4c7", rough=0.6)
box("eraser_felt", (0.26, 0.09, 0.025), (-1.4, -0.11, 0.195), felt, 0.008)
box("eraser_top", (0.26, 0.09, 0.04), (-1.4, -0.11, 0.225), top, 0.012)
# 壁（明るいクリーム色）と床
wall = simple("wall", "#b9ab90", rough=0.9)          # 真っ白に見えないよう、落ち着いた砂色に（v4.1）
box("wall", (14, 0.05, 8), (0, 0.06, 3.0), wall)
box("floor", (14, 8, 0.05), (0, -3.5, -0.9), simple("floor", "#b08a5e", rough=0.6))

# ── 光：左の窓から差す日の光（窓枠の影が黒板に落ちる）と、部屋のやわらかい明かり ──
bpy.ops.object.light_add(type="SUN", location=(-6, -6, 6)); sun = bpy.context.object
sun.data.energy = 6.5; sun.data.color = (1.0, 0.9, 0.75); sun.data.angle = math.radians(2.5)
sun.rotation_euler = (Vector((0, 0, 1.9)) - Vector((-6, -5, 5))).to_track_quat("-Z", "Y").to_euler()
# 窓枠（光をさえぎる格子。カメラには映らない）
win = simple("win", "#222222")
# v6：窓枠の十字の影は「黒い影が気になる」とのことで外した（日の光のやわらかい明暗だけ残す）
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (*lin("#d8dde6"), 1); w.node_tree.nodes["Background"].inputs[1].default_value = 0.35
bpy.ops.object.light_add(type="AREA", location=(2, -5, 3.5)); f = bpy.context.object
f.data.energy = 220; f.data.size = 5; f.data.color = (0.95, 0.97, 1.0)
f.rotation_euler = (Vector((0, 0, 1.9)) - Vector((2, -5, 3.5))).to_track_quat("-Z", "Y").to_euler()

# ── カメラ（正面。黒板が画面いっぱい、下に粉受け） ──
bpy.ops.object.camera_add(location=(0.15, -3.55, 1.76)); cam = bpy.context.object; sc.camera = cam   # 寄せて、黒板で画面をほぼ埋める（v4.1）
cam.rotation_euler = (math.radians(90), 0, 0); cam.data.lens = 30
cam.data.dof.use_dof = True; cam.data.dof.focus_distance = 3.55; cam.data.dof.aperture_fstop = 5.6

sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.use_denoising = True; sc.cycles.denoiser = "OPENIMAGEDENOISE"
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
os.makedirs(OUT, exist_ok=True)
mode = sys.argv[1]
if mode == "preview":
    sc.render.resolution_percentage = 40; sc.cycles.samples = 24
    sc.render.filepath = os.path.join(OUT, "board_pv.png"); bpy.ops.render.render(write_still=True)
else:
    sc.render.resolution_percentage = 100; sc.cycles.samples = 96
    if mode == "render":
        sc.render.filepath = os.path.join(OUT, "board.png"); bpy.ops.render.render(write_still=True)
    # 黒板消しだけを、背景を透かして上から描く（HTML で動かす）
    for o in list(sc.objects):
        if o.type == "MESH" and not o.name.startswith("eraser"): o.hide_render = True
    sc.render.film_transparent = True
    bpy.ops.object.camera_add(location=(-1.4, -0.11, 1.0)); c2 = bpy.context.object; c2.rotation_euler = (0, 0, 0)   # 真上から（黒板に当てたときに見える面）
    c2.data.type = "ORTHO"; c2.data.ortho_scale = 0.42; sc.camera = c2
    sc.render.resolution_x, sc.render.resolution_y = 900, 600; sc.cycles.samples = 48
    sc.render.filepath = os.path.join(OUT, "eraser.png"); bpy.ops.render.render(write_still=True)
