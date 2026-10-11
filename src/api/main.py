"""ASGI entry point.

Run from the repository root:
    uvicorn src.api.main:app --reload
then open http://127.0.0.1:8000 (query interface) or /docs (interactive API docs).
"""
import logging

from src.api.factory import create_app

logging.basicConfig(level=logging.INFO)
app = create_app()
