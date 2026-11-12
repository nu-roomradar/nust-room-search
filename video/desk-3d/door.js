// RoomRadar 3D 広告その2「ポスターとドア」— 夕方の廊下。掲示板の「どこ行く？」ポスター → スマホで QR を読み取る →
// 空き教室が見つかる → 友達と教室に入る → 閉まったドアにロゴ（縦 1080×1920・27秒）。
// 時刻 t（秒）だけで全部が決まる。書き出しは render.py --page door.html が window.renderAt(t) を1コマずつ呼ぶ。
// 人の姿は映さない。夕方の光でできる影だけが壁を通ってドアに入っていく（影を落とす形は描かない）。実在の人物・AI 生成の映像は使わない。
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { TEAL, clamp01, seg, ss, sss, eo, lerp, rnd, V3, loadImg, mkCanvas, texFrom, rr, loadFonts, noiseTex, glowTex, cookieTex, DofPass, GradeShader } from "./common.js";

const W = 1080, H = 1920, FPS = 30, DURATION = 27;
const Q = new URLSearchParams(location.search);

// ───────── 時間の割り振り ─────────
const T = {
  phoneIn: 3.3, phoneInEnd: 4.3, lock: 5.0, chip: 5.35, tapChip: 6.05, toApp: 6.2,     // 1 ポスター → 2 QR を読み取る
  capAIn: 6.9, capAOut: 9.7, scroll: 8.0,                                              // 3 一覧が出る
  hi: 10.0, capBIn: 10.1, capBOut: 12.8,                                               //   空いてる教室、あった
  phoneOut: 12.8,
  walk: 13.5, doorClose: 18.55, doorShut: 19.35,                                       // 4 友達と教室へ → ドアが閉まる
  logoIn: 19.8, ring: 20.45, wordIn: 20.3, noticeIn: 20.6,                             // 5 ロゴと必須の表記
};

// ───────── 場所（単位 m）。壁は z=0、廊下は z>0、教室は z<0。ドアは x=0.55〜1.45 ─────────
const DOOR = { x0: 0.55, w: 0.9, h: 2.05, cx: 1.0 };
const POSTER = { w: 0.297, h: 0.420, x: -1.05, y: 1.47 };                               // A3
const QR = { x: POSTER.x + (0.146 - 0.5) * POSTER.w, y: POSTER.y + (0.5 - 0.710) * POSTER.h };   // ポスターの左下の QR

function corkTex() {
  const c = mkCanvas(512, 512), x = c.getContext("2d"), r = rnd(21);
  x.fillStyle = "#a47a4d"; x.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 9000; i++) { const v = r(); x.fillStyle = `rgba(${60 + v * 120},${40 + v * 80},${20 + v * 40},${0.10 + r() * 0.25})`; x.beginPath(); x.arc(r() * 512, r() * 512, 0.6 + r() * 2.4, 0, 7); x.fill(); }
  const t = texFrom(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(3, 2); return t;
}
function memoTex(seed, tint) {            // ほかの掲示（読めない灰色の線だけ。実在の掲示物は写さない）
  const c = mkCanvas(420, 594), x = c.getContext("2d"), r = rnd(seed);
  x.fillStyle = tint; x.fillRect(0, 0, 420, 594);
  x.fillStyle = "rgba(60,60,60,0.55)"; x.fillRect(40, 48, 220 + r() * 80, 26);
  x.fillStyle = "rgba(90,90,90,0.30)"; for (let i = 0; i < 13; i++) x.fillRect(40, 110 + i * 32, 200 + r() * 140, 9);
  return texFrom(c);
}
function plateTex(text) {
  const c = mkCanvas(400, 200), x = c.getContext("2d");
  x.fillStyle = "#ece8df"; x.fillRect(0, 0, 400, 200);
  x.fillStyle = "#22211f"; x.font = "800 128px Syne"; x.textAlign = "center"; x.textBaseline = "middle"; x.fillText(text, 200, 108);
  return texFrom(c);
}

// 影を落とすための人の形（姿は描かない。壁と床に落ちる影だけを見せる）
function makePerson(o) {
  const g = new THREE.Group(), k = o.h / 1.7, hip = 0.90 * k, sh = 1.42 * k;
  const mat = () => new THREE.MeshBasicMaterial({ color: 0x000000 });
  const cast = (m) => { m.castShadow = true; return m; };
  const legs = [-1, 1].map((sx) => {
    const p = new THREE.Group(); p.position.set(sx * 0.085 * k, hip, 0);
    const m = cast(new THREE.Mesh(new THREE.CapsuleGeometry((o.wide ? 0.085 : 0.07) * k, 0.72 * k, 6, 12), mat())); m.position.y = -0.43 * k; p.add(m);
    const shoe = cast(new THREE.Mesh(new RoundedBoxGeometry(0.10 * k, 0.07 * k, 0.26 * k, 2, 0.03 * k), mat())); shoe.position.set(0, -0.865 * k, -0.05 * k); p.add(shoe);
    g.add(p); return p; });
  // 胴（腰は細め・肩は広め）と肩
  const hips = cast(new THREE.Mesh(new THREE.CapsuleGeometry(0.150 * k, 0.16 * k, 8, 16), mat())); hips.scale.z = 0.66; hips.position.y = hip + 0.08 * k; g.add(hips);
  const chest = cast(new THREE.Mesh(new THREE.CapsuleGeometry(0.165 * k, 0.20 * k, 8, 16), mat())); chest.scale.z = 0.64; chest.position.y = sh - 0.16 * k; g.add(chest);
  const shoulders = cast(new THREE.Mesh(new THREE.CapsuleGeometry(0.062 * k, 0.30 * k, 6, 12), mat())); shoulders.rotation.z = Math.PI / 2; shoulders.position.y = sh - 0.02 * k; g.add(shoulders);
  if (o.skirt) { const sk = cast(new THREE.Mesh(new THREE.CylinderGeometry(0.16 * k, 0.26 * k, 0.48 * k, 20), mat())); sk.scale.z = 0.75; sk.position.y = hip - 0.20 * k; g.add(sk); }
  if (o.coat) { const ct = cast(new THREE.Mesh(new THREE.CylinderGeometry(0.175 * k, 0.21 * k, 0.42 * k, 20), mat())); ct.scale.z = 0.7; ct.position.y = hip - 0.02 * k; g.add(ct); }
  // 腕（ひじを少し曲げる。手は丸くしない）
  const arms = [-1, 1].map((sx) => {
    const p = new THREE.Group(); p.position.set(sx * 0.205 * k, sh - 0.03 * k, 0); p.rotation.z = sx * 0.06;
    const up = cast(new THREE.Mesh(new THREE.CapsuleGeometry(0.043 * k, 0.24 * k, 6, 10), mat())); up.position.y = -0.15 * k; p.add(up);
    const el = new THREE.Group(); el.position.y = -0.30 * k; el.rotation.x = -(o.bend ?? 0.32); p.add(el);
    const lo = cast(new THREE.Mesh(new THREE.CapsuleGeometry(0.036 * k, 0.26 * k, 6, 10), mat())); lo.position.y = -0.15 * k; el.add(lo);
    g.add(p); p.userData.el = el; return p; });
  const neck = cast(new THREE.Mesh(new THREE.CylinderGeometry(0.052 * k, 0.062 * k, 0.10 * k, 12), mat())); neck.position.y = 1.465 * k; g.add(neck);
  const head = new THREE.Group(); head.position.y = 1.60 * k; g.add(head);
  const skull = cast(new THREE.Mesh(new THREE.SphereGeometry(0.098 * k, 20, 16), mat())); skull.scale.set(0.92, 1.14, 1.02); head.add(skull);
  const hair = cast(new THREE.Mesh(new THREE.SphereGeometry(0.106 * k, 20, 16), mat())); hair.position.set(0, 0.022 * k, 0.018 * k); hair.scale.set(0.98, 1.08, 1.05); head.add(hair);
  if (o.long) { const tail = cast(new THREE.Mesh(new THREE.CapsuleGeometry(0.085 * k, 0.16 * k, 6, 12), mat())); tail.position.set(0, -0.13 * k, 0.05 * k); tail.scale.z = 0.6; head.add(tail); }
  if (o.pony) { const tail = cast(new THREE.Mesh(new THREE.CapsuleGeometry(0.035 * k, 0.14 * k, 6, 10), mat())); tail.position.set(0, -0.04 * k, 0.13 * k); tail.rotation.x = 0.5; head.add(tail); }
  if (o.hood) { const hd = cast(new THREE.Mesh(new THREE.SphereGeometry(0.10 * k, 16, 12), mat())); hd.position.set(0, 1.44 * k, 0.10 * k); hd.scale.set(1.25, 0.8, 0.8); g.add(hd); }
  if (o.bag) { const b = cast(new THREE.Mesh(new RoundedBoxGeometry(0.27 * k, 0.37 * k, 0.14 * k, 3, 0.05 * k), mat())); b.position.set(0, 1.19 * k, 0.15 * k); g.add(b); }
  if (o.tote) { const b = cast(new THREE.Mesh(new RoundedBoxGeometry(0.06 * k, 0.30 * k, 0.32 * k, 2, 0.02 * k), mat())); b.position.set(0.02 * k, -0.20 * k, 0.02 * k); arms[1].userData.el.add(b); }
  return { g, legs, arms, head, k, o };
}

async function build() {
  await loadFonts();
  const [imWood, imLogo, imPoster, page0, rects] = await Promise.all([
    loadImg("assets/wood_src.jpg"), loadImg("assets/logo.png"), loadImg("../../assets/posters/claude-design/RoomRadar_poster_A4_2480x3508.png"),
    loadImg("assets/page0.png"), fetch("assets/rects.json").then((r) => r.json())]);

  const canvas = document.getElementById("gl");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, preserveDrawingBuffer: true, powerPreference: "high-performance" });
  const PR = (window.devicePixelRatio || 1) * Number(Q.get("rs") || 1);
  renderer.setPixelRatio(PR); renderer.setSize(W, H, false);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap; renderer.shadowMap.autoUpdate = false;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0;
  const rw = Math.round(W * PR), rh = Math.round(H * PR);
  const scene = new THREE.Scene(); scene.background = new THREE.Color(0x090706);
  const camera = new THREE.PerspectiveCamera(30, W / H, 0.03, 40);

  { // 映り込み用の環境（暗い廊下に、後ろの窓が明るい）
    const env = new THREE.Scene();
    env.add(new THREE.Mesh(new THREE.BoxGeometry(10, 4, 10), new THREE.MeshBasicMaterial({ color: 0x1a120c, side: THREE.BackSide })));
    const wm = new THREE.MeshBasicMaterial({ color: new THREE.Color(12, 7, 3.2) });
    for (const x of [-2.5, 0.5, 3.0]) { const m = new THREE.Mesh(new THREE.PlaneGeometry(1.4, 1.5), wm); m.position.set(x, 1.6, 4.9); m.rotation.y = Math.PI; env.add(m); }
    const pm = new THREE.PMREMGenerator(renderer); scene.environment = pm.fromScene(env, 0.03, 0.1, 30).texture; scene.environmentIntensity = 0.35;
  }

  // 光：後ろの窓からの夕方の光（壁に斜めに当たる）と、教室の明かり（開いたドアから廊下にこぼれる）
  const sun = new THREE.SpotLight(0xffc79a, 74, 0, 0.50, 0.45, 2);
  sun.position.set(3.4, 1.82, 4.9); sun.target.position.set(-0.15, 1.30, 0); scene.add(sun, sun.target);
  sun.castShadow = true; sun.shadow.mapSize.set(1024, 1024);   // 粗めにして影の縁をやわらかく sun.shadow.camera.near = 1.5; sun.shadow.camera.far = 12; sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.01;
  sun.map = cookieTex();
  const roomLight = new THREE.SpotLight(0xffc98f, 95, 0, 0.62, 0.7, 2);
  roomLight.position.set(DOOR.cx, 2.25, -1.7); roomLight.target.position.set(DOOR.cx, 0, 2.2); scene.add(roomLight, roomLight.target);
  roomLight.castShadow = true; roomLight.shadow.mapSize.set(2048, 2048); roomLight.shadow.camera.near = 0.5; roomLight.shadow.camera.far = 10; roomLight.shadow.bias = -0.0004; roomLight.shadow.normalBias = 0.01;
  scene.add(new THREE.HemisphereLight(0xb4a898, 0x372417, 0.30));
  // ドアが閉まったあと、廊下の明かりがドアの面を照らす（開いている間は教室の明かりが主役。人は逆光の影になる）
  const doorLight = new THREE.SpotLight(0xffd4ac, 0, 0, 0.5, 0.85, 2); doorLight.position.set(1.45, 2.55, 2.0); doorLight.target.position.set(DOOR.cx, 1.15, 0); scene.add(doorLight, doorLight.target);
  const tealLight = new THREE.PointLight(TEAL, 0, 2.2, 2); scene.add(tealLight);
  const phoneLight = new THREE.PointLight(0x9fd6ee, 0, 0.6, 2); scene.add(phoneLight);

  // 壁・床・天井
  const wallMat = new THREE.MeshStandardMaterial({ color: 0xcfc6b6, roughness: 0.93, bumpMap: noiseTex(256, 8, 14, 5), bumpScale: 0.35 });
  const box = (w, h, d, mat, x, y, z, cast = false) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, y, z); m.receiveShadow = true; m.castShadow = cast; scene.add(m); return m; };
  const WT = 0.14, WH = 2.75;
  box(DOOR.x0 + 6, WH, WT, wallMat, (DOOR.x0 - 6) / 2, WH / 2, -WT / 2, true);
  box(6 - (DOOR.x0 + DOOR.w), WH, WT, wallMat, (DOOR.x0 + DOOR.w + 6) / 2, WH / 2, -WT / 2, true);
  box(DOOR.w, WH - DOOR.h, WT, wallMat, DOOR.cx, (WH + DOOR.h) / 2, -WT / 2, true);
  const baseMat = new THREE.MeshStandardMaterial({ color: 0x3a3028, roughness: 0.7 });
  box(DOOR.x0 + 6, 0.09, 0.012, baseMat, (DOOR.x0 - 6) / 2, 0.045, 0.006); box(6 - (DOOR.x0 + DOOR.w), 0.09, 0.012, baseMat, (DOOR.x0 + DOOR.w + 6) / 2, 0.045, 0.006);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(14, 14), new THREE.MeshStandardMaterial({ color: 0x7a7064, roughness: 0.38, metalness: 0.0, bumpMap: noiseTex(256, 4, 30, 30), bumpScale: 0.12 }));
  floor.rotation.x = -Math.PI / 2; floor.position.set(0, 0, 0); floor.receiveShadow = true; scene.add(floor);
  box(14, 0.05, 14, new THREE.MeshBasicMaterial({ color: 0x110d0a }), 0, WH + 0.025, 0);
  box(0.1, WH, 8, new THREE.MeshBasicMaterial({ color: 0x1a130e }), -6, WH / 2, 3); box(0.1, WH, 8, new THREE.MeshBasicMaterial({ color: 0x1a130e }), 6, WH / 2, 3);
  // ドアの枠
  const frameMat = new THREE.MeshStandardMaterial({ color: 0x4a3a2c, roughness: 0.6 });
  box(0.06, DOOR.h + 0.06, WT + 0.03, frameMat, DOOR.x0 - 0.03, (DOOR.h + 0.06) / 2, -WT / 2 + 0.005, true); box(0.06, DOOR.h + 0.06, WT + 0.03, frameMat, DOOR.x0 + DOOR.w + 0.03, (DOOR.h + 0.06) / 2, -WT / 2 + 0.005, true);
  box(DOOR.w + 0.12, 0.06, WT + 0.03, frameMat, DOOR.cx, DOOR.h + 0.03, -WT / 2 + 0.005, true);

  // 教室の中（明るい。ぼけて見える）
  {
    const warm = (r, g, b) => new THREE.MeshBasicMaterial({ color: new THREE.Color(r, g, b) });
    box(8, WH, 0.1, warm(2.6, 1.75, 1.0), DOOR.cx, WH / 2, -6.5); box(0.1, WH, 6.5, warm(1.9, 1.25, 0.72), DOOR.cx - 3.2, WH / 2, -3.3); box(0.1, WH, 6.5, warm(1.9, 1.25, 0.72), DOOR.cx + 3.2, WH / 2, -3.3);
    box(8, 0.05, 6.5, warm(1.5, 1.05, 0.7), DOOR.cx, WH - 0.02, -3.3); box(8, 0.02, 6.4, warm(0.9, 0.62, 0.40), DOOR.cx, 0.012, -3.4);
    box(3.0, 1.05, 0.04, warm(0.26, 0.23, 0.19), DOOR.cx + 0.4, 1.45, -6.42);                       // 黒板
    const dk = warm(0.20, 0.13, 0.08);
    for (let r = 0; r < 3; r++) for (let c = -1; c <= 1; c++) { box(1.0, 0.03, 0.45, dk, DOOR.cx + c * 1.5 + 0.3, 0.72, -2.2 - r * 1.3); box(0.9, 0.68, 0.03, warm(0.14, 0.09, 0.06), DOOR.cx + c * 1.5 + 0.3, 0.36, -2.4 - r * 1.3); }
  }

  // ドア（蝶番は左。教室の側へ開く）
  const woodMap = new THREE.Texture(imWood); woodMap.colorSpace = THREE.SRGBColorSpace; woodMap.wrapS = woodMap.wrapT = THREE.MirroredRepeatWrapping; woodMap.center.set(0.5, 0.5); woodMap.rotation = Math.PI / 2; woodMap.repeat.set(1.6, 0.8); woodMap.anisotropy = 2; woodMap.needsUpdate = true;
  const doorG = new THREE.Group(); doorG.position.set(DOOR.x0, 0, -0.03); scene.add(doorG);
  const leaf = new THREE.Mesh(new THREE.BoxGeometry(DOOR.w - 0.012, DOOR.h - 0.012, 0.042), new THREE.MeshStandardMaterial({ map: woodMap, color: 0xa98463, roughness: 0.55 }));
  leaf.position.set(DOOR.w / 2, DOOR.h / 2, 0); leaf.castShadow = true; leaf.receiveShadow = true; doorG.add(leaf);
  const paneMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(2.6, 1.8, 1.0) });
  for (const z of [0.0215, -0.0215]) { const pn = new THREE.Mesh(new THREE.PlaneGeometry(0.11, 0.82), paneMat); pn.position.set(0.70, 1.45, z); if (z < 0) pn.rotation.y = Math.PI; doorG.add(pn);
    const fr = new THREE.Mesh(new THREE.PlaneGeometry(0.135, 0.845), new THREE.MeshStandardMaterial({ color: 0x2c231b, roughness: 0.6 })); fr.position.set(0.70, 1.45, z * 0.995); if (z < 0) fr.rotation.y = Math.PI; doorG.add(fr); }
  const metal = new THREE.MeshStandardMaterial({ color: 0xb9b3a9, metalness: 0.95, roughness: 0.3 });
  { const rose = new THREE.Mesh(new THREE.CylinderGeometry(0.026, 0.026, 0.012, 24), metal); rose.rotation.x = Math.PI / 2; rose.position.set(0.82, 1.0, 0.027); doorG.add(rose);
    const lever = new THREE.Mesh(new RoundedBoxGeometry(0.13, 0.02, 0.018, 3, 0.008), metal); lever.position.set(0.77, 1.0, 0.052); lever.castShadow = true; doorG.add(lever);
    const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.009, 0.009, 0.035, 12), metal); stem.rotation.x = Math.PI / 2; stem.position.set(0.82, 1.0, 0.043); doorG.add(stem); }
  // ドアのロゴ（閉まったあとに浮かぶ）
  const glow = glowTex();
  const lc = mkCanvas(imLogo.width, imLogo.height), lx = lc.getContext("2d"); lx.drawImage(imLogo, 0, 0);
  { const id = lx.getImageData(0, 0, lc.width, lc.height), d = id.data; for (let i = 0; i < d.length; i += 4) if (d[i + 3] < 10) { d[i] = 116; d[i + 1] = 166; d[i + 2] = 162; d[i + 3] = 0; } lx.putImageData(id, 0, 0); }
  const LOGO = { w: 0.50, x: DOOR.w / 2 - 0.03, y: 1.37 }; LOGO.h = LOGO.w * imLogo.height / imLogo.width;
  const logoMat = new THREE.MeshBasicMaterial({ map: texFrom(lc), color: new THREE.Color(1.3, 1.3, 1.3), transparent: true, opacity: 0, depthWrite: false });
  const logo = new THREE.Mesh(new THREE.PlaneGeometry(LOGO.w, LOGO.h), logoMat); logo.position.set(LOGO.x, LOGO.y, 0.0225); logo.visible = false; doorG.add(logo);
  const logoGlow = new THREE.Mesh(new THREE.PlaneGeometry(LOGO.w * 2.1, LOGO.h * 2.6), new THREE.MeshBasicMaterial({ map: glow, color: TEAL, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
  logoGlow.position.set(LOGO.x, LOGO.y, 0.0220); logoGlow.visible = false; doorG.add(logoGlow);
  const radarW = V3(DOOR.x0 + LOGO.x - LOGO.w / 2 + 0.4156 * LOGO.w, LOGO.y + LOGO.h / 2 - 0.4297 * LOGO.h, 0);
  // 教室の札
  const plate = new THREE.Mesh(new THREE.BoxGeometry(0.17, 0.085, 0.012), [0, 1, 2, 3, 4, 5].map((i) => new THREE.MeshStandardMaterial(i === 4 ? { map: plateTex("705"), roughness: 0.6 } : { color: 0xd8d2c6, roughness: 0.6 })));
  plate.position.set(DOOR.x0 + DOOR.w + 0.17, 1.62, 0.006); plate.castShadow = true; scene.add(plate);

  // 掲示板とポスター
  box(1.22, 0.86, 0.018, new THREE.MeshStandardMaterial({ map: corkTex(), roughness: 0.95 }), -1.0, 1.47, 0.009, true);
  const alu = new THREE.MeshStandardMaterial({ color: 0xa9a59c, metalness: 0.85, roughness: 0.45 });
  box(1.26, 0.025, 0.03, alu, -1.0, 1.47 + 0.4425, 0.015, true); box(1.26, 0.025, 0.03, alu, -1.0, 1.47 - 0.4425, 0.015, true); box(0.025, 0.86, 0.03, alu, -1.0 - 0.6175, 1.47, 0.015, true); box(0.025, 0.86, 0.03, alu, -1.0 + 0.6175, 1.47, 0.015, true);
  const posterTex = new THREE.Texture(imPoster); posterTex.colorSpace = THREE.SRGBColorSpace; posterTex.anisotropy = 4; posterTex.needsUpdate = true;
  const sheetMat = (map) => new THREE.MeshStandardMaterial({ map, roughness: 0.9 });
  const poster = new THREE.Mesh(new THREE.PlaneGeometry(POSTER.w, POSTER.h), sheetMat(posterTex)); poster.position.set(POSTER.x, POSTER.y, 0.0205); poster.rotation.z = 0.006; poster.receiveShadow = true; scene.add(poster);
  const m1 = new THREE.Mesh(new THREE.PlaneGeometry(0.21, 0.297), sheetMat(memoTex(3, "#efe9dc"))); m1.position.set(-0.70, 1.56, 0.0202); m1.rotation.z = -0.02; m1.receiveShadow = true; scene.add(m1);
  const m2 = new THREE.Mesh(new THREE.PlaneGeometry(0.21, 0.297), sheetMat(memoTex(9, "#e6e3da"))); m2.position.set(-1.40, 1.50, 0.0202); m2.rotation.z = 0.015; m2.receiveShadow = true; scene.add(m2);
  const pinM = new THREE.MeshStandardMaterial({ color: 0xd8d2c6, roughness: 0.4, metalness: 0.3 });
  for (const [x, y] of [[POSTER.x - 0.13, POSTER.y + 0.195], [POSTER.x + 0.13, POSTER.y + 0.196], [POSTER.x - 0.13, POSTER.y - 0.195], [POSTER.x + 0.13, POSTER.y - 0.194], [-0.70, 1.695], [-1.40, 1.635]]) {
    const pn = new THREE.Mesh(new THREE.SphereGeometry(0.0055, 12, 10), pinM); pn.position.set(x, y, 0.026); pn.castShadow = true; scene.add(pn); }

  // レーダーの輪（壁の面に沿って広がる）
  const RINGS = [{ t0: T.lock, c: [QR.x, QR.y], v: 0.55, s: 1.1 }, { t0: T.lock + 0.55, c: [QR.x, QR.y], v: 0.55, s: 0.7 }, { t0: T.ring, c: [radarW.x, radarW.y], v: 0.42, s: 1.15 }, { t0: T.ring + 1.0, c: [radarW.x, radarW.y], v: 0.42, s: 0.6 }];
  const ringU = { uRings: { value: Array.from({ length: 4 }, () => new THREE.Vector4(0, 0, -1, 0)) }, uColor: { value: TEAL.clone() } };
  const ringMesh = new THREE.Mesh(new THREE.PlaneGeometry(10, 3), new THREE.ShaderMaterial({
    uniforms: ringU, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: `varying vec2 vP; void main() { vec4 w = modelMatrix * vec4(position, 1.0); vP = w.xy; gl_Position = projectionMatrix * viewMatrix * w; }`,
    fragmentShader: `uniform vec4 uRings[4]; uniform vec3 uColor; varying vec2 vP;
      void main() { float I = 0.0;
        for (int i = 0; i < 4; i++) { vec4 r = uRings[i]; if (r.z < 0.0 || r.w < 0.002) continue; float x = distance(vP, r.xy) - r.z;
          float a = x / 0.006, b = x / 0.035;
          float line = abs(a) < 4.0 ? exp(-a * a) : 0.0, halo = abs(b) < 4.0 ? exp(-b * b) * 0.22 : 0.0, trail = (x < 0.0 && x > -0.6) ? exp(x / 0.14) * 0.03 : 0.0;
          I += r.w * (line * 1.6 + halo + trail); }
        if (I < 0.0015) discard;
        gl_FragColor = vec4(uColor * I, 1.0); }` }));
  ringMesh.position.set(0, 1.5, 0.034); scene.add(ringMesh);

  // スマホ（机の版と同じ形。ロゴなどの印は付けない）
  const PW = 0.0706, PHT = 0.1486, PD = 0.0083, PRAD = 0.0125, BZ = 0.0018;
  const SW = PW - 2 * BZ, SH = SW * 844 / 390;
  const rrShape = (w, h, r) => { const sh = new THREE.Shape(), x0 = -w / 2, y0 = -h / 2;
    sh.moveTo(x0 + r, y0); sh.lineTo(x0 + w - r, y0); sh.absarc(x0 + w - r, y0 + r, r, -Math.PI / 2, 0, false);
    sh.lineTo(x0 + w, y0 + h - r); sh.absarc(x0 + w - r, y0 + h - r, r, 0, Math.PI / 2, false);
    sh.lineTo(x0 + r, y0 + h); sh.absarc(x0 + r, y0 + h - r, r, Math.PI / 2, Math.PI, false);
    sh.lineTo(x0, y0 + r); sh.absarc(x0 + r, y0 + r, r, Math.PI, Math.PI * 1.5, false); return sh; };
  const phone = new THREE.Group(); scene.add(phone);                      // 原点はスマホのまん中
  const titan = new THREE.MeshStandardMaterial({ color: 0x969088, metalness: 1.0, roughness: 0.34 });
  const bev = 0.0007, frameG = new THREE.ExtrudeGeometry(rrShape(PW - 2 * bev, PHT - 2 * bev, PRAD - bev), { depth: PD - 2 * bev, bevelEnabled: true, bevelThickness: bev, bevelSize: bev, bevelSegments: 3, curveSegments: 20 });
  frameG.translate(0, 0, -PD / 2 + bev);
  phone.add(new THREE.Mesh(frameG, titan));
  const front = new THREE.Mesh(new THREE.ShapeGeometry(rrShape(PW - 0.0015, PHT - 0.0015, PRAD - 0.00075), 20), new THREE.MeshStandardMaterial({ color: 0x040405, roughness: 0.22 })); front.position.z = PD / 2 + 0.00004; phone.add(front);
  for (const [sx, y, len] of [[1, 0.0237, 0.0155], [-1, 0.0472, 0.0058], [-1, 0.0342, 0.0098], [-1, 0.0212, 0.0098]]) { const bt = new THREE.Mesh(new RoundedBoxGeometry(0.0012, len, 0.0030, 2, 0.0005), titan); bt.position.set(sx * (PW / 2 + 0.00025), y, 0); phone.add(bt); }
  const scrC = mkCanvas(390 * 5, 844 * 5), scrX = scrC.getContext("2d"), scrTex = texFrom(scrC); scrTex.generateMipmaps = true;
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(SW, SH), new THREE.MeshBasicMaterial({ map: scrTex, color: new THREE.Color(1.12, 1.12, 1.12), alphaTest: 0.5 })); screen.position.z = PD / 2 + 0.0001; phone.add(screen);   // 四隅は透明（本体の丸い角からはみ出さない）
  const scrPoint = (cx, cy) => V3((cx / 390 - 0.5) * SW, (0.5 - cy / 844) * SH, PD / 2 + 0.0002);

  // 友達3人（影だけ）
  const people = [
    makePerson({ h: 1.75, bag: true, hood: true, wide: true }),
    makePerson({ h: 1.60, long: true, tote: true, skirt: true, bend: 0.5 }),
    makePerson({ h: 1.67, pony: true, bag: true, coat: true }),
  ];
  const WALKS = [   // 廊下の奥（カメラの後ろ）からドアへ歩く。影は壁の左から右へ流れ、ドアの明かりに入っていく
    { from: [0.86, 3.60], t0: T.walk - 0.20, v: 0.95, ph: 0.0, inX: 0.6 },
    { from: [1.22, 3.75], t0: T.walk + 0.30, v: 0.96, ph: 2.1, inX: 1.5 },
    { from: [1.02, 3.90], t0: T.walk + 0.82, v: 0.97, ph: 4.0, inX: 1.0 },
  ];
  // 姿は描かない（色も奥行きも書かない）。夕方の光と教室の明かりで、壁と床に影だけが落ちる
  people.forEach((p) => p.g.traverse((o) => { if (o.isMesh) { o.material.colorWrite = false; o.material.depthWrite = false; o.receiveShadow = false; } }));
  people.forEach((p, i) => { scene.add(p.g); const w = WALKS[i]; w.pts = [V3(w.from[0], 0, w.from[1]), V3(DOOR.cx + (i - 1) * 0.06, 0, 0.55), V3(DOOR.cx, 0, -0.45), V3(w.inX, 0, -2.6)];
    w.len = [0]; for (let k = 1; k < w.pts.length; k++) w.len.push(w.len[k - 1] + w.pts[k].distanceTo(w.pts[k - 1])); });
  function walkPos(w, d) {      // 道のり d の位置と向き
    const L = w.len; d = Math.min(d, L[L.length - 1] - 0.001); let k = 1; while (k < L.length - 1 && d > L[k]) k++;
    const u = (d - L[k - 1]) / (L[k] - L[k - 1]), a = w.pts[k - 1], b = w.pts[k];
    const pos = a.clone().lerp(b, u), dir = b.clone().sub(a).normalize();
    // 角で向きをなめらかに
    if (k < L.length - 1 && L[k] - d < 0.35) { const nd = w.pts[k + 1].clone().sub(b).normalize(); dir.lerp(nd, 0.5 * (1 - (L[k] - d) / 0.35)).normalize(); }
    if (k > 1 && d - L[k - 1] < 0.35) { const pd = a.clone().sub(w.pts[k - 2]).normalize(); dir.lerp(pd, 0.5 * (1 - (d - L[k - 1]) / 0.35)).normalize(); }
    return { pos, dir };
  }

  // ───────── スマホの画面（カメラで QR を読み取る → アプリの一覧 → 教室を見つける） ─────────
  const S6 = 6, VW = 390, VH = 844, SB = 47;
  const SCROLL0 = rects.chips[1] - 96, SCROLL1 = rects.chips[1] - 12;
  const vy = (pageY, sc) => pageY - sc + SB;
  const CAM = { cx: 0.275, cy: 0.655, w: 0.50 };                         // カメラに映すポスターの範囲（ポスターの幅に対する割合）
  const camSrcW = CAM.w * imPoster.width, camSrcH = camSrcW * VH / VW;
  const qrOnScreen = { x: (0.146 - (CAM.cx - CAM.w / 2)) / CAM.w * VW, y: VH / 2 + (0.710 - CAM.cy) * imPoster.height / camSrcH * VH, s: 0.137 / CAM.w * VW };
  let lastKey = "";
  function screenState(t) {
    const st = { on: ss(seg(t, T.phoneIn + 0.2, T.phoneIn + 0.6)) };
    st.app = ss(seg(t, T.toApp + 0.25, T.toApp + 0.65)); st.dark = ss(seg(t, T.toApp, T.toApp + 0.25)) * (1 - st.app);
    st.lock = eo(seg(t, T.lock, T.lock + 0.35)); st.chip = eo(seg(t, T.chip, T.chip + 0.3));
    const drift = 1 - ss(seg(t, T.lock - 0.5, T.lock));
    st.dx = Math.sin(t * 2.3) * 7 * drift; st.dy = Math.cos(t * 1.7) * 9 * drift;
    st.scroll = lerp(SCROLL0, SCROLL1, sss(seg(t, T.scroll, T.scroll + 1.3)));
    st.taps = []; const p = seg(t, T.tapChip, T.tapChip + 0.45); if (p > 0 && p < 1) st.taps.push([qrOnScreen.x + 46, qrOnScreen.y + qrOnScreen.s / 2 + 36, p]);
    st.hi = [0, 0.95].map((d) => { const q = seg(t, T.hi + d, T.hi + d + 0.9); return q > 0 && q < 1 ? q : 0; });
    st.sel = ss(seg(t, T.hi, T.hi + 0.3));
    return st;
  }
  function drawScreen(st) {
    const key = JSON.stringify(st, (k, v) => typeof v === "number" ? Math.round(v * 500) / 500 : v);
    if (key === lastKey) return; lastKey = key;
    const c = scrX; c.save(); c.setTransform(5, 0, 0, 5, 0, 0);
    c.clearRect(0, 0, VW, VH); rr(c, 0, 0, VW, VH, 60); c.clip();          // 画面の形（角の丸い四角）の外は透明のまま
    c.fillStyle = "#000"; c.fillRect(0, 0, VW, VH);
    if (st.on > 0.001) {
      if (st.app < 1) {                                               // カメラの画面
        c.fillStyle = "#8a6843"; c.fillRect(0, 0, VW, VH);
        const sx = CAM.cx * imPoster.width - camSrcW / 2 + st.dx * 3, sy = CAM.cy * imPoster.height - camSrcH / 2 + st.dy * 3;
        c.drawImage(imPoster, sx, sy, camSrcW, camSrcH, 0, 0, VW, VH);
        c.fillStyle = "rgba(0,0,0,0.42)"; c.fillRect(0, 0, VW, 96); c.fillRect(0, VH - 178, VW, 178);
        c.strokeStyle = "rgba(255,255,255,0.92)"; c.lineWidth = 4; c.beginPath(); c.arc(VW / 2, VH - 96, 31, 0, 7); c.stroke();
        c.fillStyle = "rgba(255,255,255,0.95)"; c.beginPath(); c.arc(VW / 2, VH - 96, 25, 0, 7); c.fill();
        c.font = "700 13px RRSans"; c.textAlign = "center"; c.textBaseline = "middle"; c.fillStyle = "#ffd60a"; c.fillText("写真", VW / 2, VH - 152);
        c.fillStyle = "rgba(255,255,255,0.75)"; c.fillText("ビデオ", VW / 2 - 62, VH - 152); c.fillText("ポートレート", VW / 2 + 78, VH - 152);
        c.fillStyle = "rgba(0,0,0,0.45)"; rr(c, VW / 2 - 21, VH - 226, 42, 30, 15); c.fill(); c.fillStyle = "#ffd60a"; c.fillText("1×", VW / 2, VH - 211);
        if (st.lock > 0.01) {                                         // QR を見つけた黄色い角
          const g = qrOnScreen.s / 2 + 8 + (1 - st.lock) * 26, x0 = qrOnScreen.x - st.dx * 0.6, y0 = qrOnScreen.y - st.dy * 0.6, L = 20;
          c.strokeStyle = `rgba(255,214,10,${st.lock})`; c.lineWidth = 4; c.lineCap = "round"; c.lineJoin = "round";
          for (const [ax, ay] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) { c.beginPath(); c.moveTo(x0 + ax * g, y0 + ay * (g - L)); c.lineTo(x0 + ax * g, y0 + ay * g); c.lineTo(x0 + ax * (g - L), y0 + ay * g); c.stroke(); }
        }
        if (st.chip > 0.01) {                                         // 「開く」の黄色い札
          const w = 214, h = 36, x0 = qrOnScreen.x - 58, y0 = qrOnScreen.y + qrOnScreen.s / 2 + 18 + (1 - st.chip) * 8;
          c.globalAlpha = st.chip; c.fillStyle = "#ffd60a"; rr(c, x0, y0, w, h, 18); c.fill();
          c.fillStyle = "#1c1a12"; c.beginPath(); c.arc(x0 + 20, y0 + h / 2, 9, 0, 7); c.fill(); c.fillStyle = "#ffd60a"; c.beginPath(); c.moveTo(x0 + 23.5, y0 + h / 2 - 3.5); c.lineTo(x0 + 21.2, y0 + h / 2 + 1.2); c.lineTo(x0 + 16.5, y0 + h / 2 + 3.5); c.lineTo(x0 + 18.8, y0 + h / 2 - 1.2); c.closePath(); c.fill();
          c.fillStyle = "#1c1a12"; c.font = "700 13.5px RRSans"; c.textAlign = "left"; c.fillText("nu-roomradar.github.io", x0 + 37, y0 + h / 2 + 0.5); c.globalAlpha = 1;
        }
        if (st.dark > 0) { c.fillStyle = `rgba(10,10,15,${st.dark})`; c.fillRect(0, 0, VW, VH); }
      }
      if (st.app > 0.001) {                                           // アプリ（いま空いている教室の一覧）
        c.globalAlpha = st.app; c.fillStyle = "#0a0a0f"; c.fillRect(0, 0, VW, VH);
        c.drawImage(page0, 0, st.scroll * S6, VW * S6, (VH - SB) * S6, 0, SB, VW, VH - SB);
        const r = rects.card, y = vy(r[1], st.scroll);
        if (st.sel > 0) { c.fillStyle = `rgba(95,230,210,${0.13 * st.sel})`; rr(c, r[0], y, r[2], r[3], 14); c.fill(); c.strokeStyle = `rgba(95,230,210,${0.9 * st.sel})`; c.lineWidth = 2.2; c.stroke(); }
        for (const p of st.hi) { if (!p) continue; const g = 3 + p * 14; c.strokeStyle = `rgba(95,230,210,${(1 - p) * 0.95})`; c.lineWidth = 3 - p * 1.5; rr(c, r[0] - g, y - g, r[2] + g * 2, r[3] + g * 2, 14 + g); c.stroke(); }
        c.fillStyle = "#0a0a0f"; c.fillRect(0, 0, VW, SB); c.globalAlpha = 1;
      }
      // 上の帯（時刻・電波・電池）と、下の横棒
      c.fillStyle = "#000"; rr(c, VW / 2 - 62, 11, 124, 36, 18); c.fill();
      c.fillStyle = "rgba(255,255,255,0.96)"; c.font = "700 17px RRSans"; c.textAlign = "left"; c.textBaseline = "middle"; c.fillText("14:40", 40, 30);
      for (let i = 0; i < 4; i++) { rr(c, 286 + i * 5.2, 35 - (4 + i * 2.4), 3.4, 4 + i * 2.4, 1); c.fill(); }
      c.lineWidth = 1.2; c.strokeStyle = "rgba(255,255,255,0.6)"; rr(c, 326, 23.5, 25, 12.5, 3.6); c.stroke(); rr(c, 328, 25.5, 17, 8.5, 2); c.fill(); rr(c, 352.3, 27.6, 1.8, 4.4, 1); c.fill();
      c.lineCap = "round"; c.strokeStyle = "rgba(255,255,255,0.96)"; c.lineWidth = 1.9;
      for (let i = 0; i < 3; i++) { c.beginPath(); c.arc(314, 35.5, 2.6 + i * 3.2, -Math.PI * 0.76, -Math.PI * 0.24); c.stroke(); }
      c.fillStyle = "rgba(255,255,255,0.75)"; rr(c, VW / 2 - 70, VH - 14, 140, 5, 2.5); c.fill();
      for (const [x, y, p] of st.taps) { c.fillStyle = `rgba(255,255,255,${(1 - p) * 0.4})`; c.beginPath(); c.arc(x, y, 12 + p * 24, 0, 7); c.fill(); c.strokeStyle = `rgba(255,255,255,${(1 - p) * 0.8})`; c.lineWidth = 1.6; c.beginPath(); c.arc(x, y, 12 + p * 24, 0, 7); c.stroke(); }
      if (st.on < 1) { c.fillStyle = `rgba(0,0,0,${1 - st.on})`; c.fillRect(0, 0, VW, VH); }
    }
    c.restore(); scrTex.needsUpdate = true;
  }

  // ───────── カメラ ─────────
  const posterC = V3(POSTER.x, POSTER.y, 0.02), doorC = V3(DOOR.cx, 1.05, 0), logoC = V3(DOOR.x0 + LOGO.x, LOGO.y, 0);
  const PH_POS = V3(-1.012, 1.412, 0.700), PH_ROT = { x: -0.10, y: 0.05 };          // スマホを構える位置（カメラの少し下・ポスターの手前）
  phone.position.copy(PH_POS); phone.rotation.set(PH_ROT.x, PH_ROT.y, 0); phone.updateMatrixWorld(true);
  const pw = (cx, cy) => phone.localToWorld(scrPoint(cx, cy));
  const nrm = V3(0, 0, 1).applyQuaternion(phone.quaternion);
  const scrMid = pw(195, 422), rowsMid = pw(195, vy(rects.card[1], SCROLL1) + 70);
  const off = (p, d, dx = 0, dy = 0) => p.clone().addScaledVector(nrm, d).add(V3(dx, dy, 0));
  const KEYS = [
    { t: 0.0, p: V3(-0.30, 1.52, 2.95), l: V3(-0.78, 1.45, 0), f: posterC, k: 14 },
    { t: 3.3, p: V3(-0.985, 1.475, 1.14), l: V3(-1.045, 1.452, 0), f: posterC, k: 14 },
    { t: 4.5, p: V3(-0.990, 1.468, 1.08), l: V3(-1.040, 1.436, 0), f: scrMid, k: 22, e: "lin" },
    { t: 6.6, p: V3(-0.992, 1.462, 1.06), l: V3(-1.036, 1.430, 0), f: scrMid, k: 22, e: "lin" },
    { t: 8.0, p: off(scrMid, 0.275, 0.004, 0.004), l: scrMid, f: scrMid, k: 24 },
    { t: 9.9, p: off(rowsMid, 0.215, 0.004, 0.004), l: rowsMid, f: rowsMid, k: 24 },
    { t: 12.8, p: off(rowsMid, 0.205, 0.003, 0.004), l: rowsMid, f: rowsMid, k: 24, e: "lin" },
    { t: 14.3, p: V3(-0.30, 1.42, 4.10), l: V3(-0.38, 1.30, 0), f: V3(-0.35, 1.3, 0), k: 9 },
    { t: 16.5, p: V3(0.42, 1.34, 4.60), l: V3(0.64, 1.14, 0), f: doorC, k: 11 },
    { t: 18.6, p: V3(0.58, 1.33, 4.50), l: V3(0.80, 1.13, 0), f: doorC, k: 11, e: "lin" },
    { t: 20.9, p: V3(0.93, 1.36, 3.62), l: V3(1.0, 1.21, 0), f: logoC, k: 13 },
    { t: 27.0, p: V3(0.95, 1.37, 3.42), l: V3(1.0, 1.21, 0), f: logoC, k: 13, e: "lin" },
  ];
  const camState = { p: V3(), l: V3(), f: V3(), k: 20 };
  function evalCamera(t) {
    let i = 0; while (i < KEYS.length - 2 && t >= KEYS[i + 1].t) i++;
    const a = KEYS[i], b = KEYS[i + 1]; let u = seg(t, a.t, b.t); if (b.e !== "lin") u = sss(u);
    camState.p.lerpVectors(a.p, b.p, u); camState.l.lerpVectors(a.l, b.l, u); camState.f.lerpVectors(a.f, b.f, u); camState.k = lerp(a.k, b.k, u);
  }

  // ───────── 後処理 ─────────
  const depthTex = new THREE.DepthTexture(rw, rh);
  const rtScene = new THREE.WebGLRenderTarget(rw, rh, { type: THREE.HalfFloatType, samples: 4, depthTexture: depthTex });
  const composer = new EffectComposer(renderer);
  const dof = new DofPass(rtScene, rw, rh); composer.addPass(dof);
  composer.addPass(new UnrealBloomPass(new THREE.Vector2(rw, rh), 0.34, 0.7, 1.0));
  composer.addPass(new OutputPass());
  const grade = new ShaderPass(GradeShader); composer.addPass(grade);

  const caps = { capA: [T.capAIn, T.capAOut], capB: [T.capBIn, T.capBOut], word: [T.wordIn, 99], notice: [T.noticeIn, 99] };
  const capEl = Object.fromEntries(Object.keys(caps).map((k) => [k, document.getElementById(k)]));

  function update(t) {
    // 輪
    let tl = 0, tx = 0, ty = 0;
    ringU.uRings.value.forEach((u, i) => {
      const r = RINGS[i], age = t - r.t0; if (age < 0 || age * r.v > 3.2) { u.set(0, 0, -1, 0); return; }
      const rad = age * r.v, s = r.s * ss(seg(age, 0, 0.25)) * (1 - ss(seg(rad, 1.0, 3.0)));
      u.set(r.c[0], r.c[1], rad, s);
      const w = s * (1 - ss(seg(rad, 0, 1.2))); if (w > tl) { tl = w; tx = r.c[0]; ty = r.c[1]; }
    });
    tealLight.position.set(tx, ty, 0.25); tealLight.intensity = tl * 0.10;

    // スマホ：下から構える → 下ろす
    const inn = eo(seg(t, T.phoneIn, T.phoneInEnd)), out = sss(seg(t, T.phoneOut, T.phoneOut + 0.8));
    phone.position.set(PH_POS.x - 0.03 * out, PH_POS.y - 0.30 * (1 - inn) - 0.34 * out, PH_POS.z + 0.02 * (1 - inn) + 0.05 * out);
    phone.rotation.set(PH_ROT.x - 0.5 * (1 - inn) - 0.6 * out, PH_ROT.y + 0.15 * (1 - inn), 0.05 * (1 - inn) - 0.1 * out);
    phone.visible = t > T.phoneIn - 0.05 && out < 0.999;
    const st = screenState(t); drawScreen(st);
    phone.updateMatrixWorld(true);
    phoneLight.position.copy(phone.localToWorld(scrPoint(195, 420))).addScaledVector(V3(0, 0, 1).applyQuaternion(phone.quaternion), 0.06); phoneLight.intensity = phone.visible ? st.on * 0.03 : 0;

    // 友達が歩いて教室へ
    people.forEach((p, i) => {
      const w = WALKS[i], tt = t - w.t0, total = w.len[w.len.length - 1];
      const d = Math.max(0, tt) * w.v, moving = tt > 0 && d < total - 0.01;
      const { pos, dir } = walkPos(w, Math.max(0.001, d));
      const ph = 2 * Math.PI * 1.9 * Math.max(0, tt) + w.ph, sw = moving ? Math.sin(ph) : 0, amp = moving ? ss(seg(tt, 0, 0.5)) : 0;
      p.g.position.set(pos.x, moving ? 0.014 * p.k * Math.abs(Math.cos(ph)) : 0, pos.z);
      p.g.rotation.y = Math.atan2(-dir.x, -dir.z) + 0.03 * Math.sin(ph * 0.5);
      p.legs[0].rotation.x = 0.44 * sw * amp; p.legs[1].rotation.x = -0.44 * sw * amp;
      p.arms[0].rotation.x = -0.34 * sw * amp; p.arms[1].rotation.x = (p.o.tote ? 0.06 : 0.34) * sw * amp;
      p.head.rotation.y = 0.22 * Math.sin(tt * 1.1 + i * 2.0) * amp;       // 話しながら歩く
      p.g.visible = t > w.t0 - 0.3;
    });

    // ドア（開いている → 閉まる）
    const cl = seg(t, T.doorClose, T.doorShut), close = cl * cl * (3 - 2 * cl) * (0.6 + 0.4 * cl);
    doorG.rotation.y = 1.66 * (1 - Math.min(1, close));
    paneMat.color.setRGB(2.6, 1.8, 1.0).multiplyScalar(0.92 + 0.08 * Math.sin(t * 2.1));
    roomLight.intensity = 95;
    doorLight.intensity = 0;

    // ロゴ
    const lg = ss(seg(t, T.logoIn, T.logoIn + 1.0));
    logoMat.opacity = lg; logo.visible = lg > 0.001; logoGlow.material.opacity = lg * 0.22 * (1 + 0.5 * Math.exp(-Math.pow((t - T.ring - 0.25) / 0.4, 2))); logoGlow.visible = logo.visible;

    // 文字
    for (const k of Object.keys(caps)) {
      const [a, b] = caps[k], al = ss(seg(t, a, a + 0.45)) * (1 - ss(seg(t, b - 0.4, b)));
      capEl[k].style.opacity = al.toFixed(4); capEl[k].style.transform = `translateY(${((1 - ss(seg(t, a, a + 0.6))) * 16).toFixed(2)}px)`;
    }

    evalCamera(t);
    camera.position.copy(camState.p); camera.lookAt(camState.l); camera.updateMatrixWorld(true);
    dof.params.focus = camState.p.distanceTo(camState.f); dof.params.k = camState.k * 1.9 * PR; dof.params.maxR = 46 * PR;
    dof.params.near = camera.near; dof.params.far = camera.far; dof.params.seed = Math.round(t * FPS) % 64;
    grade.uniforms.uSeed.value = Math.round(t * FPS);
  }
  let shadowKey = "";
  function renderAt(time) {
    const t = Math.max(0, Math.min(DURATION - 0.5 / FPS, time));
    update(t);
    const sk = doorG.rotation.y.toFixed(4) + people.map((p) => `${p.g.position.x.toFixed(3)},${p.g.position.z.toFixed(3)},${p.legs[0].rotation.x.toFixed(3)}`).join("|");
    if (sk !== shadowKey) { shadowKey = sk; renderer.shadowMap.needsUpdate = true; }
    renderer.setRenderTarget(rtScene); renderer.clear(); renderer.render(scene, camera);
    composer.render();
    renderer.getContext().finish();
    return t;
  }
  window.renderAt = renderAt; window.__rr = { scene, camera, renderer, T, KEYS, DURATION, FPS };
  window.addEventListener("hf-seek", (e) => renderAt(e.detail.time));
  renderAt(Number(Q.get("t") || window.__hfThreeTime || 0));
}

window.__hf = window.__hf || {}; window.__hf.buildReady = window.__hf.buildReady || {};
window.__hf.buildReady["rr-door-3d"] = build().then(() => { window.__ready = true; }).catch((e) => { window.__error = String(e && e.stack || e); console.error(e); throw e; });
