import re
import requests
from pathlib import Path
import pypandoc

API = "https://www.baka-tsuki.org/project/api.php"
ROOT_PAGE = "Kyoukai_Senjou_no_Horizon"

WIKI_DIR = Path("wiki_exports")
MD_DIR = Path("markdown_exports")
VISITED = set()


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
    """
    Normalize MediaWiki emphasis so Pandoc parses it correctly.
    Ensures ''italic'' and '''bold''' are properly closed per line.
    """

    fixed_lines = []
    for line in wikitext.splitlines():
        if line.count("''") % 2 != 0:
            line = line + "''"
        if line.count("'''") % 2 != 0:
            line = line + "'''"
        fixed_lines.append(line)

    return "\n".join(fixed_lines)


# ---------------- NEW IMAGE CODE ----------------
def get_image_url(filename: str) -> str | None:
    """Resolve wiki [[Image:...]] filename to full image URL."""
    params = {
        "action": "query",
        "titles": f"File:{filename}",
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json"
    }
    try:
        r = requests.get(API, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        for _, page in pages.items():
            if "imageinfo" in page:
                return page["imageinfo"][0]["url"]
    except Exception as e:
        print(f"⚠️ Error resolving image {filename}: {e}")
    return None


def replace_images(wikitext: str) -> str:
    """Replace [[Image:...]] tags with Markdown ![](url)."""

    def repl(match):
        filename = match.group(1)
        url = get_image_url(filename)
        if url:
            return f"![]({url})"
        return match.group(0)

    return re.sub(r"\[\[Image:(.+?)(?:\|.*?)?\]\]", repl, wikitext)
# ---------------- END NEW CODE ----------------


def convert_to_markdown(wikitext: str, md_file: Path):
    try:
        # NEW: replace image refs before preprocessing
        wikitext = replace_images(wikitext)
        processed = preprocess_wikitext(wikitext)
        markdown = pypandoc.convert_text(
            processed, "gfm", format="mediawiki", extra_args=["--wrap=none"]
        )
        save_file(markdown, md_file)
        print(f"✅ Converted to {md_file}")
    except OSError as e:
        print(f"⚠️ Pandoc not found or failed: {e}")


def extract_links(wikitext: str) -> list[str]:
    """
    Extract links in format:
      - {{:Page|Display}}
      - [[Page|Display]]
    Only return the page title (ignore display text).
    """
    includes = re.findall(r"\{\{:\s*([^|}]+)", wikitext)
    links = re.findall(r"\[\[\s*([^|\]]+)", wikitext)
    return [x.strip() for x in (includes + links) if not x.startswith("File:")]


def process_page(title: str):
    """Fetch, save, convert, and recurse into linked pages"""
    if title in VISITED:
        return
    VISITED.add(title)

    if not title.startswith("Horizon:") and title != ROOT_PAGE:
        return
    if title.lower().startswith("horizon_talk:") or title.lower().startswith("talk:horizon:"):
        return

    print(f"Fetching {title} ...")
    wikitext = fetch_wikitext(title)
    if not wikitext:
        return

    wiki_path = title_to_path(WIKI_DIR, title, ".wiki")
    md_path = title_to_path(MD_DIR, title, ".md")

    save_file(wikitext, wiki_path)
    print(f"📄 Saved {wiki_path}")

    convert_to_markdown(wikitext, md_path)

    for link in extract_links(wikitext):
        process_page(link)


def main():
    process_page(ROOT_PAGE)
    print("\n🎉 Done!")
    print(f"Fetched {len(VISITED)} pages in total.")


if __name__ == "__main__":
    main()