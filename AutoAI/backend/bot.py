#!/usr/bin/env python
"""
AutoAI Telegram Bot Launcher
Provides a direct script entry point: `python bot.py`
"""
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from bot.main import main

if __name__ == "__main__":
    main()
