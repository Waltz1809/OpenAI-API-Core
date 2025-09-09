"""Step 4: Create chapters under a volume (merges content editing inside).

Workflow per chapter file:
  1) Navigate to manage?book_id=<id>&action=createchapter
  2) Fill title input with file stem
  3) Set TinyMCE content (converted from Markdown to HTML)
  4) Click submit button to create chapter

Utilities are provided to iterate discovered volumes and map to book_ids.
"""
from typing import Optional, Dict, List, Any
from pathlib import Path
import logging

from playwright.async_api import Page

from .step2_3_series import build_manage_url, discover_volumes
from .step5_editor import fill_title as _fill_title
from .step5_editor import fill_content_html as _fill_content_html
from .step5_editor import submit as _submit
from .editor import markdown_to_html


DEFAULT_SELECTORS = {
    # Chapter title input
    'title': 'input[name="title"]',
    # TinyMCE iframe and body
    'editor_iframe': 'iframe[title="Vùng văn bản phong phú"]',
    'editor_body': '#tinymce',
    # Submit button in the form
    'submit_button': 'button.btn.btn-primary',
}


def _read_markdown(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='ignore')


def _chapter_title_from_filename(path: Path) -> str:
    # Use filename without extension as title
    return path.stem


def _create_chapter_url(novel_id: str, book_id: str, *, base_url: Optional[str] = None) -> str:
    base_manage = build_manage_url(novel_id, base_url=base_url)
    return f"{base_manage}?book_id={book_id}&action=createchapter"


async def create_chapter_for_file(
    page: Page,
    *,
    novel_id: str,
    book_id: str,
    md_file: str,
    base_url: Optional[str] = None,
    selectors: Optional[dict] = None,
    img_base_url: Optional[str] = None,
    wait_after_submit_ms: int = 15000,
) -> bool:
    """Create a single chapter from a markdown file. Returns True on apparent success.

    Success criteria: submission performed; we don't hard-assert on URL since site behavior might vary.
    Logs current URL after submit for visibility.
    """
    logger = logging.getLogger('uploader')
    sels = {**DEFAULT_SELECTORS, **(selectors or {})}
    logger.debug(f"[chapter] Using selectors: title={sels.get('title')} iframe={sels.get('editor_iframe')} body={sels.get('editor_body')} submit={sels.get('submit_button')}")

    path = Path(md_file)
    title = _chapter_title_from_filename(path)
    md_text = _read_markdown(path)
    html = markdown_to_html(md_text)
    logger.debug(f"[chapter] File='{path.name}', md_len={len(md_text)}, html_len={len(html)}")

    # 1) Open create chapter form
    url = _create_chapter_url(novel_id, book_id, base_url=base_url)
    logger.debug(f"[chapter] Navigating to: {url}")
    await page.goto(url)
    logger.debug(f"[chapter] Landed on URL: {page.url}")
    # quick visibility: is the action iframe present?
    try:
        frame_present = bool(page.frame(name='action'))
        logger.debug(f"[chapter] action iframe present: {frame_present}")
    except Exception:
        logger.debug("[chapter] action iframe presence check failed")

    # 2) Fill title
    logger.info(f"[chapter] Title: {title}")
    await _fill_title(page, sels, title)

    # 3) Fill content
    logger.info(f"[chapter] Setting content ({len(html)} chars HTML)")
    await _fill_content_html(page, sels, html)

    # 4) Submit
    logger.info("[chapter] Submitting chapter form")
    await _submit(page, sels, wait_ms_after_submit=wait_after_submit_ms)
    logger.info(f"[chapter] After submit URL: {page.url}")
    return True


async def create_chapters_for_volume_dir(
    page: Page,
    *,
    novel_id: str,
    book_id: str,
    volume_dir: str,
    base_url: Optional[str] = None,
    selectors: Optional[dict] = None,
    img_base_url: Optional[str] = None,
) -> Dict[str, bool]:
    """Create all chapters in a given volume directory. Returns {filename: success}."""
    logger = logging.getLogger('uploader')
    vdir = Path(volume_dir)
    logger.info(f"[volume] Scanning dir: {vdir.resolve()} ({vdir.name})")

    md_exts = {'.md', '.markdown', '.mdx', '.mdown'}
    files = sorted([p for p in vdir.iterdir() if p.is_file() and p.suffix.lower() in md_exts])
    logger.info(f"[volume] {vdir.name}: {len(files)} top-level chapter file(s)")

    if not files:
        # Fallback: recursive search (handles nested chapter folders)
        logger.debug("[volume] No top-level .md; trying recursive search...")
        files = sorted([p for p in vdir.rglob('*') if p.is_file() and p.suffix.lower() in md_exts])
        logger.info(f"[volume] {vdir.name}: {len(files)} chapter file(s) found recursively")
        # Log a brief sample of entries for diagnostics
        try:
            entries = list(vdir.iterdir())
            sample = ", ".join(e.name for e in entries[:10])
            logger.debug(f"[volume] Dir entries sample: {sample}{' ...' if len(entries)>10 else ''}")
        except Exception:
            pass

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


async def create_chapters_for_discovered_volumes(
    page: Page,
    *,
    input_path: str,
    novel_id: str,
    volume_book_ids: Dict[str, Optional[str]],
    base_url: Optional[str] = None,
    selectors: Optional[dict] = None,
    img_base_url: Optional[str] = None,
) -> Dict[str, Dict[str, bool]]:
    """Iterate discovered volumes and create chapters using the provided book_id mapping.

    Returns { volume_name: { chapter_file: success } }
    """
    logger = logging.getLogger('uploader')
    vols = discover_volumes(input_path)
    overall: Dict[str, Dict[str, bool]] = {}
    for v in vols:
        name = v['name']
        vpath = v['path']
        bid = (volume_book_ids or {}).get(name)
        if not bid:
            logger.warning(f"[volumes] Missing book_id for volume '{name}', skipping")
            continue
        logger.info(f"[volumes] Processing volume '{name}' with book_id={bid}")
        result = await create_chapters_for_volume_dir(
            page,
            novel_id=novel_id,
            book_id=bid,
            volume_dir=vpath,
            base_url=base_url,
            selectors=selectors,
            img_base_url=img_base_url,
        )
        overall[name] = result
    return overall
