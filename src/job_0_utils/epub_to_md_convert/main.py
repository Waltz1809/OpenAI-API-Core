import os
import yaml
import logging
from pathlib import Path
from ebooklib import epub
import markdownify
from image_uploader import ImgboxUploader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Load config relative to main.py
script_dir = Path(__file__).parent
with open(script_dir / "config.yml", "r") as f:
    config = yaml.safe_load(f)

# Directories relative to cwd
cwd = Path.cwd()
input_dir = cwd / config.get("input_dir", "0_epub")
output_dir = cwd / config.get("output_dir", "1_input_md")
overwrite = config.get("overwrite", True)
split_chapters = config.get("split_chapters", True)
auth_cookie = config.get("auth_cookie", "")

output_dir.mkdir(parents=True, exist_ok=True)

uploader = ImgboxUploader(auth_cookie)

def flatten_toc(toc):
    """Recursively flatten book.toc to a list of titles"""
    flat = []
    for entry in toc:
        if isinstance(entry, (epub.Link, epub.Section)):
            flat.append(entry.title)
            if hasattr(entry, "subitems"):
                flat.extend(flatten_toc(entry.subitems))
        elif isinstance(entry, tuple) and len(entry) > 0:
            flat.extend(flatten_toc(entry))
    return flat

def epub_to_md(epub_file: Path):
    logging.info(f"Processing EPUB: {epub_file}")
    book = epub.read_epub(str(epub_file))

    # Prepare output folder per book
    book_folder = output_dir / epub_file.stem
    book_folder.mkdir(parents=True, exist_ok=True)

    # Flatten TOC titles
    toc_titles = flatten_toc(book.toc)

    # Extract HTML items in order
    html_items = list(book.get_items_of_type(epub.EpubHtml))

    # Handle images
    images = list(book.get_items_of_type(epub.EpubImage))
    img_map = {}
    for image in images:
        tmp_path = book_folder / image.get_name()
        with open(tmp_path, "wb") as f:
            f.write(image.get_content())
        url = uploader.upload_image(tmp_path)
        if url:
            img_map[image.get_name()] = url
        else:
            logging.warning(f"Image {image.get_name()} not uploaded")

    if split_chapters and toc_titles:
        logging.info(f"Splitting {epub_file.name} by TOC titles")
        section_files = []

        num_toc = len(toc_titles)
        num_html = len(html_items)

        # Assign HTML items to TOC sections sequentially
        idx_html = 0
        for i, title in enumerate(toc_titles):
            md_content = ""
            if i < num_toc - 1:
                # Assign one HTML item per TOC entry
                if idx_html < num_html:
                    md_content += html_items[idx_html].get_body_content().decode("utf-8")
                    idx_html += 1
            else:
                # Last TOC entry gets remaining HTML items
                while idx_html < num_html:
                    md_content += html_items[idx_html].get_body_content().decode("utf-8")
                    idx_html += 1

            md_content = markdownify.markdownify(md_content, heading_style="ATX")

            # Replace images
            for img_name, url in img_map.items():
                md_content = md_content.replace(img_name, url)

            safe_title = "".join(c if c.isalnum() else "_" for c in title)
            out_file = book_folder / f"{safe_title}.md"

            if overwrite or not out_file.exists():
                with open(out_file, "w", encoding="utf-8") as f:
                    f.write(md_content)
                logging.info(f"Saved section: {out_file}")

            section_files.append(out_file)

        return section_files
    else:
        # Merge all HTML items
        full_html = "".join(item.get_body_content().decode("utf-8") for item in html_items)
        md_content = markdownify.markdownify(full_html, heading_style="ATX")

        # Replace images
        for img_name, url in img_map.items():
            md_content = md_content.replace(img_name, url)

        out_file = book_folder / f"{epub_file.stem}.md"
        if overwrite or not out_file.exists():
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(md_content)
            logging.info(f"Saved full book: {out_file}")

        return [out_file]

def main():
    for epub_file in input_dir.glob("*.epub"):
        epub_to_md(epub_file)

if __name__ == "__main__":
    main()
