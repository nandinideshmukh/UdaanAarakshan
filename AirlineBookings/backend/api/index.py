"""
Vercel entrypoint.

The Python runtime may execute this file from the repo root or from the
backend directory depending on the deployment setup. Add the backend folder to
sys.path before importing the app package so the FastAPI app can be resolved
reliably in Vercel serverless functions.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402

# Vercel's Python runtime detects the ASGI `app` object below.
# Expose it as `handler` too for compatibility with some serverless setups.
handler = app
