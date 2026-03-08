"""URL normalization utilities for dedup matching."""

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "fbclid",
    "gclid",
}


def normalize_url(url: str) -> str:
    """Normalize a URL for consistent dedup comparison.

    Applies:
        - Lowercase scheme and host
        - Strip ``www.`` prefix
        - Remove default ports (``:80`` for HTTP, ``:443`` for HTTPS)
        - Remove tracking query params (``utm_*``, ``fbclid``, ``gclid``)
        - Strip trailing slashes (except root ``/``)
        - Drop URL fragments

    Args:
        url: The URL to normalize.

    Returns:
        The normalized URL string.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)

    scheme = parsed.scheme.lower() or "https"
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]

    port = parsed.port
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None
    netloc = f"{host}:{port}" if port else host

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    qs = parse_qs(parsed.query, keep_blank_values=False)
    filtered = {k: v for k, v in qs.items() if k not in TRACKING_PARAMS}
    query = urlencode(filtered, doseq=True)

    return urlunparse((scheme, netloc, path, "", query, ""))
