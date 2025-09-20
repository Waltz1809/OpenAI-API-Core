from urllib.parse import urlparse

from playwright.async_api import Page, TimeoutError

DEFAULT_BASE_URL = "https://docln.sbs"


async def login(
    page: Page,
    username: str,
    password: str,
    login_url: str | None = None,
    *,
    base_url: str | None = None,
    wait_for_login: bool = False,
    wait_url_contains: str | None = None,
    wait_timeout_ms: int = 300000,
) -> None:
    """
    Navigate to login and fill credentials.
    Optionally auto-waits for URL change after submit.
    """
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    url = login_url or f"{base}/login"

    await page.goto(url)
    await page.locator("#name").fill(username)
    await page.locator("#password").fill(password)

    # Auto submit
    try:
        await page.locator("button.btn.btn-primary:has-text('Đăng nhập')").click()
    except Exception:
        pass

    if not wait_for_login:
        return

    if wait_url_contains is None:
        host = urlparse(base).netloc or base
        wait_url_contains = host.split(":")[0]

    try:
        await page.wait_for_url(
            lambda u: (wait_url_contains or "") in u, timeout=wait_timeout_ms
        )
    except TimeoutError:
        # Non-fatal
        pass
