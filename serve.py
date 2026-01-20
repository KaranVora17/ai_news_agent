# serve.py
import os
import html
import re
import sqlite3
from http.server import HTTPServer, SimpleHTTPRequestHandler

DB_PATH = "news.db"
INDEX_FILE = "index.html"
HOST = "127.0.0.1"
PORT = 8765

# ---------- DB helpers ----------
def get_conn():
    return sqlite3.connect(DB_PATH)

def fetch_rows(query, args=()):
    with get_conn() as conn:
        cur = conn.execute(query, args)
        return cur.fetchall()

# ---------- HTML builder (dark + tabs) ----------
def build_index():
    rows = fetch_rows("""
        SELECT title, source, url, published
        FROM articles
        ORDER BY inserted_at DESC
        LIMIT 300
    """)

    AI_KEYWORDS = [
        "ai","agent","agents","llm","model","models","foundation",
        "gemini","claude","openai","anthropic","copilot",
        "reinforcement","transformer","embedding","vector"
    ]
    FUNDING_KW = [
        "raises","raised","funding","series","seed","round",
        "valuation","backed","led by"
    ]
    money_re = re.compile(r"(\$|usd|€|£)\s?\d+", re.IGNORECASE)

    def is_ai(title):
        t = (title or "").lower()
        return any(k in t for k in AI_KEYWORDS)

    def is_funding(title):
        t = (title or "").lower()
        return any(k in t for k in FUNDING_KW) or bool(money_re.search(t))

    # Group by source and tag
    grouped = {"all": {}, "ai": {}, "funding": {}}

    for title, source, url, published in rows:
        grouped["all"].setdefault(source or "Unknown", []).append((title or "", url or "", published or ""))
        if is_ai(title):
            grouped["ai"].setdefault(source or "Unknown", []).append((title or "", url or "", published or ""))
        if is_funding(title):
            grouped["funding"].setdefault(source or "Unknown", []).append((title or "", url or "", published or ""))

    parts = []
    parts.append("<!doctype html>")
    parts.append("<html>")
    parts.append("<head>")
    parts.append("<meta charset='utf-8'>")
    parts.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    parts.append("<title>AI News Agent</title>")
    parts.append("<style>")
    parts.append("""
:root {
  --bg: #0f1115;
  --card: #161a22;
  --text: #e5e7eb;
  --muted: #9ca3af;
  --accent: #3b82f6;
  --border: #232834;
}
body {
  margin: 0;
  padding: 24px;
  background: var(--bg);
  color: var(--text);
  font-family: Inter, Segoe UI, Arial, sans-serif;
}
h1 { margin-bottom: 6px; }
p { color: var(--muted); }
.tabs { display: flex; gap: 12px; margin: 24px 0; }
.tab {
  padding: 8px 14px;
  border-radius: 8px;
  background: var(--card);
  cursor: pointer;
  border: 1px solid var(--border);
  color: var(--muted);
}
.tab.active {
  color: white;
  border-color: var(--accent);
  background: #1e293b;
}
.view { display: none; }
.view.active { display: block; }
.source { margin-top: 32px; }
.source h2 {
  font-size: 1.1rem;
  color: #c7d2fe;
  margin-bottom: 14px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 6px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}
.card {
  background: var(--card);
  border-radius: 12px;
  padding: 14px 16px;
  border: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.card a {
  color: #93c5fd;
  font-weight: 600;
  text-decoration: none;
}
.card a:hover { text-decoration: underline; }
.snippet { margin-top: 8px; font-size: 0.9rem; color: var(--muted); }
.meta { margin-top: 10px; font-size: 0.75rem; color: #6b7280; }
.footer { margin-top: 28px; font-size: 0.8rem; color: var(--muted); }
@media (max-width: 520px) {
  .grid { grid-template-columns: 1fr; }
}
    """)
    parts.append("</style>")
    parts.append("</head>")
    parts.append("<body>")
    parts.append("<h1>AI News Agent</h1>")
    parts.append("<p>Local, curated AI signal — dark mode</p>")
    parts.append("<div class='tabs'>")
    parts.append("<div class='tab active' data-target='all'>All</div>")
    parts.append("<div class='tab' data-target='ai'>AI</div>")
    parts.append("<div class='tab' data-target='funding'>Funding</div>")
    parts.append("</div>")

    def render_view(name, data, active=False):
        class_active = "active" if active else ""
        parts.append(f"<div id='{html.escape(name)}' class='view {class_active}'>")
        if not data:
            parts.append("<p style='color:var(--muted)'>No items in this view.</p>")
        else:
            for source, items in data.items():
                parts.append(f"<div class='source'><h2>{html.escape(source)}</h2><div class='grid'>")
                for title, url, published in items:
                    snippet = title if len(title) <= 120 else (title[:117] + "...")
                    # Build card HTML
                    card_html = (
                        "<div class='card'>"
                        "<div>"
                        f"<a href=\"{html.escape(url)}\" target=\"_blank\">{html.escape(title)}</a>"
                        f"<div class='snippet'>{html.escape(snippet)}</div>"
                        "</div>"
                        f"<div class='meta'>{html.escape(published or '')}</div>"
                        "</div>"
                    )
                    parts.append(card_html)
                parts.append("</div></div>")
        parts.append("</div>")

    render_view("all", grouped["all"], active=True)
    render_view("ai", grouped["ai"], active=False)
    render_view("funding", grouped["funding"], active=False)

    # JS for tabs + simple keyboard shortcuts
    parts.append("""
<script>
document.querySelectorAll('.tab').forEach(function(t){
  t.addEventListener('click', function(){
    var target = t.getAttribute('data-target');
    document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
    document.getElementById(target).classList.add('active');
    t.classList.add('active');
  });
});

/* keyboard: 1=All, 2=AI, 3=Funding */
document.addEventListener('keydown', function(e){
  if(document.activeElement && (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA')) return;
  if(e.key === '1') document.querySelector('.tab[data-target="all"]').click();
  if(e.key === '2') document.querySelector('.tab[data-target="ai"]').click();
  if(e.key === '3') document.querySelector('.tab[data-target="funding"]').click();
});
</script>
""")

    parts.append(f"<div class='footer'>Generated from <code>{html.escape(DB_PATH)}</code>. Refresh after running <code>python ingest.py</code>.</div>")
    parts.append("</body></html>")

    content = "\n".join(parts)
    with open(INDEX_FILE, "w", encoding="utf-8") as fh:
        fh.write(content)

# ---------- Server ----------
def serve():
    build_index()
    print(f"Built {INDEX_FILE}. Serving on http://{HOST}:{PORT}/")
    # Serve from current directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")
    handler = SimpleHTTPRequestHandler
    httpd = HTTPServer((HOST, PORT), handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Stopping server...")

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found. Run: python ingest.py")
    else:
        serve()

