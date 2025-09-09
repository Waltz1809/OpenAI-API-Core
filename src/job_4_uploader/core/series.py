from typing import Optional
from playwright.async_api import Page

DEFAULT_MANAGE_URL_PATH = "/action/series/{novel_id}/manage"

async def open_series_manage(
    page: Page,
    novel_id: str,
    manage_url_template: Optional[str] = None,
    *,
    base_url: Optional[str] = None,
) -> str:
    path_or_template = (manage_url_template or DEFAULT_MANAGE_URL_PATH)
    if base_url and path_or_template.startswith("/"):
        base = base_url.rstrip("/")
        url = f"{base}{path_or_template}".format(novel_id=novel_id)
    else:
        url = path_or_template.format(novel_id=novel_id)
    await page.goto(url)
    return url

async def create_new_volume(
    page: Page,
    selectors: dict,
    name: str,
    *,
    number: Optional[int] = None,
    description: Optional[str] = None,
) -> None:
    sm = (selectors or {}).get('series_manage', {})
    new_btn = sm.get('new_volume_button')
    name_input = sm.get('volume_title_input')
    submit_btn = sm.get('volume_submit_button')

    if new_btn:
        try:
            await page.locator(new_btn).click(timeout=5000)
        except Exception:
            pass
    if name_input:
        try:
            await page.locator(name_input).fill(name)
        except Exception:
            pass
    if submit_btn:
        try:
            await page.locator(submit_btn).click()
        except Exception:
            pass

async def open_new_chapter_form(page: Page, selectors: dict) -> None:
    sm = (selectors or {}).get('series_manage', {})
    new_chap_btn = sm.get('new_chapter_button')
    if new_chap_btn:
        try:
            await page.locator(new_chap_btn).click(timeout=5000)
        except Exception:
            pass
