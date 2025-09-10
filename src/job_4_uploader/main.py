"""
Job 4 - Uploader
Consistent entry point patterned after other jobs.

Executes the volume creation flow using config.yml only (no CLI args).
Future: add full upload flows (volume/chapter) using config.yml.
"""

import asyncio
import os
import sys
import pathlib
from pathlib import Path
from typing import Dict
import logging
import datetime

import yaml


# ----------------------
# Project root utilities
# ----------------------
def find_project_root() -> pathlib.Path:
    """Locate the project root (three levels up from this file)."""
    return pathlib.Path(__file__).resolve().parent.parent.parent


def _script_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent


# Ensure cwd is project root (align with other jobs)
PROJECT_ROOT = find_project_root()
os.chdir(PROJECT_ROOT)

# Add local core modules to sys.path (no relative imports needed)
sys.path.append(str(_script_dir() / 'core'))

# Local imports
from core.step1_session import start_session_and_login_interactive  # type: ignore
from core.step2_3_series import create_volumes_and_get_book_ids, create_volume_and_get_book_id, discover_volumes  # type: ignore
from core.step4_chapter import create_chapters_for_volume_dir  # type: ignore
from core.browser import close_all  # type: ignore


# ----------------------
# Config
# ----------------------
def load_config() -> Dict:
    """Load config.yml next to this script; return empty dict if missing."""
    cfg_path = _script_dir() / 'config.yml'
    if not cfg_path.exists():
        print(f"⚠️  Config not found: {cfg_path}")
        return {}
    with cfg_path.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {}
    return data


# ----------------------
# Logging
# ----------------------
def setup_logging(name: str = 'uploader', level: str = 'INFO', log_dir_override: str | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    logger.addHandler(ch)

    # File
    try:
        if log_dir_override:
            raw_path = pathlib.Path(log_dir_override)
            log_dir = raw_path if raw_path.is_absolute() else (PROJECT_ROOT / raw_path)
        else:
            log_dir = PROJECT_ROOT / 'inventory' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        fh = logging.FileHandler(log_dir / f'uploader_{ts}.log', encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))
        logger.addHandler(fh)
    except Exception:
        pass
    return logger


# ----------------------
# Path resolving
# ----------------------
def resolve_path_from_repo(path_str: str) -> str:
    """Resolve a possibly-relative path starting from src (father.father of main) then repo root.

    Order of bases:
      1) src directory (two levels up from this file)
      2) repository root (three levels up)
    Returns the first existing path; otherwise returns the original string.
    """
    p = pathlib.Path(path_str)
    if p.is_absolute() and p.exists():
        return str(p)

    bases = [ _script_dir().parent, PROJECT_ROOT ]
    for base in bases:
        candidate = (base / path_str).resolve()
        if candidate.exists():
            return str(candidate)
    return path_str


# ----------------------
# Main async flow
# ----------------------
async def _amain() -> None:
    cfg = load_config()
    # Pre-read config for log path
    paths_section = (cfg.get('paths') or {})
    log_path_cfg = (paths_section.get('log') or '').strip() or None
    logger = setup_logging(log_dir_override=log_path_cfg)
    logger.info('Starting uploader - create volumes flow')

    series = cfg.get('series') or {}
    novel_id = (series.get('novel_id') or '').strip()
    if not novel_id:
        logger.error('Missing series.novel_id in config.yml')
        return
    base_url = (series.get('base_url') or '').strip() or None
    img_base_url = (series.get('img_base_url') or '').strip() or None

    paths = cfg.get('paths') or {}
    input_path_cfg = (paths.get('input') or '').strip()
    input_path = resolve_path_from_repo(input_path_cfg) if input_path_cfg else ''
    if not input_path:
        logger.error('Missing paths.input in config.yml')
        return
    logger.info(f"Input path: {input_path_cfg} -> {input_path}")

    creds = cfg.get('credentials') or {}
    username = creds.get('username') or ''
    password = creds.get('password') or ''
    if not username or not password:
        logger.warning('Credentials missing or incomplete in config.yml')

    # Step 1: open browser and login (manual CAPTCHA -> press Enter)
    p, browser, context, page = await start_session_and_login_interactive(
        username=username,
        password=password,
        headless=False,
        channel='msedge',
        base_url=base_url,
    )

    try:
        # Discover volumes once
        volumes = discover_volumes(input_path)
        if not volumes:
            logger.warning('No volumes discovered.')
            return
        logger.info(f"Discovered {len(volumes)} volume(s)")

        selectors = (cfg.get('selectors') or None)

        # Sequential flow per volume: create volume -> upload chapters for that volume
        for v in volumes:
            vname = v['name']
            vpath = v['path']
            logger.info(f"=== Volume: {vname} ===")
            # Step 2-3: create this volume, get book_id
            bid = await create_volume_and_get_book_id(
                page,
                novel_id=novel_id,
                volume_name=vname,
                base_url=base_url,
            )
            if not bid:
                logger.error(f"Failed to create volume '{vname}', skipping its chapters")
                continue

            # Step 4-5: create all chapters in this volume
            results = await create_chapters_for_volume_dir(
                page,
                novel_id=novel_id,
                book_id=bid,
                volume_dir=vpath,
                base_url=base_url,
                selectors=selectors,
                img_base_url=img_base_url,
            )
            total = len(results)
            ok = sum(1 for v in results.values() if v)
            fail = total - ok
            logger.info(f"Volume '{vname}' done: total={total}, ok={ok}, fail={fail}")
        await asyncio.sleep(1)
    except Exception as e:
        logger.exception(f'Unhandled error: {e}')
    finally:
        logger.info('Closing browser...')
        await close_all(p, browser, context)


def main() -> None:
    try:
        asyncio.run(_amain())
    except KeyboardInterrupt:
        print('\n⏹️  Stopped.')


if __name__ == '__main__':
    main()
