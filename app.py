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
# --- GK BANK - ROZ 15 AUTOMATIC KE LIYE ---
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
# --- LIBRARY - SAME + CLASS 9 SE 12 TAK JODA ---
LIBRARY = {
    "📚 NCERT Books": [("Class 10 Maths", "https://ncert.nic.in/"), ("Class 10 Science", "https://ncert.nic.in/")],
    "📝 Previous Paper": [("UP Board Paper", "https://upmsp.edu.in/"), ("CBSE Paper", "https://cbse.gov.in/")],
    "📚 Class 9 - NCERT Books": [("Class 9 Maths Book", "https://ncert.nic.in/textbook.php"), ("Class 9 Science Book", "https://ncert.nic.in/textbook.php"), ("Class 9 Hindi Book", "https://ncert.nic.in/textbook.php"), ("Class 9 SST Book", "https://ncert.nic.in/textbook.php")],
    "📚 Class 10 - NCERT Books": [("Class 10 Maths Book", "https://ncert.nic.in/textbook.php"), ("Class 10 Science Book", "https://ncert.nic.in/textbook.php"), ("Class 10 Hindi Book", "https://ncert.nic.in/textbook.php"), ("Class 10 SST Book", "https://ncert.nic.in/textbook.php")],
    "📚 Class 11 - NCERT Books": [("Class 11 Physics", "https://ncert.nic.in/textbook.php"), ("Class 11 Chemistry", "https://ncert.nic.in/textbook.php"), ("Class 11 Maths", "https://ncert.nic.in/textbook.php"), ("Class 11 Biology", "https://ncert.nic.in/textbook.php"), ("Class 11 Hindi", "https://ncert.nic.in/textbook.php")],
    "📚 Class 12 - NCERT Books": [("Class 12 Physics", "https://ncert.nic.in/textbook.php"), ("Class 12 Chemistry", "https://ncert.nic.in/textbook.php"), ("Class 12 Maths", "https://ncert.nic.in/textbook.php"), ("Class 12 Biology", "https://ncert.nic.in/textbook.php"), ("Class 12 Hindi", "https://ncert.nic.in/textbook.php")],
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
    h
