from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

ES_TZ = ZoneInfo("Europe/Madrid")


def _fmt_percent(value: Optional[float]) -> str:
    if value is None:
        return "?"
    # Use comma as decimal separator for percentages, e.g., 6,38%
    return (f"{value:.2f}").replace(".", ",") + "%"


def _fmt_datetime_esmadrid(dt: Optional[datetime]) -> str:
    if not dt:
        return "?"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(ES_TZ)
    return local.strftime("%d/%m %H:%M")


def _fmt_age_minutes(now: datetime, ref: Optional[datetime]) -> str:
    if not ref:
        return "?min"
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    delta = now.astimezone(timezone.utc) - ref.astimezone(timezone.utc)
    mins = max(0, int(delta.total_seconds() // 60))
    return f"{mins} min" if mins != 0 else "0 min"


@dataclass
class Selection:
    bookmaker: str
    label: str  # market / selection printable label
    odd: str | float | int


@dataclass
class EventCard:
    source_prefix: str  # "BB" or "SU"
    selection_a: Selection
    selection_b: Selection
    sport: str
    league: str
    start_time: Optional[datetime]
    match: str  # "Team A – Team B"
    value_pct: Optional[float]  # value/roi percent
    reference_time: Optional[datetime]  # timestamp of detection for age


def format_surebet_card(card: EventCard) -> str:
    """Format a two-selection surebet/valuebet card in Telegram-friendly text.

    Rules:
    - Percentages use comma decimal separator (e.g., 6,38%).
    - Odds remain with dot (e.g., @1.41).
    - Date in Europe/Madrid timezone: dd/MM HH:mm
    - Footer: "SUREBET <prefix>: <pct>    <age>"
    """
    lines: list[str] = []

    # Selections — render gracefully if fields are missing
    def _sel_line(sel: Selection) -> str:
        bk = (sel.bookmaker or "").strip()
        lbl = (sel.label or "").strip()
        odd = str(sel.odd) if sel.odd is not None else "?"
        if bk and lbl:
            return f"{bk}: {lbl} @{odd}"
        if bk and not lbl:
            return f"{bk}: @{odd}"
        if not bk and lbl:
            return f"{lbl} @{odd}"
        return f"@{odd}"

    lines.append(_sel_line(card.selection_a))
    lines.append(_sel_line(card.selection_b))
    lines.append("")

    # Match info
    # Normalize sport capitalization (first letter upper)
    def _clean(s: str) -> str:
        s = (s or "").strip()
        return "" if s in {"?", "-"} else s

    sport = _clean((card.sport or "").capitalize())
    league = _clean(card.league or "")
    # Only include start time when we actually have one
    start_str = _fmt_datetime_esmadrid(card.start_time) if card.start_time else ""
    match_line = _clean((card.match or "").replace(" vs ", " – "))

    if sport:
        lines.append(sport)
    if league:
        lines.append(league)
    if start_str:
        lines.append(start_str)
    if match_line:
        lines.append(match_line)
    lines.append("")

    # Footer
    pct = _fmt_percent(card.value_pct)
    now = datetime.now(tz=timezone.utc)
    age = _fmt_age_minutes(now, card.reference_time)
    lines.append(f"SUREBET {card.source_prefix}: {pct}    {age}")

    return "\n".join(lines)
