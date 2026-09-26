"""Build citation links from KB server metadata (#420)."""
from urllib.parse import urlsplit


def kb_file_url(kb_server_url: str, value: str) -> str:
    """Return metadata URLs that are already absolute unchanged; prefix relative paths with the KB server.

    The KB server stores `file_url` and related fields as absolute URLs built from its public
    HOME_URL, while older collections may hold server-relative `/static/...` paths.
    """
    if urlsplit(value).scheme in ('http', 'https'):
        return value
    return f"{kb_server_url.rstrip('/')}/{value.lstrip('/')}"
