"""HTML processing pipeline

Processes latest snapshots from SNAPSHOT_DIR and routes messages to Telegram
based on inferred filter and your existing YAML config.

This version does not perform browser scraping; it only consumes saved snapshots.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import List, Optional

from ..snapshots.snapshot_manager import latest_per_tab, cleanup_older_than, SnapshotRef
from ..parsers import betburger_html as bbp
from ..parsers import surebet_html as sbp
from ..processing.router import resolve_channel
from ..utils.hints_store import apply_hints
from ..utils.telegram_notifier import TelegramNotifier
from ..utils.logger import get_module_logger

logger = get_module_logger("html_pipeline")


def _load_meta(meta_path: str) -> dict:
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _read_html(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _process_ref(ref: SnapshotRef, notifier: TelegramNotifier) -> None:
    meta = _load_meta(ref.meta_path)
    url = meta.get("url", "")

    # Parse
    if ref.platform == "betburger":
        parsed = bbp.parse(_read_html(ref.html_path), url=url)
    elif ref.platform == "surebet":
        parsed = sbp.parse(_read_html(ref.html_path), url=url)
    else:
        logger.warning("Unknown platform in snapshot", platform=ref.platform)
        return

    # Apply learned hints to improve filter inference
    try:
        best_key, score = apply_hints(parsed.platform, parsed.signals)
        if best_key and score > max(1.0, parsed.confidence * 3):
            # override if learned score is meaningful
            parsed.filter_name_inferred = best_key
            # normalize confidence to 0..1
            parsed.confidence = min(1.0, 0.5 + score / 10.0)
    except Exception as e:
        logger.warning("apply_hints failed", error=str(e))

    channel_id = resolve_channel(parsed.platform, parsed.filter_name_inferred)
    if not channel_id:
        logger.warning("No channel resolved; skipping send", platform=parsed.platform, inferred=parsed.filter_name_inferred)
        return

    # Build message
    filter_name = parsed.filter_name_inferred or "(desconocido)"
    conf = f"{parsed.confidence:.2f}"
    ts_str = ref.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
    header = f"[{parsed.platform}] filtro={filter_name} conf={conf} tab={ref.tab_id}\n"
    body_lines: List[str] = []
    if url:
        body_lines.append(f"URL: {url}")
    body_lines.append(f"Snapshot: {ref.html_path.split('/')[-1]}")
    body_lines.append(f"Tomado: {ts_str}")
    # Add brief items if present
    if parsed.items:
        top = parsed.items[:3]
        for it in top:
            # Attempt generic line
            line = getattr(it, "match", "") or getattr(it, "league", "")
            if getattr(it, "roi_pct", None) is not None:
                line += f" | ROI {it.roi_pct}%"
            if getattr(it, "value_pct", None) is not None:
                line += f" | Value {it.value_pct}%"
            if line:
                body_lines.append(f"- {line}")

    text = header + "\n".join(body_lines)

    # Send
    notifier.send_text(text, chat_id=str(channel_id))


def run_once() -> None:
    """Process newest snapshot per tab for known platforms and cleanup old files."""
    notifier = TelegramNotifier()
    refs: List[SnapshotRef] = []
    refs.extend(latest_per_tab(platform="betburger"))
    refs.extend(latest_per_tab(platform="surebet"))
    if not refs:
        logger.info("No snapshots found to process")
        # Optionally notify support? Keeping silent to avoid noise.
        return

    for ref in refs:
        try:
            _process_ref(ref, notifier)
        except Exception as e:
            logger.error("Processing snapshot failed", path=ref.html_path, error=str(e))

    # Cleanup older than 6 hours
    cleanup_older_than(hours=6)


class PipelineRunner:
    """Run pipeline in a background thread (one-shot)."""

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None

    def start_once(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.info("Pipeline already running; skip new start")
            return
        self._thread = threading.Thread(target=run_once, name="html-pipeline-once", daemon=True)
        self._thread.start()
        logger.info("HTML pipeline one-shot started")
