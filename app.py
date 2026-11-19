
import feedparser, re, hashlib, urllib.parse, random, os, json
from flask import Flask, request, redirect, url_for, session
from datetime import datetime
app = Flask(__name__)
app.secret_key = "bhai-ki-news-secret-123"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Priyanshu@123")
DATA_FILE = "bhai_data.json"
def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                d = json.load(f)
                if not isinstance(d, dict): d = {}
                d.setdefault("total", 0)
                d.setdefault("today", {})
                d.setdefault("reads", {})
                d.setdefault("my_articles", [])
                return d
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
GK_LIST = [("Lal Kila kaha hai?", "Delhi me"),("Taj Mahal kaha hai?", "Agra me"),("Aasman Neela kyu hai?", "Neela rang zyada bikharne se"),("23 x 11 = ?", "253 - Trick se!"),("Bharat ka Rashtriya Pashu kaun hai?", "Bagh")]
GK_BANK = GK_LIST + [("Rashtriya Pakshi?", "Mor"),("Ganga kaha se?", "Gangotri se"),("Bharat ki Rajdhani?", "New Delhi"),("UP ki Rajdhani?", "Lucknow"),("Sabse Bada Rajya?", "Rajasthan"),("Computer ka Pita?", "Charles Babbage"),("Pani ka Formula?", "H2O"),("Samvidhan kab lagu?", "26 Jan 1950"),("Gandhi janm kab?", "2 Oct 1869"),("Pehla Rashtrapati?", "Dr. Rajendra Prasad"),("Chand par pehla?", "Neil Armstrong"),("Sabse bada grah?", "Brihaspati"),("Sharir me haddi?", "206"),("Sabse bada Mahasagar?", "Prashant"),("Kutub Minar kaha?", "Delhi me"),("Rashtriya Phool?", "Kamal"),("Rashtriya Fal?", "Aam"),("Jai Hind kisne?", "Netaji Subhash Chandra Bose"),("Vande Mataram kisne?", "Bankim Chandra"),("Jana Gana Mana kisne?", "Rabindranath Tagore"),("Lucknow kis nadi?", "Gomti"),("Ayodhya kis nadi?", "Saryu"),("Taj kisne banwaya?", "Shahjahan"),("1 GB = ?", "1024 MB"),("Pehli Rail kab?", "1853 Mumbai-Thane"),("Sabse bada Desh?", "Russia"),("Hindi Diwas kab?", "14 Sep"),("Shikshak Diwas kab?", "5 Sep"),("Bachcho ka Din kab?", "14 Nov"),("Yoga Diwas kab?", "21 June"),("Sabse tez Janwar?", "Cheetah"),("Sabse bada Janwar?", "Blue Whale"),("Heart Beat kitni?", "72 per minute"),("IT City?", "Bengaluru"),("UP ka Kila?", "Jhansi Kila"),("Char Minar kaha?", "Hyderabad"),("India Gate kaha?", "New Delhi"),("Kitne Rajya?", "28 + 8 UT"),("Gandhi pura naam?", "Mohandas Karamchand Gandhi"),("Sabse unchi choti?", "Mount Everest"),("Loh Purush?", "Sardar Patel"),("Pehla PM?", "Jawaharlal Nehru"),("Suraj paas grah?", "Budh"),("Khoon lal kyu?", "Haemoglobin se"),("Cricket Janm kaha?", "England"),("Oxygen kisne?", "Joseph Priestley"),("Qutub kisne?", "Qutubuddin Aibak"),("Internet pura naam?", "Interconnected Network"),("Sabse lamba Pul?", "Bhupen Hazarika Setu"),("Tiranga me rang?", "3 + Chakra"),("National Anthem?", "Jana Gana Mana"),("Rashtriya Khel?", "Hockey"),("CPU kya?", "Central Processing Unit"),("Sabse lambi Nadi?", "Ganga"),("Pehla Up-Rashtrapati?", "Dr. S. Radhakrishnan")]
def get_today_gk():
    n=datetime.now().timetuple().tm_yday
    s=(n*15)%len(GK_BANK)
    return [GK_BANK[(s+i)%len(GK_BANK)] for i in range(15)]
FORMULAS = [("(a+b)²", "(a² + 2ab + b²)"),("Area - Circle", "πr²"),("Speed", "Distance / Time"),("11 se Guna", "23x11 = 253 Trick")]
LIBRARY = {
    "📚 Class 9 - NCERT Books": [("Class 9 Maths Book", "https://ncert.nic.in/textbook.php"),("Class 9 Science Book", "https://ncert.nic.in/textbook.php"),("Class 9 Hindi Book", "https://ncert.nic.in/textbook.php"),("Class 9 SST Book", "https://ncert.nic.in/textbook.php")],
    "📚 Class 10 - NCERT Books": [("Class 10 Maths Book", "https://ncert.nic.in/textbook.php"),("Class 10 Science Book", "https://ncert.nic.in/textbook.php"),("Class 10 Hindi Book", "https://ncert.nic.in/textbook.php"),("Class 10 SST Book", "https://ncert.nic.in/textbook.php")],
    "📚 Class 11 - NCERT Books": [("Class 11 Physics", "https://ncert.nic.in/textbook.php"),("Class 11 Chemistry", "https://ncert.nic.in/textbook.php"),("Class 11 Maths", "https://ncert.nic.in/textbook.php"),("Class 11 Biology", "https://ncert.nic.in/textbook.php")],
    "📚 Class 12 - NCERT Books": [("Class 12 Physics", "https://ncert.nic.in/textbook.php"),("Class 12 Chemistry", "https://ncert.nic.in/textbook.php"),("Class 12 Maths", "https://ncert.nic.in/textbook.php"),("Class 12 Biology", "https://ncert.nic.in/textbook.php")],
    "✅ Class 9 - Notes + Answers": [("Maths Notes + Answers - 9", "https://www.learncbse.in/ncert-solutions-class-9-maths/"),("Science Notes + Answers - 9", "https://www.learncbse.in/ncert-solutions-class-9-science/"),("Hindi Notes - 9", "https://ncert.nic.in/textbook.php")],
    "✅ Class 10 - Notes + Answers": [("Maths Notes + Answers - 10", "https://www.learncbse.in/ncert-solutions-class-10-maths/"),("Science Notes + Answers - 10", "https://www.learncbse.in/ncert-solutions-class-10-science/"),("Hindi Notes + Answers - 10", "https://www.learncbse.in/ncert-solutions-class-10-hindi/"),("SST Notes - 10", "https://www.learncbse.in/ncert-solutions-class-10-social-science/")],
    "✅ Class 11 - Notes + Answers": [("Physics Notes + Answers - 11", "https://www.learncbse.in/ncert-solutions-class-11-physics/"),("Chemistry Notes + Answers - 11", "https://www.learncbse.in/ncert-solutions-class-11-chemistry/"),("Maths Notes + Answers - 11", "https://www.learncbse.in/ncert-solutions-class-11-maths/"),("Biology Notes - 11", "https://www.learncbse.in/ncert-solutions-class-11-biology/")],
    "✅ Class 12 - Notes + Answers": [("Physics Notes + Answers - 12", "https://www.learncbse.in/ncert-solutions-class-12-physics/"),("Chemistry Notes + Answers - 12", "https://www.learncbse.in/ncert-solutions-class-12-chemistry/"),("Maths Notes + Answers - 12", "https://www.learncbse.in/ncert-solutions-class-12-maths/"),("Biology Notes + Answers - 12", "https://www.learncbse.in/ncert-solutions-class-12-biology/")],
    "📝 UP Board Paper 9-12": [("UP Board Class 10 Paper", "https://upmsp.edu.in/"),("UP Board Class 12 Paper", "https://upmsp.edu.in/"),("CBSE Paper", "https://cbse.gov.in/")],
    "🎯 Sarkari Exam Notes": [("SSC GD / MTS Notes", "https://ssc.gov.in/"),("Police / Army Bharti", "https://uppbpb.gov.in/"),("Railway Notes", "https://www.rrbapply.gov.in/")],
}
MY_NEW_ARTICLES = [("Math - 11 se Guna Trick", "Math", "23 x 11 = 253. 2 aur 3 ko alag karo, beech me 2+3=5 daal do!"),("Science - Aasman Neela Kyu?", "Science", "Suraj ki roshni me 7 rang hote hai, Neela sabse zyada bikhar ta hai!"),("Hindi - Mera Gaon Nibandh", "Hindi", "Mera gaon mera garv hai. Yaha ki hawa saaf hai, log madad karte hai!"),("Best Article - Mehnat Kabhi Bekar Nahi Jaati", "Article", "Kanpur ke Priyanshu ne apni Website bana di. Mehnat wale ko koi nahi rok sakta!")]
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
    return f"""<div class="header"><h1>🔴 BHAI KI NEWS</h1><p><span class="live">● LIVE</span> Sirf Kaam Ki Khabar + Free Padhai</p><p>Made by Priyanshu Singh | Lucknow</p><p style="background:black;color:white;display:inline-block;padding:5px 12px;border-radius:20px;font-size:13px">👀 Aaj Aaye: {d["today"][today_str]} | Total: {d["total"]}</p><div style="margin-top:12px;display:flex;gap:8px;justify-content:center;flex-wrap:wrap"><a href="/" style="background:white;color:#d60000;padding:8px 14px;border-radius:20px;text-decoration:none;font-weight:bold">📰 News</a><a href="/library" style="background:yellow;color:black;padding:8px 14px;border-radius:20px;text-decoration:none;font-weight:bold">📚 Padhai Library</a><a href="/gk" style="background:white;color:#d60000;padding:8px 14px;border-radius:20px;text-decoration:none;font-weight:bold">🧠 GK</a><a href="/about" style="background:white;color:#d60000;padding:8px 14px;border-radius:20px;text-decoration:none;font-weight:bold">ℹ️ About</a><a href="/admin" style="background:black;color:white;padding:8px 14px;border-radius:20px;text-decoration:none;font-weight:bold">🔐 Admin</a></div></div>"""
def style():
    return """<style>body{font-family:Arial;background:#f2f2f2;margin:0}.header{background:#d60000;color:white;padding:20px;text-align:center}.header h1{margin:0;font-size:32px}.live{background:yellow;color:black;padding:3px 10px;border-radius:20px;font-weight:bold}.search-box{padding:15px;background:white;position:sticky;top:0;z-index:9;box-shadow:0 2px 5px #ccc}.search-row{display:flex;gap:10px}.search-row input{flex:1;padding:12px;font-size:16px;border:2px solid #d60000;border-radius:25px;outline:none}.search-row button{background:#d60000;color:white;border:none;padding:12px 20px;border-radius:25px;font-size:16px;font-weight:bold}.tags{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.tags a{background:#ffe5e5;color:#d60000;padding:7px 14px;border-radius:20px;text-decoration:none;font-weight:bold;font-size:14px}h2{padding:0 15px;color:#d60000}.grid{display:grid;grid-template-columns:1fr 1fr;gap:15px;padding:0 15px 20px}.card{background:white;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px #ccc}.card img{width:100%;height:180px;object-fit:cover}.card h3{font-size:17px;margin:12px 12px 5px}.card p{font-size:14px;color:#555;margin:0 12px 10px;line-height:1.5}.card a{display:block;color:#d60000;font-weight:bold;text-decoration:none;padding:0 12px 12px}.lib-card{background:white;border-radius:12px;padding:15px;box-shadow:0 2px 8px #ccc}.lib-card a{display:block;background:#d60000;color:white;text-align:center;padding:10px;border-radius:10px;text-decoration:none;font-weight:bold;margin-top:10px}.box{background:white;margin:15px;padding:20px;border-radius:12px;box-shadow:0 2px 8px #ccc;line-height:1.7}.footer{text-align:center;padding:20px;color:gray}.footer a{color:#d60000;text-decoration:none;font-weight:bold;margin:0 8px}input,select,textarea{width:100%;padding:12px;margin:8px 0;border:2px solid #ddd;border-radius:10px;font-size:16px}.btn{background:#d60000;color:white;border:none;padding:13px;border-radius:10px;width:100%;font-weight:bold;font-size:16px;cursor:pointer}.gk-num{background:#d60000;color:white;width:28px;height:28px;display:inline-flex;align-items:center;justify-content:center;border-radius:50%;font-size:14px;margin-right:8px}@media(max-width:600px){.grid{grid-template-columns:1fr}}</style>"""
def footer():
    return """<div class="footer"><a href="/ßabout">About Us</a> | <a href="/contact">Contact Us</a> | <a href="/privacy">Privacy Policy</a><br><br>© 2026 Bhai Ki News - Made by Priyanshu Singh, Lucknow</div>"""@app.route('/admin', methods=['GET','POST'])
def admin():
    if request.method=='POST':
        if request.form.get('password')==ADMIN_PASSWORD:
            session['admin']=True
            return redirect('/admin')
        else:
            return f"""<html><head><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}<div class="box"><h2>❌ Galat Password Bhai!</h2><a href="/admin">Fir se try karo</a></div>{footer()}</body></html>"""
    if not session.get('admin'):
        return f"""<html><head><title>Admin Login</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}<div class="box"><h2>🔐 Admin Login - Sirf Priyanshu Ke Liye</h2><form method="post"><input type="password" name="password" placeholder="Password dalo"><button class="btn">Login Karo</button></form></div>{footer()}</body></html>"""
    d = load_data()
    today_str = datetime.now().strftime("%Y-%m-%d")
    reads_html = "".join([f"<p>• {k} - {v} baar padha gaya</p>" for k,v in d.get("reads",{}).items()]) or "<p>Abhi kisi ne nahi padha</p>"
    my_html = "".join([f"<div class='lib-card'><h3>{a['title']} [{a['cat']}]</h3><p>{a['text']}</p></div>" for a in d.get("my_articles",[])])
    return f"""<html><head><title>Secret Dashboard</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}<div class="box"><h2>👀 SECRET DASHBOARD</h2><p><b>Total Visitors:</b> {d.get('total',0)}</p><p><b>Aaj Aaye:</b> {d['today'].get(today_str,0)}</p><h3>Kya Kya Padha Gaya?</h3>{reads_html}</div><div class="box"><h2>✍️ Apne Man Se Article Dalo</h2><form action="/add-article" method="post"><input name="title" placeholder="Title" required><select name="cat"><option>Math</option><option>Science</option><option>Hindi</option><option>News</option><option>Article</option></select><textarea name="text" rows="5" placeholder="Yaha apna Article likho..." required></textarea><button class="btn">Publish Karo 🚀</button></form></div><div class="box"><h2>📚 Tumhare Dale Hue Article</h2>{my_html or '<p>Abhi koi nahi hai</p>'}</div>{footer()}</body></html>"""
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
    return f"""<html><head><title>About Us</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}<div style="padding-top:10px">{body}</div>{footer()}</body></html>"""
@app.route('/contact')
def contact():
    body = """<div class="box"><h2>📞 Contact Us</h2><p>Koi sujhav ho to bataye!</p><p><b>Email:</b> priyanshu.bhaikinews@gmail.com</p><p><b>Address:</b> Lucknow, Uttar Pradesh, India</p></div>"""
    return f"""<html><head><title>Contact Us</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}<div style="padding-top:10px">{body}</div>{footer()}</body></html>"""
@app.route('/privacy')
def privacy():
    body = """<div class="box"><h2>🔒 Privacy Policy</h2><p>1. Hum aapka koi personal data nahi lete.</p><p>2. Khabar padhne par aap us khabar wali site par jate hai.</p><p>3. Google Ads aane par Google aapko Ads dikha sakta hai.</p></div>"""
    return f"""<html><head><title>Privacy Policy</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}<div style="padding-top:10px">{body}</div>{footer()}</body></html>"""
@app.route('/gk')
def gk():
    tg=get_today_gk()
    ds=datetime.now().strftime("%d %B %Y")
    body = f"""<div class="box" style="background:#e8ffe8"><h2>🧠 Aaj ka GK - {ds} - 15 Question</h2><p><b>🔥 Aaj ke 15 - Kal naye aayenge! Roz yaha aake yaad karo!</b></p></div>"""
    for i,(q,a) in enumerate(tg,1):
        body += f"""<div class="box"><span class="gk-num">{i}</span><b>Q: {q}</b><br><span style="color:green">✅ Answer: {a}</span></div>"""
    body += """<h2>📐 Saare Formula</h2><div class="grid">"""
    for name, val in FORMULAS:
        body += f"""<div class="lib-card"><h3 style="margin:0">{name}</h3><p style="font-size:18px;font-weight:bold;color:#d60000">{val}</p></div>"""
    body += "</div>"
    return f"""<html><head><title>Aaj ka GK - 15 Question</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}<div style="padding-top:10px">{body}</div>{footer()}</body></html>"""
@app.route('/library')
def library():
    d = load_data()
    body = "<h2 style='text-align:center'>📚 Padhai Library - Class 9 se 12 Tak - Sab Free Hai Bhai!</h2><div class='box' style='background:#fff3cd'><b>👉 Kaise Padhe?</b> Apni Class pe click karo -> Notes / Answers khulega -> Free me padho!</div>"
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
    return f"""<html><head><title>Padhai Library - Class 9 to 12</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}<div style="padding-top:10px">{body}</div>{footer()}</body></html>"""
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
    return f"""<html><head><title>Bhai Ki News - Kaam Ki Khabar, Free Padhai, GK, Sarkari Naukri</title><meta name="viewport" content="width=device-width, initial-scale=1">{style()}</head><body>{header()}<div class="search-box"><form class="search-row" action="/" method="get"><input type="text" name="q" value="{search_val}" placeholder="🔍 Kuch bhi likho... Army, Gold, Padhai..."><button type="submit">Search</button></form><div class="tags"><a href="/?q=Army">🪖 Army</a><a href="/?q=Gold">🪙 Gold</a><a href="/?q=Padhai Exam">📚 Padhai</a><a href="/?q=Cricket">🏏 Cricket</a><a href="/?q=Job Naukri">💼 Job</a><a href="/?q=UP Lucknow">📍 UP</a><a href="/library">📚 Library Khol</a><a href="/gk">🧠 Aaj ka GK</a></div></div>{body}{footer()}</body></html>"""
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
