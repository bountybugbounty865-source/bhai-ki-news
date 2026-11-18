
import feedparser, re, hashlib, urllib.parse
from flask import Flask, request
app = Flask(__name__)

FEEDS = {
    "🇮🇳 India - Kaam Ki Khabar": "https://www.aajtak.in/rss",
    "🌍 World - Kaam Ki Khabar": "https://www.bbc.com/hindi/index.xml",
}

# --- LIBRARY KA SAMAAN ---
LIBRARY = {
    "📕 NCERT Books - Class 6 se 12 Free": [
        ("Class 10 - Science / Vigyan", "https://ncert.nic.in/ncerts/l/jesc1ps.pdf"),
        ("Class 10 - Maths / Ganit", "https://ncert.nic.in/ncerts/l/jemh1ps.pdf"),
        ("Class 12 - Physics", "https://ncert.nic.in/ncerts/l/keph1ps.pdf"),
        ("Class 12 - Biology", "https://ncert.nic.in/ncerts/l/kebo1ps.pdf"),
        ("Sab NCERT Books Yahi Se Download Karo", "https://ncert.nic.in/textbook.php"),
    ],
    "📝 Previous Paper / Exam": [
        ("UP Board - Previous Paper", "https://upmsp.edu.in/PreviousYearQuestionPaper.html"),
        ("CBSE - Previous Paper", "https://cbseacademic.nic.in/SQP_CLASSX_2025-26.html"),
        ("SSC - Previous Paper", "https://ssc.gov.in/"),
        ("UPSC - Previous Paper", "https://upsc.gov.in/examinations/previous-question-papers"),
    ],
    "💼 Sarkari Naukri / Job": [
        ("Sarkari Result - Sab Naukri", "https://www.sarkariresult.com/"),
        ("UP Sarkari Naukri", "https://upsssc.gov.in/"),
        ("Railway Job", "https://www.rrbapply.gov.in/"),
        ("Army / Agniveer", "https://joinindianarmy.nic.in/"),
    ],
    "📖 Free Notes / Padhai Website": [
        ("Khan Sir - Notes", "https://www.khanglobalstudies.com/"),
        ("Physics Wallah - Free Notes", "https://www.pw.live/"),
        ("Unacademy - Free Class", "https://unacademy.com/"),
        ("Diksha - Govt Free Padhai", "https://diksha.gov.in/"),
    ],
}

def clean(text):
    try:
        text = re.sub('<[^<]+?>', '', text or '')
        return text[:200] + "..." if len(text) > 200 else text
    except:
        return ""

def get_img(entry, title):
    try:
        if 'media_content' in entry and entry.media_content:
            u = entry.media_content[0].get('url','')
            if u: return u
        if 'media_thumbnail' in entry and entry.media_thumbnail:
            u = entry.media_thumbnail[0].get('url','')
            if u: return u
        m = re.search(r'src="([^"]+)"', entry.get('summary','') or '')
        if m: return m.group(1)
    except:
        pass
    h = hashlib.md5(title.encode()).hexdigest()[:8]
    photos = ["photo-1504711434969-e33886168f5c","photo-1524492412937-b28074a5d7da","photo-1531415074968-036ba1b575da","photo-1489599849927-2ee91cede3ba","photo-1596040033229-a9821ebd058d","photo-1585829365295-ab7cd400c167","photo-1495020689067-958852a7765e","photo-1529107386315-e1a2ed48a620"]
    pick = photos[int(h,16) % len(photos)]
    return f"https://images.unsplash.com/{pick}?w=600"

def make_cards(feed, seen, limit=15):
    cards = ""
    count = 0
    for entry in feed.entries:
        if count >= limit: break
        title = entry.get('title','').strip()
        link = entry.get('link','')
        if title in seen or link in seen or not title:
            continue
        seen.add(title); seen.add(link)
        img = get_img(entry, title)
        desc = clean(entry.get('summary','') or entry.get('description',''))
        cards += f"""<div class="card"><img src="{img}"><h3>{title}</h3><p>{desc}</p><a href="{link}" target="_blank">Poori Khabar Padhein →</a></div>"""
        count += 1
    return cards

def header(search_val=""):
    return f"""
    <div class="header"><h1>🔴 BHAI KI NEWS</h1><p><span class="live">● LIVE</span> Sirf Kaam Ki Khabar</p><p>Made by Priyanshu Singh | Lucknow</p>
    <div style="margin-top:12px;display:flex;gap:10px;justify-content:center"><a href="/" style="background:white;color:#d60000;padding:8px 18px;border-radius:20px;text-decoration:none;font-weight:bold">📰 News</a><a href="/library" style="background:yellow;color:black;padding:8px 18px;border-radius:20px;text-decoration:none;font-weight:bold">📚 Padhai Library</a></div></div>
    """

def style():
    return """
    <style>
        body{font-family:Arial;background:#f2f2f2;margin:0}
        .header{background:#d60000;color:white;padding:20px;text-align:center}
        .header h1{margin:0;font-size:32px}
        .live{background:yellow;color:black;padding:3px 10px;border-radius:20px;font-weight:bold}
        .search-box{padding:15px;background:white;position:sticky;top:0;z-index:9;box-shadow:0 2px 5px #ccc}
        .search-row{display:flex;gap:10px}
        .search-row input{flex:1;padding:12px;font-size:16px;border:2px solid #d60000;border-radius:25px;outline:none}
        .search-row button{background:#d60000;color:white;border:none;padding:12px 20px;border-radius:25px;font-size:16px;font-weight:bold}
        .tags{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
        .tags a{background:#ffe5e5;color:#d60000;padding:7px 14px;border-radius:20px;text-decoration:none;font-weight:bold;font-size:14px}
        h2{padding:0 15px;color:#d60000}
        .grid{display:grid;grid-template-columns:1fr 1fr;gap:15px;padding:0 15px 20px}
        .card{background:white;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px #ccc}
        .card img{width:100%;height:180px;object-fit:cover}
        .card h3{font-size:17px;margin:12px 12px 5px}
        .card p{font-size:14px;color:#555;margin:0 12px 10px;line-height:1.5}
        .card a{display:block;color:#d60000;font-weight:bold;text-decoration:none;padding:0 12px 12px}
        .lib-card{background:white;border-radius:12px;padding:15px;box-shadow:0 2px 8px #ccc}
        .lib-card a{display:block;background:#d60000;color:white;text-align:center;padding:10px;border-radius:10px;text-decoration:none;font-weight:bold;margin-top:10px}
        @media(max-width:600px){.grid{grid-template-columns:1fr}}
    </style>
    """

@app.route('/library')
def library():
    body = "<h2 style='text-align:center'>📚 Padhai Library - Sab Free Hai Bhai!</h2>"
    for cat, items in LIBRARY.items():
        body += f"<h2>{cat}</h2><div class='grid'>"
        for name, link in items:
            body += f"""<div class="lib-card"><h3 style="margin:0">{name}</h3><a href="{link}" target="_blank">Khol ke Padho →</a></div>"""
        body += "</div>"
    return f"""<html><head><title>Padhai Library</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}<div style="padding-top:10px">{body}</div><div style="text-align:center;padding:20px;color:gray">© 2026 Bhai Ki News - Library</div></body></html>"""

@app.route('/')
def home():
    q = request.args.get('q','').strip()
    if q:
        search_url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:7d") + "&hl=hi&gl=IN&ceid=IN:hi"
        feed = feedparser.parse(search_url)
        seen = set()
        cards = make_cards(feed, seen, limit=30)
        if not cards:
            cards = "<p style='text-align:center;padding:20px'>😔 Is naam ki koi khabar nahi mili!</p>"
        body = f"<h2>🔍 '{q}' ki khabar</h2><div class='grid'>{cards}</div><div style='text-align:center;padding:10px'><a href='/' style='color:#d60000;font-weight:bold'>← Wapas Home</a></div>"
        search_val = q
    else:
        all_news = ""
        seen = set()
        for category, url in FEEDS.items():
            try:
                feed = feedparser.parse(url)
                cards = make_cards(feed, seen, limit=15)
                if cards:
                    all_news += f"<h2>{category}</h2><div class='grid'>{cards}</div>"
            except:
                continue
        body = all_news
        search_val = ""
    return f"""
    <html><head><title>BHAI KI NEWS</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head>
    <body>
        {header()}
        <div class="search-box">
            <form class="search-row" action="/" method="get"><input type="text" name="q" value="{search_val}" placeholder="🔍 Kuch bhi likho... Army, Gold, Padhai..."><button type="submit">Search</button></form>
            <div class="tags"><a href="/?q=Army">🪖 Army</a><a href="/?q=Gold">🪙 Gold</a><a href="/?q=Padhai Exam">📚 Padhai</a><a href="/?q=Cricket">🏏 Cricket</a><a href="/?q=Job Naukri">💼 Job</a><a href="/?q=UP Lucknow">📍 UP</a><a href="/library">📚 Library Khol</a></div>
        </div>
        {body}
        <div style="text-align:center;padding:20px;color:gray">© 2026 Bhai Ki News</div>
    </body></html>
    """
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
