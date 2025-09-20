"""
Consolidated uploader steps for Job 4.

This module merges prior step1_session, step2_3_series, step4_chapter, step5_editor
into a single lightweight set of functions used by main.py.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from playwright.async_api import Browser, BrowserContext, Page

from .auth import login as core_login
from .browser import close_all, launch_browser
from .editor import (
    fill_title as _fill_title,
    markdown_to_html,
    set_tinymce_content as _set_tinymce_content,
)

# -----------------------------
# Session / login
# -----------------------------


async def start_session_and_login_interactive(
    username: str,
    password: str,
    *,
    headless: bool = False,
    channel: str | None = "msedge",
    base_url: str | None = None,
) -> Tuple[object, Browser, BrowserContext, Page]:
    """Launch browser, go to login, fill credentials, and auto-login."""
    p, browser, context, page = await launch_browser(headless=headless, channel=channel)
    await core_login(page, username, password, base_url=base_url, wait_for_login=False)
    return p, browser, context, page


# -----------------------------
# Volume & chapter discovery
# -----------------------------

_MD_EXTS = {".md", ".markdown", ".mdown", ".mdx"}


def _natural_key(s: str) -> list[Any]:
    """Split string into list of ints/strings for natural sorting."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def discover_volumes(input_path: str) -> List[Dict[str, Any]]:
    """
    Return list of volumes with chapters discovered under input_path.

    Structure:
        input/VolumeFolder/*.md
    If no subfolders but md files, treat root as one volume.
    """
    logger = logging.getLogger("uploader")
    root = Path(input_path)
    logger.info(f"Discovering volumes under: {root}")

    if not root.exists() or not root.is_dir():
        logger.warning(f"Input path not found or not a directory: {root}")
        return []

    def is_hidden(p: Path) -> bool:
        return p.name.startswith(".") or p.name.startswith("_")

    volume_dirs = [d for d in root.iterdir() if d.is_dir() and not is_hidden(d)]
    volume_dirs.sort(key=lambda p: _natural_key(p.name))
    logger.info(f"Found {len(volume_dirs)} volume folders")

    volumes: List[Dict[str, Any]] = []

    if not volume_dirs:
        # No subfolders → treat root as a single volume
        chapter_files = [
            f
            for f in root.iterdir()
            if f.is_file() and f.suffix.lower() in _MD_EXTS and not is_hidden(f)
        ]
        chapter_files.sort(key=lambda p: _natural_key(p.name))
        if chapter_files:
            volumes.append(
                {
                    "name": root.name,
                    "path": str(root),
                    "chapters": [{"name": f.name, "path": str(f)} for f in chapter_files],
                }
            )
        else:
            logger.warning("No markdown files found in input path")
            return []
    else:
        for vdir in volume_dirs:
            chapter_files = [
                f
                for f in vdir.iterdir()
                if f.is_file() and f.suffix.lower() in _MD_EXTS and not is_hidden(f)
            ]
            chapter_files.sort(key=lambda p: _natural_key(p.name))
            volumes.append(
                {
                    "name": vdir.name,
                    "path": str(vdir),
                    "chapters": [{"name": f.name, "path": str(f)} for f in chapter_files],
                }
            )

    logger.info(f"Discovered {len(volumes)} volume(s)")
    for v in volumes:
        logger.info(f"  volume: {v['name']} (chapters: {len(v['chapters'])})")
    return volumes


# -----------------------------
# Volume creation helpers
# -----------------------------

DEFAULT_URL = "https://docln.sbs"


def _build_manage_url(novel_id: str, *, base_url: str | None = None) -> str:
    base = (base_url or DEFAULT_URL).rstrip("/")
    return f"{base}/action/series/{novel_id}/manage"


async def _fill_title_and_submit_createbook(page: Page, volume_name: str) -> None:
    """Fill volume title and click submit button (iframe or fallback)."""
    logger = logging.getLogger("uploader")
    form_frame = page.frame_locator('iframe[name="action"]')
    title_input = form_frame.locator('input[name="title"]')
    try:
        await title_input.wait_for(state="visible", timeout=15000)
        await title_input.fill(volume_name)
        try:
            await form_frame.get_by_role("button", name="Thêm sách").click()
        except Exception:
            await form_frame.locator("button.btn.btn-primary").click()
        return
    except Exception:
        logger.debug("Iframe path failed; fallback to main page")

    # Fallback: main page
    title_input = page.locator('input[name="title"]')
    await title_input.wait_for(state="visible", timeout=15000)
    await title_input.fill(volume_name)
    try:
        await page.get_by_role("button", name="Thêm sách").click()
    except Exception:
        await page.locator("button.btn.btn-primary").click()


def _parse_book_id_from_url(url: str) -> Optional[str]:
    m = re.search(r"[?&]book_id=(\d+)", url)
    return m.group(1) if m else None


async def _wait_for_book_id(page: Page, timeout_ms: int = 30000) -> Optional[str]:
    """Wait until book_id appears in URL (either page or iframe)."""
    logger = logging.getLogger("uploader")
    try:
        await page.wait_for_url(
            lambda u: ("book_id=" in u and "action=editbook" in u), timeout=timeout_ms
        )
        bid = _parse_book_id_from_url(page.url)
        if bid:
            return bid
    except Exception:
        pass

    elapsed, step = 0, 500
    while elapsed < timeout_ms:
        frame = page.frame(name="action")
        if frame:
            url = frame.url
            if url and ("book_id=" in url and "action=editbook" in url):
                bid = _parse_book_id_from_url(url)
                if bid:
                    return bid
        await page.wait_for_timeout(step)
        elapsed += step
    return None


async def create_volume_and_get_book_id(
    page: Page,
    *,
    novel_id: str,
    volume_name: str,
    base_url: str | None = None,
    timeout_ms: int = 30000,
) -> Optional[str]:
    """Create a new volume and return its book_id."""
    logger = logging.getLogger("uploader")
    manage_url = _build_manage_url(novel_id, base_url=base_url)
    create_url = f"{manage_url}?action=createbook"
    logger.info(f"Creating volume '{volume_name}' via {create_url}")

    await page.goto(create_url)
    await _fill_title_and_submit_createbook(page, volume_name)
    bid = await _wait_for_book_id(page, timeout_ms=timeout_ms)
    logger.info(f"Volume '{volume_name}' book_id={bid}")
    return bid


# -----------------------------
# Chapter creation
# -----------------------------

DEFAULT_SELECTORS = {
    "title": 'input[name="title"]',
    "editor_iframe": 'iframe[title="Vùng văn bản phong phú"]',
    "editor_body": "#tinymce",
    "submit_button": "button.btn.btn-primary",
}


def _read_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _chapter_title_from_filename(path: Path) -> str:
    return path.stem


def _create_chapter_url(
    novel_id: str, book_id: str, *, base_url: str | None = None
) -> str:
    base_manage = _build_manage_url(novel_id, base_url=base_url)
    return f"{base_manage}?book_id={book_id}&action=createchapter"


async def _submit_form(
    page: Page, selectors: dict, wait_after_submit_ms: int = 15000
) -> None:
    form_frame = page.frame_locator('iframe[name="action"]')
    await form_frame.locator(selectors["submit_button"]).click()
    await page.wait_for_timeout(wait_after_submit_ms)


async def create_chapter_for_file(
    page: Page,
    *,
    novel_id: str,
    book_id: str,
    md_file: str,
    base_url: str | None = None,
    selectors: dict | None = None,
    img_base_url: str | None = None,
    wait_after_submit_ms: int = 15000,
) -> bool:
    """Upload a single chapter from a markdown file."""
    logger = logging.getLogger("uploader")
    sels = {**DEFAULT_SELECTORS, **(selectors or {})}
    path = Path(md_file)

    title = _chapter_title_from_filename(path)
    md_text = _read_markdown(path)
    html = markdown_to_html(md_text, img_base_url=img_base_url)

    url = _create_chapter_url(novel_id, book_id, base_url=base_url)
    await page.goto(url)
    logger.info(f"[chapter] Title: {title}")

    await _fill_title(page, sels, title)
    logger.info(f"[chapter] Setting content ({len(html)} chars HTML)")
    await _set_tinymce_content(page, sels, html)

    logger.info("[chapter] Submitting chapter form")
    await _submit_form(page, sels, wait_after_submit_ms=wait_after_submit_ms)
    logger.info(f"[chapter] After submit URL: {page.url}")
    return True


async def create_chapters_for_volume_dir(
    page: Page,
    *,
    novel_id: str,
    book_id: str,
    volume_dir: str,
    base_url: str | None = None,
    selectors: dict | None = None,
    img_base_url: str | None = None,
) -> Dict[str, bool]:
    """Upload all chapters in a given volume directory."""
    logger = logging.getLogger("uploader")
    vdir = Path(volume_dir)
    logger.info(f"[volume] Scanning dir: {vdir.resolve()} ({vdir.name})")

    md_exts = {".md", ".markdown", ".mdx", ".mdown"}
    files = sorted(
        [p for p in vdir.iterdir() if p.is_file() and p.suffix.lower() in md_exts]
    )
    logger.info(f"[volume] {vdir.name}: {len(files)} top-level chapter(s)")

    if not files:
        files = sorted(
            [p for p in vdir.rglob("*") if p.is_file() and p.suffix.lower() in md_exts]
        )
        logger.info(f"[volume] {vdir.name}: {len(files)} chapter(s) found recursively")

    results: Dict[str, bool] = {}
    for f in files:
        try:
            logger.info(f"[volume] Creating chapter from: {f.name}")
            ok = await create_chapter_for_file(
                page,
                novel_id=novel_id,
                book_id=book_id,
                md_file=str(f),
                base_url=base_url,
                selectors=selectors,
                img_base_url=img_base_url,
            )
            results[f.name] = ok
        except Exception as e:
            logger.exception(f"[volume] Failed for {f.name}: {e}")
            results[f.name] = False
    return results


__all__ = [
    "start_session_and_login_interactive",
    "discover_volumes",
    "create_volume_and_get_book_id",
    "create_chapters_for_volume_dir",
    "close_all",
]