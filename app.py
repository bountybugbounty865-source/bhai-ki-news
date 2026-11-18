from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return """
    <html><head><title>Bhai Ki News</title>
    <style>body{font-family:Arial;background:#111;color:white;text-align:center;padding:20px}
    .card{background:#222;padding:20px;margin:15px;border-radius:15px}
    h1{color:#ffcc00}</style></head>
    <body>
    <h1>BHAI KI NEWS</h1>
    <p>Latest News - Lucknow, UP</p>
    <div class='card'><h2>Breaking News: Bhai Ki Website Live Ho Gayi!</h2><p>Ab sabse tez news yahi milegi.</p></div>
    <div class='card'><h2>Lucknow Me Mausam Mast Hai</h2><p>Aaj ka mausam ekdum badhiya hai.</p></div>
    <div class='card'><h2>Cricket Me India Jeet Gaya!</h2><p>Bhai ne bola tha, jeet pakki hai!</p></div>
    <p>Made by Priyanshu Singh</p>
    </body></html>
    """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
