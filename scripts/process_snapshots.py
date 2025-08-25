"""
Process HTML snapshots from Surebet and Betburger and emit normalized JSON templates.

- Reads snapshots from SNAPSHOT_DIR (default: logs/html)
- Cleans overlay/irrelevant nodes in-memory (keeps original HTML untouched)
- Extracts the latest alert only (heuristic, robust to class name changes)
- Writes JSON into PARSED_OUTPUT_DIR (default: logs/snapshots_parsed)
- Produces both a timestamped file and a '-latest.json' symlink-like copy

Usage examples:
  python -m scripts.process_snapshots --all
  python -m scripts.process_snapshots --file logs/html/betburger-bet365_valuebets.html --source betburger --profile bet365_valuebets

Notes:
- Uses BeautifulSoup if available. If not installed, falls back to a very basic HTML text search.
- JSON schema aligns with samples in samples/betburger_valid.json and samples/surebet_valid.json
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Optional BeautifulSoup import
try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore

# -----------------------------
# Config
# -----------------------------
ENV_SNAPSHOT_DIR = os.getenv("SNAPSHOT_DIR", "logs/html")
ENV_PARSED_OUTPUT_DIR = os.getenv("PARSED_OUTPUT_DIR", "logs/snapshots_parsed")

SUPPORTED_SOURCES = {"surebet", "betburger"}

SPORT_TOKENS = {
    "football": {"football", "fútbol", "futbol"},
    "tennis": {"tennis"},
    "basketball": {"basketball", "baloncesto"},
    "table tennis": {"table tennis", "tenis de mesa"},
    "ice hockey": {"ice hockey", "hockey sobre hielo", "hockey hielo"},
}

PERCENT_RE = re.compile(r"(?P<val>-?\d{1,3}([\.,]\d{1,2})?)\s*%")
ODD_RE = re.compile(r"(?P<odd>\d{1,2}(?:[\.,]\d{1,3})?)")
TEAM_VS_RE = re.compile(r"([A-Za-zÀ-ÿ0-9\-\.\s]{2,})\s+vs\s+([A-Za-zÀ-ÿ0-9\-\.\s]{2,})", re.IGNORECASE)
BRACKETS_PERIOD_RE = re.compile(r"\[(?P<period>[^\]]+)\]")


def _utc_now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclasses.dataclass
class ParsedAlert:
    # Common
    source: str
    profile: str
    timestamp_utc: str
    sport: Optional[str] = None
    league: Optional[str] = None
    match: Optional[str] = None
    market: Optional[str] = None
    target_link: Optional[str] = None
    event_start: Optional[str] = None

    # Selections
    selection_a: Optional[Dict[str, Any]] = None
    selection_b: Optional[Dict[str, Any]] = None

    # Metrics
    roi_pct: Optional[float] = None  # Betburger
    value_pct: Optional[float] = None  # Surebet

    def to_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        # Remove None keys for cleanliness
        return {k: v for k, v in d.items() if v is not None}


# -----------------------------
# HTML helpers
# -----------------------------

def load_html(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def clean_html(html: str) -> str:
    if not BeautifulSoup:
        return html  # fallback: cannot clean without bs4
    soup = BeautifulSoup(html, "lxml") if "lxml" in sys.modules else BeautifulSoup(html, "html.parser")

    # Remove known overlays/noise
    try:
        el = soup.find(id="statuses-widget")
        if el:
            el.decompose()
    except Exception:
        pass

    try:
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
    except Exception:
        pass

    # Remove invisible elements that often pollute text search
    try:
        for el in soup.select('[aria-hidden="true"], [style*="display:none"], [style*="visibility:hidden"]'):
            el.decompose()
    except Exception:
        pass

    return str(soup)


# -----------------------------
# Heuristic extraction (latest alert)
# -----------------------------

def _find_percent_values(text: str) -> list[Tuple[float, int]]:
    """Return list of (value, index) for all percents in the text."""
    out: list[Tuple[float, int]] = []
    for m in PERCENT_RE.finditer(text):
        raw = m.group("val").replace(",", ".")
        try:
            out.append((float(raw), m.start()))
        except ValueError:
            continue
    return out


def _guess_sport(text: str) -> Optional[str]:
    lower = text.lower()
    for sport, tokens in SPORT_TOKENS.items():
        if any(tok in lower for tok in tokens):
            return sport
    return None


def _guess_match(text: str) -> Optional[str]:
    m = TEAM_VS_RE.search(text)
    if m:
        a = re.sub(r"\s+", " ", m.group(1)).strip()
        b = re.sub(r"\s+", " ", m.group(2)).strip()
        return f"{a} vs {b}"
    return None


def _guess_market(text: str) -> Optional[str]:
    # Basic markets often present
    for mk in ["1X2", "Hándicap", "Handicap", "Over/Under", "Total", "Draw No Bet", "Double Chance"]:
        if mk.lower() in text.lower():
            return mk
    return None


def _extract_near(text: str, idx: int, span: int = 400) -> str:
    a = max(0, idx - span)
    b = min(len(text), idx + span)
    return text[a:b]


def parse_latest_alert(html: str, *, source: str, profile: str) -> Optional[ParsedAlert]:
    # Convert to text for heuristic search
    if BeautifulSoup:
        soup = BeautifulSoup(html, "lxml") if "lxml" in sys.modules else BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        # Try to capture a click-through URL if present
        link = soup.find("a", href=True)
        target_link = link["href"] if link else None
    else:
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        target_link = None

    percents = _find_percent_values(text)
    if not percents:
        # No percent found; still emit a minimal template with what we can
        candidate_text = text
        roi = value = None
        anchor = 0
    else:
        # Choose the last percent occurrence as the latest alert proxy
        roi_value, anchor = percents[-1]
        candidate_text = _extract_near(text, anchor)
        # Map metric by source
        roi = roi_value if source == "betburger" else None
        value = roi_value if source == "surebet" else None

    sport = _guess_sport(candidate_text)
    match = _guess_match(candidate_text)
    market = _guess_market(candidate_text)

    # Bookmaker + odds extraction near the detected alert anchor
    selection_a = None
    selection_b = None
    try:
        # For Betburger, try to extract bookmaker-odd pairs (e.g., "Pinnacle 1.85")
        if source == "betburger":
            pairs = re.findall(r"(?i)([A-Za-z][A-Za-z0-9 _\-\.']{2,32})\D([0-9]+(?:[\.,][0-9]+)?)", candidate_text)
            # Deduplicate by bookmaker name while keeping order
            seen = set()
            uniq = []
            for bk, odd in pairs:
                key = bk.strip().title()
                if key in seen:
                    continue
                seen.add(key)
                try:
                    odd_f = float(str(odd).replace(",", "."))
                except ValueError:
                    continue
                uniq.append((key, odd_f))
                if len(uniq) >= 2:
                    break
            if uniq:
                selection_a = {"bookmaker": uniq[0][0], "odd": uniq[0][1]}
            if len(uniq) > 1:
                selection_b = {"bookmaker": uniq[1][0], "odd": uniq[1][1]}
        else:
            # Generic fallback (Surebet): capture up to two odds without bookmaker names
            odds = [float(x.replace(",", ".")) for x in re.findall(r"\b\d{1,2}[\.,]\d{1,3}\b", candidate_text)]
            if odds:
                selection_a = {"bookmaker": None, "odd": odds[0]}
            if len(odds) > 1:
                selection_b = {"bookmaker": None, "odd": odds[1]}
    except Exception:
        pass

    alert = ParsedAlert(
        source=source,
        profile=profile,
        timestamp_utc=_utc_now_iso(),
        sport=sport,
        league=None,
        match=match,
        market=market,
        target_link=target_link,
        event_start=None,
        selection_a=selection_a,
        selection_b=selection_b,
        roi_pct=roi,
        value_pct=value,
    )
    return alert


# -----------------------------
# IO helpers
# -----------------------------

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def write_parsed_json(alert: ParsedAlert, out_dir: Path) -> Path:
    ensure_dir(out_dir)
    ts = alert.timestamp_utc.replace(":", "").replace("-", "")
    base = f"{alert.source}-{alert.profile}-{ts}.json"
    out_path = out_dir / base
    tmp = out_path.with_suffix(".tmp")
    data = alert.to_dict()
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out_path)

    # Also write/update latest copy
    latest = out_dir / f"{alert.source}-{alert.profile}-latest.json"
    latest_tmp = latest.with_suffix(".tmp")
    latest_tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_tmp.replace(latest)

    return out_path


# -----------------------------
# Orchestration
# -----------------------------

def process_file(file_path: Path, *, source: Optional[str], profile: Optional[str]) -> Optional[Path]:
    if not file_path.exists():
        print(f"[process_snapshots] File not found: {file_path}", file=sys.stderr)
        return None

    # Infer source/profile if not provided
    src = (source or _infer_source(file_path)).lower()
    if src not in SUPPORTED_SOURCES:
        print(f"[process_snapshots] Unsupported or unknown source: {src}", file=sys.stderr)
        return None

    prof = profile or _infer_profile(file_path)

    raw_html = load_html(file_path)
    cleaned = clean_html(raw_html)
    alert = parse_latest_alert(cleaned, source=src, profile=prof)
    if not alert:
        print(f"[process_snapshots] No alert parsed from {file_path}")
        return None

    out_dir = Path(ENV_PARSED_OUTPUT_DIR)
    out_path = write_parsed_json(alert, out_dir)
    print(f"[process_snapshots] Wrote {out_path}")
    return out_path


def _infer_source(path: Path) -> str:
    name = path.name.lower()
    if "surebet" in name:
        return "surebet"
    if "betburger" in name or "bet-burger" in name or "burger" in name:
        return "betburger"
    return "betburger"  # default


def _infer_profile(path: Path) -> str:
    # Extract between source- and extension
    name = path.stem
    parts = name.split("-")
    if len(parts) >= 2:
        return "-".join(parts[1:])
    return name


def process_all_in_dir(snapshot_dir: Path) -> int:
    count = 0
    for p in snapshot_dir.glob("*.html"):
        try:
            if process_file(p, source=None, profile=None):
                count += 1
        except Exception as e:
            print(f"[process_snapshots] Error processing {p}: {e}", file=sys.stderr)
    return count


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Process snapshots and emit normalized JSON")
    ap.add_argument("--all", action="store_true", help="Process all snapshots in SNAPSHOT_DIR")
    ap.add_argument("--file", type=str, help="Path to a single snapshot HTML file")
    ap.add_argument("--source", type=str, choices=sorted(SUPPORTED_SOURCES), help="Source override")
    ap.add_argument("--profile", type=str, help="Profile override")
    return ap.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    snap_dir = Path(ENV_SNAPSHOT_DIR)

    if args.all:
        ensure_dir(Path(ENV_PARSED_OUTPUT_DIR))
        processed = process_all_in_dir(snap_dir)
        print(f"[process_snapshots] Processed {processed} file(s)")
        return 0

    if args.file:
        out = process_file(Path(args.file), source=args.source, profile=args.profile)
        return 0 if out else 2

    print("Usage: --all or --file <path>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
