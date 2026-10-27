"""Inngang for Vercel (FastAPI zero-config leter etter `app` i app.py). Lokalt: python scripts/serve.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from klatreforhold.api import app  # noqa: E402,F401
