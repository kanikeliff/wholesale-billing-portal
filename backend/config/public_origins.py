"""Explicit public development URLs, shared with Vite by configuration."""
import os
from urllib.parse import urlsplit


def public_portal_origins():
    origins = []
    for value in os.getenv("PORTAL_PUBLIC_ORIGINS", "").split(","):
        value = value.strip().rstrip("/")
        if not value:
            continue
        parsed = urlsplit(value)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or "*" in parsed.netloc
                or parsed.path or parsed.query or parsed.fragment):
            raise ValueError("PORTAL_PUBLIC_ORIGINS must contain explicit HTTP(S) origins only.")
        origins.append(value)
    return origins
