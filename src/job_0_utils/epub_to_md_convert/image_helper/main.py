import requests
import yaml
from pathlib import Path
from typing import List, Union, Dict, Optional
import time
from bs4 import BeautifulSoup
import os
import sys

IMGBOX_HOME_URL = "https://imgbox.com/"
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}


def get_upload_form(session: requests.Session, logger: bool = False):
    r = session.get(IMGBOX_HOME_URL, headers=BROWSER_HEADERS, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"Failed to load Imgbox homepage, status={r.status_code}")
    soup = BeautifulSoup(r.text, "html.parser")
    form = soup.find("form", {"id": "upload-form"})
    if not form:
        raise RuntimeError("Upload form not found on Imgbox page")
    action = form.get("action")
    if action.startswith("/"):
        action = "https://imgbox.com" + action

    hidden = {}
    for inp in form.find_all("input", {"type": "hidden"}):
        if inp.get("name") and inp.get("value") is not None:
            hidden[inp["name"]] = inp["value"]

    if logger:
        print(f"🔗 Discovered upload URL: {action}")
        if hidden:
            print(f"🪪 Hidden fields: {hidden}")
    return action, hidden


def upload_to_imgbox(
    images: List[Union[str, Path]],
    auth_cookie: Optional[str] = None,
    album_title: Optional[str] = None,
    content_type: str = "safe",
    thumbnail_size: str = "350c",
    comments_enabled: bool = True,
    logger: bool = False,
    timeout: float = 30.0,
    delay: float = 0.0,
    batch_size: int = 1,
):
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)

    if auth_cookie:
        session.headers.update({"Cookie": auth_cookie})
        if logger:
            print("🔑 Using authentication cookie")

    upload_url, hidden_fields = get_upload_form(session, logger=logger)

    uploaded: List[Dict] = []
    failures: List[Dict] = []

    def _single_upload(src: str, filename: str):
        data = {
            **hidden_fields,
            "gallery_title": album_title or "",
            "content_type": content_type,
            "thumb_size": thumbnail_size,
            "comments_enabled": "1" if comments_enabled else "0",
        }
        files = None
        if src.startswith("http://") or src.startswith("https://"):
            data["url"] = src
        else:
            try:
                fh = open(src, "rb")
            except FileNotFoundError:
                failures.append({"source": src, "error": "not_found"})
                if logger:
                    print(f"⚠️ File not found: {src}")
                return
            files = {"files[]": (filename, fh)}

        if logger:
            print(f"⬆️ Uploading {src} ...")

        try:
            r = session.post(upload_url, data=data, files=files, timeout=timeout)
        except Exception as exc:
            if logger:
                print(f"❌ Network error ({exc}) {src}")
            if files:
                files["files[]"][1].close()
            failures.append({"source": src, "error": "network"})
            return
        if files:
            files["files[]"][1].close()

        if r.status_code != 200:
            if logger:
                print(f"❌ HTTP {r.status_code} {src}")
            failures.append({"source": src, "error": f"http_{r.status_code}"})
            return

        soup = BeautifulSoup(r.text, "html.parser")
        link = None
        for a in soup.find_all("a", href=True):
            if "imgbox.com" in a["href"]:
                link = a["href"]
                break
        if not link:
            failures.append({"source": src, "error": "no_link"})
            if logger:
                print(f"⚠️ No link parsed for {src}")
        else:
            uploaded.append({"source": src, "url": link})
            if logger:
                print(f"✅ {src} -> {link}")

    for img in images:
        src = str(img)
        filename = Path(src).name
        _single_upload(src, filename)
        if delay > 0:
            time.sleep(delay)

    if logger:
        print(f"\nSummary: success={len(uploaded)} failure={len(failures)} total={len(images)}")
        if failures:
            for f in failures:
                print(f"  - FAIL {f['source']} ({f['error']})")

    return uploaded, failures


def load_config(path: Union[str, Path]) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    if len(sys.argv) > 1:
        config_file = Path(sys.argv[1])
    else:
        config_file = Path(__file__).with_name("config.yml")
        print(f"⚠️ No config path provided, using default: {config_file}")

    if not config_file.is_file():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    config = load_config(config_file)

    results, failures = upload_to_imgbox(
        config.get("input", []),
        auth_cookie=config.get("auth_cookie"),
        album_title=config.get("album_title"),
        content_type=config.get("content_type", "safe"),
        thumbnail_size=config.get("thumbnail_size", "350c"),
        comments_enabled=config.get("comments_enabled", True),
        logger=config.get("logger", False),
        timeout=float(config.get("timeout", 30)),
        delay=float(config.get("delay", 0)),
        batch_size=int(config.get("batch_size", 1)),
    )

    output_file = config.get("output_file", "uploaded.yml")
    payload = {
        "success": results,
        "failures": failures,
        "counts": {
            "success": len(results),
            "failures": len(failures),
            "total": len(config.get("input", [])),
        },
    }
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)

    print(f"\n📄 Upload complete. Success={len(results)} Fail={len(failures)} -> {output_file}")


if __name__ == "__main__":
    main()
