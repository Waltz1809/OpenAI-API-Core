OpenAI-API-Core/
├─ .gitignore
├─ README.md
├─ secrets.yml
├─ input/ …
├─ output/ …
└─ src/
   ├─ 0_utils/
   │  ├─ README.md
   │  ├─ bakatsuki_crawler/
   │  │  ├─ config.yml
   │  │  └─ main.py
   │  └─ wiki_to_md_convert/
   │     ├─ config.yml
   │     └─ main.py
   ├─ 1_splitter/
   │  ├─ README.md
   │  ├─ config.yml
   │  ├─ main.py
   │  ├─ main_old.py
   │  ├─ clean_cache.py
   │  └─ core/
   │     ├─ __init__.py
   │     ├─ cache_manager.py
   │     ├─ config.py
   │     ├─ file_manager.py
   │     ├─ logging.py
   │     └─ text_processor.py
   ├─ 2_translator/
   │  ├─ README.md
   │  ├─ config.yml
   │  ├─ main.py
   │  ├─ batch_runner.py
   │  ├─ api_client/
   │  │  └─ google_ai.py
   │  └─ core/
   │     ├─ retry.py
   │     ├─ ai_factory.py
   │     ├─ key_rotator.py
   │     ├─ logger.py
   │     └─ yaml_processor.py
   ├─ 4_analyzer/
   │  ├─ README.md
   │  ├─ config.yml
   │  └─ main.py
   └─ inventory/
      ├─ prompt/
      │  ├─ prompt.txt
      │  ├─ title_prompt.txt
      │  └─ context_prompt.txt
      └─ logs/