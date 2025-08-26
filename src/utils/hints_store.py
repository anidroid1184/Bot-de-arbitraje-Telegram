"""Hints Store for incremental learning of filter inference.

Persists a JSON file with structure:
{
  "version": 1,
  "platforms": {
    "betburger": {
      "filters": {
        "bet365_valuebets": {
          "keywords": {"valuebet": 2.0, "bet365": 3.0},
          "url_contains": {"valuebets": 2.0, "prematch": 1.5},
          "title_contains": {"Valuebets": 1.5}
        }
      }
    },
    "surebet": { ... }
  }
}

API:
- add_label(platform, filter_key, signals)
- apply_hints(platform, signals) -> (best_filter, score)

Signals is a list[str] like ["title:...", "url:...", "h:..."] produced by parsers.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

from .logger import get_module_logger

logger = get_module_logger("hints_store")

DEFAULT_PATH = os.path.join("logs", "models", "filter_hints.json")


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _load(path: str = DEFAULT_PATH) -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning("Failed to load hints", error=str(e))
    return {"version": 1, "platforms": {}}


def _save(data: Dict, path: str = DEFAULT_PATH) -> None:
    try:
        _ensure_parent(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Failed to save hints", path=path, error=str(e))


def add_label(platform: str, filter_key: str, signals: List[str], path: str = DEFAULT_PATH) -> None:
    data = _load(path)
    platforms = data.setdefault("platforms", {})
    p = platforms.setdefault(platform, {})
    filts = p.setdefault("filters", {})
    fentry = filts.setdefault(filter_key, {"keywords": {}, "url_contains": {}, "title_contains": {}, "headers_contains": {}})

    # Simple harvesting: split signals into categories and increment weights
    for s in signals:
        if s.startswith("url:"):
            token = s[4:].strip().lower()
            if token:
                fentry["url_contains"][token] = fentry["url_contains"].get(token, 0.0) + 1.0
        elif s.startswith("title:"):
            token = s[6:].strip()
            if token:
                fentry["title_contains"][token] = fentry["title_contains"].get(token, 0.0) + 1.0
        elif s.startswith("h:"):
            token = s[2:].strip()
            if token:
                fentry["headers_contains"][token] = fentry["headers_contains"].get(token, 0.0) + 1.0
        else:
            # generic keyword bucket
            token = s.strip().lower()
            if token:
                fentry["keywords"][token] = fentry["keywords"].get(token, 0.0) + 0.5

    _save(data, path)
    logger.info("Hints updated", platform=platform, filter=filter_key)


def apply_hints(platform: str, signals: List[str], path: str = DEFAULT_PATH) -> Tuple[Optional[str], float]:
    data = _load(path)
    p = (data.get("platforms") or {}).get(platform)
    if not isinstance(p, dict):
        return None, 0.0
    filts = p.get("filters") or {}
    if not isinstance(filts, dict):
        return None, 0.0

    # Prepare signal sets for quick matching
    url_txt = "|".join([s[4:] for s in signals if s.startswith("url:")]).lower()
    title_txt = "|".join([s[6:] for s in signals if s.startswith("title:")])
    headers_txt = "|".join([s[2:] for s in signals if s.startswith("h:")])
    joined = "|".join(signals).lower()

    best_key: Optional[str] = None
    best_score = 0.0

    for key, fentry in filts.items():
        score = 0.0
        try:
            for token, w in (fentry.get("url_contains") or {}).items():
                if token and token in url_txt:
                    score += float(w)
            for token, w in (fentry.get("title_contains") or {}).items():
                if token and token in title_txt:
                    score += float(w)
            for token, w in (fentry.get("headers_contains") or {}).items():
                if token and token in headers_txt:
                    score += float(w)
            for token, w in (fentry.get("keywords") or {}).items():
                if token and token in joined:
                    score += float(w)
        except Exception:
            continue
        if score > best_score:
            best_score = score
            best_key = key

    return best_key, best_score
