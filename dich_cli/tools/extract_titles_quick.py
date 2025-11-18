#!/usr/bin/env python3
"""
Quick Extract Titles - Script nhanh để extract titles từ file YAML
Dùng sau khi dịch xong để có title đã được dịch

Usage: python extract_titles_quick.py <input_yaml_file> [--remove]
"""

import sys
from pathlib import Path

# Add core to path (để TitleExtractor có thể import core modules)
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import trực tiếp vì cùng folder
from extract_titles import TitleExtractor


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_titles_quick.py <input_yaml_file> [--remove]")
        print()
        print("Arguments:")
        print("  input_yaml_file: Path to YAML file (relative to project root)")
        print("  --remove: Xoa title khoi content sau khi extract (optional)")
        print()
        print("Example:")
        print("  python extract_titles_quick.py data/yaml/output/WebNovel/real_game/151125_2048_gmn_real_game_context.yaml")
        print("  python extract_titles_quick.py data/yaml/output/WebNovel/real_game/151125_2048_gmn_real_game_context.yaml --remove")
        sys.exit(1)
    
    input_file = sys.argv[1]
    remove_from_content = '--remove' in sys.argv
    
    print("EXTRACT TITLES TOOL")
    print("=" * 60)
    print(f"Input: {input_file}")
    print(f"Mode: {'Remove from content' if remove_from_content else 'Keep in content'}")
    print("=" * 60)
    
    try:
        extractor = TitleExtractor()
        extractor.extract_titles(
            input_file,
            output_file=None,  # Overwrite input
            remove_from_content=remove_from_content
        )
    except Exception as e:
        print(f"\nLoi: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

