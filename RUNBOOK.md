# OpenClaw Operational Runbook

**Last Updated:** 2026-02-23
**System:** Raspberry Pi 5 + Hailo-10H AI HAT+ 2
**OS:** Raspberry Pi OS (Debian-based)
**Access:** SSH via LAN (10.0.0.175) or Tailscale (100.66.59.84)

---

## 1. Gateway Not Running

**Symptoms:** Telegram bot unresponsive, no trade alerts, monitor sends "GATEWAY DOWN" alert

**Diagnosis:**
```bash
systemctl --user status openclaw-gateway
journalctl --user -u openclaw-gateway --since "30 min ago" --no-pager | tail -20
```

**Resolution:**
```bash
# Check if kill switch is engaged
ls ~/.openclaw/killswitch.lock

# If kill switch is engaged, restore first
~/bin/killswitch-restore

# If no kill switch, just restart
systemctl --user restart openclaw-gateway

# Verify
systemctl --user status openclaw-gateway
```

**Rollback:** If gateway keeps crashing, engage kill switch: `~/bin/killswitch`

---

## 2. Gateway Crash Loop

**Symptoms:** Gateway restarts repeatedly, high CPU from systemd restarts

**Diagnosis:**
```bash
journalctl --user -u openclaw-gateway --since "1 hour ago" --no-pager | grep -i "error\|fatal\|crash"
systemctl --user show openclaw-gateway | grep NRestarts
```

**Resolution:**
```bash
# Stop the crash loop
~/bin/killswitch

# Check logs for root cause
journalctl --user -u openclaw-gateway --since "1 hour ago" --no-pager > /tmp/crash-logs.txt
less /tmp/crash-logs.txt

# Common fixes:
# - Config error: openclaw doctor
# - Memory: free -h (restart if OOM)
# - Disk full: df -h (clean logs)

# After fixing, restore
~/bin/killswitch-restore
```

**Rollback:** Keep kill switch engaged until root cause is identified

---

## 3. API Key Rotation

**Symptoms:** 401/403 errors in logs, API calls failing

**Diagnosis:**
```bash
grep -i "401\|403\|unauthorized\|forbidden" ~/.openclaw/logs/openclaw-app.log | tail -10
```

**Resolution:**

For **Claude API key:**
```bash
# Generate new key at console.anthropic.com
openclaw config set auth.profiles.anthropic:default.key NEW_KEY_HERE
# Verify
openclaw doctor
```

For **Alpha Vantage / Alpaca / Telegram keys:**
```bash
nano ~/.openclaw/workspace/.env
# Update the relevant key
# ALPHA_VANTAGE_API_KEY=new_key
# ALPACA_API_KEY=new_key
# ALPACA_SECRET_KEY=new_secret
# TELEGRAM_BOT_TOKEN=new_token_from_BotFather
# NEVER commit this file — it is listed in .gitignore
```

For **Jira API token** (on Mac):
```bash
nano /Users/jaysamples/devproj/openclaw-jira-setup/.env
# Update JIRA_API_TOKEN=new_token
```

**Rollback:** Keep old key until new one is verified working

---

## 4. Disk Full

**Symptoms:** Services failing to write, "No space left on device" errors

**Diagnosis:**
```bash
df -h /
du -sh ~/.openclaw/logs/ ~/.openclaw/metrics/ ~/.openclaw/workspace/news-data/ ~/.openclaw/workspace/market-data/
```

**Resolution:**
```bash
# Clean old logs (keep last 3 days)
find ~/.openclaw/logs/ -name "*.log.*" -mtime +3 -delete

# Clean old metrics (keep last 30 days - auto-managed but verify)
find ~/.openclaw/metrics/ -name "metrics_*.csv" -mtime +30 -delete

# Clean old news/market data (keep last 14 days)
find ~/.openclaw/workspace/news-data/ -mtime +14 -delete
find ~/.openclaw/workspace/market-data/ -mtime +14 -delete

# Clean old cost files (keep last 90 days)
find ~/.openclaw/costs/ -name "costs_*.json" -mtime +90 -delete

# Nuclear option: clean journald
sudo journalctl --vacuum-size=100M

# Verify
df -h /
```

**Rollback:** N/A (deletion is permanent — only delete old data)

---

## 5. High CPU / Temperature Throttling

**Symptoms:** Monitor sends CPU/temp alerts, sluggish responses

**Diagnosis:**
```bash
vcgencmd measure_temp
top -bn1 | head -15
~/bin/metrics-viewer today --summary
```

**Resolution:**
```bash
# Identify the culprit
ps aux --sort=-%cpu | head -10

# If OpenClaw is the cause, restart
systemctl --user restart openclaw-gateway

# If another process, kill it
kill -9 <PID>

# If thermal throttling, check cooling
vcgencmd get_throttled
# 0x0 = OK, anything else = throttling occurred
```

**Rollback:** If Pi keeps overheating, reduce cron frequency or add cooling

---

## 6. Telegram Bot Not Responding

**Symptoms:** No alerts received, trade proposals not sent

**Diagnosis:**
```bash
# Check chat ID exists
cat ~/.openclaw/monitor/chat_id

# Test manually (token loaded from .env — never hardcode in scripts)
BOT_TOKEN=$(grep TELEGRAM_BOT_TOKEN ~/.openclaw/workspace/.env | cut -d= -f2)
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getMe"

# Check recent errors
grep -i "telegram" ~/.openclaw/logs/openclaw-app.log | tail -5
```

**Resolution:**
```bash
# If chat_id missing, re-pair via Telegram:
# 1. Open Telegram, find @openclaw_trader_bbrd_bot
# 2. Send /start
# 3. Note the chat ID from the gateway logs

# If bot token invalid, create new bot via @BotFather on Telegram
# Set the new token in ~/.openclaw/workspace/.env:
#   TELEGRAM_BOT_TOKEN=<new_token_from_BotFather>
# NEVER commit real tokens to source control.
```

**Rollback:** Bot tokens don't expire unless revoked — keep old token as backup

---

## 7. Alpaca Paper Trading Issues

**Symptoms:** Trade proposals fail, 401 errors from Alpaca

**Diagnosis:**
```bash
cd ~/.openclaw/workspace
python3 trader.py test
grep -i "alpaca" ~/.openclaw/logs/openclaw-app.log | tail -10
```

**Resolution:**
```bash
# Verify keys
grep ALPACA ~/.openclaw/workspace/.env

# Test connection
python3 trader.py test

# If market is closed (weekends/holidays), orders queue until next open
# Check market status
python3 -c "
from trader import alpaca_request
clock = alpaca_request('GET', '/clock')
print(f'Market open: {clock.get(\"is_open\")}')
print(f'Next open: {clock.get(\"next_open\")}')
"
```

**Rollback:** Cancel pending orders via Alpaca dashboard at https://app.alpaca.markets

---

## 8. News Feed / Sentiment Pipeline Down

**Symptoms:** No new articles, stale sentiment data, stale reports

**Diagnosis:**
```bash
ls -lt ~/.openclaw/workspace/news-data/ | head -5
ls -lt ~/.openclaw/workspace/sentiment-data/ | head -5
cat ~/.openclaw/logs/newsfeed.log | tail -20
```

**Resolution:**
```bash
cd ~/.openclaw/workspace

# Run newsfeed manually
python3 newsfeed.py

# Run sentiment analysis
python3 sentiment.py

# Generate fresh report
python3 report.py

# Check cron is still set
crontab -l | grep newsfeed
```

**Rollback:** Pipeline is stateless — just re-run the scripts

---

## 9. Tailscale VPN Down

**Symptoms:** Can't SSH via Tailscale IP (100.66.59.84), only LAN works

**Diagnosis:**
```bash
# From the Pi (via LAN SSH)
tailscale status
sudo systemctl status tailscaled

# Check if logged in
tailscale ip
```

**Resolution:**
```bash
# Restart Tailscale
sudo systemctl restart tailscaled

# If not logged in
sudo tailscale up

# If auth expired, re-authenticate
sudo tailscale up --login-server https://controlplane.tailscale.com
# Follow the URL to re-auth

# Verify
tailscale status
ping -c 3 100.66.59.84
```

**Rollback:** Fall back to LAN SSH (10.0.0.175) while troubleshooting

---

## 10. OpenClaw Update

**Symptoms:** N/A (planned maintenance)

**Procedure:**
```bash
# 1. Check current version
openclaw --version

# 2. Engage kill switch (prevent auto-restart during update)
~/bin/killswitch

# 3. Update OpenClaw
npm update -g openclaw  # or whatever the update command is

# 4. Run doctor to validate config
openclaw doctor

# 5. Restore service
~/bin/killswitch-restore

# 6. Verify
systemctl --user status openclaw-gateway
openclaw --version
```

**Rollback:** If update breaks things, downgrade: `npm install -g openclaw@<previous-version>`

---

## 11. Memory Exhaustion (OOM)

**Symptoms:** Services killed, "Killed" in logs, swap usage high

**Diagnosis:**
```bash
free -h
dmesg | grep -i "oom\|killed" | tail -5
~/bin/metrics-viewer today --summary
```

**Resolution:**
```bash
# Check what's consuming memory
ps aux --sort=-%mem | head -10

# Restart gateway (often fixes memory leaks)
systemctl --user restart openclaw-gateway

# If swap is full too
sudo swapoff -a && sudo swapon -a

# Long-term: increase swap
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile  # Set CONF_SWAPSIZE=4096
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

**Rollback:** N/A — restart is the fix

---

## 12. Complete System Recovery (Nuclear Option)

**Symptoms:** Multiple systems down, can't diagnose, or Pi unresponsive

**Procedure:**
```bash
# 1. Hard reboot (if SSH accessible)
sudo reboot

# 2. If Pi is unresponsive, power cycle physically
# Unplug power, wait 10 seconds, plug back in

# 3. After reboot, verify services
systemctl --user status openclaw-gateway
tailscale status
crontab -l

# 4. Run health check
~/bin/openclaw-monitor

# 5. Check metrics are collecting
~/bin/metrics-viewer today

# 6. Run all pipelines manually
cd ~/.openclaw/workspace
python3 newsfeed.py
python3 sentiment.py
python3 report.py
python3 trader.py status
```

**Important:** Gateway auto-starts on boot. Cron jobs persist through reboot. Tailscale reconnects automatically.

---

## Quick Reference

| Service | Check | Restart |
|---------|-------|---------|
| Gateway | `systemctl --user status openclaw-gateway` | `systemctl --user restart openclaw-gateway` |
| Tailscale | `tailscale status` | `sudo systemctl restart tailscaled` |
| Cron | `crontab -l` | `sudo systemctl restart cron` |
| UFW | `sudo ufw status` | `sudo ufw enable` |
| Monitoring | `~/bin/metrics-viewer today` | Cron auto-runs |

## Cron Schedule

| Schedule | Script | Purpose |
|----------|--------|---------|
| Every 1 min | `metrics-collector` | System metrics |
| Every 5 min | `openclaw-monitor` | Health alerts |
| Every 4 hours | `newsfeed.py` | News collection |
| 4pm ET Mon-Fri | `trader.py summary` | Daily portfolio summary |
| 8am ET Sunday | `costtracker.py weekly` | Weekly cost report |

## Key Paths

| Path | Purpose |
|------|---------|
| `~/.openclaw/openclaw.json` | Main config |
| `~/.openclaw/workspace/.env` | API keys |
| `~/.openclaw/logs/` | Application logs |
| `~/.openclaw/metrics/` | System metrics CSV |
| `~/.openclaw/costs/` | API cost tracking |
| `~/.openclaw/monitor/` | Monitor state + chat ID |
| `~/.openclaw/workspace/trades/` | Trade audit trail |
| `~/bin/killswitch` | Emergency stop |
| `~/bin/killswitch-restore` | Restore after stop |
