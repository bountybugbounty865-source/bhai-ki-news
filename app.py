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
# RSS CACHE
# =====================================================

FEED_CACHE = {}

FEED_LOCK = RLock()

FEED_CACHE_TIME = 300


def fetch_feed(url):

    try:

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "BhaiKiNews/2.0"
            }
        )

        with urllib.request.urlopen(
            req,
            timeout=8
        ) as response:

            content = response.read(2 * 1024 * 1024 + 1)

        if len(content) > 2 * 1024 * 1024:
            raise ValueError("RSS feed too large")

        return feedparser.parse(content)

    except Exception:

        app.logger.exception("RSS feed error")

        return feedparser.parse("")


def get_cached_feed(name, url):

    now = time.time()

    with FEED_LOCK:

        cached = FEED_CACHE.get(name)

        if cached and now - cached["time"] < FEED_CACHE_TIME:

            return cached["feed"]

    feed = fetch_feed(url)

    with FEED_LOCK:

        FEED_CACHE[name] = {
            "time": now,
            "feed": feed
        }

    return feed


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


def get_img(entry, title):

    try:

        media = entry.get("media_content", [])

        if media:

            url = safe_url(
                media[0].get("url", "")
            )

            if url:
                return url

        for link in entry.get("links", []):

            if "image" in link.get("type", ""):

                url = safe_url(
                    link.get("href", "")
                )

                if url:
                    return url

    except Exception:
        pass

    image_hash = hashlib.sha256(
        title.encode("utf-8")
    ).hexdigest()[:20]

    return (
        "https://picsum.photos/seed/"
        + image_hash
        + "/600/400"
    )


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

        img = get_img(entry, title)

        description = clean(
            entry.get("summary", "")
            or entry.get("description", "")
        )

        cards += f"""
        <div class="card">

            <img src="{esc(img)}"
                 alt="{esc(title)}"
                 loading="lazy">

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
        border-radius: 20px;
