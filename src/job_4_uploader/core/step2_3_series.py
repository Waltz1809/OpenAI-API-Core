"""Steps 2 & 3: Open novel editor (manage) and create new volume.

Also includes helpers to parse the input folder structure into ordered volumes and chapters:
    input_path/VolumeFolder/*.md  ->  volumes[] with sorted chapters[]

Volume and chapter order use natural sort on folder/file names to be stable even when names vary.
"""
from typing import Optional, List, Dict, Any
from playwright.async_api import Page
from pathlib import Path
import re
import logging

from .series import open_series_manage as _open_series_manage
from .series import create_new_volume as _create_new_volume


async def open_manage(page: Page, novel_id: str, *, base_url: Optional[str] = None, manage_url_template: Optional[str] = None) -> str:
    """Open the series manage page for a given novel id. Returns the URL navigated to."""
    logger = logging.getLogger('uploader')
    logger.debug(f"Open manage for novel_id={novel_id}, base_url={base_url}")
    url = await _open_series_manage(page, novel_id, manage_url_template, base_url=base_url)
    logger.debug(f"Manage URL navigated: {url}")
    return url


async def create_volume(page: Page, selectors: dict, *, name: str, number: Optional[int] = None, description: Optional[str] = None) -> None:
    """Create a volume using the provided selectors mapped to the site's UI."""
    await _create_new_volume(page, selectors, name, number=number, description=description)


# -----------------------------
# Volume/Chapter discovery
# -----------------------------

_MD_EXTS = {".md", ".markdown", ".mdown", ".mdx"}


def _natural_key(s: str):
    """Split string into a list of text/number chunks for natural sorting (e.g., V2 < V10)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def discover_volumes(input_path: str) -> List[Dict[str, Any]]:
    """Parse input_path into ordered volumes and chapters.

    input structure:
        input_path/
            <volume_folder_1>/
                *.md (chapters)
            <volume_folder_2>/
                *.md

    Fallback: if input_path itself contains markdown files and no subfolders, treat it as a single volume.

    Returns a list of volumes, each volume is a dict:
        { 'name': str, 'path': str, 'chapters': [ { 'name': str, 'path': str } ... ] }
    Volumes and chapters are sorted naturally by folder/file name.
    """
    logger = logging.getLogger('uploader')
    root = Path(input_path)
    logger.info(f"Discovering volumes under: {root}")
    if not root.exists() or not root.is_dir():
        logger.warning(f"Input path not found or not a directory: {root}")
        return []

    def is_hidden(p: Path) -> bool:
        return p.name.startswith('.') or p.name.startswith('_')

    # Collect volume directories
    volume_dirs = [d for d in root.iterdir() if d.is_dir() and not is_hidden(d)]
    volume_dirs.sort(key=lambda p: _natural_key(p.name))
    logger.info(f"Found {len(volume_dirs)} volume folders")
    for d in volume_dirs:
        logger.debug(f"  volume dir: {d.name}")

    volumes: List[Dict[str, Any]] = []
    if not volume_dirs:
        # Fallback: use root as a single volume if md files exist
        chapter_files = [f for f in root.iterdir() if f.is_file() and f.suffix.lower() in _MD_EXTS and not is_hidden(f)]
        chapter_files.sort(key=lambda p: _natural_key(p.name))
        if chapter_files:
            logger.info("No subfolders; treating root as a single volume")
            chapters = [{"name": f.name, "path": str(f)} for f in chapter_files]
            volumes.append({
                "name": root.name,
                "path": str(root),
                "chapters": chapters,
            })
        else:
            logger.warning("No markdown files found in input path")
            return []
    else:
        for vdir in volume_dirs:
            # Collect markdown chapter files in the volume directory
            chapter_files = [f for f in vdir.iterdir() if f.is_file() and f.suffix.lower() in _MD_EXTS and not is_hidden(f)]
            chapter_files.sort(key=lambda p: _natural_key(p.name))
            chapters = [{"name": f.name, "path": str(f)} for f in chapter_files]

            volumes.append({
                "name": vdir.name,
                "path": str(vdir),
                "chapters": chapters,
            })

    logger.info(f"Discovered {len(volumes)} volume(s)")
    for v in volumes:
        logger.info(f"  volume: {v['name']} (chapters: {len(v['chapters'])})")
    return volumes


# -----------------------------
# Step 2 & 3 Orchestration
# -----------------------------

DEFAULT_URL = "https://docln.sbs"


def build_manage_url(novel_id: str, *, base_url: Optional[str] = None) -> str:
    base = (base_url or DEFAULT_URL).rstrip("/")
    return f"{base}/action/series/{novel_id}/manage"


def scan_volume_names(input_path: str) -> List[str]:
    """Return natural-sorted list of volume folder names under input_path."""
    vols = discover_volumes(input_path)
    return [v["name"] for v in vols]


async def _fill_title_and_submit_createbook(page: Page, volume_name: str) -> None:
    """On the createbook page, fill title and submit. Targets the action iframe when present."""
    logger = logging.getLogger('uploader')
    logger.debug("Trying to submit createbook form via iframe 'action'")
    # Prefer working inside the form iframe if present
    form_frame = page.frame_locator('iframe[name="action"]')
    title_input = form_frame.locator('input[name="title"]')
    try:
        await title_input.wait_for(state='visible', timeout=15000)
        await title_input.fill(volume_name)
        # Try role-based button first
        try:
            await form_frame.get_by_role('button', name='Thêm sách').click()
        except Exception:
            await form_frame.locator('button.btn.btn-primary').click()
        logger.debug("Createbook submitted via iframe")
        return
    except Exception:
        logger.debug("Iframe path failed; falling back to main page selectors")

    # Fallback: try on main page (if no iframe)
    title_input = page.locator('input[name="title"]')
    await title_input.wait_for(state='visible', timeout=15000)
    await title_input.fill(volume_name)
    try:
        await page.get_by_role('button', name='Thêm sách').click()
    except Exception:
        await page.locator('button.btn.btn-primary').click()
    logger.debug("Createbook submitted via main page")


def _parse_book_id_from_url(url: str) -> Optional[str]:
    m = re.search(r"[?&]book_id=(\d+)", url)
    return m.group(1) if m else None


async def _wait_for_book_id(page: Page, timeout_ms: int = 30000) -> Optional[str]:
    """Wait for a redirect to a URL containing book_id=...&action=editbook, on either page or action frame."""
    logger = logging.getLogger('uploader')
    logger.debug("Waiting for book_id in URL redirect...")
    # First, try page-level URL
    try:
        await page.wait_for_url(lambda u: ('book_id=' in u and 'action=editbook' in u), timeout=timeout_ms)
        bid = _parse_book_id_from_url(page.url)
        if bid:
            logger.info(f"Redirect detected on page URL: {page.url}")
            return bid
    except Exception:
        logger.debug("Page-level URL wait timed out; will poll iframe")

    # Poll the 'action' iframe's URL
    elapsed = 0
    step = 500
    while elapsed < timeout_ms:
        frame = page.frame(name='action')
        if frame:
            url = frame.url
            if url and ('book_id=' in url and 'action=editbook' in url):
                bid = _parse_book_id_from_url(url)
                if bid:
                    logger.info(f"Redirect detected in iframe URL: {url}")
                    return bid
        await page.wait_for_timeout(step)
        elapsed += step
    logger.warning("Timed out waiting for book_id in redirect")
    return None


async def create_volumes_and_get_book_ids(
    page: Page,
    input_path: str,
    novel_id: str,
    *,
    base_url: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """For each volume folder under input_path, create a new book and return a map { volume_name: book_id }.

    Steps per volume:
      1) Open manage URL with action=createbook
      2) Fill input[name='title'] with volume_name
      3) Click the 'Thêm sách' submit button
      4) Wait for redirect containing book_id=...&action=editbook, capture book_id
    """
    logger = logging.getLogger('uploader')
    manage_url = build_manage_url(novel_id, base_url=base_url)
    logger.info(f"Manage URL base: {manage_url}")
    volume_names = scan_volume_names(input_path)
    logger.info(f"Volumes to create: {volume_names}")
    mapping: Dict[str, Optional[str]] = {name: None for name in volume_names}

    if not volume_names:
        logger.warning("No volume names discovered from input path")
        return mapping

    for name in volume_names:
        try:
            logger.info(f"Creating volume: {name}")
            # 1) Open createbook page
            create_url = f"{manage_url}?action=createbook"
            logger.debug(f"Navigating to: {create_url}")
            await page.goto(create_url)
            logger.debug(f"Landed on URL: {page.url}")

            # 2-3) Fill title and submit
            await _fill_title_and_submit_createbook(page, name)
            logger.debug("Submitted createbook form; waiting for book_id...")

            # 4) Wait for redirect and parse book_id
            book_id = await _wait_for_book_id(page, timeout_ms=30000)
            mapping[name] = book_id
            logger.info(f"Result for '{name}': book_id={book_id}")
        except Exception as e:
            logger.exception(f"Failed to create volume '{name}': {e}")
            mapping[name] = None

    return mapping


async def create_volume_and_get_book_id(
    page: Page,
    *,
    novel_id: str,
    volume_name: str,
    base_url: Optional[str] = None,
    timeout_ms: int = 30000,
) -> Optional[str]:
    """Create a single volume and return its book_id (or None on failure)."""
    logger = logging.getLogger('uploader')
    manage_url = build_manage_url(novel_id, base_url=base_url)
    create_url = f"{manage_url}?action=createbook"
    logger.info(f"Creating volume '{volume_name}' via {create_url}")
    await page.goto(create_url)
    logger.debug(f"Create volume landed URL: {page.url}")
    await _fill_title_and_submit_createbook(page, volume_name)
    bid = await _wait_for_book_id(page, timeout_ms=timeout_ms)
    logger.info(f"Volume '{volume_name}' book_id={bid}")
    return bid
