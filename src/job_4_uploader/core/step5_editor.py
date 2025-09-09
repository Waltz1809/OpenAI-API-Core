"""Step 5: Add content to TinyMCE editor and submit chapter."""
from typing import Optional
from playwright.async_api import Page

from .editor import fill_title as _fill_title
from .editor import set_tinymce_content as _set_tinymce_content


async def fill_title(page: Page, selectors: dict, title: str) -> None:
    await _fill_title(page, selectors, title)


async def fill_content_html(page: Page, selectors: dict, html: str, *, editor_ready_timeout_ms: int = 60000) -> None:
    await _set_tinymce_content(page, selectors, html, editor_ready_timeout_ms=editor_ready_timeout_ms)


async def submit(page: Page, selectors: dict, *, wait_ms_after_submit: int = 15000, success_selector: Optional[str] = None) -> None:
    form_frame = page.frame_locator('iframe[name="action"]')
    await form_frame.locator(selectors['submit_button']).click()

    if success_selector:
        try:
            await page.locator(success_selector).wait_for(state='visible', timeout=30000)
            return
        except Exception:
            pass
    await page.wait_for_timeout(wait_ms_after_submit)
