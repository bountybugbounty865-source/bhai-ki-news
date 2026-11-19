import feedparser, re, hashlib, urllib.parse, random, os, json
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
    return {"total":0, "today":{}, "reads":{}, "my_articles":[]}
def save_data(d):
    with open(DATA_FILE,"w") as f: json.dump(d,f)

FEEDS = {
    "🔥 Top Khabar": "https://news.google.com/rss?hl=hi&gl=IN&ceid=IN:hi",
    "🏏 Cricket": "https://news.google.com/rss/search?q=Cricket&hl=hi&gl=IN&ceid=IN:hi",
    "💼 Naukri": "https://news.google.com/rss/search?q=Sarkari Naukri&hl=hi&gl=IN&ceid=IN:hi",
    "📚 Padhai": "https://news.google.com/rss/search?q=Exam Padhai&hl=hi&gl=IN&ceid=IN:hi",
}
GK_LIST = [
    ("Lal Kila kaha hai?", "Delhi me"),
    ("Taj Mahal kaha hai?", "Agra me"),
    ("Aasman Neela kyu hai?", "Neela rang zyada bikharne se"),
    ("23 x 11 = ?", "253 - Trick se!"),
    ("Bharat ka Rashtriya Pashu kaun hai?", "Bagh"),
]
FORMULAS = [
    ("(a+b)²", "(a² + 2ab + b²)"),
    ("Area - Circle", "πr²"),
    ("Speed", "Distance / Time"),
    ("11 se Guna", "23x11 = 253 Trick"),
]
LIBRARY = {
    "📚 NCERT Books": [("Class 10 Maths", "https://ncert.nic.in/"), ("Class 10 Science", "https://ncert.nic.in/")],
    "📝 Previous Paper": [("UP Board Paper", "https://upmsp.edu.in/"), ("CBSE Paper", "https://cbse.gov.in/")],
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
        input,select,textarea{width:100%;padding:12px;margin:8px 
