// リール3本の共通。時刻 t だけで絵が決まる（render.py が renderAt(t) を1コマずつ呼ぶ）
const NOTE = '本サービスは、学生が「自主創造プロジェクト」の一環として開発・運営している試験運用中のサービスです。大学が公式に提供するサービスではありません。';
function endCard(lead) {
  const d = document.createElement('div'); d.className = 'scene'; d.id = 'end';
  d.innerHTML = `${lead ? `<div class="c" style="top:360px;font-weight:900;font-size:56px;line-height:1.4">${lead}</div>` : ''}
    <img class="logo" src="assets/logo.png" alt="">
    <div class="c name">空き教室検索 <span style="font-family:Syne;font-weight:800">RoomRadar</span></div>
    <div class="pill">プロフィールのリンクから</div>
    <div class="c doornote">使う前に、ドア越しに確認を。</div>
    <div class="note">${NOTE}</div>`;
  document.body.appendChild(d); return d;
}
function addEnd(tl, at, lead) {
  endCard(lead);
  tl.to('#end', { opacity: 1, duration: 0.35 }, at)
    .from('#end .logo', { scale: 0.7, opacity: 0, duration: 0.6, ease: 'back.out(1.6)' }, at + 0.05)
    .from('#end .name', { y: 30, opacity: 0, duration: 0.45 }, at + 0.3)
    .from('#end .pill', { y: 30, opacity: 0, duration: 0.45 }, at + 0.45)
    .from(['#end .doornote', '#end .note'], { opacity: 0, duration: 0.4 }, at + 0.6);
}
function show(tl, sel, at, dur = 0.3) { tl.to(sel, { opacity: 1, duration: dur }, at); }
function hide(tl, sel, at, dur = 0.3) { tl.to(sel, { opacity: 0, duration: dur }, at); }
// 3D の背景（Blender で描いたコマ）を使うページは BG3D を決めておく。renderAt は絵が読み終わるまで待つ
window.renderAt = async t => {
  window.TL.seek(t, false);
  if (window.BG3D) await window.BG3D(t);
};
