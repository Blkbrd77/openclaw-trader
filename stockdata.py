#!/usr/bin/env python3
"""OpenClaw Stock Data Fetcher - Alpha Vantage Integration"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

CACHE_DIR = Path(os.path.expanduser("~/.openclaw/workspace/market-data"))
WATCHLIST = ["AVAV", "KTOS", "JOBY", "ACHR", "TSLA", "COHR"]
API_BASE = "https://www.alphavantage.co/query"


def get_api_key():
    key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not key:
        env_file = Path(os.path.expanduser("~/.openclaw/workspace/.env"))
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("ALPHA_VANTAGE_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
    if not key:
        print("ERROR: ALPHA_VANTAGE_API_KEY not set")
        sys.exit(1)
    return key


def fetch_quote(symbol, api_key):
    """Fetch current quote for a symbol."""
    url = f"{API_BASE}?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if "Global Quote" in data and data["Global Quote"]:
            q = data["Global Quote"]
            return {
                "symbol": symbol,
                "price": float(q.get("05. price", 0)),
                "open": float(q.get("02. open", 0)),
                "high": float(q.get("03. high", 0)),
                "low": float(q.get("04. low", 0)),
                "volume": int(q.get("06. volume", 0)),
                "prev_close": float(q.get("08. previous close", 0)),
                "change": float(q.get("09. change", 0)),
                "change_pct": q.get("10. change percent", "0%"),
                "latest_day": q.get("07. latest trading day", ""),
                "fetched_at": datetime.now().isoformat(),
            }
        elif "Note" in data or "Information" in data:
            msg = data.get("Note") or data.get("Information", "")
            print(f"  RATE LIMITED on {symbol}: {msg}")
            return None
        else:
            print(f"  No data for {symbol}: {json.dumps(data)[:200]}")
            return None
    except urllib.error.URLError as e:
        print(f"  ERROR fetching {symbol}: {e}")
        return None


def fetch_daily(symbol, api_key):
    """Fetch daily OHLCV history (compact = last 100 days)."""
    url = f"{API_BASE}?function=TIME_SERIES_DAILY&symbol={symbol}&outputsize=compact&apikey={api_key}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        if "Time Series (Daily)" in data:
            series = data["Time Series (Daily)"]
            daily = []
            for date_str, vals in sorted(series.items(), reverse=True)[:30]:
                daily.append({
                    "date": date_str,
                    "open": float(vals["1. open"]),
                    "high": float(vals["2. high"]),
                    "low": float(vals["3. low"]),
                    "close": float(vals["4. close"]),
                    "volume": int(vals["5. volume"]),
                })
            return daily
        elif "Note" in data or "Information" in data:
            msg = data.get("Note") or data.get("Information", "")
            print(f"  RATE LIMITED on {symbol} daily: {msg}")
            return None
        else:
            print(f"  No daily data for {symbol}")
            return None
    except urllib.error.URLError as e:
        print(f"  ERROR fetching daily {symbol}: {e}")
        return None


def cache_data(symbol, quote, daily):
    """Cache data locally to minimize API calls."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{symbol}.json"
    cached = {}
    if cache_file.exists():
        cached = json.loads(cache_file.read_text())
    if quote:
        cached["quote"] = quote
    if daily:
        cached["daily"] = daily
    cached["last_updated"] = datetime.now().isoformat()
    cache_file.write_text(json.dumps(cached, indent=2))


def is_cache_fresh(symbol, max_age_minutes=60):
    """Check if cached data is still fresh."""
    cache_file = CACHE_DIR / f"{symbol}.json"
    if not cache_file.exists():
        return False
    cached = json.loads(cache_file.read_text())
    last = cached.get("last_updated")
    if not last:
        return False
    age = datetime.now() - datetime.fromisoformat(last)
    return age < timedelta(minutes=max_age_minutes)


def get_cached(symbol):
    """Get cached data for a symbol."""
    cache_file = CACHE_DIR / f"{symbol}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    return None


def fetch_all(force=False):
    """Fetch quotes and daily data for all watchlist symbols."""
    api_key = get_api_key()
    results = {}
    for i, symbol in enumerate(WATCHLIST):
        if not force and is_cache_fresh(symbol):
            print(f"  {symbol}: using cache")
            results[symbol] = get_cached(symbol)
            continue
        print(f"  Fetching {symbol}...")
        quote = fetch_quote(symbol, api_key)
        # Alpha Vantage free tier: 25 requests/day, pace requests
        time.sleep(12)
        daily = fetch_daily(symbol, api_key)
        if quote or daily:
            cache_data(symbol, quote, daily)
            results[symbol] = {"quote": quote, "daily": daily}
        if i < len(WATCHLIST) - 1:
            time.sleep(12)
    return results


def print_summary(results):
    """Print a summary table of current quotes."""
    print("\n" + "=" * 70)
    print(f"{'Symbol':<8} {'Price':>10} {'Change':>10} {'Change%':>10} {'Volume':>12}")
    print("-" * 70)
    for symbol in WATCHLIST:
        data = results.get(symbol, {})
        q = data.get("quote") if data else None
        if q:
            print(f"{q['symbol']:<8} {q['price']:>10.2f} {q['change']:>+10.2f} {q['change_pct']:>10} {q['volume']:>12,}")
        else:
            print(f"{symbol:<8} {'N/A':>10} {'N/A':>10} {'N/A':>10} {'N/A':>12}")
    print("=" * 70)
    print(f"Data as of: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    force = "--force" in sys.argv
    print("OpenClaw Stock Data Fetcher")
    print(f"Watchlist: {', '.join(WATCHLIST)}")
    print()
    results = fetch_all(force=force)
    print_summary(results)
