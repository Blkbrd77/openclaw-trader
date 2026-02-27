#!/usr/bin/env python3
"""OpenClaw Paper Trader - Alpaca integration with risk constraints and human approval"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(os.path.expanduser("~/.openclaw/workspace"))
TRADES_DIR = WORKSPACE / "trades"
REPORTS_DIR = WORKSPACE / "reports"

# Telegram config
BOT_TOKEN = None  # loaded from .env via load_env()
CHAT_ID_FILE = Path(os.path.expanduser("~/.openclaw/monitor/chat_id"))

# Alpaca paper trading base URL
ALPACA_BASE = "https://paper-api.alpaca.markets/v2"

# Risk constraints (per KAN-30)
MAX_PORTFOLIO_VALUE = 100.00  # $100 seed budget
MAX_POSITIONS = 5
MAX_POSITION_PCT = 0.30  # 30% max per position
NO_MARGIN = True
NO_OPTIONS = True

WATCHLIST = ["AVAV", "KTOS", "JOBY", "ACHR", "TSLA", "COHR"]


def load_env():
    """Load API keys from .env file."""
    env_file = WORKSPACE / ".env"
    env = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                env[key.strip()] = val.strip()
    return env


def alpaca_request(method, endpoint, data=None):
    """Make an authenticated request to Alpaca API."""
    env = load_env()
    api_key = env.get("ALPACA_API_KEY", "")
    secret_key = env.get("ALPACA_SECRET_KEY", "")

    url = f"{ALPACA_BASE}{endpoint}"
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key,
        "Content-Type": "application/json",
    }

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  Alpaca API error {e.code}: {error_body}")
        return {"error": error_body, "status": e.code}
    except Exception as e:
        print(f"  Request error: {e}")
        return {"error": str(e)}


def get_account():
    """Get paper trading account details."""
    return alpaca_request("GET", "/account")


def get_positions():
    """Get current open positions."""
    return alpaca_request("GET", "/positions")


def get_position(symbol):
    """Get position for a specific symbol."""
    result = alpaca_request("GET", f"/positions/{symbol}")
    if "error" in result:
        return None
    return result


def get_orders(status="open"):
    """Get orders by status."""
    return alpaca_request("GET", f"/orders?status={status}&limit=50")


def submit_order(symbol, qty, side, order_type="market", time_in_force="day"):
    """Submit an order to Alpaca."""
    data = {
        "symbol": symbol,
        "qty": str(qty),
        "side": side,
        "type": order_type,
        "time_in_force": time_in_force,
    }
    return alpaca_request("POST", "/orders", data)


def get_latest_price(symbol):
    """Get latest price from Alpaca."""
    env = load_env()
    api_key = env.get("ALPACA_API_KEY", "")
    secret_key = env.get("ALPACA_SECRET_KEY", "")

    url = f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest"
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key,
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return float(data.get("quote", {}).get("ap", 0))
    except Exception:
        return None


# --- Risk Engine (KAN-30) ---

def check_risk_constraints(symbol, side, qty, price):
    """Check if a proposed trade passes all risk constraints."""
    violations = []

    account = get_account()
    portfolio_value = float(account.get("portfolio_value", 0))
    cash = float(account.get("cash", 0))
    positions = get_positions()
    if isinstance(positions, dict) and "error" in positions:
        positions = []

    num_positions = len(positions)
    trade_value = qty * price

    if side == "buy":
        # Check total portfolio doesn't exceed seed budget
        if portfolio_value + trade_value > MAX_PORTFOLIO_VALUE:
            violations.append(f"Trade would exceed ${MAX_PORTFOLIO_VALUE:.2f} budget (current: ${portfolio_value:.2f}, trade: ${trade_value:.2f})")

        # Check max positions
        existing = any(p["symbol"] == symbol for p in positions)
        if not existing and num_positions >= MAX_POSITIONS:
            violations.append(f"Already at max {MAX_POSITIONS} positions")

        # Check single position size
        max_allowed = MAX_PORTFOLIO_VALUE * MAX_POSITION_PCT
        current_position_value = 0
        for p in positions:
            if p["symbol"] == symbol:
                current_position_value = abs(float(p.get("market_value", 0)))
        if current_position_value + trade_value > max_allowed:
            violations.append(f"Position would exceed {MAX_POSITION_PCT*100:.0f}% limit (${max_allowed:.2f})")

        # Check cash available
        if trade_value > cash:
            violations.append(f"Insufficient cash (need ${trade_value:.2f}, have ${cash:.2f})")

    return violations


# --- Trade Logging ---

def log_trade(trade_data):
    """Log a trade proposal/execution to the audit trail."""
    TRADES_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = TRADES_DIR / f"trades_{today}.json"

    trades = []
    if log_file.exists():
        trades = json.loads(log_file.read_text())

    trade_data["timestamp"] = datetime.now().isoformat()
    trades.append(trade_data)
    log_file.write_text(json.dumps(trades, indent=2))


# --- Telegram Integration (KAN-31) ---

def send_telegram(msg):
    BOT_TOKEN = load_env().get("TELEGRAM_BOT_TOKEN", "")
    """Send a message via Telegram."""
    if not CHAT_ID_FILE.exists():
        print("No Telegram chat ID configured.")
        return
    chat_id = CHAT_ID_FILE.read_text().strip()
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "Markdown",
    }).encode()
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data=data
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")


def request_approval(symbol, side, qty, price, reasoning):
    """Send trade proposal to Telegram and wait for approval."""
    trade_value = qty * price
    msg = (
        f"*TRADE PROPOSAL*\n\n"
        f"*Action:* {side.upper()} {qty} x {symbol}\n"
        f"*Price:* ${price:.2f}\n"
        f"*Value:* ${trade_value:.2f}\n\n"
        f"*Reasoning:* {reasoning}\n\n"
        f"Reply *yes* to approve, *no* to reject."
    )
    send_telegram(msg)

    log_trade({
        "type": "proposal",
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "price": price,
        "value": trade_value,
        "reasoning": reasoning,
        "status": "pending_approval",
    })

    print(f"\nTrade proposal sent to Telegram. Waiting for approval...")
    print(f"  {side.upper()} {qty} x {symbol} @ ${price:.2f} = ${trade_value:.2f}")
    print(f"  Reasoning: {reasoning}")

    return wait_for_approval()


def wait_for_approval(timeout_seconds=3600):
    """Poll Telegram for approval response. Timeout = 1 hour."""
    env = load_env()
    start = time.time()
    last_update_id = 0

    while time.time() - start < timeout_seconds:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=10"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())

            for update in data.get("result", []):
                last_update_id = update["update_id"]
                msg = update.get("message", {})
                text = msg.get("text", "").strip().lower()

                if text in ["yes", "y", "approve"]:
                    return "approved"
                elif text in ["no", "n", "reject", "deny"]:
                    return "rejected"
                elif text.startswith("modify"):
                    return f"modify:{text}"

        except Exception:
            pass

        time.sleep(5)

    return "timeout"


# --- Position Tracker & P&L (KAN-32) ---

def get_portfolio_summary():
    """Generate portfolio summary with P&L."""
    account = get_account()
    positions = get_positions()
    if isinstance(positions, dict):
        positions = []

    portfolio_value = float(account.get("portfolio_value", 0))
    cash = float(account.get("cash", 0))
    equity = float(account.get("equity", 0))

    summary = []
    summary.append("*PORTFOLIO SUMMARY*\n")
    summary.append(f"*Cash:* ${cash:.2f}")
    summary.append(f"*Portfolio Value:* ${portfolio_value:.2f}")
    summary.append(f"*Equity:* ${equity:.2f}")
    summary.append(f"*Positions:* {len(positions)}/{MAX_POSITIONS}\n")

    total_unrealized = 0

    if positions:
        summary.append("*Open Positions:*")
        for p in positions:
            sym = p["symbol"]
            qty = float(p["qty"])
            avg_entry = float(p["avg_entry_price"])
            current = float(p["current_price"])
            market_val = float(p["market_value"])
            unrealized = float(p["unrealized_pl"])
            unrealized_pct = float(p["unrealized_plpc"]) * 100
            total_unrealized += unrealized

            arrow = "+" if unrealized >= 0 else ""
            summary.append(
                f"  {sym}: {qty:.0f} shares @ ${avg_entry:.2f} | "
                f"Now ${current:.2f} | {arrow}${unrealized:.2f} ({arrow}{unrealized_pct:.1f}%)"
            )
    else:
        summary.append("_No open positions_")

    summary.append(f"\n*Total Unrealized P&L:* ${total_unrealized:+.2f}")

    # Get recent closed trades
    orders = get_orders("closed")
    if isinstance(orders, list) and orders:
        recent = orders[:5]
        summary.append(f"\n*Recent Orders:*")
        for o in recent:
            filled_qty = o.get("filled_qty", "0")
            filled_price = o.get("filled_avg_price") or "N/A"
            summary.append(
                f"  {o['side'].upper()} {filled_qty} x {o['symbol']} "
                f"@ {'$' + format(float(filled_price), '.2f') if filled_price != 'N/A' else 'N/A'} "
                f"({o['status']})"
            )

    return "\n".join(summary)


# --- Main Commands ---

def cmd_status():
    """Show account status and positions."""
    print("Fetching portfolio status...")
    summary = get_portfolio_summary()
    print(summary)
    return summary


def cmd_propose(symbol, side, qty, reasoning="Manual proposal"):
    """Propose a trade with risk checks and human approval."""
    symbol = symbol.upper()
    side = side.lower()

    if symbol not in WATCHLIST:
        print(f"  {symbol} is not in watchlist: {WATCHLIST}")
        return

    if side not in ["buy", "sell"]:
        print("  Side must be 'buy' or 'sell'")
        return

    # Get current price
    price = get_latest_price(symbol)
    if not price:
        print(f"  Could not get price for {symbol}")
        return

    print(f"\n  {side.upper()} {qty} x {symbol} @ ~${price:.2f} = ${qty * price:.2f}")

    # Risk checks
    violations = check_risk_constraints(symbol, side, qty, price)
    if violations:
        print("\n  RISK VIOLATIONS:")
        for v in violations:
            print(f"    - {v}")
        log_trade({
            "type": "blocked",
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "violations": violations,
        })
        send_telegram(f"*TRADE BLOCKED*\n{side.upper()} {qty} x {symbol}\n\nViolations:\n" + "\n".join(f"- {v}" for v in violations))
        return

    # Request human approval
    approval = request_approval(symbol, side, qty, price, reasoning)

    if approval == "approved":
        print("\n  APPROVED - Executing trade...")
        result = submit_order(symbol, qty, side)
        if "error" not in result:
            log_trade({
                "type": "executed",
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "price": price,
                "order_id": result.get("id"),
                "status": result.get("status"),
            })
            send_telegram(f"*TRADE EXECUTED*\n{side.upper()} {qty} x {symbol}\nOrder ID: {result.get('id', 'N/A')}\nStatus: {result.get('status', 'N/A')}")
            print(f"  Order submitted: {result.get('status')}")
        else:
            print(f"  Order failed: {result}")
            send_telegram(f"*TRADE FAILED*\n{side.upper()} {qty} x {symbol}\nError: {result.get('error')}")
    elif approval == "rejected":
        print("\n  REJECTED by user.")
        log_trade({
            "type": "rejected",
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "reasoning": reasoning,
        })
        send_telegram(f"*TRADE REJECTED*\n{side.upper()} {qty} x {symbol} - Rejected by Jay.")
    elif approval == "timeout":
        print("\n  TIMED OUT - Auto-rejected after 1 hour.")
        log_trade({
            "type": "timeout",
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
        })
        send_telegram(f"*TRADE EXPIRED*\n{side.upper()} {qty} x {symbol} - No response in 1 hour. Auto-rejected.")
    else:
        print(f"\n  Response: {approval}")


def cmd_daily_summary():
    """Send daily portfolio summary to Telegram."""
    summary = get_portfolio_summary()
    send_telegram(summary)
    print("Daily summary sent to Telegram.")


def print_usage():
    print("OpenClaw Paper Trader")
    print()
    print("Usage:")
    print("  python3 trader.py status              - Show portfolio status")
    print("  python3 trader.py propose TSLA buy 1 'reasoning here'")
    print("                                        - Propose a trade (requires approval)")
    print("  python3 trader.py summary              - Send daily summary to Telegram")
    print("  python3 trader.py test                 - Run connection test")
    print()


def cmd_test():
    """Test Alpaca connection."""
    print("Testing Alpaca connection...")
    account = get_account()
    if "error" in account:
        print(f"  FAILED: {account['error']}")
        return

    print(f"  Account: {account['account_number']}")
    print(f"  Status: {account['status']}")
    print(f"  Cash: ${float(account['cash']):,.2f}")
    print(f"  Portfolio: ${float(account['portfolio_value']):,.2f}")
    print(f"  Buying Power: ${float(account['buying_power']):,.2f}")
    print("  Connection OK!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "status":
        cmd_status()
    elif cmd == "test":
        cmd_test()
    elif cmd == "summary":
        cmd_daily_summary()
    elif cmd == "propose":
        if len(sys.argv) < 5:
            print("Usage: trader.py propose SYMBOL buy|sell QTY [reasoning]")
            sys.exit(1)
        symbol = sys.argv[2]
        side = sys.argv[3]
        qty = int(sys.argv[4])
        reasoning = " ".join(sys.argv[5:]) if len(sys.argv) > 5 else "Manual proposal"
        cmd_propose(symbol, side, qty, reasoning)
    else:
        print_usage()
