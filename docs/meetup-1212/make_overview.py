"""12/12 自主創造プロジェクト メンバー募集交流会：事前に出す「プロジェクトの概要がわかる資料（1枚）」を作る。
本部 学生部学生課（信夫さん）の依頼（2026-11-27 受信）。提出期限 12/4（金）15:00、ファイル名に所属学部と氏名。
  python3 docs/meetup-1212/make_overview.py <出力フォルダ>
  → 理工学部_二川航大_RoomRadar概要.pdf（A4 横1枚。提出はこれ）・同 .pptx（同じ絵を1枚に貼ったもの）・プレビュー .png
決まり：必須の表記（ルール1）、「予約」「確保」と書かない、船橋を出さない、利用の数字は公開済みのもの（検索数1,000回）だけ、
12/19 のあとも続けるとは書かない（学生課と協議中）。学籍番号・電話番号は入れない。
運営は複数人のチームとして書く（2026-11-27 運営者。公開している開発メンバーは6名・3学部。about.html）。"""
import base64, io, os, sys
import qrcode
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from _browser import find_chrome
from playwright.sync_api import sync_playwright
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
BASE = "理工学部_二川航大_RoomRadar概要"
F = os.path.join(ROOT, "video", "desk-3d", "fonts")
NOTE = "本サービスは、学生が「自主創造プロジェクト」の一環として開発・運営している試験運用中のサービスです。大学が公式に提供するサービスではありません。"

def uri(path_or_img, fmt="PNG"):
    im = path_or_img if isinstance(path_or_img, Image.Image) else Image.open(path_or_img)
    b = io.BytesIO(); (im if im.mode == "RGBA" and fmt == "PNG" else im.convert("RGB")).save(b, fmt); return f"data:image/{fmt.lower()};base64," + base64.b64encode(b.getvalue()).decode()
qr = qrcode.QRCode(border=1, box_size=10); qr.add_data("https://nu-roomradar.github.io/nust-room-search/intro.html"); qr.make(fit=True)
QR = uri(qr.make_image(fill_color="#0b1b3f", back_color="white").get_image())
IGQR = uri(os.path.join(ROOT, "assets", "lp", "instagram-qr.png"))
LOGO = uri(os.path.join(ROOT, "video", "cm-ai", "rr_logo_hd.png"))
SCR = uri(Image.open(os.path.join(ROOT, "video", "xmas-1124", "assets", "s_main_n.png")).resize((780, 1688)))

html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>
@font-face{{font-family:'S';font-weight:400;src:url('file://{F}/NotoSansCJKjp-Regular.otf')}}
@font-face{{font-family:'S';font-weight:500;src:url('file://{F}/NotoSansCJKjp-Medium.otf')}}
@font-face{{font-family:'S';font-weight:700;src:url('file://{F}/NotoSansCJKjp-Bold.otf')}}
@font-face{{font-family:'S';font-weight:900;src:url('file://{F}/NotoSansCJKjp-Black.otf')}}
@font-face{{font-family:'Syne';font-weight:400 800;src:url('file://{F}/Syne-wght.ttf')}}
@page{{size:297mm 210mm;margin:0}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:297mm;height:210mm}}
body{{font-family:'S';color:#14213d;background:#fff;position:relative;overflow:hidden}}
.top{{position:absolute;left:0;right:0;top:0;height:30mm;background:linear-gradient(100deg,#0b1b3f 0%,#13306e 70%,#1d4ed8 100%);color:#fff;display:flex;align-items:center;padding:0 12mm}}
.top img{{height:17mm;margin-right:5mm}}
.top .nm{{font-family:Syne;font-weight:800;font-size:10mm;letter-spacing:-.2mm;line-height:1}}
.top .sub{{margin-left:6mm;padding-left:6mm;border-left:.4mm solid rgba(255,255,255,.35);font-weight:700;font-size:5mm;line-height:1.45}}
.top .sub small{{display:block;font-weight:500;font-size:3.5mm;color:#c7d6f5}}
.top .who{{margin-left:auto;text-align:right;font-weight:500;font-size:3.6mm;line-height:1.55;color:#dbe6fb}}
.top .who b{{display:block;font-weight:700;font-size:5mm;color:#fff}}
.hero{{position:absolute;left:12mm;right:12mm;top:34mm;height:17mm;display:flex;align-items:center;gap:7mm;padding-bottom:3mm;border-bottom:.3mm solid #e2e8f4}}
.hero .tag{{flex:none;font-weight:900;font-size:7.2mm;letter-spacing:.2mm;color:#0b1b3f;line-height:1.25}} .hero .tag span{{color:#1d4ed8}}
.hero .why{{font-size:3.35mm;line-height:1.6;color:#3a455c;padding-left:5mm;border-left:.8mm solid #ffcf99}}
.l{{position:absolute;left:12mm;top:56mm;width:150mm}}
.tiles{{display:flex;gap:3mm;margin:-.6mm 0 4mm}}
.tiles div{{flex:1;background:#f2f6ff;border-radius:3mm;padding:2.2mm 3.4mm 2.4mm;font-size:2.9mm;line-height:1.45;color:#3a455c}}
.tiles b{{display:block;font-weight:900;font-size:7.6mm;line-height:1.2;color:#1d4ed8;white-space:nowrap}} .tiles small{{font-family:'S';font-weight:700;font-size:3.6mm;margin-left:.6mm;color:#0b1b3f}}
.team{{margin-top:3mm;padding:2.6mm 4mm;border-radius:3mm;background:#0b1b3f;color:#dbe6fb;font-size:3.1mm;line-height:1.55}} .team b{{display:block;color:#fff;font-size:3.5mm}}
.blk{{margin-bottom:3.8mm}}
.h{{display:flex;align-items:center;gap:2.4mm;font-weight:900;font-size:5mm;color:#0b1b3f;margin-bottom:1.6mm}}
.h i{{font-style:normal;display:inline-flex;align-items:center;justify-content:center;width:6.4mm;height:6.4mm;border-radius:50%;background:#1d4ed8;color:#fff;font-size:3.4mm;font-weight:700}}
.p{{font-size:3.45mm;line-height:1.62;color:#27324a}}
.p b{{color:#0b1b3f}} .p em{{font-style:normal;background:linear-gradient(transparent 62%,#ffe1b8 62%)}}
ul.p{{list-style:none}} ul.p li{{position:relative;padding-left:4mm}} ul.p li:before{{content:"";position:absolute;left:.6mm;top:2.5mm;width:1.6mm;height:1.6mm;border-radius:50%;background:#1d4ed8}}
.ph{{position:absolute;left:168mm;top:56mm;width:46mm;height:99.5mm;border-radius:7mm;background:#1b1e25;padding:1.6mm}}
.ph img{{width:100%;height:100%;border-radius:5.6mm;object-fit:cover;object-position:top}}
.ph p{{position:absolute;left:0;right:0;top:101.5mm;text-align:center;font-size:2.9mm;color:#5b6478}}
.r{{position:absolute;left:220mm;top:56mm;width:65mm}}
.rec{{background:#f2f6ff;border:.35mm solid #c9d8fb;border-radius:4mm;padding:3.4mm 4.4mm}}
.rec .t{{font-weight:900;font-size:4.7mm;color:#0b1b3f;line-height:1.4}}
.rec .t span{{color:#1d4ed8}}
.rec ul{{list-style:none;margin-top:2.6mm}}
.rec li{{font-size:3.3mm;line-height:1.45;padding:1.2mm 0;border-top:.25mm dashed #c9d8fb}}
.rec li b{{display:block;font-size:3.75mm;color:#0b1b3f}}
.rec .n{{margin-top:2.2mm;font-size:3.3mm;line-height:1.55;color:#27324a}}
.cn{{margin-top:3mm;display:flex;gap:3mm}}
.cn div{{flex:1;text-align:center;font-size:2.9mm;line-height:1.45;color:#27324a}}
.cn img{{width:21mm;height:21mm;display:block;margin:0 auto 1.2mm;border:.3mm solid #dfe6f5;border-radius:2mm;padding:.8mm;background:#fff}}
.cn b{{display:block;font-size:3.2mm;color:#0b1b3f}}
.ft{{position:absolute;left:12mm;right:12mm;bottom:7mm;display:flex;gap:3mm;align-items:flex-start;padding-top:3mm;border-top:.3mm solid #e2e8f4}}
.ft span{{flex:none;font-family:Syne;font-weight:700;font-size:2.8mm;letter-spacing:.5mm;padding:.6mm 1.8mm;border:.3mm solid #b9a595;border-radius:1mm;color:#5b4c40}}
.ft p{{font-size:3.15mm;line-height:1.6;color:#4a5263}}
</style></head><body>
<div class="top"><img src="{LOGO}"><div class="nm">RoomRadar</div>
  <div class="sub">日大理工の空き教室検索<small>自主創造プロジェクト</small></div>
  <div class="who">代表　理工学部 物理学科<b>二川 航大</b></div></div>
<div class="hero"><p class="tag">「開けたら、空いてる」を<span>当たり前に。</span></p>
  <p class="why">空きコマに教室を探して歩き回り、ドアを開けたら授業中。そんな「教室さがしの時間」を減らしたくて、学生のチームで作りました。</p></div>

<div class="l">
  <div class="blk"><div class="h"><i>1</i>どんなプロジェクト？</div>
    <p class="p">時間割をもとに、<b>いま授業のない教室を一覧で出す Web サービス</b>です。登録なし・無料で、スマホで開くだけ。教室ごとの1週間の空きも見られます。企画・開発・周知・運営まで、すべて学生が行っています。</p></div>
  <div class="tiles">
    <div><b>72<small>室</small></b>駿河台キャンパスの<br>対象の教室</div>
    <div><b>1,000<small>回を突破</small></b>検索された回数<br>（11月上旬）</div>
    <div><b>6<small>名・3学部</small></b>統括・開発・会計・広報・CM<br>理工／商／生産工</div>
  </div>
  <div class="blk"><div class="h"><i>2</i>いまの状況</div>
    <ul class="p">
      <li><b>2026年10月13日〜12月19日</b>、理工学部学生課と協議のうえ、駿河台キャンパス（タワー・スコラ／駿河台校舎）で<b>試験運用中</b></li>
      <li>校内のポスター掲示と Instagram で周知しています</li>
      <li>時間割にない授業もあるため、「使う前にドア越しに確認を」と画面とポスターで呼びかけています</li>
    </ul></div>
  <div class="blk"><div class="h"><i>3</i>これからやりたいこと（令和9年度の申請に向けて）</div>
    <ul class="p">
      <li>年度ごとの時間割の取り込みを、手作業から自動に近づける</li>
      <li>使った人の声を聞いて、画面と案内を直していく</li>
      <li>メンバーを増やし、役割ごとに引き継いで続けられる体制にする</li>
    </ul></div>
</div>

<div class="ph"><img src="{SCR}"><p>実際の検索画面</p></div>

<div class="r">
  <div class="rec">
    <div class="t">いっしょに作る<br><span>メンバーを募集中</span></div>
    <ul>
      <li><b>時間割データの取り込み</b>Excel の時間割を読み込む仕組み（Python）</li>
      <li><b>画面づくり</b>HTML・CSS、検索アプリ（Flask）</li>
      <li><b>周知</b>ポスター・Instagram・動画</li>
      <li><b>企画・大学とのやり取り</b>学生課との相談、使う人の声を集める</li>
    </ul>
    <p class="n">学部・学年は問いません。どれか1つでも、少しだけでも歓迎です。</p>
  </div>
  <div class="cn">
    <div><img src="{QR}"><b>2分でわかる紹介</b>紹介ページ</div>
    <div><img src="{IGQR}"><b>Instagram</b>@roomradar_nust</div>
  </div>
</div>

<div class="ft"><span>TEST</span><p>{NOTE}</p></div>
</body></html>"""
tmp = os.path.join(OUT, "_overview.html"); open(tmp, "w", encoding="utf-8").write(html)
pdf, png = os.path.join(OUT, BASE + ".pdf"), os.path.join(OUT, BASE + ".png")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=find_chrome())
    pg = b.new_page(viewport={"width": 1123, "height": 794}, device_scale_factor=3)
    pg.goto("file://" + tmp); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(600)
    pg.screenshot(path=png); b.close()
# PDF は絵にしてから作る（2026-11-27：iPhone の PDF 表示で、スマホの絵の影が灰色の四角になった。見る側のアプリで見え方が変わらないようにする）
Image.open(png).convert("RGB").save(pdf, "PDF", resolution=3369 / 297 * 25.4)
os.remove(tmp)
from pptx import Presentation
from pptx.util import Mm
pr = Presentation(); pr.slide_width, pr.slide_height = Mm(297), Mm(210)
s = pr.slides.add_slide(pr.slide_layouts[6]); s.shapes.add_picture(png, 0, 0, width=pr.slide_width, height=pr.slide_height)
pr.save(os.path.join(OUT, BASE + ".pptx"))
print(pdf)
