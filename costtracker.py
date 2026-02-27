#!/usr/bin/env python3
"""OpenClaw API Cost Tracker - Tracks API usage and estimated costs"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

COSTS_DIR = Path(os.path.expanduser("~/.openclaw/costs"))
COSTS_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR = Path(os.path.expanduser("~/.openclaw/logs"))

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

CHAT_ID_FILE = Path(os.path.expanduser("~/.openclaw/monitor/chat_id"))

# Cost estimates per API call (conservative estimates)
COST_PER_CALL = {
    "claude": {
        "haiku_input_1k": 0.001,     # $1/MTok input
        "haiku_output_1k": 0.005,    # $5/MTok output
        "avg_call": 0.002,           # ~2k input + 500 output avg
    },
    "alpha_vantage": {
        "per_call": 0.00,            # Free tier (25/day)
        "daily_limit": 25,
    },
    "alpaca": {
        "per_call": 0.00,            # Free paper trading
    },
    "telegram": {
        "per_call": 0.00,            # Free
    },
}

# Alert thresholds
DAILY_ALERT_THRESHOLD = 1.00   # $1/day
MONTHLY_ALERT_THRESHOLD = 5.00  # $5/month


def get_today_file():
    today = datetime.now().strftime("%Y-%m-%d")
    return COSTS_DIR / f"costs_{today}.json"


def load_today():
    f = get_today_file()
    if f.exists():
        return json.loads(f.read_text())
    return {"date": datetime.now().strftime("%Y-%m-%d"), "services": {}, "total_estimated": 0}


def save_today(data):
    get_today_file().write_text(json.dumps(data, indent=2))


def record_api_call(service, endpoint="", tokens_in=0, tokens_out=0):
    """Record an API call for cost tracking."""
    data = load_today()

    if service not in data["services"]:
        data["services"][service] = {
            "calls": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "estimated_cost": 0,
        }

    svc = data["services"][service]
    svc["calls"] += 1
    svc["tokens_in"] += tokens_in
    svc["tokens_out"] += tokens_out

    # Estimate cost
    if service == "claude":
        cost = (tokens_in / 1000) * COST_PER_CALL["claude"]["haiku_input_1k"]
        cost += (tokens_out / 1000) * COST_PER_CALL["claude"]["haiku_output_1k"]
        if cost == 0:
            cost = COST_PER_CALL["claude"]["avg_call"]
        svc["estimated_cost"] += cost
    else:
        svc["estimated_cost"] += COST_PER_CALL.get(service, {}).get("per_call", 0)

    # Recalculate total
    data["total_estimated"] = sum(s["estimated_cost"] for s in data["services"].values())

    save_today(data)
    return data


def scan_logs_for_api_calls():
    """Scan structured logs for API calls and update cost tracking."""
    app_log = LOG_DIR / "openclaw-app.log"
    if not app_log.exists():
        return 0

    data = load_today()
    today = datetime.now().strftime("%Y-%m-%d")
    counted = 0

    for line in app_log.read_text().splitlines():
        try:
            entry = json.loads(line)
            ctx = entry.get("context", {})
            if ctx.get("type") == "api_call":
                ts = entry.get("timestamp", "")
                if today in ts:
                    service = ctx.get("service", "unknown")
                    record_api_call(service, ctx.get("endpoint", ""))
                    counted += 1
        except (json.JSONDecodeError, KeyError):
            continue

    return counted


def get_weekly_summary():
    """Generate weekly cost summary."""
    total_cost = 0
    total_calls = 0
    daily_costs = []
    services_total = {}

    for i in range(7):
        day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        f = COSTS_DIR / f"costs_{day}.json"
        if f.exists():
            data = json.loads(f.read_text())
            day_cost = data.get("total_estimated", 0)
            total_cost += day_cost
            daily_costs.append({"date": day, "cost": day_cost})

            for svc_name, svc_data in data.get("services", {}).items():
                if svc_name not in services_total:
                    services_total[svc_name] = {"calls": 0, "cost": 0}
                services_total[svc_name]["calls"] += svc_data.get("calls", 0)
                services_total[svc_name]["cost"] += svc_data.get("estimated_cost", 0)
                total_calls += svc_data.get("calls", 0)

    monthly_projection = (total_cost / max(len(daily_costs), 1)) * 30

    lines = []
    lines.append("*OPENCLAW WEEKLY COST REPORT*\n")
    lines.append(f"*Period:* Last 7 days")
    lines.append(f"*Total Estimated Cost:* ${total_cost:.4f}")
    lines.append(f"*Total API Calls:* {total_calls}")
    lines.append(f"*Monthly Projection:* ${monthly_projection:.2f}\n")

    if services_total:
        lines.append("*By Service:*")
        for svc, data in sorted(services_total.items()):
            lines.append(f"  {svc}: {data['calls']} calls (${data['cost']:.4f})")

    if daily_costs:
        lines.append("\n*Daily Breakdown:*")
        for dc in daily_costs:
            lines.append(f"  {dc['date']}: ${dc['cost']:.4f}")

    # Alert status
    today_data = load_today()
    today_cost = today_data.get("total_estimated", 0)
    if today_cost > DAILY_ALERT_THRESHOLD:
        lines.append(f"\n*ALERT:* Today's cost ${today_cost:.4f} exceeds ${DAILY_ALERT_THRESHOLD:.2f} threshold")
    if monthly_projection > MONTHLY_ALERT_THRESHOLD:
        lines.append(f"*ALERT:* Monthly projection ${monthly_projection:.2f} exceeds ${MONTHLY_ALERT_THRESHOLD:.2f} threshold")

    return "\n".join(lines)


def check_alerts():
    """Check if cost thresholds are exceeded and send alerts."""
    data = load_today()
    today_cost = data.get("total_estimated", 0)
    alerts = []

    if today_cost > DAILY_ALERT_THRESHOLD:
        alerts.append(f"Daily cost ${today_cost:.4f} exceeds ${DAILY_ALERT_THRESHOLD:.2f}")

    # Check monthly projection
    total_7d = 0
    days_with_data = 0
    for i in range(7):
        day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        f = COSTS_DIR / f"costs_{day}.json"
        if f.exists():
            d = json.loads(f.read_text())
            total_7d += d.get("total_estimated", 0)
            days_with_data += 1

    if days_with_data > 0:
        monthly_proj = (total_7d / days_with_data) * 30
        if monthly_proj > MONTHLY_ALERT_THRESHOLD:
            alerts.append(f"Monthly projection ${monthly_proj:.2f} exceeds ${MONTHLY_ALERT_THRESHOLD:.2f}")

    if alerts:
        send_telegram("*COST ALERT*\n\n" + "\n".join(f"- {a}" for a in alerts))

    return alerts


def send_telegram(msg):
    BOT_TOKEN = load_env().get("TELEGRAM_BOT_TOKEN", "")
    if not CHAT_ID_FILE.exists():
        return
    chat_id = CHAT_ID_FILE.read_text().strip()
    data = urllib.parse.urlencode({
        "chat_id": chat_id, "text": msg, "parse_mode": "Markdown"
    }).encode()
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data=data
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")


def cleanup_old_costs(days=90):
    """Remove cost files older than N days."""
    cutoff = datetime.now() - timedelta(days=days)
    for f in COSTS_DIR.glob("costs_*.json"):
        try:
            date_str = f.stem.replace("costs_", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            if file_date < cutoff:
                f.unlink()
        except ValueError:
            continue


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"

    if cmd == "summary":
        print(get_weekly_summary())
    elif cmd == "today":
        data = load_today()
        print(json.dumps(data, indent=2))
    elif cmd == "scan":
        counted = scan_logs_for_api_calls()
        print(f"Scanned {counted} API calls from logs")
    elif cmd == "check":
        alerts = check_alerts()
        if alerts:
            print("Alerts triggered:")
            for a in alerts:
                print(f"  - {a}")
        else:
            print("No alerts - costs within thresholds")
    elif cmd == "weekly":
        summary = get_weekly_summary()
        print(summary)
        send_telegram(summary)
        print("\nSent to Telegram.")
    else:
        print("OpenClaw Cost Tracker")
        print("  costtracker.py summary   - Show weekly summary")
        print("  costtracker.py today     - Show today's costs")
        print("  costtracker.py scan      - Scan logs for API calls")
        print("  costtracker.py check     - Check alert thresholds")
        print("  costtracker.py weekly    - Send weekly report to Telegram")
