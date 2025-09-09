#!/usr/bin/env python3
"""
Job 3 - Merger
Reverse of job_1_splitter: merge YAML segments back into Markdown files.

Requirements:
- Merge segments in YAML into a single Markdown file
- Change output file name to the (first non-empty) title
- Preserve input directory tree structure under an output root
- Run independently (no cross-job imports)
"""

import os
import re
import sys
import yaml
import pathlib
from typing import List, Dict, Optional, Tuple


# ----------------------
# Project root utilities
# ----------------------
def find_project_root() -> pathlib.Path:
	"""Locate the project root (three levels up from this file)."""
	return pathlib.Path(__file__).resolve().parent.parent.parent


def _script_dir() -> pathlib.Path:
	return pathlib.Path(__file__).resolve().parent


# ----------------------
# Config
# ----------------------
DEFAULT_CONFIG = {
	'paths': {
		# Input root contains YAML produced by splitter/translator
		'input': 'file_input',
		# Output root where merged Markdown will be written
		'output': 'file_output/merged_markdown',
	},
	'processing': {
		# Prepend a Markdown H2 header with the title at top of file
		'write_title_header': True,
	}
}


def load_config() -> Dict:
	"""Load config.yml (next to this script). Fallback to DEFAULT_CONFIG if missing/empty."""
	cfg_path = _script_dir() / 'config.yml'
	data: Optional[Dict] = None
	if cfg_path.exists():
		try:
			with open(cfg_path, 'r', encoding='utf-8') as f:
				data = yaml.safe_load(f)  # type: ignore
		except Exception:
			data = None
	if not isinstance(data, dict):
		data = {}

	# Deep merge with defaults
	cfg = DEFAULT_CONFIG.copy()
	for k, v in (data or {}).items():
		if isinstance(v, dict) and isinstance(cfg.get(k), dict):
			cfg[k].update(v)
		else:
			cfg[k] = v
	return cfg


# ----------------------
# YAML helpers
# ----------------------
SEGMENT_RE = re.compile(r"Segment_(\d+)")


def _segment_index(segment_id: str) -> int:
	m = SEGMENT_RE.search(segment_id or '')
	return int(m.group(1)) if m else 0


def _sanitize_title_for_filename(title: str) -> str:
	"""Make a safe filename for Windows/macOS/Linux from a title."""
	if not title:
		title = 'Untitled'
	# Remove illegal characters for Windows: <>:"/\|?*
	title = re.sub(r'[<>:"/\\|?*]', ' ', title)
	# Normalize whitespace and dots
	title = re.sub(r"\s+", ' ', title).strip().strip('.')
	# Limit length to something reasonable
	return title[:120] if len(title) > 120 else title


def _read_yaml_segments(path: pathlib.Path) -> List[Dict]:
	with open(path, 'r', encoding='utf-8') as f:
		data = yaml.safe_load(f)
	if not isinstance(data, list):
		raise ValueError(f"YAML must be a list of segments: {path}")
	# Validate minimal schema
	for i, seg in enumerate(data):
		if not isinstance(seg, dict):
			raise ValueError(f"Segment {i} is not an object: {path}")
		for key in ('id', 'title', 'content'):
			if key not in seg:
				raise ValueError(f"Segment {i} missing '{key}': {path}")
	return data


def _compose_markdown(segments: List[Dict], write_title_header: bool) -> Tuple[str, str]:
	"""Return (title, markdown_text)."""
	# Pick first non-empty title across segments
	title = next((s.get('title', '').strip() for s in segments if s.get('title', '').strip()), 'Untitled')

	# Sort by segment index if present; otherwise keep file order
	try:
		segments_sorted = sorted(segments, key=lambda s: _segment_index(str(s.get('id', ''))))
	except Exception:
		segments_sorted = segments

	parts: List[str] = []
	if write_title_header and title:
		parts.append(f"## {title}\n")

	for seg in segments_sorted:
		content = seg.get('content') or ''
		# Ensure str and normalize newlines
		content = str(content).replace('\r\n', '\n').replace('\r', '\n')
		parts.append(content.strip())

	# Join with double newlines between segments
	md = "\n\n".join(p for p in parts if p)
	if not md.endswith("\n"):
		md += "\n"
	return title, md


# ----------------------
# Main flow
# ----------------------
def main():
	project_root = find_project_root()
	cfg = load_config()

	input_root = project_root / cfg['paths']['input']
	output_root = project_root / cfg['paths']['output']

	if not input_root.exists():
		print(f"❌ Input directory not found: {input_root}")
		sys.exit(1)

	yaml_files: List[pathlib.Path] = []
	for ext in ('*.yml', '*.yaml'):
		yaml_files.extend(input_root.rglob(ext))

	if not yaml_files:
		print("⚠️  No YAML files found.")
		return

	print(f"📁 Input root:  {input_root}")
	print(f"📁 Output root: {output_root}")
	print(f"🧾 Files: {len(yaml_files)}")

	write_title_header = bool(cfg.get('processing', {}).get('write_title_header', True))

	processed = 0
	failed = 0

	for ypath in yaml_files:
		try:
			rel_dir = ypath.parent.relative_to(input_root)
			segments = _read_yaml_segments(ypath)
			title, md = _compose_markdown(segments, write_title_header)

			safe_name = _sanitize_title_for_filename(title) + '.md'
			out_dir = output_root / rel_dir
			out_dir.mkdir(parents=True, exist_ok=True)

			out_path = out_dir / safe_name
			# Ensure uniqueness if collision occurs
			if out_path.exists():
				base = out_path.stem
				suffix = out_path.suffix
				i = 1
				while out_path.exists() and i < 1000:
					out_path = out_dir / f"{base} ({i}){suffix}"
					i += 1

			with open(out_path, 'w', encoding='utf-8') as f:
				f.write(md)

			processed += 1
			print(f"✅ {rel_dir.as_posix()}/{ypath.name} → {out_path.relative_to(output_root).as_posix()}")
		except Exception as e:
			failed += 1
			print(f"❌ Failed {ypath}: {e}")

	print("\n📊 Summary")
	print(f"   ✅ Processed: {processed}")
	print(f"   ❌ Failed:    {failed}")


if __name__ == '__main__':
	main()

