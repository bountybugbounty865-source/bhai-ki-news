import feedparser, re, hashlib, urllib.parse, random, os, json, time
from flask import Flask, request, redirect, url_for, session
from datetime import datetime

app = Flask(__name__)
app.secret_key = "bhai-ki-news-secret-123"

# --- SECRET PASSWORD - YAHI SE BADLEGA, KAHI AUR NAHI DIKHEGA ---
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Priyanshu@123")
# Naya Password hai: Priyanshu@123 - Isko kisi ko mat batana!

# --- VISITOR + ARTICLE STORAGE ---
DATA_FILE = "bhai_data.json"
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f: return json.load(f)
        except: pass
    return {"total":0, "today":{}, "reads":{}, "my_articles":[], "online":[]}
def save_data(d):
    with open(DATA_FILE,"w") as f: json.dump(d,f)

FEEDS = {
    "🔥 Top Khabar": "https://news.google.com/rss?hl=hi&gl=IN&ceid=IN:hi",
    "🏏 Cricket": "https://news.google.com/rss/search?q=Cricket&hl=hi&gl=IN&ceid=IN:hi",
    "💼 Naukri": "https://news.google.com/rss/search?q=Sarkari Naukri&hl=hi&gl=IN&ceid=IN:hi",
    "📚 Padhai": "https://news.google.com/rss/search?q=Exam Padhai&hl=hi&gl=IN&ceid=IN:hi",
    "📍 UP / Lucknow News": "https://news.google.com/rss/search?q=Uttar Pradesh Lucknow&hl=hi&gl=IN&ceid=IN:hi",
    "🌦️ Mausam": "https://news.google.com/rss/search?q=Mausam Mandi Bhav&hl=hi&gl=IN&ceid=IN:hi",
}
GK_LIST = [
    ("Lal Kila kaha hai?", "Delhi me"),
    ("Taj Mahal kaha hai?", "Agra me"),
    ("Aasman Neela kyu hai?", "Neela rang zyada bikharne se"),
    ("23 x 11 = ?", "253 - Trick se!"),
    ("Bharat ka Rashtriya Pashu kaun hai?", "Bagh"),
]
# --- GK BANK - ROZ 15 AUTOMATIC ---
GK_BANK = GK_LIST + [
    ("Bharat ka Rashtriya Pakshi?", "Mor"),
    ("Ganga nadi kaha se nikalti hai?", "Gangotri se"),
    ("Bharat ki Rajdhani?", "New Delhi"),
    ("UP ki Rajdhani?", "Lucknow"),
    ("Bharat ka Sabse Bada Rajya?", "Rajasthan"),
    ("Computer ka Pita kise kehte hai?", "Charles Babbage"),
    ("Pani ka Formula?", "H2O"),
    ("Bharat ka Samvidhan kab lagu hua?", "26 Jan 1950"),
    ("Mahatma Gandhi ka janm kab?", "2 Oct 1869"),
    ("Bharat ka pehla Rashtrapati?", "Dr. Rajendra Prasad"),
    ("Chand par pehla kadam kisne rakha?", "Neil Armstrong"),
    ("Sabse bada grah?", "Brihaspati"),
    ("Manav sharir me kitni haddi?", "206"),
    ("Duniya ka sabse bada Mahasagar?", "Prashant"),
    ("Kutub Minar kaha hai?", "Delhi me"),
    ("Bharat ka Rashtriya Phool?", "Kamal"),
    ("Bharat ka Rashtriya Fal?", "Aam"),
    ("Jai Hind kisne kaha?", "Netaji Subhash Chandra Bose"),
    ("Vande Mataram kisne likha?", "Bankim Chandra Chatterjee"),
    ("Jana Gana Mana kisne likha?", "Rabindranath Tagore"),
    ("Lucknow kis nadi kinare?", "Gomti"),
    ("Ayodhya kis nadi kinare?", "Saryu"),
    ("Taj Mahal kisne banwaya?", "Shahjahan"),
    ("Computer me 1 GB = ?", "1024 MB"),
    ("Bharat me pehli Rail kab chali?", "1853 Mumbai-Thane"),
    ("Duniya ka sabse bada Desh?", "Russia"),
    ("Hindi Diwas kab?", "14 September"),
    ("Shikshak Diwas kab?", "5 September"),
    ("Bachcho ka Din kab?", "14 November"),
    ("Yoga Diwas kab?", "21 June"),
    ("Duniya ka sabse tez Janwar?", "Cheetah"),
    ("Duniya ka sabse bada Janwar?", "Blue Whale"),
    ("Insan ki Heart Beat kitni?", "72 per minute"),
    ("Bharat ka IT City?", "Bengaluru"),
    ("UP ka famous Kila?", "Jhansi Kila"),
    ("Char Minar kaha hai?", "Hyderabad"),
    ("India Gate kaha hai?", "New Delhi"),
    ("Bharat me kitne Rajya?", "28 Rajya + 8 UT"),
    ("Gandhi ji ka pura naam?", "Mohandas Karamchand Gandhi"),
    ("Himalaya ki sabse unchi choti?", "Mount Everest"),
    ("Sardar Patel ko kya kehte hai?", "Loh Purush"),
    ("Bharat ka pehla PM?", "Jawaharlal Nehru"),
    ("Suraj sabse paas ka grah?", "Budh"),
    ("Khoon ka rang lal kyu?", "Haemoglobin se"),
    ("Cricket ka Janm kaha?", "England"),
    ("Oxygen kisne khoji?", "Joseph Priestley"),
    ("Qutub Minar kisne banwaya?", "Qutubuddin Aibak"),
    ("Internet ka pura naam?", "Interconnected Network"),
    ("Bharat ka sabse lamba Pul?", "Bhupen Hazarika Setu"),
    ("Tiranga me kitne rang?", "3 + Ashok Chakra"),
    ("Bharat ka National Anthem?", "Jana Gana Mana"),
]
def get_today_gk():
    day_num = datetime.now().timetuple().tm_yday
    start = (day_num * 15) % len(GK_BANK)
    out = []
    for i in range(15):
        out.append(GK_BANK[(start + i) % len(GK_BANK)])
    return out

FORMULAS = [
    ("(a+b)²", "(a² + 2ab + b²)"),
    ("Area - Circle", "πr²"),
    ("Speed", "Distance / Time"),
    ("11 se Guna", "23x11 = 253 Trick"),
]
LIBRARY = {
    "📚 NCERT Books": [("Class 10 Maths", "https://ncert.nic.in/"), ("Class 10 Science", "https://ncert.nic.in/")],
    "📝 Previous Paper": [("UP Board Paper", "https://upmsp.edu.in/"), ("CBSE Paper", "https://cbse.gov.in/")],
    "📚 Class 9 - NCERT Books": [("Class 9 Maths Book", "https://ncert.nic.in/textbook.php"), ("Class 9 Science Book", "https://ncert.nic.in/textbook.php"), ("Class 9 Hindi Book", "https://ncert.nic.in/textbook.php"), ("Class 9 SST Book", "https://ncert.nic.in/textbook.php")],
    "📚 Class 10 - NCERT Books": [("Class 10 Maths Book", "https://ncert.nic.in/textbook.php"), ("Class 10 Science Book", "https://ncert.nic.in/textbook.php"), ("Class 10 Hindi Book", "https://ncert.nic.in/textbook.php"), ("Class 10 SST Book", "https://ncert.nic.in/textbook.php")],
    "📚 Class 11 - NCERT Books": [("Class 11 Physics", "https://ncert.nic.in/textbook.php"), ("Class 11 Chemistry", "https://ncert.nic.in/textbook.php"), ("Class 11 Maths", "https://ncert.nic.in/textbook.php"), ("Class 11 Biology", "https://ncert.nic.in/textbook.php")],
    "📚 Class 12 - NCERT Books": [("Class 12 Physics", "https://ncert.nic.in/textbook.php"), ("Class 12 Chemistry", "https://ncert.nic.in/textbook.php"), ("Class 12 Maths", "https://ncert.nic.in/textbook.php"), ("Class 12 Biology", "https://ncert.nic.in/textbook.php")],
    "✅ Class 9 NCERT Solutions": [("Maths Solutions - Class 9", "https://www.learncbse.in/ncert-solutions-class-9-maths/"), ("Science Solutions - Class 9", "https://www.learncbse.in/ncert-solutions-class-9-science/")],
    "✅ Class 10 NCERT Solutions": [("Maths Solutions - Class 10", "https://www.learncbse.in/ncert-solutions-class-10-maths/"), ("Science Solutions - Class 10", "https://www.learncbse.in/ncert-solutions-class-10-science/"), ("Hindi Solutions - Class 10", "https://www.learncbse.in/ncert-solutions-class-10-hindi/")],
    "✅ Class 11 NCERT Solutions": [("Physics Solutions - Class 11", "https://www.learncbse.in/ncert-solutions-class-11-physics/"), ("Chemistry Solutions - Class 11", "https://www.learncbse.in/ncert-solutions-class-11-chemistry/"), ("Maths Solutions - Class 11", "https://www.learncbse.in/ncert-solutions-class-11-maths/")],
    "✅ Class 12 NCERT Solutions": [("Physics Solutions - Class 12", "https://www.learncbse.in/ncert-solutions-class-12-physics/"), ("Chemistry Solutions - Class 12", "https://www.learncbse.in/ncert-solutions-class-12-chemistry/"), ("Maths Solutions - Class 12", "https://www.learncbse.in/ncert-solutions-class-12-maths/"), ("Biology Solutions - Class 12", "https://www.learncbse.in/ncert-solutions-class-12-biology/")],
    "📝 UP Board Class 10 Paper": [("UP Board Class 10 Paper", "https://upmsp.edu.in/")],
    "📝 UP Board Class 12 Paper": [("UP Board Class 12 Paper", "https://upmsp.edu.in/")],
    "🎯 Sarkari Exam": [("SSC GD / MTS Notes", "https://ssc.gov.in/"), ("Police / Army Bharti", "https://uppbpb.gov.in/"), ("Railway Notes", "https://www.rrbapply.gov.in/")],
}
MY_NEW_ARTICLES = [
    ("Math - 11 se Guna Trick", "Math", "23 x 11 = 253. 2 aur 3 ko alag karo, beech me 2+3=5 daal do!"),
    ("Science - Aasman Neela Kyu?", "Science", "Suraj ki roshni me 7 rang hote hai, Neela sabse zyada bikhar ta hai!"),
    ("Hindi - Mera Gaon Nibandh", "Hindi", "Mera gaon mera garv hai. Yaha ki hawa saaf hai, log madad karte hai!"),
    ("Best Article - Mehnat Kabhi Bekar Nahi Jaati", "Article", "Kanpur ke Priyanshu ne apni Website bana di. Mehnat wale ko koi nahi rok sakta!"),
]

def clean(t):
    t = re.sub('<[^<]+?>','',t or '')
    return t[:180]+"..." if len(t)>180 else t
def get_img(entry, title):
    try:
        if 'media_content' in entry: return entry.media_content[0]['url']
        if 'links' in entry:
            for l in entry.links:
                if 'image' in l.get('type',''): return l['href']
    except: pass
    h = hashlib.md5(title.encode()).hexdigest()
    return f"https://picsum.photos/seed/{h}/600/400"

def make_cards(feed, seen, limit=15):
    cards=""; count=0
    for entry in feed.entries:
        if count>=limit: break
        title = entry.get('title','').strip()
        link = entry.get('link','')
        if title in seen or link in seen or not title: continue
        seen.add(title); seen.add(link)
        img = get_img(entry, title)
        desc = clean(entry.get('summary','') or entry.get('description',''))
        cards += f"""<div class="card"><img src="{img}"><h3>{title}</h3><p>{desc}</p><a href="{link}" target="_blank">Poori Khabar Padhein →</a></div>"""
        count += 1
    return cards

def header(search_val=""):
    d = load_data()
    d["total"] = d.get("total",0)+1
    today_str = datetime.now().strftime("%Y-%m-%d")
    if "today" not in d: d["today"] = {}
    d["today"][today_str] = d["today"].get(today_str,0)+1
    if "online" not in d: d["online"] = []
    now = time.time()
    d["online"] = [t for t in d["online"] if now - t < 120]
    d["online"].append(now)
    online_count = len(d["online"])
    save_data(d)
    return f"""
    <div class="header"><h1>🔴 BHAI KI NEWS</h1><p><span class="live">● LIVE</span> Sirf Kaam Ki Khabar + Free Padhai</p><p>Made by Priyanshu Singh | Lucknow</p>
    <p style="background:black;color:white;display:inline-block;padding:5px 12px;border-radius:20px;font-size:13px">👀 Aaj: {d["today"][today_str]} | Total: {d["total"]} | 🟢 Online: {online_count}</p>
    <div style="margin-top:12px;display:flex;gap:8px;justify-content:center;flex-wrap:wrap"><a href="/" style="background:white;color:#d60000;padding:8px 14px;border-radius:20px;text-decoration:none;font-weight:bold">📰 News</a><a href="/library" style="background:yellow;color:black;padding:8px 14px;border-radius:20px;text-decoration:none;font-weight:bold">📚 Padhai Library</a><a href="/gk" style="background:white;color:#d60000;padding:8px 14px;border-radius:20px;text-decoration:none;font-weight:bold">🧠 GK</a><a href="/about" style="background:white;color:#d60000;padding:8px 14px;border-radius:20px;text-decoration:none;font-weight:bold">ℹ️ About</a><a href="/admin" style="background:black;color:white;padding:8px 14px;border-radius:20px;text-decoration:none;font-weight:bold">🔐 Admin</a></div></div>
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
        .card img{width:100%;height:220px;object-fit:cover}
        .card h3{font-size:18px;margin:12px 12px 5px;line-height:1.4}
        .card p{font-size:14px;color:#555;margin:0 12px 10px;line-height:1.5}
        .card a{display:block;color:#d60000;font-weight:bold;text-decoration:none;padding:0 12px 12px}
        .lib-card{background:white;border-radius:12px;padding:15px;box-shadow:0 2px 8px #ccc}
        .lib-card a{display:block;background:#d60000;color:white;text-align:center;padding:10px;border-radius:10px;text-decoration:none;font-weight:bold;margin-top:10px}
        .box{background:white;margin:15px;padding:20px;border-radius:12px;box-shadow:0 2px 8px #ccc;line-height:1.7}
        .footer{text-align:center;padding:20px;color:gray}
        .footer a{color:#d60000;text-decoration:none;font-weight:bold;margin:0 8px}
        input,select,textarea{width:100%;padding:12px;margin:8px 0;border:1px solid #ccc;border-radius:10px;box-sizing:border-box;font-size:15px}
        .btn{background:#d60000;color:white;border:none;padding:12px;border-radius:10px;font-weight:bold;font-size:16px;cursor:pointer}
        .gk-num{background:#d60000;color:white;width:28px;height:28px;display:inline-flex;align-items:center;justify-content:center;border-radius:50%;font-size:14px;margin-right:8px}
        @media(max-width:600px){.grid{grid-template-columns:1fr}}
    </style>
    """

def footer():
    return """<div class="footer"><a href="/">Home</a> | <a href="/library">Library</a> | <a href="/gk">GK</a> | <a href="/about">About Us</a> | <a href="/contact">Contact Us</a> | <a href="/privacy">Privacy Policy</a><br><br>© 2026 Bhai Ki News - Made by Priyanshu Singh, Lucknow</div></body></html>"""

def search_box(q=""):
    return f"""<div class="search-box"><form action="/" method="get"><div class="search-row"><input name="q" value="{q}" placeholder="Khabar khojo... jaise Cricket, Naukri"><button>Search 🔍</button></div></form><div class="tags"><a href="/?q=Cricket">🏏 Cricket</a><a href="/?q=Naukri">💼 Naukri</a><a href="/?q=UP">📍 UP News</a><a href="/?q=Weather">🌦️ Mausam</a><a href="/?q=Gold">🪙 Gold</a><a href="/library">📚 Library Khol</a><a href="/gk">🧠 Aaj ka GK</a></div></div>"""

@app.route("/")
def home():
    q = request.args.get("q","").strip()
    h = header()
    s = style()
    html = f"""<html><head><title>Bhai Ki News - Lucknow</title><meta name="viewport" content="width=device-width, initial-scale=1">{s}</head><body>{h}{search_box(q)}"""
    d = load_data()
    all_my = MY_NEW_ARTICLES + [(a.get("title",""), a.get("cat",""), a.get("text","")) for a in d.get("my_articles",[])]
    if not q or any(q.lower() in (t+" "+c+" "+txt).lower() for t,c,txt in all_my):
        html += """<h2>✍️ Bhai Ke Apne Article</h2><div class="grid">"""
        for t,c,txt in all_my:
            if q and q.lower() not in (t+" "+c+" "+txt).lower(): continue
            html += f"""<div class="card"><img src="https://picsum.photos/seed/{hashlib.md5(t.encode()).hexdigest()}/600/400"><h3>{t}</h3><p><b>{c}</b> - {txt[:150]}</p></div>"""
        html += "</div>"
    seen=set()
    for name, url in FEEDS.items():
        if q:
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=hi&gl=IN&ceid=IN:hi"
            feed = feedparser.parse(url)
            cards = make_cards(feed, seen, limit=20)
            html += f"<h2>🔍 Search: {q}</h2><div class='grid'>{cards}</div>"
            break
        try:
            feed = feedparser.parse(url)
            cards = make_cards(feed, seen, limit=15)
            html += f"<h2>{name}</h2><div class='grid'>{cards}</div>"
        except: pass
    html += footer()
    return html

@app.route("/library")
def library():
    h=header(); s=style()
    html=f"""<html><head><title>Padhai Library - Class 9 to 12</title><meta name="viewport" content="width=device-width, initial-scale=1">{s}</head><body>{h}<h2>📚 Padhai Library - Class 9 se 12 Tak - Sab Free Hai Bhai!</h2><div class="box" style="background:#fff3cd"><b>👉 Kaise Padhe?</b> Apni Class pe click karo -> Book ya Solutions khulega -> Free me padho!</div><div class="grid">"""
    for cat, items in LIBRARY.items():
        for title, link in items:
            html += f"""<div class="lib-card"><h3>{cat}</h3><p>{title}</p><a href="{link}" target="_blank">Khol ke Padho →</a></div>"""
    html += "</div><div class='box'><h3>📐 Formula Yaad Karo</h3>"
    for a,b in FORMULAS:
        html += f"<p><b>{a}</b> = {b}</p>"
    html += "</div>"+footer()
    return html

@app.route("/gk")
def gk():
    h=header(); s=style()
    today_gk = get_today_gk()
    today_str = datetime.now().strftime("%d %B %Y")
    html=f"""<html><head><title>Aaj ka GK - 15 Question</title><meta name="viewport" content="width=device-width, initial-scale=1">{s}</head><body>{h}<h2>🧠 Aaj ka GK - {today_str} - 15 Question</h2><div class="box" style="background:#e8ffe8"><b>🔥 Aaj ke 15 Question - Kal naye aayenge! Roz yaha aake yaad karo!</b></div>"""
    for i,(q,a) in enumerate(today_gk,1):
        html += f"""<div class="box"><span class="gk-num">{i}</span><b>Q: {q}</b><br><span style="color:green">✅ Answer: {a}</span></div>"""
    html += """<div class="box"><h3>📐 Saare Formula</h3>"""
    for a,b in FORMULAS:
        html += f"<p><b>{a}</b> = {b}</p>"
    html += "</div>"+footer()
    return html

@app.route("/about")
def about():
    h=header(); s=style()
    return f"""<html><head><title>About</title><meta name="viewport" content="width=device-width, initial-scale=1">{s}</head><body>{h}<div class="box"><h2>ℹ️ About Bhai Ki News</h2><p>Namaste! Main <b>Priyanshu Singh, Lucknow</b> se hu. Maine ye Website isliye banayi taaki gaon aur sheher ke sabhi bhaiyo ko ek jagah News + Free Padhai mil jaye.</p><p>Roz yaha Cricket, Naukri, UP News aur GK milega.</p><p><b>Instagram:</b> @priyanshu538617</p></div>{footer()}"""

@app.route("/about-us")
def about_us():
    return redirect("/about")

@app.route("/contact")
@app.route("/contact-us")
def contact():
    h=header(); s=style()
    return f"""<html><head><title>Contact Us</title><meta name="viewport" content="width=device-width, initial-scale=1">{s}</head><body>{h}<div class="box"><h2>📞 Contact Us</h2><p>Namaste Bhai! Koi bhi dikkat ho to Instagram pe Message karo.</p><p><b>Instagram:</b> @priyanshu538617</p><p><b>Website:</b> Bhai Ki News, Lucknow</p></div>{footer()}"""

@app.route("/privacy")
@app.route("/privacy-policy")
def privacy():
    h=header(); s=style()
    return f"""<html><head><title>Privacy Policy</title><meta name="viewport" content="width=device-width, initial-scale=1">{s}</head><body>{h}<div class="box"><h2>🔐 Privacy Policy</h2><p>Hum aapka koi Personal Data nahi lete. Sirf ye dekhte hai kitne log Website dekh rahe hai, taaki hum achhi Khabar de sake.</p><p>Google ke Ads aane par Google apni Policy se Data lega.</p></div>{footer()}"""

@app.route("/admin", methods=["GET","POST"])
def admin():
    s=style()
    if request.method=="POST" and request.form.get("password")==ADMIN_PASSWORD:
        session["admin"]=True
    if request.method=="POST" and session.get("admin"):
        d=load_data()
        title=request.form.get("title","").strip()
        cat=request.form.get("cat","Article")
        text=request.form.get("text","").strip()
        if title and text:
            d["my_articles"].append({"title":title,"cat":cat,"text":text})
            save_data(d)
            return redirect("/admin")
    if not session.get("admin"):
        return f"""<html><head><meta name="viewport" content="width=device-width, initial-scale=1">{s}</head><body>{header()}<div class="box"><h2>🔐 Admin Login</h2><form method="post"><input type="password" name="password" placeholder="Password daalo"><button class="btn">Login</button></form></div>{footer()}"""
    d=load_data()
    return f"""<html><head><meta name="viewport" content="width=device-width, initial-scale=1">{s}</head><body>{header()}<div class="box"><h2>✍️ Naya Article Daalo</h2><form method="post"><input name="title" placeholder="Title - jaise Qutub Minar"><input name="cat" p
