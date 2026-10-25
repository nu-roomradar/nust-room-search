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
    document.getElementById('now-period').textContent = found ? found + '限 授業中' : '授業時間外';
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
            setTimeout(() => location.reload(), 1000);
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
        closeModal();
        showToast('⚠ 報告しました。ありがとうございます！');
        setTimeout(() => location.reload(), 1000);
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
