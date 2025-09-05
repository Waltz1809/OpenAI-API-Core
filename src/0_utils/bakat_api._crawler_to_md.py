import re
import requests
from pathlib import Path
import pypandoc

API = "https://www.baka-tsuki.org/project/api.php"
ROOT_PAGE = "Kyoukai_Senjou_no_Horizon"

WIKI_DIR = Path("wiki_exports")
MD_DIR = Path("markdown_exports")
VISITED = set()
IMAGE_CACHE = {}
# token counter
_IMAGE_TOKEN_COUNTER = 0


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


# ---------------- IMAGE & GALLERY HANDLING (NEW) ----------------
def get_image_url(filename: str) -> str | None:
    """Resolve wiki [[File:/Image:...]] filename to full image URL (with cache)."""
    filename = filename.strip()
    # cache key normalized
    key = filename.replace(" ", "_")
    if key in IMAGE_CACHE:
        return IMAGE_CACHE[key]

    params = {
        "action": "query",
        "titles": f"File:{filename}",
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json"
    }
    try:
        r = requests.get(API, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        for _, page in pages.items():
            if "imageinfo" in page:
                url = page["imageinfo"][0]["url"]
                IMAGE_CACHE[key] = url
                return url
    except Exception as e:
        print(f"⚠️ Error resolving image {filename}: {e}")

    IMAGE_CACHE[key] = None
    return None


def _new_image_token(token_map: dict, url: str, caption: str | None) -> str:
    """Create a unique token and register it in token_map."""
    global _IMAGE_TOKEN_COUNTER
    token = f"@@IMG_{_IMAGE_TOKEN_COUNTER}@@"
    _IMAGE_TOKEN_COUNTER += 1
    token_map[token] = (url, caption)
    return token


def replace_images_and_galleries(wikitext: str) -> tuple[str, dict]:
    """
    Replace [[File:...]] / [[Image:...]] and <gallery>...</gallery> with unique tokens.
    Returns (new_wikitext, token_map) where token_map maps token -> (url, caption).
    """
    token_map: dict = {}

    # 1) Handle <gallery>...</gallery> blocks
    gallery_pattern = re.compile(r"<gallery[^>]*>(.*?)</gallery>", re.IGNORECASE | re.DOTALL)

    def _replace_gallery(match):
        content = match.group(1)
        lines = content.splitlines()
        tokens = []
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            # parse "File:Name.jpg|caption" or "Image:Name.jpg|caption" or "Name.jpg|caption"
            m = re.match(r'(?:(?:File|Image):)?\s*([^|]+?)(?:\|(.*))?$', ln, flags=re.IGNORECASE)
            if not m:
                continue
            filename = m.group(1).strip()
            caption = m.group(2).strip() if m.group(2) else None
            url = get_image_url(filename)
            if url:
                token = _new_image_token(token_map, url, caption)
                tokens.append(token)
        # Join tokens with two newlines so each becomes separate block after pandoc
        return "\n\n".join(tokens)

    wikitext = gallery_pattern.sub(_replace_gallery, wikitext)

    # 2) Handle inline [[File:...|...]] or [[Image:...|...]]
    inline_pattern = re.compile(r'\[\[(?:File|Image):\s*([^|\]]+?)(?:\|([^\]]*?))?\]\]', re.IGNORECASE)

    def _replace_inline(match):
        filename = match.group(1).strip()
        caption = match.group(2).strip() if match.group(2) else None
        url = get_image_url(filename)
        if url:
            return _new_image_token(token_map, url, caption)
        return match.group(0)  # keep original if not found

    wikitext = inline_pattern.sub(_replace_inline, wikitext)

    return wikitext, token_map
# ----------------------------------------------------------------


def convert_to_markdown(wikitext: str, md_file: Path):
    try:
        # replace images & galleries with tokens (and collect token map)
        wikitext_with_tokens, token_map = replace_images_and_galleries(wikitext)

        # preprocess wiki (fix unpaired emphasis)
        processed = preprocess_wikitext(wikitext_with_tokens)

        # convert to markdown (Pandoc)
        markdown = pypandoc.convert_text(
            processed, "gfm", format="mediawiki", extra_args=["--wrap=none"]
        )

        # after conversion, replace tokens with real Markdown image tags
        # do caption-aware replacement
        for token, (url, caption) in token_map.items():
            if caption:
                # use caption as alt text; strip pipes/newlines from caption
                safe_caption = caption.replace("\n", " ").strip()
                img_md = f"![{safe_caption}]({url})"
            else:
                img_md = f"![]({url})"
            # replace all occurrences of token (literal)
            markdown = markdown.replace(token, img_md)

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
    md_path = title_to_path(MD_DIR, title, ".md")

    save_file(wikitext, wiki_path)
    print(f"📄 Saved {wiki_path}")

    convert_to_markdown(wikitext, md_path)

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
