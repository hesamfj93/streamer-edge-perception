"""Entry point for the Windows GUI application.

Run from this directory:
    python run_app.py

Or from anywhere with the absolute path:
    python C:\\path\\to\\windows_app\\run_app.py
"""
import sys
from pathlib import Path

# Make sure the 'app' package is importable regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.main import main

if __name__ == "__main__":
    main()
