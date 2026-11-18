
import feedparser, re, hashlib
from flask import Flask
app = Flask(__name__)

FEEDS = {
    "📍 UP / Lucknow": "https://www.amarujala.com/rss/uttar-pradesh.xml",
    "🇮🇳 India": "https://www.aajtak.in/rss",
    "🏏 Cricket": "https://www.aajtak.in/rss/sports-cricket",
    "🎬 Bollywood": "https://www.aajtak.in/rss/entertainment",
    "🌍 World": "https://www.bbc.com/hindi/index.xml",
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
    # Black photo fix - ab Unsplash wali sahi photo aayegi
    h = hashlib.md5(title.encode()).hexdigest()[:8]
    photos = ["photo-1504711434969-e33886168f5c","photo-1524492412937-b28074a5d7da","photo-1531415074968-036ba1b575da","photo-1489599849927-2ee91cede3ba","photo-1596040033229-a9821ebd058d","photo-1585829365295-ab7cd400c167","photo-1495020689067-958852a7765e","photo-1529107386315-e1a2ed48a620","photo-1541872703-74c5e44368f9","photo-1575320181282-9afab399332c"]
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
                if count >= 6: break
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
                all_news += f"<h2>{category}</h2><div class='grid'>{cards}</div>"
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
        <div class="header"><h1>🔴 BHAI KI NEWS</h1><p><span class="live">● LIVE</span> Real News - Har Minute Update</p><p>Made by Priyanshu Singh | Lucknow</p></div>
        {all_news}
        <div style="text-align:center;padding:20px;color:gray">© 2026 Bhai Ki News</div>
    </body></html>
    """
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
