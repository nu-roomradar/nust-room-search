# リール撮影用: 時刻を「火曜 10:52（2限の授業中）」に固定してアプリを起動する
import sys, os, datetime
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, REPO); os.chdir(REPO)
_real = datetime.datetime
_JST = datetime.timezone(datetime.timedelta(hours=9))
FIXED = _real(2026, 10, 20, 10, 52, tzinfo=_JST)
class _Fake(_real):
    @classmethod
    def now(cls, tz=None):
        return FIXED.astimezone(tz) if tz else FIXED.replace(tzinfo=None)
datetime.datetime = _Fake
import app
app.app.run(host="127.0.0.1", port=5056)
