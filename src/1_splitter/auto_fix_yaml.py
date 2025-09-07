#!/usr/bin/env python3
"""
Auto YAML Raw \n Fixer
Automatically scans all YAML files and fixes raw \n characters by converting to literal block format
"""

import pathlib
import re
import sys

def has_raw_newlines(file_path):
    """Check if a YAML file has raw \n characters in content fields"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Look for content fields that are quoted and contain raw \n
        patterns = [
            r'content:\s*"[^"]*\\n[^"]*"',  # Double quoted with \n
            r"content:\s*'[^']*\\n[^']*'",  # Single quoted with \n
        ]
        
        for pattern in patterns:
            if re.search(pattern, content, re.DOTALL):
                return True
                
        return False
        
    except Exception as e:
        print(f"Error checking {file_path}: {e}")
        return False

def fix_yaml_file(file_path):
    """Fix raw \n characters in a YAML file by converting to literal block format"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern to find content: "..." with \n inside
        def replace_quoted_content(match):
            quoted_content = match.group(1)
            
            # Convert \n to actual newlines and unescape
            try:
                actual_content = quoted_content.encode().decode('unicode_escape')
            except:
                # Fallback for problematic escape sequences
                actual_content = quoted_content.replace('\\n', '\n')
            
            # Format as literal block with proper indentation
            lines = actual_content.split('\n')
            literal_block = 'content: |-\n'
            for line in lines:
                literal_block += '    ' + line + '\n'
            
            return literal_block.rstrip('\n')
        
        # Replace quoted content with literal blocks (double quotes)
        pattern = r'content: "((?:[^"\\]|\\.)*)"'
        new_content = re.sub(pattern, replace_quoted_content, content, flags=re.DOTALL)
        
        # Also handle single quotes
        pattern2 = r"content: '((?:[^'\\]|\\.)*)'"
        new_content = re.sub(pattern2, replace_quoted_content, new_content, flags=re.DOTALL)
        
        # Only write if content changed
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
        
        return False
        
    except Exception as e:
        print(f"  ✗ Error fixing {file_path}: {e}")
        return False

def scan_and_fix_yaml_files(root_dir):
    """Scan all YAML files in directory and fix raw \n issues"""
    print("YAML Raw \\n Auto-Fixer")
    print("=" * 50)
    
    root_path = pathlib.Path(root_dir)
    if not root_path.exists():
        print(f"Directory not found: {root_dir}")
        return 1
    
    # Find all YAML files
    yaml_files = []
    for pattern in ['**/*.yml', '**/*.yaml']:
        yaml_files.extend(root_path.glob(pattern))
    
    print(f"Scanning {len(yaml_files)} YAML files...")
    
    # Check which files need fixing
    files_to_fix = []
    for yaml_file in yaml_files:
        if has_raw_newlines(yaml_file):
            files_to_fix.append(yaml_file)
    
    print(f"Found {len(files_to_fix)} files with raw \\n issues")
    
    if not files_to_fix:
        print("✓ All YAML files are properly formatted!")
        return 0
    
    # Show files that will be fixed
    print("\nFiles to be fixed:")
    for file_path in files_to_fix:
        relative_path = file_path.relative_to(root_path)
        print(f"  - {relative_path}")
    
    # Ask for confirmation
    response = input(f"\nFix {len(files_to_fix)} files? [y/N]: ").strip().lower()
    if response not in ['y', 'yes']:
        print("Operation cancelled.")
        return 0
    
    # Fix the files
    print(f"\nFixing files...")
    fixed = 0
    failed = 0
    
    for file_path in files_to_fix:
        relative_path = file_path.relative_to(root_path)
        print(f"Processing: {relative_path}")
        
        if fix_yaml_file(file_path):
            print(f"  ✓ Fixed")
            fixed += 1
        else:
            print(f"  ⚠️  No changes needed")
    
    print("\n" + "=" * 50)
    print(f"✓ Fixed: {fixed} files")
    if failed > 0:
        print(f"✗ Failed: {failed} files")
    
    return 0 if failed == 0 else 1

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Auto-fix YAML files with raw \\n characters')
    parser.add_argument('--dir', '-d', default='input', 
                       help='Directory to scan (default: input)')
    parser.add_argument('--auto', '-a', action='store_true',
                       help='Auto-fix without confirmation')
    
    args = parser.parse_args()
    
    # Override confirmation if --auto is used
    if args.auto:
        # Monkey patch input function to always return 'y'
        import builtins
        builtins.input = lambda prompt: 'y'
    
    return scan_and_fix_yaml_files(args.dir)

if __name__ == "__main__":
    sys.exit(main())
