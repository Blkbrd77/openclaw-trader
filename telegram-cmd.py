#!/usr/bin/env python3
"""OpenClaw Telegram Command Handler - Respond to commands via Telegram"""

import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

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
STATE_FILE = Path(os.path.expanduser("~/.openclaw/monitor/cmd_last_update_id"))

COMMANDS = {
    "/metrics": {
        "description": "Pi system metrics summary",
        "cmd": ["metrics-viewer", "today", "--summary"],
    },
    "/tail": {
        "description": "Last 10 metric readings",
        "cmd": ["metrics-viewer", "today", "--tail"],
    },
    "/costs": {
        "description": "Weekly cost summary",
        "cmd": ["python3", os.path.expanduser("~/.openclaw/workspace/costtracker.py"), "summary"],
    },
    "/status": {
        "description": "Gateway and system status",
        "shell": True,
        "cmd": (
            "echo '=== OpenClaw Status ==='; echo '';"
            "echo \"Date: $(date)\";"
            "echo \"Uptime: $(uptime -p)\";"
            "echo '';"
            "echo '--- Gateway ---';"
            "systemctl --user is-active openclaw-gateway && echo 'Gateway: RUNNING' || echo 'Gateway: DOWN';"
            "echo '';"
            "echo '--- Resources ---';"
            "echo \"CPU Temp: $(vcgencmd measure_temp 2>/dev/null || echo 'N/A')\";"
            "echo \"Memory: $(free -h | awk '/Mem:/ {printf \"%s / %s (%s used)\", $3, $2, $3/$2*100}')\";"
            "echo \"Disk: $(df -h / | awk 'NR==2 {printf \"%s / %s (%s)\", $3, $2, $5}')\";"
            "echo \"Load: $(cat /proc/loadavg | awk '{print $1, $2, $3}')\";"
            "echo '';"
            "echo '--- Tailscale ---';"
            "tailscale status 2>/dev/null | head -3 || echo 'N/A'"
        ),
    },
    "/portfolio": {
        "description": "Portfolio status from Alpaca",
        "cmd": ["python3", os.path.expanduser("~/.openclaw/workspace/trader.py"), "status"],
    },
    "/help": {
        "description": "Show available commands",
        "builtin": "help",
    },
}


def get_chat_id():
    if CHAT_ID_FILE.exists():
        return CHAT_ID_FILE.read_text().strip()
    return None


def get_last_update_id():
    if STATE_FILE.exists():
        return int(STATE_FILE.read_text().strip())
    return 0


def save_last_update_id(uid):
    STATE_FILE.write_text(str(uid))


def send_message(chat_id, text):
    """Send a message, splitting if over 4096 chars."""
    bot_token = load_env().get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        print("Telegram not configured: TELEGRAM_BOT_TOKEN missing from .env.")
        return
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "",
        }).encode()
        try:
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{bot_token}/sendMessage", data=data
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            print(f"Send error: {e}")


def run_command(cmd_key):
    """Execute a command and return output."""
    cmd_info = COMMANDS[cmd_key]

    if cmd_info.get("builtin") == "help":
        lines = ["OpenClaw Commands:\n"]
        for k, v in COMMANDS.items():
            lines.append(f"  {k} - {v['description']}")
        return "\n".join(lines)

    try:
        if cmd_info.get("shell"):
            result = subprocess.run(
                cmd_info["cmd"], shell=True, capture_output=True, text=True, timeout=30
            )
        else:
            result = subprocess.run(
                cmd_info["cmd"], capture_output=True, text=True, timeout=30
            )
        output = result.stdout.strip()
        if result.stderr.strip():
            output += f"\n\n(stderr: {result.stderr.strip()[:200]})"
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out (30s limit)"
    except Exception as e:
        return f"Error: {e}"


def poll_once():
    """Check for new messages and respond to commands."""
    chat_id = get_chat_id()
    if not chat_id:
        return

    bot_token = load_env().get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        print("Telegram not configured: TELEGRAM_BOT_TOKEN missing from .env.")
        return

    last_id = get_last_update_id()

    try:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates?offset={last_id + 1}&timeout=1"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return

    for update in data.get("result", []):
        update_id = update["update_id"]
        save_last_update_id(update_id)

        msg = update.get("message", {})
        text = msg.get("text", "").strip().lower()
        msg_chat_id = str(msg.get("chat", {}).get("id", ""))

        # Only respond to our paired chat
        if msg_chat_id != chat_id:
            continue

        # Match command (ignore args for now)
        cmd_key = text.split()[0] if text else ""

        if cmd_key in COMMANDS:
            print(f"[{time.strftime('%H:%M:%S')}] Command: {cmd_key}")
            output = run_command(cmd_key)
            send_message(chat_id, output)
        elif cmd_key.startswith("/"):
            send_message(chat_id, f"Unknown command: {cmd_key}\n\nType /help for available commands.")


def run_daemon():
    """Run as a persistent polling daemon."""
    print("OpenClaw Telegram Command Handler started")
    print(f"Chat ID: {get_chat_id()}")
    print(f"Listening for commands: {', '.join(COMMANDS.keys())}")
    print("Press Ctrl+C to stop\n")

    while True:
        try:
            poll_once()
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Poll error: {e}")
        time.sleep(3)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        poll_once()
    else:
        run_daemon()
