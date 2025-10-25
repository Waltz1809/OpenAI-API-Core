#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path
import sys
import textwrap

def main():
    print("=== AI Translate Tool Environment Setup ===")

    # --- 1️⃣ Install dependencies ---
    print("[1/3] Installing Python dependencies...")
    try:
        subprocess.run(["pip", "install", "-r", "requirements.txt"], check=True)
    except subprocess.CalledProcessError:
        print("pip command failed, retrying with python -m pip...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

    # --- 2️⃣ Create necessary folders ---
    print("[2/3] Creating folders...")
    folders = [
        "0_epub",
        "0_wiki_export",
        "1_input_md",
        "2_input_segment",
        "3_output_segment",
        "4_output_md",
        "inventory/logs/splitter",
        "inventory/logs/translator",
        "inventory/logs/uploader",
        "inventory/prompts"
    ]

    for folder in folders:
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        print(f"  ✔ {folder}")

    # --- 3️⃣ Create secrets.yml if missing ---
    print("[3/3] Creating secrets.yml...")
    secret_path = Path("secrets.yml")
    if not secret_path.exists():
        secret_content = textwrap.dedent("""\
            gemini_keys:
              - api_key: ""
        """)
        secret_path.write_text(secret_content, encoding="utf-8")
        print("  ✔ secrets.yml created.")
    else:
        print("  ℹ secrets.yml already exists — skipped.")

    print("\n✅ Setup complete.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Setup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
