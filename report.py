#!/usr/bin/env python3
"""OpenClaw Research Report Generator - Synthesizes price, news, and sentiment"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(os.path.expanduser("~/.openclaw/workspace"))
MARKET_DIR = WORKSPACE / "market-data"
NEWS_DIR = WORKSPACE / "news-data"
SENTIMENT_DIR = WORKSPACE / "sentiment-data"
REPORTS_DIR = WORKSPACE / "reports"
FUNDAMENTALS_DIR = WORKSPACE / "fundamentals"

BOT_TOKEN_FILE = Path(os.path.expanduser("~/.openclaw/monitor/chat_id"))
BOT_TOKEN = None  # loaded from .env

def load_env():
    env_file = Path(os.path.expanduser("~/.openclaw/workspace/.env"))
    env = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                env[key.strip()] = val.strip()
    return env


WATCHLIST = ["AVAV", "KTOS", "JOBY", "ACHR", "TSLA", "COHR"]

STOCK_NAMES = {
    "AVAV": "AeroVironment",
    "KTOS": "Kratos Defense",
    "JOBY": "Joby Aviation",
    "ACHR": "Archer Aviation",
    "TSLA": "Tesla",
    "COHR": "Coherent Corp",
}


def load_json(path):
    """Load JSON file if it exists."""
    if path.exists():
        return json.loads(path.read_text())
    return None



def fmt_money(val):
    if val is None:
        return "N/A"
    if abs(val) >= 1e12:
        return f"${val/1e12:.2f}T"
    elif abs(val) >= 1e9:
        return f"${val/1e9:.2f}B"
    elif abs(val) >= 1e6:
        return f"${val/1e6:.2f}M"
    return f"${val:,.0f}"


def get_fundamentals(symbol):
    path = FUNDAMENTALS_DIR / f"{symbol}.json"
    return load_json(path)


def get_latest_file(directory, prefix):
    """Get the most recent file matching prefix."""
    files = sorted(directory.glob(f"{prefix}*.json"), reverse=True)
    return files[0] if files else None


def get_price_data(symbol):
    """Get cached price data for a symbol."""
    data = load_json(MARKET_DIR / f"{symbol}.json")
    if not data:
        return None
    return data


def get_price_trend(daily_data):
    """Calculate 7d and 30d price trends."""
    if not daily_data or len(daily_data) < 2:
        return None, None

    current = daily_data[0]["close"]

    # 7-day trend
    trend_7d = None
    if len(daily_data) >= 5:
        price_7d = daily_data[min(4, len(daily_data) - 1)]["close"]
        trend_7d = round(((current - price_7d) / price_7d) * 100, 2)

    # 30-day trend
    trend_30d = None
    if len(daily_data) >= 20:
        price_30d = daily_data[min(19, len(daily_data) - 1)]["close"]
        trend_30d = round(((current - price_30d) / price_30d) * 100, 2)

    return trend_7d, trend_30d


def get_sentiment_data(symbol):
    """Get sentiment data for a symbol from latest analysis."""
    latest = get_latest_file(SENTIMENT_DIR, "sentiment_")
    if not latest:
        return []
    data = load_json(latest)
    if not data:
        return []
    return [r for r in data if symbol in r.get("associated_stocks", [])]


def get_news_articles(symbol):
    """Get recent news for a symbol."""
    latest = get_latest_file(NEWS_DIR, "articles_")
    if not latest:
        return []
    data = load_json(latest)
    if not data:
        return []

    symbol_lower = symbol.lower()
    name_lower = STOCK_NAMES.get(symbol, "").lower()

    relevant = []
    for article in data:
        text = f"{article.get('title', '')} {article.get('description', '')}".lower()
        if symbol_lower in text or name_lower in text:
            relevant.append(article)

    # Sort by relevance score descending
    relevant.sort(key=lambda a: a.get("relevance_score", 0), reverse=True)
    return relevant[:5]


def generate_stock_report(symbol):
    """Generate a research report for a single stock."""
    name = STOCK_NAMES.get(symbol, symbol)
    price_data = get_price_data(symbol)
    sentiment_results = get_sentiment_data(symbol)
    news = get_news_articles(symbol)

    report = []
    report.append(f"## {symbol} - {name}")
    report.append("")

    # Price section
    if price_data and price_data.get("quote"):
        q = price_data["quote"]
        report.append(f"**Price:** ${q['price']:.2f} ({q['change_pct']})")
        report.append(f"**Volume:** {q['volume']:,}")
        report.append(f"**Day Range:** ${q['low']:.2f} - ${q['high']:.2f}")

        daily = price_data.get("daily", [])
        trend_7d, trend_30d = get_price_trend(daily)
        if trend_7d is not None:
            arrow_7d = "up" if trend_7d > 0 else "down"
            report.append(f"**7-Day Trend:** {trend_7d:+.2f}% ({arrow_7d})")
        if trend_30d is not None:
            arrow_30d = "up" if trend_30d > 0 else "down"
            report.append(f"**30-Day Trend:** {trend_30d:+.2f}% ({arrow_30d})")
    else:
        report.append("**Price:** Data unavailable")

    report.append("")

    # Sentiment section
    if sentiment_results:
        pos = sum(1 for r in sentiment_results if r["sentiment"] == "positive")
        neg = sum(1 for r in sentiment_results if r["sentiment"] == "negative")
        neu = sum(1 for r in sentiment_results if r["sentiment"] == "neutral")
        avg = sum(r["compound_score"] for r in sentiment_results) / len(sentiment_results)

        if avg > 0.15:
            signal = "BULLISH"
        elif avg < -0.15:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"

        report.append(f"**Sentiment:** {signal} (score: {avg:+.3f})")
        news_count = sum(1 for r in sentiment_results if r.get("source") != "X/Twitter")
        x_count = sum(1 for r in sentiment_results if r.get("source") == "X/Twitter")
        source_label = f"{news_count} news"
        if x_count:
            source_label += f" + {x_count} tweets"
        report.append(f"**Breakdown:** {pos} positive / {neg} negative / {neu} neutral ({source_label})")
    else:
        report.append("**Sentiment:** No data available")

    report.append("")

    # News section
    if news:
        report.append("**Top Headlines:**")
        for i, article in enumerate(news[:3], 1):
            title = article.get("title", "")[:80]
            source = article.get("source", "Unknown")
            report.append(f"{i}. {title}")
            report.append(f"   _Source: {source}_")
    else:
        report.append("**Headlines:** No recent articles found")

    # X/Twitter sentiment
    x_results = [r for r in sentiment_results if r.get("source") == "X/Twitter"] if sentiment_results else []
    if x_results:
        top_x = sorted(x_results, key=lambda r: r.get("engagement", 0), reverse=True)[:3]
        report.append("")
        report.append("**Top X/Twitter Posts:**")
        for i, tweet in enumerate(top_x, 1):
            text = tweet.get("text", "")[:80]
            score = tweet.get("compound_score", 0)
            report.append(f"{i}. [{score:+.3f}] {text}")

    report.append("")

    # Fundamentals section
    fund = get_fundamentals(symbol)
    if fund and fund.get("overview"):
        ov = fund["overview"]
        report.append("**Fundamentals:**")
        mcap = fmt_money(ov.get("market_cap"))
        pe = ov.get("pe_ratio", "N/A")
        eps_val = ov.get("eps", "N/A")
        rev = fmt_money(ov.get("revenue_ttm"))
        pm = ov.get("profit_margin")
        pm_str = f"{pm*100:.1f}%" if pm else "N/A"
        wk_lo = ov.get("52_week_low", "N/A")
        wk_hi = ov.get("52_week_high", "N/A")
        target = ov.get("analyst_target", "N/A")
        report.append(f"  Market Cap: {mcap} | P/E: {pe} | EPS: ${eps_val}")
        report.append(f"  Revenue (TTM): {rev} | Profit Margin: {pm_str}")
        report.append(f"  52-Week: ${wk_lo} - ${wk_hi} | Analyst Target: ${target}")
        bs = fund.get("balance_sheet", {})
        if bs:
            cash_str = fmt_money(bs.get("cash"))
            debt_str = fmt_money(bs.get("total_debt"))
            report.append(f"  Cash: {cash_str} | Debt: {debt_str}")
        earn_q = fund.get("earnings", {}).get("quarterly", [])
        if earn_q:
            e = earn_q[0]
            rep_e = e.get("reported_eps", "N/A")
            est_e = e.get("estimated_eps", "N/A")
            sp = e.get("surprise_pct")
            sp_str = f" (surprise: {sp:+.1f}%)" if sp is not None else ""
            report.append(f"  Latest EPS: ${rep_e} vs est. ${est_e}{sp_str}")
        officers = fund.get("officers", [])
        if officers:
            parts = []
            for o in officers[:3]:
                n = o.get("name", "")
                t = o.get("title", "")
                parts.append(f"{n} ({t})")
            report.append("  Leadership: " + ", ".join(parts))
        report.append("")

    # Recommendation section
    recommendation = generate_recommendation(symbol, price_data, sentiment_results)
    report.append(f"**Outlook:** {recommendation}")
    report.append("")
    report.append("---")
    report.append("")

    return "\n".join(report)


def generate_recommendation(symbol, price_data, sentiment_results):
    """Generate an outlook based on price trend + sentiment. NOT financial advice."""
    signals = []

    # Price trend signal
    if price_data and price_data.get("daily"):
        trend_7d, trend_30d = get_price_trend(price_data["daily"])
        if trend_7d is not None:
            if trend_7d > 3:
                signals.append("strong short-term momentum")
            elif trend_7d > 0:
                signals.append("positive short-term trend")
            elif trend_7d < -3:
                signals.append("short-term weakness")
            else:
                signals.append("flat short-term")

        if trend_30d is not None:
            if trend_30d > 10:
                signals.append("strong monthly uptrend")
            elif trend_30d > 0:
                signals.append("positive monthly trend")
            elif trend_30d < -10:
                signals.append("significant monthly decline")
            else:
                signals.append("flat monthly")

    # Sentiment signal
    if sentiment_results:
        avg = sum(r["compound_score"] for r in sentiment_results) / len(sentiment_results)
        if avg > 0.15:
            signals.append("bullish news sentiment")
        elif avg < -0.15:
            signals.append("bearish news sentiment")
        else:
            signals.append("mixed news sentiment")

    if signals:
        return f"{', '.join(signals).capitalize()}. Monitor for changes. (This is not financial advice.)"
    else:
        return "Insufficient data for outlook. (This is not financial advice.)"


def generate_full_report(symbols=None):
    """Generate a full research report for all or specified symbols."""
    if symbols is None:
        symbols = WATCHLIST

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report_lines = []
    report_lines.append("# OpenClaw Research Report")
    report_lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
    report_lines.append(f"**Watchlist:** {', '.join(symbols)}")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    for symbol in symbols:
        print(f"  Generating report for {symbol}...")
        report_lines.append(generate_stock_report(symbol))

    report_lines.append("_This report is generated by OpenClaw for informational purposes only. It does not constitute financial advice. Always do your own research before making investment decisions._")

    report_text = "\n".join(report_lines)

    # Save as markdown
    today = datetime.now().strftime("%Y-%m-%d")
    report_file = REPORTS_DIR / f"report_{today}.md"
    report_file.write_text(report_text)
    print(f"\nReport saved: {report_file}")

    return report_text, report_file


def send_telegram_report(report_text):
    """Send report summary to Telegram."""
    import urllib.request
    import urllib.parse
    bot_token = load_env().get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        print("Telegram not configured: TELEGRAM_BOT_TOKEN missing from .env. Skipping.")
        return

    if not BOT_TOKEN_FILE.exists():
        print("No Telegram chat ID configured. Skipping.")
        return

    chat_id = BOT_TOKEN_FILE.read_text().strip()

    # Telegram has a 4096 char limit per message, so truncate if needed
    if len(report_text) > 4000:
        # Send a summary instead
        lines = report_text.split("\n")
        summary = []
        for line in lines:
            if line.startswith("## ") or line.startswith("**Price:") or line.startswith("**Sentiment:") or line.startswith("**Outlook:") or line.startswith("# ") or line.startswith("**Generated:"):
                summary.append(line)
        msg = "\n".join(summary)
        if len(msg) > 4000:
            msg = msg[:3997] + "..."
    else:
        msg = report_text

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "Markdown",
    }).encode()

    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=data,
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                print("Report sent to Telegram.")
            else:
                print(f"Telegram error: {result}")
    except Exception as e:
        print(f"Failed to send to Telegram: {e}")


if __name__ == "__main__":
    print("OpenClaw Research Report Generator")
    print()

    # Check for specific symbol argument
    symbols = None
    if len(sys.argv) > 1:
        symbols = [s.upper() for s in sys.argv[1:] if s.upper() in WATCHLIST or s == "--send"]

    send = "--send" in sys.argv
    if symbols:
        symbols = [s for s in symbols if s != "--SEND"]

    report_text, report_file = generate_full_report(symbols or None)

    # Print to terminal
    print()
    print(report_text)

    if send:
        send_telegram_report(report_text)
