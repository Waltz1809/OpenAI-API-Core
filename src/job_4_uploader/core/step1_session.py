"""Step 1: Open browser and login.

This module wraps launching a browser context and performing login,
matching the sample behavior by default (no auto-submit or wait).
"""
from typing import Optional, Tuple
from playwright.async_api import Page, Browser, BrowserContext

from .browser import launch_browser, close_all  # re-export if needed
from .auth import login as core_login


async def setup_browser(
    *,
    headless: bool = False,
    channel: Optional[str] = "msedge",
) -> Tuple[object, Browser, BrowserContext, Page]:
    """Launch browser, create a context with clipboard permissions, return (p,browser,context,page)."""
    return await launch_browser(headless=headless, channel=channel)


async def login(
    page: Page,
    username: str,
    password: str,
    *,
    base_url: Optional[str] = None,
    wait_for_login: bool = False,
    wait_url_contains: Optional[str] = None,
    wait_timeout_ms: int = 300000,
) -> None:
    """Fill credentials on the login page. Does not auto-submit by default.

    Set wait_for_login=True to wait for a URL change indicating success (optional).
    """
    await core_login(
        page,
        username,
        password,
        base_url=base_url,
        wait_for_login=wait_for_login,
        wait_url_contains=wait_url_contains,
        wait_timeout_ms=wait_timeout_ms,
    )


async def start_session_and_login_interactive(
    username: str,
    password: str,
    *,
    headless: bool = False,
    channel: Optional[str] = "msedge",
    base_url: Optional[str] = None,
) -> Tuple[object, Browser, BrowserContext, Page]:
    """Replicates the sample logic: open browser, go to login, fill creds, wait for user to solve CAPTCHA and click login.

    Returns (p, browser, context, page).
    """
    p, browser, context, page = await setup_browser(headless=headless, channel=channel)
    # Navigate and fill credentials (no auto-wait/submit)
    await core_login(page, username, password, base_url=base_url, wait_for_login=False)

    # Print the same instructions as the sample and wait for user confirmation
    print("==============================================================")
    print(">> Vui lòng giải reCAPTCHA và nhấn 'Đăng nhập'.")
    print(">> Sau khi đăng nhập xong, quay lại đây và nhấn Enter.")
    print("==============================================================")
    input("Nhấn Enter để bắt đầu quá trình đăng hàng loạt...")

    return p, browser, context, page
