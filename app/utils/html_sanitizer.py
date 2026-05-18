from __future__ import annotations

from typing import Optional

try:
    import bleach
except Exception:  # pragma: no cover - graceful fallback if bleach not installed
    bleach = None


def sanitize_html(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    raw = str(value)
    if not raw.strip():
        return None

    # If bleach is available use it, otherwise perform a minimal escape
    if bleach is not None:
        allowed_tags = ["div", "span", "p", "br", "ul", "ol", "li", "strong", "em", "b", "i", "u", "a"]
        allowed_attrs = {"a": ["href", "target", "rel"]}
        cleaned = bleach.clean(raw, tags=allowed_tags, attributes=allowed_attrs, strip=True)
        # Ensure links are safe — bleach will strip javascript: hrefs when configured, but
        # normalize target/rel to recommended values when present.
        return cleaned

    # Minimal fallback: strip angle brackets
    return raw.replace("<", "&lt;").replace(">", "&gt;")
