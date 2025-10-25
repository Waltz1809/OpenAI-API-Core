#!/usr/bin/env bash
set -e

echo "=== AI Translate Tool Environment Setup ==="

# 1️⃣ Install Python dependencies
echo "[1/3] Installing Python dependencies..."
pip install -r requirements.txt || python -m pip install -r requirements.txt

# 2️⃣ Create necessary folders
echo "[2/3] Creating folders..."
mkdir -p 0_epub 0_wiki_export 1_input_md 2_input_segment 3_output_segment 4_output_md inventory/logs/splitter inventory/logs/translator inventory/logs/uploader inventory/prompts

# 3️⃣ Create secret.yml if it doesn't exist
echo "[3/3] Creating secret.yml..."
if [ ! -f "secret.yml" ]; then
cat > secret.yml <<EOF
gemini_keys:
  - api_key: ""
EOF
    echo "secret.yml created."
else
    echo "secret.yml already exists — skipped."
fi

echo "✅ Setup complete."
