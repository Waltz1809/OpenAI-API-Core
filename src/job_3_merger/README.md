# Job 3 — Merger (YAML → Markdown)

Reverse of splitter: takes YAML segment files and merges them back into Markdown.

What it does
- Recursively scans the configured input directory for .yml/.yaml files
- Reads segments with schema: [{ id, title, content }, ...]
- Sorts segments by Segment_N in id (if present), otherwise keeps file order
- Picks the first non-empty title and uses it for the output filename
- Writes one .md per input YAML, preserving the relative directory structure
- Optionally writes a top-level `## <title>` header in the Markdown

Config
- File: `src/job_3_merger/config.yml`

```
paths:
  input: "file_input"
  output: "file_output/merged_markdown"

processing:
  write_title_header: true
```

Run
- Open a terminal at the project root and run the script with Python.

Notes
- Invalid YAML structure (non-list or missing keys) will be reported and skipped.
- If a filename collision happens in the destination folder, the script appends " (n)".
- Filenames are sanitized to be safe on Windows.
