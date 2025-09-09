from playwright.async_api import Page, TimeoutError
from urllib.parse import urlparse

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
    """Navigate to login and fill credentials.

    Behavior matches the sample by default (no automatic wait or submit).
    Optionally, set wait_for_login=True to wait for a URL change containing a substring.
    """
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    url = login_url or f"{base}/login"
    await page.goto(url)
    await page.locator("#name").fill(username)
    await page.locator("#password").fill(password)

    if not wait_for_login:
        return

    # When waiting, derive default wait_url_contains from base host if not provided
    if wait_url_contains is None:
        host = urlparse(base).netloc or base
        wait_url_contains = host.split(":")[0]
    try:
        await page.wait_for_url(lambda u: (wait_url_contains or "") in u, timeout=wait_timeout_ms)
    except TimeoutError:
        # Non-fatal; some sites keep same URL
        pass
