// 3D 広告で共通に使う部品（小道具・書体の読み込み・質感の素・浅いピント・色の仕上げ）。
// scene.js（机の上）から同じものを写した。door.js（ポスターとドア）が読み込む。scene.js は書き出し済みの版と揃えるため、そのままにしてある。
import * as THREE from "three";
import { Pass, FullScreenQuad } from "three/addons/postprocessing/Pass.js";

export const TEAL = new THREE.Color(0x4fe3cf);
// ───────── 小道具 ─────────
export const clamp01 = (x) => Math.min(1, Math.max(0, x));
export const seg = (t, a, b) => clamp01((t - a) / (b - a));
export const ss = (x) => x * x * (3 - 2 * x);
export const sss = (x) => x * x * x * (x * (x * 6 - 15) + 10);
export const eo = (x) => 1 - Math.pow(1 - x, 3);
export const back = (x) => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
export const lerp = (a, b, p) => a + (b - a) * p;
export function rnd(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
export const V3 = (x, y, z) => new THREE.Vector3(x, y, z);
export const loadImg = (src) => new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = () => rej(new Error("画像を読めません: " + src)); im.src = src; });
export function mkCanvas(w, h) { const c = document.createElement("canvas"); c.width = w; c.height = h; return c; }
export function texFrom(c, srgb = true) { const t = new THREE.CanvasTexture(c); if (srgb) t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t; }
export function rr(c, x, y, w, h, r) { c.beginPath(); c.roundRect(x, y, w, h, r); }

export async function loadFonts() {
  const defs = [["RRSans", "400", "Regular"], ["RRSans", "500", "Medium"], ["RRSans", "700", "Bold"], ["RRSans", "900", "Black"]];
  for (const [fam, w, n] of defs) { const f = new FontFace(fam, `url(fonts/NotoSansCJKjp-${n}.otf)`, { weight: w }); await f.load(); document.fonts.add(f); }
  const s = new FontFace("Syne", "url(fonts/Syne-wght.ttf)", { weight: "400 800" }); await s.load(); document.fonts.add(s);
}

export function noiseTex(size, seed, rx, ry) {
  const c = mkCanvas(size, size), x = c.getContext("2d"), id = x.createImageData(size, size), r = rnd(seed);
  for (let i = 0; i < id.data.length; i += 4) { const v = r() * 255; id.data[i] = id.data[i + 1] = id.data[i + 2] = v; id.data[i + 3] = 255; }
  x.putImageData(id, 0, 0);
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(rx, ry); return t;
}
export function glowTex() {
  const c = mkCanvas(128, 128), x = c.getContext("2d"), g = x.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(0.25, "rgba(255,255,255,0.55)"); g.addColorStop(0.6, "rgba(255,255,255,0.12)"); g.addColorStop(1, "rgba(255,255,255,0)");
  x.fillStyle = g; x.fillRect(0, 0, 128, 128); return texFrom(c, false);
}
export function cookieTex() {      // 窓の形の光（桟の影つき）。スポットライトに投影する
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
// ───────── 被写界深度（浅いピント）。半分の解像度でぼかして、ピントの合ったところは元の絵のまま重ねる ─────────
export const DOF_COMMON = `
  uniform sampler2D tDepth; uniform float uNear, uFar, uFocus, uK, uMaxR; uniform vec2 uRes; varying vec2 vUv;
  float viewZ(float d) { return (uNear * uFar) / (uFar - d * (uFar - uNear)); }
  float coc(float dist) { return clamp(uK * abs(dist - uFocus) / max(dist, 1e-3), 0.0, uMaxR); }
  float ign(vec2 p) { return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715)))); }`;
export const FS_VERT = `varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;
export class DofPass extends Pass {
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
export const GradeShader = {
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

