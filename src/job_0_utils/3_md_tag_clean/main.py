#!/usr/bin/env python3
"""Markdown tag cleaner.

Removes unwanted HTML / Markdown constructs while preserving basic formatting.
Output mirrors input directory tree (in-place overwrite).

Rules (implemented):
 - Keep formatting: **bold**, *italic*, __bold__, _italic_, ~~strike~~.
 - Underline: preserve <u>...</u> tags (strip attributes).
 - Images: keep `![alt](url)` exactly as-is; always isolate each image as a standalone block.
 - Remove all other HTML tags (unwrap content).
 - Inline links: [text](url) -> text (strip URL), but do NOT touch images.
 - Code spans: `code` -> code (unwrap backticks).
 - Collapse multiple blank lines -> paragraphs separated by exactly 2 newlines.
 - Ensure images are separated by 2 newlines before and after.

Processing order:
  1. normalize <u> tags, remove other HTML,
  2. strip inline links (excluding images),
  3. unwrap code spans,
  4. normalize newlines,
  5. parse each line and isolate images (handles multiple images / inline images),
  6. collapse excessive blank lines.
"""

from __future__ import annotations

import os
import re
import sys
import yaml
from pathlib import Path
from typing import Iterable, List, Tuple

# -------------------------
# Paths & Config
# -------------------------
CWD = Path.cwd()
CONFIG_PATH = Path(__file__).resolve().parent  / "config.yml"
if not CONFIG_PATH.exists():
    print(f"ERROR: config.yml not found next to main.py ({CONFIG_PATH})")
    print("Create config.yml (see example in the script header), then re-run.")
    sys.exit(1)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f) or {}

INPUT_DIR = (CWD / config.get("input_dir", ".")).resolve()
if not INPUT_DIR:
    print("WARNING: INPUT_DIR is empty in config.yml. Using current working directory.")

# Project root & config (kept as you had it)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
os.chdir(PROJECT_ROOT)
CONFIG_PATH = Path(__file__).parent / 'config.yml'


def load_config() -> dict:
    """Load config.yml from current job directory."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config not found: {CONFIG_PATH}")
    with CONFIG_PATH.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    return data


# --- Regex patterns ---
# Keep <u> tags (we'll normalize them), remove all other HTML tags
OPEN_U_RE = re.compile(r'<\s*u\b[^>]*>', flags=re.IGNORECASE)
CLOSE_U_RE = re.compile(r'<\s*/\s*u\s*>', flags=re.IGNORECASE)
OTHER_HTML_RE = re.compile(r'<[^>]+>')

# Inline link pattern - exclude images via negative lookbehind
INLINE_LINK_PATTERN = re.compile(r'(?<!\!)\[([^\]]+)\]\([^)]*\)')

# Code span pattern
CODE_SPAN_PATTERN = re.compile(r'`([^`]+)`')


def _find_markdown_images(line: str) -> List[Tuple[int, int, str]]:
    """
    Find markdown image occurrences in a line robustly.

    Returns list of (start_index, end_index, image_text) for each match.
    This parser:
      - finds '!' followed by '['
      - finds the matching closing ']' (first one after)
      - ensures '(' follows (skipping whitespace)
      - finds the matching ')' by counting parentheses so URLs with parentheses work
    """
    results: List[Tuple[int, int, str]] = []
    n = len(line)
    i = 0
    while i < n:
        idx = line.find('![', i)
        if idx == -1:
            break
        # find closing bracket for alt text
        alt_start = idx + 2
        alt_end = alt_start
        while alt_end < n and line[alt_end] != ']':
            alt_end += 1
        if alt_end >= n:
            # no closing ']' found
            i = idx + 2
            continue
        # find '(' after ']' (allow whitespace)
        j = alt_end + 1
        while j < n and line[j].isspace():
            j += 1
        if j >= n or line[j] != '(':
            i = alt_end + 1
            continue
        # find matching ')', allowing nested parentheses in URL
        paren_count = 0
        k = j
        while k < n:
            if line[k] == '(':
                paren_count += 1
            elif line[k] == ')':
                paren_count -= 1
                if paren_count == 0:
                    break
            k += 1
        if k >= n or line[k] != ')':
            # no closing ')'
            i = alt_end + 1
            continue
        # record image
        img_text = line[idx:k + 1]
        results.append((idx, k, img_text))
        i = k + 1
    return results


def clean_markdown(content: str) -> str:
    """Clean markdown content according to rules and isolate images."""
    if not content:
        return ''

    # 1) Normalize <u> tags: convert any opening <u ...> to plain <u> and close tags to </u>
    text = OPEN_U_RE.sub('<u>', content)
    text = CLOSE_U_RE.sub('</u>', text)

    # 2) Remove other HTML tags (we already normalized <u> above)
    text = OTHER_HTML_RE.sub('', text)

    # 3) Strip inline links (keep only link text), but do not touch image syntax.
    text = INLINE_LINK_PATTERN.sub(r'\1', text)

    # 4) Unwrap inline code spans: `code` -> code
    text = CODE_SPAN_PATTERN.sub(r'\1', text)

    # 5) Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # 6) Process each physical line, locate images and isolate them
    out_lines: List[str] = []
    for raw_line in text.splitlines():
        # preserve exact spacing inside lines when possible, but we'll strip edges
        line = raw_line.rstrip()
        if not line:
            out_lines.append('')  # preserve blank line
            continue

        images = _find_markdown_images(line)
        if not images:
            out_lines.append(line)
            continue

        # if images found, split the line into segments around the images
        last = 0
        for (s, e, img_text) in images:
            pre = line[last:s].strip()
            if pre:
                out_lines.append(pre)
            # ensure a blank line before image
            if out_lines and out_lines[-1] != '':
                out_lines.append('')
            # append image exactly as found (do NOT modify)
            out_lines.append(img_text)
            # blank line after image
            out_lines.append('')
            last = e + 1
        # any trailing text after last image
        tail = line[last:].strip()
        if tail:
            out_lines.append(tail)

    # 7) Collapse runs of 3+ newlines to exactly 2 (paragraph separation)
    text = '\n'.join(out_lines)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 8) Trim trailing spaces at line end, ensure single newline at EOF
    text = '\n'.join(l.rstrip() for l in text.splitlines())
    return text.strip() + '\n'


def iter_markdown_files(root: Path) -> Iterable[Path]:
    """Yield all markdown files under root."""
    for p in root.rglob('*.md'):
        if p.is_file():
            yield p


def mirror_path(src_file: Path, src_root: Path, dst_root: Path) -> Path:
    """Map source file path into destination root with tree mirroring."""
    rel = src_file.relative_to(src_root)
    return dst_root / rel


def process_file(src: Path, src_root: Path, dst_root: Path):
    """Process a single markdown file and save cleaned output in dst_root."""
    text = src.read_text(encoding='utf-8', errors='ignore')
    cleaned = clean_markdown(text)
    out_path = mirror_path(src, src_root, dst_root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(cleaned, encoding='utf-8')
    return out_path


def run() -> int:
    """Run cleaner on configured input directory (in-place)."""

    files = list(iter_markdown_files(INPUT_DIR))
    if not files:
        print("⚠️ No markdown files found.")
        return 0

    print(f"Found {len(files)} markdown files")
    for i, f in enumerate(files, 1):
        text = f.read_text(encoding='utf-8', errors='ignore')
        cleaned = clean_markdown(text)
        f.write_text(cleaned, encoding='utf-8')
        print(f"[{i}/{len(files)}] {f.relative_to(INPUT_DIR)} overwritten")

    print("✅ Done.")
    return 0


if __name__ == '__main__':
    sys.exit(run())