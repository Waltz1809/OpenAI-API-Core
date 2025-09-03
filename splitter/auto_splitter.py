#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal Auto Splitter with Tracking + Smart Naming
Single mode: always split into segments.
Suffix removed from output naming.
"""

import os
import json
import fnmatch
import hashlib
from pathlib import Path
from datetime import datetime

from enhanced_chapter_splitter import split_and_output


class AutoSplitter:
    def __init__(self, config_file=None):
        script_dir = Path(__file__).resolve().parent
        self.config_file = Path(config_file) if config_file else script_dir / "config.json"

        self.config = self.load_config()
        self.tracking_file = script_dir / self.config["tracking_file"]
        self.tracking = self.load_tracking()

    # -----------------
    # Config + Tracking
    # -----------------
    def load_config(self):
        with open(self.config_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_tracking(self):
        if self.tracking_file.exists():
            try:
                with open(self.tracking_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_tracking(self):
        with open(self.tracking_file, "w", encoding="utf-8") as f:
            json.dump(self.tracking, f, indent=2, ensure_ascii=False)

    def file_hash(self, path: Path):
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        return h.hexdigest()

    # -----------------
    # File Scanning
    # -----------------
    def scan_files(self):
        base_dir = Path(self.config["input_base_dir"])
        patterns = self.config["filters"]["file_patterns"]
        exclude_dirs = set(self.config["filters"]["exclude_folders"])
        exclude_files = set(self.config["filters"]["exclude_files"])
        min_size = self.config["filters"]["min_file_size_bytes"]

        files = []
        for root, dirs, filenames in os.walk(base_dir):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for name in filenames:
                if any(fnmatch.fnmatch(name, p) for p in patterns):
                    path = Path(root) / name
                    if name not in exclude_files and path.stat().st_size >= min_size:
                        files.append(path)
        return files

    # -----------------
    # Smart Naming
    # -----------------
    def smart_name(self, folder: str, filename: str):
        stem = Path(filename).stem
        folder_name = os.path.basename(folder) if folder else ""
        if folder_name and not stem.lower().startswith(folder_name.lower()):
            return f"{folder_name}_{stem}"
        return stem

    # -----------------
    # Main Processing
    # -----------------
    def process_file(self, file: Path):
        settings = self.config["split_settings"]
        if not settings.get("enabled", True):
            return []

        rel_path = str(file.relative_to(self.config["input_base_dir"]))
        file_hash = self.file_hash(file)

        tracked = self.tracking.get(rel_path, {})
        if tracked.get("file_hash") == file_hash:
            return [("segment", "skip")]

        # output path
        folder = str(Path(rel_path).parent)
        smart_stem = self.smart_name(folder, file.name)
        out_name = f"{smart_stem}.{self.config['global_settings']['output_format']}"
        out_dir = Path(self.config["output_base_dir"]) / folder
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / out_name

        # split
        split_and_output(
            file_path=str(file),
            max_chars=settings["segment_chars"],
            max_chapter=self.config["global_settings"]["max_chapter"],
            output_path=str(out_path),
            mode=settings["mode"],
            output_format=self.config["global_settings"]["output_format"],
        )

        # update tracking
        self.tracking[rel_path] = {
            "file_hash": file_hash,
            "last_updated": datetime.now().isoformat(),
            "output": str(out_path),
        }

        return [("segment", "done")]

    def run(self):
        files = self.scan_files()
        print(f"📁 {len(files)} files found")
        for f in files:
            print(f"\n📄 {f}")
            results = self.process_file(f)
            for mode, status in results:
                if status == "done":
                    print(f"  ✅ processed")
                else:
                    print(f"  ⏭️ skipped (unchanged)")
        self.save_tracking()
        print("\n🎉 Done!")


def main():
    AutoSplitter().run()


if __name__ == "__main__":
    main()
