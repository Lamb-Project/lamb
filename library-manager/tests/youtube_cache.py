"""Cache layer for YouTube subtitle fetches during testing.

On the first test run, the real yt-dlp call is made and the parsed
subtitle pieces are saved to a JSON file. On subsequent runs, the
cached data is returned directly, avoiding YouTube rate limits.

Usage in conftest.py::

    from youtube_cache import install_youtube_cache
    install_youtube_cache()
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).parent / ".yt_cache"
_patched = False


def _cache_path(video_id: str, language: str) -> Path:
    """Return the cache file path for a given video+language combination."""
    _CACHE_DIR.mkdir(exist_ok=True)
    return _CACHE_DIR / f"{video_id}_{language}.json"


def _cached_fetch_transcript(
    video_id: str,
    language: str,
    proxy_url: str | None,
) -> tuple[list[dict[str, Any]], str]:
    """Fetch transcript with file-based caching.

    First call hits YouTube via the real implementation and saves the
    result. Subsequent calls return the cached data.
    """
    cache_file = _cache_path(video_id, language)

    if cache_file.is_file():
        logger.info("YouTube cache hit: %s/%s", video_id, language)
        data = json.loads(cache_file.read_text("utf-8"))
        return data["pieces"], data["source"]

    from plugins.youtube_transcript_import import (  # noqa: PLC0415
        _fetch_transcript as _real_fetch,
    )

    logger.info("YouTube cache miss — fetching live: %s/%s", video_id, language)
    pieces, source = _real_fetch.__wrapped__(video_id, language, proxy_url)

    cache_file.write_text(
        json.dumps({"pieces": pieces, "source": source}, default=str),
        encoding="utf-8",
    )
    return pieces, source


def install_youtube_cache() -> None:
    """Monkey-patch the YouTube plugin to use cached subtitle data.

    Safe to call multiple times — only patches once.
    """
    global _patched
    if _patched:
        return

    from plugins import youtube_transcript_import as yt_mod  # noqa: PLC0415

    original = yt_mod._fetch_transcript
    _cached_fetch_transcript.__wrapped__ = original
    yt_mod._fetch_transcript = _cached_fetch_transcript

    _patched = True
    logger.info("YouTube subtitle cache installed")
