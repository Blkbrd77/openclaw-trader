#!/usr/bin/env python3
"""OpenClaw News & RSS Monitor - Defense/Drone/EV/SpaceX"""

import json
import hashlib
import os
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.path.expanduser("~/.openclaw/workspace/news-data"))
SEEN_FILE = DATA_DIR / "seen_articles.json"

# Keywords for relevance filtering
KEYWORDS = [
    "avav", "aerovironment", "ktos", "kratos",
    "joby", "joby aviation", "achr", "archer aviation",
    "tsla", "tesla", "cohr", "coherent",
    "spacex", "starlink", "starship",
    "defense drone", "military drone", "uav", "uas",
    "autonomous vehicle", "self-driving", "ev", "electric vehicle",
    "drone delivery", "drone strike", "drone warfare",
    "hailo", "edge ai", "npu",
    "rivian", "lucid", "lidar", "autonomy",
]

# RSS feeds to monitor
FEEDS = [
    {
        "name": "Google News - Defense Drones",
        "url": "https://news.google.com/rss/search?q=defense+drone+stock&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "name": "Google News - Tesla",
        "url": "https://news.google.com/rss/search?q=Tesla+TSLA+stock&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "name": "Google News - SpaceX",
        "url": "https://news.google.com/rss/search?q=SpaceX&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "name": "Google News - eVTOL",
        "url": "https://news.google.com/rss/search?q=eVTOL+Joby+Archer&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "name": "SEC EDGAR - Full-Text Search",
        "url": "https://efts.sec.gov/LATEST/search-index?q=%22AeroVironment%22+OR+%22Kratos%22+OR+%22Tesla%22&forms=8-K,10-K,10-Q&dateRange=custom&startdt=2026-02-01&enddt=2026-02-17",
        "is_sec": True,
    },
    {
        "name": "Google News - Defense Stocks",
        "url": "https://news.google.com/rss/search?q=AeroVironment+OR+Kratos+OR+Coherent+stock&hl=en-US&gl=US&ceid=US:en",
    },
]


def load_seen():
    """Load set of previously seen article hashes."""
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen):
    """Save seen article hashes."""
    SEEN_FILE.write_text(json.dumps(list(seen)))


def article_hash(title, link):
    """Create a unique hash for deduplication."""
    return hashlib.md5(f"{title}|{link}".encode()).hexdigest()


def relevance_score(title, description=""):
    """Score article relevance based on keyword matches."""
    text = f"{title} {description}".lower()
    score = 0
    matched = []
    for kw in KEYWORDS:
        if kw.lower() in text:
            score += 1
            matched.append(kw)
    return score, matched


def find_el(item, *names):
    """Find first matching element by tag names."""
    for name in names:
        el = item.find(name)
        if el is not None:
            return el
    return None


def parse_rss(xml_text, source_name):
    """Parse RSS XML and return list of articles."""
    articles = []
    try:
        root = ET.fromstring(xml_text)
        # Handle both RSS 2.0 and Atom formats
        items = root.findall(".//item")
        if not items:
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        for item in items:
            title_el = find_el(item, "title", "{http://www.w3.org/2005/Atom}title")
            link_el = find_el(item, "link", "{http://www.w3.org/2005/Atom}link")
            desc_el = find_el(item, "description", "{http://www.w3.org/2005/Atom}summary")
            pubdate_el = find_el(item, "pubDate", "{http://www.w3.org/2005/Atom}published")

            title = title_el.text if title_el is not None and title_el.text else ""
            if link_el is not None:
                link = link_el.text if link_el.text else link_el.get("href", "")
            else:
                link = ""
            description = desc_el.text if desc_el is not None and desc_el.text else ""
            pubdate = pubdate_el.text if pubdate_el is not None and pubdate_el.text else ""

            if title:
                score, matched = relevance_score(title, description)
                articles.append({
                    "title": title.strip(),
                    "link": link.strip(),
                    "description": description[:500].strip(),
                    "published": pubdate.strip(),
                    "source": source_name,
                    "relevance_score": score,
                    "matched_keywords": matched,
                    "fetched_at": datetime.now().isoformat(),
                })
    except ET.ParseError as e:
        print(f"  XML parse error for {source_name}: {e}")
    return articles


def fetch_sec_edgar(feed):
    """Fetch SEC EDGAR full-text search results (JSON API)."""
    url = feed["url"]
    name = feed["name"]
    articles = []
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "OpenClaw jay@openclaw.local",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        hits = data.get("hits", {}).get("hits", [])
        for hit in hits[:20]:
            src = hit.get("_source", {})
            title = f"{src.get('form_type', '')} - {src.get('entity_name', '')}"
            link = f"https://www.sec.gov/Archives/edgar/data/{src.get('entity_id', '')}/{src.get('file_num', '')}"
            filed = src.get("file_date", "")
            score, matched = relevance_score(title, src.get("entity_name", ""))
            articles.append({
                "title": title.strip(),
                "link": link,
                "description": f"Filed: {filed}",
                "published": filed,
                "source": name,
                "relevance_score": max(score, 1),
                "matched_keywords": matched,
                "fetched_at": datetime.now().isoformat(),
            })
    except Exception as e:
        print(f"  ERROR fetching {name}: {e}")
    return articles


def fetch_feed(feed):
    """Fetch and parse a single RSS feed."""
    if feed.get("is_sec"):
        return fetch_sec_edgar(feed)
    url = feed["url"]
    name = feed["name"]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; OpenClaw/1.0)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_text = resp.read().decode("utf-8", errors="replace")
        return parse_rss(xml_text, name)
    except (urllib.error.URLError, Exception) as e:
        print(f"  ERROR fetching {name}: {e}")
        return []


def fetch_all_feeds():
    """Fetch all configured feeds, deduplicate, and store."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    seen = load_seen()
    all_articles = []
    new_articles = []

    for feed in FEEDS:
        print(f"  Fetching: {feed['name']}...")
        articles = fetch_feed(feed)
        print(f"    Found {len(articles)} articles")
        time.sleep(2)

        for article in articles:
            h = article_hash(article["title"], article["link"])
            all_articles.append(article)
            if h not in seen:
                seen.add(h)
                new_articles.append(article)

    # Sort by relevance
    new_articles.sort(key=lambda a: a["relevance_score"], reverse=True)

    # Save new articles
    today = datetime.now().strftime("%Y-%m-%d")
    daily_file = DATA_DIR / f"articles_{today}.json"
    existing = []
    if daily_file.exists():
        existing = json.loads(daily_file.read_text())
    existing.extend(new_articles)
    daily_file.write_text(json.dumps(existing, indent=2))

    save_seen(seen)

    return new_articles, len(all_articles)


def print_summary(new_articles, total_fetched):
    """Print summary of new articles."""
    print(f"\n{'=' * 70}")
    print(f"Total fetched: {total_fetched} | New (unseen): {len(new_articles)}")
    print(f"{'=' * 70}")

    if not new_articles:
        print("No new articles since last check.")
        return

    # Show top articles by relevance
    top = [a for a in new_articles if a["relevance_score"] > 0][:10]
    if top:
        print(f"\nTop relevant articles ({len(top)}):")
        print("-" * 70)
        for a in top:
            kw = ", ".join(a["matched_keywords"][:5])
            print(f"  [{a['relevance_score']}] {a['title'][:80]}")
            print(f"      Source: {a['source']} | Keywords: {kw}")
            print()
    else:
        print("\nNo highly relevant articles found this cycle.")
        print("Showing latest 5:")
        for a in new_articles[:5]:
            print(f"  {a['title'][:80]}")
            print(f"      Source: {a['source']}")
            print()

    print(f"Data saved to: {DATA_DIR}")


if __name__ == "__main__":
    print("OpenClaw News Monitor")
    print(f"Monitoring {len(FEEDS)} feeds")
    print(f"Keywords: {len(KEYWORDS)} tracked terms")
    print()
    new_articles, total = fetch_all_feeds()
    print_summary(new_articles, total)
