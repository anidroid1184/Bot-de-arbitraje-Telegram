#!/usr/bin/env python3
"""
Ensure critical Python dependencies are importable at runtime inside the container.
If any are missing, attempt to install from requirements.txt using pip --user.
This is a safety net against stale image layers or volume overrides.
"""
import importlib
import subprocess
import sys
from pathlib import Path

CRITICAL_MODULES = [
    "yaml",  # pyyaml
    "dotenv",  # python-dotenv
    "selenium",
    "bs4",  # beautifulsoup4
    "lxml",
    "pandas",
    "requests",
    "aiohttp",
    "telegram",  # python-telegram-bot
    "structlog",
]

REQ_FILE = Path("/app/requirements.txt")


def can_import(mod: str) -> bool:
    try:
        importlib.import_module(mod)
        return True
    except Exception:
        return False


def main() -> int:
    missing = [m for m in CRITICAL_MODULES if not can_import(m)]
    if not missing:
        print("[deps] All critical modules present.")
        return 0

    print(f"[deps] Missing modules: {missing}")
    if not REQ_FILE.exists():
        print("[deps] requirements.txt not found; cannot auto-install.")
        return 1

    # Try user install to avoid permission issues for seluser
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--user",
        "--no-cache-dir",
        "-r",
        str(REQ_FILE),
    ]
    print("[deps] Running:", " ".join(cmd))
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        print("[deps] pip install failed:", e)
        return 2

    # Re-check
    still_missing = [m for m in CRITICAL_MODULES if not can_import(m)]
    if still_missing:
        print(f"[deps] Still missing after install: {still_missing}")
        return 3

    print("[deps] Dependencies installed and verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
