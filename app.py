import os
import re
import hmac
import html
import time
import sqlite3
import secrets
import hashlib
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime
from zoneinfo import ZoneInfo
from contextlib import contextmanager

from flask import (
Flask, request, redirect, url_for, session,
abort, render_template_string
)

from werkzeug.middleware.proxy_fix import ProxyFix

# ==========================================
# BHAI KI NEWS - COMPLETE FLASK APPLICATION

# ==========================================

app = Flask(__name__)

app.wsgi_app = ProxyFix(
app.wsgi_app,
x_for=1,
x_proto=1,
x_host=1
)

SECRET_KEY = os.environ.get("SECRET_KEY", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

if len(SECRET_KEY) < 32:
raise RuntimeError(
"SECRET_KEY kam-se-kam 32 characters ka hona chahiye."
)

if len(ADMIN_PASSWORD) < 12:
raise RuntimeError(
"ADMIN_PASSWORD kam-se-kam 12 characters ka hona chahiye."
)

app.secret_key = SECRET_KEY

app.config.update(
SESSION_COOKIE_HTTPONLY=True,
SESSION_COOKIE_SAMESITE="Lax",
SESSION_COOKIE_SECURE=(
os.environ.get("COOKIE_SECURE", "true").lower() == "true"
),
PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
MAX_CONTENT_LENGTH=1 * 1024 * 1024
)

TZ = ZoneInfo("Asia/Kolkata")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = (
"/data"
if os.path.isdir("/data") and os.access("/data", os.W_OK)
else os.path.join(BASE_DIR, "instance")
)

os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "bhai_news.db")

SITE_NAME = "Bhai Ki News"
SITE_TAGLINE = "News • Free Study • GK • Electrical"

=====================================================

DATABASE

=====================================================

@contextmanager
def db():

conn = sqlite3.connect(    
    DB_PATH,    
    timeout=20    
)    

conn.row_factory = sqlite3.Row    

try:    
    conn.execute("PRAGMA journal_mode=WAL")    
    conn.execute("PRAGMA foreign_keys=ON")    

    yield conn    

    conn.commit()    

finally:    
    conn.close()

def init_db():

with db() as con:    

    con.executescript("""    

    CREATE TABLE IF NOT EXISTS articles (    
        id INTEGER PRIMARY KEY AUTOINCREMENT,    
        title TEXT NOT NULL,    
        body TEXT NOT NULL,    
        created_at TEXT NOT NULL    
    );    

    CREATE TABLE IF NOT EXISTS visits (    
        id INTEGER PRIMARY KEY AUTOINCREMENT,    
        visitor_hash TEXT NOT NULL,    
        visited_at TEXT NOT NULL,    
        path TEXT NOT NULL    
    );    

    CREATE INDEX IF NOT EXISTS idx_visits_date    
    ON visits(visited_at);    

    CREATE INDEX IF NOT EXISTS idx_visits_hash    
    ON visits(visitor_hash);    

    CREATE TABLE IF NOT EXISTS login_attempts (    
        attempt_key TEXT PRIMARY KEY,    
        count INTEGER NOT NULL,    
        first_at REAL NOT NULL,    
        blocked_until REAL NOT NULL DEFAULT 0    
    );    

    """)

init_db()

=====================================================

CSRF SECURITY

=====================================================

def csrf_token():

token = session.get("_csrf")    

if not token:    
    token = secrets.token_urlsafe(32)    
    session["_csrf"] = token    

return token

def check_csrf():

sent = request.form.get("_csrf", "")    
saved = session.get("_csrf", "")    

if (    
    not sent    
    or not saved    
    or not hmac.compare_digest(sent, saved)    
):    
    abort(400)

@app.context_processor
def inject_globals():

return {    
    "csrf_token": csrf_token,    
    "site_name": SITE_NAME    
}

=====================================================

SECURITY HEADERS

=====================================================

@app.after_request
def security_headers(response):

response.headers["X-Content-Type-Options"] = "nosniff"    

response.headers["X-Frame-Options"] = "DENY"    

response.headers["Referrer-Policy"] = (    
    "strict-origin-when-cross-origin"    
)    

response.headers["Permissions-Policy"] = (    
    "camera=(), microphone=(), geolocation=()"    
)    

response.headers["Content-Security-Policy"] = (    
    "default-src 'self' https: data:; "    
    "style-src 'self' 'unsafe-inline' https:; "    
    "img-src 'self' https: data:; "    
    "base-uri 'self'; "    
    "form-action 'self'; "    
    "frame-ancestors 'none'"    
)    

if request.is_secure:    

    response.headers["Strict-Transport-Security"] = (    
        "max-age=31536000; includeSubDomains"    
    )    

return response

=====================================================

VISITOR COUNTER

=====================================================

def visitor_hash():

raw = (    
    (request.remote_addr or "")    
    + "|"    
    + request.headers.get("User-Agent", "")[:250]    
)    

return hashlib.sha256(    
    (SECRET_KEY + raw).encode()    
).hexdigest()

def record_visit():

if request.method != "GET":    
    return    

if request.path.startswith(("/static", "/health")):    
    return    

ua = request.headers.get("User-Agent", "").lower()    

if any(    
    bot in ua    
    for bot in ("bot", "spider", "crawler", "slurp")    
):    
    return    

with db() as con:    

    con.execute(    
        """    
        INSERT INTO visits    
        (visitor_hash, visited_at, path)    
        VALUES (?, ?, ?)    
        """,    
        (    
            visitor_hash(),    
            datetime.now(TZ).isoformat(timespec="seconds"),    
            request.path[:250]    
        )    
    )

@app.before_request
def count_visit():

try:    
    record_visit()    

except sqlite3.Error:    

    app.logger.exception(    
        "Visitor counter database error"    
    )

=====================================================

DAILY GK

=====================================================

GK = [

("भारत का संविधान कब लागू हुआ?", "26 जनवरी 1950"),    
("भारत की राजधानी क्या है?", "नई दिल्ली"),    
("उत्तर प्रदेश की राजधानी क्या है?", "लखनऊ"),    
("भारत का राष्ट्रीय जलीय जीव कौन है?", "गंगा डॉल्फिन"),    
("विद्युत धारा की SI इकाई क्या है?", "एम्पियर"),    
("ओम का नियम क्या है?", "V = I × R"),    
("भारत का सबसे बड़ा राज्य कौन-सा है?", "राजस्थान"),    
("सौरमंडल का सबसे बड़ा ग्रह कौन-सा है?", "बृहस्पति"),    
("रक्त पंप करने वाला अंग कौन-सा है?", "हृदय"),    
("पृथ्वी का प्राकृतिक उपग्रह कौन है?", "चंद्रमा"),    
("भारत का राष्ट्रीय पशु कौन है?", "बाघ"),    
("कंप्यूटर का मस्तिष्क किसे कहते हैं?", "CPU"),    
("पानी का रासायनिक सूत्र क्या है?", "H₂O"),    
("पौधे प्रकाश संश्लेषण में कौन-सी गैस लेते हैं?", "कार्बन डाइऑक्साइड"),    
("शिक्षक दिवस कब मनाया जाता है?", "5 सितंबर"),    
("भारत का राष्ट्रीय गान किसने लिखा?", "रवीन्द्रनाथ टैगोर"),    
("विद्युत शक्ति की SI इकाई क्या है?", "वाट"),    
("ट्रांसफॉर्मर किस सिद्धांत पर काम करता है?", "पारस्परिक विद्युत चुंबकीय प्रेरण"),    
("भारत का पहला उपग्रह कौन-सा था?", "आर्यभट्ट"),    
("विश्व पर्यावरण दिवस कब मनाया जाता है?", "5 जून"),    
("भारत का राष्ट्रीय फूल कौन-सा है?", "कमल")

]

=====================================================

ELECTRICAL FORMULAS

=====================================================

FORMULAS = [

("ओम का नियम", "V = I × R"),    
("विद्युत शक्ति", "P = V × I"),    
("विद्युत ऊर्जा", "E = P × t"),    
("प्रतिरोध", "R = V / I"),    
("धारा", "I = Q / t"),    
("आवेश", "Q = I × t"),    
("श्रृंखला प्रतिरोध", "R = R₁ + R₂ + R₃"),    
("समानांतर प्रतिरोध", "R = (R₁ × R₂) / (R₁ + R₂)"),    
("AC आवृत्ति", "f = 1 / T"),    
("कोणीय आवृत्ति", "ω = 2πf"),    
("ट्रांसफॉर्मर टर्न्स अनुपात", "V₁ / V₂ = N₁ / N₂"),    
("ट्रांसफॉर्मर दक्षता", "η = (Output / Input) × 100%"),    
("सिंक्रोनस गति", "Ns = 120f / P"),    
("पावर फैक्टर", "cos φ = P / S"),    
("तीन-फेज शक्ति", "P = √3 × VL × IL × cos φ"),    
("चुंबकीय फ्लक्स", "Φ = B × A"),    
("कैपेसिटेंस", "C = Q / V"),    
("इंडक्टिव रिएक्टेंस", "XL = 2πfL"),    
("कैपेसिटिव रिएक्टेंस", "XC = 1 / (2πfC)"),    
("विद्युत बिल ऊर्जा", "यूनिट = Power (kW) × Time (h)")

]

def daily_item(items):

index = datetime.now(TZ).date().toordinal() % len(items)    

return items[index]

=====================================================

RSS NEWS

=====================================================

RSS_FEEDS = [

(    
    "BBC हिंदी",    
    "https://feeds.bbci.co.uk/hindi/rss.xml"    
),    

(    
    "Google News",    
    "https://news.google.com/rss?hl=hi&gl=IN&ceid=IN:hi"    
)

]

_news_cache = {
"time": 0,
"items": []
}

def fetch_news():

now = time.time()    

if now - _news_cache["time"] < 300:    
    return _news_cache["items"]    

collected = []    

for category, feed_url in RSS_FEEDS:    

    try:    

        req = urllib.request.Request(    
            feed_url,    
            headers={    
                "User-Agent": "BhaiKiNews/1.0"    
            }    
        )    

        with urllib.request.urlopen(    
            req,    
            timeout=7    
        ) as response:    

            raw = response.read(1_000_000)    

        root = ET.fromstring(raw)    

        for item in root.findall(".//item")[:8]:    

            title = item.findtext(    
                "title",    
                default=""    
            ).strip()    

            link = item.findtext(    
                "link",    
                default=""    
            ).strip()    

            pub = item.findtext(    
                "pubDate",    
                default=""    
            ).strip()    

            if (    
                title    
                and link.startswith(("https://", "http://"))    
            ):    

                collected.append({    

                    "category": category,    
                    "title": title[:250],    
                    "link": link,    
                    "date": pub[:100]    

                })    

    except Exception:    

        app.logger.warning(    
            "RSS unavailable: %s",    
            category    
        )    

_news_cache["time"] = now    
_news_cache["items"] = collected    

return collected

=====================================================

WEBSITE DESIGN

=====================================================

CSS = """

* {
box-sizing: border-box;
}


body {
margin: 0;
background: #f3f6fb;
color: #172033;
font-family: Arial, sans-serif;
line-height: 1.6;
}

header {
background: #102a56;
color: white;
padding: 18px 14px;
}

.wrap {
max-width: 1050px;
margin: auto;
padding: 14px;
}

.brand {
font-size: 25px;
font-weight: bold;
}

.tag {
font-size: 13px;
color: #dbeafe;
}

nav {
display: flex;
flex-wrap: wrap;
gap: 8px;
margin-top: 12px;
}

nav a {
color: white;
text-decoration: none;
background: #214578;
padding: 7px 10px;
border-radius: 7px;
font-size: 14px;
}

.box {
background: white;
padding: 17px;
margin: 14px 0;
border-radius: 12px;
box-shadow: 0 2px 9px #0000000c;
}

h1, h2, h3 {
line-height: 1.3;
}

h1 {
font-size: 25px;
}

h2 {
font-size: 21px;
}

.grid {
display: grid;
grid-template-columns: repeat(
auto-fit,
minmax(220px, 1fr)
);
gap: 12px;
}

.card {
border: 1px solid #e4eaf2;
border-radius: 9px;
padding: 12px;
background: white;
overflow-wrap: anywhere;
}

a {
color: #0759b7;
}

input, textarea {
width: 100%;
padding: 11px;
border: 1px solid #bdc9d8;
border-radius: 7px;
margin: 6px 0 12px;
font: inherit;
}

button, .btn {
display: inline-block;
border: 0;
background: #0759b7;
color: white;
padding: 10px 15px;
border-radius: 7px;
text-decoration: none;
cursor: pointer;
font: inherit;
}

.danger {
background: #b42318;
}

.muted {
color: #637083;
font-size: 13px;
}

footer {
text-align: center;
padding: 25px;
color: #657084;
}

.answer {
color: #087443;
font-weight: bold;
}

"""

HEADER = """

<header>    
<div class="wrap">    <div class="brand">📘 Bhai Ki News</div>    <div class="tag">    
News • Free Study • GK • Electrical    
</div>    <nav>    <a href="/">Home</a>
<a href="/news">News</a>
<a href="/gk">Daily GK</a>
<a href="/formulas">Electrical Formulas</a>
<a href="/library">Free Library</a>
<a href="/notes">Notes</a>
<a href="/about">About</a>
<a href="/contact">Contact</a>

</nav>    
</div>    
</header>    """

FOOTER = """

<footer>    © {{ year }} Bhai Ki News · पढ़ें, सीखें और आगे बढ़ें

<br>    <a href="/privacy">Privacy Policy</a>
·
<a href="/admin">Admin</a>

</footer>    """

def page(title, content):

template = """    

<!doctype html>    

<html lang="hi">    

<head>    

<meta charset="utf-8">    

<meta name="viewport"    
content="width=device-width,initial-scale=1">    

<title>{{ title }} | {{ site_name }}</title>    

<meta name="description"    
content="Bhai Ki News पर हिंदी समाचार, GK, Electrical Engineering formulas और free study material पढ़ें।">    

<style>{{ css|safe }}</style>    

</head>    

<body>    

""" + HEADER + """    

<main class="wrap">    

""" + content + """    

</main>    

""" + FOOTER + """    

</body>    
</html>    

"""    

return render_template_string(    

    template,    
    title=title,    
    css=CSS,    
    year=datetime.now(TZ).year,    
    site_name=SITE_NAME    

)

=====================================================

ARTICLE CARDS

=====================================================

def article_cards():

with db() as con:    

    rows = con.execute(    
        "SELECT * FROM articles ORDER BY id DESC LIMIT 20"    
    ).fetchall()    

if not rows:    

    return "<p>अभी कोई नया लेख प्रकाशित नहीं हुआ है।</p>"    

out = ""    

for row in rows:    

    out += (    

        '<div class="card"><h3><a href="/article/'    
        + str(row["id"])    
        + '">'    
        + html.escape(row["title"])    
        + "</a></h3><p class='muted'>"    
        + html.escape(row["created_at"])    
        + "</p><p>"    
        + html.escape(row["body"][:180])    
        + "...</p></div>"    

    )    

return '<div class="grid">' + out + "</div>"

=====================================================

HOME PAGE

=====================================================

@app.route("/")
def home():

question, answer = daily_item(GK)    

formula_name, formula_value = daily_item(FORMULAS)    

news = fetch_news()[:6]    

news_html = ""    

for item in news:    

    news_html += (    

        '<div class="card"><b>'    
        + html.escape(item["category"])    
        + '</b><br><a href="'    
        + html.escape(item["link"], quote=True)    
        + '" target="_blank" rel="noopener noreferrer">'    
        + html.escape(item["title"])    
        + '</a><p class="muted">'    
        + html.escape(item["date"])    
        + "</p></div>"    

    )    

if not news_html:    

    news_html = (    
        "<p>अभी समाचार लोड नहीं हो पाए। "    
        "कुछ देर बाद फिर प्रयास करें।</p>"    
    )    

content = f"""    

<section class="box">    

<h1>स्वागत है Bhai Ki News पर</h1>    

<p>    
यहाँ हिंदी समाचार, सामान्य ज्ञान,    
Electrical Engineering formulas    
और पढ़ाई से जुड़ी सामग्री मिलेगी।    
</p>    

</section>    


<section class="box">    

<h2>🧠 आज का GK प्रश्न</h2>    

<p>{html.escape(question)}</p>    

<p class="answer">    
उत्तर: {html.escape(answer)}    
</p>    

<a class="btn" href="/gk">और GK पढ़ें</a>    

</section>    


<section class="box">    

<h2>⚡ आज का Electrical Formula</h2>    

<p><b>{html.escape(formula_name)}</b></p>    

<p class="answer">    
{html.escape(formula_value)}    
</p>    

<a class="btn" href="/formulas">सभी Formula देखें</a>    

</section>    


<section class="box">    

<h2>📰 ताज़ा समाचार</h2>    

<div class="grid">{news_html}</div>    

<p class="muted">    
समाचार संबंधित RSS स्रोतों से दिखाए जाते हैं।    
मूल खबर के लिए शीर्षक पर क्लिक करें।    
</p>    

</section>    


<section class="box">    

<h2>📚 नए लेख</h2>    

{article_cards()}    

</section>    

"""    

return page("Home", content)

=====================================================

NEWS PAGE

=====================================================

@app.route("/news")
def news_page():

items = fetch_news()    

cards = ""    

for item in items:    

    cards += (    

        '<div class="card"><b>'    
        + html.escape(item["category"])    
        + '</b><h3><a href="'    
        + html.escape(item["link"], quote=True)    
        + '" target="_blank" rel="noopener noreferrer">'    
        + html.escape(item["title"])    
        + '</a></h3><p class="muted">'    
        + html.escape(item["date"])    
        + "</p></div>"    

    )    

return page(    

    "News",    

    '<div class="box"><h1>📰 समाचार</h1>'    
    '<div class="grid">'    
    + (cards or "<p>समाचार अभी उपलब्ध नहीं हैं।</p>")    
    + "</div></div>"    

)

=====================================================

GK PAGE

=====================================================

@app.route("/gk")
def gk_page():

cards = ""    

for i, (q, a) in enumerate(GK, 1):    

    cards += (    

        '<div class="card"><b>'    
        + str(i)    
        + ". "    
        + html.escape(q)    
        + '</b><p class="answer">उत्तर: '    
        + html.escape(a)    
        + "</p></div>"    

    )    

return page(    

    "Daily GK",    

    '<div class="box"><h1>🧠 सामान्य ज्ञान</h1>'    
    '<div class="grid">'    
    + cards    
    + "</div></div>"    

)

=====================================================

FORMULAS PAGE

=====================================================

@app.route("/formulas")
def formulas_page():

cards = ""    

for i, (name, formula) in enumerate(FORMULAS, 1):    

    cards += (    

        '<div class="card"><b>'    
        + str(i)    
        + ". "    
        + html.escape(name)    
        + '</b><p class="answer">'    
        + html.escape(formula)    
        + "</p></div>"    

    )    

return page(    

    "Electrical Formulas",    

    '<div class="box"><h1>⚡ Electrical Engineering Formulas</h1>'    
    '<div class="grid">'    
    + cards    
    + "</div></div>"    

)

=====================================================

FREE LIBRARY

=====================================================

@app.route("/library")
def library_page():

content = """    

<div class="box">    

<h1>📚 Free Library</h1>    

<p>    
यहाँ उपयोगी शैक्षणिक वेबसाइटों के लिंक दिए गए हैं।    
</p>    

<div class="grid">    

<div class="card">    
<h3>NCERT</h3>    
<a href="https://ncert.nic.in/"    
target="_blank" rel="noopener noreferrer">    
Official NCERT Website    
</a>    
</div>    

<div class="card">    
<h3>SWAYAM</h3>    
<a href="https://swayam.gov.in/"    
target="_blank" rel="noopener noreferrer">    
Free Online Courses    
</a>    
</div>    

<div class="card">    
<h3>e-PG Pathshala</h3>    
<a href="https://epgp.inflibnet.ac.in/"    
target="_blank" rel="noopener noreferrer">    
Study Material    
</a>    
</div>    

<div class="card">    
<h3>DIKSHA</h3>    
<a href="https://diksha.gov.in/"    
target="_blank" rel="noopener noreferrer">    
Learning Resources    
</a>    
</div>    

</div>    
</div>    

"""    

return page("Free Library", content)

=====================================================

NOTES

=====================================================

@app.route("/notes")
def notes_page():

return page("Notes", """    

<div class="box">    

<h1>📝 Study Notes</h1>    

<p>    
इस सेक्शन में Electrical Engineering,    
GK और प्रतियोगी परीक्षाओं से जुड़े नोट्स    
प्रकाशित किए जा सकते हैं।    
</p>    

<p>    
नए लेख देखने के लिए    
<a href="/">Home Page</a> par jaayein.</p></div>""")

=====================================================

ARTICLE READ

=====================================================

@app.route("/article/int:article_id")
def article_page(article_id):
with db() as con:
row = con.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
if not row:
abort(404)
content = (
'<div class="box"><h1>' + html.escape(row["title"]) + '</h1><p class="muted">' +
html.escape(row["created_at"]) + '</p><div style="white-space:pre-wrap">' +
html.escape(row[
