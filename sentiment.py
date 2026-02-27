#!/usr/bin/env python3
"""OpenClaw Sentiment Analyzer - CPU-based using VADER + financial keyword boosting"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

NEWS_DIR = Path(os.path.expanduser("~/.openclaw/workspace/news-data"))
RESULTS_DIR = Path(os.path.expanduser("~/.openclaw/workspace/sentiment-data"))

# Financial sentiment boosters - words that shift sentiment in financial context
FINANCIAL_POSITIVE = [
    "upgrade", "outperform", "beat", "exceeded", "growth", "bullish",
    "rally", "surge", "breakthrough", "contract awarded", "partnership",
    "revenue growth", "earnings beat", "price target raised", "buy rating",
    "strong demand", "record revenue", "expanded", "approved", "certified",
]

FINANCIAL_NEGATIVE = [
    "downgrade", "underperform", "miss", "missed", "decline", "bearish",
    "crash", "plunge", "lawsuit", "investigation", "recall", "delay",
    "revenue miss", "earnings miss", "price target cut", "sell rating",
    "weak demand", "layoffs", "debt", "default", "bankruptcy", "grounded",
]

# Stock symbol to company name mapping for association
WATCHLIST_MAP = {
    "AVAV": ["aerovironment", "avav"],
    "KTOS": ["kratos", "ktos"],
    "JOBY": ["joby", "joby aviation"],
    "ACHR": ["archer", "archer aviation", "achr"],
    "TSLA": ["tesla", "tsla", "elon musk"],
    "COHR": ["coherent", "cohr"],
    "SPACEX": ["spacex", "starlink", "starship"],
}


def get_analyzer():
    """Create VADER analyzer with financial lexicon updates."""
    analyzer = SentimentIntensityAnalyzer()
    # Boost financial terms in VADER's lexicon
    for word in FINANCIAL_POSITIVE:
        analyzer.lexicon[word] = 2.5
    for word in FINANCIAL_NEGATIVE:
        analyzer.lexicon[word] = -2.5
    return analyzer


def classify_sentiment(compound_score):
    """Classify compound score into label with confidence."""
    if compound_score >= 0.15:
        label = "positive"
        confidence = min(abs(compound_score), 1.0)
    elif compound_score <= -0.15:
        label = "negative"
        confidence = min(abs(compound_score), 1.0)
    else:
        label = "neutral"
        confidence = 1.0 - abs(compound_score) * 3
    return label, round(confidence, 3)


def associate_stocks(text):
    """Associate article with relevant stock symbols."""
    text_lower = text.lower()
    associated = []
    for symbol, keywords in WATCHLIST_MAP.items():
        for kw in keywords:
            if kw in text_lower:
                associated.append(symbol)
                break
    return associated


def analyze_article(analyzer, article):
    """Analyze sentiment of a single article."""
    # Combine title and description for analysis
    text = f"{article.get('title', '')} {article.get('description', '')}"

    scores = analyzer.polarity_scores(text)
    label, confidence = classify_sentiment(scores["compound"])
    stocks = associate_stocks(text)

    return {
        "title": article.get("title", ""),
        "source": article.get("source", ""),
        "published": article.get("published", ""),
        "sentiment": label,
        "confidence": confidence,
        "compound_score": round(scores["compound"], 4),
        "pos": round(scores["pos"], 4),
        "neg": round(scores["neg"], 4),
        "neu": round(scores["neu"], 4),
        "associated_stocks": stocks,
        "analyzed_at": datetime.now().isoformat(),
    }


def analyze_today():
    """Analyze all articles from today's news data."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    analyzer = get_analyzer()

    # Find latest articles file
    article_files = sorted(NEWS_DIR.glob("articles_*.json"), reverse=True)
    if not article_files:
        print("No article files found. Run newsfeed.py first.")
        return []

    latest_file = article_files[0]
    print(f"Analyzing: {latest_file.name}")

    articles = json.loads(latest_file.read_text())
    print(f"Articles to analyze: {len(articles)}")

    results = []
    for article in articles:
        result = analyze_article(analyzer, article)
        results.append(result)

    # Save results
    today = datetime.now().strftime("%Y-%m-%d")
    results_file = RESULTS_DIR / f"sentiment_{today}.json"
    results_file.write_text(json.dumps(results, indent=2))

    return results


def print_summary(results):
    """Print sentiment summary by stock."""
    if not results:
        return

    print(f"\n{'=' * 70}")
    print("SENTIMENT SUMMARY")
    print(f"{'=' * 70}")

    # Overall stats
    pos = sum(1 for r in results if r["sentiment"] == "positive")
    neg = sum(1 for r in results if r["sentiment"] == "negative")
    neu = sum(1 for r in results if r["sentiment"] == "neutral")
    print(f"\nOverall: {pos} positive | {neg} negative | {neu} neutral | {len(results)} total")

    # Per-stock breakdown
    print(f"\n{'Symbol':<8} {'Pos':>5} {'Neg':>5} {'Neu':>5} {'Avg Score':>10} {'Signal':<10}")
    print("-" * 50)

    for symbol in WATCHLIST_MAP:
        stock_results = [r for r in results if symbol in r["associated_stocks"]]
        if not stock_results:
            continue
        s_pos = sum(1 for r in stock_results if r["sentiment"] == "positive")
        s_neg = sum(1 for r in stock_results if r["sentiment"] == "negative")
        s_neu = sum(1 for r in stock_results if r["sentiment"] == "neutral")
        avg_score = sum(r["compound_score"] for r in stock_results) / len(stock_results)

        if avg_score > 0.15:
            signal = "BULLISH"
        elif avg_score < -0.15:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"

        print(f"{symbol:<8} {s_pos:>5} {s_neg:>5} {s_neu:>5} {avg_score:>+10.4f} {signal:<10}")

    print(f"\n{'=' * 70}")
    print(f"Analysis completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Top positive and negative headlines
    sorted_results = sorted(results, key=lambda r: r["compound_score"], reverse=True)
    top_pos = [r for r in sorted_results if r["sentiment"] == "positive" and r["associated_stocks"]][:3]
    top_neg = [r for r in sorted_results if r["sentiment"] == "negative" and r["associated_stocks"]][-3:]

    if top_pos:
        print("\nMost positive:")
        for r in top_pos:
            stocks = ", ".join(r["associated_stocks"])
            print(f"  [{r['compound_score']:+.3f}] ({stocks}) {r['title'][:70]}")

    if top_neg:
        print("\nMost negative:")
        for r in reversed(top_neg):
            stocks = ", ".join(r["associated_stocks"])
            print(f"  [{r['compound_score']:+.3f}] ({stocks}) {r['title'][:70]}")


if __name__ == "__main__":
    print("OpenClaw Sentiment Analyzer")
    print()
    results = analyze_today()
    print_summary(results)
