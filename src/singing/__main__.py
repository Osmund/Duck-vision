#!/usr/bin/env python3
"""Start Singing Duck service."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.singing.song_service import main

if __name__ == "__main__":
    main()
