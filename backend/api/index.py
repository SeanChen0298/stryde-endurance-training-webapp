"""
Vercel entrypoint. vercel.json routes every request here; the FastAPI app
itself lives in main.py one level up.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402,F401
