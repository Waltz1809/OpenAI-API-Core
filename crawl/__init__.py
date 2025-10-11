"""
Unified Novel Crawler Package
============================

Crawler cho tw.linovelib.com với config JSON và retry mechanism
"""

from .tw_parser import TWLinovelibParser
from .unified_crawler import UnifiedCrawler

__version__ = "1.0.0"
__all__ = ["TWLinovelibParser", "UnifiedCrawler"] 