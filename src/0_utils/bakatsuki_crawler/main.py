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
                    wiki_dir: wiki_exports

Notes:
    - The script avoids re-fetching pages via an in-memory VISITED set.
    - Network errors are caught and reported; failed pages are skipped.
    - Only raw wikitext is stored now (no Pandoc / markdown processing).
"""

from pathlib import Path
import re
import requests

try:  # Optional dependency (PyYAML). Fail fast with clear message if missing.
        import yaml  # type: ignore
except ImportError as _e:  # pragma: no cover
        raise SystemExit("PyYAML is required. Install with: pip install pyyaml") from _e

# ------------------------- Load Configuration -------------------------
_CONFIG_PATH = Path(__file__).parent / "config.yml"
if not _CONFIG_PATH.exists():  # pragma: no cover
        raise SystemExit(f"Missing config file: {_CONFIG_PATH}")

with _CONFIG_PATH.open("r", encoding="utf-8") as _f:
        _RAW_CFG = yaml.safe_load(_f) or {}

API: str = _RAW_CFG.get("api", "https://www.baka-tsuki.org/project/api.php")
ROOT_PAGE: str = _RAW_CFG.get("root_page", "Kyoukai_Senjou_no_Horizon")
WIKI_DIR = Path(_RAW_CFG.get("output", {}).get("wiki_dir", "wiki_exports"))

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


def detect_volume(title: str) -> str:
    """Detect 'Volume_X' or return 'Misc' if not found"""
    match = re.search(r"Volume[_ ]?(\d+[A-Z]?)", title, re.IGNORECASE)
    if match:
        return f"Volume_{match.group(1)}"
    return "Misc"


def sanitize_filename(name: str) -> str:
    """Make a safe filename"""
    return re.sub(r'[\\/*?:"<>|]', "_", name)


def title_to_path(base_dir: Path, title: str, ext: str) -> Path:
    """
    Build output path:
    - Uses volume subfolder
    - Keeps only title (no display name, to avoid long paths)
    """
    volume = detect_volume(title)
    base_name = title.replace(":", "_").replace(" ", "_")
    filename = sanitize_filename(base_name) + ext
    return base_dir.joinpath(volume, filename)


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
    norm_title = normalize_title(title)
    if norm_title in VISITED:
        return
    VISITED.add(norm_title)

    if not title.startswith("Horizon:") and title != ROOT_PAGE:
        return
    if title.lower().startswith("horizon_talk:") or title.lower().startswith("talk:horizon:"):
        return

    print(f"📖 Fetching {title} ...")
    wikitext = fetch_wikitext(title)
    if not wikitext:
        return

    wiki_path = title_to_path(WIKI_DIR, title, ".wiki")
    save_file(wikitext, wiki_path)
    print(f"📄 Saved {wiki_path}")

    for link in extract_links(wikitext):
        process_page(link)


def main():
    # Use root only for discovering volume links (do not save root)
    root_wikitext = fetch_wikitext(ROOT_PAGE)
    if not root_wikitext:
        print("⚠️ Could not fetch root page")
        return

    volume_links = extract_links(root_wikitext)
    volumes = [link for link in volume_links if link.lower().startswith("horizon:volume")]
    print(f"📚 Found {len(volumes)} volumes")

    for vol in volumes:
        process_page(vol)

    print("\n🎉 Done!")
    print(f"Fetched {len(VISITED)} pages in total.")


if __name__ == "__main__":
    main()