"""Notification helpers for Apex 50K AUTOMATION pipeline.
Supports Discord webhooks and Telegram bot messages. Both are opt-in via
environment variables; if neither is set, notify() becomes a no-op.

Env vars:
  DISCORD_WEBHOOK_URL   — Discord channel webhook (https://discord.com/api/webhooks/...)
  TELEGRAM_BOT_TOKEN    — Telegram bot token (from @BotFather)
  TELEGRAM_CHAT_ID      — chat/group id to send to
"""
import os
import json
import requests


def _post_json(url: str, payload: dict, timeout: int = 10) -> bool:
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        if r.status_code in (200, 204):
            return True
        print(f"[notify] POST {url} -> {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"[notify] POST {url} -> error: {e}")
        return False


def send_discord(content: str, username: str = "A 皮盤房 Scanner",
                 embeds: list | None = None) -> bool:
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        return False
    payload = {"username": username, "content": content}
    if embeds:
        payload["embeds"] = embeds
    return _post_json(url, payload)


def send_telegram(content: str, parse_mode: str = "Markdown") -> bool:
    token   = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": content, "parse_mode": parse_mode,
               "disable_web_page_preview": True}
    return _post_json(url, payload)


def notify(content: str, **kwargs) -> dict:
    """Send to all configured channels. Returns {channel: ok}."""
    results = {}
    if os.environ.get("DISCORD_WEBHOOK_URL"):
        results["discord"] = send_discord(content, **kwargs)
    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        results["telegram"] = send_telegram(content, **kwargs)
    if not results:
        # No webhooks configured — silent no-op (or print in dev)
        if os.environ.get("APEX_NOTIFY_VERBOSE"):
            print(f"[notify] (no channels) {content[:200]}")
    return results


def notify_actionable_setups(setups: list, date_str: str) -> dict:
    """Format actionable A/B scanner setups and push to webhooks.

    setups: list of dicts with keys
      ticker, grade, bias, entry, sl, tp, rr, contracts, pattern
    """
    if not setups:
        return {}
    lines = [f"**A 皮盤房 v2.6 — {date_str} actionable setups**"]
    for s in setups:
        lines.append(
            f"• **{s['ticker']}** ({s['grade']}/{s['bias']}) "
            f"Entry `{s['entry']}` SL `{s['sl']}` TP `{s['tp']}` "
            f"RR `{s['rr']}` ×{s.get('contracts',1)} micro  "
            f"_{s.get('pattern','')}_"
        )
    lines.append("\n⚠️ KILLZONE 09:00-11:00 EST · same-day exit · daily SL -$100 停手")
    return notify("\n".join(lines))


def notify_forward_pnl(day_pnl: float, cumulative_pnl: float,
                        n_trades_today: int, date_str: str) -> dict:
    """Format forward-test P&L update and push."""
    emoji = "🟢" if day_pnl >= 0 else "🔴"
    cum_emoji = "🟢" if cumulative_pnl >= 0 else "🔴"
    content = (
        f"{emoji} **{date_str}** forward test: ${day_pnl:+.0f} "
        f"({n_trades_today} trades)\n"
        f"{cum_emoji} Cumulative: ${cumulative_pnl:+.0f}"
    )
    return notify(content)
