// ── 時計 & 現在時限の自動検出 ──
// 時限の時刻はサーバー（app.py の PERIODS）から受け取る。二重管理しない。
const PERIODS = RR.periods;
const DAYS = ["日","月","火","水","木","金","土"];

function toMin(t) { const [h,m] = t.split(':').map(Number); return h*60+m; }

function updateClock() {
    const now = new Date();
    const jst = new Date(now.toLocaleString('en', {timeZone:'Asia/Tokyo'}));
    const h = String(jst.getHours()).padStart(2,'0');
    const m = String(jst.getMinutes()).padStart(2,'0');
    document.getElementById('clock').textContent = h + ':' + m;

    const cur = h*60 + jst.getMinutes();
    let found = null;
    for (const [p, [s,e]] of Object.entries(PERIODS)) {
        if (cur >= toMin(s) && cur <= toMin(e)) { found = p; break; }
    }
    // 日曜・休み時間・授業の後を言い分ける（2026-11-11 B4。前は日曜でも「○限 授業中」と出ていた）
    let label;
    if (jst.getDay() === 0) label = '本日は授業なし';
    else if (found) label = found + '限 授業中';
    else {
        let next = null;
        for (const [p, [s]] of Object.entries(PERIODS)) { if (cur < toMin(s)) { next = p; break; } }
        label = next ? (next === '1' ? '授業前' : '休み時間') + ' · 次は' + next + '限' : '本日の授業は終了';
    }
    document.getElementById('now-period').textContent = label;
}
setInterval(updateClock, 1000);
updateClock();

// ── ページ読み込み時に現在の曜日・時限をセット（GETのみ） ──
if (!RR.searched) (function() {
    const now = new Date();
    const jst = new Date(now.toLocaleString('en', {timeZone:'Asia/Tokyo'}));
    const dayIdx = jst.getDay(); // 0=日
    const dayName = DAYS[dayIdx === 0 ? 1 : dayIdx]; // 日曜は月に
    const sel = document.getElementById('sel-day');
    for (let i = 0; i < sel.options.length; i++) {
        if (sel.options[i].value === dayName) { sel.selectedIndex = i; break; }
    }
    const cur = jst.getHours()*60 + jst.getMinutes();
    let period = 1;
    for (const [p, [s,e]] of Object.entries(PERIODS)) {
        if (cur >= toMin(s) && cur <= toMin(e)) { period = parseInt(p); break; }
        if (cur < toMin(s)) { period = Math.max(1, parseInt(p)-1); break; }
    }
    document.getElementById('sel-period').value = period;
})();

// ── GA4: 検索イベント計測 ──
(function() {
    const form = document.getElementById('search-form');
    if (!form) return;
    form.addEventListener('submit', function() {
        if (typeof gtag === 'function') {
            gtag('event', 'search', {
                search_day:      document.getElementById('sel-day').value,
                search_period:   document.getElementById('sel-period').value,
                search_building: form.building.value
            });
        }
        // 押した瞬間のローディング表示（更新されることを明示）
        const btn = document.getElementById('btn-search');
        if (btn) {
            btn.classList.add('loading');
            const tx = btn.querySelector('.btn-text');
            if (tx) tx.textContent = '検索中…';
        }
    });
})();

// ── 検索後：結果へスクロール＋強調＋トースト（更新に気づけるように） ──
if (RR.searched && !RR.auto && !RR.error) window.addEventListener('load', function() {
    const meta = document.getElementById('result-meta');
    if (meta) {
        meta.scrollIntoView({ behavior: 'smooth', block: 'center' });
        setTimeout(function() {
            meta.classList.add('flash');
            const chip = document.getElementById('count-chip');
            if (chip) chip.classList.add('pop');
        }, 380);
    }
    showToast('✓ 検索しました — ' + RR.count + '室');
});

// ── 使った目的のワンタップ調査（任意・匿名。1台1日1回まで） ──
// 答えは GA4 に目的ごとのイベント（purpose_study など）として送るだけ。教室名や端末は送らず、サーバーにも残さない。
// 結果は全体の集計（週次の記録・運営用ダッシュボード・学生課への結果報告）にだけ使う（2026-10-25 運営）
(function() {
    const bar = document.getElementById('purpose-bar');
    if (!bar) return;
    const d = new Date();
    const key = 'purpose_asked_' + d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate();
    try { if (localStorage.getItem(key)) return; } catch (e) { /* 保存できない環境でも聞くだけは聞く */ }
    bar.hidden = false;
    function finish(eventName) {
        try { localStorage.setItem(key, '1'); } catch (e) {}
        if (typeof gtag === 'function') {
            gtag('event', eventName, {
                search_day: RR.day, search_period: String(RR.period), search_building: RR.building
            });
        }
    }
    bar.addEventListener('click', function(e) {
        const chip = e.target.closest('[data-purpose]');
        if (chip) {
            finish('purpose_' + chip.dataset.purpose);
            document.getElementById('purpose-chips').hidden = true;
            document.getElementById('purpose-thanks').hidden = false;
            setTimeout(function() { bar.hidden = true; }, 2400);
            return;
        }
        if (e.target.closest('#purpose-close')) {
            finish('purpose_skip');
            bar.hidden = true;
        }
    });
})();

// ── 教室モーダル（その教室の1週間へのリンクと「実は使われていた」の報告） ──
let currentRoom = '', currentBuilding = '';

function openModal(room, building) {
    currentRoom = room;
    currentBuilding = building;
    document.getElementById('modal-title').textContent = room;
    document.getElementById('modal-week').href = window.roomWeekUrl(room, RR.year, RR.term);  // static/rooms.js
    document.getElementById('modal-info').textContent =
        building + ' · ' + RR.day + '曜 ' + RR.period + '限';
    document.getElementById('modal').classList.add('open');
    updateReportButton();
    if (typeof gtag === 'function') gtag('event', 'room_open', { room: room, building: building });   // 2026-11-09 A5
}

// 教室カード（data-room）を押す・Enter で開く。「使用中の可能性」になったカードは開かない
function cardFromEvent(e) {
    const card = e.target.closest && e.target.closest('.room-card[data-room]');
    return card && !card.classList.contains('reported') ? card : null;
}
document.addEventListener('click', function(e) {
    const card = cardFromEvent(e);
    if (card) openModal(card.dataset.room, card.dataset.bldg);
});
document.addEventListener('keydown', function(e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const card = cardFromEvent(e);
    if (card) { e.preventDefault(); openModal(card.dataset.room, card.dataset.bldg); }
});

function closeModal() {
    document.getElementById('modal').classList.remove('open');
}

function handleOverlayClick(e) {
    if (e.target === document.getElementById('modal')) closeModal();
}

// ── 使用中報告 ──
// 報告の中身はサーバーでは時限が終わると消えるので、報告と取り消しの件数を GA4 に残す（全体の集計用）。
// 曜日・時限は検索と同じ名前（search_day・search_period）で送り、GA4 側の追加設定なしで数えられるようにする
function reportEventParams() {
    return { building: currentBuilding, room: currentRoom, search_day: RR.day, search_period: String(RR.period) };
}

async function submitReport() {
    const cancelCode = localStorage.getItem(`report_${currentRoom}_${RR.day}_${RR.period}`);
    
    // すでに報告済みなら取り消し
    if (cancelCode) {
        const res = await fetch('/api/report/cancel', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({room: currentRoom, day: RR.day, period: RR.period, cancel_code: cancelCode})
        });
        const data = await res.json();
        if (data.ok) {
            localStorage.removeItem(`report_${currentRoom}_${RR.day}_${RR.period}`);
            if (typeof gtag === 'function') {
                gtag('event', 'report_cancel', reportEventParams());
            }
            closeModal();
            showToast('✓ 報告を取り消しました');
            setTimeout(refreshResults, 1000);
        }
        return;
    }

    // 新規報告
    const res = await fetch('/api/report', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({room: currentRoom, day: RR.day, period: RR.period})
    });
    const data = await res.json();
    if (!data.ok) {
        showToast(data.error === 'already_reported' ? 'この教室はすでに報告済みです'
                : data.error === 'too_many_reports' ? '1つの時限に報告できるのは3教室までです'
                : data.error === 'rate_limited' ? '操作が続いたため少し待ってからお試しください'
                : '報告できませんでした');
        return;
    }
    if (data.ok) {
        localStorage.setItem(`report_${currentRoom}_${RR.day}_${RR.period}`, data.cancel_code);
        if (typeof gtag === 'function') {
            gtag('event', 'report_room', reportEventParams());
        }
        // 同じ校舎の別の空き教室を3つまで出す（2026-11-11 B6）。無ければ今までどおり一覧に戻る
        const alts = Array.from(document.querySelectorAll('.room-card[data-room]:not(.reported)'))
            .filter(c => c.dataset.bldg === currentBuilding && c.dataset.room !== currentRoom).slice(0, 3);
        const box = document.getElementById('alt-rooms');
        if (box && alts.length) {
            const list = document.getElementById('alt-list');
            list.textContent = '';
            alts.forEach(c => {
                const a = document.createElement('a');
                a.href = window.roomWeekUrl(c.dataset.room, RR.year, RR.term);
                a.textContent = c.dataset.room;
                const span = c.querySelector('.room-span');
                if (span) { const s = document.createElement('small'); s.textContent = span.textContent; a.appendChild(s); }
                a.addEventListener('click', () => { if (typeof gtag === 'function') gtag('event', 'alt_room_click', { building: currentBuilding }); });
                list.appendChild(a);
            });
            document.getElementById('alt-lead').textContent = currentBuilding + 'で、いま空きと出ている教室';
            ['.btn-report', '#report-note', '#modal-week', '#modal .modal-actions'].forEach(q => {
                const el = document.querySelector(q); if (el) el.style.display = 'none';
            });
            box.hidden = false;
            return;
        }
        closeModal();
        showToast('⚠ 報告しました。ありがとうございます！');
        setTimeout(refreshResults, 1000);
    }
}

function updateReportButton() {
    const btn = document.querySelector('.btn-report');
    const note = document.getElementById('report-note');
    if (!btn || !currentRoom) return;
    const cancelCode = localStorage.getItem(`report_${currentRoom}_${RR.day}_${RR.period}`);
    if (cancelCode) {
        btn.textContent = '✓ 報告済み（タップで取り消し）';
        btn.style.background = 'rgba(255,80,80,0.2)';
        if (note) note.textContent = '時限終了後に自動でリセットされます';
    } else {
        btn.textContent = '⚠ 実は使われていた';
        btn.style.background = '';
        if (note) note.textContent = '2件以上の報告で「使用中の可能性」と表示されます';
    }
}

function showToast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.remove('show');
    void t.offsetWidth;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2600);
}

// ── 見た目の切り替え（通常｜🎃｜🎄。2026-11-07 運営）。始まった季節の見た目だけ選べる。選んだものはこの端末に保存し、
//    次に開いたときは templates/_season_boot.html が描画の前に反映する ──
(function() {
    const picker = document.getElementById('theme-picker');
    if (!picker) return;
    const current = picker.dataset.current;                  // いまの時期の季節（日付で決まる）
    const buttons = Array.prototype.slice.call(picker.querySelectorAll('[data-theme]'));
    const themes = buttons.map(function(b) { return b.dataset.theme; }).filter(function(t) { return t !== 'off'; });
    function active() {
        for (let i = 0; i < themes.length; i++) if (document.body.classList.contains('theme-' + themes[i])) return themes[i];
        return 'off';
    }
    function sync() { const a = active(); buttons.forEach(function(b) { b.setAttribute('aria-checked', b.dataset.theme === a ? 'true' : 'false'); }); }
    sync();
    const calm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let busy = false;
    // 切り替えの演出：押したボタンの位置から円が広がって画面を覆い、覆いきった瞬間に見た目を替えて、ふっと晴れる。
    // ハロウィーンはかぼちゃが弾んでコウモリが飛び立ち、クリスマスはツリーが弾んで雪の結晶が舞う。
    // 「視差効果を減らす」設定では演出なしで替える
    function play(theme, btn, apply) {
        if (calm) { apply(); return; }
        const on = theme !== 'off';
        const r = btn.getBoundingClientRect();
        const fx = document.createElement('div');
        fx.className = 'season-fx ' + (on ? 'fx-' + theme : 'fx-normal');
        fx.setAttribute('aria-hidden', 'true');
        fx.style.setProperty('--fx-x', Math.round(r.left + r.width / 2) + 'px');
        fx.style.setProperty('--fx-y', Math.round(r.top + r.height / 2) + 'px');
        const six = ['b1', 'b2', 'b3', 'b4', 'b5', 'b6'];
        if (theme === 'halloween') {
            fx.innerHTML = '<span class="fx-pumpkin">🎃</span>' +
                six.map(function(c) { return '<span class="fx-bat ' + c + '">🦇</span>'; }).join('') +
                '<span class="fx-text">Trick or Room?</span>';
        } else if (theme === 'christmas') {
            fx.innerHTML = '<span class="fx-pop">🎄</span>' +
                six.map(function(c) { return '<span class="fx-flake ' + c + '">❄️</span>'; }).join('') +
                '<span class="fx-text">Merry Christmas!</span>';
        }
        document.body.appendChild(fx);
        setTimeout(apply, 420);                                   // 円が画面を覆ったところで替える
        setTimeout(function() { fx.classList.add('fx-out'); }, on ? 1150 : 560);
        setTimeout(function() { fx.remove(); busy = false; }, on ? 1650 : 1000);
    }
    buttons.forEach(function(btn) {
        btn.addEventListener('click', function() {
            const t = btn.dataset.theme;
            if (busy || t === active()) return;
            busy = !calm;
            buttons.forEach(function(b) { b.setAttribute('aria-checked', b === btn ? 'true' : 'false'); });  // ボタンはすぐ動かす
            // いまの季節を選んだら「季節に合わせる」（次の季節も着せ替え）、前の季節を選んだらその見た目で固定、通常はオフ
            const pref = t === 'off' ? 'off' : (t === current ? 'on' : t);
            try {
                localStorage.setItem('rr_theme', pref);
                localStorage.removeItem('rr_season_on'); localStorage.removeItem('rr_season_off');   // 前の作りの記録
            } catch (e) {}
            if (typeof gtag === 'function') gtag('event', t === 'off' ? 'season_theme_off' : 'season_theme_on', { season: t === 'off' ? current : t });
            play(t, btn, function() {
                themes.forEach(function(n) { document.body.classList.remove('theme-' + n); });
                if (t !== 'off') document.body.classList.add('theme-' + t);
                sync();
            });
        });
    });
})();

// ── 結果の出し直し（2026-11-09 定着の改善 A4） ──
// 報告のあとに結果を取り直す。開いた直後の画面（GET）はそのまま読み直し、検索した結果（POST）は同じ条件で検索し直す
// （location.reload だと POST の画面で「再送信しますか」が出るため）
function refreshResults() {
    const form = document.getElementById('search-form');
    if (RR.auto || !form) location.replace(location.href);
    else form.submit();
}

// いまの（休み時間なら次の）曜日と時限。app.py の upcoming_period と同じ決め方。日曜と授業の後は次の授業日の1限
function currentSlot() {
    const jst = new Date(new Date().toLocaleString('en', {timeZone: 'Asia/Tokyo'}));
    const wd = jst.getDay(), cur = jst.getHours() * 60 + jst.getMinutes();
    let p = null;
    for (const [k, [, e]] of Object.entries(PERIODS)) { if (cur <= toMin(e)) { p = Number(k); break; } }
    if (wd === 0) return '月|1';
    if (p === null) return (wd === 6 ? '月' : DAYS[wd + 1]) + '|1';
    return DAYS[wd] + '|' + p;
}

// 開いたままの画面に戻ったとき、時限が変わっていたら、開いた直後の画面はいまの時限で取り直す。
// 自分で検索した結果は消さずに「この結果は○限のもの」と知らせる
(function() {
    if (!RR.searched || RR.error) return;
    const shown = RR.day + '|' + RR.period;
    const loaded = currentSlot();
    let noticed = false;
    function check() {
        if (document.visibilityState === 'hidden') return;
        const now = currentSlot();
        if (RR.auto) {
            if (now !== shown) {
                if (typeof gtag === 'function') gtag('event', 'stale_refresh', { mode: 'auto' });
                location.replace(location.pathname + location.search);
            }
        } else if (now !== loaded && !noticed) {
            noticed = true;
            const meta = document.getElementById('result-meta');
            if (!meta) return;
            const bar = document.createElement('div');
            bar.className = 'stale-bar';
            bar.innerHTML = 'この結果は <b></b> のものです · <a href="/">いまの空きを見る</a>';
            bar.querySelector('b').textContent = RR.day + '曜 ' + RR.period + '限';
            meta.parentNode.insertBefore(bar, meta);
            if (typeof gtag === 'function') gtag('event', 'stale_refresh', { mode: 'manual_notice' });
        }
    }
    document.addEventListener('visibilitychange', check);
    window.addEventListener('pageshow', function(e) { if (e.persisted) check(); });
})();

// ── 計測（2026-11-09 定着の改善 A5）。結果が出たとき、一覧が最初の画面に入っていたか・ホーム画面から開いたか ──
(function() {
    if (!RR.searched || RR.error || typeof gtag !== 'function') return;
    const first = document.querySelector('.room-card');
    const standalone = (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) || navigator.standalone === true;
    gtag('event', 'results_view', {
        mode: RR.auto ? 'auto' : 'manual',
        in_view: first && first.getBoundingClientRect().top < window.innerHeight ? 'yes' : 'no',
        remembered: RR.remembered ? 'yes' : 'no',
        display: standalone ? 'standalone' : 'browser',
    });
})();

// 目的の質問（何に使う？）は、件数の行のすぐ下・教室の上に置く（テンプレートの位置のまま）。
// 2026-11-11 に最初の校舎の教室のあとへ移したが、2026-11-12 に運営の指示で元の位置に戻した。

// ── 「ホーム画面に追加」の案内（2026-11-11 B2）。2回目に来たときから、閉じるまで出す。ホーム画面から開いているときは出さない ──
(function() {
    const box = document.getElementById('a2hs');
    if (!box || !RR.searched) return;
    const standalone = (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) || navigator.standalone === true;
    let visits = 0, closed = false;
    try {
        const today = new Date().toDateString();
        visits = Number(localStorage.getItem('rr_visits') || 0);
        if (localStorage.getItem('rr_visit_day') !== today) { visits += 1; localStorage.setItem('rr_visits', visits); localStorage.setItem('rr_visit_day', today); }
        closed = localStorage.getItem('rr_a2hs') === 'closed';
    } catch (e) { return; }
    if (standalone || closed || visits < 2) return;
    const ua = navigator.userAgent, ios = /iPhone|iPad|iPod/.test(ua), android = /Android/.test(ua);
    if (!ios && !android) return;                                 // PC には QR の案内を出している
    const inapp = /Instagram|Line\/|FBAN|FBAV/.test(ua);
    document.getElementById('a2hs-how').textContent =
        inapp ? 'まず右上のメニューから「外部ブラウザで開く」。そのあと共有ボタン →「ホーム画面に追加」'
      : ios ? (/CriOS/.test(ua) ? 'アドレスバー右の共有ボタン →「ホーム画面に追加」' : '画面下の共有ボタン →「ホーム画面に追加」')
      : '右上の「︙」→「ホーム画面に追加」';
    box.hidden = false;
    if (typeof gtag === 'function') gtag('event', 'a2hs_shown', { where: inapp ? 'inapp' : ios ? 'ios' : 'android' });
    document.getElementById('a2hs-close').addEventListener('click', function() {
        box.hidden = true;
        try { localStorage.setItem('rr_a2hs', 'closed'); } catch (e) {}
        if (typeof gtag === 'function') gtag('event', 'a2hs_dismiss');
    });
})();
