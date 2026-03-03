#!/usr/bin/env python3
"""OpenClaw X/Twitter Sentiment - Search recent tweets and score with VADER"""

import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(os.path.expanduser("~/.openclaw/workspace"))
RESULTS_DIR = WORKSPACE / "sentiment-data"
X_CACHE_DIR = WORKSPACE / "x-data"

# X API v2 search endpoint
X_API_BASE = "https://api.twitter.com/2"

# Search queries per watchlist symbol
SEARCH_QUERIES = {
    "AVAV": "$AVAV OR AeroVironment",
    "KTOS": "$KTOS OR Kratos Defense",
    "JOBY": "$JOBY OR \"Joby Aviation\"",
    "ACHR": "$ACHR OR \"Archer Aviation\"",
    "TSLA": "$TSLA Tesla stock",
    "COHR": "$COHR OR Coherent Corp",
}

# Max tweets per symbol (Free tier = 1500/month total)
# 6 symbols x 40 tweets x ~8 runs/month = 1920, so cap at 30
MAX_TWEETS_PER_SYMBOL = 30


def load_env():
    env_file = WORKSPACE / ".env"
    env = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                env[key.strip()] = val.strip()
    return env


def x_request(endpoint, params=None):
    """Make authenticated request to X API v2."""
    env = load_env()
    bearer = env.get("X_BEARER_TOKEN", "")
    if not bearer:
        print("X_BEARER_TOKEN not configured in .env")
        return None

    url = f"{X_API_BASE}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {bearer}",
        "User-Agent": "OpenClaw/1.0",
    })

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            # Check rate limit headers
            remaining = resp.headers.get("x-rate-limit-remaining")
            if remaining and int(remaining) < 5:
                print(f"  WARNING: X API rate limit low ({remaining} remaining)")
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        if e.code == 429:
            print("  X API rate limit exceeded. Try again later.")
        elif e.code == 403:
            print("  X API access forbidden. Check your API tier/permissions.")
        else:
            print(f"  X API error {e.code}: {error_body[:200]}")
        return None
    except Exception as e:
        print(f"  X request error: {e}")
        return None


def search_tweets(query, max_results=30):
    """Search recent tweets using X API v2."""
    params = {
        "query": f"{query} lang:en -is:retweet",
        "max_results": min(max_results, 100),
        "tweet.fields": "created_at,public_metrics,author_id",
    }
    return x_request("/tweets/search/recent", params)


def fetch_symbol_tweets(symbol):
    """Fetch recent tweets for a watchlist symbol."""
    query = SEARCH_QUERIES.get(symbol)
    if not query:
        return []

    result = search_tweets(query, MAX_TWEETS_PER_SYMBOL)
    if not result or "data" not in result:
        return []

    tweets = []
    for tweet in result["data"]:
        tweets.append({
            "text": tweet.get("text", ""),
            "created_at": tweet.get("created_at", ""),
            "likes": tweet.get("public_metrics", {}).get("like_count", 0),
            "retweets": tweet.get("public_metrics", {}).get("retweet_count", 0),
            "replies": tweet.get("public_metrics", {}).get("reply_count", 0),
            "symbol": symbol,
        })

    return tweets


def analyze_tweets(tweets):
    """Score tweets with VADER using financial lexicon from sentiment.py."""
    # Import the shared analyzer
    sys.path.insert(0, str(WORKSPACE))
    from sentiment import get_analyzer, classify_sentiment

    analyzer = get_analyzer()
    results = []

    for tweet in tweets:
        text = tweet["text"]
        scores = analyzer.polarity_scores(text)
        label, confidence = classify_sentiment(scores["compound"])

        # Engagement weighting: high-engagement tweets get slight boost
        engagement = tweet["likes"] + tweet["retweets"] * 2
        engagement_weight = min(1.5, 1.0 + (engagement / 500))

        weighted_score = scores["compound"] * engagement_weight
        weighted_score = max(-1.0, min(1.0, weighted_score))

        results.append({
            "text": text[:200],
            "source": "X/Twitter",
            "published": tweet["created_at"],
            "sentiment": label,
            "confidence": confidence,
            "compound_score": round(weighted_score, 4),
            "raw_score": round(scores["compound"], 4),
            "pos": round(scores["pos"], 4),
            "neg": round(scores["neg"], 4),
            "neu": round(scores["neu"], 4),
            "associated_stocks": [tweet["symbol"]],
            "engagement": engagement,
            "analyzed_at": datetime.now().isoformat(),
        })

    return results


def fetch_and_analyze():
    """Fetch tweets for all watchlist symbols and analyze sentiment."""
    X_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    all_tweets = []
    all_results = []

    for symbol in SEARCH_QUERIES:
        print(f"  Fetching tweets for {symbol}...", end=" ")
        tweets = fetch_symbol_tweets(symbol)
        print(f"{len(tweets)} tweets")

        if tweets:
            all_tweets.extend(tweets)
            results = analyze_tweets(tweets)
            all_results.extend(results)

    if not all_results:
        print("\nNo tweets collected.")
        return []

    # Save raw tweets
    today = datetime.now().strftime("%Y-%m-%d")
    cache_file = X_CACHE_DIR / f"tweets_{today}.json"
    cache_file.write_text(json.dumps(all_tweets, indent=2))

    # Merge with existing sentiment data for today
    sentiment_file = RESULTS_DIR / f"sentiment_{today}.json"
    existing = []
    if sentiment_file.exists():
        existing = json.loads(sentiment_file.read_text())
        # Remove old X/Twitter entries to avoid duplicates
        existing = [r for r in existing if r.get("source") != "X/Twitter"]

    combined = existing + all_results
    sentiment_file.write_text(json.dumps(combined, indent=2))

    return all_results


def print_summary(results):
    """Print X/Twitter sentiment summary."""
    if not results:
        return

    print(f"\n{'=' * 60}")
    print("X/TWITTER SENTIMENT SUMMARY")
    print(f"{'=' * 60}")

    print(f"\nTotal tweets analyzed: {len(results)}")

    pos = sum(1 for r in results if r["sentiment"] == "positive")
    neg = sum(1 for r in results if r["sentiment"] == "negative")
    neu = sum(1 for r in results if r["sentiment"] == "neutral")
    print(f"Overall: {pos} positive | {neg} negative | {neu} neutral")

    print(f"\n{'Symbol':<8} {'Tweets':>6} {'Pos':>5} {'Neg':>5} {'Avg':>8} {'Signal':<10}")
    print("-" * 50)

    for symbol in SEARCH_QUERIES:
        sym_results = [r for r in results if symbol in r["associated_stocks"]]
        if not sym_results:
            continue
        s_pos = sum(1 for r in sym_results if r["sentiment"] == "positive")
        s_neg = sum(1 for r in sym_results if r["sentiment"] == "negative")
        avg = sum(r["compound_score"] for r in sym_results) / len(sym_results)
        signal = "BULLISH" if avg > 0.15 else "BEARISH" if avg < -0.15 else "NEUTRAL"
        print(f"{symbol:<8} {len(sym_results):>6} {s_pos:>5} {s_neg:>5} {avg:>+8.3f} {signal:<10}")

    # Top engagement tweets
    by_engagement = sorted(results, key=lambda r: r["engagement"], reverse=True)
    top = [t for t in by_engagement if t["engagement"] > 0][:5]
    if top:
        print("\nTop engagement tweets:")
        for t in top:
            stocks = ", ".join(t["associated_stocks"])
            print(f"  [{t['compound_score']:+.3f}] ({stocks}, {t['engagement']} eng) {t['text'][:70]}")

    print(f"\n{'=' * 60}")


if __name__ == "__main__":
    print("OpenClaw X/Twitter Sentiment Analyzer")
    print()

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test API connectivity
        print("Testing X API connection...")
        result = x_request("/tweets/search/recent", {
            "query": "$TSLA lang:en -is:retweet",
            "max_results": 10,
        })
        if result and "data" in result:
            print(f"  OK - got {len(result['data'])} tweets")
            for t in result["data"][:3]:
                print(f"  -> {t['text'][:80]}")
        else:
            print(f"  Failed: {result}")
    else:
        results = fetch_and_analyze()
        print_summary(results)
