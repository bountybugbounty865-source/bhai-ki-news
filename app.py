import feedparser, re
from flask import Flask
app = Flask(__name__)

FEEDS = {
    "📍 UP / Lucknow": "https://news.google.com/rss/search?q=Lucknow&hl=hi&gl=IN&ceid=IN:hi",
    "🇮🇳 India": "https://news.google.com/rss/search?q=India&hl=hi&gl=IN&ceid=IN:hi",
    "🏏 Cricket": "https://news.google.com/rss/search?q=cricket&hl=hi&gl=IN&ceid=IN:hi",
    "🎬 Bollywood": "https://news.google.com/rss/search?q=Bollywood&hl=hi&gl=IN&ceid=IN:hi",
    "🌍 World": "https://news.google.com/rss/search?q=world&hl=hi&gl=IN&ceid=IN:hi",
}

def clean(text):
    text = re.sub('<[^<]+?>', '', text or '')
    return text[:300] + "..." if len(text) > 300 else text

def get_img(entry):
    if 'media_content' in entry and entry.media_content:
        return entry.media_content[0].get('url','')
    if 'media_thumbnail' in entry and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url','')
    if 'enclosures' in entry and entry.enclosures:
        return entry.enclosures[0].get('href','')
    # summary me se image nikalna
    m = re.search(r'src="([^"]+)"', entry.get('summary',''))
    return m.group(1) if m else "https://via.placeholder.com/600x300?text=BHAI+KI+NEWS"

@app.route('/')
def home():
    all_news = ""
    for category, url in FEEDS.items():
        feed = feedparser.parse(url)
        cards = ""
        for entry in feed.entries[:6]:
            img = get_img(entry)
            desc = clean(entry.get('summary',''))
            cards += f"""
            <div class="card">
                <img src="{img}">
                <h3>{entry.title}</h3>
                <p>{desc}</p>
                <a href="{entry.link}" target="_blank">Poori Khabar Padhein →</a>
            </div>
            """
        all_news += f"<h2>{category}</h2><div class='grid'>{cards}</div>"
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
