/* about.html の小さな演出。無くても全部読める（言語切替・計測・3D 模型の読み込みは about.html の中にある）。
   1) 目次：いま読んでいる章に印を付ける  2) 読み上げ用の名前（aria-label）を言語に合わせる
   3) テスト運用の期間のうち、今日がどのあたりかの目印  4) 印刷のときに閉じた details を開く */
(function () {
  'use strict';
  var doc = document;
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function lang() { var c = doc.body.classList; return c.contains('lang-en') ? 'en' : c.contains('lang-zh') ? 'zh' : 'ja'; }

  // ── 1) 目次の現在地 ──
  var list = doc.getElementById('tocList');
  if (list && 'IntersectionObserver' in window) {
    var links = {}, chapters = [], current = null;
    Array.prototype.forEach.call(list.querySelectorAll('a[href^="#"]'), function (a) {
      var sec = doc.getElementById(a.getAttribute('href').slice(1));
      if (sec) { links[sec.id] = a; chapters.push(sec); }
    });
    var setCurrent = function (id) {
      if (id === current) return;
      current = id;
      Object.keys(links).forEach(function (k) {
        if (k === id) links[k].setAttribute('aria-current', 'location'); else links[k].removeAttribute('aria-current');
      });
      // 横に並んでいるとき（スマホ）は、いまの項目が見える位置まで目次だけを横に送る。ページの縦の位置は動かさない
      var a = id && links[id];
      if (a && list.scrollWidth > list.clientWidth + 4) {
        var left = Math.max(0, a.parentNode.offsetLeft - (list.clientWidth - a.offsetWidth) / 2);
        if (list.scrollTo) list.scrollTo({ left: left, behavior: reduce ? 'auto' : 'smooth' }); else list.scrollLeft = left;
      }
    };
    var inBand = {};
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { inBand[e.target.id] = e.isIntersecting; });
      for (var i = 0; i < chapters.length; i++) { if (inBand[chapters[i].id]) { setCurrent(chapters[i].id); return; } }
      // どの章も帯に入っていない: 最初の章より上（表紙）なら印を外す。章と章のすき間では前の印のまま
      if (chapters.length && chapters[0].getBoundingClientRect().top > window.innerHeight * 0.4) setCurrent(null);
    }, { rootMargin: '-30% 0px -60% 0px' });   // 画面の上から3〜4割の帯にかかっている章を「いま読んでいる章」とする
    chapters.forEach(function (s) { io.observe(s); });
  }

  // ── 2) 読み上げ用の名前も言語に合わせる。日本語は HTML に書いたもの、英語・中国語は data-label-en / -zh ──
  var labelled = doc.querySelectorAll('[data-label-en], [data-label-zh]');
  if (labelled.length) {
    Array.prototype.forEach.call(labelled, function (el) { el.setAttribute('data-label-ja', el.getAttribute('aria-label') || ''); });
    var applyLabels = function () {
      var l = lang();
      Array.prototype.forEach.call(labelled, function (el) {
        var v = el.getAttribute('data-label-' + l) || el.getAttribute('data-label-ja');
        if (v) el.setAttribute('aria-label', v);
      });
    };
    applyLabels();
    if ('MutationObserver' in window) new MutationObserver(applyLabels).observe(doc.body, { attributes: true, attributeFilter: ['class'] });
  }

  // ── 3) テスト運用の期間の目印（2026-10-13〜12-19 の予定。期間の外では出さない）──
  var span = doc.getElementById('trialSpan'), fill = doc.getElementById('trialFill'), now = doc.getElementById('trialNow');
  if (span && fill && now) {
    var start = Date.UTC(2026, 9, 13), end = Date.UTC(2026, 11, 19);
    var t = new Date(Date.now() + 9 * 3600000);                       // 日本の日付で数える
    var today = Date.UTC(t.getUTCFullYear(), t.getUTCMonth(), t.getUTCDate());
    if (today >= start && today <= end) {
      var pct = (today - start) / (end - start) * 100;
      fill.style.width = pct + '%';
      now.style.left = pct + '%';
      if (pct < 10) now.classList.add('is-l'); else if (pct > 90) now.classList.add('is-r');
      now.hidden = false; span.hidden = false;
    }
  }

  // ── 4) 印刷するときは、閉じている details（よくある質問・くわしく・それより前の年表）も開いて全部出す。終わったら戻す ──
  window.addEventListener('beforeprint', function () {
    Array.prototype.forEach.call(doc.querySelectorAll('details:not([open])'), function (d) { d.setAttribute('data-pr', '1'); d.open = true; });
  });
  window.addEventListener('afterprint', function () {
    Array.prototype.forEach.call(doc.querySelectorAll('details[data-pr]'), function (d) { d.removeAttribute('data-pr'); d.open = false; });
  });

})();
