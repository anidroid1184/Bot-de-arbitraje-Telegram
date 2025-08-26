"""
Betburger network token extractor.

Parses Betburger requests to extract lightweight, non-sensitive tokens that help
identify active filters and tab context. Safe to persist in snapshot meta.

Functions:
- extract_tokens_from_request(url, method, headers, body_bytes) -> dict
  Returns a dict with keys like:
    {
      "endpoint": "pro_search" | "search_filters_active",
      "filter_id": 1218062,
      "active": true,                      # only for search_filters_active
      "locale": "es",
      "is_live": false,
      "grouped": true,
      "sort_by": "percent",
      "per_page": 10,
      "koef_format": "decimal",
      "event_arb_types": [1,2,...],
      "bk_ids_count": 123,                 # count only; we avoid persisting huge arrays
      "bk_ids_sample": [1, 2, 3],          # first few for learning if needed
    }
  and a list of string signals in tokens["signals"], e.g. ["net:bb:filter_id=1218062"].

Note: We do not persist access_token or other secrets.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse, parse_qs


def _safe_int(val: Any) -> int | None:
    try:
        return int(val)
    except Exception:
        return None


def _coerce_bool(val: Any) -> bool | None:
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in {"true", "1", "yes"}:
        return True
    if s in {"false", "0", "no"}:
        return False
    return None


def _first(q: Dict[str, List[str]], key: str) -> str | None:
    v = q.get(key)
    if not v:
        return None
    return v[0]


def _ints(q: Dict[str, List[str]], key: str, limit: int | None = None) -> Tuple[List[int], int]:
    arr = q.get(key) or []
    out: List[int] = []
    for x in arr[: (limit or len(arr))]:
        i = _safe_int(x)
        if i is not None:
            out.append(i)
    return out, len(arr)


def extract_tokens_from_request(url: str, method: str, headers: Dict[str, str] | None, body_bytes: bytes | None) -> Dict[str, Any]:
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    path = parsed.path or ""

    tokens: Dict[str, Any] = {
        "endpoint": None,
        "locale": _first(q, "locale"),
        "signals": [],
    }

    # Classify endpoint
    if "/api/v1/arbs/pro_search" in path:
        tokens["endpoint"] = "pro_search"
    elif "/api/v1/search_filters/" in path and "/active/" in path:
        tokens["endpoint"] = "search_filters_active"
        try:
            # .../search_filters/{id}/active/{state}
            parts = path.strip("/").split("/")
            idx = parts.index("search_filters")
            fid = _safe_int(parts[idx + 1])
            state = parts[idx + 3] if len(parts) > idx + 3 else None
            tokens["filter_id"] = fid
            tokens["active"] = _coerce_bool(state)
            if fid is not None:
                tokens["signals"].append(f"net:bb:filter_id={fid}")
            if state is not None:
                tokens["signals"].append(f"net:bb:filter_active={state}")
        except Exception:
            pass
        return tokens

    # Parse body (form or JSON) for pro_search
    if tokens["endpoint"] == "pro_search":
        body = body_bytes or b""
        body_text = body.decode("utf-8", errors="ignore")

        # Try JSON first
        payload: Dict[str, Any] | None = None
        if body_text.lstrip().startswith("{"):
            try:
                payload = json.loads(body_text)
            except Exception:
                payload = None

        # Fallback: URL-encoded form
        if payload is None:
            form = parse_qs(body_text, keep_blank_values=True)
            # Basic fields
            tokens["is_live"] = _coerce_bool(_first(form, "is_live"))
            tokens["grouped"] = _coerce_bool(_first(form, "grouped"))
            tokens["sort_by"] = _first(form, "sort_by")
            tokens["koef_format"] = _first(form, "koef_format")
            per_page = _safe_int(_first(form, "per_page"))
            if per_page is not None:
                tokens["per_page"] = per_page

            # search_filter id(s)
            sf_ids, sf_count = _ints(form, "search_filter[]", limit=3)
            if sf_ids:
                tokens["filter_id"] = sf_ids[0]
                tokens["signals"].append(f"net:bb:filter_id={sf_ids[0]}")
                if sf_count > 1:
                    tokens["signals"].append(f"net:bb:filter_ids_count={sf_count}")

            # bk_ids
            bk_sample, bk_count = _ints(form, "bk_ids[]", limit=5)
            tokens["bk_ids_count"] = bk_count
            if bk_sample:
                tokens["bk_ids_sample"] = bk_sample
                tokens["signals"].append(f"net:bb:bk_count={bk_count}")

            # event_arb_types
            eat_sample, eat_count = _ints(form, "event_arb_types[]", limit=12)
            if eat_sample:
                tokens["event_arb_types"] = eat_sample
                tokens["signals"].append(f"net:bb:eat_count={eat_count}")

        else:
            # TODO: Map JSON structure if Betburger switches to JSON payload in some cases
            # Persist a minimal subset
            tokens["is_live"] = bool(payload.get("is_live")) if isinstance(payload, dict) else None  # type: ignore

    return tokens
