from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from tiktok_publisher.config import AppSettings, load_selectors
from tiktok_publisher.dolphin_client import DolphinClient
from tiktok_publisher.session_runner import profile_browser_session

logger = logging.getLogger(__name__)


def run_smoke(settings: AppSettings, profile_id: str) -> int:
    dolphin = DolphinClient(settings)
    ok, msg = dolphin.ping()
    if not ok:
        print(f"Dolphin API: {msg}")
        return 1

    loop = asyncio.new_event_loop()
    try:
        with profile_browser_session(settings, profile_id, loop) as bs:
            if settings.dry_run:
                print("OK: dry-run smoke (no browser)")
                return 0
            handle = bs.handle
            assert handle is not None
            selectors = load_selectors(settings.selectors_file)
            upload_url = selectors.get("upload_url", "https://www.tiktok.com/upload")
            page = loop.run_until_complete(handle.get_page())
            loop.run_until_complete(page.goto(upload_url, wait_until="domcontentloaded"))
            out = Path(settings.logging.log_dir) / f"smoke_{profile_id}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            loop.run_until_complete(page.screenshot(path=str(out), full_page=True))
            print(f"OK: screenshot {out} url={page.url}")
            return 0
    except Exception as e:
        print(f"Smoke failed: {e}")
        return 1
    finally:
        loop.close()
