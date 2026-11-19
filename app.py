import feedparser, re, hashlib, urllib.parse, os, json, time
from flask import Flask, request, redirect, session
from datetime import datetime
app = Flask(__name__)
app.secret_key = "bhai-ki-news-secret-123"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Priyanshu@123")
DATA_FILE = "bhai_data.json"
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                d=json.load(f)
                d.setdefault("total",0); d.setdefault("today",{}); d.setdefault("my_articles",[]); d.setdefault("online",[])
                return d
        except: pass
    return {"total":0,"today":{},"my_articles":[],"online":[]}
def save_data(d):
    with open(DATA_FILE,"w") as f: json.dump(d,f)
FEEDS = {
 "🔥 Top Khabar": "https://news.google.com/rss?hl=hi&gl=IN&ceid=IN:hi",
 "🏏 Cricket": "https://news.google.com/rss/search?q=Cricket&hl=hi&gl=IN&ceid=IN:hi",
 "💼 Naukri": "https://news.google.com/rss/search?q=Sarkari Naukri&hl=hi&gl=IN&ceid=IN:hi",
 "📚 Padhai": "https://news.google.com/rss/search?q=Exam Padhai&hl=hi&gl=IN&ceid=IN:hi",
 "📍 UP News": "https://news.google.com/rss/search?q=Uttar Pradesh Lucknow&hl=hi&gl=IN&ceid=IN:hi",
 "🌦️ Mausam": "https://news.google.com/rss/search?q=Mausam&hl=hi&gl=IN&ceid=IN:hi",
}
GK_BANK = [("Lal Kila kaha hai?","Delhi me"),("Taj Mahal kaha hai?","Agra me"),("Aasman Neela kyu hai?","Neela rang zyada bikharne se"),("23 x 11 = ?","253 - Trick se!"),("Bharat ka Rashtriya Pashu?","Bagh"),("Rashtriya Pakshi?","Mor"),("Ganga kaha se?","Gangotri se"),("Bharat ki Rajdhani?","New Delhi"),("UP ki Rajdhani?","Lucknow"),("Sabse Bada Rajya?","Rajasthan"),("Computer ka Pita?","Charles Babbage"),("Pani ka Formula?","H2O"),("Samvidhan kab lagu?","26 Jan 1950"),("Gandhi janm kab?","2 Oct 1869"),("Pehla Rashtrapati?","Dr. Rajendra Prasad"),("Chand par pehla?","Neil Armstrong"),("Sabse bada grah?","Brihaspati"),("Sharir me haddi?","206"),("Sabse bada Mahasagar?","Prashant"),("Kutub Minar kaha?","Delhi me"),("Rashtriya Phool?","Kamal"),("Rashtriya Fal?","Aam"),("Jai Hind kisne?","Netaji Subhash Chandra Bose"),("Vande Mataram kisne?","Bankim Chandra"),("Jana Gana Mana kisne?","Rabindranath Tagore"),("Lucknow kis nadi?","Gomti"),("Ayodhya kis nadi?","Saryu"),("Taj kisne banwaya?","Shahjahan"),("1 GB = ?","1024 MB"),("Pehli Rail kab?","1853 Mumbai-Thane"),("Sabse bada Desh?","Russia"),("Hindi Diwas kab?","14 Sep"),("Shikshak Diwas kab?","5 Sep"),("Bachcho ka Din kab?","14 Nov"),("Yoga Diwas kab?","21 June"),("Sabse tez Janwar?","Cheetah"),("Sabse bada Janwar?","Blue Whale"),("Heart Beat kitni?","72 per minute"),("IT City?","Bengaluru"),("UP ka Kila?","Jhansi Kila"),("Char Minar kaha?","Hyderabad"),("India Gate kaha?","New Delhi"),("Kitne Rajya?","28 + 8 UT"),("Gandhi pura naam?","Mohandas Karamchand Gandhi"),("Sabse unchi choti?","Mount Everest"),("Loh Purush?","Sardar Patel"),("Pehla PM?","Jawaharlal Nehru"),("Suraj paas grah?","Budh"),("Khoon lal kyu?","Haemoglobin se"),("Cricket Janm kaha?","England"),("Oxygen kisne?","Joseph Priestley"),("Qutub kisne?","Qutubuddin Aibak"),("Internet pura naam?","Interconnected Network"),("Sabse lamba Pul?","Bhupen Hazarika Setu"),("Tiranga me rang?","3 + Chakra"),("National Anthem?","Jana Gana Mana")]
def get_today_gk():
    n=datetime.now().timetuple().tm_yday
    s=(n*15)%len(GK_BANK)
    return [GK_BANK[(s+i)%len(GK_BANK)] for i in range(15)]
FORMULAS=[("(a+b)²","(a²+2ab+b²)"),("Area-Circle","πr²"),("Speed","Distance/Time"),("11 se Guna","23x11=253 Trick")]
LIBRARY={
 "📚 NCERT Books":[("Class 10 Maths","https://ncert.nic.in/"),("Class 10 Science","https://ncert.nic.in/")],
 "📝 Previous Paper":[("UP Board Paper","https://upmsp.edu.in/"),("CBSE Paper","https://cbse.gov.in/")],
 "📚 Class 9 Books":[("Class 9 Maths","https://ncert.nic.in/textbook.php"),("Class 9 Science","https://ncert.nic.in/textbook.php"),("Class 9 Hindi","https://ncert.nic.in/textbook.php"),("Class 9 SST","https://ncert.nic.in/textbook.php")],
 "📚 Class 10 Books":[("Class 10 Maths","https://ncert.nic.in/textbook.php"),("Class 10 Science","https://ncert.nic.in/textbook.php"),("Class 10 Hindi","https://ncert.nic.in/textbook.php"),("Class 10 SST","https://ncert.nic.in/textbook.php")],
 "📚 Class 11 Books":[("Class 11 Physics","https://ncert.nic.in/textbook.php"),("Class 11 Chemistry","https://ncert.nic.in/textbook.php"),("Class 11 Maths","https://ncert.nic.in/textbook.php"),("Class 11 Biology","https://ncert.nic.in/textbook.php")],
 "📚 Class 12 Books":[("Class 12 Physics","https://ncert.nic.in/textbook.php"),("Class 12 Chemistry","https://ncert.nic.in/textbook.php"),("Class 12 Maths","https://ncert.nic.in/textbook.php"),("Class 12 Biology","https://ncert.nic.in/textbook.php")],
 "✅ Class 9 Solutions":[("Maths Sol-9","https://www.learncbse.in/ncert-solutions-class-9-maths/"),("Science Sol-9","https://www.learncbse.in/ncert-solutions-class-9-science/")],
 "✅ Class 10 Solutions":[("Maths Sol-10","https://www.learncbse.in/ncert-solutions-class-10-maths/"),("Science Sol-10","https://www.learncbse.in/ncert-solutions-class-10-science/")],
 "✅ Class 11 Solutions":[("Physics Sol-11","https://www.learncbse.in/ncert-solutions-class-11-physics/"),("Chemistry Sol-11","https://www.learncbse.in/ncert-solutions-class-11-chemistry/"),("Maths Sol-11","https://www.learncbse.in/ncert-solutions-class-11-maths/")],
 "✅ Class 12 Solutions":[("Physics Sol-12","https://www.learncbse.in/ncert-solutions-class-12-physics/"),("Chemistry Sol-12","https://www.learncbse.in/ncert-solutions-class-12-chemistry/"),("Maths Sol-12","https://www.learncbse.in/ncert-solutions-class-12-maths/"),("Biology Sol-12","https://www.learncbse.in/ncert-solutions-class-12-biology/")],
 "🎯 Sarkari Exam":[("SSC Notes","https://ssc.gov.in/"),("Police Bharti","https://uppbpb.gov.in/"),("Railway","https://www.rrbapply.gov.in/")],
}
MY_NEW_ARTICLES=[("Math - 11 se Guna Trick","Math","23 x 11 = 253. 2 aur 3 ko alag karo, beech me 2+3=5 daal do!"),("Science - Aasman Neela Kyu?","Science","Suraj ki roshni me 7 rang hote hai, Neela sabse zyada bikhar ta hai!"),("Hindi - Mera Gaon Nibandh","Hindi","Mera gaon mera garv hai. Yaha ki hawa saaf hai, log madad karte hai!"),("Best Article - Mehnat Kabhi Bekar Nahi Jaati","Article","Kanpur ke Priyanshu ne apni Website bana di. Mehnat wale ko koi nahi rok sakta!")]
def clean(t):
    t=re.sub('<[^<]+?>','',t or '')
    return t[:180]+"..." if len(t)>180 else t
def get_img(entry,title):
    try:
        if 'media_content' in entry: return entry.media_content[0]['url']
        if 'links' in entry:
            for l in entry.links:
                if 'image' in l.get('type',''): return l['href']
    except: pass
    h=hashlib.md5(title.encode()).hexdigest()
    return f"https://picsum.photos/seed/{h}/600/400"
def make_cards(feed,seen,limit=15):
    cards="";c=0
    for e in feed.entries:
        if c>=limit: break
        t=e.get('title','').strip(); link=e.get('link','')
        if t in seen or link in seen or not t: continue
        seen.add(t); seen.add(link)
        img=get_img(e,t); desc=clean(e.get('summary','') or e.get('description',''))
        cards+=f"""<div class="card"><img src="{img}"><h3>{t}</h3><p>{desc}</p><a href="{link}" target="_blank">Poori Khabar Padhein →</a></div>"""
        c+=1
    return cardsdef header():
    d=load_data(); d["total"]=d.get("total",0)+1
    ts=datetime.now().strftime("%Y-%m-%d")
    d["today"][ts]=d["today"].get(ts,0)+1
    now=time.time()
    d["online"]=[t for t in d.get("online",[]) if now-t<120]
    d["online"].append(now); save_data(d)
    return f"""<div class="header"><h1>🔴 BHAI KI NEWS</h1><p><span class="live">● LIVE</span> Sirf Kaam Ki Khabar + Free Padhai</p><p>Made by Priyanshu Singh | Lucknow</p><p style="background:black;color:white;display:inline-block;padding:5px 12px;border-radius:20px;font-size:13px">👀 Aaj: {d["today"][ts]} | Total: {d["total"]} | 🟢 Online: {len(d["online"])}</p><div style="margin-top:12px;display:flex;gap:8px;justify-content:center;flex-wrap:wrap"><a href="/" style="background:white;color:#d60000;padding:8px 14px;border-radius:20px;text-decoration:none;font-weight:bold">📰 News</a><a href="/library" style="background:yellow;color:black;padding:8px 14px;border-radius:20px;text-decoration:none;font-weight:bold">📚 Padhai Library</a><a href="/gk" style="background:white;color:#d60000;padding:8px 14px;border-radius:20px;text-decoration:none;font-weight:bold">🧠 GK</a><a href="/about" style="background:white;color:#d60000;padding:8px 14px;border-radius:20px;text-decoration:none;font-weight:bold">ℹ️ About</a><a href="/admin" style="background:black;color:white;padding:8px 14px;border-radius:20px;text-decoration:none;font-weight:bold">🔐 Admin</a></div></div>"""
def style():
    return """<style>body{font-family:Arial;background:#f2f2f2;margin:0}.header{background:#d60000;color:white;padding:20px;text-align:center}.header h1{margin:0;font-size:32px}.live{background:yellow;color:black;padding:3px 10px;border-radius:20px;font-weight:bold}.search-box{padding:15px;background:white;position:sticky;top:0;z-index:9;box-shadow:0 2px 5px #ccc}.search-row{display:flex;gap:10px}.search-row input{flex:1;padding:12px;font-size:16px;border:2px solid #d60000;border-radius:25px;outline:none}.search-row button{background:#d60000;color:white;border:none;padding:12px 20px;border-radius:25px;font-size:16px;font-weight:bold}.tags{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.tags a{background:#ffe5e5;color:#d60000;padding:7px 14px;border-radius:20px;text-decoration:none;font-weight:bold;font-size:14px}h2{padding:0 15px;color:#d60000}.grid{display:grid;grid-template-columns:1fr 1fr;gap:15px;padding:0 15px 20px}.card{background:white;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px #ccc}.card img{width:100%;height:220px;object-fit:cover}.card h3{font-size:18px;margin:12px 12px 5px;line-height:1.4}.card p{font-size:14px;color:#555;margin:0 12px 10px;line-height:1.5}.card a{display:block;color:#d60000;font-weight:bold;text-decoration:none;padding:0 12px 12px}.lib-card{background:white;border-radius:12px;padding:15px;box-shadow:0 2px 8px #ccc}.lib-card a{display:block;background:#d60000;color:white;text-align:center;padding:10px;border-radius:10px;text-decoration:none;font-weight:bold;margin-top:10px}.box{background:white;margin:15px;padding:20px;border-radius:12px;box-shadow:0 2px 8px #ccc;line-height:1.7}.footer{text-align:center;padding:20px;color:gray}.footer a{color:#d60000;text-decoration:none;font-weight:bold;margin:0 8px}input,select,textarea{width:100%;padding:12px;margin:8px 0;border:1px solid #ccc;border-radius:10px;box-sizing:border-box;font-size:15px}.btn{background:#d60000;color:white;border:none;padding:12px;border-radius:10px;font-weight:bold;font-size:16px;cursor:pointer}.gk-num{background:#d60000;color:white;width:28px;height:28px;display:inline-flex;align-items:center;justify-content:center;border-radius:50%;font-size:14px;margin-right:8px}@media(max-width:600px){.grid{grid-template-columns:1fr}}</style>"""
def footer():
    return """<div class="footer"><a href="/">Home</a> | <a href="/library">Library</a> | <a href="/gk">GK</a> | <a href="/about">About Us</a> | <a href="/contact">Contact Us</a> | <a href="/privacy">Privacy Policy</a><br><br>© 2026 Bhai Ki News - Made by Priyanshu Singh, Lucknow</div></body></html>"""
def search_box(q=""):
    return f"""<div class="search-box"><form action="/" method="get"><div class="search-row"><input name="q" value="{q}" placeholder="Khabar khojo... jaise Cricket, Naukri"><button>Search 🔍</button></div></form><div class="tags"><a href="/?q=Cricket">🏏 Cricket</a><a href="/?q=Naukri">💼 Naukri</a><a href="/?q=UP">📍 UP News</a><a href="/?q=Weather">🌦️ Mausam</a><a href="/library">📚 Library</a><a href="/gk">🧠 Aaj ka GK</a></div></div>"""
@app.route("/")
def home():
    q=request.args.get("q","").strip(); h=header(); s=style()
    html=f"""<html><head><title>Bhai Ki News</title><meta name="viewport" content="width=device-width, initial-scale=1">{s}</head><body>{h}{search_box(q)}"""
    d=load_data(); all_my=MY_NEW_ARTICLES+[(a.get("title",""),a.get("cat",""),a.get("text","")) for a in d.get("my_articles",[])]
    if not q or any(q.lower() in (t+" "+c+" "+x).lower() for t,c,x in all_my):
        html+="<h2>✍️ Bhai Ke Apne Article</h2><div class='grid'>"
        for t,c,x in all_my:
            if q and q.lower() not in (t+" "+c+" "+x).lower(): continue
            html+=f"""<div class="card"><img src="https://picsum.photos/seed/{hashlib.md5(t.encode()).hexdigest()}/600/400"><h3>{t}</h3><p><b>{c}</b> - {x[:150]}</p></div>"""
        html+="</div>"
    seen=set()
    for name,url in FEEDS.items():
        if q:
            url=f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=hi&gl=IN&ceid=IN:hi"
            cards=make_cards(feedparser.parse(url),seen,limit=20); html+=f"<h2>🔍 Search: {q}</h2><div class='grid'>{cards}</div>"; break
        try:
            cards=make_cards(feedparser.parse(url),seen,limit=15); html+=f"<h2>{name}</h2><div class='grid'>{cards}</div>"
        except: pass
    return html+footer()
@app.route("/library")
def library():
    h=header(); s=style(); html=f"""<html><head><title>Library</title><meta name="viewport" content="width=device-width, initial-scale=1">{s}</head><body>{h}<h2>📚 Library - Class 9 se 12 Tak - Sab Free!</h2><div class="grid">"""
    for cat,items in LIBRARY.items():
        for title,link in items: html+=f"""<div class="lib-card"><h3>{cat}</h3><p>{title}</p><a href="{link}" target="_blank">Khol ke Padho →</a></div>"""
    html+="</div><div class='box'><h3>📐 Formula</h3>"
    for a,b in FORMULAS: html+=f"<p><b>{a}</b> = {b}</p>"
    return html+"</div>"+footer()
@app.route("/gk")
def gk():
    h=header(); s=style(); tg=get_today_gk(); ds=datetime.now().strftime("%d %B %Y")
    html=f"""<html><head><title>GK</title><meta name="viewport" content="width=device-width, initial-scale=1">{s}</head><body>{h}<h2>🧠 Aaj ka GK - {ds} - 15 Question</h2><div class="box" style="background:#e8ffe8"><b>🔥 Aaj ke 15 - Kal naye aayenge!</b></div>"""
    for i,(q,a) in enumerate(tg,1): html+=f"""<div class="box"><span class="gk-num">{i}</span><b>Q: {q}</b><br><span style="color:green">✅ Answer: {a}</span></div>"""
    return html+footer()
@app.route("/about")
def about():
    h=header(); s=style()
    return f"""<html><head><title>About</title><meta name="viewport" content="width=device-width, initial-scale=1">{s}</head><body>{h}<div class="box"><h2>ℹ️ About Bhai Ki News</h2><p>Namaste! Main <b>Priyanshu Singh, Lucknow</b> se hu. Yaha News + Free Padhai milega.</p><p><b>Instagram:</b> @priyanshu538617</p></div>{footer()}"""
@app.route("/about-us")
def about_us(): return redirect("/about")
@app.route("/contact")
@app.route("/contact-us")
def contact():
    h=header(); s=style()
    return f"""<html><head><title>Contact</title><meta name="viewport" content="width=device-width, initial-scale=1">{s}</head><body>{h}<div class="box"><h2>📞 Contact Us</h2><p>Koi dikkat ho to Instagram pe Message karo.</p><p><b>Instagram:</b> @priyanshu538617</p></div>{footer()}"""
@app.route("/privacy")
@app.route("/privacy-policy")
def privacy():
    h=header(); s=style()
    return f"""<html><head><title>Privacy</title><meta name="viewport" content="width=device-width, initial-scale=1">{s}</head><body>{h}<div class="box"><h2>🔐 Privacy Policy</h2><p>Hum aapka Personal Data nahi lete. Sirf Visitor Count dekhte hai.</p></div>{footer()}"""
@app.route("/admin", methods=["GET","POST"])
def admin():
    s=style()
    if request.method=="POST" and request.form.get("password")==ADMIN_PASSWORD: session["admin"]=True
    if request.method=="POST" and session.get("admin"):
        d=load_data(); t=request.form.get("title","").strip(); c=request.form.get("cat","Article"); x=request.form.get("text","").strip()
        if t and x: d["my_articles"].append({"title":t,"cat":c,"text":x}); save_data(d); return redirect("/admin")
    if not session.get("admin"):
        return f"""<html><head><meta name="viewport" content="width=device-width, initial-scale=1">{s}</head><body>{header()}<div class="box"><h2>🔐 Admin Login</h2><form method="post"><input type="password" name="password" placeholder="Password daalo"><button class="btn">Login</button></form></div>{footer()}"""
    d=load_data()
    return f"""<html><head><meta name="viewport" content="width=device-width, initial-scale=1">{s}</head><body>{header()}<div class="box"><h2>✍️ Naya Article Daalo</h2><form method="post"><input name="title" placeholder="Title"><input name="cat" placeholder="Category"><textarea name="text" rows="6" placeholder="Pura Article..."></textarea><button class="btn">Publish Karo 🚀</button></form><hr><h3>Total Articles: {len(d.get("my_articles",[]))+len(MY_NEW_ARTICLES)}</h3><h3>Total Visitors: {d.get("total",0)}</h3></div>{footer()}"""
if __name__=="__main__":
    port=int(os.environ.get("PORT",5000)); app.run(host="0.0.0.0",port=port)
