import logging
import re
import sys
import importlib
from typing import Optional

from playwright.async_api import Page


async def fill_title(page: Page, selectors: dict, title: str) -> None:
    logger = logging.getLogger("uploader")
    form_frame = page.frame_locator('iframe[name="action"]')
    title_locator = form_frame.locator(selectors["title"])
    logger.debug(f"[editor] Waiting for title locator: {selectors['title']}")
    await title_locator.wait_for(state="visible", timeout=30000)
    logger.debug(f"[editor] Filling title with {len(title)} chars")
    await title_locator.fill(title)


async def set_tinymce_content(
    page: Page,
    selectors: dict,
    html: str,
    editor_ready_timeout_ms: int = 60000,
) -> None:
    logger = logging.getLogger("uploader")
    form_frame = page.frame_locator('iframe[name="action"]')
    editor_iframe_locator = form_frame.locator(selectors["editor_iframe"])
    logger.debug(f"[editor] Waiting for editor iframe: {selectors['editor_iframe']}")
    await editor_iframe_locator.wait_for(
        state="attached", timeout=editor_ready_timeout_ms
    )

    # Try TinyMCE API
    form_frame_obj = page.frame(name="action")
    try:
        if form_frame_obj:
            await form_frame_obj.evaluate(
                """
                html => {
                    if (window.tinymce && tinymce.activeEditor) {
                        tinymce.activeEditor.setContent(html);
                        tinymce.activeEditor.focus();
                    } else {
                        throw new Error('TinyMCE not ready');
                    }
                }
                """,
                html,
            )
            logger.debug("[editor] Set content via TinyMCE activeEditor API")
            return
    except Exception as e:
        logger.debug(f"[editor] TinyMCE API path failed: {e}")

    # Fallback: editor body
    editor_body_locator = form_frame.frame_locator(selectors["editor_iframe"]).locator(
        selectors["editor_body"]
    )
    logger.debug(f"[editor] Waiting for editor body: {selectors['editor_body']}")
    await editor_body_locator.wait_for(
        state="visible", timeout=editor_ready_timeout_ms
    )

    try:
        await editor_body_locator.evaluate(
            "(el, html) => { el.focus(); el.innerHTML = html; }", html
        )
        logger.debug("[editor] Set content via body.innerHTML")
        return
    except Exception as e:
        logger.debug(f"[editor] body.innerHTML path failed: {e}")

    # Clipboard paste
    try:
        await page.evaluate("(text) => navigator.clipboard.writeText(text)", html)
        await editor_body_locator.click()
        paste_combo = "Control+V" if sys.platform != "darwin" else "Meta+V"
        await page.keyboard.press(paste_combo)
        logger.debug("[editor] Pasted content via clipboard")
        return
    except Exception as e:
        logger.debug(f"[editor] Clipboard paste failed: {e}")

    # Last resort: fill
    try:
        await editor_body_locator.fill(html)
        logger.debug("[editor] Filled content via locator.fill")
    except Exception as e:
        logger.debug(f"[editor] locator.fill failed: {e}")


# --- Markdown conversion ---


def markdown_to_html(md_text: str, *, img_base_url: Optional[str] = None) -> str:
    try:
        _md = importlib.import_module("markdown")  # type: ignore
        html = _md.markdown(md_text, extensions=["extra"])  # type: ignore[attr-defined]
    except Exception:
        html = markdown_to_html_fallback(md_text)

    if img_base_url:

        def _rewrite_src(match: re.Match) -> str:
            before, src, after = match.group(1), match.group(2), match.group(3)
            if re.match(r"^(data:|https?://|/)", src or ""):
                return f"{before}{src}{after}"
            new_src = f"{img_base_url.rstrip('/')}/{(src or '').lstrip('./')}"
            return f"{before}{new_src}{after}"

        html = re.sub(
            r"(<img\s+[^>]*src=[\"'])(.*?)([\"'])",
            _rewrite_src,
            html,
            flags=re.IGNORECASE,
        )
    return html


def markdown_to_html_fallback(md_text: str) -> str:
    text = md_text
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"^######\s+(.*)$", r"<h6>\1</h6>", text, flags=re.MULTILINE)
    text = re.sub(r"^#####\s+(.*)$", r"<h5>\1</h5>", text, flags=re.MULTILINE)
    text = re.sub(r"^####\s+(.*)$", r"<h4>\1</h4>", text, flags=re.MULTILINE)
    text = re.sub(r"^###\s+(.*)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s+(.*)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
    text = re.sub(r"^#\s+(.*)$", r"<h1>\1</h1>", text, flags=re.MULTILINE)
    text = re.sub(r"!\[(.*?)\]\((.*?)\)", r"<img src='\2' alt='\1' />", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"<a href='\2'>\1</a>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(
        r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text
    )
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return "\n\n".join(f"<p>{p.replace('\n', '<br>')}</p>" for p in paragraphs)
