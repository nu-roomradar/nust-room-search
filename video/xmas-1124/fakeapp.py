# クリスマスの動画の撮影用：時刻を 2026-12-01（火）に固定してアプリを起動する。 python3 fakeapp.py [時:分] [ポート]
import sys, os, datetime
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, REPO); os.chdir(REPO)
hh, mm = map(int, (sys.argv[1] if len(sys.argv) > 1 else "13:40").split(":")); port = int(sys.argv[2]) if len(sys.argv) > 2 else 5071
_real = datetime.datetime
_JST = datetime.timezone(datetime.timedelta(hours=9))
FIXED = _real(2026, 12, 1, hh, mm, tzinfo=_JST)          # 2026-12-01 は火曜。クリスマスの見た目が既定で出る最初の日
class _Fake(_real):
    @classmethod
    def now(cls, tz=None):
        return FIXED.astimezone(tz) if tz else FIXED.replace(tzinfo=None)
datetime.datetime = _Fake
import app
app.app.run(host="127.0.0.1", port=port)
