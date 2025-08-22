"""
Run sequentially:
  1) scripts.smoke_betburger_arbs_tabs (login + open /es/arbs + duplicate tabs)
  2) scripts.arbs_select_filters_and_dump (select filters per tab + send Telegram alerts)

Usage:
  python -m scripts.run_smoke_and_select

Optional env:
  SLEEP_BETWEEN_STEPS=2   # seconds to wait between smoke and select (default 1)
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.logger import get_module_logger  # type: ignore

logger = get_module_logger("run_smoke_and_select")


def main() -> int:
    # Import lazily to keep side effects controlled
    from scripts import smoke_betburger_arbs_tabs as smoke  # type: ignore
    from scripts import arbs_select_filters_and_dump as select  # type: ignore

    logger.info("Step 1/2: smoke_betburger_arbs_tabs")
    rc1 = smoke.main()
    if rc1 != 0:
        logger.error("Smoke step failed, aborting", return_code=rc1)
        return rc1 if isinstance(rc1, int) else 1

    # Short pause to ensure tabs are fully initialized
    sleep_secs = float(os.getenv("SLEEP_BETWEEN_STEPS", "1") or "1")
    if sleep_secs > 0:
        time.sleep(sleep_secs)

    logger.info("Step 2/2: arbs_select_filters_and_dump")
    rc2 = select.main()
    if rc2 != 0:
        logger.error("Select step finished with non-zero code", return_code=rc2)
        return rc2 if isinstance(rc2, int) else 1

    logger.info("All steps completed successfully - browser session kept alive")
    logger.info("You can now run: python3 -m scripts.betburger_send_first_tab_results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
