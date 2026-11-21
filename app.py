import os
import re
import hmac
import html
import time
import sqlite3
import secrets
import hashlib
import ipaddress
import urllib.parse
import urllib.request
import feedparser

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from threading import RLock
from concurrent.futures import ThreadPoolExecutor

from flask import (
    Flask, request, redirect, session,
    abort, make_response, url_for
)


# =====================================================
# APP CONFIGURATION
# =====================================================

app = Flask(__name__)

SECRET_KEY = os.environ.get("SECRET_KEY", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

if len(SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY must be at least 32 characters!")

if len(ADMIN_PASSWORD) < 12:
    raise RuntimeError("ADMIN_PASSWORD must be at least 12 characters!")

app.secret_key = SECRET_KEY

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    MAX_CONTENT_LENGTH=500 * 1024
)

TZ = ZoneInfo("Asia/Kolkata")

SITE_NAME = "BHAI KI NEWS"

# Render Persistent Disk

if os.path.isdir("/data") and os.access("/data", os.W_OK):
    DATA_DIR = "/data"
else:
    DATA_DIR = "instance"
    os.makedirs(DATA_DIR, exist_ok=True)

DB_FILE = os.path.join(DATA_DIR, "bhai_data.db")

DB_LOCK = RLock()


# =====================================================
# DATABASE
# =====================================================

def get_db():

    conn = sqlite3.connect(
        DB_FILE,
        timeout=20
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    with DB_LOCK:

        conn = get_db()

        try:

            conn.execute("""
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    total INTEGER DEFAULT 0
                )
            """)

            conn.execute("""
                INSERT OR IGNORE INTO stats (id, total)
                VALUES (1, 0)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_visits (
                    day TEXT PRIMARY KEY,
                    visits INTEGER DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS visitor_sessions (
                    visitor_id TEXT,
                    day TEXT,
                    PRIMARY KEY(visitor_id, day)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                article_date_index
                ON articles(created_at)
            """)

            conn.commit()

        finally:
            conn.close()


init_db()


# =====================================================
# DATABASE HELPERS
# =====================================================

def get_stats():

    with DB_LOCK:

        conn = get_db()

        try:

            today = datetime.now(TZ).strftime("%Y-%m-%d")

            total = conn.execute(
                "SELECT total FROM stats WHERE id=1"
            ).fetchone()

            daily = conn.execute(
                "SELECT visits FROM daily_visits WHERE day=?",
                (today,)
            ).fetchone()

            return {
                "total": total["total"] if total else 0,
                "today": daily["visits"] if daily else 0
            }

        finally:
            conn.close()


def get_articles():

    with DB_LOCK:

        conn = get_db()

        try:

            rows = conn.execute("""
                SELECT * FROM articles
                ORDER BY id DESC
            """).fetchall()

            return [dict(row) for row in rows]

        finally:
            conn.close()


def add_article(title, category, content):

    with DB_LOCK:

        conn = get_db()

        try:

            conn.execute("""
                INSERT INTO articles
                (title, category, content, created_at)
                VALUES (?, ?, ?, ?)
            """, (
                title,
                category,
                content,
                datetime.now(TZ).isoformat()
            ))

            conn.commit()

        finally:
            conn.close()


def delete_article(article_id):

    with DB_LOCK:

        conn = get_db()

        try:

            conn.execute(
                "DELETE FROM articles WHERE id=?",
                (article_id,)
            )

            conn.commit()

        finally:
            conn.close()


# =====================================================
# VISITOR COUNTER
# =====================================================

@app.before_request
def count_visitors():

    if request.method != "GET":
        return

    if request.path.startswith("/static"):
        return

    if request.path in ("/health",):
        return

    if request.path.startswith("/admin"):
        return

    today = datetime.now(TZ).strftime("%Y-%m-%d")

    visitor_id = session.get("visitor_id")

    if not visitor_id:

        visitor_id = secrets.token_urlsafe(24)

        session["visitor_id"] = visitor_id

    if session.get("visited_date") == today:
        return

    with DB_LOCK:

        conn = get_db()

        try:

            conn.execute("BEGIN IMMEDIATE")

            cursor = conn.execute("""
                INSERT OR IGNORE INTO visitor_sessions
                (visitor_id, day)
                VALUES (?, ?)
            """, (visitor_id, today))

            if cursor.rowcount:

                conn.execute("""
                    UPDATE stats
                    SET total = total + 1
                    WHERE id=1
                """)

                conn.execute("""
                    INSERT INTO daily_visits(day, visits)
                    VALUES (?, 1)
                    ON CONFLICT(day)
                    DO UPDATE SET visits = visits + 1
                """, (today,))

            conn.commit()

            session["visited_date"] = today

        except Exception:

            conn.rollback()
            app.logger.exception("Visitor counter error")

        finally:
            conn.close()


# =====================================================
# SECURITY HELPERS
# =====================================================

def esc(value):

    return html.escape(
        str(value or ""),
        quote=True
    )


def csrf_token():

    if "_csrf" not in session:

        session["_csrf"] = secrets.token_urlsafe(32)

    return session["_csrf"]


def csrf_input():

    return (
        '<input type="hidden" name="_csrf" value="'
        + esc(csrf_token())
        + '">'
    )


def check_csrf():

    sent = request.form.get("_csrf", "")

    saved = session.get("_csrf", "")

    if not sent or not saved:
        abort(403)

    if not hmac.compare_digest(sent, saved):
        abort(403)


def admin_required():

    return bool(session.get("admin") is True)


def require_admin():

    if not admin_required():

        return redirect(url_for("admin"))

    return None


@app.after_request
def security_headers(response):

    response.headers["X-Content-Type-Options"] = "nosniff"

    response.headers["X-Frame-Options"] = "DENY"

    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )

    response.headers["Content-Security-Policy"] = (
        "default-src 'self' https:; "
        "img-src 'self' https: data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    )

    if request.path.startswith("/admin"):
        response.headers["Cache-Control"] = "no-store"

    return response


# =====================================================
# NEWS FEEDS
# =====================================================

FEEDS = {

    "🔥 Top Khabar":
        "https://news.google.com/rss?hl=hi&gl=IN&ceid=IN:hi",

    "🏏 Cricket":
        "https://news.google.com/rss/search?q=Cricket&hl=hi&gl=IN&ceid=IN:hi",

    "💼 Naukri":
        "https://news.google.com/rss/search?q=Sarkari+Naukri&hl=hi&gl=IN&ceid=IN:hi",

    "📚 Padhai":
        "https://news.google.com/rss/search?q=Exam+Padhai&hl=hi&gl=IN&ceid=IN:hi"

}


# =====================================================
# RSS CACHE WITH RATE LIMIT PROTECTION
# =====================================================

FEED_CACHE = {}
FEED_LOCK = RLock()

# Cache for 15 minutes
FEED_CACHE_TIME = 900


def fetch_feed(url):

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "BhaiKiNews/2.0",
                "Accept": "application/rss+xml, application/xml, text/xml"
            }
        )

        with urllib.request.urlopen(
            req,
            timeout=10
        ) as response:

            content = response.read(
                2 * 1024 * 1024 + 1
            )

        if len(content) > 2 * 1024 * 1024:
            raise ValueError("RSS feed too large")

        return feedparser.parse(content)

    except Exception as e:

        app.logger.warning(
            "RSS fetch failed: %s", str(e)
        )

        return None


def get_cached_feed(name, url):

    now = time.time()

    with FEED_LOCK:

        cached = FEED_CACHE.get(name)

        # Return fresh cache
        if cached and now - cached["time"] < FEED_CACHE_TIME:

            return cached["feed"]

        # Fetch only when cache expires
        feed = fetch_feed(url)

        # Successful fetch
        if feed is not None:

            FEED_CACHE[name] = {
                "time": time.time(),
                "feed": feed
            }

            return feed

        # Keep old news if RSS server fails
        if cached:

            app.logger.warning(
                "Using stale RSS cache: %s", name
            )

            return cached["feed"]

        # No old cache available
        return feedparser.parse("")


# =====================================================
# CONTENT HELPERS
# =====================================================

def clean(text):

    text = re.sub(
        r"<[^>]*>",
        " ",
        str(text or "")
    )

    text = html.unescape(text)

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    if len(text) > 180:

        text = text[:180] + "..."

    return text


def safe_url(url):

    try:

        parsed = urllib.parse.urlsplit(str(url))

        if parsed.scheme not in ("http", "https"):
            return ""

        if not parsed.hostname:
            return ""

        if parsed.username or parsed.password:
            return ""

        hostname = parsed.hostname

        if hostname.lower() == "localhost":
            return ""

        try:

            ip = ipaddress.ip_address(hostname)

            if not ip.is_global:
                return ""

        except ValueError:
            pass

        return str(url)

    except Exception:

        return ""


import re

def get_news_image(entry):
    image_url = ""

    # Kharab photo ko pehchanne ke liye
    bad_words = ['logo', 'placeholder', 'icon', 'avatar', '1x1', 'pixel']

    def is_good_image(url):
        if not url:
            return False
        url_low = url.lower()
        for bad in bad_words:
            if bad in url_low:
                return False
        return True

    # 1. RSS Media Content
    if hasattr(entry, 'media_content'):
        for media in entry.media_content:
            if is_good_image(media.get('url')):
                image_url = media.get('url')
                break

    # 2. RSS Media Thumbnail
    if not image_url and hasattr(entry, 'media_thumbnail'):
        for thumb in entry.media_thumbnail:
            if is_good_image(thumb.get('url')):
                image_url = thumb.get('url')
                break

    # 3. RSS Enclosures
    if not image_url and hasattr(entry, 'enclosures'):
        for enc in entry.enclosures:
            if is_good_image(enc.get('href')) and 'image' in enc.get('type', ''):
                image_url = enc.get('href')
                break

    # 4. Image Links
    if not image_url and hasattr(entry, 'links'):
        for link in entry.links:
            if is_good_image(link.get('href')) and 'image' in link.get('type', ''):
                image_url = link.get('href')
                break

    # 5. Description me Image
    if not image_url:
        desc = entry.get('description', '') or entry.get('summary', '')
        match = re.search(r'<img[^>]+src=["\'](.*?)["\']', desc)
        if match and is_good_image(match.group(1)):
            image_url = match.group(1)

    return image_url
def make_cards(feed, seen, limit=15):

    cards = ""

    count = 0

    for entry in getattr(feed, "entries", []):

        if count >= limit:
            break

        title = clean(
            entry.get("title", "")
        )

        link = safe_url(
            entry.get("link", "")
        )

        if not title or not link:
            continue

        if title in seen or link in seen:
            continue

        seen.add(title)
        seen.add(link)


    img = get_news_image(entry)
    print("IMAGE DEBUG:", title, img)  
    image_html = (
            f'<img src="{esc(img)}" alt="{esc(title)}" loading="lazy">'
            if img else ""
        )

        description = clean(
            entry.get("summary", "")
            or entry.get("description", "")
        )

        cards += f"""
        <div class="card">
            {image_html}
            <h3>{esc(title)}</h3>
            <p>{esc(description)}</p>
            <a href="{esc(link)}"
               target="_blank"
               rel="noopener noreferrer">
               Poori Khabar Padhein
            </a>
        </div>
        """

        count += 1

    return cards


# =====================================================
# GK
# =====================================================

GK_LIST = [

    ("Lal Kila kaha hai?", "Delhi me"),

    ("Taj Mahal kaha hai?", "Agra me"),

    ("Aasman Neela kyu hai?",
     "Neeli roshni ka prakirnan zyada hota hai"),

    ("23 x 11 = ?", "253"),

    ("Bharat ka Rashtriya Pashu kaun hai?", "Bagh"),

    ("Bharat ki Rajdhani kya hai?", "New Delhi"),

    ("Bharat ka Rashtriya Pakshi kaunsa hai?", "Mor"),

    ("Ganga Nadi ka udgam kahan hai?",
     "Gangotri Glacier ke paas"),

    ("Bharat ka sabse bada Rajya kaunsa hai?",
     "Rajasthan"),

    ("Computer ka Pita kise kehte hain?",
     "Charles Babbage"),

    ("Bharat ke Pehle Rashtrapati kaun the?",
     "Dr. Rajendra Prasad"),

    ("UP ki Rajdhani kya hai?", "Lucknow"),

    ("Qutub Minar kaha hai?", "Delhi me"),

    ("Bharat ka Rashtriya Phool kaunsa hai?", "Kamal"),

    ("Bharat ka Rashtriya Khel kaunsa hai?",
     "Bharat ka koi adhikarik rashtriya khel nahi hai"),

    ("Mahatma Gandhi ka janm kab hua?",
     "2 October 1869"),

    ("Bharat ko Azadi kab mili?",
     "15 August 1947"),

    ("Bharat ka Samvidhan kab lagu hua?",
     "26 January 1950"),

    ("Bharat ki sabse lambi nadi kaunsi hai?",
     "Ganga"),

    ("Ashok Chakra me kitni teeliya hoti hain?",
     "24"),

    ("Bharat ka Rashtriya Gaan kaunsa hai?",
     "Jana Gana Mana"),

    ("Jana Gana Mana kisne likha?",
     "Rabindranath Tagore"),

    ("Lucknow kis nadi ke kinare hai?",
     "Gomti Nadi"),

    ("Bharat me kitne Rajya hain?",
     "28 Rajya aur 8 Kendra Shasit Pradesh"),

    ("Chand par pehla kadam kisne rakha?",
     "Neil Armstrong"),

    ("Bharat ke Pehle Pradhan Mantri kaun the?",
     "Jawaharlal Nehru"),

    ("Bharat ka Pehla Upgrah kaunsa tha?",
     "Aryabhata"),

    ("1 Minute me kitne Second hote hain?",
     "60 Second")

]


# =====================================================
# FORMULAS
# =====================================================

FORMULAS = [

    ("(a+b)²", "a² + 2ab + b²"),

    ("Circle Area", "πr²"),

    ("Speed", "Distance / Time"),

    ("Ohm's Law", "V = I × R"),

    ("Electrical Power", "P = V × I"),

    ("Resistance", "R = V / I"),

    ("Current", "I = V / R"),

    ("Electrical Energy", "E = P × t"),

    ("Frequency", "f = 1 / T"),

    ("Power Factor", "cos φ"),

    ("Series Resistance", "R = R1 + R2"),

    ("Parallel Resistance",
     "1/R = 1/R1 + 1/R2")

]


# =====================================================
# AUTOMATIC NOTES
# =====================================================

AUTO_NOTES = [

    {
        "title": "Aaj Ka GK - Bharat Ki Rajdhani",
        "cat": "GK",
        "content": "Bharat ki Rajdhani New Delhi hai."
    },

    {
        "title": "Aaj Ka Vocab - 5 New Words",
        "cat": "English",
        "content": "Brave = Bahadur, Honest = Imaandaar, Quick = Tez, Happy = Khush, Strong = Mazboot."
    },

    {
        "title": "Aaj Ka Formula - Ganit",
        "cat": "Maths",
        "content": "(a+b)² = a² + 2ab + b²."
    },

    {
        "title": "Aaj Ka Computer - CPU",
        "cat": "Computer",
        "content": "CPU ka full form Central Processing Unit hai."
    },

    {
        "title": "Aaj Ka SST - Mughal Kal",
        "cat": "SST",
        "content": "Akbar Mughal Samrajya ka ek pramukh shasak tha."
    },

    {
        "title": "Aaj Ka Current Affairs",
        "cat": "GK",
        "content": "Current Affairs ke liye bharosemand news sources padhein."
    },

    {
        "title": "Aaj Ka Motivation",
        "cat": "Motivation",
        "content": "Roj thoda-thoda padhna bhi achhi progress hai."
    }

]


def get_today_note():

    articles = get_articles()

    if articles:

        note = articles[0]

        return {
            "title": note["title"],
            "cat": note["category"],
            "content": note["content"],
            "type": "Tera Wala"
        }

    day = datetime.now(TZ).timetuple().tm_yday

    note = AUTO_NOTES[day % len(AUTO_NOTES)]

    return {
        "title": note["title"],
        "cat": note["cat"],
        "content": note["content"],
        "type": "Automatic"
    }


# =====================================================
# LIBRARY
# =====================================================

LIBRARY = {

    "📚 NCERT Books": [

        ("Class 10 Maths", "https://ncert.nic.in/"),

        ("Class 10 Science", "https://ncert.nic.in/"),

        ("Class 10 English", "https://ncert.nic.in/")

    ],

    "📝 Previous Paper": [

        ("UP Board Paper", "https://upmsp.edu.in/"),

        ("CBSE Paper", "https://cbse.gov.in/")

    ],

    "📖 English Grammar": [

        ("Tense Notes", "https://ncert.nic.in/"),

        ("Active Passive", "https://ncert.nic.in/"),

        ("Letter Writing", "https://ncert.nic.in/")

    ],

    "💻 Computer": [

        ("Computer Kya Hai?", "https://ncert.nic.in/"),

        ("MS Word / Excel", "https://ncert.nic.in/"),

        ("Internet Aur Email", "https://ncert.nic.in/")

    ],

    "🌍 SST": [

        ("Bharat Ka Itihas", "https://ncert.nic.in/"),

        ("Bharat Ka Bhugol", "https://ncert.nic.in/"),

        ("Samvidhan", "https://ncert.nic.in/")

    ],

    "🧠 Daily GK + Formula": [

        ("Aaj Ka GK", "/gk"),

        ("Maths Formula", "/gk"),

        ("Science Formula", "/gk")

    ],

    "💼 Sarkari Naukri": [

        ("UP Police", "https://uppbpb.gov.in/"),

        ("SSC", "https://ssc.gov.in/"),

        ("Railway", "https://rrbapply.gov.in/")

    ]

}


# =====================================================
# ARTICLES
# =====================================================

MY_NEW_ARTICLES = [

    (
        "Math - 11 se Guna Trick",
        "Math",
        "23 x 11 = 253. 2 aur 3 ko alag karo, beech me 2+3=5 daal do!"
    ),

    (
        "Science - Aasman Neela Kyu?",
        "Science",
        "Suraj ki roshni me kai rang hote hain. Vayumandal me neeli roshni ka prakirnan zyada hota hai."
    ),

    (
        "Hindi - Mera Gaon Nibandh",
        "Hindi",
        "Mera gaon mera garv hai. Yaha ke log ek dusre ki madad karte hain."
    ),

    (
        "Mehnat Kabhi Bekar Nahi Jaati",
        "Article",
        "Mehnat aur lagan se seekhna jari rakho!"
    )

]


# =====================================================
# DESIGN
# =====================================================

def style():

    return """
    <style>

    * {
        box-sizing: border-box;
    }

    body {
        font-family: Arial, sans-serif;
        background: #f2f2f2;
        margin: 0;
        color: #222;
    }

    .header {
        background: #d60000;
        color: white;
        padding: 20px;
        text-align: center;
    }

    .header h1 {
        margin: 0;
        font-size: 32px;
    }

    .live {
        background: yellow;
        color: black;
        padding: 3px 10px;
        border-radius: 20px;
        font-weight: bold;
    }

    .nav {
        display: flex;
        gap: 8px;
        justify-content: center;
        flex-wrap: wrap;
        margin-top: 15px;
    }

    .nav a {
        background: white;
        color: #d60000;
        padding: 9px 14px;
        border-radius: 20px;        text-decoration: none;
        font-weight: bold;
    }

    .search-box {
        padding: 15px;
        background: white;
        position: sticky;
        top: 0;
        z-index: 9;
    }

    .search-row {
        display: flex;
        gap: 10px;
    }

    .search-row input {
        flex: 1;
        padding: 12px;
        font-size: 16px;
        border: 2px solid #d60000;
        border-radius: 25px;
    }

    .search-row button {
        background: #d60000;
        color: white;
        border: none;
        padding: 12px 20px;
        border-radius: 25px;
        font-weight: bold;
    }

    h2 {
        padding: 0 15px;
        color: #d60000;
    }

    .grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 15px;
        padding: 0 15px 20px;
    }

    .card {
        background: white;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 2px 8px #ccc;
    }

    .card img {
        width: 100%;
        height: 180px;
        object-fit: cover;
    }

  .card h3 {
    font-size: 19px;
    font-weight: 800;
    line-height: 1.5;
    margin: 12px;
    color: #222;
}  

    .card p {
        font-size: 14px;
        color: #555;
        margin: 0 12px 10px;
    }

    .card a {
        display: block;
        color: #d60000;
        font-weight: bold;
        padding: 0 12px 12px;
        text-decoration: none;
    }

    .box {
        background: white;
        margin: 15px;
        padding: 20px;
        border-radius: 12px;
    }
.box h3 {
    font-size: 22px;
    font-weight: 800;
    line-height: 1.5;
    color: #b71c1c;
    margin: 12px 0;
}

.box h2 {
    font-size: 22px;
    font-weight: 800;
}
    .footer {
        text-align: center;
        padding: 20px;
        color: gray;
    }

    .footer a {
        color: #d60000;
        text-decoration: none;
        font-weight: bold;
        margin: 0 8px;
    }

    input, textarea {
        width: 100%;
        padding: 12px;
        margin: 8px 0;
        border: 2px solid #ddd;
        border-radius: 10px;
        font-size: 16px;
    }

    .btn {
        background: #d60000;
        color: white;
        border: none;
        padding: 13px;
        border-radius: 10px;
        width: 100%;
        font-weight: bold;
        font-size: 16px;
        cursor: pointer;
    }

    @media(max-width: 600px) {
        .grid { grid-template-columns: 1fr; }
        .header h1 { font-size: 27px; }
    }

    </style>
    """

def header():

    s = get_stats()

    return f"""
    <div class="header">
        <h1>{SITE_NAME}</h1>
        <p><span class="live">LIVE</span> Sirf Kaam Ki Khabar + Free Padhai</p>
        <p>Made by Priyanshu Singh | Lucknow</p>
        <p style="background:black;color:white;display:inline-block;padding:5px 12px;border-radius:20px;font-size:13px">
        Aaj Aaye: {s["today"]} | Total: {s["total"]}</p>
        <div class="nav">
            <a href="/">News</a>
            <a href="/library">Padhai Library</a>
            <a href="/gk">GK</a>
            <a href="/about">About</a>
            <a href="/admin">Admin</a>
        </div>
    </div>
    """

def footer():

    return """
    <div class="footer">
        <a href="/">Home</a>
        <a href="/library">Library</a>
        <a href="/gk">GK</a>
        <a href="/about">About</a>
        <p>© BHAI KI NEWS | Made by Priyanshu Singh</p>
    </div>
    """

def page(title, body):

    return f"""<!doctype html>
    <html lang="hi">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>{esc(title)} | {SITE_NAME}</title>
        {style()}
    </head>
    <body>
        {header()}
        <main>{body}</main>
        {footer()}
    </body>
    </html>
    """

def search_box():

    return """
    <div class="search-box">
        <form action="/search" method="get">
            <div class="search-row">
                <input type="text" name="q" placeholder="Khabar search karo..." required>
                <button type="submit">Search</button>
            </div>
        </form>
        <div style="margin-top:10px">
            <a href="/?cat=Top">🔥 Top</a> &nbsp;
            <a href="/?cat=Cricket">🏏 Cricket</a> &nbsp;
            <a href="/?cat=Naukri">💼 Naukri</a> &nbsp;
            <a href="/?cat=Padhai">📚 Padhai</a>
        </div>
    </div>
    """

@app.route("/")
def home():

    cat = request.args.get("cat", "")
    seen = set()
    cards = ""

    if cat:
        for name, url in FEEDS.items():
            if cat.lower() in name.lower():
                cards += make_cards(get_cached_feed(name, url), seen, limit=20)
    else:
        with ThreadPoolExecutor(max_workers=4) as ex:
            fut = {n: ex.submit(get_cached_feed, n, u) for n, u in FEEDS.items()}
            for n in FEEDS:
                try:
                    cards += make_cards(fut[n].result(), seen, limit=10)
                except Exception:
                    pass

    note = get_today_note()
    arts = get_articles()

    my = ""
    for a in arts[:6]:
        my += f'<div class="card"><h3>{esc(a["title"])}</h3><p>{esc(a["category"])}</p><p>{esc(a["content"][:180])}</p></div>'

    if not my:
        for t, c, txt in MY_NEW_ARTICLES:
            my += f'<div class="card"><h3>{esc(t)}</h3><p>{esc(c)}</p><p>{esc(txt)}</p></div>'

    body = f"""
    {search_box()}
    <div class="box">
        <h2>📝 Aaj Ka Note - {esc(note["type"])}</h2>
        <h3>{esc(note["title"])}</h3>
        <p>{esc(note["content"])}</p>
    </div>
    <h2>✍️ Mere Articles</h2>
    <div class="grid">{my}</div>
    <h2>📰 Taaza Khabar</h2>
    <div class="grid">{cards or "<p>Abhi khabar load nahi hui</p>"}</div>
    """

    return page("Home", body)

@app.route("/search")
def search():

    q = request.args.get("q", "").strip()

    if not q:
        return redirect(url_for("home"))

    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=hi&gl=IN&ceid=IN:hi"
    cards = make_cards(get_cached_feed("search", url), set(), limit=20)

    body = f"""
    {search_box()}
    <h2>🔍 Search: {esc(q)}</h2>
    <div class="grid">{cards or "<p>Kuch nahi mila</p>"}</div>
    """

    return page("Search", body)

@app.route("/gk")
def gk():

    gk_html = ""
    for q, a in GK_LIST:
        gk_html += f'<div class="card"><h3>{esc(q)}</h3><p><b>Uttar:</b> {esc(a)}</p></div>'

    f_html = ""
    for n, f in FORMULAS:
        f_html += f'<div class="card"><h3>{esc(n)}</h3><p><b>{esc(f)}</b></p></div>'

    body = f"""
    <h2>🧠 Daily GK</h2>
    <div class="grid">{gk_html}</div>
    <h2>⚡ Formulas</h2>
    <div class="grid">{f_html}</div>
    """

    return page("GK + Formula", body)

@app.route("/library")
def library():

    out = '<h2>📚 Padhai Library</h2>'

    for cat, items in LIBRARY.items():
        out += f"<h2>{esc(cat)}</h2><div class='grid'>"
        for title, link in items:
            out += f'<div class="card"><h3>{esc(title)}</h3><a href="{esc(link)}" target="_blank" rel="noopener noreferrer">Open</a></div>'
        out += "</div>"

    return page("Library", out)

@app.route("/about")
def about():

    return page("About", """
    <div class="box">
        <h2>About Bhai Ki News</h2>
        <p>Bhai Ki News - Sirf kaam ki khabar + Free Padhai. Made by Priyanshu Singh, Lucknow.</p>
        <p>Yaha Top Khabar, Cricket, Naukri, Padhai, Daily GK aur Formulas milte hai.</p>
    </div>
    """)

@app.route("/health")
def health():

    return "OK", 200

@app.route("/admin", methods=["GET", "POST"])
def admin():

    if request.method == "POST":

        check_csrf()

        pw = request.form.get("password", "")

        if pw == ADMIN_PASSWORD:
            session["admin"] = True
            session.permanent = True
            return redirect(url_for("admin"))

        return page("Admin", f"""
        <div class="box">
            <p>Galat password!</p>
            <form method="post">{csrf_input()}
            <input type="password" name="password" placeholder="Admin Password" required>
            <button class="btn" type="submit">Login</button></form>
        </div>
        """)

    if not admin_required():

        return page("Admin Login", f"""
        <div class="box">
            <h2>Admin Login</h2>
            <form method="post">{csrf_input()}
            <input type="password" name="password" placeholder="Admin Password" required>
            <button class="btn" type="submit">Login</button></form>
        </div>
        """)

    arts = get_articles()
    st = get_stats()

    rows = ""
    for a in arts:
        rows += f'<div class="box"><b>{esc(a["title"])}</b> - {esc(a["category"])}<form method="post" action="/admin/delete/{a["id"]}">{csrf_input()}<button class="btn" type="submit">Delete</button></form></div>'

    body = f"""
    <div class="box">
        <h2>Admin Panel</h2>
        <p>Total: {st["total"]} | Aaj: {st["today"]}</p>
        <form method="post" action="/admin/add">{csrf_input()}
        <input name="title" placeholder="Title" required>
        <input name="category" placeholder="Category" required>
        <textarea name="content" placeholder="Content" required></textarea>
        <button class="btn" type="submit">Add Article</button></form>
        <p><a href="/admin/logout">Logout</a></p>
    </div>
    <h2>Mere Articles</h2>
    {rows or "<div class=box>Koi article nahi hai.</div>"}
    """

    return page("Admin", body)

@app.route("/admin/add", methods=["POST"])
def admin_add():

    if not admin_required():
        return redirect(url_for("admin"))

    check_csrf()

    t = request.form.get("title", "").strip()[:200]
    c = request.form.get("category", "").strip()[:100]
    co = request.form.get("content", "").strip()[:5000]

    if t and co:
        add_article(t, c or "General", co)

    return redirect(url_for("admin"))

@app.route("/admin/delete/<int:article_id>", methods=["POST"])
def admin_delete(article_id):

    if not admin_required():
        return redirect(url_for("admin"))

    check_csrf()
    delete_article(article_id)

    return redirect(url_for("admin"))

@app.route("/admin/logout")
def admin_logout():

    session.pop("admin", None)

    return redirect(url_for("admin"))

@app.errorhandler(404)
def not_found(e):

    return page("Not Found", '<div class="box"><h2>Page nahi mila</h2><p><a href="/">Home pe wapas jao</a></p></div>'), 404

@app.errorhandler(403)
def forbidden(e):

    return page("Forbidden", '<div class="box"><h2>Galat request</h2><p><a href="/">Home pe wapas jao</a></p></div>'), 403

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))# ===== ADMIN FIX - PURANE WALE KO OVERRIDE KAREGA =====
from flask import session as _session

@app.route('/admin', methods=['GET', 'POST'])
def admin_fixed():
    if request.method == 'POST':
        pw = request.form.get('password', '')
        if pw == ADMIN_PASSWORD:
            session['admin'] = True
            session['admin_logged_in'] = True
            return redirect('/admin/dashboard')
        return "Wrong Password! <a href='/admin'>Wapas Jao</a>"
    return '''
    <h2>Bhai Ki News - Admin Login</h2>
    <form method="POST">
    <input type="password" name="password" placeholder="Admin Password" required>
    <br><br><button type="submit">Login</button>
    </form>
    '''

@app.route('/admin/dashboard')
def admin_dashboard_fixed():
    if not session.get('admin'):
        return redirect('/admin')
    return '<h2>Admin Dashboard Khul Gaya! 🎉</h2><p>Ab kaam karega.</p><a href="/">Home</a>'
