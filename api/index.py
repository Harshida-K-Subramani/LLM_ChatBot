"""
SmartAI - Vercel Serverless Entrypoint
Exports the Flask application instance 'app' for Vercel Python runtime.
"""

import sys
from pathlib import Path

# Ensure application root is in Python module search path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app

# Export for WSGI server
application = app

