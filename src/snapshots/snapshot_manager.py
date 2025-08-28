"""Snapshot manager for HTML persistence.

- Writes HTML and sidecar meta JSON with URL/title/hash.
- Lists latest snapshot per (platform, tab_id).
- Cleans up files older than N hours.

Filenames:
  {platform}-{tab_id}-{YYYYmmddTHHMMSS}.html
  {platform}-{tab_id}-{YYYYmmddTHHMMSS}.meta.json

Env:
  SNAPSHOT_DIR (default: logs/html)
"""
from __future__ import annotations

import os
import re
import json
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

import structlog

logger = structlog.get_logger("snapshot_manager")

ISO_FMT = "%Y%m%dT%H%M%S"
FILENAME_RE = re.compile(r"^(?P<platform>[a-zA-Z0-9_-]+)-(?P<tab>\d+)-(?P<ts>\d{8}T\d{6})\.(?P<ext>html|meta\.json)$")


def _snapshot_dir() -> str:
    base = os.getenv("SNAPSHOT_DIR", "logs/html").strip() or "logs/html"
    return base


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


@dataclass(frozen=True)
class SnapshotRef:
    platform: str
    tab_id: int
    timestamp: datetime
    html_path: str
    meta_path: str


def _build_name(platform: str, tab_id: int, ts: datetime) -> Tuple[str, str]:
    stamp = ts.strftime(ISO_FMT)
    base = f"{platform}-{tab_id}-{stamp}"
    return base + ".html", base + ".meta.json"


def save_html_snapshot(platform: str, tab_id: int, html: str, url: str = "", title: str = "", extras: Optional[Dict] = None) -> SnapshotRef:
    """Persist HTML and metadata. Returns a SnapshotRef.
    Never raises; logs errors and best-effort writes.
    """
    ts = datetime.now(timezone.utc)
    dirp = _snapshot_dir()
    _ensure_dir(dirp)

    html_file, meta_file = _build_name(platform, tab_id, ts)
    html_path = os.path.join(dirp, html_file)
    meta_path = os.path.join(dirp, meta_file)

    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as e:
        logger.error("Failed to write HTML snapshot", path=html_path, error=str(e))

    try:
        digest = hashlib.sha256(html.encode("utf-8", errors="ignore")).hexdigest()
        meta = {
            "platform": platform,
            "tab_id": tab_id,
            "url": url,
            "title": title,
            "created_at": ts.isoformat(),
            "sha256": digest,
        }
        if extras:
            meta.update({k: v for k, v in extras.items() if k not in meta})
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Failed to write META snapshot", path=meta_path, error=str(e))

    return SnapshotRef(platform, tab_id, ts, html_path, meta_path)


def iter_snapshots() -> Iterable[SnapshotRef]:
    dirp = _snapshot_dir()
    if not os.path.isdir(dirp):
        return []
    refs: List[SnapshotRef] = []
    for name in os.listdir(dirp):
        m = FILENAME_RE.match(name)
        if not m:
            continue
        if not name.endswith(".html"):
            continue
        platform = m.group("platform")
        tab_id = int(m.group("tab"))
        ts = datetime.strptime(m.group("ts"), ISO_FMT).replace(tzinfo=timezone.utc)
        base = name[:-5]
        html_path = os.path.join(dirp, f"{base}.html")
        meta_path = os.path.join(dirp, f"{base}.meta.json")
        refs.append(SnapshotRef(platform, tab_id, ts, html_path, meta_path))
    # Return sorted newest first
    refs.sort(key=lambda r: r.timestamp, reverse=True)
    return refs


def latest_per_tab(platform: Optional[str] = None) -> List[SnapshotRef]:
    """Return newest snapshot per (platform, tab_id). Optionally filter platform."""
    latest: Dict[Tuple[str, int], SnapshotRef] = {}
    for ref in iter_snapshots():
        if platform and ref.platform != platform:
            continue
        key = (ref.platform, ref.tab_id)
        if key not in latest or ref.timestamp > latest[key].timestamp:
            latest[key] = ref
    return sorted(latest.values(), key=lambda r: (r.platform, r.tab_id))


def cleanup_older_than(hours: int = 6) -> int:
    """Delete snapshot files older than 'hours'. Returns count deleted files."""
    dirp = _snapshot_dir()
    if not os.path.isdir(dirp):
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    deleted = 0
    for name in list(os.listdir(dirp)):
        m = FILENAME_RE.match(name)
        if not m:
            continue
        ts = datetime.strptime(m.group("ts"), ISO_FMT).replace(tzinfo=timezone.utc)
        if ts >= cutoff:
            continue
        try:
            os.remove(os.path.join(dirp, name))
            deleted += 1
        except FileNotFoundError:
            continue
        except Exception as e:
            logger.warning("Failed to delete old snapshot", file=name, error=str(e))
    if deleted:
        logger.info("Snapshot cleanup done", deleted=deleted)
    return deleted
