# 3D 広告の撮影用: 時刻を固定してアプリを起動する。 python3 fakeapp.py [時:分] [ポート]
#   既定は 水曜 14:40（3限の授業中）・ポート 5057。場面5（時限が変わる）用に 15:10・5058 でも起動する。
import sys, os, datetime
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, REPO); os.chdir(REPO)
hh, mm = map(int, (sys.argv[1] if len(sys.argv) > 1 else "14:40").split(":")); port = int(sys.argv[2]) if len(sys.argv) > 2 else 5057
_real = datetime.datetime
_JST = datetime.timezone(datetime.timedelta(hours=9))
FIXED = _real(2026, 11, 18, hh, mm, tzinfo=_JST)          # 2026-11-18 は水曜
class _Fake(_real):
    @classmethod
    def now(cls, tz=None):
        return FIXED.astimezone(tz) if tz else FIXED.replace(tzinfo=None)
datetime.datetime = _Fake
import app
app.app.run(host="127.0.0.1", port=port)
