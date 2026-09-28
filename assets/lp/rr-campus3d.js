/*!
 * RoomRadar — 校舎3Dモデル（組み込み用） v1.0
 * 1 タワー・スコラ / 2 駿河台校舎 1号館 / 3 船橋校舎 — three.js r184（CDN から自動読込・ビルド不要）
 *
 * 使い方:
 *   <script type="module" src="rr-campus3d.js"></script>
 *   <rr-campus mode="overview" theme="night" badges style="height:520px"></rr-campus>
 *   <rr-campus mode="single" focus="tower" zone="2-5F" theme="day" style="height:480px"></rr-campus>
 *
 * 属性: mode = overview | single / theme = day | night / focus = tower | ichi | funa
 *       zone = tower: 1F 2-5F 6-18F R · ichi: 3-5F 6F stair · funa: bldg track
 *       period = 1周の秒数（0 で停止, 既定 80） / badges = 全体表示に 1・2・3 のボタンを重ねる
 * イベント: ready / pick（detail.id — badges のクリック） / anchors（detail = [{id,x,y}] 毎フレーム）
 * JS から: el.stage.setFocus('ichi','6F') など createStage() の戻り値を直接操作可
 */
// three.js r184 は CDN ではなく同じサイトから読む（学内ネットワークや CDN 障害で止まらないように）
import * as THREE from './vendor/three/three.module.min.js';

const K = 0.04, KF = 0.0085, PH = 0.34;
const V3 = THREE.Vector3;
const UB = new THREE.BoxGeometry(1, 1, 1), UE = new THREE.EdgesGeometry(UB), ICO = new THREE.IcosahedronGeometry(1, 1);

const THEMES = {
  day: { paper: 0xF2F0E8, frame: 0xFAF9F5, glass: 0xCBC7BB, dim: 0xCBC7BB, dimE: 0x141413, dimEI: 0, lit: 0xD97757, litE: 0xC15F3C, litEI: 0.32, board: 0xE8E6DC, road: 0xD6D2C6, plinth: 0x29261B, table: 0xF0EEE6, green: 0x8E9C72, damper: 0x6F6A60, metal: 0xD8D3C8, line: 0x141413, lineO: 0.2, lab: 0xE8E6DC, roofNo: 0x5E5D59, shadow: 0.17, hemi: [0xFFFCF5, 0xE8E6DC, 1.05], sun: [0xFFF4E4, 2.5], env: 0.5, exp: 1.0 },
  night: { paper: 0x393733, frame: 0x4A4843, glass: 0x1B1A19, dim: 0x5A4332, dimE: 0x6B4A30, dimEI: 0.55, lit: 0xE08A6D, litE: 0xE08A6D, litEI: 1.7, board: 0x252422, road: 0x1A1918, plinth: 0x0F0F0E, table: 0x1F1E1D, green: 0x3B4531, damper: 0x6A665E, metal: 0x8A867C, line: 0xA8A49B, lineO: 0.13, lab: 0xA8A49B, roofNo: 0xA8A49B, shadow: 0.42, hemi: [0xB9C1D1, 0x1F1E1D, 0.5], sun: [0xD6DEEE, 0.75], env: 0.24, exp: 1.05 }
};

function rng(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }
function hash(str) { let h = 7; for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0; return h; }
const dimh = (k) => hash(k) % 3 === 0;

function B(g, mat, w, h, d, x, y, z, o = {}) {
  const m = new THREE.Mesh(UB, mat);
  m.scale.set(w, h, d); m.position.set(x, y + h / 2, z);
  m.castShadow = o.cast !== false; m.receiveShadow = true; g.add(m);
  if (o.edge) { const l = new THREE.LineSegments(UE, o.edge); l.scale.copy(m.scale); l.position.copy(m.position); g.add(l); }
  return m;
}
function I(g, mat, list, cast = true) {
  const im = new THREE.InstancedMesh(UB, mat, list.length), o = new THREE.Object3D();
  list.forEach((b, i) => { o.position.set(b[3], b[4], b[5]); o.rotation.set(b[6] || 0, 0, b[7] || 0); o.scale.set(b[0], b[1], b[2]); o.updateMatrix(); im.setMatrixAt(i, o.matrix); });
  im.castShadow = cast; im.receiveShadow = true; im.computeBoundingSphere(); g.add(im); return im;
}
function trees(g, M, pts, r, y0, seed) {
  const rnd = rng(seed), tr = [], im = new THREE.InstancedMesh(ICO, M.green, pts.length), o = new THREE.Object3D();
  pts.forEach(([x, z], i) => {
    const k = r * (0.8 + rnd() * 0.45);
    tr.push([k * 0.14, k * 1.2, k * 0.14, x, y0 + k * 0.6, z]);
    o.position.set(x, y0 + k * 1.2 + k * 0.72, z); o.scale.set(k, k * 0.92, k); o.rotation.set(0, rnd() * 3, 0); o.updateMatrix(); im.setMatrixAt(i, o.matrix);
  });
  im.castShadow = im.receiveShadow = true; im.computeBoundingSphere(); g.add(im); I(g, M.frame, tr);
}
function rec() { return { root: new THREE.Group(), L: [], zones: {}, ov: [] }; }
function reg(R, m, keys, dim) { R.L.push({ m, keys: [].concat(keys), base: m.material, dim: !!dim }); return m; }
function site(R, k) { const s = new THREE.Group(); s.scale.setScalar(k); s.position.y = PH + 0.012; R.root.add(s); return s; }

function textTex(str, o = {}) {
  const w = o.w || 1024, h = o.h || 128, c = document.createElement('canvas'); c.width = w; c.height = h;
  const ctx = c.getContext('2d'), tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
  const draw = () => {
    ctx.clearRect(0, 0, w, h); ctx.fillStyle = '#FAF9F5';
    ctx.font = o.font || '500 50px ui-monospace, "SF Mono", Menlo, Consolas, monospace';
    try { ctx.letterSpacing = o.ls || '7px'; } catch (e) {}
    ctx.textBaseline = 'middle'; ctx.textAlign = o.center ? 'center' : 'left';
    ctx.fillText(str, o.center ? w / 2 : 6, h / 2 + 3); tex.needsUpdate = true;
  };
  draw(); if (document.fonts && document.fonts.ready) document.fonts.ready.then(draw);
  return tex;
}
function plinthBase(R, M, w, d, label) {
  const W = w + 0.14, D = d + 0.14;
  B(R.root, M.plinth, W, PH, D, 0, 0, 0);
  const mat = new THREE.MeshBasicMaterial({ map: textTex(label), transparent: true, toneMapped: false, depthWrite: false });
  M.labMats.push(mat);
  const lw = Math.min(W - 0.3, 2.1), pl = new THREE.Mesh(new THREE.PlaneGeometry(lw, lw / 8), mat);
  pl.position.set(-W / 2 + 0.16 + lw / 2, PH * 0.5, D / 2 + 0.003); R.root.add(pl);
}
function roofNo(g, M, no, x, y, z, size) {
  const mat = new THREE.MeshBasicMaterial({ map: textTex(no, { w: 256, h: 256, center: true, ls: '0px', font: '600 150px "Source Serif 4", "Shippori Mincho", Georgia, serif' }), transparent: true, toneMapped: false, depthWrite: false });
  M.roofMats.push(mat);
  const p = new THREE.Mesh(new THREE.PlaneGeometry(size, size), mat); p.rotation.x = -Math.PI / 2; p.position.set(x, y, z); g.add(p);
}

// CST SPHERE — rhombic triacontahedron (30 rhombic faces)
function triacontahedron(r) {
  const p = (1 + Math.sqrt(5)) / 2;
  const ico = [[-1, p, 0], [1, p, 0], [-1, -p, 0], [1, -p, 0], [0, -1, p], [0, 1, p], [0, -1, -p], [0, 1, -p], [p, 0, -1], [p, 0, 1], [-p, 0, -1], [-p, 0, 1]].map(v => new V3(...v).normalize());
  const F = [[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11], [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8], [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9], [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1]];
  const cen = F.map(f => new V3().add(ico[f[0]]).add(ico[f[1]]).add(ico[f[2]]).normalize());
  const E = new Map();
  F.forEach((f, fi) => { for (let k = 0; k < 3; k++) { const a = Math.min(f[k], f[(k + 1) % 3]), b = Math.max(f[k], f[(k + 1) % 3]), key = a + '_' + b; if (!E.has(key)) E.set(key, { a, b, fs: [] }); E.get(key).fs.push(fi); } });
  const pos = [];
  for (const e of E.values()) {
    const A = ico[e.a], Bv = ico[e.b], m = A.clone().add(Bv).normalize(), hA = A.dot(m);
    const C1 = cen[e.fs[0]].clone(), C2 = cen[e.fs[1]].clone();
    C1.multiplyScalar(hA / C1.dot(m)); C2.multiplyScalar(hA / C2.dot(m));
    let q = [A, C1, Bv, C2];
    if (new V3().subVectors(C1, A).cross(new V3().subVectors(Bv, A)).dot(m) < 0) q = q.reverse();
    for (const v of [q[0], q[1], q[2], q[0], q[2], q[3]]) pos.push(v.x * r, v.y * r, v.z * r);
  }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.computeVertexNormals(); return g;
}
function stadium(rOut, rIn, L, depth) {
  const loop = (P, r) => { P.absarc(0, L / 2, r, 0, Math.PI, false); P.absarc(0, -L / 2, r, Math.PI, Math.PI * 2, false); P.closePath(); return P; };
  const sh = loop(new THREE.Shape(), rOut); sh.holes.push(loop(new THREE.Path(), rIn));
  const g = new THREE.ExtrudeGeometry(sh, { depth, bevelEnabled: false, curveSegments: 40 }); g.rotateX(-Math.PI / 2); return g;
}

// 1 — Tower Schola: B3 / 18F / PH1, 82.4 m, glass curtain wall with visible toggle dampers
function buildTower(M) {
  const R = rec(), W = 96, D = 72;
  plinthBase(R, M, W * K, D * K, '1 — TOWER SCHOLA');
  const s = site(R, K);
  B(s, M.board, W, 0.6, D, 0, -0.6, 0);
  B(s, M.road, W, 0.12, 10, 0, 0, -31, { cast: false });
  B(s, M.road, 10, 0.12, D - 10, 45, 0, 5, { cast: false });
  const dash = [];
  for (let x = -44; x < 38; x += 6) dash.push([3, 0.06, 0.3, x, 0.15, -31]);
  for (let z = -22; z < 35; z += 6) dash.push([0.3, 0.06, 3, 45, 0.15, z]);
  I(s, M.frame, dash, false);

  const tx = -16, tz = 2, TW = 44, TD = 32, hw = TW / 2, hd = TD / 2;
  const fl = [[1, 0, 6]]; let y = 6;
  for (let f = 2; f <= 5; f++) { fl.push([f, y, y + 4.4]); y += 4.4; }
  for (let f = 6; f <= 18; f++) { fl.push([f, y, y + 4.3]); y += 4.3; }
  const top = y;
  reg(R, B(s, M.glass, TW - 3, 6, TD - 3, tx, 0, tz), 'f1');
  const cols = [];
  for (let i = 0; i <= 6; i++) { const x = tx - hw + 0.6 + i * (TW - 1.2) / 6; cols.push([0.9, 6, 0.9, x, 3, tz - hd + 0.6], [0.9, 6, 0.9, x, 3, tz + hd - 0.6]); }
  for (let i = 1; i < 4; i++) { const z = tz - hd + 0.6 + i * (TD - 1.2) / 4; cols.push([0.9, 6, 0.9, tx - hw + 0.6, 3, z], [0.9, 6, 0.9, tx + hw - 0.6, 3, z]); }
  I(s, M.frame, cols);
  B(s, M.frame, 18, 0.5, 5, tx, 5.3, tz - hd - 2.5);
  for (const [f, y0, y1] of fl) {
    if (f === 1) continue;
    B(s, M.frame, TW, 0.9, TD, tx, y0, tz);
    reg(R, B(s, M.glass, TW - 0.5, y1 - y0 - 0.9, TD - 0.5, tx, y0 + 0.9, tz), 'f' + f, dimh('t' + f));
  }
  const H = top - 6, cy = 6 + H / 2, nx = 24, nz = 18, mul = [];
  for (let i = 0; i <= nx; i++) { const x = tx - hw + i * TW / nx; mul.push([0.28, H, 0.6, x, cy, tz - hd], [0.28, H, 0.6, x, cy, tz + hd]); }
  for (let i = 1; i < nz; i++) { const z = tz - hd + i * TD / nz; mul.push([0.6, H, 0.28, tx - hw, cy, z], [0.6, H, 0.28, tx + hw, cy, z]); }
  I(s, M.frame, mul);
  const br = [], sx = TW / nx, sz = TD / nz;
  for (const [f, y0, y1] of fl) {
    if (f === 1) continue;
    const h = y1 - y0 - 0.9, c = y0 + 0.9 + h / 2, sg = f % 2 ? 1 : -1;
    for (const bx of [tx - hw + 2 * sx, tx + hw - 2 * sx]) {
      const bw = 2 * sx, L = Math.hypot(bw, h), a = Math.atan2(h, bw) * sg;
      br.push([L, 0.34, 0.18, bx, c, tz - hd + 0.13, 0, a], [L, 0.34, 0.18, bx, c, tz + hd - 0.13, 0, -a]);
    }
    const bw = 2 * sz, L = Math.hypot(bw, h), a = Math.atan2(h, bw) * sg;
    br.push([0.18, 0.34, L, tx - hw + 0.13, c, tz, a, 0], [0.18, 0.34, L, tx + hw - 0.13, c, tz, -a, 0]);
  }
  I(s, M.damper, br, false);
  B(s, M.damper, 8, 3.2, 0.3, tx, 6.95, tz - hd - 0.05);
  B(s, M.frame, TW, 0.9, TD, tx, top, tz, { edge: M.line });
  const pY = top + 0.9;
  B(s, M.frame, TW, 2, 0.5, tx, pY, tz - hd + 0.25); B(s, M.frame, TW, 2, 0.5, tx, pY, tz + hd - 0.25);
  B(s, M.frame, 0.5, 2, TD - 1, tx - hw + 0.25, pY, tz); B(s, M.frame, 0.5, 2, TD - 1, tx + hw - 0.25, pY, tz);
  reg(R, B(s, M.paper, 14, 2, 10, tx + 9, pY, tz + 4, { edge: M.line }), 'roof');
  reg(R, B(s, M.paper, 7, 2.5, 6, tx - 13, pY, tz - 7), 'roof');
  reg(R, B(s, M.green, 18, 0.5, 11, tx - 7, pY, tz + 7), 'roof');
  reg(R, B(s, M.green, 10, 0.5, 7, tx + 11, pY, tz - 8), 'roof');
  I(s, M.frame, [[3, 1.4, 2, tx + 2, pY + 0.7, tz - 9], [3, 1.4, 2, tx + 6, pY + 0.7, tz - 9], [2, 1, 2, tx - 2, pY + 0.5, tz + 1]]);
  const out = new THREE.LineSegments(UE, M.line); out.scale.set(TW + 0.62, top - 6, TD + 0.62); out.position.set(tx, 6 + (top - 6) / 2, tz); s.add(out);

  // plaza on the former Bldg.5 site + CST SPHERE
  B(s, M.frame, 30, 0.16, 50, 23, 0, 1, { cast: false });
  const pv = []; for (let z = -22; z <= 24; z += 5) pv.push([30, 0.04, 0.12, 23, 0.18, z]);
  I(s, M.board, pv, false);
  B(s, M.frame, 3.4, 0.6, 3.4, 23, 0.16, 1);
  const sg = triacontahedron(1.9), sp = new THREE.Mesh(sg, M.metal);
  sp.position.set(23, 0.76 + 1.85, 1); sp.rotation.set(0.35, 0.5, 0.1); sp.castShadow = true; s.add(sp);
  const se = new THREE.LineSegments(new THREE.EdgesGeometry(sg, 5), M.line); se.position.copy(sp.position); se.rotation.copy(sp.rotation); s.add(se);
  I(s, M.frame, [[6, 0.45, 0.9, 16, 0.4, -12], [6, 0.45, 0.9, 30, 0.4, -12], [6, 0.45, 0.9, 16, 0.4, 16], [6, 0.45, 0.9, 30, 0.4, 16]]);
  const tp = [];
  for (let x = -42; x <= 36; x += 7.5) tp.push([x, -23.5]);
  for (let z = -16; z <= 33; z += 7.5) tp.push([37.5, z]);
  tp.push([11, -19], [35, 23], [11, 23]);
  trees(s, M, tp, 2.6, 0.12, 5);

  R.anchor = new V3(tx * K, PH + 84 * K + 0.24, tz * K);
  R.fit = { rp: Math.hypot(W * K / 2, D * K / 2) + 0.1, rt: Math.hypot(Math.abs(tx) + hw, Math.abs(tz) + hd) * K, h: PH + 83 * K, elev: 18 };
  const up = []; for (let f = 6; f <= 18; f++) up.push('f' + f);
  R.zones = { '1F': ['f1'], '2-5F': ['f2', 'f3', 'f4', 'f5'], '6-18F': up, 'R': ['roof'] };
  R.ov = ['f3', 'f5'];
  return R;
}

// 2 — Surugadai Bldg. 1: 7F / B1, glass street front, CST Gallery 3–5F, CST Hall 6F, grand-stair atrium
function buildIchi(M) {
  const R = rec(), W = 76, D = 50;
  plinthBase(R, M, W * K, D * K, '2 — SURUGADAI BLDG. 1');
  const s = site(R, K);
  B(s, M.board, W, 0.6, D, 0, -0.6, 0);
  B(s, M.road, W, 0.12, 9, 0, 0, 20.5, { cast: false });
  const dash = []; for (let x = -36; x < 36; x += 6) dash.push([3, 0.06, 0.3, x, 0.15, 20.5]);
  I(s, M.frame, dash, false);
  const bx = 0, bz = -4, BW = 58, BD = 24, hw = 29, hd = 12, fz = bz + hd, kz = bz - hd;
  const fl = [[1, 0, 5], [2, 5, 9.2], [3, 9.2, 13.4], [4, 13.4, 17.6], [5, 17.6, 21.8], [6, 21.8, 28.8], [7, 28.8, 32.8]], top = 32.8;
  for (const [f, y0, y1] of fl) {
    if (f > 1) B(s, M.frame, BW, 0.8, BD, bx, y0, bz);
    const gy = f > 1 ? y0 + 0.8 : y0, dm = dimh('i' + f);
    reg(R, B(s, M.glass, BW - 0.5, y1 - gy, BD - 0.5, bx, gy, bz), 'f' + f, dm);
    if (f > 1 && f !== 6) {
      reg(R, B(s, M.glass, BW - 8, 1.6, 0.3, bx, y0 + 1.5, kz - 0.45), 'f' + f, dm);
      for (const k of [-1, 1]) reg(R, B(s, M.glass, 0.3, 1.6, BD - 6, bx + k * (hw + 0.45), y0 + 1.5, bz), 'f' + f, dm);
    }
  }
  B(s, M.paper, BW + 0.6, top, 0.6, bx, 0, kz - 0.05, { edge: M.line });
  for (const k of [-1, 1]) B(s, M.paper, 0.6, top, BD, bx + k * (hw + 0.05), 0, bz, { edge: M.line });
  const mul = []; for (let i = 0; i <= 38; i++) mul.push([0.22, top, 0.5, bx - hw + i * BW / 38, top / 2, fz]);
  I(s, M.frame, mul);
  const br = [];
  for (const [f, y0, y1] of fl) {
    if (f < 2 || f === 6) continue;
    const h = y1 - y0 - 0.8, c = y0 + 0.8 + h / 2, sg = f % 2 ? 1 : -1, L = Math.hypot(3.05, h);
    for (const x of [-17.6, 2.3, 18.3]) br.push([L, 0.3, 0.16, x, c, fz - 0.13, 0, Math.atan2(h, 3.05) * sg]);
  }
  I(s, M.damper, br, false);
  reg(R, B(s, M.paper, BW - 1, 6.2, 0.5, bx, 22.6, fz + 0.1), 'hall');
  const fins = []; for (let i = 0; i <= 46; i++) fins.push([0.16, 6.2, 0.5, bx - hw + 0.5 + i * (BW - 1) / 46, 25.7, fz + 0.55]);
  I(s, M.frame, fins);
  const gz = fz + 1.1;
  reg(R, B(s, M.glass, 30, 12.6, 1.9, 3, 9.2, gz, { edge: M.line }), 'gallery');
  B(s, M.frame, 30.6, 0.45, 2.2, 3, 21.8, gz); B(s, M.frame, 30.6, 0.45, 2.2, 3, 8.75, gz);
  const gm = []; for (let i = 0; i <= 10; i++) gm.push([0.2, 12.6, 0.3, -12 + i * 3, 15.5, gz + 0.95]);
  gm.push([30, 0.28, 0.3, 3, 13.4, gz + 0.95], [30, 0.28, 0.3, 3, 17.6, gz + 0.95]);
  I(s, M.frame, gm);
  const ax = -25.5, az = fz + 1.2;
  B(s, M.glass, 7, 28.8, 2.2, ax, 0, az, { edge: M.line });
  B(s, M.frame, 7.4, 0.5, 2.5, ax, 28.8, az);
  const st = [];
  for (let f = 0; f < 5; f++) {
    const y0 = fl[f][1], y1 = fl[f + 1][1], dir = f % 2 ? -1 : 1, n = 9;
    for (let i = 0; i < n; i++) { const t = (i + 0.5) / n; st.push([0.62, 0.3, 0.9, ax + dir * (-2.6 + 5.2 * t), y0 + (y1 - y0) * t, az + 1.2]); }
    st.push([1.4, 0.3, 1.0, ax + dir * 2.7, y1, az + 1.2]);
  }
  reg(R, I(s, M.frame, st), 'stair');
  B(s, M.frame, 14, 0.4, 3.5, 12, 4.5, fz + 1.75);
  B(s, M.frame, BW + 0.7, 0.6, BD + 0.4, bx, top, bz, { edge: M.line });
  const rY = top + 0.6;
  B(s, M.frame, BW + 0.7, 1.2, 0.4, bx, rY, fz); B(s, M.frame, BW + 0.7, 1.2, 0.4, bx, rY, kz);
  I(s, M.frame, [[8, 2.2, 5, -10, rY + 1.1, -6], [5, 1.6, 4, 6, rY + 0.8, -8], [3, 1.2, 3, 14, rY + 0.6, 0]]);
  B(s, M.paper, 6, 3, 5, 20, rY, -8, { edge: M.line });
  const tp = []; for (let x = -34; x <= 34; x += 7.5) tp.push([x, 13.6]);
  trees(s, M, tp, 2.4, 0.12, 9);

  R.anchor = new V3(0, PH + 36 * K + 0.24, bz * K);
  R.fit = { rp: Math.hypot(W * K / 2, D * K / 2) + 0.1, rt: Math.hypot(hw + 1, Math.abs(bz) + hd + 3) * K, h: PH + 36 * K, elev: 24 };
  R.zones = { '3-5F': ['gallery'], '6F': ['hall'], 'stair': ['stair'] };
  R.ov = ['f2', 'f4'];
  return R;
}

// 3 — Funabashi campus (schematic site plan): numbered buildings, experiment halls, traffic test track
function buildFuna(M) {
  const R = rec(), W = 440, D = 320;
  plinthBase(R, M, W * KF, D * KF, '3 — FUNABASHI CAMPUS');
  const s = site(R, KF);
  B(s, M.board, W, 1.4, D, 0, -1.4, 0);
  const rd = (w, d, x, z) => B(s, M.road, w, 0.3, d, x, 0, z, { cast: false });
  rd(W, 10, 0, -148); rd(310, 10, -60, -40); rd(9, 288, -60, 6); rd(9, 288, 96, 6);
  const bl = [['1', -170, -118, 70, 18, 5], ['2', -105, -118, 50, 18, 4], ['3', -170, -80, 60, 16, 4], ['6', -105, -80, 44, 16, 3], ['7', -175, -8, 50, 20, 4], ['8', -112, -8, 46, 20, 4], ['9', -175, 36, 50, 18, 3], ['10', -112, 38, 56, 22, 5], ['11', -25, -118, 40, 20, 3], ['12', 38, -118, 50, 20, 4], ['13', -25, -76, 34, 18, 3], ['14', 40, -74, 60, 26, 6]];
  for (const [no, x, z, w, d, f] of bl) {
    const h = f * 4 + 1.2;
    B(s, M.paper, w, h, d, x, 0, z, { edge: M.line });
    for (let i = 0; i < f; i++) { const key = 'b' + no + 'f' + (i + 1); reg(R, B(s, M.glass, w + 0.4, 1.5, d + 0.4, x, i * 4 + 1.4, z), [key, 'bldg'], dimh(key)); }
    roofNo(s, M, no, x, h + 0.08, z, Math.min(w, d) * 0.85);
  }
  for (const [x, z, w, d, h] of [[18, 2, 72, 32, 12], [18, 62, 72, 30, 10]]) {
    B(s, M.paper, w, h, d, x, 0, z, { edge: M.line });
    const roof = new THREE.Mesh(new THREE.CylinderGeometry(d / 2, d / 2, w, 32, 1, false, 0, Math.PI), M.frame);
    roof.rotation.z = Math.PI / 2; roof.scale.x = 0.32; roof.position.set(x, h, z); roof.castShadow = roof.receiveShadow = true; s.add(roof);
  }
  const tg = stadium(50, 38, 130, 0.6), trk = new THREE.Mesh(tg, M.road);
  trk.position.set(158, 0, 10); trk.receiveShadow = true; s.add(trk); reg(R, trk, 'track');
  const te = new THREE.LineSegments(new THREE.EdgesGeometry(tg, 20), M.line); te.position.copy(trk.position); s.add(te);
  B(s, M.frame, 120, 0.4, 62, -140, 0, 110, { edge: M.line, cast: false });
  const rg = stadium(24, 20, 60, 0.5); rg.rotateY(Math.PI / 2);
  const ring = new THREE.Mesh(rg, M.road); ring.position.set(-140, 0.4, 110); ring.receiveShadow = true; s.add(ring);
  const rnd = rng(11), tp = [];
  for (let x = -205; x <= 205; x += 13) tp.push([x + rnd() * 4, -136 + rnd() * 3], [x + rnd() * 4, 152 + rnd() * 3]);
  for (let z = -128; z <= 140; z += 13) tp.push([-212 + rnd() * 3, z + rnd() * 4], [214 + rnd() * 3, z + rnd() * 4]);
  for (let x = -200; x <= 86; x += 14) tp.push([x + rnd() * 3, -48], [x + rnd() * 3, -32]);
  for (let i = 0; i < 14; i++) tp.push([150 + rnd() * 16, -30 + rnd() * 80]);
  trees(s, M, tp, 5, 0, 13);

  R.anchor = new V3(0, PH + 0.62, 0);
  const rp = Math.hypot(W * KF / 2, D * KF / 2);
  R.fit = { rp: rp + 0.1, rt: rp, h: PH + 32 * KF, elev: 36 };
  R.zones = { bldg: ['bldg'], track: ['track'] };
  R.ov = ['b10f4', 'b14f2', 'b7f1'];
  return R;
}

function studioEnv() {
  const s = new THREE.Scene();
  const room = new THREE.Mesh(new THREE.BoxGeometry(20, 12, 20), new THREE.MeshBasicMaterial({ color: 0x8A8780, side: THREE.BackSide }));
  room.position.y = 5; s.add(room);
  const panel = (w, h, x, y, z, rx, ry, i) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(i, i * 0.98, i * 0.94), side: THREE.DoubleSide })); m.position.set(x, y, z); m.rotation.set(rx, ry, 0); s.add(m); };
  panel(10, 10, 0, 10.9, 0, Math.PI / 2, 0, 3.2);
  panel(6, 8, -9.9, 5, 2, 0, Math.PI / 2, 1.8);
  panel(6, 6, 9.9, 5, -3, 0, -Math.PI / 2, 1.1);
  panel(20, 4, 0, 0.1, 0, -Math.PI / 2, 0, 0.55);
  return s;
}
function mats() {
  const S = (name, o) => { const m = new THREE.MeshStandardMaterial(o); m.name = name; return m; };
  return {
    paper: S('paper', { roughness: 0.92 }), frame: S('frame', { roughness: 0.8 }), glass: S('glass', { roughness: 0.22, metalness: 0.1 }),
    dim: S('glassWarm', { roughness: 0.4 }), lit: S('vacant', { roughness: 0.5 }), board: S('board', { roughness: 0.95 }), road: S('road', { roughness: 1 }),
    plinth: S('plinth', { roughness: 0.6 }), table: S('table', { roughness: 0.85 }), green: S('green', { roughness: 1, flatShading: true }),
    damper: S('damper', { roughness: 0.45, metalness: 0.25 }), metal: S('metal', { roughness: 0.28, metalness: 0.8 }),
    line: new THREE.LineBasicMaterial({ transparent: true, depthWrite: false }), labMats: [], roofMats: []
  };
}
function paint(M, T) {
  for (const k of ['paper', 'frame', 'glass', 'board', 'road', 'plinth', 'table', 'green', 'damper', 'metal']) M[k].color.setHex(T[k]);
  M.dim.color.setHex(T.dim); M.dim.emissive.setHex(T.dimE); M.dim.emissiveIntensity = T.dimEI;
  M.lit.color.setHex(T.lit); M.lit.emissive.setHex(T.litE); M.lit.emissiveIntensity = T.litEI;
  M.line.color.setHex(T.line); M.line.opacity = T.lineO;
  M.labMats.forEach(m => m.color.setHex(T.lab)); M.roofMats.forEach(m => m.color.setHex(T.roofNo));
}

export function createStage(canvas, opts = {}) {
  const mode = opts.mode || 'overview';
  let theme = opts.theme || 'day', period = opts.period ?? 80, focus = opts.focus || 'tower', zone = opts.zone || null;
  const reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance', preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.setClearColor(0x141413, 0);
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(24, 1, 0.1, 400);
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(studioEnv(), 0.04).texture; pmrem.dispose();
  const M = mats();
  const hemi = new THREE.HemisphereLight(); scene.add(hemi);
  const sun = new THREE.DirectionalLight(); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.02; sun.shadow.radius = 3;
  scene.add(sun, sun.target);
  const groundMat = new THREE.ShadowMaterial({ opacity: 0.16, color: 0x141413 });
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(90, 90), groundMat); ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground);
  const rig = new THREE.Group(); scene.add(rig);
  const models = { tower: buildTower(M), ichi: buildIchi(M), funa: buildFuna(M) };

  if (mode === 'overview') {
    const tg = new THREE.CylinderGeometry(6.1, 6.1, 0.14, 128), table = new THREE.Mesh(tg, M.table);
    table.position.y = -0.07; table.castShadow = table.receiveShadow = true; rig.add(table);
    const te = new THREE.LineSegments(new THREE.EdgesGeometry(tg, 30), M.line); te.position.y = -0.07; rig.add(te);
    const place = (R, x, z, ry) => { R.root.position.set(x, 0, z); R.root.rotation.y = ry; rig.add(R.root); };
    place(models.tower, 0, -1.85, 0); place(models.ichi, -2.55, 1.85, 0.32); place(models.funa, 2.45, 1.8, -0.32);
    ground.position.y = -0.142;
  } else {
    for (const k in models) { rig.add(models[k].root); models[k].root.visible = k === focus; }
    ground.position.y = -0.002;
  }

  function applyLit(R, keys) {
    const set = new Set(keys || []);
    for (const e of R.L) e.m.material = e.keys.some(k => set.has(k)) ? M.lit : (theme === 'night' && e.dim ? M.dim : e.base);
  }
  function relight() {
    if (mode === 'overview') for (const k in models) applyLit(models[k], models[k].ov);
    else { const R = models[focus]; applyLit(R, zone && R.zones[zone] ? R.zones[zone] : []); }
  }
  function applyTheme() {
    const T = THEMES[theme] || THEMES.day;
    paint(M, T);
    hemi.color.setHex(T.hemi[0]); hemi.groundColor.setHex(T.hemi[1]); hemi.intensity = T.hemi[2];
    sun.color.setHex(T.sun[0]); sun.intensity = T.sun[1];
    scene.environmentIntensity = T.env; renderer.toneMappingExposure = T.exp; groundMat.opacity = T.shadow;
    relight();
  }

  let target = new V3();
  function samples() {
    const p = [];
    if (mode === 'overview') {
      for (let i = 0; i < 32; i++) {
        const a = i / 32 * Math.PI * 2, c = Math.cos(a), s = Math.sin(a);
        p.push(new V3(c * 6.1, 0, s * 6.1), new V3(c * 6.1, -0.14, s * 6.1));
        if (i % 2 === 0) p.push(new V3(c * 2.95, PH + 84 * K, s * 2.95));
      }
    } else {
      const f = models[focus].fit;
      for (let i = 0; i < 24; i++) { const a = i / 24 * Math.PI * 2, c = Math.cos(a), s = Math.sin(a); p.push(new V3(c * f.rp, 0, s * f.rp), new V3(c * f.rp, PH, s * f.rp), new V3(c * f.rt, f.h, s * f.rt)); }
    }
    return p;
  }
  function fit() {
    const pts = samples(), c = new V3(); pts.forEach(p => c.add(p)); c.divideScalar(pts.length);
    const el = THREE.MathUtils.degToRad(mode === 'overview' ? 27 : models[focus].fit.elev), dir = new V3(0, Math.sin(el), Math.cos(el));
    const MG = 0.88;
    const ext = (d, t) => {
      camera.position.copy(t).addScaledVector(dir, d); camera.lookAt(t); camera.updateMatrixWorld(true);
      let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9; const v = new V3();
      for (const p of pts) { v.copy(p).project(camera); x0 = Math.min(x0, v.x); x1 = Math.max(x1, v.x); y0 = Math.min(y0, v.y); y1 = Math.max(y1, v.y); }
      return { x0, x1, y0, y1 };
    };
    let t = c.clone(), dist = 10;
    for (let pass = 0; pass < 3; pass++) {
      let lo = 0.5, hi = 300;
      for (let i = 0; i < 26; i++) { const d = (lo + hi) / 2, b = ext(d, t); if (Math.max(-b.x0, b.x1, -b.y0, b.y1) > MG) lo = d; else hi = d; }
      dist = hi; const b = ext(dist, t);
      const halfH = dist * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2), halfW = halfH * camera.aspect;
      const right = new V3().setFromMatrixColumn(camera.matrixWorld, 0), upv = new V3().setFromMatrixColumn(camera.matrixWorld, 1);
      t.addScaledVector(right, (b.x0 + b.x1) / 2 * halfW).addScaledVector(upv, (b.y0 + b.y1) / 2 * halfH);
    }
    ext(dist, t); target = t;
    camera.near = dist / 40; camera.far = dist * 4; camera.updateProjectionMatrix();
    let rad = 0; pts.forEach(p => rad = Math.max(rad, p.distanceTo(c)));
    sun.target.position.copy(c);
    sun.position.copy(c).add(new V3(-0.55, 1, 0.62).normalize().multiplyScalar(rad * 3));
    const sc = sun.shadow.camera; sc.left = sc.bottom = -rad * 1.15; sc.right = sc.top = rad * 1.15; sc.near = 0.1; sc.far = rad * 7; sc.updateProjectionMatrix();
  }
  function resize() {
    const w = canvas.clientWidth || 1, h = canvas.clientHeight || 1;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); fit();
  }

  let angle = mode === 'overview' ? -0.35 : -0.6, vel = 0, idle = 10, drag = false, px = 0, last = performance.now(), vis = true, raf = 0, ready = false;
  const onDown = e => { drag = true; px = e.clientX; vel = 0; try { canvas.setPointerCapture(e.pointerId); } catch (x) {} canvas.style.cursor = 'grabbing'; };
  const onMove = e => { if (!drag) return; const d = (e.clientX - px) * 0.009; px = e.clientX; angle += d; vel = d; idle = 0; };
  const onUp = () => { drag = false; idle = 0; canvas.style.cursor = 'grab'; };
  canvas.addEventListener('pointerdown', onDown); canvas.addEventListener('pointermove', onMove);
  canvas.addEventListener('pointerup', onUp); canvas.addEventListener('pointercancel', onUp); canvas.addEventListener('lostpointercapture', onUp);
  const ro = new ResizeObserver(resize); ro.observe(canvas);
  const io = new IntersectionObserver(es => { vis = es[0].isIntersecting; }, { threshold: 0 }); io.observe(canvas);
  canvas.style.transition = 'opacity 260ms ease';

  const anc = ['tower', 'ichi', 'funa'], av = new V3();
  function frame(now) {
    raf = requestAnimationFrame(frame);
    if ((!vis || document.hidden) && ready) { last = now; return; }
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (!drag) {
      angle += vel; vel *= 0.9; idle += dt;
      const w = !reduce && period > 0 ? Math.PI * 2 / period : 0;
      angle += w * dt * Math.min(1, Math.max(0, (idle - 1.2) / 2));
    }
    rig.rotation.y = angle;
    renderer.render(scene, camera);
    if (opts.onAnchors && mode === 'overview') {
      const w = canvas.clientWidth, h = canvas.clientHeight;
      opts.onAnchors(anc.map(id => { const R = models[id]; av.copy(R.anchor); R.root.localToWorld(av); av.project(camera); return { id, x: (av.x + 1) / 2 * w, y: (1 - av.y) / 2 * h }; }));
    }
    if (!ready) { ready = true; opts.onReady && opts.onReady(); }
  }
  applyTheme(); resize(); raf = requestAnimationFrame(frame);

  let swapT = 0;
  window.__rr = (window.__rr || []).concat([{ renderer, scene, camera }]);
  return {
    setTheme(t) { theme = t; applyTheme(); },
    setPeriod(p) { period = p; },
    setZone(z) { zone = z; relight(); },
    setFocus(id, z) {
      if (mode !== 'single') return;
      if (z !== undefined) zone = z;
      if (id === focus) { relight(); return; }
      clearTimeout(swapT); canvas.style.opacity = '0';
      swapT = setTimeout(() => {
        focus = id; for (const k in models) models[k].root.visible = k === focus;
        angle = -0.6; vel = 0; idle = 10; relight(); fit(); canvas.style.opacity = '1';
      }, 240);
    },
    dispose() {
      cancelAnimationFrame(raf); clearTimeout(swapT); ro.disconnect(); io.disconnect();
      canvas.removeEventListener('pointerdown', onDown); canvas.removeEventListener('pointermove', onMove);
      scene.traverse(o => { if (o.geometry && o.geometry !== UB && o.geometry !== UE && o.geometry !== ICO) o.geometry.dispose(); });
      renderer.dispose();
    }
  };
}

// ─── <rr-campus> web component ───
const IDS = ['tower', 'ichi', 'funa'];
class RRCampus extends HTMLElement {
  static get observedAttributes() { return ['theme', 'period', 'focus', 'zone']; }
  connectedCallback() {
    if (this.stage) return;
    const root = this.shadowRoot || this.attachShadow({ mode: 'open' });
    root.innerHTML = '<style>:host{display:block;position:relative;min-height:280px;overflow:hidden}canvas{position:absolute;inset:0;width:100%;height:100%;display:block;touch-action:pan-y;cursor:grab}button{position:absolute;left:0;top:0;width:32px;height:32px;margin:-16px 0 0 -16px;border:none;border-radius:50%;cursor:pointer;font:600 15px/1 "Source Serif 4","Shippori Mincho",Georgia,serif;transform:translate(-999px,-999px);background:var(--rr-badge-bg,#141413);color:var(--rr-badge-ink,#FAF9F5)}:host([theme=night]) button{background:var(--rr-badge-bg,#FAF9F5);color:var(--rr-badge-ink,#141413)}button:focus-visible{outline:2px solid #D97757;outline-offset:2px}</style><canvas role="img"></canvas>';
    const canvas = root.querySelector('canvas');
    canvas.setAttribute('aria-label', this.getAttribute('aria-label') || '日本大学理工学部の校舎模型');
    const mode = this.getAttribute('mode') === 'single' ? 'single' : 'overview', badges = mode === 'overview' && this.hasAttribute('badges');
    this.badgeEls = {};
    if (badges) IDS.forEach((id, i) => {
      const b = document.createElement('button'); b.type = 'button'; b.textContent = String(i + 1); b.setAttribute('aria-label', ['タワー・スコラ', '駿河台校舎 1号館', '船橋校舎'][i]);
      b.addEventListener('click', () => this.dispatchEvent(new CustomEvent('pick', { detail: { id }, bubbles: true })));
      root.appendChild(b); this.badgeEls[id] = b;
    });
    const p = this.getAttribute('period');
    try {
      this.stage = createStage(canvas, {
        mode, theme: this.getAttribute('theme') || 'day', period: p === null ? 80 : +p,
        focus: this.getAttribute('focus') || 'tower', zone: this.getAttribute('zone') || null,
        onAnchors: (a) => {
          for (const q of a) { const b = this.badgeEls[q.id]; if (b) b.style.transform = 'translate(' + q.x.toFixed(1) + 'px,' + q.y.toFixed(1) + 'px)'; }
          this.dispatchEvent(new CustomEvent('anchors', { detail: a }));
        },
        onReady: () => this.dispatchEvent(new Event('ready'))
      });
    } catch (e) { console.warn('[rr-campus] WebGL unavailable', e); this.dispatchEvent(new CustomEvent('error', { detail: e })); }
  }
  disconnectedCallback() { if (this.stage) { this.stage.dispose(); this.stage = null; } }
  attributeChangedCallback(n, o, v) {
    const s = this.stage; if (!s || o === v) return;
    if (n === 'theme') s.setTheme(v || 'day');
    else if (n === 'period') s.setPeriod(v === null ? 80 : +v);
    else if (n === 'focus') s.setFocus(v || 'tower', this.getAttribute('zone') || null);
    else if (n === 'zone') s.setZone(v || null);
  }
}
if (!customElements.get('rr-campus')) customElements.define('rr-campus', RRCampus);
export { RRCampus };
