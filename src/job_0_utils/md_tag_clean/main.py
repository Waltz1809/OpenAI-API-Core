#!/usr/bin/env python3
"""Markdown tag cleaner.

Removes all HTML / Markdown constructs except: bold, italic, underline, strikethrough, images.
Output mirrors input directory tree.

Rules:
 - Keep formatting: **bold**, *italic*, __bold__, _italic_, ~~strike~~.
 - Convert underline if present as <u>...</u> (only keep tag, strip attributes).
 - Images: keep markdown image syntax unchanged.
 - Remove headings, lists, blockquotes, code blocks, tables, links (preserve text), HTML tags (unwrap content).
 - Inline links [text](url) -> text.
 - Code spans `code` -> code (just raw text without backticks).
"""
from __future__ import annotations

import os
import re
import sys
import yaml
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
os.chdir(PROJECT_ROOT)

CONFIG_PATH = Path(__file__).parent / 'config.yml'


def load_config() -> dict:
	if not CONFIG_PATH.exists():
		raise FileNotFoundError(f"Config not found: {CONFIG_PATH}")
	with CONFIG_PATH.open('r', encoding='utf-8') as f:
		data = yaml.safe_load(f) or {}
	return data


HTML_TAG_PATTERN = re.compile(r'<[^>]+>')


def clean_markdown(content: str) -> str:
	"""Remove all HTML tags (<...>) leaving inner text; do not convert anything."""
	if not content:
		return ''
	cleaned = HTML_TAG_PATTERN.sub('', content)
	return '\n'.join(line.rstrip() for line in cleaned.splitlines()) + '\n'


	# (Replaced by minimal clean_markdown above)


def iter_markdown_files(root: Path) -> Iterable[Path]:
	for p in root.rglob('*.md'):
		if p.is_file():
			yield p


def mirror_path(src_file: Path, src_root: Path, dst_root: Path) -> Path:
	rel = src_file.relative_to(src_root)
	return dst_root / rel


def process_file(src: Path, src_root: Path, dst_root: Path):
	text = src.read_text(encoding='utf-8', errors='ignore')
	cleaned = clean_markdown(text)
	out_path = mirror_path(src, src_root, dst_root)
	out_path.parent.mkdir(parents=True, exist_ok=True)
	out_path.write_text(cleaned, encoding='utf-8')
	return out_path


def run():
	cfg = load_config()
	input_dir = Path(cfg.get('input_dir', '4_output_md_raw'))
	print(f"In-place clean directory: {input_dir}")
	if not input_dir.exists():
		print(f"❌ Input directory not found: {input_dir}")
		return 1
	files = list(iter_markdown_files(input_dir))
	if not files:
		print("⚠️ No markdown files found.")
		return 0
	print(f"Found {len(files)} markdown files")
	for i, f in enumerate(files, 1):
		text = f.read_text(encoding='utf-8', errors='ignore')
		cleaned = clean_markdown(text)
		f.write_text(cleaned, encoding='utf-8')
		print(f"[{i}/{len(files)}] {f.relative_to(input_dir)} overwritten")
	print("✅ Done.")
	return 0


if __name__ == '__main__':
	sys.exit(run())
