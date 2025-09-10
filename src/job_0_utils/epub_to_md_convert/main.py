"""Minimal EPUB -> per-section Markdown splitter (TOC based).

Implements user requirements:
	- Based on TOC, create one chapter .md per TOC entry.
	- Each chapter.md includes everything from that entry's anchor position up to (but not including)
		the next TOC entry's anchor (within same underlying XHTML file); if next anchor is in another
		file we slice until file end.

Simplifications:
	- Only TOC (nav.xhtml or NCX) is used. No spine fallback, no combined file, no images, no nav links.
	- If an entry has no fragment (#), slice starts at top of that file.
	- Missing anchor -> warning and skip (can be adjusted to fallback entire file if desired).
	- Output naming: <book_stem>/<zero-padded index>_<slugified-title>.md

Config (config.yml beside this script):
	input_dir: path/to/epubs   (required)
	output_dir: path/to/output (required)
	overwrite: true|false (default true)

Usage:
	python -m job_0_utils.epub_to_md_convert.main

Dependencies:
	pip install ebooklib beautifulsoup4 markdownify pyyaml
"""

from __future__ import annotations

import os
import re
import ebooklib
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Iterable, Tuple
from ebooklib import epub
from bs4 import BeautifulSoup
from markdownify import markdownify as md_convert
import unicodedata
import string

@dataclass
class Settings:
	input_dir: Path
	output_dir: Path
	overwrite: bool = True


@dataclass
class TocEntry:
	index: int
	file: str            # internal file path inside the epub
	fragment: Optional[str]
	title: str


def _find_repo_root(start: Path) -> Path:
	current = start.parent if start.is_file() else start
	for p in [current, *current.parents]:
		if (p / '.git').is_dir():
			return p
	for p in [current, *current.parents]:
		if (p / 'README.md').is_file():
			return p
	return current


def load_settings() -> Settings:
	cfg_path = Path(__file__).parent / 'config.yml'
	if not cfg_path.is_file():
		raise SystemExit(f'Config file not found: {cfg_path}')
	cfg = yaml.safe_load(cfg_path.read_text(encoding='utf-8')) or {}

	repo_root = _find_repo_root(Path(__file__).resolve())
	os.chdir(repo_root)

	in_raw = cfg.get('input_dir')
	out_raw = cfg.get('output_dir')
	if not in_raw:
		raise SystemExit("'input_dir' is required in config.yml")
	if not out_raw:
		raise SystemExit("'output_dir' is required in config.yml")

	inp = Path(str(in_raw))
	input_dir = inp if inp.is_absolute() else (repo_root / inp)
	if not input_dir.is_dir():
		raise SystemExit(f'Input directory not found: {input_dir}')
	outp = Path(str(out_raw))
	output_dir = outp if outp.is_absolute() else (repo_root / outp)
	output_dir.mkdir(parents=True, exist_ok=True)

	overwrite = bool(cfg.get('overwrite', True))
	return Settings(input_dir=input_dir, output_dir=output_dir, overwrite=overwrite)


def iter_epubs(settings: Settings):
	for path in settings.input_dir.rglob('*.epub'):
		if path.is_file():
			yield path


WHITESPACE_RE = re.compile(r"\n{3,}")


def html_to_markdown(html: str) -> str:
	soup = BeautifulSoup(html, 'html.parser')
	for tag in soup(['script','style']):
		tag.decompose()
	md = md_convert(str(soup), heading_style='ATX', strip=['a'])
	md = WHITESPACE_RE.sub('\n\n', md).strip() + '\n'
	return md


def parse_nav(book) -> List[TocEntry]:
	entries: List[TocEntry] = []
	nav_items = list(book.get_items_of_type(ebooklib.ITEM_NAVIGATION))
	if not nav_items:
		return entries
	idx = 1
	for nav in nav_items:
		soup = BeautifulSoup(nav.get_content(), 'html.parser')
		nav_tags = [n for n in soup.find_all('nav') if (n.get('epub:type') and 'toc' in n.get('epub:type'))] or soup.find_all('nav')
		def crawl(list_tag):
			nonlocal idx
			for li in list_tag.find_all('li', recursive=False):
				a = li.find('a', recursive=False)
				if a and a.get('href'):
					href = a['href']
					title = a.get_text(strip=True) or f'Section {idx}'
					if '#' in href:
						file, frag = href.split('#', 1)
					else:
						file, frag = href, None
					entries.append(TocEntry(index=idx, file=file, fragment=frag, title=title))
					idx += 1
				for sub in li.find_all(['ol','ul'], recursive=False):
					crawl(sub)
		for nt in nav_tags:
			for top in nt.find_all(['ol','ul'], recursive=False):
				crawl(top)
	return entries


def parse_ncx(book) -> List[TocEntry]:
	entries: List[TocEntry] = []
	raw = getattr(book, 'toc', [])
	def walk(items):
		for it in items:
			if isinstance(it, tuple) and len(it) == 2 and hasattr(it[0], 'href'):
				link, kids = it
				href = getattr(link, 'href', None)
				title = getattr(link, 'title', None) or f'Section {len(entries)+1}'
				if href:
					if '#' in href:
						file, frag = href.split('#', 1)
					else:
						file, frag = href, None
					entries.append(TocEntry(index=len(entries)+1, file=file, fragment=frag, title=title))
				walk(kids)
			elif hasattr(it, 'href'):
				href = getattr(it, 'href', None)
				title = getattr(it, 'title', None) or f'Section {len(entries)+1}'
				if href:
					if '#' in href:
						file, frag = href.split('#', 1)
					else:
						file, frag = href, None
					entries.append(TocEntry(index=len(entries)+1, file=file, fragment=frag, title=title))
	walk(raw)
	return entries


ANCHOR_PAT_TEMPLATE = r'<[^>]+?(?:id|name)=["\']{frag}["\'][^>]*>'


def group_by_file(entries: Iterable[TocEntry]) -> Dict[str, List[TocEntry]]:
	m: Dict[str, List[TocEntry]] = {}
	for e in entries:
		m.setdefault(e.file, []).append(e)
	for lst in m.values():
		lst.sort(key=lambda x: x.index)
	return m


def extract_sections_from_file(html: str, entries: List[TocEntry]) -> Dict[int, str]:
	if not entries:
		return {}
	positions: List[Tuple[int, TocEntry]] = []
	for e in entries:
		if e.fragment is None:
			positions.append((0, e))
			continue
		pat = ANCHOR_PAT_TEMPLATE.format(frag=re.escape(e.fragment))
		m = re.search(pat, html, flags=re.IGNORECASE)
		if not m:
			print(f"⚠️ Missing anchor '{e.fragment}' in {e.file}; skipping '{e.title}'")
			continue
		positions.append((m.start(), e))
	positions.sort(key=lambda x: x[0])
	out: Dict[int, str] = {}
	for i, (start, entry) in enumerate(positions):
		end = positions[i + 1][0] if i + 1 < len(positions) else None
		slice_html = html[start:end] if end is not None else html[start:]
		out[entry.index] = slice_html
	return out


def _anchor_pos(html: str, fragment: Optional[str]) -> int:
	"""Locate anchor position; if missing or no fragment return 0."""
	if not fragment:
		return 0
	pat = ANCHOR_PAT_TEMPLATE.format(frag=re.escape(fragment))
	m = re.search(pat, html, flags=re.IGNORECASE)
	return m.start() if m else 0


def build_chapters(book) -> List[tuple[TocEntry, str]]:
	"""Slice chapters across spine files until next TOC entry.

	Previous version only captured within a single XHTML file leading to missing
	body text when a chapter spans multiple spine documents (e.g. title page
	separate from content). This implementation gathers all intervening files
	between the current TOC entry and the next.
	"""
	entries = parse_nav(book)
	if not entries:
		entries = parse_ncx(book)
	if not entries:
		print('⚠️ No TOC entries found; skipping book.')
		return []

	# Build spine order (excluding nav) as list of file names
	spine_ids = [idref for (idref, _) in book.spine if idref != 'nav']
	id_to_item = {item.get_id(): item for item in book.get_items() if item.get_type() == ebooklib.ITEM_DOCUMENT}
	spine_files: List[str] = []
	for sid in spine_ids:
		item = id_to_item.get(sid)
		if item:
			spine_files.append(item.file_name)

	if not spine_files:
		print('⚠️ Empty spine; aborting.')
		return []

	file_index: Dict[str, int] = {f: i for i, f in enumerate(spine_files)}

	# Load HTML for files we have
	file_html: Dict[str, str] = {}
	for fn in spine_files:
		item = next((it for it in book.get_items() if it.file_name == fn), None)
		if not item:
			continue
		try:
			file_html[fn] = item.get_content().decode('utf-8', errors='ignore')
		except Exception:
			file_html[fn] = str(item.get_content())

	out: List[tuple[TocEntry, str]] = []
	total = len(entries)
	for i, entry in enumerate(entries):
		if entry.file not in file_index:
			print(f"⚠️ TOC references file not in spine: {entry.file}")
			continue
		start_file_i = file_index[entry.file]
		start_html = file_html.get(entry.file, '')
		start_pos = _anchor_pos(start_html, entry.fragment)

		# Determine end boundaries based on next entry
		if i + 1 < total:
			next_entry = entries[i + 1]
			next_file_i = file_index.get(next_entry.file, len(spine_files) - 1)
			next_html = file_html.get(next_entry.file, '')
			next_pos = _anchor_pos(next_html, next_entry.fragment)
		else:
			next_entry = None
			next_file_i = len(spine_files) - 1
			next_pos = None

		if next_file_i < start_file_i:
			# Degenerate ordering; constrain slice to start file only
			next_file_i = start_file_i
			next_pos = None

		if start_file_i == next_file_i:
			segment_html = start_html[start_pos: next_pos] if next_pos is not None else start_html[start_pos:]
		else:
			parts = []
			# Start file from start_pos to end
			parts.append(start_html[start_pos:])
			# Intermediate full files
			for mid_i in range(start_file_i + 1, next_file_i):
				mid_fn = spine_files[mid_i]
				parts.append(file_html.get(mid_fn, ''))
			# End file up to next_pos (or full)
			end_fn = spine_files[next_file_i]
			end_html = file_html.get(end_fn, '')
			parts.append(end_html[:next_pos] if next_pos is not None else end_html)
			segment_html = ''.join(parts)

		out.append((entry, segment_html))

	out.sort(key=lambda t: t[0].index)
	return out


def slugify(title: str, max_len: int = 60) -> str:
	t = unicodedata.normalize('NFKC', title).strip()
	t = re.sub(r'\s+', '_', t)
	allowed = string.ascii_letters + string.digits + '-_'
	out = ''.join(ch for ch in t if ch in allowed)
	if not out:
		out = 'section'
	return out[:max_len].rstrip('-_') or 'section'


def safe_filename_from_title(title: str, index: int) -> str:
	"""Return a filesystem-safe filename based on the original (possibly unicode) title.

	Differences from slugify:
	  - Preserves unicode (e.g., Japanese) characters.
	  - Strips only characters invalid on Windows: <>:"/\|?* and control chars.
	  - Collapses whitespace to single space then replaces with underscore.
	  - Falls back to 'section_<index>' if result empty.
	"""
	t = unicodedata.normalize('NFKC', title).strip()
	# Remove control chars
	t = ''.join(ch for ch in t if ord(ch) >= 32)
	# Remove invalid filename chars
	t = re.sub(r'[<>:"/\\|?*]', '', t)
	# Normalize whitespace
	t = re.sub(r'\s+', ' ', t)
	if not t:
		t = f'section_{index:03}'
	# Replace spaces with underscore for consistency
	t = t.replace(' ', '_')
	# Limit length
	if len(t) > 120:
		t = t[:120].rstrip('_')
	return t or f'section_{index:03}'


def convert_epub(path: Path, settings: Settings):
	book = epub.read_epub(str(path))
	chapters = build_chapters(book)
	if not chapters:
		return 0, 0
	book_dir = settings.output_dir / path.stem
	book_dir.mkdir(parents=True, exist_ok=True)
	written = 0
	for entry, html in chapters:
		md_body = html_to_markdown(html)
		title = entry.title.replace('\n', ' ').strip()
		md_full = f"## {title}\n\n" + md_body
		# New naming: filename derived purely from section title; ensure uniqueness.
		if 'used_names' not in locals():
			used_names = set()
		base = safe_filename_from_title(title, entry.index)
		fname_candidate = base
		suffix = 2
		while fname_candidate in used_names:
			fname_candidate = f"{base}_{suffix}"
			suffix += 1
		used_names.add(fname_candidate)
		fname = f"{fname_candidate}.md"
		out_path = book_dir / fname
		if out_path.exists() and not settings.overwrite:
			continue
		out_path.write_text(md_full, encoding='utf-8')
		written += 1
		print(f"✅ {path.name}: {title} -> {fname}")
	print(f"📄 {path.name}: wrote {written}/{len(chapters)} sections")
	return written, len(chapters)


def process(settings: Settings):
	total_files = 0
	for epub_path in iter_epubs(settings):
		try:
			convert_epub(epub_path, settings)
			total_files += 1
		except Exception as e:
			print(f"⚠️ Failed {epub_path.name}: {e}")
	print(f"\nDone. Processed {total_files} file(s).")


def main():  # pragma: no cover
	settings = load_settings()
	print(f"➡️ TOC split | Input={settings.input_dir} | Output={settings.output_dir} | Overwrite={settings.overwrite}")
	process(settings)


if __name__ == '__main__':  # pragma: no cover
	main()

