import requests
import os
import logging

class ImgboxUploader:
    def __init__(self, auth_cookie: str):
        self.session = requests.Session()
        self.session.cookies.set("auth", auth_cookie)
        self.upload_url = "https://imgbox.com/upload/process"
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    
    def upload_image(self, filepath: str):
        filename = os.path.basename(filepath)
        logging.info(f"Uploading image: {filename}")
        try:
            with open(filepath, "rb") as f:
                files = {"file": (filename, f)}
                resp = self.session.post(self.upload_url, files=files)
            resp.raise_for_status()
            data = resp.json()
            # [Inference] Imgbox's response contains the URL in data['links']['original'] in most APIs
            url = data.get("links", {}).get("original")
            if not url:
                logging.error(f"Failed to get URL for {filename}: {data}")
                return None
            logging.info(f"Uploaded: {filename} -> {url}")
            return url
        except Exception as e:
            logging.error(f"Error uploading {filename}: {e}")
            return None
