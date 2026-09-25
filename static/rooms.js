// 教室から探す: 1週間ページの URL、最近見た教室（この端末だけに保存）、検索画面の年度・学期の引き継ぎ
(function () {
    var KEY = 'rr_recent_rooms';
    var MAX = 6;
    var CLS = { 'タワースコラ': 'tower', '駿河台校舎': 'surugadai', '船橋校舎': 'funabashi' };

    // 教室の1週間ページの URL。教室名に「/」を含むもの（S1704/07/13/16 など）があるので、区切りごとにエンコードする
    window.roomWeekUrl = function (name, year, term) {
        var q = new URLSearchParams();
        if (year) q.set('year', year);
        if (term) q.set('term', term);
        return '/room/' + String(name).split('/').map(encodeURIComponent).join('/') + '?' + q.toString();
    };

    function load() {
        try {
            var list = JSON.parse(localStorage.getItem(KEY) || '[]');
            // 手で書き換えられた・古い形式の値でも落ちないよう、形の合うものだけ使う
            return Array.isArray(list) ? list.filter(function (r) {
                return r && typeof r.name === 'string' && r.name && r.name.length <= 40;
            }).slice(0, MAX) : [];
        } catch (e) { return []; }
    }
    function save(list) {
        try { localStorage.setItem(KEY, JSON.stringify(list.slice(0, MAX))); } catch (e) { /* 保存できない環境では何もしない */ }
    }

    // 1週間ページを開いたら記録する
    var here = document.body.getAttribute('data-room');
    if (here) {
        var visited = load().filter(function (r) { return r.name !== here; });
        visited.unshift({ name: here, building: document.body.getAttribute('data-building') || '' });
        save(visited);
    }

    // 空き教室検索の画面: 年度・学期を変えたら「教室から1週間を見る」のリンク先もそれに合わせる
    var link = document.getElementById('room-search-link');
    var selYear = document.getElementById('sel-year');
    var selTerm = document.getElementById('sel-term');
    if (link && selYear && selTerm) {
        var syncLink = function () {
            var q = new URLSearchParams({ year: selYear.value, term: selTerm.value });
            link.href = '/room?' + q.toString();
        };
        selYear.addEventListener('change', syncLink);
        selTerm.addEventListener('change', syncLink);
        syncLink();
    }

    // 最近見た教室をチップで出す（いま見ている教室は除く）
    var form = document.querySelector('form.room-search');
    var box = document.getElementById('room-recent');
    if (!form || !box) return;
    var yearInput = form.querySelector('.room-search-year');
    var termInput = form.querySelector('.room-search-term');
    var recent = load().filter(function (r) { return r.name !== here; });
    if (!recent.length) return;
    var chips = box.querySelector('.room-recent-chips');
    recent.forEach(function (r) {
        var a = document.createElement('a');
        a.className = 'room-chip ' + (CLS.hasOwnProperty(r.building) ? CLS[r.building] : '');
        a.textContent = r.name;
        a.href = window.roomWeekUrl(r.name, yearInput && yearInput.value, termInput && termInput.value);
        chips.appendChild(a);
    });
    box.hidden = false;
})();
