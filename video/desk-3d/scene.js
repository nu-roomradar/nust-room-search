// RoomRadar 3D 広告「机の上」— 夕方の空き教室の机の上だけで7場面が進む（縦 1080×1920・30秒）。
// 時刻 t（秒）だけで全部が決まるように作る（乱数は種を固定。requestAnimationFrame は使わない）。
// 書き出しは render.py が window.renderAt(t) を1コマずつ呼ぶ。HyperFrames の hf-seek も受ける。
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { Pass, FullScreenQuad } from "three/addons/postprocessing/Pass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";

const W = 1080, H = 1920, FPS = 30, DURATION = 30;
const Q = new URLSearchParams(location.search);
const TEAL = new THREE.Color(0x4fe3cf);

// ───────── 時間の割り振り（場面の切れ目はここだけで決める） ─────────
const T = {
  ring1: 0.6, ring2: 1.5, ring3: 2.4, sweep: 3.3,                    // 1 導入 → 2 空きコマが光る
  cap2In: 4.7, cap2Out: 7.9,
  ringToPhone: 8.0, phoneUp: 8.5, phoneUpEnd: 9.7, screenOn: 9.15,   // 3 スマホが立ち上がる
  cap3In: 9.9, cap3Out: 11.7,
  badge: 12.55, cap4In: 12.2, cap4Out: 13.95,                        // 4 ふつうの使い方：何限まで空いているか
  tapCard: 14.0, modalIn: 14.15, cap4bIn: 14.45, cap4bOut: 17.0,     //   教室を押す → 1週間を見る
  tapLink: 15.05, toRoom: 15.2, backToList: 16.85,
  ringToClock: 16.5, clockRun: 17.2, clockEnd: 18.75, chime: 18.8, refresh: 19.05,   // 5 時限が変わっても「いま」
  cap5In: 17.5, cap5Out: 20.2,
  phoneDown: 20.2, sheetUp: 20.5, sheetUpEnd: 21.8, tagIn: 21.5, tagInEnd: 22.3,    // 6 決めの言葉
  sheetDown: 23.7, sheetDownEnd: 24.8,
  logoIn: 24.5, ring7: 25.3, wordIn: 25.0, noticeIn: 25.2,           // 7 ロゴと必須の表記
};

// ───────── 小道具 ─────────
const clamp01 = (x) => Math.min(1, Math.max(0, x));
const seg = (t, a, b) => clamp01((t - a) / (b - a));
const ss = (x) => x * x * (3 - 2 * x);
const sss = (x) => x * x * x * (x * (x * 6 - 15) + 10);
const eo = (x) => 1 - Math.pow(1 - x, 3);
const back = (x) => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
const lerp = (a, b, p) => a + (b - a) * p;
function rnd(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const V3 = (x, y, z) => new THREE.Vector3(x, y, z);
const loadImg = (src) => new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = () => rej(new Error("画像を読めません: " + src)); im.src = src; });
function mkCanvas(w, h) { const c = document.createElement("canvas"); c.width = w; c.height = h; return c; }
function texFrom(c, srgb = true) { const t = new THREE.CanvasTexture(c); if (srgb) t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t; }
function rr(c, x, y, w, h, r) { c.beginPath(); c.roundRect(x, y, w, h, r); }

async function loadFonts() {
  const defs = [["RRSans", "400", "Regular"], ["RRSans", "500", "Medium"], ["RRSans", "700", "Bold"], ["RRSans", "900", "Black"]];
  for (const [fam, w, n] of defs) { const f = new FontFace(fam, `url(fonts/NotoSansCJKjp-${n}.otf)`, { weight: w }); await f.load(); document.fonts.add(f); }
  const s = new FontFace("Syne", "url(fonts/Syne-wght.ttf)", { weight: "400 800" }); await s.load(); document.fonts.add(s);
}

// ───────── 紙（時間割の表）。単位は mm。A4 縦 ─────────
const TT = { W: 210, H: 297, x0: 8, labelW: 24, colW: 34, headY: 46, headH: 16, rowY: 62, rowH: 40, PX: 10 };
const DAYS = ["月", "火", "水", "木", "金"];
const TIMES = ["9:00", "10:50", "13:20", "15:10", "17:00"];
const CLASSES = [          // [曜日][時限]。null が空きコマ。架空の時間割（実在の人のものではない）
  ["線形代数Ⅱ", "英語Ⅱ", null, "物理学Ⅱ", null],
  [null, "微分方程式", "プログラミング", "化学Ⅱ", null],
  ["物理学実験", "物理学実験", null, null, "ドイツ語Ⅱ"],
  [null, "電磁気学", "統計学", null, null],
  ["熱力学", null, "英語Ⅱ", "力学演習", null],
];
const HERO = [2, 2];                                        // 水曜3限
const cellRect = (d, p) => [TT.x0 + TT.labelW + d * TT.colW, TT.rowY + p * TT.rowH, TT.colW, TT.rowH];
const SHEET_Z = 0.2085;                                     // 紙の手前の辺（ここを軸に起き上がる）
const mmToWorld = (mx, my) => V3((mx - 105) / 1000, 0, SHEET_Z - (TT.H - my) / 1000);   // 平らに置いたとき

function paperBase(seed) {
  const c = mkCanvas(TT.W * TT.PX, TT.H * TT.PX), x = c.getContext("2d");
  x.fillStyle = "#e9e2d2"; x.fillRect(0, 0, c.width, c.height);
  const n = mkCanvas(c.width / 4, c.height / 4), nx = n.getContext("2d"), id = nx.createImageData(n.width, n.height), r = rnd(seed);
  for (let i = 0; i < id.data.length; i += 4) { const v = 120 + r() * 110; id.data[i] = v; id.data[i + 1] = v * 0.98; id.data[i + 2] = v * 0.93; id.data[i + 3] = 255; }
  nx.putImageData(id, 0, 0);
  x.globalAlpha = 0.10; x.drawImage(n, 0, 0, c.width, c.height); x.globalAlpha = 1;
  x.strokeStyle = "rgba(120,108,86,0.07)"; x.lineWidth = 1.6;
  for (let i = 0; i < 1400; i++) { const px = r() * c.width, py = r() * c.height, a = r() * Math.PI, l = 14 + r() * 46; x.beginPath(); x.moveTo(px, py); x.lineTo(px + Math.cos(a) * l, py + Math.sin(a) * l); x.stroke(); }
  return c;
}
function drawGrid(x, alpha) {
  const P = TT.PX, gx = TT.x0 * P, gw = (TT.labelW + 5 * TT.colW) * P, gy = TT.headY * P, gh = (TT.headH + 5 * TT.rowH) * P;
  x.save(); x.globalAlpha = alpha; x.strokeStyle = "#2b2a28"; x.lineWidth = 2.4;
  x.strokeRect(gx, gy, gw, gh);
  x.beginPath();
  for (let d = 0; d <= 5; d++) { const vx = (TT.x0 + TT.labelW + d * TT.colW) * P; x.moveTo(vx, gy); x.lineTo(vx, gy + gh); }
  for (let p = 0; p <= 5; p++) { const hy = (TT.rowY + p * TT.rowH) * P; x.moveTo(gx, hy); x.lineTo(gx + gw, hy); }
  x.stroke(); x.restore();
}
function makeTimetable() {
  const c = paperBase(11), x = c.getContext("2d"), P = TT.PX;
  x.fillStyle = "#23221f"; x.textBaseline = "alphabetic";
  x.font = "700 92px RRSans"; x.fillText("後期 時間割", TT.x0 * P, 33 * P);
  x.font = "500 34px RRSans"; x.fillStyle = "#5c574d"; x.textAlign = "right"; x.fillText("月〜金 ／ 1〜5限", (TT.W - TT.x0) * P, 33 * P); x.textAlign = "left";
  // 見出しの帯と、授業のあるマスの薄い地色
  x.fillStyle = "rgba(96,86,64,0.13)"; x.fillRect(TT.x0 * P, TT.headY * P, (TT.labelW + 5 * TT.colW) * P, TT.headH * P);
  x.fillRect(TT.x0 * P, TT.rowY * P, TT.labelW * P, 5 * TT.rowH * P);
  for (let d = 0; d < 5; d++) for (let p = 0; p < 5; p++) if (CLASSES[d][p]) { const [cx, cy, cw, ch] = cellRect(d, p); x.fillStyle = "rgba(96,86,64,0.07)"; x.fillRect(cx * P, cy * P, cw * P, ch * P); }
  drawGrid(x, 1);
  x.fillStyle = "#23221f"; x.textAlign = "center";
  x.font = "700 62px RRSans";
  DAYS.forEach((d, i) => x.fillText(d, (TT.x0 + TT.labelW + (i + 0.5) * TT.colW) * P, (TT.headY + 11.6) * P));
  for (let p = 0; p < 5; p++) {
    const cy = (TT.rowY + p * TT.rowH) * P, cx = (TT.x0 + TT.labelW / 2) * P;
    x.font = "700 78px RRSans"; x.fillStyle = "#23221f"; x.fillText(String(p + 1), cx, cy + 19.5 * P);
    x.font = "500 30px RRSans"; x.fillStyle = "#5c574d"; x.fillText(TIMES[p] + "〜", cx, cy + 28.5 * P);
  }
  for (let d = 0; d < 5; d++) for (let p = 0; p < 5; p++) {
    const name = CLASSES[d][p]; if (!name) continue;
    const [cx, cy, cw, ch] = cellRect(d, p);
    x.fillStyle = "#262522"; let fs = 46; x.font = `700 ${fs}px RRSans`;
    const lines = name.length > 5 ? [name.slice(0, Math.ceil(name.length / 2)), name.slice(Math.ceil(name.length / 2))] : [name];
    lines.forEach((ln, i) => x.fillText(ln, (cx + cw / 2) * P, (cy + ch / 2) * P + (i - (lines.length - 1) / 2) * 58 + 16));
  }
  x.font = "500 30px RRSans"; x.fillStyle = "#77705f"; x.textAlign = "left"; x.fillText("メモ", TT.x0 * P, 275 * P);
  x.strokeStyle = "rgba(60,56,48,0.35)"; x.lineWidth = 1.5; x.beginPath(); x.moveTo(TT.x0 * P + 80, 276 * P); x.lineTo((TT.W - TT.x0) * P, 276 * P); x.moveTo(TT.x0 * P, 287 * P); x.lineTo((TT.W - TT.x0) * P, 287 * P); x.stroke();
  return c;
}
function makeTagline() {
  const c = paperBase(11), x = c.getContext("2d"), P = TT.PX;
  drawGrid(x, 0.06);
  x.textAlign = "center"; x.fillStyle = "#1f2422";
  x.font = "900 240px RRSans"; x.fillText("空きコマに、", 105 * P, 128 * P);
  x.font = "900 208px RRSans"; x.fillText("すぐ使える教室を。", 105 * P, 163 * P);
  const g = x.createLinearGradient(18 * P, 0, 192 * P, 0); g.addColorStop(0, "rgba(47,196,178,0)"); g.addColorStop(0.12, "rgba(47,196,178,0.95)"); g.addColorStop(0.88, "rgba(47,196,178,0.95)"); g.addColorStop(1, "rgba(47,196,178,0)");
  x.fillStyle = g; x.fillRect(18 * P, 174 * P, 174 * P, 1.8 * P);
  return c;
}
function noiseTex(size, seed, rx, ry) {
  const c = mkCanvas(size, size), x = c.getContext("2d"), id = x.createImageData(size, size), r = rnd(seed);
  for (let i = 0; i < id.data.length; i += 4) { const v = r() * 255; id.data[i] = id.data[i + 1] = id.data[i + 2] = v; id.data[i + 3] = 255; }
  x.putImageData(id, 0, 0);
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(rx, ry); return t;
}
function glowTex() {
  const c = mkCanvas(128, 128), x = c.getContext("2d"), g = x.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(0.25, "rgba(255,255,255,0.55)"); g.addColorStop(0.6, "rgba(255,255,255,0.12)"); g.addColorStop(1, "rgba(255,255,255,0)");
  x.fillStyle = g; x.fillRect(0, 0, 128, 128); return texFrom(c, false);
}
function cookieTex() {      // 窓の形の光（桟の影つき）。スポットライトに投影する
  const c = mkCanvas(512, 512), x = c.getContext("2d");
  x.fillStyle = "#000"; x.fillRect(0, 0, 512, 512);
  x.filter = "blur(5px)"; x.fillStyle = "#fff";
  x.save(); x.translate(256, 256); x.rotate(-0.04);
  // 机のまん中は窓ガラスの中（明るい）。桟の影は手前と左を細く横切る
  const mx = -128, my = 142, bw = 5;
  [[-236, -236, mx - bw + 236, my - bw + 236], [mx + bw, -236, 236 - mx - bw, my - bw + 236], [-236, my + bw, mx - bw + 236, 236 - my - bw], [mx + bw, my + bw, 236 - mx - bw, 236 - my - bw]]
    .forEach(([px, py, pw, ph]) => x.fillRect(px, py, pw, ph));
  x.restore(); x.filter = "none";
  const t = texFrom(c); return t;
}
function clockFaceTex() {
  const S = 512, c = mkCanvas(S, S), x = c.getContext("2d");
  const g = x.createRadialGradient(S / 2, S / 2, 20, S / 2, S / 2, S / 2); g.addColorStop(0, "#f4eee0"); g.addColorStop(1, "#e2d9c6");
  x.fillStyle = g; x.beginPath(); x.arc(S / 2, S / 2, S / 2, 0, 7); x.fill();
  x.translate(S / 2, S / 2); x.strokeStyle = "#24221f"; x.lineCap = "butt";
  for (let i = 0; i < 60; i++) { const a = i / 60 * Math.PI * 2, big = i % 5 === 0; x.lineWidth = big ? 7 : 2.5; const r0 = big ? 196 : 210, r1 = 228; x.beginPath(); x.moveTo(Math.sin(a) * r0, -Math.cos(a) * r0); x.lineTo(Math.sin(a) * r1, -Math.cos(a) * r1); x.stroke(); }
  x.fillStyle = "#24221f"; x.font = "700 62px RRSans"; x.textAlign = "center"; x.textBaseline = "middle";
  [[12, 0, -150], [3, 152, 2], [6, 0, 154], [9, -152, 2]].forEach(([n, px, py]) => x.fillText(String(n), px, py));
  return texFrom(c);
}
function wallTex() {
  const c = mkCanvas(512, 256), x = c.getContext("2d");
  const g = x.createLinearGradient(0, 0, 512, 0); g.addColorStop(0, "#6b4226"); g.addColorStop(0.35, "#3a2518"); g.addColorStop(1, "#1a120d");
  x.fillStyle = g; x.fillRect(0, 0, 512, 256);
  const v = x.createLinearGradient(0, 0, 0, 256); v.addColorStop(0, "rgba(0,0,0,0.45)"); v.addColorStop(0.5, "rgba(0,0,0,0)"); v.addColorStop(1, "rgba(0,0,0,0.5)");
  x.fillStyle = v; x.fillRect(0, 0, 512, 256); return texFrom(c);
}

// ───────── 被写界深度（浅いピント）。半分の解像度でぼかして、ピントの合ったところは元の絵のまま重ねる ─────────
const DOF_COMMON = `
  uniform sampler2D tDepth; uniform float uNear, uFar, uFocus, uK, uMaxR; uniform vec2 uRes; varying vec2 vUv;
  float viewZ(float d) { return (uNear * uFar) / (uFar - d * (uFar - uNear)); }
  float coc(float dist) { return clamp(uK * abs(dist - uFocus) / max(dist, 1e-3), 0.0, uMaxR); }
  float ign(vec2 p) { return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715)))); }`;
const FS_VERT = `varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;
class DofPass extends Pass {
  constructor(rtScene, w, h) {
    super(); this.rtScene = rtScene;
    const hw = Math.max(2, Math.round(w / 2)), hh = Math.max(2, Math.round(h / 2));
    const opt = { type: THREE.HalfFloatType, depthBuffer: false };
    this.rtA = new THREE.WebGLRenderTarget(hw, hh, opt); this.rtB = new THREE.WebGLRenderTarget(hw, hh, opt);
    const U = () => ({ tColor: { value: null }, tDepth: { value: null }, tBlur: { value: null }, uNear: { value: 0.02 }, uFar: { value: 30 }, uFocus: { value: 0.5 }, uK: { value: 20 }, uMaxR: { value: 26 }, uRes: { value: new THREE.Vector2(w, h) }, uSeed: { value: 0 } });
    this.gather = new THREE.ShaderMaterial({ uniforms: U(), vertexShader: FS_VERT, depthTest: false, depthWrite: false, fragmentShader: `
      uniform sampler2D tColor; uniform float uSeed; ${DOF_COMMON}
      void main() {
        float dc = viewZ(texture2D(tDepth, vUv).x), cc = coc(dc);
        vec3 c0 = texture2D(tColor, vUv).rgb; vec3 acc = c0; float ws = 1.0;
        float rot = ign(gl_FragCoord.xy + uSeed) * 6.2831853;
        for (int i = 1; i <= 48; i++) {
          float r = sqrt((float(i) - 0.5) / 48.0) * uMaxR;
          float a = float(i) * 2.39996323 + rot;
          vec2 uv = vUv + vec2(cos(a), sin(a)) * r / uRes;
          float ds = viewZ(texture2D(tDepth, uv).x), cs = coc(ds);
          if (ds > dc) cs = min(cs, cc * 2.0);                 // 奥のぼけを、手前のピントの合ったものに乗せない
          float m = smoothstep(r - 1.0, r + 1.0, cs);
          vec3 c = texture2D(tColor, uv).rgb;
          m *= 1.0 + 0.35 * min(dot(c, vec3(0.3, 0.6, 0.1)), 6.0);   // 明るい点を少し強く（玉ぼけ）
          acc += c * m; ws += m;
        }
        gl_FragColor = vec4(acc / ws, cc / uMaxR);
      }` });
    this.fill = new THREE.ShaderMaterial({ uniforms: U(), vertexShader: FS_VERT, depthTest: false, depthWrite: false, fragmentShader: `
      uniform sampler2D tBlur; ${DOF_COMMON}
      void main() {
        vec4 c = texture2D(tBlur, vUv); float r = c.a * uMaxR * 0.16 + 0.5; vec3 acc = c.rgb; float n = 1.0;
        for (int i = 0; i < 8; i++) { float a = float(i) * 0.7853982; vec2 o = vec2(cos(a), sin(a)) * r / uRes; acc += texture2D(tBlur, vUv + o).rgb; n += 1.0; }
        for (int i = 0; i < 8; i++) { float a = float(i) * 0.7853982 + 0.3927; vec2 o = vec2(cos(a), sin(a)) * r * 2.0 / uRes; acc += texture2D(tBlur, vUv + o).rgb * 0.6; n += 0.6; }
        gl_FragColor = vec4(acc / n, c.a);
      }` });
    this.comp = new THREE.ShaderMaterial({ uniforms: U(), vertexShader: FS_VERT, depthTest: false, depthWrite: false, fragmentShader: `
      uniform sampler2D tColor, tBlur; ${DOF_COMMON}
      void main() {
        float cc = coc(viewZ(texture2D(tDepth, vUv).x));
        vec4 b = texture2D(tBlur, vUv);
        float f = max(smoothstep(0.7, 2.6, cc), smoothstep(0.10, 0.30, b.a) * 0.0);
        gl_FragColor = vec4(mix(texture2D(tColor, vUv).rgb, b.rgb, f), 1.0);
      }` });
    this.fsq = new FullScreenQuad(this.gather);
    this.params = { focus: 0.5, k: 20, maxR: 26, near: 0.02, far: 30, seed: 0 };
  }
  render(renderer, writeBuffer) {
    const p = this.params;
    for (const m of [this.gather, this.fill, this.comp]) {
      const u = m.uniforms; u.tColor.value = this.rtScene.texture; u.tDepth.value = this.rtScene.depthTexture;
      u.uNear.value = p.near; u.uFar.value = p.far; u.uFocus.value = p.focus; u.uK.value = p.k; u.uMaxR.value = p.maxR; u.uSeed.value = p.seed;
    }
    this.fsq.material = this.gather; renderer.setRenderTarget(this.rtA); this.fsq.render(renderer);
    this.fill.uniforms.tBlur.value = this.rtA.texture;
    this.fsq.material = this.fill; renderer.setRenderTarget(this.rtB); this.fsq.render(renderer);
    this.comp.uniforms.tBlur.value = this.rtB.texture;
    this.fsq.material = this.comp; renderer.setRenderTarget(this.renderToScreen ? null : writeBuffer); this.fsq.render(renderer);
  }
}
const GradeShader = {
  uniforms: { tDiffuse: { value: null }, uSeed: { value: 0 }, uVig: { value: 0.42 }, uGrain: { value: 0.035 } },
  vertexShader: FS_VERT,
  fragmentShader: `uniform sampler2D tDiffuse; uniform float uSeed, uVig, uGrain; varying vec2 vUv;
    float h(vec2 p) { vec3 q = fract(vec3(p.xyx) * 0.1031); q += dot(q, q.yzx + 33.33); return fract((q.x + q.y) * q.z); }
    void main() {
      vec3 c = texture2D(tDiffuse, vUv).rgb;
      vec2 d = (vUv - 0.5) * vec2(0.82, 1.0); float v = smoothstep(0.30, 0.98, length(d) * 1.35);
      c *= 1.0 - uVig * v;
      c = mix(c, c * vec3(1.03, 1.0, 0.95), 0.6);                         // わずかに暖かく
      float g = h(gl_FragCoord.xy + uSeed * 17.0) - 0.5; c += g * uGrain * (1.0 - 0.5 * dot(c, vec3(0.333)));
      gl_FragColor = vec4(c, 1.0);
    }`,
};

// ───────── ここから組み立て ─────────
async function build() {
  await loadFonts();
  const [imWood, imLogo, page0, pageN, modal0, room0, rects] = await Promise.all([
    loadImg("assets/wood_src.jpg"), loadImg("assets/logo.png"), loadImg("assets/page0.png"), loadImg("assets/pageN.png"),
    loadImg("assets/modal0.png"), loadImg("assets/room0.png"), fetch("assets/rects.json").then((r) => r.json())]);

  const canvas = document.getElementById("gl");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, preserveDrawingBuffer: true, powerPreference: "high-performance" });
  const PR = (window.devicePixelRatio || 1) * Number(Q.get("rs") || 1);
  renderer.setPixelRatio(PR); renderer.setSize(W, H, false);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = Q.has("pcf") ? THREE.PCFShadowMap : THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0;
  const rw = Math.round(W * PR), rh = Math.round(H * PR);

  const scene = new THREE.Scene(); scene.background = new THREE.Color(0x0b0806);
  const camera = new THREE.PerspectiveCamera(30, W / H, 0.02, 30);

  // 映り込み用の環境（暗い部屋に、左の窓だけが明るい）
  {
    const env = new THREE.Scene();
    env.add(new THREE.Mesh(new THREE.BoxGeometry(8, 4, 8), new THREE.MeshBasicMaterial({ color: 0x1c130c, side: THREE.BackSide })));
    const wm = new THREE.MeshBasicMaterial({ color: new THREE.Color(14, 8.2, 3.6) });
    for (const z of [-2.4, -0.9, 0.6]) { const m = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 1.5), wm); m.position.set(-3.9, 0.9, z); m.rotation.y = Math.PI / 2; env.add(m); }
    const cm = new THREE.Mesh(new THREE.PlaneGeometry(8, 8), new THREE.MeshBasicMaterial({ color: 0x2a2018 })); cm.rotation.x = Math.PI / 2; cm.position.y = 1.95; env.add(cm);
    const pm = new THREE.PMREMGenerator(renderer); scene.environment = pm.fromScene(env, 0.03, 0.1, 20).texture; scene.environmentIntensity = 0.42;
  }

  // 光：窓からの夕方の光（斜め・暖色・桟の影）と、弱い全体の光
  const sun = new THREE.SpotLight(0xffab6b, 27, 0, 0.33, 0.4, 2);
  sun.position.set(-1.95, 1.02, -1.2); sun.target.position.set(0.03, 0, 0.08); scene.add(sun, sun.target);
  sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.camera.near = 0.9; sun.shadow.camera.far = 4.5; sun.shadow.bias = -0.00012; sun.shadow.normalBias = 0.0025;
  sun.map = cookieTex();
  scene.add(new THREE.HemisphereLight(0xb7ab9c, 0x3b2617, 0.26));
  const tealLight = new THREE.PointLight(TEAL, 0, 0.9, 2); scene.add(tealLight);
  const frontFill = new THREE.DirectionalLight(0xffe2c4, 0); frontFill.position.set(-0.55, 0.42, 1.25); frontFill.target.position.set(0, 0.14, SHEET_Z); scene.add(frontFill, frontFill.target);
  const phoneLight = new THREE.PointLight(0x9fd6ee, 0, 0.5, 2); scene.add(phoneLight);

  // 机
  const woodMap = new THREE.Texture(imWood); woodMap.colorSpace = THREE.SRGBColorSpace; woodMap.wrapS = woodMap.wrapT = THREE.MirroredRepeatWrapping; woodMap.repeat.set(1.7 / 0.80, 1.15 / 0.60); woodMap.anisotropy = 2; woodMap.needsUpdate = true;
  const woodBump = new THREE.Texture(imWood); woodBump.wrapS = woodBump.wrapT = THREE.MirroredRepeatWrapping; woodBump.repeat.copy(woodMap.repeat); woodBump.needsUpdate = true;
  const desk = new THREE.Mesh(new THREE.BoxGeometry(1.7, 0.036, 1.15), new THREE.MeshPhysicalMaterial({ map: woodMap, color: 0xe6d2bd, roughness: 0.52, bumpMap: woodBump, bumpScale: 0.9, clearcoat: Q.has("nocc") ? 0 : 0.32, clearcoatRoughness: 0.34 }));
  desk.position.set(0, -0.018, 0.05); desk.receiveShadow = true; scene.add(desk);

  // 教室（ぼけて見える背景。光らない単色で組む）
  {
    const B = (w, h, d, col, x, y, z) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), new THREE.MeshBasicMaterial({ color: col })); m.position.set(x, y, z); scene.add(m); return m; };
    const back = new THREE.Mesh(new THREE.PlaneGeometry(9, 3.4), new THREE.MeshBasicMaterial({ map: wallTex() })); back.position.set(0.6, 0.75, -3.6); scene.add(back);
    B(3.3, 1.15, 0.04, 0x16211d, 0.5, 1.02, -3.56); B(3.42, 0.05, 0.05, 0x4a3323, 0.5, 0.43, -3.54);     // 黒板と粉受け
    B(0.05, 3.4, 9, 0x2a1b12, -2.72, 0.75, -0.2);                                                       // 左の壁
    B(9, 0.05, 9, 0x22180f, 0.6, -0.74, -0.2); B(9, 0.05, 9, 0x120d09, 0.6, 2.2, -0.2); B(0.05, 3.4, 9, 0x150f0b, 3.6, 0.75, -0.2);
    const pane = new THREE.MeshBasicMaterial({ color: new THREE.Color(7.5, 4.2, 1.7) }), paneHi = new THREE.MeshBasicMaterial({ color: new THREE.Color(11, 7.0, 3.4) });
    for (const z of [-2.75, -1.25, 0.25]) {
      const p = new THREE.Mesh(new THREE.PlaneGeometry(1.2, 1.45), pane); p.rotation.y = Math.PI / 2; p.position.set(-2.69, 0.95, z); scene.add(p);
      const p2 = new THREE.Mesh(new THREE.PlaneGeometry(1.2, 0.5), paneHi); p2.rotation.y = Math.PI / 2; p2.position.set(-2.685, 0.52, z); scene.add(p2);
      B(0.03, 1.5, 0.045, 0x1c120b, -2.67, 0.95, z); B(0.03, 0.045, 1.24, 0x1c120b, -2.67, 0.95, z);
      B(0.04, 1.56, 0.07, 0x1c120b, -2.67, 0.95, z - 0.62); B(0.04, 1.56, 0.07, 0x1c120b, -2.67, 0.95, z + 0.62);
    }
    const r = rnd(5);
    for (let row = 0; row < 3; row++) for (let col = -2; col <= 2; col++) {            // ほかの机といす
      if (row === 0 && col === 0) continue;
      const x = col * 1.25 + 0.1, z = -1.25 - (row - 0) * 1.05 + (row === 0 ? 1.25 : 0.2), lit = clamp01(1 - (x + 2.6) / 4.2);
      const top = new THREE.Color().setRGB(0.05 + 0.26 * lit, 0.03 + 0.13 * lit, 0.018 + 0.05 * lit);
      B(1.05, 0.03, 0.48, top, x, -0.02, z); B(0.95, 0.5, 0.03, 0x1b130d, x, -0.3, z - 0.2);
      const cb = new THREE.Color().setRGB(0.035 + 0.10 * lit, 0.022 + 0.055 * lit, 0.014 + 0.024 * lit);
      B(0.36, 0.34, 0.025, cb, x - 0.22 + r() * 0.06, 0.02, z + 0.42); B(0.36, 0.34, 0.025, cb, x + 0.26 + r() * 0.06, 0.02, z + 0.44);
    }
  }

  // 紙（左右2枚。真ん中を背にして本のように少し開ける）
  const paperTex = texFrom(makeTimetable()), tagTex = texFrom(makeTagline());
  const paperBump = noiseTex(256, 3, 5, 7);
  const sheet = new THREE.Group(); sheet.position.set(0, 0.0009, SHEET_Z); sheet.rotation.x = -Math.PI / 2; scene.add(sheet);
  const halves = [], tagMats = [];
  for (const side of [-1, 1]) {
    const g = new THREE.PlaneGeometry(0.105, 0.297, 14, 40); g.translate(side * 0.0525, 0.1485, 0);
    const pos = g.attributes.position, uv = g.attributes.uv;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i), y = pos.getY(i);
      const c1 = clamp01((x - 0.03) / 0.075) * clamp01((y - 0.19) / 0.107), c2 = clamp01((-x - 0.05) / 0.055) * clamp01((0.07 - y) / 0.07);
      pos.setZ(i, 0.0016 * c1 * c1 + 0.0009 * c2 * c2 + 0.00025 * (1 + Math.sin(y * 34 + x * 21)) * 0.5);
      uv.setX(i, side < 0 ? uv.getX(i) * 0.5 : 0.5 + uv.getX(i) * 0.5);
    }
    g.computeVertexNormals();
    const grp = new THREE.Group();
    const m = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ map: paperTex, roughness: 0.93, metalness: 0, bumpMap: paperBump, bumpScale: 0.25, side: THREE.DoubleSide }));
    m.castShadow = true; m.receiveShadow = true; grp.add(m);
    const tm = new THREE.MeshStandardMaterial({ map: tagTex, roughness: 0.93, metalness: 0, bumpMap: paperBump, bumpScale: 0.25, transparent: true, opacity: 0, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
    const t = new THREE.Mesh(g, tm); t.receiveShadow = true; t.visible = false; grp.add(t); tagMats.push([t, tm]);
    sheet.add(grp); halves.push([grp, side]);
  }

  // 空きコマの光る札
  const glow = glowTex();
  const tiles = [];
  const sweepC = mmToWorld(cellRect(...HERO)[0] + TT.colW / 2, cellRect(...HERO)[1] + TT.rowH / 2);
  for (let d = 0; d < 5; d++) for (let p = 0; p < 5; p++) {
    if (CLASSES[d][p]) continue;
    const [cx, cy, cw, ch] = cellRect(d, p), c = mmToWorld(cx + cw / 2, cy + ch / 2), hero = d === HERO[0] && p === HERO[1];
    const g = new THREE.Group(); g.position.copy(c);
    const mat = new THREE.MeshBasicMaterial({ color: new THREE.Color(0x1fc7b0).multiplyScalar(hero ? 1.25 : 0.95), transparent: true, opacity: 0, depthWrite: false });
    const box = new THREE.Mesh(new THREE.BoxGeometry(cw / 1000 * 0.9, 0.0012, ch / 1000 * 0.9), mat); g.add(box);
    const em = new THREE.LineBasicMaterial({ color: TEAL.clone().multiplyScalar(hero ? 4.5 : 2.6), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
    const edge = new THREE.LineSegments(new THREE.EdgesGeometry(box.geometry), em); g.add(edge);
    const sm = new THREE.SpriteMaterial({ map: glow, color: TEAL, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
    const halo = new THREE.Mesh(new THREE.PlaneGeometry(cw / 1000 * 2.1, ch / 1000 * 2.1), new THREE.MeshBasicMaterial({ map: glow, color: 0x18b8a2, transparent: true, opacity: 0, depthWrite: false }));
    halo.rotation.x = -Math.PI / 2; halo.position.set(c.x, 0.0031, c.z); scene.add(halo);
    scene.add(g); tiles.push({ g, mat, em, halo, hero, tOn: T.sweep + c.distanceTo(sweepC) / 0.17 }); void sm;
  }

  // レーダーの輪（机の面に沿って広がる）
  const RINGS = [
    { t0: T.ring1, c: [sweepC.x, sweepC.z], v: 0.085, s: 1.0 }, { t0: T.ring2, c: [sweepC.x, sweepC.z], v: 0.085, s: 0.8 }, { t0: T.ring3, c: [sweepC.x, sweepC.z], v: 0.085, s: 0.8 },
    { t0: T.sweep, c: [sweepC.x, sweepC.z], v: 0.17, s: 1.25 },
    { t0: T.ringToPhone, c: [sweepC.x, sweepC.z], v: 0.30, s: 1.1 },
    { t0: T.ringToClock, c: [-0.035, -0.165], v: 0.22, s: 1.0 },
    { t0: T.chime, c: [0.082, -0.100], v: 0.26, s: 1.1 },
    { t0: T.sheetUp - 0.25, c: [0, SHEET_Z], v: 0.30, s: 1.0 },
    { t0: T.ring7, c: [-0.01435, 0.36300], v: 0.15, s: 1.05 }, { t0: T.ring7 + 0.9, c: [-0.01435, 0.36300], v: 0.15, s: 0.7 },
  ];
  const ringU = { uRings: { value: Array.from({ length: 6 }, () => new THREE.Vector4(0, 0, -1, 0)) }, uColor: { value: TEAL.clone() } };
  const ringMesh = new THREE.Mesh(new THREE.PlaneGeometry(3, 3), new THREE.ShaderMaterial({
    uniforms: ringU, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: `varying vec2 vP; void main() { vec4 w = modelMatrix * vec4(position, 1.0); vP = w.xz; gl_Position = projectionMatrix * viewMatrix * w; }`,
    fragmentShader: `uniform vec4 uRings[6]; uniform vec3 uColor; varying vec2 vP;
      void main() { float I = 0.0;
        for (int i = 0; i < 6; i++) { vec4 r = uRings[i]; if (r.z < 0.0 || r.w < 0.002) continue; float x = distance(vP, r.xy) - r.z;
          // 遠いところは計算しない（とても小さい数になり、ソフトウェア描画が極端に遅くなる）
          float a = x / 0.0022, b = x / 0.011;
          float line = abs(a) < 4.0 ? exp(-a * a) : 0.0, halo = abs(b) < 4.0 ? exp(-b * b) * 0.22 : 0.0, trail = (x < 0.0 && x > -0.3) ? exp(x / 0.05) * 0.025 : 0.0;
          I += r.w * (line * 1.6 + halo + trail); }
        if (I < 0.0015) discard;
        gl_FragColor = vec4(uColor * I, 1.0); }` }));
  ringMesh.rotation.x = -Math.PI / 2; ringMesh.position.y = 0.0034; scene.add(ringMesh);

  // スマホ（平らに置いてあり、立ち上がる）。平らな金属の枠・角の丸い黒いガラス・細い縁・横のボタン。ロゴなどの印は付けない
  const PW = 0.0706, PHT = 0.1486, PD = 0.0083, PRAD = 0.0125, BZ = 0.0018;
  const SW = PW - 2 * BZ, SH = SW * 844 / 390, SCY = PHT / 2, PH = { x: -0.035, z: -0.165, lean: -0.25 };
  const rrShape = (w, h, r, y0) => { const sh = new THREE.Shape(), x0 = -w / 2;
    sh.moveTo(x0 + r, y0); sh.lineTo(x0 + w - r, y0); sh.absarc(x0 + w - r, y0 + r, r, -Math.PI / 2, 0, false);
    sh.lineTo(x0 + w, y0 + h - r); sh.absarc(x0 + w - r, y0 + h - r, r, 0, Math.PI / 2, false);
    sh.lineTo(x0 + r, y0 + h); sh.absarc(x0 + r, y0 + h - r, r, Math.PI / 2, Math.PI, false);
    sh.lineTo(x0, y0 + r); sh.absarc(x0 + r, y0 + r, r, Math.PI, Math.PI * 1.5, false); return sh; };
  const phone = new THREE.Group(); phone.position.set(PH.x, 0.0004, PH.z); scene.add(phone);
  const titan = new THREE.MeshStandardMaterial({ color: 0x969088, metalness: 1.0, roughness: 0.34 });
  const bev = 0.0007, frameG = new THREE.ExtrudeGeometry(rrShape(PW - 2 * bev, PHT - 2 * bev, PRAD - bev, bev), { depth: PD - 2 * bev, bevelEnabled: true, bevelThickness: bev, bevelSize: bev, bevelSegments: 3, curveSegments: 20 });
  frameG.translate(0, 0, bev);
  const body = new THREE.Mesh(frameG, titan); body.castShadow = true; body.receiveShadow = true; phone.add(body);
  const front = new THREE.Mesh(new THREE.ShapeGeometry(rrShape(PW - 0.0015, PHT - 0.0015, PRAD - 0.00075, 0.00075), 20), new THREE.MeshStandardMaterial({ color: 0x040405, roughness: 0.22, metalness: 0 }));
  front.position.z = PD + 0.00004; phone.add(front);
  for (const [sx, y, len] of [[1, 0.098, 0.0155], [-1, 0.1215, 0.0058], [-1, 0.1085, 0.0098], [-1, 0.0955, 0.0098]]) {      // 右：電源／左：上のボタンと音量
    const bt = new THREE.Mesh(new RoundedBoxGeometry(0.0012, len, 0.0030, 2, 0.0005), titan); bt.position.set(sx * (PW / 2 + 0.00025), y, PD / 2); bt.castShadow = true; phone.add(bt);
  }
  const scrC = mkCanvas(390 * 5, 844 * 5), scrX = scrC.getContext("2d"), scrTex = texFrom(scrC); scrTex.generateMipmaps = true;
  const scrMat = new THREE.MeshBasicMaterial({ map: scrTex, color: new THREE.Color(1.12, 1.12, 1.12) });
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(SW, SH), scrMat); screen.position.set(0, SCY, PD + 0.00010); phone.add(screen);
  { // ガラスらしい、うっすらした斜めの映り込み（光の点は出さない）
    const gc = mkCanvas(256, 512), gx = gc.getContext("2d"), g = gx.createLinearGradient(0, 0, 256, 512);
    g.addColorStop(0, "rgba(255,255,255,0)"); g.addColorStop(0.30, "rgba(255,255,255,0)"); g.addColorStop(0.44, "rgba(255,240,225,0.028)"); g.addColorStop(0.52, "rgba(255,240,225,0.008)"); g.addColorStop(0.60, "rgba(255,240,225,0.018)"); g.addColorStop(0.72, "rgba(255,255,255,0)"); g.addColorStop(1, "rgba(255,255,255,0)");
    gx.fillStyle = g; gx.fillRect(0, 0, 256, 512);
    const sheen = new THREE.Mesh(new THREE.PlaneGeometry(SW, SH), new THREE.MeshBasicMaterial({ map: texFrom(gc), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })); sheen.position.set(0, SCY, PD + 0.00016); phone.add(sheen);
  }
  const scrPoint = (cx, cy) => V3((cx / 390 - 0.5) * SW, SCY + (0.5 - cy / 844) * SH, PD + 0.0002);     // 画面上の位置（CSS px）→ スマホの中の位置

  // 置き時計
  const clock = new THREE.Group(); clock.position.set(0.082, 0, -0.100); clock.rotation.y = -0.22; scene.add(clock);
  const metal = new THREE.MeshStandardMaterial({ color: 0x2c2a27, metalness: 0.85, roughness: 0.38 }), brass = new THREE.MeshStandardMaterial({ color: 0xa98a58, metalness: 0.95, roughness: 0.3 });
  const cy0 = 0.052;
  const cb = new THREE.Mesh(new THREE.CylinderGeometry(0.046, 0.046, 0.03, 72), metal); cb.rotation.x = Math.PI / 2; cb.position.y = cy0; cb.castShadow = true; clock.add(cb);
  const rim = new THREE.Mesh(new THREE.TorusGeometry(0.0452, 0.0026, 18, 80), brass); rim.position.set(0, cy0, 0.015); rim.castShadow = true; clock.add(rim);
  const face = new THREE.Mesh(new THREE.CircleGeometry(0.0432, 72), new THREE.MeshStandardMaterial({ map: clockFaceTex(), roughness: 0.8 })); face.position.set(0, cy0, 0.0152); clock.add(face);
  const handM = new THREE.MeshStandardMaterial({ color: 0x191817, roughness: 0.5 });
  const hg = new THREE.BoxGeometry(0.0032, 0.024, 0.0007); hg.translate(0, 0.009, 0); const hourH = new THREE.Mesh(hg, handM); hourH.position.set(0, cy0, 0.0164); clock.add(hourH);
  const mg = new THREE.BoxGeometry(0.0022, 0.037, 0.0007); mg.translate(0, 0.0145, 0); const minH = new THREE.Mesh(mg, handM); minH.position.set(0, cy0, 0.0173); clock.add(minH);
  const capM = new THREE.Mesh(new THREE.CylinderGeometry(0.0024, 0.0024, 0.0016, 20), brass); capM.rotation.x = Math.PI / 2; capM.position.set(0, cy0, 0.0182); clock.add(capM);
  const cg = new THREE.Mesh(new THREE.CircleGeometry(0.0432, 72), new THREE.MeshPhysicalMaterial({ color: 0x000000, roughness: 0.05, transparent: true, opacity: 0.12, envMapIntensity: 2 })); cg.position.set(0, cy0, 0.0192); clock.add(cg);
  const foot = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.008, 0.034), metal); foot.position.set(0, 0.004, 0); foot.castShadow = true; foot.receiveShadow = true; clock.add(foot);
  const clockFace = clock.localToWorld(V3(0, cy0, 0.016));

  // 鉛筆
  {
    const pen = new THREE.Group(); pen.position.set(-0.168, 0.0037, 0.105); pen.rotation.y = 1.02; scene.add(pen);
    const lac = new THREE.MeshPhysicalMaterial({ color: 0x22201e, roughness: 0.35, clearcoat: 0.6, clearcoatRoughness: 0.2 });
    const b1 = new THREE.Mesh(new THREE.CylinderGeometry(0.0036, 0.0036, 0.15, 6), lac); b1.rotation.z = Math.PI / 2; b1.castShadow = true; pen.add(b1);
    const tip = new THREE.Mesh(new THREE.CylinderGeometry(0.0006, 0.0036, 0.013, 6), new THREE.MeshStandardMaterial({ color: 0xd9bb93, roughness: 0.8 })); tip.rotation.z = Math.PI / 2; tip.position.x = -0.0815; tip.castShadow = true; pen.add(tip);
    const lead = new THREE.Mesh(new THREE.CylinderGeometry(0.00005, 0.0009, 0.0035, 6), new THREE.MeshStandardMaterial({ color: 0x2b2b2e, roughness: 0.4, metalness: 0.3 })); lead.rotation.z = Math.PI / 2; lead.position.x = -0.0893; pen.add(lead);
    const fer = new THREE.Mesh(new THREE.CylinderGeometry(0.0037, 0.0037, 0.009, 16), new THREE.MeshStandardMaterial({ color: 0xb9b3a8, metalness: 0.95, roughness: 0.28 })); fer.rotation.z = Math.PI / 2; fer.position.x = 0.0795; fer.castShadow = true; pen.add(fer);
    const er = new THREE.Mesh(new THREE.CylinderGeometry(0.0034, 0.0034, 0.008, 16), new THREE.MeshStandardMaterial({ color: 0xcdbfb3, roughness: 0.9 })); er.rotation.z = Math.PI / 2; er.position.x = 0.088; er.castShadow = true; pen.add(er);
  }

  // ロゴ（机の上に光で描く）。透明なところの色のごみを消してから使う
  const LOGO = { w: 0.19, cx: 0.0, cz: 0.365 }; LOGO.h = LOGO.w * imLogo.height / imLogo.width;
  const lc = mkCanvas(imLogo.width, imLogo.height), lx = lc.getContext("2d"); lx.drawImage(imLogo, 0, 0);
  { const id = lx.getImageData(0, 0, lc.width, lc.height), d = id.data; for (let i = 0; i < d.length; i += 4) if (d[i + 3] < 10) { d[i] = 116; d[i + 1] = 166; d[i + 2] = 162; d[i + 3] = 0; } lx.putImageData(id, 0, 0); }
  const logoMat = new THREE.MeshBasicMaterial({ map: texFrom(lc), color: new THREE.Color(1.22, 1.22, 1.22), transparent: true, opacity: 0, depthWrite: false });
  const logo = new THREE.Mesh(new THREE.PlaneGeometry(LOGO.w, LOGO.h), logoMat); logo.rotation.x = -Math.PI / 2; logo.position.set(LOGO.cx, 0.0038, LOGO.cz); scene.add(logo);
  const logoGlow = new THREE.Mesh(new THREE.PlaneGeometry(LOGO.w * 2.2, LOGO.h * 2.6), new THREE.MeshBasicMaterial({ map: glow, color: TEAL, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
  logoGlow.rotation.x = -Math.PI / 2; logoGlow.position.set(LOGO.cx, 0.0036, LOGO.cz); scene.add(logoGlow);
  const radarC = V3(LOGO.cx - LOGO.w / 2 + 0.4156 * LOGO.w, 0, LOGO.cz - LOGO.h / 2 + 0.4297 * LOGO.h);
  RINGS[8].c = RINGS[9].c = [radarC.x, radarC.z];

  // 光の粒（報告の印が消えるとき）
  const sparks = [];
  { const r = rnd(42); for (let i = 0; i < 150; i++) { const sm = new THREE.SpriteMaterial({ map: glow, color: TEAL.clone().multiplyScalar(2.2), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }); const s = new THREE.Sprite(sm); s.visible = false; scene.add(s);
      sparks.push({ s, sm, d: V3((r() - 0.5) * 1.0, 0.35 + r() * 1.0, 0.15 + r() * 0.9).multiplyScalar(0.035 + r() * 0.05), o: V3((r() - 0.5) * 0.019, (r() - 0.5) * 0.015, 0), life: 0.7 + r() * 1.0, delay: r() * 0.35, size: 0.0022 + r() * 0.0042, ph: r() * 6.28 }); } }

  // ───────── スマホの画面（アプリの実画面の写真を、時刻に合わせて描く） ─────────
  // 流れ：一覧（水曜3限）→「〜6限」の札 → 教室を押す → その教室の1週間 → 一覧に戻る → 時限が変わると「いま」が水曜4限に
  const S6 = 6, VW = 390, VH = 844, SB = 47;
  const SCROLL0 = rects.chips[1] - 96, SCROLL1 = rects.chips[1] - 12;          // 開いた直後 → 少しスクロールして教室を見る
  const vy = (pageY, sc) => pageY - sc + SB;                                   // ページの中の位置 → 画面の中の位置
  const M0 = { top: rects.modal[1], h: rects.modal[3] }, LINK = rects.link;
  const BADGES = ["span701", "span", "span751", "span752", "span805"].map((k, i) => ({ r: rects[k], t0: T.badge + i * 0.22 }));
  const ROOMSC = 52;                                                           // 1週間のページを少しスクロールして表を真ん中に
  let lastKey = "";
  function screenState(t) {
    const st = { on: ss(seg(t, T.screenOn, T.screenOn + 0.5)) * (1 - ss(seg(t, T.phoneDown, T.phoneDown + 0.5))) };
    st.scroll = lerp(SCROLL0, SCROLL1, sss(seg(t, T.screenOn + 0.7, T.screenOn + 1.9)));
    st.next = ss(seg(t, T.refresh, T.refresh + 0.8));                                           // 時限が変わったあとの一覧へ
    st.room = eo(seg(t, T.toRoom, T.toRoom + 0.42)) * (1 - eo(seg(t, T.backToList, T.backToList + 0.42)));   // 1週間のページ（横から入る）
    st.roomScroll = ROOMSC * sss(seg(t, T.toRoom + 0.5, T.toRoom + 1.3));
    st.modalP = eo(seg(t, T.modalIn, T.modalIn + 0.38)) * (1 - ss(seg(t, T.toRoom, T.toRoom + 0.2)));
    st.press = seg(t, T.tapLink, T.tapLink + 0.08) * (1 - seg(t, T.tapLink + 0.1, T.tapLink + 0.28));
    st.taps = [];
    const tap = (t0, x, y) => { const p = seg(t, t0, t0 + 0.5); if (p > 0 && p < 1) st.taps.push([x, y, p]); };
    tap(T.tapCard, rects.card[0] + rects.card[2] / 2, vy(rects.card[1], SCROLL1) + rects.card[3] / 2);
    tap(T.tapLink, LINK[0] + LINK[2] / 2, LINK[1] + LINK[3] / 2);
    st.badges = BADGES.map((b) => { const p = seg(t, b.t0, b.t0 + 0.9); return p > 0 && p < 1 ? p : 0; });
    st.clock = t >= T.clockEnd ? "15:10" : "14:40";
    return st;
  }
  function drawScreen(st) {
    const key = JSON.stringify(st, (k, v) => typeof v === "number" ? Math.round(v * 500) / 500 : v);
    if (key === lastKey) return; lastKey = key;
    const c = scrX; c.save(); c.setTransform(5, 0, 0, 5, 0, 0);
    c.fillStyle = "#000"; c.fillRect(0, 0, VW, VH);
    if (st.on > 0.001) {
      rr(c, 0, 0, VW, VH, 60); c.clip();
      c.fillStyle = "#0a0a0f"; c.fillRect(0, 0, VW, VH);
      const xl = -st.room * VW * 0.28;                                // 一覧は少し左へ下がる
      const list = (img, a) => { c.globalAlpha = a; c.drawImage(img, 0, st.scroll * S6, VW * S6, (VH - SB) * S6, xl, SB, VW, VH - SB); c.globalAlpha = 1; };
      list(page0, 1); if (st.next > 0) list(pageN, st.next);
      st.badges.forEach((p, i) => { if (!p) return;                   // 「〜6限」の札を青緑で囲む
        const r = BADGES[i].r, g = 2 + p * 5, a = Math.sin(Math.PI * Math.min(1, p * 1.25));
        c.strokeStyle = `rgba(95,230,210,${a})`; c.lineWidth = 2; rr(c, xl + r[0] - g, vy(r[1], st.scroll) - g, r[2] + g * 2, r[3] + g * 2, 8 + g); c.stroke();
        c.fillStyle = `rgba(95,230,210,${a * 0.16})`; c.fill(); });
      if (st.modalP > 0.001) {
        c.globalAlpha = Math.min(1, st.modalP * 1.2); c.drawImage(modal0, 0, 0, VW * S6, M0.top * S6, 0, 0, VW, M0.top);
        c.fillStyle = "rgba(6,6,10,0.86)"; c.fillRect(0, M0.top, VW, VH - M0.top); c.globalAlpha = 1;
        const yo = (1 - st.modalP) * (M0.h + 20);
        c.drawImage(modal0, 0, M0.top * S6, VW * S6, M0.h * S6, 0, M0.top + yo, VW, M0.h);
        if (st.press > 0) { c.fillStyle = `rgba(120,160,255,${0.22 * st.press})`; rr(c, LINK[0] - 8, LINK[1] - 7 + yo, LINK[2] + 16, LINK[3] + 14, 8); c.fill(); }
      }
      if (st.room > 0.001) {                                         // その教室の1週間（右から入ってくる）
        const xr = (1 - st.room) * VW;
        c.fillStyle = `rgba(0,0,0,${0.4 * st.room})`; c.fillRect(0, SB, VW, VH - SB);
        c.fillStyle = "#0a0a0f"; c.fillRect(xr, SB, VW, VH - SB);
        const hSrc = Math.min((VH - SB) * S6, room0.height - st.roomScroll * S6);
        c.drawImage(room0, 0, st.roomScroll * S6, VW * S6, hSrc, xr, SB, VW, hSrc / S6);
      }
      // 上の帯（時刻・電波・電池）と、下の横棒
      c.fillStyle = "#0a0a0f"; c.fillRect(0, 0, VW, SB);
      c.fillStyle = "#000"; rr(c, VW / 2 - 62, 11, 124, 36, 18); c.fill();
      c.fillStyle = "rgba(255,255,255,0.96)"; c.font = "700 17px RRSans"; c.textAlign = "left"; c.textBaseline = "middle"; c.fillText(st.clock, 40, 30);
      for (let i = 0; i < 4; i++) { rr(c, 286 + i * 5.2, 35 - (4 + i * 2.4), 3.4, 4 + i * 2.4, 1); c.fill(); }
      c.lineWidth = 1.2; c.strokeStyle = "rgba(255,255,255,0.6)"; rr(c, 326, 23.5, 25, 12.5, 3.6); c.stroke(); rr(c, 328, 25.5, 17, 8.5, 2); c.fill(); rr(c, 352.3, 27.6, 1.8, 4.4, 1); c.fill();
      c.lineCap = "round"; c.strokeStyle = "rgba(255,255,255,0.96)"; c.lineWidth = 1.9;
      for (let i = 0; i < 3; i++) { c.beginPath(); c.arc(314, 35.5, 2.6 + i * 3.2, -Math.PI * 0.76, -Math.PI * 0.24); c.stroke(); }
      c.fillStyle = "rgba(255,255,255,0.75)"; rr(c, VW / 2 - 70, VH - 14, 140, 5, 2.5); c.fill();
      for (const [x, y, p] of st.taps) {                           // 押したところ
        c.fillStyle = `rgba(255,255,255,${(1 - p) * 0.34})`; c.beginPath(); c.arc(x, y, 12 + p * 24, 0, 7); c.fill();
        c.strokeStyle = `rgba(255,255,255,${(1 - p) * 0.7})`; c.lineWidth = 1.6; c.beginPath(); c.arc(x, y, 12 + p * 24, 0, 7); c.stroke();
      }
      if (st.on < 1) { c.fillStyle = `rgba(0,0,0,${1 - st.on})`; c.fillRect(0, 0, VW, VH); }
    }
    c.restore(); scrTex.needsUpdate = true;
  }

  // ───────── カメラ ─────────
  phone.rotation.x = PH.lean; phone.updateMatrixWorld(true);
  const pw = (cx, cy) => phone.localToWorld(scrPoint(cx, cy));
  const nrm = V3(0, 0, 1).applyQuaternion(phone.quaternion);
  const scrMid = pw(195, 422), modalMid = pw(195, 652);
  const rowsMid = pw(195, vy(rects.card[1], SCROLL1) + 92);                                    // 教室カードの1〜2段目
  const weekMid = pw(195, vy(rects.week[1] + rects.week[3] / 2, ROOMSC) - 30);                 // 1週間の表
  const sheetMid = V3(0, 0.15, SHEET_Z - 0.03), paperMid = V3(0, 0, 0.06);
  const off = (p, d, dx = 0, dy = 0) => p.clone().addScaledVector(nrm, d).add(V3(dx, dy, 0));
  const KEYS = [   // t, 位置, 見る先, ピントを合わせる点, ぼけの強さ, その時刻までの進み方（io=ゆっくり始めてゆっくり止まる / lin=等速）
    { t: 0.0, p: V3(0.185, 0.105, 0.330), l: V3(0.0, 0.0, 0.075), f: V3(0.012, 0, 0.075), k: 14 },
    { t: 3.3, p: V3(0.140, 0.135, 0.365), l: V3(0.0, 0.0, 0.070), f: V3(0.012, 0, 0.075), k: 14, e: "lin" },
    { t: 5.0, p: V3(0.030, 0.520, 0.640), l: V3(0.0, 0.0, 0.052), f: paperMid, k: 15 },
    { t: 7.9, p: V3(-0.020, 0.555, 0.615), l: V3(0.0, 0.0, 0.048), f: paperMid, k: 15, e: "lin" },
    { t: 9.8, p: V3(0.050, 0.150, 0.385), l: V3(-0.026, 0.070, -0.135), f: scrMid, k: 26 },
    { t: 11.7, p: V3(0.028, 0.142, 0.320), l: V3(-0.030, 0.072, -0.14), f: scrMid, k: 26, e: "lin" },
    { t: 12.5, p: off(rowsMid, 0.212, 0.006, 0.004), l: rowsMid, f: rowsMid, k: 26 },
    { t: 13.9, p: off(rowsMid, 0.204, 0.004, 0.004), l: rowsMid, f: rowsMid, k: 26, e: "lin" },
    { t: 14.75, p: off(modalMid, 0.215, 0.004, 0.006), l: modalMid, f: modalMid, k: 26 },
    { t: 15.2, p: off(modalMid, 0.212, 0.004, 0.006), l: modalMid, f: modalMid, k: 26, e: "lin" },
    { t: 16.0, p: off(weekMid, 0.212, 0.003, 0.004), l: weekMid, f: weekMid, k: 26 },
    { t: 16.7, p: off(weekMid, 0.206, 0.003, 0.004), l: weekMid, f: weekMid, k: 26, e: "lin" },
    { t: 17.6, p: V3(0.075, 0.105, 0.430), l: V3(0.030, 0.066, -0.125), f: clockFace, k: 22 },
    { t: 18.8, p: V3(0.062, 0.108, 0.405), l: V3(0.026, 0.068, -0.125), f: clockFace, k: 22, e: "lin" },
    { t: 19.5, p: V3(0.048, 0.110, 0.385), l: V3(0.018, 0.070, -0.130), f: scrMid, k: 22 },
    { t: 20.3, p: V3(0.040, 0.112, 0.395), l: V3(0.014, 0.071, -0.130), f: scrMid, k: 22, e: "lin" },
    { t: 22.0, p: V3(0.0, 0.160, 1.035), l: V3(0.0, 0.146, SHEET_Z), f: sheetMid, k: 22 },
    { t: 23.7, p: V3(0.0, 0.160, 0.975), l: V3(0.0, 0.146, SHEET_Z), f: sheetMid, k: 22, e: "lin" },
    { t: 25.4, p: V3(0.0, 0.560, 0.790), l: V3(0.0, 0.0, 0.425), f: V3(0, 0, 0.365), k: 20 },
    { t: 30.0, p: V3(0.0, 0.530, 0.770), l: V3(0.0, 0.0, 0.425), f: V3(0, 0, 0.365), k: 20, e: "lin" },
  ];
  const camState = { p: V3(), l: V3(), f: V3(), k: 20 };
  function evalCamera(t) {
    let i = 0; while (i < KEYS.length - 2 && t >= KEYS[i + 1].t) i++;
    const a = KEYS[i], b = KEYS[i + 1]; let u = seg(t, a.t, b.t); if (b.e !== "lin") u = sss(u);
    camState.p.lerpVectors(a.p, b.p, u); camState.l.lerpVectors(a.l, b.l, u); camState.f.lerpVectors(a.f, b.f, u); camState.k = lerp(a.k, b.k, u);
    if (t > 18.75 && t < 19.6) camState.f.lerpVectors(clockFace, scrMid, sss(seg(t, 18.85, 19.5)));
  }

  // ───────── 後処理（浅いピント → 光のにじみ → 色 → 粒子） ─────────
  const depthTex = new THREE.DepthTexture(rw, rh);
  const rtScene = new THREE.WebGLRenderTarget(rw, rh, { type: THREE.HalfFloatType, samples: Q.has("nomsaa") ? 0 : 4, depthTexture: depthTex });
  const composer = new EffectComposer(renderer);
  const dof = new DofPass(rtScene, rw, rh); composer.addPass(dof);
  const bloom = new UnrealBloomPass(new THREE.Vector2(rw, rh), 0.34, 0.7, 1.0); composer.addPass(bloom);
  composer.addPass(new OutputPass());
  const grade = new ShaderPass(GradeShader); composer.addPass(grade);

  const caps = { cap2: [T.cap2In, T.cap2Out], cap3: [T.cap3In, T.cap3Out], cap4: [T.cap4In, T.cap4Out], cap4b: [T.cap4bIn, T.cap4bOut], cap5: [T.cap5In, T.cap5Out], word: [T.wordIn, 99], notice: [T.noticeIn, 99] };
  const capEl = Object.fromEntries(Object.keys(caps).map((k) => [k, document.getElementById(k)]));

  // ───────── t のときの状態 ─────────
  function update(t) {
    // 輪
    const act = RINGS.map((r) => ({ r, age: t - r.t0 })).filter((x) => x.age >= 0 && x.age * x.r.v < 0.9).slice(-6);
    let tl = 0, tx = 0, tz = 0;
    ringU.uRings.value.forEach((u, i) => {
      const a = act[i]; if (!a) { u.set(0, 0, -1, 0); return; }
      const rad = a.age * a.r.v, s = a.r.s * ss(seg(a.age, 0, 0.25)) * (1 - ss(seg(rad, 0.34, 0.85)));
      u.set(a.r.c[0], a.r.c[1], rad, s);
      const w = s * (1 - ss(seg(rad, 0.0, 0.5))); if (w > tl) { tl = w; tx = a.r.c[0]; tz = a.r.c[1]; }
    });
    tealLight.position.set(tx, 0.07, tz); tealLight.intensity = tl * 0.012; tealLight.visible = !Q.has("lightsoff") || tl > 0.002;

    // 空きコマの札
    const tilesOut = 1 - ss(seg(t, T.phoneDown - 0.4, T.phoneDown + 0.2));
    for (const tl2 of tiles) {
      const p = seg(t, tl2.tOn, tl2.tOn + 0.7), a = ss(p), calm = 1 - 0.55 * ss(seg(t, T.ringToPhone, T.ringToPhone + 1.2));
      const lift = (tl2.hero ? 0.011 : 0.0055) * back(clamp01(p)) * (0.55 + 0.45 * calm);
      const breathe = 1 + 0.06 * Math.sin((t - tl2.tOn) * 2.2 + tl2.g.position.x * 40);
      tl2.g.position.y = 0.0026 + lift; tl2.g.visible = a > 0.001 && tilesOut > 0.001;
      tl2.mat.opacity = a * (tl2.hero ? 0.82 : 0.50) * calm * tilesOut * breathe;
      tl2.em.opacity = a * calm * tilesOut;
      tl2.halo.material.opacity = a * (tl2.hero ? 0.60 : 0.30) * calm * tilesOut * breathe; tl2.halo.visible = tl2.g.visible;
    }

    // スマホ
    const up = back(seg(t, T.phoneUp, T.phoneUpEnd)) * (1 - sss(seg(t, T.phoneDown, T.phoneDown + 0.9)));
    phone.rotation.x = lerp(-Math.PI / 2, PH.lean, up);
    const st = screenState(t); drawScreen(st);
    phone.updateMatrixWorld(true);
    const sp = phone.localToWorld(scrPoint(195, 420)); phoneLight.position.copy(sp).addScaledVector(V3(0, 0, 1).applyQuaternion(phone.quaternion), 0.05); phoneLight.intensity = st.on * 0.035; phoneLight.visible = !Q.has("lightsoff") || st.on > 0.002;

    // 時計（14:40 → 15:10。4限の始まり）
    const min = lerp(40, 70, sss(seg(t, T.clockRun, T.clockEnd)));
    minH.rotation.z = -(min / 60) * Math.PI * 2; hourH.rotation.z = -((2 + min / 60) / 12) * Math.PI * 2;

    // 光の粒
    const so = phone.localToWorld(scrPoint(rects.chips[0] + 58, vy(rects.chips[1], SCROLL1) + 27));
    for (const s of sparks) {
      const a = (t - T.refresh - s.delay) / s.life; s.s.visible = a > 0 && a < 1; if (!s.s.visible) continue;
      const tt = a * s.life; s.s.position.copy(so).add(s.o).addScaledVector(s.d, tt * (1.2 - 0.45 * a)); s.s.position.x += Math.sin(tt * 5 + s.ph) * 0.0022;
      const sc = s.size * (0.6 + 0.9 * Math.sin(Math.PI * Math.min(1, a * 1.6))); s.s.scale.set(sc, sc, 1); s.sm.opacity = Math.sin(Math.PI * a) * 0.95;
    }

    // 紙（起き上がって本のように少し開き、言葉が出る。そのあと元に戻る）
    const rise = sss(seg(t, T.sheetUp, T.sheetUpEnd)) * (1 - sss(seg(t, T.sheetDown, T.sheetDownEnd)));
    sheet.rotation.x = lerp(-Math.PI / 2, -0.16, rise);
    for (const [grp, side] of halves) grp.rotation.y = -side * 0.16 * ss(seg(rise, 0.55, 1));
    const tag = ss(seg(t, T.tagIn, T.tagInEnd)) * (1 - ss(seg(t, T.sheetDownEnd - 0.5, T.sheetDownEnd + 0.4)));
    for (const [m, mat] of tagMats) { mat.opacity = tag; m.visible = tag > 0.001; }
    frontFill.intensity = 2.3 * ss(seg(rise, 0.25, 0.95)); frontFill.visible = !Q.has("lightsoff") || frontFill.intensity > 0.002;

    // ロゴ
    const lg = ss(seg(t, T.logoIn, T.logoIn + 0.9));
    logoMat.opacity = lg; logo.visible = lg > 0.001; logoGlow.material.opacity = lg * 0.20 * (1 + 0.5 * Math.exp(-Math.pow((t - T.ring7 - 0.25) / 0.35, 2))); logoGlow.visible = logo.visible;

    // 文字
    for (const k of Object.keys(caps)) {
      const [a, b] = caps[k], al = ss(seg(t, a, a + 0.45)) * (1 - ss(seg(t, b - 0.4, b)));
      capEl[k].style.opacity = al.toFixed(4); capEl[k].style.transform = `translateY(${((1 - ss(seg(t, a, a + 0.6))) * 16).toFixed(2)}px)`;
    }

    // カメラとピント
    evalCamera(t);
    camera.position.copy(camState.p); camera.lookAt(camState.l); camera.updateMatrixWorld(true);
    dof.params.focus = camState.p.distanceTo(camState.f); dof.params.k = camState.k * 1.9 * PR; dof.params.maxR = 46 * PR;
    dof.params.near = camera.near; dof.params.far = camera.far; dof.params.seed = Math.round(t * FPS) % 64;
    grade.uniforms.uSeed.value = Math.round(t * FPS);
  }
  renderer.shadowMap.autoUpdate = false; let shadowKey = "";
  function renderAt(time) {
    const t = Math.max(0, Math.min(DURATION - 0.5 / FPS, time));
    update(t);
    const sk = `${phone.rotation.x.toFixed(5)}|${sheet.rotation.x.toFixed(5)}|${halves[0][0].rotation.y.toFixed(5)}`;
    if (sk !== shadowKey) { shadowKey = sk; renderer.shadowMap.needsUpdate = true; }
    renderer.setRenderTarget(rtScene); renderer.clear(); renderer.render(scene, camera);
    composer.render();
    renderer.getContext().finish();
    return t;
  }
  window.renderAt = renderAt; window.__rr = { scene, camera, renderer, T, KEYS, DURATION, FPS, composer, dof, bloom, rtScene, update, sun, desk };
  window.addEventListener("hf-seek", (e) => renderAt(e.detail.time));
  renderAt(Number(Q.get("t") || window.__hfThreeTime || 0));
}

window.__hf = window.__hf || {}; window.__hf.buildReady = window.__hf.buildReady || {};
window.__hf.buildReady["rr-desk-3d"] = build().then(() => { window.__ready = true; }).catch((e) => { window.__error = String(e && e.stack || e); console.error(e); throw e; });
