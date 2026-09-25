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

// ── 仮予約モーダル ──
let currentRoom = '', currentBuilding = '';

function openModal(room, building) {
    currentRoom = room;
    currentBuilding = building;
    document.getElementById('modal-title').textContent = room;
    const q = new URLSearchParams({term: RR.term});
    if (RR.year) q.set('year', RR.year);
    // 教室名に「/」を含むもの（S1704/07/13/16 など）があるので、区切りごとにエンコードする
    document.getElementById('modal-week').href = '/room/' + room.split('/').map(encodeURIComponent).join('/') + '?' + q;
    document.getElementById('modal-info').textContent =
        building + ' · ' + RR.day + '曜 ' + RR.period + '限';
    document.getElementById('reserve-name').value = '';
    document.getElementById('reserve-note').value = '';
    document.getElementById('modal').classList.add('open');
    updateReserveButton();
    updateReportButton();
}

function closeModal() {
    document.getElementById('modal').classList.remove('open');
}

function handleOverlayClick(e) {
    if (e.target === document.getElementById('modal')) closeModal();
}

async function submitReserve() {
    const name    = document.getElementById('reserve-name').value.trim();
    const purpose = document.getElementById('reserve-note').value.trim();
    if (!name) { showToast('⚠ お名前を入力してください'); return; }

    // すでに予約済みなら取り消し
    const storedCode = localStorage.getItem(`reserve_${currentRoom}_${RR.day}_${RR.period}`);
    if (storedCode) {
        const res = await fetch('/api/reserve/cancel', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({room: currentRoom, day: RR.day, period: RR.period, cancel_code: storedCode})
        });
        const data = await res.json();
        if (data.ok) {
            localStorage.removeItem(`reserve_${currentRoom}_${RR.day}_${RR.period}`);
            closeModal();
            showToast('✓ 仮予約を取り消しました');
            setTimeout(() => location.reload(), 1000);
        }
        return;
    }

    // 新規予約
    const res = await fetch('/api/reserve', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            room: currentRoom, building: currentBuilding,
            day: RR.day, period: RR.period,
            name, purpose
        })
    });
    const data = await res.json();
    if (data.ok) {
        localStorage.setItem(`reserve_${currentRoom}_${RR.day}_${RR.period}`, data.cancel_code);
        if (typeof gtag === 'function') {
            gtag('event', 'reserve_room', { building: currentBuilding, room: currentRoom });
        }
        closeModal();
        showToast('✓ ' + currentRoom + ' を仮予約しました（RoomRadar上のみ）');
        setTimeout(() => location.reload(), 1000);
    } else if (data.error === 'rate_limited') {
        showToast('⚠ しばらく時間をおいて再試行してください');
    }
}

// ── 使用中報告 ──
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
                : data.error === 'rate_limited' ? '操作が続いたため少し待ってからお試しください'
                : '報告できませんでした');
        return;
    }
    if (data.ok) {
        localStorage.setItem(`report_${currentRoom}_${RR.day}_${RR.period}`, data.cancel_code);
        if (typeof gtag === 'function') {
            gtag('event', 'report_room', { building: currentBuilding, room: currentRoom });
        }
        closeModal();
        showToast('⚠ 報告しました。ありがとうございます！');
        setTimeout(() => location.reload(), 1000);
    }
}

function updateReserveButton() {
    const btn  = document.querySelector('.btn-reserve');
    const code = localStorage.getItem(`reserve_${currentRoom}_${RR.day}_${RR.period}`);
    if (!btn) return;
    if (code) {
        btn.textContent = '✓ 予約済み（タップで取り消し）';
        btn.style.background = 'rgba(77,217,160,0.3)';
    } else {
        btn.textContent = '仮予約する';
        btn.style.background = '';
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
