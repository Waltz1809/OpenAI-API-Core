"""Simple crawler for the Baka-Tsuki Horizon project pages.

Purpose:
    - Start from a configured ROOT_PAGE (MediaWiki title) and discover volume links.
    - Recursively fetch only pages whose titles begin with the Horizon namespace rules
        (e.g. Horizon:Volume_*), skipping talk pages.
    - Save raw MediaWiki source (.wiki) into volume-based folders under the configured
        wiki export directory. (Markdown conversion & image handling were removed.)

Configuration:
    - Externalized to a YAML file `config.yml` that lives next to this script.
        Example minimal file:
                api: https://www.baka-tsuki.org/project/api.php
                root_page: Kyoukai_Senjou_no_Horizon
                output:
                    OUTPUT_DIR: wiki_exports

Notes:
    - The script avoids re-fetching pages via an in-memory VISITED set.
    - Network errors are caught and reported; failed pages are skipped.
    - Only raw wikitext is stored now (no Pandoc / markdown processing).
"""

from pathlib import Path
import re
import sys
import requests

try:  # Optional dependency (PyYAML). Fail fast with clear message if missing.
        import yaml  # type: ignore
except ImportError as _e:  # pragma: no cover
        raise SystemExit("PyYAML is required. Install with: pip install pyyaml") from _e

# ------------------------- Load Configuration -------------------------
CWD = Path.cwd()
CONFIG_PATH = Path(__file__).resolve().parent  / "config.yml"
if not CONFIG_PATH.exists():
    print(f"ERROR: config.yml not found next to main.py ({CONFIG_PATH})")
    print("Create config.yml (see example in the script header), then re-run.")
    sys.exit(1)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f) or {}

API: str = config.get("api", "https://www.baka-tsuki.org/project/api.php")
ROOT_PAGE: str = config.get("root_page", "")
if not ROOT_PAGE:  # pragma: no cover
        raise SystemExit("Configuration error: 'root_page' must be specified in config.yml")
PREFIX_FILTER: str | None = config.get("prefix_filter")  # Only crawl titles starting with this (case-sensitive)
OUTPUT_DIR = Path(config.get("output_dir", "."))

VISITED: set[str] = set()
# ---------------------------------------------------------------------


def fetch_wikitext(title: str) -> str | None:
    """Fetch raw .wiki text for a given page title via MediaWiki API"""
    params = {
        "action": "query",
        "prop": "revisions",
        "titles": title,
        "rvslots": "main",
        "rvprop": "content",
        "format": "json",
    }
    try:
        res = requests.get(API, params=params, timeout=15)
        res.raise_for_status()
        data = res.json()
        pages = data["query"]["pages"]

        for _, page_data in pages.items():
            if "revisions" in page_data:
                return page_data["revisions"][0]["slots"]["main"]["*"]
    except Exception as e:
        print(f"⚠️ Error fetching {title}: {e}")
    return None


def _strip_namespace(title: str) -> tuple[str, str]:
    """Return (namespace, remainder). If no namespace, namespace is ''."""
    if ":" in title:
        ns, rest = title.split(":", 1)
        return ns, rest
    return "", title


GROUP_VOLUME_PATTERN = re.compile(r"^(volume_[0-9]+[a-z]?)_", re.IGNORECASE)
GROUP_GENERIC_PATTERN = re.compile(r"^([a-z]+_[0-9]+[a-z]?)_", re.IGNORECASE)


def grouping_folder(full_title: str) -> str:
    """Derive a lower-case grouping folder from the page title (without namespace).

    Rules:
      1. Lower-case and underscore-normalize (spaces -> underscores).
      2. If starts with volume_<n>[letter]_<...> group by volume_<n>[letter].
      3. Else if pattern <word>_<n>[letter]_<...> group by that base (e.g. aname_3).
      4. Else fallback to 'misc'.
    """
    _, core = _strip_namespace(full_title)
    norm = core.replace(" ", "_").lower()
    m = GROUP_VOLUME_PATTERN.match(norm)
    if m:
        return m.group(1)
    m2 = GROUP_GENERIC_PATTERN.match(norm)
    if m2:
        return m2.group(1)
    return "misc"


def sanitize_filename(name: str) -> str:
    """Make a safe filename"""
    return re.sub(r'[\\/*?:"<>|]', "_", name)


# -------- Project root folder (one folder per novel/root page) ---------
# Allow optional manual override via config key 'root_dir_name'. Otherwise derive
# from ROOT_PAGE (lowercased, sanitized).
_root_dir_override = _RAW_CFG.get("output", {}).get("root_dir_name") if _RAW_CFG.get("output") else None
ROOT_DIR_NAME = sanitize_filename((_root_dir_override or ROOT_PAGE).lower())
PROJECT_DIR = OUTPUT_DIR / ROOT_DIR_NAME  # All exports for this root page live here
# -----------------------------------------------------------------------


def title_to_path(base_dir: Path, title: str, ext: str) -> Path:
    """Build output path using grouping folder derived via regex logic inside project folder."""
    group = grouping_folder(title)
    base_name = title.replace(":", "_").replace(" ", "_")
    filename = sanitize_filename(base_name) + ext
    return PROJECT_DIR.joinpath(group, filename)


def save_file(content: str, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def preprocess_wikitext(wikitext: str) -> str:
    """Minimal clean-up (currently passthrough; kept for future tweaks)."""
    return wikitext


def extract_links(wikitext: str) -> list[str]:
    """
    Extract links in format:
      - {{:Page|Display}}
      - [[Page|Display]]
    Only return the page title (ignore display text).
    Exclude File: and Image: references.
    """
    includes = re.findall(r"\{\{:\s*([^|}]+)", wikitext)
    links = re.findall(r"\[\[\s*([^|\]]+)", wikitext)
    return [x.strip() for x in (includes + links) if not (x.lower().startswith("file:") or x.lower().startswith("image:"))]


def normalize_title(title: str) -> str:
    """Normalize title for consistent deduplication"""
    return title.strip().replace(" ", "_")


def process_page(title: str):
    """Fetch and store a page, then recurse through links.

    Modes:
      - Filtered mode (PREFIX_FILTER provided & non-empty): only crawl titles starting with that prefix.
      - Unfiltered mode (no prefix or empty string): crawl every page reachable from the starting seeds.
    """
    norm_title = normalize_title(title)
    if norm_title in VISITED:
        return
    VISITED.add(norm_title)

    if PREFIX_FILTER:  # filtered mode
        if not title.startswith(PREFIX_FILTER):
            return

    print(f"📖 Fetching {title} ...")
    wikitext = fetch_wikitext(title)
    if not wikitext:
        return

    wiki_path = title_to_path(OUTPUT_DIR, title, ".wiki")
    save_file(wikitext, wiki_path)
    print(f"📄 Saved {wiki_path}")

    for link in extract_links(wikitext):
        process_page(link)


 # If desired, could add a listing endpoint to pre-seed all pages matching prefix.


def main():
    # Fetch root page for initial link discovery.
    root_wikitext = fetch_wikitext(ROOT_PAGE)
    if not root_wikitext:
        print("⚠️ Could not fetch root page")
        return

    links = extract_links(root_wikitext)
    if PREFIX_FILTER:
        seeds = [l for l in links if l.startswith(PREFIX_FILTER)]
        print(f"🔎 Prefix mode: {len(seeds)} seed pages matching '{PREFIX_FILTER}' from root")
    else:
        seeds = list(dict.fromkeys(links))  # preserve order, remove dups
        print(f"🌐 Unfiltered mode: {len(seeds)} initial seed pages from root")

    for s in seeds:
        process_page(s)

    print("\n🎉 Done!")
    print(f"Fetched {len(VISITED)} pages in total.")


if __name__ == "__main__":
    main()