"""Utilities to persist and read HTML snapshots per platform/profile.

Atomic single-file mode to avoid disk saturation. Intended for use in 24/7 loops.

Env controls (read by caller typically):
- SNAPSHOT_ENABLED: "true" | "false"
- SNAPSHOT_DIR: base directory, default: logs/html
- SNAPSHOT_MODE: only "single" supported for now
"""
from __future__ import annotations

import os
import hashlib
from pathlib import Path
from typing import Optional


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def atomic_write_text(dest: Path, content: str, encoding: str = "utf-8") -> None:
    """Write text atomically by writing to a temp file and replacing the target.

    This avoids partially written files being read by the parser.
    """
    _ensure_dir(dest.parent)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_text(content, encoding=encoding)
    os.replace(tmp, dest)


def compute_hash(content: str) -> str:
    """Compute a stable SHA1 hash for change detection."""
    return hashlib.sha1(content.encode("utf-8", errors="ignore")).hexdigest()


def snapshot_path(base_dir: Path, platform: str, profile: str) -> Path:
    safe_profile = profile.replace("/", "_").replace("\\", "_")
    filename = f"{platform}-{safe_profile}.html"
    return base_dir / filename


def write_snapshot(html: str, base_dir: Path, platform: str, profile: str) -> Path:
    """Write the latest HTML snapshot atomically and return its path."""
    dest = snapshot_path(base_dir, platform, profile)
    atomic_write_text(dest, html)
    return dest


def read_snapshot(base_dir: Path, platform: str, profile: str) -> Optional[str]:
    """Read the snapshot if it exists, else None."""
    p = snapshot_path(base_dir, platform, profile)
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
