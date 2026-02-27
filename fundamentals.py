#!/usr/bin/env python3
"""OpenClaw Fundamentals Fetcher - Company overview, financials, earnings, and officers"""

import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(os.path.expanduser("~/.openclaw/workspace"))
FUNDAMENTALS_DIR = WORKSPACE / "fundamentals"
FUNDAMENTALS_DIR.mkdir(parents=True, exist_ok=True)

WATCHLIST = ["AVAV", "KTOS", "JOBY", "ACHR", "TSLA", "COHR"]

STOCK_NAMES = {
    "AVAV": "AeroVironment",
    "KTOS": "Kratos Defense & Security Solutions",
    "JOBY": "Joby Aviation",
    "ACHR": "Archer Aviation",
    "TSLA": "Tesla",
    "COHR": "Coherent Corp",
}

# Cache fundamentals for 7 days (they don't change often)
CACHE_MAX_AGE_HOURS = 168


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


def alpha_vantage_request(function, symbol):
    """Make a request to Alpha Vantage."""
    env = load_env()
    api_key = env.get("ALPHA_VANTAGE_API_KEY", "")
    url = f"https://www.alphavantage.co/query?function={function}&symbol={symbol}&apikey={api_key}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OpenClaw/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            if "Note" in data or "Information" in data:
                print(f"  API limit hit: {data.get('Note', data.get('Information', ''))}")
                return None
            return data
    except Exception as e:
        print(f"  Error fetching {function} for {symbol}: {e}")
        return None


def fetch_company_overview(symbol):
    """Fetch company overview from Alpha Vantage."""
    print(f"  Fetching overview for {symbol}...")
    data = alpha_vantage_request("OVERVIEW", symbol)
    if not data or "Symbol" not in data:
        return None

    return {
        "symbol": data.get("Symbol"),
        "name": data.get("Name"),
        "description": data.get("Description"),
        "sector": data.get("Sector"),
        "industry": data.get("Industry"),
        "market_cap": safe_float(data.get("MarketCapitalization")),
        "pe_ratio": safe_float(data.get("PERatio")),
        "forward_pe": safe_float(data.get("ForwardPE")),
        "eps": safe_float(data.get("EPS")),
        "dividend_yield": safe_float(data.get("DividendYield")),
        "dividend_per_share": safe_float(data.get("DividendPerShare")),
        "revenue_ttm": safe_float(data.get("RevenueTTM")),
        "gross_profit_ttm": safe_float(data.get("GrossProfitTTM")),
        "ebitda": safe_float(data.get("EBITDA")),
        "profit_margin": safe_float(data.get("ProfitMargin")),
        "operating_margin": safe_float(data.get("OperatingMarginTTM")),
        "beta": safe_float(data.get("Beta")),
        "52_week_high": safe_float(data.get("52WeekHigh")),
        "52_week_low": safe_float(data.get("52WeekLow")),
        "50_day_ma": safe_float(data.get("50DayMovingAverage")),
        "200_day_ma": safe_float(data.get("200DayMovingAverage")),
        "shares_outstanding": safe_float(data.get("SharesOutstanding")),
        "book_value": safe_float(data.get("BookValue")),
        "price_to_book": safe_float(data.get("PriceToBookRatio")),
        "analyst_target": safe_float(data.get("AnalystTargetPrice")),
        "analyst_rating": data.get("AnalystRatingStrongBuy", "N/A"),
        "exchange": data.get("Exchange"),
        "country": data.get("Country"),
        "fiscal_year_end": data.get("FiscalYearEnd"),
    }


def fetch_earnings(symbol):
    """Fetch earnings data from Alpha Vantage."""
    print(f"  Fetching earnings for {symbol}...")
    data = alpha_vantage_request("EARNINGS", symbol)
    if not data:
        return None

    quarterly = []
    for e in data.get("quarterlyEarnings", [])[:8]:
        quarterly.append({
            "date": e.get("fiscalDateEnding"),
            "reported_eps": safe_float(e.get("reportedEPS")),
            "estimated_eps": safe_float(e.get("estimatedEPS")),
            "surprise": safe_float(e.get("surprise")),
            "surprise_pct": safe_float(e.get("surprisePercentage")),
        })

    annual = []
    for e in data.get("annualEarnings", [])[:5]:
        annual.append({
            "date": e.get("fiscalDateEnding"),
            "reported_eps": safe_float(e.get("reportedEPS")),
        })

    return {"quarterly": quarterly, "annual": annual}


def fetch_income_statement(symbol):
    """Fetch income statement from Alpha Vantage."""
    print(f"  Fetching income statement for {symbol}...")
    data = alpha_vantage_request("INCOME_STATEMENT", symbol)
    if not data:
        return None

    quarterly = []
    for r in data.get("quarterlyReports", [])[:8]:
        quarterly.append({
            "date": r.get("fiscalDateEnding"),
            "revenue": safe_float(r.get("totalRevenue")),
            "gross_profit": safe_float(r.get("grossProfit")),
            "operating_income": safe_float(r.get("operatingIncome")),
            "net_income": safe_float(r.get("netIncome")),
            "ebitda": safe_float(r.get("ebitda")),
        })

    annual = []
    for r in data.get("annualReports", [])[:5]:
        annual.append({
            "date": r.get("fiscalDateEnding"),
            "revenue": safe_float(r.get("totalRevenue")),
            "gross_profit": safe_float(r.get("grossProfit")),
            "operating_income": safe_float(r.get("operatingIncome")),
            "net_income": safe_float(r.get("netIncome")),
            "ebitda": safe_float(r.get("ebitda")),
        })

    return {"quarterly": quarterly, "annual": annual}


def fetch_balance_sheet(symbol):
    """Fetch balance sheet from Alpha Vantage."""
    print(f"  Fetching balance sheet for {symbol}...")
    data = alpha_vantage_request("BALANCE_SHEET", symbol)
    if not data:
        return None

    latest = data.get("quarterlyReports", [{}])[0] if data.get("quarterlyReports") else {}
    return {
        "date": latest.get("fiscalDateEnding"),
        "total_assets": safe_float(latest.get("totalAssets")),
        "total_liabilities": safe_float(latest.get("totalLiabilities")),
        "total_equity": safe_float(latest.get("totalShareholderEquity")),
        "cash": safe_float(latest.get("cashAndCashEquivalentsAtCarryingValue")),
        "short_term_debt": safe_float(latest.get("shortTermDebt")),
        "long_term_debt": safe_float(latest.get("longTermDebt")),
        "total_debt": safe_float(latest.get("shortLongTermDebtTotal")),
        "current_assets": safe_float(latest.get("totalCurrentAssets")),
        "current_liabilities": safe_float(latest.get("totalCurrentLiabilities")),
    }


def fetch_officers_sec(symbol):
    """Fetch company officers from SEC EDGAR."""
    cik = get_cik(symbol)
    if not cik:
        return []

    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "OpenClaw jaysamples@gmail.com",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        officers = []
        for filing in data.get("filings", {}).get("recent", {}).get("form", []):
            if filing in ["10-K", "DEF 14A"]:
                break

        # SEC doesn't give officers directly in the JSON — pull from company info
        name = data.get("name", "")
        former_names = [n.get("name", "") for n in data.get("formerNames", [])]

        # Officers are in the top-level if available
        if "officers" in data:
            for officer in data["officers"]:
                officers.append({
                    "name": officer.get("name", ""),
                    "title": officer.get("title", ""),
                })

        return officers
    except Exception as e:
        print(f"  SEC EDGAR error for {symbol}: {e}")
        return []


def get_cik(symbol):
    """Look up CIK number for a ticker symbol."""
    try:
        url = "https://www.sec.gov/files/company_tickers.json"
        req = urllib.request.Request(url, headers={
            "User-Agent": "OpenClaw jaysamples@gmail.com",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        for entry in data.values():
            if entry.get("ticker", "").upper() == symbol.upper():
                return str(entry["cik_str"]).zfill(10)
    except Exception as e:
        print(f"  CIK lookup error: {e}")
    return None


def safe_float(val):
    """Safely convert to float, return None if not possible."""
    if val is None or val == "None" or val == "-" or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def fmt_money(val):
    """Format a number as money (abbreviated)."""
    if val is None:
        return "N/A"
    if abs(val) >= 1e12:
        return f"${val/1e12:.2f}T"
    elif abs(val) >= 1e9:
        return f"${val/1e9:.2f}B"
    elif abs(val) >= 1e6:
        return f"${val/1e6:.2f}M"
    else:
        return f"${val:,.0f}"


def is_cache_fresh(symbol):
    """Check if cached data is still fresh."""
    cache_file = FUNDAMENTALS_DIR / f"{symbol}.json"
    if not cache_file.exists():
        return False
    data = json.loads(cache_file.read_text())
    fetched = data.get("fetched_at", "")
    if not fetched:
        return False
    try:
        fetched_dt = datetime.fromisoformat(fetched)
        age_hours = (datetime.now() - fetched_dt).total_seconds() / 3600
        return age_hours < CACHE_MAX_AGE_HOURS
    except ValueError:
        return False


def fetch_all(symbol):
    """Fetch all fundamental data for a symbol."""
    if is_cache_fresh(symbol):
        print(f"  {symbol}: Using cached data (< 7 days old)")
        return json.loads((FUNDAMENTALS_DIR / f"{symbol}.json").read_text())

    print(f"\nFetching fundamentals for {symbol}...")

    result = {
        "symbol": symbol,
        "name": STOCK_NAMES.get(symbol, symbol),
        "fetched_at": datetime.now().isoformat(),
    }

    # Fetch with rate limiting (12s between calls for free tier)
    overview = fetch_company_overview(symbol)
    if overview:
        result["overview"] = overview
    time.sleep(12)

    earnings = fetch_earnings(symbol)
    if earnings:
        result["earnings"] = earnings
    time.sleep(12)

    income = fetch_income_statement(symbol)
    if income:
        result["income_statement"] = income
    time.sleep(12)

    balance = fetch_balance_sheet(symbol)
    if balance:
        result["balance_sheet"] = balance
    time.sleep(12)

    officers = fetch_officers_sec(symbol)
    if officers:
        result["officers"] = officers
    time.sleep(1)

    # Save cache
    cache_file = FUNDAMENTALS_DIR / f"{symbol}.json"
    cache_file.write_text(json.dumps(result, indent=2))

    return result


def generate_fundamental_report(symbol):
    """Generate a markdown fundamental analysis for one symbol."""
    cache_file = FUNDAMENTALS_DIR / f"{symbol}.json"
    if not cache_file.exists():
        return f"## {symbol} - No fundamental data available\n\n---\n"

    data = json.loads(cache_file.read_text())
    ov = data.get("overview", {})
    bs = data.get("balance_sheet", {})
    earn = data.get("earnings", {})
    inc = data.get("income_statement", {})
    officers = data.get("officers", [])

    lines = []
    lines.append(f"## {symbol} - {ov.get('name', STOCK_NAMES.get(symbol, symbol))}")
    lines.append("")

    # Company description
    desc = ov.get("description", "")
    if desc:
        lines.append(f"_{desc[:300]}{'...' if len(desc) > 300 else ''}_")
        lines.append("")

    # Key metrics
    lines.append("**Key Metrics:**")
    lines.append(f"  Sector: {ov.get('sector', 'N/A')} | Industry: {ov.get('industry', 'N/A')}")
    lines.append(f"  Market Cap: {fmt_money(ov.get('market_cap'))}")
    lines.append(f"  P/E: {ov.get('pe_ratio', 'N/A')} | Forward P/E: {ov.get('forward_pe', 'N/A')}")
    lines.append(f"  EPS: ${ov.get('eps', 'N/A')} | Beta: {ov.get('beta', 'N/A')}")
    div_y = ov.get('dividend_yield')
    lines.append(f"  Dividend Yield: {div_y*100:.2f}%" if div_y else "  Dividend Yield: None")
    lines.append(f"  52-Week Range: ${ov.get('52_week_low', 'N/A')} - ${ov.get('52_week_high', 'N/A')}")
    lines.append(f"  50-Day MA: ${ov.get('50_day_ma', 'N/A')} | 200-Day MA: ${ov.get('200_day_ma', 'N/A')}")
    lines.append(f"  Analyst Target: ${ov.get('analyst_target', 'N/A')}")
    lines.append("")

    # Revenue & profitability
    lines.append("**Financials (TTM):**")
    lines.append(f"  Revenue: {fmt_money(ov.get('revenue_ttm'))}")
    lines.append(f"  Gross Profit: {fmt_money(ov.get('gross_profit_ttm'))}")
    lines.append(f"  EBITDA: {fmt_money(ov.get('ebitda'))}")
    pm = ov.get('profit_margin')
    om = ov.get('operating_margin')
    lines.append(f"  Profit Margin: {pm*100:.1f}%" if pm else "  Profit Margin: N/A")
    lines.append(f"  Operating Margin: {om*100:.1f}%" if om else "  Operating Margin: N/A")
    lines.append("")

    # Balance sheet
    if bs:
        lines.append(f"**Balance Sheet ({bs.get('date', 'N/A')}):**")
        lines.append(f"  Total Assets: {fmt_money(bs.get('total_assets'))}")
        lines.append(f"  Total Liabilities: {fmt_money(bs.get('total_liabilities'))}")
        lines.append(f"  Shareholder Equity: {fmt_money(bs.get('total_equity'))}")
        lines.append(f"  Cash: {fmt_money(bs.get('cash'))}")
        lines.append(f"  Total Debt: {fmt_money(bs.get('total_debt'))}")
        ca = bs.get('current_assets')
        cl = bs.get('current_liabilities')
        if ca and cl and cl > 0:
            lines.append(f"  Current Ratio: {ca/cl:.2f}")
        lines.append("")

    # Earnings history
    q_earnings = earn.get("quarterly", [])
    if q_earnings:
        lines.append("**Recent Earnings:**")
        for e in q_earnings[:4]:
            surprise_str = ""
            if e.get("surprise_pct") is not None:
                surprise_str = f" | Surprise: {e['surprise_pct']:+.1f}%"
            lines.append(
                f"  {e['date']}: EPS ${e.get('reported_eps', 'N/A')}"
                f" (est. ${e.get('estimated_eps', 'N/A')}){surprise_str}"
            )
        lines.append("")

    # Revenue trend
    q_income = inc.get("quarterly", []) if inc else []
    if q_income:
        lines.append("**Quarterly Revenue Trend:**")
        for q in q_income[:4]:
            ni = q.get('net_income')
            ni_str = f" | Net Income: {fmt_money(ni)}" if ni is not None else ""
            lines.append(f"  {q['date']}: Revenue {fmt_money(q.get('revenue'))}{ni_str}")
        lines.append("")

    # Officers
    if officers:
        lines.append("**Leadership:**")
        for o in officers[:8]:
            lines.append(f"  {o.get('name', 'N/A')} - {o.get('title', 'N/A')}")
        lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def print_usage():
    print("OpenClaw Fundamentals Fetcher")
    print()
    print("Usage:")
    print("  python3 fundamentals.py fetch           - Fetch all watchlist fundamentals")
    print("  python3 fundamentals.py fetch TSLA       - Fetch one symbol")
    print("  python3 fundamentals.py report           - Generate fundamental reports")
    print("  python3 fundamentals.py report TSLA      - Report for one symbol")
    print("  python3 fundamentals.py show TSLA        - Show cached data as JSON")
    print()
    print(f"Cache: {FUNDAMENTALS_DIR} (refreshes weekly)")
    print(f"Watchlist: {', '.join(WATCHLIST)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "fetch":
        symbols = [sys.argv[2].upper()] if len(sys.argv) > 2 else WATCHLIST
        # Alpha Vantage free tier: 25 calls/day, 4 calls per symbol
        # Can only do ~6 symbols per run
        for symbol in symbols:
            fetch_all(symbol)
        print("\nFundamentals fetch complete.")

    elif cmd == "report":
        symbols = [sys.argv[2].upper()] if len(sys.argv) > 2 else WATCHLIST
        print("# OpenClaw Fundamental Analysis")
        print(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M ET')}")
        print()
        print("---")
        print()
        for symbol in symbols:
            print(generate_fundamental_report(symbol))

    elif cmd == "show":
        if len(sys.argv) < 3:
            print("Usage: fundamentals.py show SYMBOL")
            sys.exit(1)
        symbol = sys.argv[2].upper()
        cache_file = FUNDAMENTALS_DIR / f"{symbol}.json"
        if cache_file.exists():
            print(cache_file.read_text())
        else:
            print(f"No cached data for {symbol}. Run: fundamentals.py fetch {symbol}")

    else:
        print_usage()
