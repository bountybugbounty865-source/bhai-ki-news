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
import html
import time
import socket
import ssl
import io
import warnings
import ipaddress
import threading
import http.client
from urllib.parse import urljoin, urlsplit
from html.parser import HTMLParser

try:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 25000000
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

_LOCK = threading.Lock()
_OG_CACHE = {}
_OG_TTL = 3600
_OG_EMPTY_TTL = 300
_OG_MAX = 500
_IMG_CHECK_CACHE = {}
_IMG_TTL = 3600
_IMG_MAX = 1000
_DNS_CACHE = {}
_DNS_TTL = 60
_DNS_EMPTY_TTL = 5
_MAX_CANDIDATES = 15
_MAX_PIXELS = 25000000
_CHUNK = 32768
_DNS_SEM = threading.Semaphore(20)

class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.og = ""
        self.twitter = ""
    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        d = {k.lower(): v for k, v in attrs}
        prop = str(d.get("property") or d.get("name") or "").strip().lower()
        content = str(d.get("content") or "").strip()
        if not content:
            return
        if prop in ("og:image", "og:image:url") and not self.og:
            self.og = content.strip()
        elif prop in ("twitter:image", "twitter:image:src") and not self.twitter:
            self.twitter = content.strip()

def _clean_mime(raw):
    return raw.split(";", 1)[0].strip().lower()

def _resolve_ips(host):
    host = host.rstrip(".").lower()
    try:
        ip = ipaddress.ip_address(host)
        return {str(ip)}
    except ValueError:
        pass
    now = time.time()
    with _LOCK:
        if host in _DNS_CACHE:
            ips, t, ttl = _DNS_CACHE[host]
            if now - t < ttl:
                return set(ips)
    try:
        infos = socket.getaddrinfo(host, None)
        ips = set(info[4][0] for info in infos)
    except Exception:
        ips = set()
    with _LOCK:
        if len(_DNS_CACHE) >= 1000:
            _DNS_CACHE.clear()
        ttl = _DNS_TTL if ips else _DNS_EMPTY_TTL
        _DNS_CACHE[host] = (set(ips), now, ttl)
    return ips

def _resolve_ips_deadline(host, deadline):
    try:
        ip = ipaddress.ip_address(host.rstrip(".").lower())
        return {str(ip)}
    except ValueError:
        pass
    now = time.time()
    with _LOCK:
        if host.rstrip(".").lower() in _DNS_CACHE:
            ips, t, ttl = _DNS_CACHE[host.rstrip(".").lower()]
            if now - t < ttl:
                return set(ips)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return set()
    if not _DNS_SEM.acquire(timeout=min(remaining, 1)):
        return set()
    holder = {}
    def _do():
        try:
            holder["ips"] = _resolve_ips(host)
        finally:
            _DNS_SEM.release()
    th = threading.Thread(target=_do, daemon=True)
    th.start()
    th.join(timeout=remaining)
    if th.is_alive():
        return set()
    return holder.get("ips", set())

def _is_ip_public(ip_str):
    try:
        return ipaddress.ip_address(ip_str).is_global
    except Exception:
        return False

def _is_syntax_safe_url(url):
    try:
        p = urlsplit(url)
        if p.scheme not in ("http", "https"):
            return False
        if not p.hostname or p.username or p.password:
            return False
        host = p.hostname.lower()
        try:
            ip = ipaddress.ip_address(host.rstrip("."))
            if not ip.is_global:
                return False
        except ValueError:
            pass
        if host.rstrip(".").lower() in ("localhost",):
            return False
        return True
    except Exception:
        return False

def _is_safe_url(url):
    return _is_syntax_safe_url(url)

def _host_header(host, port):
    h = f"[{host}]" if ":" in host else host
    if port:
        h += f":{port}"
    return h

class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, pinned_ip, *a, **kw):
        super().__init__(host, *a, **kw)
        self._pinned_ip = pinned_ip
    def connect(self):
        self.sock = socket.create_connection((self._pinned_ip, self.port), timeout=self.timeout)

class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, pinned_ip, *a, **kw):
        super().__init__(host, *a, **kw)
        self._pinned_ip = pinned_ip
    def connect(self):
        raw = socket.create_connection((self._pinned_ip, self.port), timeout=self.timeout)
        ctx = ssl.create_default_context()
        self.sock = ctx.wrap_socket(raw, server_hostname=self.host)

def _read_limited(resp, max_bytes, deadline, sock=None):
    buf = bytearray()
    read_error = False
    try:
        while len(buf) <= max_bytes:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                read_error = True
                break
            if sock is not None:
                try:
                    sock.settimeout(remaining)
                except Exception:
                    pass
            chunk = resp.read(min(_CHUNK, max_bytes + 1 - len(buf)))
            if not chunk:
                break
            buf.extend(chunk)
    except Exception:
        read_error = True
    is_truncated = len(buf) > max_bytes
    return bytes(buf[:max_bytes]), is_truncated, read_error

def _pinned_request(method, url, timeout=4, max_bytes=200000, use_range=True):
    if method not in ("GET", "HEAD"):
        return None
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
        return None
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        return None
    start = time.monotonic()
    deadline = start + timeout + 2
    try:
        p = urlsplit(url)
    except (ValueError, TypeError):
        return None
    if p.scheme not in ("http", "https") or not p.hostname:
        return None
    if p.username or p.password:
        return None
    host = p.hostname.lower()
    if host in ("localhost", "127.0.0.1", "::1"):
        return None
    try:
        port = p.port or (443 if p.scheme == "https" else 80)
        if not 1 <= port <= 65535:
            return None
    except ValueError:
        return None
    ips = _resolve_ips_deadline(host, deadline)
    if not ips or not all(_is_ip_public(x) for x in ips):
        return None
    path = p.path or "/"
    if p.query:
        path += "?" + p.query
    sorted_ips = sorted(ips, key=lambda x: 0 if "." in x else 1)
    for ip in sorted_ips:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        conn_timeout = min(timeout, remaining)
        if conn_timeout <= 0:
            return None
        conn = None
        try:
            if p.scheme == "https":
                conn = _PinnedHTTPSConnection(host, ip, port, timeout=conn_timeout)
            else:
                conn = _PinnedHTTPConnection(host, ip, port, timeout=conn_timeout)
            headers = {"Host": _host_header(host, p.port), "User-Agent": "Mozilla/5.0 BHAI-KI-NEWS-Bot", "Accept": "*/*", "Connection": "close"}
            if method == "GET" and use_range:
                headers["Range"] = f"bytes=0-{max_bytes-1}"
            conn.request(method, path, headers=headers)
            remaining2 = deadline - time.monotonic()
            if remaining2 <= 0:
                try:
                    conn.close()
                except Exception:
                    pass
                return None
            try:
                if conn.sock is not None:
                    conn.sock.settimeout(remaining2)
            except Exception:
                pass
            resp = conn.getresponse()
            status = resp.status
            r_headers = {k.lower(): v for k, v in resp.getheaders()}
            cl_early = r_headers.get("content-length", "")
            if cl_early.isdigit() and int(cl_early) > max_bytes:
                try:
                    conn.close()
                except Exception:
                    pass
                return {"status": status, "headers": r_headers, "location": r_headers.get("location", ""), "body": b"", "final_url": url, "is_partial": True, "total": int(cl_early)}
            sock = None
            try:
                sock = conn.sock
            except Exception:
                sock = None
            body, is_truncated, read_error = _read_limited(resp, max_bytes, deadline, sock)
            is_partial = False
            if read_error:
                is_partial = True
            total = None
            cr = r_headers.get("content-range", "")
            cl = r_headers.get("content-length", "")
            if status == 206 and not cr:
                is_partial = True
            if cr:
                try:
                    m = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+|\*)", cr.strip(), re.I)
                    if not m:
                        is_partial = True
                    else:
                        start_b = int(m.group(1))
                        end = int(m.group(2))
                        total_part = m.group(3)
                        total = None if total_part == "*" else int(total_part)
                        expected_len = end - start_b + 1
                        if start_b != 0 or end < start_b:
                            is_partial = True
                        if total is not None and total <= end:
                            is_partial = True
                        if not use_range and total is not None and end + 1 != total:
                            is_partial = True
                        if len(body) != expected_len:
                            is_partial = True
                except (ValueError, TypeError):
                    is_partial = True
                    total = None
            elif cl.isdigit():
                try:
                    total = int(cl)
                    if status == 200 and len(body) < total:
                        is_partial = True
                except Exception:
                    total = None
            if is_truncated:
                is_partial = True
            try:
                conn.close()
            except Exception:
                pass
            return {"status": status, "headers": r_headers, "location": r_headers.get("location", ""), "body": body, "final_url": url, "is_partial": is_partial, "total": total}
        except Exception:
            try:
                if conn:
                    conn.close()
            except Exception:
                pass
            continue
    return None

def _is_image_bytes(data):
    if not data or len(data) < 12:
        return False
    if data[:3] == b"\xff\xd8\xff":
        return True
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return True
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return True
    if len(data) >= 20 and data[4:8] == b"ftyp":
        if b"avif" in data[8:32] or b"avis" in data[8:32]:
            return True
    return False

def _is_valid_image_data(data):
    if not _is_image_bytes(data):
        return False
    if not _HAS_PIL:
        return False
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            im = Image.open(io.BytesIO(data))
            if im.format not in ("JPEG", "PNG", "GIF", "WEBP", "AVIF"):
                return False
            w, h = im.size
            if w <= 0 or h <= 0 or w * h > _MAX_PIXELS:
                return False
            im.verify()
        return True
    except Exception:
        return False

def _og_cache_set(key, val, now):
    with _LOCK:
        if len(_OG_CACHE) >= _OG_MAX:
            try:
                _OG_CACHE.pop(next(iter(_OG_CACHE)), None)
            except StopIteration:
                pass
        _OG_CACHE[key] = (val, now)

def _img_cache_get(url, now):
    with _LOCK:
        if url in _IMG_CHECK_CACHE:
            val, t = _IMG_CHECK_CACHE[url]
            if now - t < _IMG_TTL:
                return val
            _IMG_CHECK_CACHE.pop(url, None)
    return None

def _img_cache_set(url, val, now):
    with _LOCK:
        if len(_IMG_CHECK_CACHE) >= _IMG_MAX:
            try:
                _IMG_CHECK_CACHE.pop(next(iter(_IMG_CHECK_CACHE)), None)
            except StopIteration:
                pass
        _IMG_CHECK_CACHE[url] = (val, now)

def _is_relevant_image(img_url, article_url):
    try:
        path = urlsplit(img_url).path.lower()
        if re.search(r'logo|avatar|placeholder|icon|pixel|sprite|default|no-image|blank|banner-ad|advertisement', path):
            return False
        return True
    except Exception:
        return False

def _is_real_image(url):
    now = time.time()
    cached = _img_cache_get(url, now)
    if cached is not None:
        return cached
    current = url
    orig_scheme = urlsplit(url).scheme
    for _ in range(4):
        if urlsplit(current).scheme not in ("http", "https"):
            _img_cache_set(url, False, now)
            return False
        try:
            r = _pinned_request("GET", current, timeout=3, max_bytes=2*1024*1024, use_range=False)
            if r is None:
                _img_cache_set(url, False, now)
                return False
            status = r["status"]
            if status in (301, 302, 303, 307, 308):
                nxt = r["headers"].get("location", "")
                if not nxt:
                    _img_cache_set(url, False, now)
                    return False
                nxt_abs = urljoin(current, nxt)
                if not _is_syntax_safe_url(nxt_abs):
                    _img_cache_set(url, False, now)
                    return False
                if orig_scheme == "https" and urlsplit(nxt_abs).scheme == "http":
                    _img_cache_set(url, False, now)
                    return False
                current = nxt_abs
                continue
            ct = _clean_mime(r["headers"].get("content-type", ""))
            if status in (200, 206) and ct.startswith("image/"):
                if r.get("is_partial"):
                    _img_cache_set(url, False, now)
                    return False
                if r.get("total") is not None and r["total"] > 2*1024*1024:
                    _img_cache_set(url, False, now)
                    return False
                if len(r["body"]) >= 2*1024*1024:
                    _img_cache_set(url, False, now)
                    return False
                if _is_valid_image_data(r["body"]):
                    _img_cache_set(url, True, now)
                    return True
            _img_cache_set(url, False, now)
            return False
        except Exception:
            _img_cache_set(url, False, now)
            return False
    _img_cache_set(url, False, now)
    return False

def _safe_fetch(url):
    current = url
    orig_scheme = urlsplit(url).scheme
    for _ in range(4):
        if urlsplit(current).scheme not in ("http", "https"):
            return None
        r = _pinned_request("GET", current, timeout=4, max_bytes=200000, use_range=True)
        if r is None:
            return None
        status = r["status"]
        if status in (301, 302, 303, 307, 308):
            nxt = r["headers"].get("location", "")
            if not nxt:
                return None
            nxt_abs = urljoin(current, nxt)
            if not _is_syntax_safe_url(nxt_abs):
                return None
            if orig_scheme == "https" and urlsplit(nxt_abs).scheme == "http":
                return None
            current = nxt_abs
            continue
        if status in (200, 206):
            ct = _clean_mime(r["headers"].get("content-type", ""))
            if "text/html" not in ct and "application/xhtml+xml" not in ct:
                return None
            return current, r["body"].decode("utf-8", errors="ignore"), r.get("is_partial", False)
        return None
    return None

  class NewsImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() != "img":
            return
        attrs = dict(attrs)
        src = (attrs.get("src") or attrs.get("data-src") or attrs.get("data-original") or attrs.get("data-lazy-src"))
        if src:
            self.images.append(src)

def valid_news_image(url):
    if not url:
        return False
    url = html.unescape(str(url)).strip()
    if len(url) > 2048:
        return False
    try:
        p = urlsplit(url)
        if p.scheme not in ("http", "https"):
            return False
        if not p.hostname:
            return False
        if p.username or p.password:
            return False
        host = p.hostname.lower()
        if host in ("localhost",):
            return False
        try:
            ip = ipaddress.ip_address(host)
            if not ip.is_global:
                return False
        except ValueError:
            pass
        if "." not in host:
            return False
        bad_words = ("logo", "icon", "avatar", "placeholder", "default", "favicon", "blank", "pixel", "no-image")
        if any(x in url.lower() for x in bad_words):
            return False
        return True
    except Exception:
        return False

def get_news_image(entry):
    candidates = []
    for item in entry.get("media_content", []) or []:
        if isinstance(item, dict):
            candidates.append(item.get("url", ""))
    for item in entry.get("media_thumbnail", []) or []:
        if isinstance(item, dict):
            candidates.append(item.get("url", ""))
    for item in entry.get("enclosures", []) or []:
        if isinstance(item, dict):
            typ = item.get("type", "")
            if typ.startswith("image/"):
                candidates.append(item.get("href") or item.get("url", ""))
    for item in entry.get("links", []) or []:
        if isinstance(item, dict):
            if item.get("type", "").startswith("image/"):
                candidates.append(item.get("href", ""))
    parser = NewsImageParser()
    contents = []
    for item in entry.get("content", []) or []:
        if isinstance(item, dict):
            contents.append(item.get("value", ""))
    contents.append(entry.get("summary", ""))
    for content in contents:
        if not content:
            continue
        try:
            parser.feed(str(content))
        except Exception:
            continue
    candidates.extend(parser.images)
    article_url = entry.get("link", "")
    for candidate in candidates:
        if not candidate:
            continue
        candidate = html.unescape(str(candidate)).strip()
        candidate = urljoin(article_url, candidate)
        if valid_news_image(candidate):
            return candidate
    return ""
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
