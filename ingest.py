import hashlib
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

from db import init_db, insert_article, get_recent, get_todays_articles, get_recent_rows
from sources import SOURCES


# ---------- Utilities ----------

def make_id(title, source, url):
    key = f"{title}|{source}|{url}".lower().strip()
    return hashlib.sha256(key.encode("utf-8")).hexdigest()

def fetch_feed(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()

def parse_rss_date(raw):
    if not raw:
        return None
    raw = raw.strip()
    fmts = [
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(raw, fmt).isoformat()
        except Exception:
            pass
    return None


# ---------- Ingestion ----------

def ingest_source(source_name, feed_url, limit=25):
    xml_bytes = fetch_feed(feed_url)
    root = ET.fromstring(xml_bytes)

    new_count = 0

    # RSS
    items = root.findall(".//item")[:limit]
    for item in items:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = item.findtext("pubDate")

        if not title or not link:
            continue

        article = {
            "id": make_id(title, source_name, link),
            "title": title,
            "source": source_name,
            "url": link,
            "published": parse_rss_date(pub_date),
        }

        if insert_article(article):
            new_count += 1

    # Atom fallback
    if not items:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entries = root.findall(".//a:entry", ns)[:limit]
        for entry in entries:
            title = (entry.findtext("a:title", namespaces=ns) or "").strip()

            link_el = entry.find("a:link[@rel='alternate']", ns)
            if link_el is None:
                link_el = entry.find("a:link", ns)
            link = (link_el.get("href") if link_el is not None else "").strip()

            published = (
                entry.findtext("a:published", namespaces=ns)
                or entry.findtext("a:updated", namespaces=ns)
            )

            if not title or not link:
                continue

            article = {
                "id": make_id(title, source_name, link),
                "title": title,
                "source": source_name,
                "url": link,
                "published": (published.strip() if published else None),
            }

            if insert_article(article):
                new_count += 1

    return new_count

def ingest_all():
    total = 0
    for source_name, feed_url in SOURCES:
        try:
            added = ingest_source(source_name, feed_url)
            print(f"[OK] {source_name}: +{added}")
            total += added
        except Exception as e:
            print(f"[ERROR] {source_name}: {e}")
    return total


# ---------- Simple scoring / filters ----------

AI_KEYWORDS = [
    "ai", "agent", "agents", "llm", "model", "models", "foundation",
    "gemini", "claude", "openai", "anthropic", "copilot",
    "reinforcement learning", "rl", "neural", "transformer", "inference",
    "vector", "embedding", "orchestration",
]

FUNDING_KEYWORDS = [
    "raises", "raised", "funding", "series a", "series b", "series c", "seed",
    "round", "valuation", "backed", "led by",
]

_money_re = re.compile(r"(\$|usd|€|£)\s?\d+(\.\d+)?\s?(m|million|b|billion)?", re.IGNORECASE)

def score_ai(title: str) -> int:
    t = title.lower()
    score = 0
    for kw in AI_KEYWORDS:
        if kw in t:
            score += 2
    # Prefer “AI” but not false positives like “said”
    if " ai " in f" {t} " or t.startswith("ai ") or t.endswith(" ai"):
        score += 2
    return score

def is_funding(title: str) -> bool:
    t = title.lower()
    if any(kw in t for kw in FUNDING_KEYWORDS):
        return True
    if _money_re.search(t):
        return True
    return False


# ---------- Views ----------

def print_todays_brief():
    rows = get_todays_articles()
    print("\n=== Today's Brief ===")
    if not rows:
        print("No articles today.")
        return
    for i, (title, source, url, published) in enumerate(rows, 1):
        print(f"{i}. [{source}] {title}")
        print(f"   {url}")

def print_recent():
    rows = get_recent(10)
    print("\n=== Recent Articles (last 10 ingested) ===")
    if not rows:
        print("No articles yet.")
        return
    for i, (title, source, url, published) in enumerate(rows, 1):
        print(f"{i}. [{source}] {title}")
        print(f"   {url}")

def print_ai_brief(limit=15, scan=200):
    rows = get_recent_rows(scan)
    scored = []
    for title, source, url, published, inserted_at in rows:
        s = score_ai(title or "")
        if s > 0:
            scored.append((s, inserted_at, source, title, url))
    scored.sort(reverse=True)

    print("\n=== AI Brief (ranked) ===")
    if not scored:
        print("No AI-related items found in recent scan.")
        return

    for i, (s, inserted_at, source, title, url) in enumerate(scored[:limit], 1):
        print(f"{i}. ({s}) [{source}] {title}")
        print(f"   {url}")

def print_funding_tracker(limit=20, scan=300):
    rows = get_recent_rows(scan)
    hits = []
    for title, source, url, published, inserted_at in rows:
        if is_funding(title or ""):
            hits.append((inserted_at, source, title, url))
    hits.sort(reverse=True)

    print("\n=== Funding Tracker ===")
    if not hits:
        print("No funding-related items found in recent scan.")
        return

    for i, (inserted_at, source, title, url) in enumerate(hits[:limit], 1):
        print(f"{i}. [{source}] {title}")
        print(f"   {url}")


# ---------- CLI ----------
def usage():
    print("Usage:")
    print("  python ingest.py            -> ingest feeds + show today + recent")
    print("  python ingest.py --brief    -> show ranked AI brief")
    print("  python ingest.py --funding  -> show funding tracker")
    print("  python ingest.py --recent   -> show recent items")
    print("  python ingest.py --ingest   -> ingest only")


if __name__ == "__main__":
    init_db()

    args = sys.argv[1:]

    if not args:
        total_added = ingest_all()
        print(f"\nIngest complete. New articles added: {total_added}")
        print_todays_brief()
        print_recent()
        sys.exit(0)

    if "--help" in args or "-h" in args:
        usage()
        sys.exit(0)

    if "--ingest" in args:
        total_added = ingest_all()
        print(f"\nIngest complete. New articles added: {total_added}")
        sys.exit(0)

    if "--brief" in args:
        print_ai_brief()
        sys.exit(0)

    if "--funding" in args:
        print_funding_tracker()
        sys.exit(0)

    if "--recent" in args:
        print_recent()
        sys.exit(0)

    usage()
    sys.exit(1)

