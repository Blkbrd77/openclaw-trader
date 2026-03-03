# Go/No-Go Criteria: Paper Trading to Live Trading

**Version:** 1.0
**Date:** 2026-03-02
**Live Budget:** $100 real funds via Alpaca
**Paper Trading Period:** Feb 23 - Mar 23, 2026 (4 weeks)

---

## Gate 1: System Reliability (must pass ALL)

| # | Criterion | Metric | Threshold |
|---|-----------|--------|-----------|
| 1.1 | Pipeline uptime | Cron jobs executed vs expected | >= 95% over final 2 weeks |
| 1.2 | Data freshness | Stock data, sentiment, news updated daily | No gaps > 1 business day |
| 1.3 | Analyzer runs | trader.py analyze executes on schedule | >= 90% of trading days |
| 1.4 | No unhandled crashes | Errors in logs that halt the pipeline | Zero in final week |
| 1.5 | Telegram delivery | Summaries and trade notifications arrive | >= 90% delivery rate |

**How to verify:** Review cron logs, metrics-collector data, and Telegram message history.

---

## Gate 2: Trading Performance (must pass 4 of 5)

| # | Criterion | Metric | Threshold |
|---|-----------|--------|-----------|
| 2.1 | Total trades executed | Orders filled during paper period | >= 5 trades |
| 2.2 | Win rate | Trades closed at profit / total closed | >= 40% |
| 2.3 | Max drawdown | Largest peak-to-trough decline | <= 20% of portfolio |
| 2.4 | Net P&L | Total paper P&L at end of period | > -10% (not losing badly) |
| 2.5 | Signal quality | Trades with score > 0.25 outperform random | Positive alpha vs buy-and-hold |

**Note:** With a $100 budget and $20 position sizes, absolute dollar P&L will be small. Focus on percentages and directional accuracy, not dollar amounts.

**How to verify:** Review trades/ audit logs, Alpaca order history, and portfolio value vs starting $100.

---

## Gate 3: Risk Controls (must pass ALL)

| # | Criterion | Metric | Threshold |
|---|-----------|--------|-----------|
| 3.1 | Budget enforcement | No trade exceeds $100 total invested | Zero violations |
| 3.2 | Position sizing | No single position > 30% of budget | Zero violations |
| 3.3 | Max positions | Never holds > 5 positions | Zero violations |
| 3.4 | Watchlist only | All trades are in WATCHLIST symbols | Zero violations |
| 3.5 | No margin used | Margin/buying power never leveraged | Zero violations |
| 3.6 | Audit trail complete | Every trade has log entry with reasoning | 100% logged |

**How to verify:** Review trades/ JSON logs, Alpaca account history, check for any risk constraint violations.

---

## Gate 4: Security (must pass ALL)

| # | Criterion | Metric | Threshold |
|---|-----------|--------|-----------|
| 4.1 | No secrets in git | GitHub repo clean of API keys/tokens | Zero findings |
| 4.2 | CI pipeline green | All checks pass on main branch | Green on latest commit |
| 4.3 | .env permissions | Secrets file not world-readable | chmod 600 or 640 |
| 4.4 | UFW firewall active | Default deny, only required ports open | Verified |
| 4.5 | Alpaca API key scoped | Live key has paper-equivalent permissions only | Verified |

**How to verify:** Run KAN-48 security audit checklist.

---

## Decision Framework

### GO (proceed to live trading)
- Gate 1: ALL criteria pass
- Gate 2: At least 4 of 5 criteria pass
- Gate 3: ALL criteria pass
- Gate 4: ALL criteria pass

### CONDITIONAL GO (proceed with restrictions)
- Gate 1 or 2 has 1 failure: proceed but reduce budget to $50 and review weekly
- Gate 2 has 2 failures: extend paper trading 2 more weeks

### NO-GO (do not proceed)
- Any Gate 3 failure (risk controls broken)
- Any Gate 4 failure (security issue)
- Gate 1 has 2+ failures (system unreliable)
- Gate 2 has 3+ failures (strategy not working)

---

## Review Process

1. **Week 2 checkpoint (Mar 9):** Quick health check on Gates 1 and 3. Fix any issues early.
2. **Week 3 checkpoint (Mar 16):** Full review of all gates. Identify any risks to go-live.
3. **Week 4 final review (Mar 23):** Go/no-go decision. Document results in a decision memo.

### Decision Memo Template

```
Date: ____
Reviewer: Jay Samples

Gate 1 (Reliability): PASS / FAIL
  - Pipeline uptime: ___%
  - Data gaps: ___
  - Crashes: ___

Gate 2 (Performance): _/5 PASS
  - Trades executed: ___
  - Win rate: ___%
  - Max drawdown: ___%
  - Net P&L: ___%
  - Signal alpha: ___

Gate 3 (Risk Controls): PASS / FAIL
  - Violations: ___

Gate 4 (Security): PASS / FAIL
  - Findings: ___

DECISION: GO / CONDITIONAL GO / NO-GO
NOTES: ___
```

---

## Live Trading Differences

When transitioning to live, the following changes apply:

| Setting | Paper | Live |
|---------|-------|------|
| Alpaca endpoint | paper-api.alpaca.markets | api.alpaca.markets |
| Budget | $100 (of $100K paper) | $100 (real funds) |
| Approval mode | Auto-execute | Telegram approval required |
| Position size | $20 | $20 |
| Max positions | 5 | 5 |
| Order types | Market only | Market only (initially) |
| Trading hours | Regular hours | Regular hours only |
