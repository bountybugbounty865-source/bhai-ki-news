import feedparser, re, hashlib, urllib.parse, random, os, json
from flask import Flask, request, redirect, url_for, session
from datetime import datetime

app = Flask(__name__)

# Secure Environment Variables
app.secret_key = os.environ.get("SECRET_KEY")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

if not app.secret_key or not ADMIN_PASSWORD:
    raise RuntimeError("Security Environment Variables Missing!")

# Secure Session Cookies
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=1800
)

DATA_FILE = "bhai_data.json"
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f: return json.load(f)
        except: pass
    return {"total":0, "today":{}, "reads":{}, "my_articles":[]}
def save_data(d):
    with open(DATA_FILE,"w") as f: json.dump(d,f)

FEEDS = {
"🔥 Top Khabar": "https://news.google.com/rss?hl=hi&gl=IN&ceid=IN:hi",
"🏏 Cricket": "https://news.google.com/rss/search?q=Cricket&hl=hi&gl=IN&ceid=IN:hi",
"💼 Naukri": "https://news.google.com/rss/search?q=Sarkari Naukri&hl=hi&gl=IN&ceid=IN:hi",
"📚 Padhai": "https://news.google.com/rss/search?q=Exam Padhai&hl=hi&gl=IN&ceid=IN:hi",
}

# --- 31 DIN KE LIYE 31 GK ---

GK_LIST = [
("Lal Kila kaha hai?", "Delhi me"),
("Taj Mahal kaha hai?", "Agra me"),
("Aasman Neela kyu hai?", "Neela rang zyada bikharne se"),
("23 x 11 = ?", "253 - Trick se!"),
("Bharat ka Rashtriya Pashu kaun hai?", "Bagh"),
("Bharat ki Rajdhani kya hai?", "New Delhi"),
("Bharat ka Rashtriya Pakshi kaunsa hai?", "Mor"),
("Ganga Nadi kaha se nikalti hai?", "Gangotri se"),
("Bharat ka sabse bada Rajya kaunsa hai?", "Rajasthan"),
("Computer ka Pita kise kehte hai?", "Charles Babbage"),
("Bharat ke Pehle Rashtrapati kaun the?", "Dr. Rajendra Prasad"),
("UP ki Rajdhani kya hai?", "Lucknow"),
("Qutub Minar kaha hai?", "Delhi me"),
("Bharat ka Rashtriya Phool kaunsa hai?", "Kamal"),
("Bharat ka Rashtriya Khel kaunsa hai? (Unofficial)", "Hockey mana jata hai"),
("Mahatma Gandhi ka janm kab hua?", "2 October 1869"),
("Bharat ko Azadi kab mili?", "15 August 1947"),
("Bharat ka Samvidhan kab lagu hua?", "26 January 1950"),
("Bharat ka sabse lamba pahaad kaunsa hai?", "K2 - Godwin Austin"),
("Bharat ki sabse lambi nadi kaunsi hai?", "Ganga"),
("Tiranga me kitne rang hote hai?", "3 - Kesar, Safed, Hara + Ashok Chakra"),
("Ashok Chakra me kitni teeliya hoti hai?", "24"),
("Bharat ka Rashtriya Gaan kaunsa hai?", "Jana Gana Mana"),
("Jana Gana Mana kisne likha?", "Rabindranath Tagore"),
("Bharat ka Sabse Bada Sheher kaunsa hai?", "Mumbai"),
("Lucknow kis nadi ke kinare hai?", "Gomti Nadi"),
("Bharat me kitne Rajya hai?", "28 Rajya + 8 Kendra Shasit Pradesh"),
("Chand par pehla kadam kisne rakha?", "Neil Armstrong"),
("Bharat ka Pehla Pradhan Mantri kaun tha?", "Pandit Jawaharlal Nehru"),
("Bharat ka Pehla Upgrah kaunsa tha?", "Aryabhatta"),
("1 Minute me kitne Second hote hai?", "60 Second"),
]
FORMULAS = [
("(a+b)²", "(a² + 2ab + b²)"),
("Area - Circle", "πr²"),
("Speed", "Distance / Time"),
("11 se Guna", "23x11 = 253 Trick"),
]
LIBRARY = {
"📚 NCERT Books": [("Class 10 Maths", "https://ncert.nic.in/"), ("Class 10 Science", "https://ncert.nic.in/"), ("Class 10 English", "https://ncert.nic.in/")],
"📝 Previous Paper": [("UP Board Paper", "https://upmsp.edu.in/"), ("CBSE Paper", "https://cbse.gov.in/")],
"📖 English Grammar": [("Tense Trick - Full Notes", "https://ncert.nic.in/"), ("Active Passive", "https://ncert.nic.in/"), ("Letter Writing", "https://ncert.nic.in/")],
"💻 Computer": [("Computer Kya Hai?", "https://ncert.nic.in/"), ("MS Word / Excel", "https://ncert.nic.in/"), ("Internet Aur Email", "https://ncert.nic.in/")],
"🌍 SST - Itihas / Bhugol": [("Bharat Ka Itihas", "https://ncert.nic.in/"), ("Bharat Ka Bhugol", "https://ncert.nic.in/"), ("Samvidhan - Constitution", "https://ncert.nic.in/")],
"🧠 Daily GK + Formula": [("Aaj Ka GK", "/gk"), ("Maths Formula", "/gk"), ("Science Formula", "/gk")],
"💼 Sarkari Naukri Notes": [("UP Police Notes", "https://upmsp.edu.in/"), ("SSC GD Notes", "https://ssc.gov.in/"), ("Railway Notes", "https://rrbapply.gov.in/")],
}# ===== HYBRID DAILY NOTES SYSTEM =====
# Tu yaha roj dalega - Ye sabse upar dikhega

MY_MANUAL_NOTES = {
    # Example - Isko badal ke apna dal de
    # "aaj-ka-tense": {"title": "Tense Trick - Aaj Ka", "cat": "English", "content": "Aaj maine Tense padhaya... Present Simple = Daily kaam"},
}

# Automatic wala - Tu na dale to ye apne aap chalega - 30 Din ka
AUTO_NOTES = [
    {"title": "Aaj Ka GK - Bharat Ki Rajdhani", "cat": "GK", "content": "Bharat ki Rajdhani New Delhi hai. GK roj yaad karo."},
    {"title": "Aaj Ka Vocab - 5 New Words", "cat": "English", "content": "1. Brave = Bahadur, 2. Honest = Imaandaar, 3. Quick = Tez, 4. Happy = Khush, 5. Strong = Mazboot"},
    {"title": "Aaj Ka Formula - Ganit", "cat": "Maths", "content": "Aaj ka Formula: (a+b)2 = a2 + 2ab + b2 - Isko 5 baar likh ke yaad karo."},
    {"title": "Aaj Ka Computer - CPU Kya Hai?", "cat": "Computer", "content": "CPU ko Computer ka Dimag kehte hai. CPU = Central Processing Unit."},
    {"title": "Aaj Ka SST - Mugal Kal", "cat": "SST", "content": "Akbar ko Akbar The Great kehte hai. Usne Din-i-Ilahi chalaya tha."},
    {"title": "Aaj Ka Current Affairs", "cat": "GK", "content": "Aaj ka Current Affairs - Roj Newspaper se 1 news yaha likhna hai."},
    {"title": "Aaj Ka Motivation", "cat": "Motivation", "content": "Roj 1 Ghanta padhoge to 1 Saal me Top karoge. Aaj se shuru karo!"},
]

# Logic - Manual hai to Manual, nahi to Automatic
import datetime
def get_today_note():
    if MY_MANUAL_NOTES:
        # Sabse last wala manual note le lo
        last_key = list(MY_MANUAL_NOTES.keys())[-1]
        d = MY_MANUAL_NOTES[last_key]
        return {"slug": last_key, "title": d["title"], "cat": d["cat"], "content": d["content"], "type": "Tera Wala 🔥"}
    else:
        day = datetime.date.today().timetuple().tm_yday
        d = AUTO_NOTES[day % len(AUTO_NOTES)]
        return {"slug": "auto", "title": d["title"], "cat": d["cat"], "content": d["content"], "type": "Automatic ✨"}

@app.route("/notes/<slug>")
def show_note(slug):
    if slug in MY_MANUAL_NOTES:
        d = MY_MANUAL_NOTES[slug]
        note = {"title": d["title"], "cat": d["cat"], "content": d["content"]}
    elif slug == "auto" or slug == "today":
        note = get_today_note()
    else:
        # Auto me se dhoondho
        note = get_today_note()
    return f"""
    <div style="max-width:700px;margin:20px auto;padding:20px;font-family:sans-serif">
    <a href="/">← Back</a>
    <h1>{note['title']}</h1>
    <p style="color:#666">Category: {note['cat']}</p>
    <hr>
    <p style="font-size:18px;line-height:1.8">{note['content']}</p>
    <br><a href="/" style="background:#2563eb;color:white;padding:10px 20px;border-radius:10px;text-decoration:none">Home Jao</a>
    </div>
    """
# ===== END HYBRID SYSTEM =====
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
    d["today"][today_str] = d["today"].get(today_str,0)+1
    save_data(d)
    return f"""
<div class="header"><h1>🔴 BHAI KI NEWS</h1><p><span class="live">● LIVE</span> Sirf Kaam Ki Khabar + Free Padhai</p><p>Made by Priyanshu Singh | Lucknow</p>
<p style="background:black;color:white;display:inline-block;padding:5px 12px;border-radius:20px;font-size:13px">👀 Aaj Aaye: {d["today"][today_str]} | Total: {d["total"]}</p>
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
.card img{width:100%;height:180px;object-fit:cover}
.card h3{font-size:17px;margin:12px 12px 5px}
.card p{font-size:14px;color:#555;margin:0 12px 10px;line-height:1.5}
.card a{display:block;color:#d60000;font-weight:bold;text-decoration:none;padding:0 12px 12px}
.lib-card{background:white;border-radius:12px;padding:15px;box-shadow:0 2px 8px #ccc}
.lib-card a{display:block;background:#d60000;color:white;text-align:center;padding:10px;border-radius:10px;text-decoration:none;font-weight:bold;margin-top:10px}
.box{background:white;margin:15px;padding:20px;border-radius:12px;box-shadow:0 2px 8px #ccc;line-height:1.7}
.footer{text-align:center;padding:20px;color:gray}
.footer a{color:#d60000;text-decoration:none;font-weight:bold;margin:0 8px}
input,select,textarea{width:100%;padding:12px;margin:8px 0;border:2px solid #ddd;border-radius:10px;font-size:16px}
.btn{background:#d60000;color:white;border:none;padding:13px;border-radius:10px;width:100%;font-weight:bold;font-size:16px;cursor:pointer}
@media(max-width:600px){.grid{grid-template-columns:1fr}}
</style>
"""

def footer():
    return """<div class="footer"><a href="/about">About Us</a> | <a href="/contact">Contact Us</a> | <a href="/privacy">Privacy Policy</a><br><br>© 2026 Bhai Ki News - Made by Priyanshu Singh, Lucknow</div>"""

@app.route('/admin', methods=['GET','POST'])
def admin():
    if request.method=='POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session.clear()
            session['admin'] = True
            session.permanent = True
            return redirect('/admin')
        else:
            return f"""<html><head><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}<div class="box"><h2>❌ Galat Password Bhai!</h2><a href="/admin">Fir se try karo</a></div>{footer()}</body></html>"""
    if not session.get('admin'):
        return f"""<html><head><title>Admin Login</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}<div class="box"><h2>🔐 Admin Login - Sirf Priyanshu Ke Liye</h2><form method="post"><input type="password" name="password" placeholder="Password dalo"><button class="btn">Login Karo</button></form></div>{footer()}</body></html>"""
    d = load_data()
    today_str = datetime.now().strftime("%Y-%m-%d")
    reads_html = "".join([f"<p>• {k} - {v} baar padha gaya</p>" for k,v in d.get("reads",{}).items()]) or "<p>Abhi kisi ne nahi padha</p>"
    my_html = "".join([f"<div class='lib-card'><h3>{a['title']} [{a['cat']}]</h3><p>{a['text']}</p></div>" for a in d.get("my_articles",[])])
    return f"""<html><head><title>Secret Dashboard</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}
<div class="box"><h2>👀 SECRET DASHBOARD - Sirf Tumhe Dikhega!</h2><p><b>Total Visitors:</b> {d.get('total',0)}</p><p><b>Aaj Aaye:</b> {d['today'].get(today_str,0)}</p><h3>Kya Kya Padha Gaya?</h3>{reads_html}</div>
<div class="box"><h2>✍️ Apne Man Se Article Dalo</h2><form action="/add-article" method="post"><input name="title" placeholder="Title - Jaise Aaj ka GK" required><select name="cat"><option>Math</option><option>Science</option><option>Hindi</option><option>News</option><option>Article</option></select><textarea name="text" rows="5" placeholder="Yaha apna Article likho..." required></textarea><button class="btn">Publish Karo 🚀</button></form></div>
<div class="box"><h2>📚 Tumhare Dale Hue Article</h2>{my_html or '<p>Abhi koi nahi hai</p>'}</div>
{footer()}</body></html>"""

@app.route('/add-article', methods=['POST'])
def add_article():
    if not session.get('admin'): return redirect('/admin')
    d = load_data()
    d.setdefault("my_articles",[]).insert(0, {"title":request.form.get('title'), "cat":request.form.get('cat'), "text":request.form.get('text')})
    save_data(d)
    return redirect('/admin')

@app.route('/about')
def about():
    body = """<div class="box"><h2>ℹ️ About Us - Bhai Ki News</h2><p>Namaste Dosto! Main <b>Priyanshu Singh, Lucknow</b> se hu.</p><p>Maine ye website isliye banayi taaki har bhai ko <b>Sirf Kaam Ki Khabar</b> aur <b>Free Padhai</b> ek hi jagah mil jaye.</p><p>Yaha milega: Daily News, NCERT Books, Previous Paper, Sarkari Naukri, GK aur Formula - Sab Free!</p></div>"""
    return f"""<html><head><title>About Us - Bhai Ki News</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}<div style="padding-top:10px">{body}</div>{footer()}</body></html>"""

@app.route('/contact')
def contact():
    body = """<div class="box"><h2>📞 Contact Us</h2><p>Koi sujhav ho to bataye!</p><p><b>Email:</b> priyanshu.bhaikinews@gmail.com</p><p><b>Address:</b> Lucknow, Uttar Pradesh, India</p></div>"""
    return f"""<html><head><title>Contact Us - Bhai Ki News</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}<div style="padding-top:10px">{body}</div>{footer()}</body></html>"""

@app.route('/privacy')
def privacy():
    body = """<div class="box"><h2>🔒 Privacy Policy</h2><p>1. Hum aapka koi personal data nahi lete.</p><p>2. Khabar padhne par aap us khabar wali site par jate hai.</p><p>3. Google Ads aane par Google aapko Ads dikha sakta hai.</p></div>"""
    return f"""<html><head><title>Privacy Policy - Bhai Ki News</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}<div style="padding-top:10px">{body}</div>{footer()}</body></html>"""

@app.route('/gk')
def gk():
    aaj = datetime.now()
    din_number = aaj.timetuple().tm_yday
    q, a = GK_LIST[din_number % len(GK_LIST)]
    body = f"""<div class="box"><h2>🧠 Aaj ka GK Question - {aaj.strftime('%d %B %Y')}</h2><h3>Q: {q}</h3><p><b>Answer:</b> {a}</p><p style="color:gray;font-size:13px">Kal naya sawaal apne aap aayega! Roz 1 naya GK!</p></div><h2>📐 Saare Formula</h2><div class="grid">"""
    for name, val in FORMULAS:
        body += f"""<div class="lib-card"><h3 style="margin:0">{name}</h3><p style="font-size:18px;font-weight:bold;color:#d60000">{val}</p></div>"""
    body += "</div>"
    return f"""<html><head><title>Aaj ka GK Question aur Formula - Bhai Ki News</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}<div style="padding-top:10px">{body}</div>{footer()}</body></html>"""

@app.route('/library')
def library():
    d = load_data()
    body = "<h2 style='text-align:center'>📚 Padhai Library - Sab Free Hai Bhai!</h2>"
    body += "<h2>✍️ Bhai Ke Apne Article - Math / Science / Hindi</h2><div class='grid'>"
    for title, cat, text in MY_NEW_ARTICLES:
        body += f"""<div class="lib-card"><h3 style="margin:0">{title}</h3><p>{text}</p><span style="background:#ffe5e5;padding:4px 10px;border-radius:20px;font-size:12px">{cat}</span></div>"""
    for a in d.get("my_articles",[]):
        body += f"""<div class="lib-card" style="border:2px solid #d60000"><h3 style="margin:0">{a['title']}</h3><p>{a['text']}</p><span style="background:yellow;padding:4px 10px;border-radius:20px;font-size:12px">{a['cat']} - NAYA!</span></div>"""
    body += "</div>"
    for cat, items in LIBRARY.items():
        body += f"<h2>{cat}</h2><div class='grid'>"
        for name, link in items:
            body += f"""<div class="lib-card"><h3 style="margin:0">{name}</h3><a href="{link}" target="_blank">Khol ke Padho →</a></div>"""
        body += "</div>"
    return f"""<html><head><title>Padhai Library - Free NCERT Books, Previous Paper</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}<div style="padding-top:10px">{body}</div>{footer()}</body></html>"""

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
<html><head><title>Bhai Ki News - Kaam Ki Khabar, Free Padhai, GK, Sarkari Naukri</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head>
<body>
{header()}
<div class="search-box">
<form class="search-row" action="/" method="get"><input type="text" name="q" value="{search_val}" placeholder="🔍 Kuch bhi likho... Army, Gold, Padhai..."><button type="submit">Search</button></form>
<div class="tags"><a href="/?q=Army">🪖 Army</a><a href="/?q=Gold">🪙 Gold</a><a href="/?q=Padhai Exam">📚 Padhai</a><a href="/?q=Cricket">🏏 Cricket</a><a href="/?q=Job Naukri">💼 Job</a><a href="/?q=UP Lucknow">📍 UP</a><a href="/library">📚 Library Khol</a><a href="/gk">🧠 Aaj ka GK</a></div>
</div>
{body}
{footer()}
</body></html>
"""
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
