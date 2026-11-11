# 3D 広告の撮影用: 時刻を「水曜 14:40（3限の授業中）」に固定してアプリを起動する（ポート 5057）
import sys, os, datetime
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, REPO); os.chdir(REPO)
_real = datetime.datetime
_JST = datetime.timezone(datetime.timedelta(hours=9))
FIXED = _real(2026, 11, 18, 14, 40, tzinfo=_JST)
class _Fake(_real):
    @classmethod
    def now(cls, tz=None):
        return FIXED.astimezone(tz) if tz else FIXED.replace(tzinfo=None)
datetime.datetime = _Fake
import app
app.app.run(host="127.0.0.1", port=5057)
