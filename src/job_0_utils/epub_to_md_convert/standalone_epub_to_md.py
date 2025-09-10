from __future__ import annotations

import sys
import re
import time
import ebooklib  # type: ignore
from ebooklib import epub  # type: ignore
from pathlib import Path
from typing import List, Tuple
from bs4 import BeautifulSoup  # type: ignore
from markdownify import markdownify as md_convert  # type: ignore
try:  # required now (no CLI fallback)
    import yaml  # type: ignore
except Exception as e:  # pragma: no cover
    raise SystemExit("PyYAML required for config mode. Install with: pip install pyyaml") from e

SEP = "\n\n---\n\n"

# ---------------- Logging helpers ---------------- #
def _ts() -> str:
    return time.strftime("%H:%M:%S")

def log_info(msg: str):
    print(f"[{_ts()}] ℹ️  {msg}")

def log_ok(msg: str):
    print(f"[{_ts()}] ✅ {msg}")

def log_warn(msg: str):
    print(f"[{_ts()}] ⚠️  {msg}")

def log_err(msg: str):
    print(f"[{_ts()}] ❌ {msg}")


def html_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(['script', 'style']):
        tag.decompose()
    md = md_convert(str(soup), heading_style="ATX", strip=['a'])
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


def convert(epub_path: Path, add_separators: bool = True, debug: bool = False) -> str:
    try:
        book = epub.read_epub(str(epub_path))
    except Exception as e:
        raise SystemExit(f"Failed to read EPUB: {epub_path}\n{e}")
    title = None
    try:
        meta = book.get_metadata('DC', 'title')
        if meta and meta[0] and meta[0][0]:
            title = meta[0][0].strip()
    except Exception:
        if debug:
            print("(debug) Could not extract DC:title metadata")
    spine_ids = [idref for (idref, _) in book.spine if idref != 'nav']
    if debug:
        print(f"(debug) spine ids count: {len(spine_ids)} -> {spine_ids}")
    id_to_item = {it.get_id(): it for it in book.get_items() if it.get_type() == ebooklib.ITEM_DOCUMENT}
    if not spine_ids:
        raise SystemExit("No spine documents found (after filtering 'nav').")
    md_chunks: List[str] = []
    for idx, sid in enumerate(spine_ids, start=1):
        item = id_to_item.get(sid)
        if not item:
            if debug:
                print(f"(debug) Missing item for spine id {sid}")
            continue
        try:
            html = item.get_content().decode('utf-8', errors='ignore')
        except Exception:
            html = str(item.get_content())
        md = html_to_markdown(html)
        if debug:
            print(f"(debug) Converted spine {idx}/{len(spine_ids)} id={sid} chars={len(md)}")
        md_chunks.append(md)
    if not md_chunks:
        raise SystemExit("All spine items empty or unreadable.")
    body = (SEP.join(md_chunks) + "\n") if add_separators else ("\n".join(md_chunks) + "\n")
    header = f"# {title}\n\n" if title else ""
    return header + body


def _find_repo_root(start: Path) -> Path:
    current = start.parent if start.is_file() else start
    for p in [current, *current.parents]:
        if (p / '.git').is_dir():
            return p
    for p in [current, *current.parents]:
        if (p / 'README.md').is_file():
            return p
    return current


def resolve_path(p: Path, repo_root: Path) -> Path:
    if p.is_absolute():
        return p
    return (repo_root / p).resolve()


def load_config(repo_root: Path):
    """Load config.yml next to this script.
    Keys:
      input_dir (required)  : file OR directory
      output_dir (optional) : file if single input file; directory if batch
      separators (bool)     : insert --- between spine docs (default true)
      debug (bool)          : verbose spine logging
    """
    cfg_path = Path(__file__).parent / 'config.yml'
    if not cfg_path.is_file():
        raise SystemExit("Config file not found: " + str(cfg_path))
    raw = yaml.safe_load(cfg_path.read_text(encoding='utf-8')) or {}
    in_raw = raw.get('input_dir') or raw.get('input')
    if not in_raw:
        raise SystemExit("config.yml missing 'input_dir'")
    out_raw = raw.get('output_dir') or raw.get('output')
    separators = bool(raw.get('separators', True))
    debug = bool(raw.get('debug', False))
    inp = resolve_path(Path(str(in_raw)), repo_root)
    if out_raw:
        out = resolve_path(Path(str(out_raw)), repo_root)
    else:
        out = inp.with_suffix('.md') if inp.is_file() else inp
    return inp, out, separators, debug


def _convert_directory(inp_dir: Path, out_dir: Path, add_sep: bool, debug: bool) -> Tuple[int, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    epub_files = sorted(inp_dir.glob('*.epub'))
    if not epub_files:
        log_warn(f"No .epub files in directory: {inp_dir}")
        return 0, 0
    log_info(f"Found {len(epub_files)} EPUB files")
    success = 0
    for i, epub_path in enumerate(epub_files, start=1):
        target = out_dir / (epub_path.stem + '.md')
        log_info(f"[{i}/{len(epub_files)}] {epub_path.name} -> {target.relative_to(out_dir)}")
        try:
            md = convert(epub_path, add_separators=add_sep, debug=debug)
            target.write_text(md, encoding='utf-8')
            log_ok(f"Wrote {target.name} ({len(md)} chars)")
            success += 1
        except Exception as e:
            log_err(f"Failed {epub_path.name}: {e}")
    return len(epub_files), success


def main() -> int:  # pragma: no cover
    repo_root = _find_repo_root(Path(__file__).resolve())
    inp, out, add_sep, debug = load_config(repo_root)
    mode = 'file' if inp.is_file() else 'directory'
    log_info(f"Repo root: {repo_root}")
    log_info(f"Mode: {mode}")
    log_info(f"Input: {inp}")
    log_info(f"Output: {out}")
    log_info(f"Separators: {add_sep} | Debug: {debug}")
    start = time.time()
    if inp.is_dir():
        total, success = _convert_directory(inp, out if out.is_dir() else out.parent, add_sep, debug)
        elapsed = time.time() - start
        if total:
            log_info(f"Summary: {success}/{total} succeeded ({elapsed:.2f}s)")
        else:
            log_warn("No EPUB files processed.")
        return 0 if success > 0 else 5
    if not inp.is_file():
        log_err(f"Input EPUB not found: {inp}")
        return 3
    log_info(f"Converting single EPUB: {inp.name}")
    md = convert(inp, add_separators=add_sep, debug=debug)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding='utf-8')
    elapsed = time.time() - start
    log_ok(f"Wrote {out} ({len(md)} chars) in {elapsed:.2f}s")
    return 0


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
