import sqlite3

DB_PATH = "news.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            source TEXT NOT NULL,
            url TEXT NOT NULL,
            published TEXT,
            inserted_at TEXT DEFAULT (datetime('now'))
        )
        """)
        conn.commit()

def insert_article(article):
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO articles (id, title, source, url, published) VALUES (?, ?, ?, ?, ?)",
                (article["id"], article["title"], article["source"], article["url"], article["published"])
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def get_recent(limit=10):
    with get_conn() as conn:
        cur = conn.execute("""
            SELECT title, source, url, published
            FROM articles
            ORDER BY inserted_at DESC
            LIMIT ?
        """, (limit,))
        return cur.fetchall()

def get_todays_articles():
    with get_conn() as conn:
        cur = conn.execute("""
            SELECT title, source, url, published
            FROM articles
            WHERE published IS NOT NULL
              AND date(published) = date('now')
            ORDER BY published DESC
        """)
        return cur.fetchall()
def get_recent_rows(limit=200):
    with get_conn() as conn:
        cur = conn.execute("""
            SELECT title, source, url, published, inserted_at
            FROM articles
            ORDER BY inserted_at DESC
            LIMIT ?
        """, (limit,))
        return cur.fetchall()

