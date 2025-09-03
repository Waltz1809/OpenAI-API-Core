import os
import sys
import argparse
from pathlib import Path

try:
	import ebooklib
	from ebooklib import epub
	from bs4 import BeautifulSoup
except ImportError:
	epub = None
	BeautifulSoup = None
try:
	import PyPDF2
except ImportError:
	PyPDF2 = None

def txt_to_md(input_path, output_path):
	with open(input_path, 'r', encoding='utf-8') as fin, open(output_path, 'w', encoding='utf-8') as fout:
		fout.write(fin.read())

def epub_to_md(input_path, output_path):
	if epub is None or BeautifulSoup is None:
		print("[ERROR] Please install ebooklib and beautifulsoup4 to convert epub files.")
		return
	book = epub.read_epub(input_path)
	md_content = []
	for item in book.get_items():
		if item.get_type() == ebooklib.ITEM_DOCUMENT:
			soup = BeautifulSoup(item.get_content(), 'html.parser')
			md_content.append(soup.get_text())
	with open(output_path, 'w', encoding='utf-8') as fout:
		fout.write('\n\n'.join(md_content))

def pdf_to_md(input_path, output_path):
	if PyPDF2 is None:
		print("[ERROR] Please install PyPDF2 to convert pdf files.")
		return
	reader = PyPDF2.PdfReader(input_path)
	text = []
	for page in reader.pages:
		text.append(page.extract_text() or "")
	with open(output_path, 'w', encoding='utf-8') as fout:
		fout.write('\n\n'.join(text))

def convert_file(input_file, mode, output_root=None, base_input_dir=None):
	input_file = Path(input_file)
	if output_root:
		if base_input_dir:
			rel_path = input_file.relative_to(base_input_dir)
			output_path = Path(output_root) / rel_path.with_suffix('.md')
			output_path.parent.mkdir(parents=True, exist_ok=True)
		else:
			# If no base_input_dir, put all files flat in output_root
			output_path = Path(output_root) / input_file.name
			output_path = output_path.with_suffix('.md')
			output_path.parent.mkdir(parents=True, exist_ok=True)
	else:
		# If no output_root, default to current working directory, preserving structure if possible
		output_path = Path.cwd() / input_file.name
		output_path = output_path.with_suffix('.md')
		output_path.parent.mkdir(parents=True, exist_ok=True)

	if (mode == 'txt' or mode == 'all') and input_file.suffix.lower() == '.txt':
		txt_to_md(str(input_file), str(output_path))
	elif (mode == 'epub' or mode == 'all') and input_file.suffix.lower() == '.epub':
		epub_to_md(str(input_file), str(output_path))
	elif (mode == 'pdf' or mode == 'all') and input_file.suffix.lower() == '.pdf':
		pdf_to_md(str(input_file), str(output_path))

def scan_files(directory, mode):
	exts = []
	if mode == 'txt':
		exts = ['.txt']
	elif mode == 'epub':
		exts = ['.epub']
	elif mode == 'pdf':
		exts = ['.pdf']
	elif mode == 'all':
		exts = ['.txt', '.epub', '.pdf']
	for root, _, files in os.walk(directory):
		for f in files:
			if Path(f).suffix.lower() in exts:
				yield os.path.join(root, f)

def main():
	parser = argparse.ArgumentParser(description='Convert txt, epub, pdf to markdown (.md)')
	parser.add_argument('-m', '--mode', required=True, choices=['txt', 'epub', 'pdf', 'all'], help='Conversion mode')
	parser.add_argument('-f', '--file', help='Input file to convert')
	parser.add_argument('-d', '--directory', help='Input directory to scan (recursive)')
	parser.add_argument('-o', '--output', help='Output directory (optional, default: same as input)')
	args = parser.parse_args()

	if args.file and args.directory:
		print('Cannot use -f and -d at the same time.')
		sys.exit(1)

	if args.file:
		convert_file(args.file, args.mode, args.output)
		print(f"Converted: {args.file}")
	else:
		if args.directory:
			base_dir = Path(args.directory)
			files = list(scan_files(args.directory, args.mode))
			for f in files:
				convert_file(f, args.mode, args.output, base_input_dir=base_dir)
				print(f"Converted: {f}")
		else:
			cwd = os.getcwd()
			files = [str(Path(cwd) / f) for f in os.listdir(cwd) if Path(f).is_file() and Path(f).suffix.lower() in (['.txt', '.epub', '.pdf'] if args.mode == 'all' else [f'.{args.mode}'])]
			for f in files:
				convert_file(f, args.mode, args.output)
				print(f"Converted: {f}")

if __name__ == '__main__':
	main()
