"""MediaWiki (.wiki) -> Markdown converter (minimal config).

config.yml (must sit next to this script) keys:
	api:        <MediaWiki API endpoint>        (required)
	input_dir:  <folder with .wiki files>       (required)
	output_dir: <folder to write .md files>     (required)
	overwrite:  true|false (default: true)      (optional)

Behavior:
	- Recursively converts every *.wiki under input_dir.
	- Resolves relative paths against repo root and chdirs there first.
	- Images are resolved via MediaWiki API and embedded as Markdown image links.
	- If overwrite=false existing .md files are left untouched (reported as EXISTS).

Usage:
	python -m wiki_to_md_convert.main
"""

from __future__ import annotations

import re
import sys
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import requests

try:
	import pypandoc  # type: ignore
except ImportError as e:  # pragma: no cover
	raise SystemExit("pypandoc required. Install with: pip install pypandoc") from e

try:
	import yaml  # type: ignore
except ImportError:  # pragma: no cover
	yaml = None  # Config via YAML becomes unavailable; CLI args still work.


@dataclass
class Settings:
	api: str
	input_dir: Path
	output_dir: Path
	overwrite: bool = True


IMAGE_CACHE: Dict[str, str | None] = {}
_TOKEN_COUNTER = 0


def preprocess_wikitext(wikitext: str) -> str:
	"""Close unpaired bold/italic markers line-by-line for pandoc friendliness."""
	fixed = []
	for line in wikitext.splitlines():
		if line.count("'''") % 2:  # odd bold markers
			line += "'''"
		if line.count("''") % 2:   # odd italic markers
			line += "''"
		fixed.append(line)
	return "\n".join(fixed)


def get_image_url(api: str, filename: str) -> str | None:
	filename = filename.strip()
	key = filename.replace(" ", "_")
	if key in IMAGE_CACHE:
		return IMAGE_CACHE[key]
	params = {
		"action": "query",
		"titles": f"File:{filename}",
		"prop": "imageinfo",
		"iiprop": "url",
		"format": "json",
	}
	try:
		r = requests.get(api, params=params, timeout=15)
		r.raise_for_status()
		data = r.json()
		for _, page in data.get("query", {}).get("pages", {}).items():
			if "imageinfo" in page:
				url = page["imageinfo"][0]["url"]
				IMAGE_CACHE[key] = url
				return url
	except Exception as e:  # pragma: no cover
		print(f"⚠️ Image resolve failed {filename}: {e}")
	IMAGE_CACHE[key] = None
	return None


def _new_token(token_map: Dict[str, Tuple[str, str | None]], url: str, caption: str | None) -> str:
	global _TOKEN_COUNTER
	tok = f"@@IMG_{_TOKEN_COUNTER}@@"
	_TOKEN_COUNTER += 1
	token_map[tok] = (url, caption)
	return tok

import re

# Robust template/ruby/furigana patterns
FURIGANA_TEMPLATE_FULL_RE = re.compile(
    r"(?:<\s*)?\{\{\s*(?:ruby|ふりがな|furigana)\s*\|([^|}]+)(?:\|[^}]*)*\}\}(?:\s*>)?",
    re.IGNORECASE | re.DOTALL,
)

FURIGANA_RUBY_RE = re.compile(
    r"<ruby\s*>(?P<inner>.*?)</ruby\s*>",
    re.IGNORECASE | re.DOTALL,
)

RT_RE = re.compile(r"<rt\s*>.*?</rt\s*>", re.IGNORECASE | re.DOTALL)

ANGLE_AROUND_BOLD_RE = re.compile(r"<\s*\*\*(.+?)\*\*\s*>", re.DOTALL)


def remove_furigana(text: str) -> str:
    """
    Replace furigana/ruby markup with Markdown bold of the base text.

    Examples:
      <{{furigana|Seven-Headed Dragon|Seven Heads}}>  -> **Seven-Headed Dragon**
      {{ruby|computer|コンピュータ}}                   -> **computer**
      東京<ruby>京<rt>きょう</rt></ruby>              -> **東京**
    """

    def _template_sub(m: re.Match) -> str:
        base = (m.group(1) or "").strip()
        return f"**{base}**"

    def _ruby_sub(m: re.Match) -> str:
        inner = m.group("inner") or ""
        # remove all <rt>...</rt> occurrences inside the ruby block
        base_only = RT_RE.sub("", inner).strip()
        return f"**{base_only}**"

    prev = None
    s = text

    # Do a few passes to catch nested / weird placements
    while s != prev:
        prev = s
        # 1) Replace templates (handles with or without surrounding <>)
        s = FURIGANA_TEMPLATE_FULL_RE.sub(_template_sub, s)

        # 2) Replace <ruby>...</ruby> (strip <rt> tags inside)
        s = FURIGANA_RUBY_RE.sub(_ruby_sub, s)

        # 3) Remove any <**...**> wrappers left around our bold tokens
        s = ANGLE_AROUND_BOLD_RE.sub(r"**\1**", s)

        # 4) If upstream processors escaped special chars (e.g. produced \* \< \>),
        #    remove backslashes before these specific chars so Markdown renders correctly.
        s = re.sub(r"\\([<>*])", r"\1", s)

    return s

GALLERY_RE = re.compile(r"<gallery[^>]*>(.*?)</gallery>", re.IGNORECASE | re.DOTALL)
INLINE_IMG_RE = re.compile(r"\[\[(?:File|Image):\s*([^|\]]+?)(?:\|([^\]]*?))?\]\]", re.IGNORECASE)


def replace_images(api: str, wikitext: str) -> tuple[str, Dict[str, Tuple[str, str | None]]]:
	"""Replace gallery and inline image tags with tokens; return (text, token_map)."""
	token_map: Dict[str, Tuple[str, str | None]] = {}

	def _gallery_sub(match: re.Match) -> str:
		body = match.group(1)
		out_tokens: list[str] = []
		for raw_line in body.splitlines():
			ln = raw_line.strip()
			if not ln:
				continue
			m = re.match(r'(?:(?:File|Image):)?\s*([^|]+?)(?:\|(.*))?$', ln, flags=re.IGNORECASE)
			if not m:
				continue
			filename = m.group(1).strip()
			caption = m.group(2).strip() if m.group(2) else None
			url = get_image_url(api, filename)
			if url:
				out_tokens.append(_new_token(token_map, url, caption))
		return "\n\n".join(out_tokens)

	wikitext = GALLERY_RE.sub(_gallery_sub, wikitext)

	def _inline_sub(match: re.Match) -> str:
		filename = match.group(1).strip()
		caption = match.group(2).strip() if match.group(2) else None
		url = get_image_url(api, filename)
		if url:
			return _new_token(token_map, url, caption)
		return match.group(0)

	wikitext = INLINE_IMG_RE.sub(_inline_sub, wikitext)
	return wikitext, token_map

def unescape_markdown(md: str) -> str:
    # Remove backslashes before * < >
    return re.sub(r"\\([*<>])", r"\1", md)

def convert_wiki_to_md(api: str, wikitext: str) -> str:
	wikitext = remove_furigana(wikitext)

	text_with_tokens, token_map = replace_images(api, wikitext)
	processed = preprocess_wikitext(text_with_tokens)
	try:
		md = pypandoc.convert_text(processed, to="gfm", format="mediawiki", extra_args=["--wrap=none"])
	except OSError as e:  # pragma: no cover
		raise SystemExit(f"Pandoc not available: {e}")

	for token, (url, caption) in token_map.items():
		if caption:
			alt = caption.replace("\n", " ").strip()
			rep = f"![{alt}]({url})"
		else:
			rep = f"![]({url})"
		md = md.replace(token, rep)
	
	md = unescape_markdown(md)

	return md


def write_output(md: str, source_path: Path, src_root: Path, out_root: Path, overwrite: bool):
	rel = source_path.relative_to(src_root)
	target = out_root / rel.with_suffix(".md")
	if target.exists() and not overwrite:
		return target  # skip writing
	target.parent.mkdir(parents=True, exist_ok=True)
	target.write_text(md, encoding="utf-8")
	return target


def iter_wiki_files(settings: Settings):
	for path in settings.input_dir.rglob("*.wiki"):
		yield path


def process_directory(settings: Settings) -> int:
	count = 0
	for path in iter_wiki_files(settings):
		try:
			wikitext = path.read_text(encoding="utf-8")
			md = convert_wiki_to_md(settings.api, wikitext)
			out_path = write_output(md, path, settings.input_dir, settings.output_dir, settings.overwrite)
			action = "UPDATED" if settings.overwrite else ("EXISTS" if out_path.exists() else "CREATED")
			print(f"✅ {action}: {path.relative_to(settings.input_dir)} -> {out_path.relative_to(settings.output_dir)}")
			count += 1
		except Exception as e:
			print(f"⚠️ Failed {path}: {e}")
	return count


def load_settings() -> Settings:
	cfg_path = Path(__file__).parent / "config.yml"
	if not cfg_path.is_file():
		raise SystemExit(f"Config file not found: {cfg_path}")
	if yaml is None:
		raise SystemExit("PyYAML not installed; cannot read config.yml")
	cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

	api = cfg.get("api")
	if not api:
		raise SystemExit("Missing required 'api' in config.yml")

	# Find repo root (non-configurable now)  
	def _find_repo_root(start: Path) -> Path:
		current = start.parent if start.is_file() else start
		for p in [current, *current.parents]:
			if (p / '.git').is_dir():
				return p
		# Fallback to README.md if no .git found
		for p in [current, *current.parents]:
			if (p / 'README.md').is_file():
				return p
		return current

	repo_root = _find_repo_root(Path(__file__).resolve())

	input_dir_raw = cfg.get("input_dir")
	if not input_dir_raw:
		raise SystemExit("'input_dir' is required in config.yml")
	# Change working directory to repo root early for simplicity
	os.chdir(repo_root)
	inp_path = Path(str(input_dir_raw))
	input_dir = inp_path if inp_path.is_absolute() else (repo_root / inp_path)
	if not input_dir.is_dir():
		raise SystemExit(f"Input directory not found: {input_dir}")

	output_dir_raw = cfg.get("output_dir")
	if not output_dir_raw:
		raise SystemExit("'output_dir' is required in config.yml")
	out_path = Path(str(output_dir_raw))
	output_dir = out_path if out_path.is_absolute() else (repo_root / out_path)

	overwrite = bool(cfg.get("overwrite", True))

	# Already validated above
	output_dir.mkdir(parents=True, exist_ok=True)

	return Settings(
		api=api,
		input_dir=input_dir,
		output_dir=output_dir,
		overwrite=overwrite,
	)


def main():  # pragma: no cover
	settings = load_settings()
	print(
		"➡️  Converting .wiki -> .md"
		f"\nAPI: {settings.api}"
		f"\nInput: {settings.input_dir}"
		f"\nOutput: {settings.output_dir}"
		f"\nOverwrite: {settings.overwrite}"
	)
	total = process_directory(settings)
	print(f"\n🎉 Converted {total} files.")


if __name__ == "__main__":  # pragma: no cover
	main()
