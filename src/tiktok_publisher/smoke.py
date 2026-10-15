from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from tiktok_publisher.browser_session import close_browser, open_browser
from tiktok_publisher.config import AppSettings, load_selectors
from tiktok_publisher.dolphin_client import DolphinClient

logger = logging.getLogger(__name__)


def run_smoke(settings: AppSettings, profile_id: str) -> int:
    dolphin = DolphinClient(settings)
    ok, msg = dolphin.ping()
    if not ok:
        print(f"Dolphin API: {msg}")
        return 1

    loop = asyncio.new_event_loop()
    handle = None
    try:
        session = dolphin.start_profile(profile_id)
        handle = open_browser(session, loop)
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
        close_browser(handle)
        if profile_id:
            dolphin.stop_profile(profile_id)
        loop.close()
