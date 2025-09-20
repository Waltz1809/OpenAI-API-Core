from typing import Optional, Tuple

from playwright.async_api import async_playwright, Page, Browser, BrowserContext


async def launch_browser(
    headless: bool = False,
    channel: Optional[str] = "msedge",
) -> Tuple[object, Browser, BrowserContext, Page]:
    """Start Playwright and launch a browser."""
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=headless, channel=channel)
    context = await browser.new_context()
    await context.grant_permissions(["clipboard-read", "clipboard-write"])
    page = await context.new_page()
    return p, browser, context, page


async def close_all(p: object, browser: Browser, context: BrowserContext) -> None:
    """Close context, browser, and stop Playwright."""
    try:
        await context.close()
    finally:
        try:
            await browser.close()
        finally:
            try:
                await p.stop()  # type: ignore[attr-defined]
            except Exception:
                pass