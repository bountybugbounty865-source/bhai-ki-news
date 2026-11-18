
import feedparser, re, hashlib
from flask import Flask
app = Flask(__name__)

FEEDS = {
    "🇮🇳 India - Main Khabar": "https://www.aajtak.in/rss",
    "📍 UP / Lucknow": "https://www.amarujala.com/rss/uttar-pradesh.xml",
    "🪙 Gold / Paisa - Sona Badha Ya Gira?": "https://www.aajtak.in/rss/business",
    "📚 Padhai / Job - Exam & Naukri": "https://www.aajtak.in/rss/education",
    "🏏 Cricket": "https://www.aajtak.in/rss/sports-cricket",
    "🌍 Duniya - Kaam Ki Khabar": "https://www.bbc.com/hindi/index.xml",
}

def clean(text):
    try:
        text = re.sub('<[^<]+?>', '', text or '')
        return text[:250] + "..." if len(text) > 250 else text
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
        if 'enclosures' in entry and entry.enclosures:
            u = entry.enclosures[0].get('href','')
            if u: return u
        m = re.search(r'src="([^"]+)"', entry.get('summary','') or '')
        if m: return m.group(1)
    except:
        pass
    h = hashlib.md5(title.encode()).hexdigest()[:8]
    photos = ["photo-1504711434969-e33886168f5c","photo-1524492412937-b28074a5d7da","photo-1531415074968-036ba1b575da","photo-1489599849927-2ee91cede3ba","photo-1596040033229-a9821ebd058d","photo-1585829365295-ab7cd400c167","photo-1495020689067-958852a7765e","photo-1529107386315-e1a2ed48a620","photo-1541872703-74c5e44368f9","photo-1575320181282-9afab399332c","photo-1610375461246-83df859d849d","photo-1523050854058-8df90110c9f1"]
    pick = photos[int(h,16) % len(photos)]
    return f"https://images.unsplash.com/{pick}?w=600"

@app.route('/')
def home():
    all_news = ""
    seen = set()
    for category, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            cards = ""
            count = 0
            for entry in feed.entries:
                if count >= 8: break
                title = entry.get('title','').strip()
                link = entry.get('link','')
                if title in seen or link in seen or not title:
                    continue
                seen.add(title)
                seen.add(link)
                img = get_img(entry, title)
                desc = clean(entry.get('summary','') or entry.get('description',''))
                cards += f"""
                <div class="card">
                    <img src="{img}">
                    <h3>{title}</h3>
                    <p>{desc}</p>
                    <a href="{link}" target="_blank">Poori Khabar Padhein →</a>
                </div>
                """
                count += 1
            if cards:
                all_news += f"<div class='section'><h2>{category}</h2><div class='grid'>{cards}</div></div>"
        except:
            continue
    return f"""
    <html><head><title>BHAI KI NEWS</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body{{font-family:Arial;background:#f2f2f2;margin:0}}
        .header{{background:#d60000;color:white;padding:20px;text-align:center;position:sticky;top:0;z-index:10}}
        .header h1{{margin:0;font-size:32px}}
        .live{{background:yellow;color:black;padding:3px 10px;border-radius:20px;font-weight:bold}}
        .search-box{{padding:15px;background:white;position:sticky;top:0;z-index:9;box-shadow:0 2px 5px #ccc}}
        .search-box input{{width:100%;padding:12px;font-size:16px;border:2px solid #d60000;border-radius:25px;outline:none;box-sizing:border-box}}
        h2{{padding:0 15px;color:#d60000}}
        .grid{{display:grid;grid-template-columns:1fr 1fr;gap:15px;padding:0 15px 20px}}
        .card{{background:white;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px #ccc}}
        .card img{{width:100%;height:180px;object-fit:cover}}
        .card h3{{font-size:17px;margin:12px 12px 5px}}
        .card p{{font-size:14px;color:#555;margin:0 12px 10px;line-height:1.5}}
        .card a{{display:block;color:#d60000;font-weight:bold;text-decoration:none;padding:0 12px 12px}}
        @media(max-width:600px){{.grid{{grid-template-columns:1fr}}}}
    </style></head>
    <body>
        <div class="header"><h1>🔴 BHAI KI NEWS</h1><p><span class="live">● LIVE</span> Kaam Ki Khabar - India | Gold | Padhai</p><p>Made by Priyanshu Singh | Lucknow</p></div>
        <div class="search-box"><input type="text" id="search" onkeyup="doSearch()" placeholder="🔍 Search Karo... Gold, Exam, Job, Cricket..."></div>
        <div id="noResult" style="display:none;text-align:center;padding:20px;font-size:18px">😔 Is naam ki koi khabar nahi mili!</div>
        {all_news}
        <div style="text-align:center;padding:20px;color:gray">© 2026 Bhai Ki News</div>
        <script>
        function doSearch(){{
            var v = document.getElementById('search').value.toLowerCase().trim();
            var words = v.split(' ');
            var cards = document.querySelectorAll('.card');
            var found = 0;
            cards.forEach(function(c){{
                var t = c.innerText.toLowerCase();
                var match = words.some(function(w){{ return w.length>2 && t.includes(w); }});
                if(v=='' || match){{ c.style.display='block'; found++; }} else {{ c.style.display='none'; }}
            }});
            document.querySelectorAll('.section').forEach(function(s){{
                var vis = Array.from(s.querySelectorAll('.card')).some(function(c){{ return c.style.display!='none'; }});
                s.style.display = vis ? 'block' : 'none';
            }});
            document.getElementById('noResult').style.display = found==0 ? 'block' : 'none';
        }}
        </script>
    </body></html>
    """
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
