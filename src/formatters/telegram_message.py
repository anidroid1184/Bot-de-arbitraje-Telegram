"""
Formatter utilities to render alert dicts into concise Telegram messages.

Input alert schema matches processors output (see betburger_parser.parse_betburger_html).
"""
from __future__ import annotations

from typing import Any, Dict


def format_alert_telegram(alert: Dict[str, Any]) -> str:
    """Return a compact human-friendly Telegram message for an alert.

    Expected keys: source, roi_pct/value_pct, sport, market, match, selection_a/_b, event_start, target_link, profile
    """
    source = alert.get("source", "src")
    profile = alert.get("profile", "-")
    roi = alert.get("roi_pct")
    value = alert.get("value_pct")
    sport = alert.get("sport") or ""
    market = alert.get("market") or ""
    match = alert.get("match") or ""

    sel_a = alert.get("selection_a") or {}
    sel_b = alert.get("selection_b") or {}
    a_bk = sel_a.get("bookmaker", "?")
    a_od = sel_a.get("odd", "?")
    b_bk = sel_b.get("bookmaker", "?")
    b_od = sel_b.get("odd", "?")

    event_start = alert.get("event_start")
    link = alert.get("target_link")

    headline_metric = None
    if roi is not None:
        headline_metric = f"{roi:.2f}% ROI"
    elif value is not None:
        headline_metric = f"{value:.2f}% VALUE"
    else:
        headline_metric = "Alert"

    lines = []
    lines.append(f"[{source}] {headline_metric} — {sport.title()} • {market}")
    if match:
        lines.append(f"{match}")
    if event_start:
        lines.append(f"Inicio: {event_start}")
    lines.append(f"{a_bk}: {a_od} | {b_bk}: {b_od}")
    lines.append(f"Perfil: {profile}")
    if link:
        lines.append(f"Link: {link}")

    return "\n".join(lines)
