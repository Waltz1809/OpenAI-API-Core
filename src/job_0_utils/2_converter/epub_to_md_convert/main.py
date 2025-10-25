#!/usr/bin/env python3
"""
main.py - EPUB -> Markdown converter (single file)

Features:
- Parse EPUB (container.xml, OPF, NCX/nav) and split into chapters via TOC (or spine fallback)
- Convert chapter HTML to Markdown (basic conversions + ruby/furigana handling)
- Extract all images and upload them to freeimage.host API using BASE64 payloads (batch upload)
- Replace image placeholders with returned URLs
- Create book output folder in current working directory and write numbered Markdown chapter files

Usage:
- Place config.yml next to this script (same directory)
- Run from the directory you want used as search root (CWD). You may set input_dir in config.yml (relative to CWD).
- Run: python main.py [optional_epub_path1.epub epub2.epub ...]

Dependencies:
pip install beautifulsoup4 markdownify pyyaml requests tqdm
"""
import os
import re
import sys
import time
import zipfile
import shutil
import tempfile
import xml.etree.ElementTree as ET
import base64
from pathlib import Path
from io import BytesIO
from typing import Dict

import yaml
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from tqdm import tqdm

# -------------------------
# Paths & Config
# -------------------------
SCRIPT_DIR = Path(__file__).resolve().parent       # config.yml must sit here
CWD = Path.cwd()                                   # root for searching files (as requested)

CONFIG_PATH = SCRIPT_DIR / "config.yml"
DEFAULT_CONFIG = {
    "api_key": "",
    "output_dir": "output",
    "input_dir": ".",               # relative to CWD; default is CWD (root)
    "batch_size": 5,
    "sleep_between_batches": 1
}

if not CONFIG_PATH.exists():
    print(f"ERROR: config.yml not found next to main.py ({CONFIG_PATH})")
    print("Create config.yml (see example in the script header), then re-run.")
    sys.exit(1)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f) or {}
config = {**DEFAULT_CONFIG, **cfg}

API_KEY = (config.get("api_key") or "").strip()
if not API_KEY:
    print("ERROR: api_key is empty in config.yml. freeimage.host API key required.")
    sys.exit(1)

OUTPUT_BASE = CWD / config.get("output_dir", "output")
INPUT_DIR = (CWD / config.get("input_dir", ".")).resolve()  # search root is CWD; input_dir is relative to CWD
BATCH_SIZE = int(config.get("batch_size", 5))
SLEEP_BETWEEN_BATCHES = float(config.get("sleep_between_batches", 1))

FREEIMAGE_API_URL = "https://cors.moldich.eu.org/?q=https://freeimage.host/api/1/upload"

# -------------------------
# XML helpers
# -------------------------
def parse_xml_bytes(b: bytes):
    try:
        return ET.fromstring(b.decode("utf-8"))
    except Exception:
        return ET.fromstring(b)

def get_text(elem):
    return (elem.text or "").strip()

# -------------------------
# EPUB parsing
# -------------------------
def find_epub_files():
    # look for .epub files under INPUT_DIR (non-recursive)
    if INPUT_DIR.is_file() and INPUT_DIR.suffix.lower() == ".epub":
        return [INPUT_DIR]
    if INPUT_DIR.is_dir():
        return sorted([p for p in INPUT_DIR.glob("*.epub") if p.is_file()])
    return []

def read_zip_bytes(z: zipfile.ZipFile, path: str):
    try:
        return z.read(path)
    except KeyError:
        return None

def find_container_path(z: zipfile.ZipFile):
    try:
        container_raw = read_zip_bytes(z, "META-INF/container.xml")
        if not container_raw:
            return None
        root = parse_xml_bytes(container_raw)
        # try namespace-aware search for rootfile
        for rf in root.findall(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"):
            fp = rf.get("full-path")
            if fp:
                return fp
        # fallback
        rf = root.find(".//rootfile")
        if rf is not None:
            return rf.get("full-path")
    except Exception:
        pass
    return None

def parse_opf(z: zipfile.ZipFile, opf_path: str):
    opf_raw = read_zip_bytes(z, opf_path)
    if not opf_raw:
        raise RuntimeError("OPF file not found at " + opf_path)
    tree = ET.fromstring(opf_raw.decode("utf-8", errors="ignore"))
    manifest = {}
    manifest_id_to_href = {}
    for item in tree.findall(".//{*}manifest/{*}item"):
        iid = item.get("id")
        href = item.get("href")
        mtype = item.get("media-type")
        manifest[iid] = {"href": href, "media-type": mtype}
        if iid:
            manifest_id_to_href[iid] = href
    spine = []
    for it in tree.findall(".//{*}spine/{*}itemref"):
        idref = it.get("idref")
        if idref:
            spine.append(idref)
    ncx_href = None
    for v in manifest.values():
        if v.get("media-type") == "application/x-dtbncx+xml":
            ncx_href = v.get("href")
            break
    spine_elem = tree.find(".//{*}spine")
    if spine_elem is not None and 'toc' in spine_elem.attrib:
        toc_id = spine_elem.attrib.get('toc')
        if toc_id and toc_id in manifest:
            ncx_href = manifest[toc_id]['href']
    base_dir = opf_path.rpartition('/')[0]
    if base_dir:
        base_dir = base_dir + '/'
    else:
        base_dir = ''
    return {
        "manifest": manifest,
        "manifest_id_to_href": manifest_id_to_href,
        "spine": spine,
        "ncx_href": ncx_href,
        "base_dir": base_dir
    }

def parse_ncx(z: zipfile.ZipFile, ncx_path: str):
    raw = read_zip_bytes(z, ncx_path)
    if not raw:
        return []
    root = parse_xml_bytes(raw)
    navpoints = []
    for np in root.findall(".//{*}navPoint"):
        label = np.find(".//{*}navLabel/{*}text")
        content = np.find(".//{*}content")
        title = get_text(label) if label is not None else ""
        src = content.get("src") if content is not None else None
        if src:
            src = src.split('#')[0]
        navpoints.append({"title": title or "", "href": src})
    return navpoints

def build_chapters(z: zipfile.ZipFile, opf_info):
    chapters = []
    base_dir = opf_info["base_dir"]
    if opf_info.get("ncx_href"):
        ncx_path = base_dir + opf_info["ncx_href"]
        navpoints = parse_ncx(z, ncx_path)
        for np in navpoints:
            chapters.append({"title": np['title'] or "Chapter", "href": np['href'], "files": []})
    if not chapters:
        idx = 1
        for idref in opf_info["spine"]:
            href = opf_info["manifest"].get(idref, {}).get("href")
            if href and href.lower().endswith(('.html', '.xhtml', '.htm')):
                chapters.append({"title": f"Chapter {idx}", "href": href, "files": [href]})
                idx += 1
    spine_hrefs = []
    for idref in opf_info["spine"]:
        href = opf_info["manifest"].get(idref, {}).get("href")
        if href:
            spine_hrefs.append(href)
    if chapters and all(len(c.get("files", [])) == 0 for c in chapters):
        current_idx = 0
        for href in spine_hrefs:
            found = False
            for i, ch in enumerate(chapters):
                ch_href = ch.get("href")
                if ch_href and (ch_href.endswith(href) or href.endswith(ch_href)):
                    current_idx = i
                    found = True
                    break
                if ch_href and Path(ch_href).name == Path(href).name:
                    current_idx = i
                    found = True
                    break
            if current_idx < len(chapters):
                chapters[current_idx].setdefault("files", []).append(href)
            else:
                chapters[-1].setdefault("files", []).append(href)
    for ch in chapters:
        if not ch.get("files"):
            if ch.get("href"):
                ch["files"] = [ch["href"]]
            else:
                ch["files"] = []
    return chapters

# -------------------------
# HTML -> Markdown helpers
# -------------------------
def process_ruby(soup: BeautifulSoup):
    for ruby in soup.find_all("ruby"):
        rb = ruby.find("rb")
        rt = ruby.find("rt")
        if rb and rt:
            replacement = f"{rb.get_text(strip=True)}({rt.get_text(strip=True)})"
            ruby.replace_with(replacement)
        else:
            ruby.replace_with(ruby.get_text(" ", strip=True))

def element_text_with_image_tags(elem: BeautifulSoup):
    cloned = BeautifulSoup(str(elem), "html.parser")
    for bad in cloned.find_all(['script', 'style', 'head', 'title']):
        bad.decompose()
    for img in cloned.find_all('img'):
        src = img.get('src') or ""
        filename = Path(src.split('#')[0]).name
        img.replace_with(f'<img src="{filename}"/>')
    text = cloned.get_text(separator=" ", strip=True)
    text = re.sub(r'\s+', ' ', text)
    return text

def html_to_markdown(html_text: str):
    md_text = md(html_text, heading_style="ATX")
    md_text = md_text.strip()
    md_text = re.sub(r'\n{3,}', '\n\n', md_text)
    return md_text

# -------------------------
# Image extraction & base64 upload
# -------------------------
def collect_all_images(z: zipfile.ZipFile):
    image_exts = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg')
    images = {}
    for name in z.namelist():
        if name.lower().endswith(image_exts) and not name.endswith('/'):
            filename = Path(name).name
            try:
                images[filename] = z.read(name)
            except Exception:
                pass
    return images

def extract_image_by_possible_paths(z: zipfile.ZipFile, base_dir: str, image_path: str):
    candidates = []
    image_path_clean = image_path.split('#')[0]
    candidates.append(base_dir + image_path_clean)
    candidates.append(image_path_clean)
    candidates.append(image_path_clean.replace('../', ''))
    candidates.append(image_path_clean.replace('../', base_dir))
    candidates.append('OEBPS/' + image_path_clean)
    candidates.append('images/' + Path(image_path_clean).name)
    candidates.append('Images/' + Path(image_path_clean).name)
    candidates.append(Path(image_path_clean).name)
    seen = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        try:
            data = z.read(c)
            return Path(c).name, data
        except Exception:
            continue
    basename = Path(image_path_clean).name
    for name in z.namelist():
        if Path(name).name == basename:
            try:
                return basename, z.read(name)
            except Exception:
                pass
    return None, None

_EXT_TO_MIME = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.bmp': 'image/bmp',
    '.webp': 'image/webp',
    '.svg': 'image/svg+xml'
}

def guess_mime_for_filename(fname: str):
    ext = Path(fname).suffix.lower()
    return _EXT_TO_MIME.get(ext, 'application/octet-stream')

def upload_image_batch_base64(image_dict: Dict[str, bytes]):
    """
    Upload images to freeimage.host using base64-encoded payloads (without BytesIO).
    The API still expects multipart/form-data with binary data, so we decode the base64 back
    into bytes at send-time to ensure compatibility.
    """
    uploaded = {}
    entries = list(image_dict.items())
    total = len(entries)
    idx = 0
    print(f"[upload] Uploading {total} images in batches of {BATCH_SIZE}...")

    for i in range(0, total, BATCH_SIZE):
        batch = entries[i:i+BATCH_SIZE]
        print(f"[upload] Batch {i // BATCH_SIZE + 1} / {((total - 1) // BATCH_SIZE) + 1}, {len(batch)} images...")
        for filename, bts in batch:
            idx += 1
            try:
                # Encode to base64, then decode back to bytes for upload (no BytesIO)
                b64 = base64.b64encode(bts).decode("ascii")
                data = {
                    'key': API_KEY,
                    'action': 'upload',
                    'format': 'json'
                }
                mime = guess_mime_for_filename(filename)
                # Send binary as a simple tuple (no BytesIO)
                files = {'source': (filename, base64.b64decode(b64), mime)}

                resp = requests.post(FREEIMAGE_API_URL, data=data, files=files, timeout=120)
                if resp.status_code != 200:
                    print(f"  [!] {idx}/{total} {filename} -> HTTP {resp.status_code}, fallback to filename")
                    uploaded[filename] = filename
                    continue

                j = resp.json()
                if isinstance(j, dict) and j.get('status_code') == 200 and j.get('success'):
                    url = (
                        j.get('image', {}).get('url')
                        or j.get('image', {}).get('display_url')
                        or j.get('image', {}).get('url_viewer')
                    )
                    if url:
                        uploaded[filename] = url
                        print(f"  [✓] {idx}/{total} {filename} -> {url}")
                    else:
                        uploaded[filename] = filename
                        print(f"  [~] {idx}/{total} {filename} -> uploaded but no url returned")
                else:
                    uploaded[filename] = filename
                    reason = j.get('status_txt') if isinstance(j, dict) else str(j)
                    print(f"  [✗] {idx}/{total} {filename} -> API error: {reason}")

            except Exception as e:
                uploaded[filename] = filename
                print(f"  [ERROR] {idx}/{total} {filename} -> {e}")

        if i + BATCH_SIZE < total:
            time.sleep(SLEEP_BETWEEN_BATCHES)

    success_count = sum(1 for v in uploaded.values() if v and v != Path(v).name)
    print(f"[upload] Completed. {success_count}/{total} images uploaded with remote URLs.")
    return uploaded

# -------------------------
# Main conversion
# -------------------------
def process_epub(epub_path: Path):
    print(f"\nProcessing EPUB: {epub_path.name}")
    with zipfile.ZipFile(epub_path, 'r') as z:
        opf_path = find_container_path(z)
        if not opf_path:
            raise RuntimeError("container.xml or OPF path not found in EPUB")
        print(f"Found OPF at: {opf_path}")
        opf_info = parse_opf(z, opf_path)
        chapters = build_chapters(z, opf_info)
        book_title = Path(epub_path.stem).name
        try:
            opf_raw = z.read(opf_path).decode('utf-8', errors='ignore')
            root = ET.fromstring(opf_raw)
            title_elt = root.find(".//{*}metadata/{*}title")
            if title_elt is not None and title_elt.text:
                book_title = title_elt.text.strip()
        except Exception:
            pass
        safe_book_title = sanitize_filename(book_title)
        output_folder = OUTPUT_BASE / safe_book_title
        print(f"Output folder: {output_folder}")
        if not output_folder.exists():
            output_folder.mkdir(parents=True, exist_ok=True)
        else:
            print(f"Note: {output_folder} already exists. Files may be overwritten.")
        all_images = collect_all_images(z)
        print(f"Found {len(all_images)} images inside EPUB (quick scan).")
        chapter_data = {}
        images_to_upload = {}  # filename -> bytes
        for ci, ch in enumerate(chapters, start=1):
            title = ch.get("title") or f"Chapter {ci}"
            print(f"Extracting chapter {ci}: {title}")
            chapter_text_parts = []
            chapter_image_names = set()
            for href in ch.get("files", []):
                candidate_paths = []
                if opf_info["base_dir"]:
                    candidate_paths.append(opf_info["base_dir"] + href)
                candidate_paths.append(href)
                html_raw = None
                for p in candidate_paths:
                    try:
                        html_raw = z.read(p).decode('utf-8', errors='ignore')
                        break
                    except Exception:
                        html_raw = None
                if not html_raw:
                    bname = Path(href).name
                    for name in z.namelist():
                        if Path(name).name == bname:
                            try:
                                html_raw = z.read(name).decode('utf-8', errors='ignore')
                                break
                            except Exception:
                                html_raw = None
                if not html_raw:
                    print(f"  [warn] cannot read file for href: {href}")
                    continue
                soup = BeautifulSoup(html_raw, "html.parser")
                process_ruby(soup)
                for img in soup.find_all(['img', 'image']):
                    src = img.get('src') or img.get('xlink:href') or img.get('href') or ''
                    filename = Path(src.split('#')[0]).name or ''
                    if not filename:
                        continue
                    img['src'] = filename
                    if filename not in images_to_upload:
                        if filename in all_images:
                            images_to_upload[filename] = all_images[filename]
                        else:
                            fname, data = extract_image_by_possible_paths(z, opf_info["base_dir"], src)
                            if fname and data:
                                images_to_upload[fname] = data
                                all_images[fname] = data
                    chapter_image_names.add(filename)
                special_ps = soup.select('p[style*="opacity:0.4"], p[style*="opacity: 0.4"]')
                body_text = ""
                if special_ps:
                    for p in special_ps:
                        t = element_text_with_image_tags(p)
                        if t:
                            body_text += t + "\n\n"
                else:
                    all_p = soup.find_all('p')
                    if all_p:
                        for p in all_p:
                            t = element_text_with_image_tags(p)
                            if t:
                                body_text += t + "\n\n"
                    else:
                        body = soup.find('body') or soup
                        t = element_text_with_image_tags(body)
                        if t:
                            body_text += t + "\n\n"
                chapter_text_parts.append(body_text.strip())
            joined = "\n\n".join([p for p in chapter_text_parts if p])
            final_title = ch.get("title") or ""
            chapter_data[title] = {
                "title": title,
                "content": final_title + "\n\n" + (joined.strip() if joined else ""),
                "images": list(chapter_image_names)
            }
        print(f"Collected {len(images_to_upload)} unique images referenced by chapters.")
        uploaded_map = {}
        if images_to_upload:
            uploaded_map = upload_image_batch_base64(images_to_upload)
        else:
            print("[upload] No images to upload.")
        total_ch = len(chapters)
        pad = max(2, len(str(total_ch)))
        chapter_index = 1
        for toc_entry in chapters:
            title = toc_entry.get("title") or f"Chapter {chapter_index}"
            safe_title = sanitize_filename(title)
            filename = f"{str(chapter_index).zfill(pad)}_{safe_title}.md"
            content_obj = chapter_data.get(title) or {"content": title}
            raw_content = content_obj.get("content", title) or title
            md_ready = raw_content
            for fname, url in uploaded_map.items():
                placeholder1 = f'<img src="{fname}"/>'
                placeholder2 = f'<img src="images/{fname}"/>'
                md_ready = md_ready.replace(placeholder1, f"![{Path(fname).stem}]({url})")
                md_ready = md_ready.replace(placeholder2, f"![{Path(fname).stem}]({url})")
                md_ready = re.sub(rf'<img[^>]*src=["\'](?:images/)?{re.escape(fname)}["\'][^>]*>', f'![{Path(fname).stem}]({url})', md_ready)
                md_ready = re.sub(rf'src=["\'](?:images/)?{re.escape(fname)}["\']', f'src="{url}"', md_ready)
            md_text = html_to_markdown(md_ready)
            if not md_text.lstrip().startswith("#"):
                md_text = f"# {title}\n\n{md_text}"
            out_path = output_folder / filename
            with open(out_path, "w", encoding="utf-8") as outf:
                outf.write(md_text)
            print(f"[saved] {out_path}")
            chapter_index += 1
    print(f"Done: output in {output_folder}")

# -------------------------
# Utilities
# -------------------------
def sanitize_filename(name: str):
    s = name.strip()
    s = re.sub(r'[<>:"/\\|?*\n\r\t]', '', s)
    s = re.sub(r'\s+', '_', s)
    if len(s) > 120:
        s = s[:120]
    if not s:
        s = "book"
    return s

# -------------------------
# Entry point
# -------------------------
def main():
    args = sys.argv[1:]
    epubs = []
    if args:
        for a in args:
            p = Path(a)
            if not p.exists():
                print(f"Specified epub not found: {a}")
            else:
                epubs.append(p)
    else:
        epubs = find_epub_files()
    if not epubs:
        print(f"No epub files found in input_dir: {INPUT_DIR}. Place .epub files there or pass as argument.")
        return
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    for epub in epubs:
        try:
            process_epub(epub)
        except Exception as e:
            print(f"[ERROR] processing {epub.name}: {e}")

if __name__ == "__main__":
    main()