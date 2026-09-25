// 教室から探す: 最近見た教室（この端末だけに保存）と、検索画面の年度・学期の引き継ぎ
(function () {
    var KEY = 'rr_recent_rooms';
    var MAX = 6;

    function load() {
        try { return JSON.parse(localStorage.getItem(KEY) || '[]') || []; } catch (e) { return []; }
    }
    function save(list) {
        try { localStorage.setItem(KEY, JSON.stringify(list.slice(0, MAX))); } catch (e) { /* 保存できない環境では何もしない */ }
    }

    // 1週間ページを開いたら記録する
    var here = document.body.getAttribute('data-room');
    if (here) {
        var list = load().filter(function (r) { return r && r.name !== here; });
        list.unshift({ name: here, building: document.body.getAttribute('data-building') || '' });
        save(list);
    }

    var form = document.querySelector('form.room-search');
    if (!form) return;
    var yearInput = form.querySelector('.room-search-year');
    var termInput = form.querySelector('.room-search-term');

    // 空き教室検索の年度・学期を変えたら、教室から探すときもそれに合わせる
    var selYear = document.getElementById('sel-year');
    var selTerm = document.getElementById('sel-term');
    function sync() {
        if (selYear && yearInput) yearInput.value = selYear.value;
        if (selTerm && termInput) termInput.value = selTerm.value;
    }
    if (selYear) selYear.addEventListener('change', sync);
    if (selTerm) selTerm.addEventListener('change', sync);
    sync();

    // 最近見た教室をチップで出す（いま見ている教室は除く）
    var recent = load().filter(function (r) { return r && r.name && r.name !== here; });
    var box = document.getElementById('room-recent');
    if (!box || !recent.length) return;
    var chips = box.querySelector('.room-recent-chips');
    var cls = { 'タワースコラ': 'tower', '駿河台校舎': 'surugadai', '船橋校舎': 'funabashi' };
    recent.forEach(function (r) {
        var a = document.createElement('a');
        a.className = 'room-chip ' + (cls[r.building] || '');
        a.textContent = r.name;
        a.href = '#';
        a.addEventListener('click', function (ev) {
            ev.preventDefault();
            var q = new URLSearchParams();
            if (yearInput && yearInput.value) q.set('year', yearInput.value);
            if (termInput && termInput.value) q.set('term', termInput.value);
            // 教室名に「/」を含むもの（S1704/07/13/16 など）があるので、1文字ずつではなく区切りごとにエンコードする
            location.href = '/room/' + r.name.split('/').map(encodeURIComponent).join('/') + '?' + q.toString();
        });
        chips.appendChild(a);
    });
    box.hidden = false;
})();
