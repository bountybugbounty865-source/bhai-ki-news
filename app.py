import feedparser
from flask import Flask
app = Flask(__name__)

FEEDS = {
    "🇮🇳 India": "https://news.google.com/rss/search?q=India&hl=hi&gl=IN&ceid=IN:hi",
    "🏏 Cricket": "https://news.google.com/rss/search?q=cricket&hl=hi&gl=IN&ceid=IN:hi",
    "🎬 Bollywood": "https://news.google.com/rss/search?q=Bollywood&hl=hi&gl=IN&ceid=IN:hi",
    "🌍 World": "https://news.google.com/rss/search?q=world&hl=hi&gl=IN&ceid=IN:hi",
}

@app.route('/')
def home():
    all_news = ""
    for category, url in FEEDS.items():
        feed = feedparser.parse(url)
        cards = ""
        for entry in feed.entries[:6]:
            cards += f"""
            <div class="card">
                <h3>{entry.title}</h3>
                <a href="{entry.link}" target="_blank">Poori Khabar Padhein →</a>
            </div>
            """
        all_news += f"<h2>{category}</h2><div class='grid'>{cards}</div>"
    return f"""
    <html><head><title>BHAI KI NEWS</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body{{font-family:Arial;background:#f2f2f2;margin:0}}
        .header{{background:#d60000;color:white;padding:20px;text-align:center;position:sticky;top:0}}
        .header h1{{margin:0;font-size:32px}}
        .live{{background:yellow;color:black;padding:3px 10px;border-radius:20px;font-weight:bold}}
        h2{{padding:0 15px;color:#d60000}}
        .grid{{display:grid;grid-template-columns:1fr 1fr;gap:15px;padding:0 15px 20px}}
        .card{{background:white;padding:15px;border-radius:12px;box-shadow:0 2px 8px #ccc}}
        .card h3{{font-size:16px;margin:0 0 8px}} .card a{{color:#d60000;font-weight:bold;text-decoration:none}}
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
