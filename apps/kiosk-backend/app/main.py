"""Backward-compatible entrypoint shim.

Use `app.app:app` as the canonical ASGI target.
`app.main:app` remains available to avoid breaking older scripts.
"""

from app.app import app, create_app  # noqa: F401
