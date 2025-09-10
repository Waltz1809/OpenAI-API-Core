## Job 4 - Uploader (Simplified Flow)

Current implementation focuses on: 
1. Logging in (manual CAPTCHA) 
2. Discovering volume folders under paths.input 
3. Creating each volume on docln.sbs sequentially 
4. Creating all markdown chapters inside each volume folder (fallback: recursive scan) 

### Config (`config.yml`)
```yaml
credentials:
    username: ""
    password: ""
series:
    novel_id: ""   # required
    # base_url: "https://docln.sbs"   # optional override
    # img_base_url: "https://cdn.example.com"  # optional image base for markdown img src rewrite
paths:
    input: "4_output_md"                 # root containing volume folders
    log: "inventory/logs/uploader"       # optional custom log dir
```

Each subfolder inside `paths.input` is treated as a volume; every `*.md` file inside becomes a chapter. If there are no subfolders but markdown files exist at the root, that root is treated as a single volume.

### Run
```
python -m src.job_4_uploader.main
```

Browser opens, credentials are filled, you solve CAPTCHA and click Login, then press Enter in the terminal (prompt shown). Process logs to console and rotating timestamped log file.

### Markdown Handling
Markdown is converted to HTML (python-markdown if installed, otherwise a lightweight fallback). Relative <img> sources can be rewritten using `series.img_base_url`.

### Selectors Override
Add an optional `selectors:` section in `config.yml` to override any of the default keys used in the editor form.
Defaults (from `core/steps.py`):
```
title: input[name="title"]
editor_iframe: iframe[title="Vùng văn bản phong phú"]
editor_body: #tinymce
submit_button: button.btn.btn-primary
```
Only specify keys you need to change; unspecified ones fall back to defaults.

### Removed Legacy Code
Legacy `sample.py` (older multi-mode prototype) is deprecated and slated for removal.

### Future Ideas
- Resume / skip existing chapters
- Limit number of chapters per volume per run
- Headless mode toggle & debug screenshot dumps
- Parallel volume processing (currently sequential for stability)
