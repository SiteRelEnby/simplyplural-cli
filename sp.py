#!/usr/bin/env python3
"""Thin wrapper for running from source. Use 'sp' command after pip install."""
import sys
from pathlib import Path

# Add src/ to path for running without installing
sys.path.insert(0, str(Path(__file__).parent / "src"))

from simplyplural.cli import main
sys.exit(main())
