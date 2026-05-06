"""YouTube transcript import plugin using yt-dlp.

Downloads subtitles (preferring manual, falling back to auto-captions),
parses SRT content, and produces a single Markdown document with
timestamped sections.
"""

import logging
import re
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from plugins.base import (
    ImportResult,
    LibraryImportPlugin,
    PluginParameter,
    PluginRegistry,
)

logger = logging.getLogger(__name__)


@PluginRegistry.register
class YouTubeTranscriptImportPlugin(LibraryImportPlugin):
    """Import YouTube video transcripts as Markdown."""

    name = "youtube_transcript_import"
    description = "Download YouTube transcripts via yt-dlp and convert to Markdown."
    supported_source_types = {"youtube"}
    supported_file_types: set[str] = set()  # YouTube plugin works with URLs, not local files
    required_keys: list[str] = []

    def import_content(
        self,
        source_path: str,
        *,
        api_keys: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> ImportResult:
        """Download and parse a YouTube video transcript.

        Args:
            source_path: YouTube video URL.
            api_keys: Not used by this plugin.
            **kwargs: Plugin parameters (``language``, ``proxy_url``).

        Returns:
            ImportResult with the transcript as Markdown.

        Raises:
            ValueError: If the URL is not a valid YouTube link.
            RuntimeError: If transcript download fails.
        """
        url = source_path
        video_id = _parse_youtube_url(url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from URL: {url}")

        language = kwargs.get("language", "en")
        proxy_url = kwargs.get("proxy_url")

        self.report_progress(kwargs, 0, 3, f"Fetching transcript for {video_id}...")

        t0 = time.monotonic()
        pieces, subtitle_source = _fetch_transcript(video_id, language, proxy_url)
        fetch_duration_ms = int((time.monotonic() - t0) * 1000)

        if not pieces:
            return ImportResult(
                full_text=f"*(No transcript available for video {video_id})*",
                metadata={
                    "video_id": video_id,
                    "source_url": url,
                    "language": language,
                    "subtitle_source": "none",
                },
                source_ref=_build_source_ref(url, video_id, language),
            )

        self.report_progress(kwargs, 1, 3, "Building Markdown...")

        md_lines = [f"# Transcript: {url}\n"]
        for piece in pieces:
            ts = _seconds_to_timestamp(piece["start"])
            md_lines.append(f"**[{ts}]** {piece['text']}\n")

        full_text = "\n".join(md_lines)

        self.report_progress(kwargs, 2, 3, "Building metadata...")

        metadata = {
            "video_id": video_id,
            "source_url": url,
            "language": language,
            "subtitle_source": subtitle_source,
            "transcript_pieces": len(pieces),
            "character_count": len(full_text),
            "fetch_duration_ms": fetch_duration_ms,
            "import_plugin": self.name,
        }

        source_ref = _build_source_ref(url, video_id, language)

        self.report_progress(kwargs, 3, 3, "Import complete.")

        return ImportResult(
            full_text=full_text,
            pages=[],
            images=[],
            metadata=metadata,
            source_ref=source_ref,
        )

    def get_parameters(self) -> list[PluginParameter]:
        """Return configurable parameters.

        Returns:
            Parameter descriptors.
        """
        return [
            PluginParameter(
                name="language",
                type="string",
                description="Transcript language (ISO 639-1 code).",
                default="en",
            ),
            PluginParameter(
                name="proxy_url",
                type="string",
                description="Optional HTTP proxy for yt-dlp.",
                advanced=True,
            ),
        ]


# ---------------------------------------------------------------------------
# Transcript fetching
# ---------------------------------------------------------------------------


def _fetch_transcript(
    video_id: str,
    language: str,
    proxy_url: str | None,
) -> tuple[list[dict[str, Any]], str]:
    """Download subtitles for a YouTube video via yt-dlp.

    Prefers manual subtitles, falls back to auto-captions.

    Args:
        video_id: YouTube video ID (11 characters).
        language: ISO 639-1 language code.
        proxy_url: Optional HTTP proxy URL.

    Returns:
        Tuple of (parsed subtitle pieces, subtitle source label).
    """
    import yt_dlp  # noqa: PLC0415

    url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts: dict[str, Any] = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [language],
        "subtitlesformat": "srt",
        "quiet": True,
        "no_warnings": True,
    }
    if proxy_url:
        ydl_opts["proxy"] = proxy_url

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        logger.error("yt-dlp failed for %s: %s", video_id, exc)
        raise RuntimeError(
            f"Failed to fetch video info for {video_id}: {exc}"
        ) from exc

    # Try manual subtitles first, then auto-captions.
    for sub_key, source_label in [
        ("subtitles", "manual"),
        ("automatic_captions", "auto"),
    ]:
        subs = (info or {}).get(sub_key, {})
        lang_subs = subs.get(language, [])
        for sub_entry in lang_subs:
            sub_url = sub_entry.get("url", "")
            if not sub_url:
                continue
            try:
                resp = requests.get(sub_url, timeout=30)
                resp.raise_for_status()
                pieces = _parse_srt_content(resp.text)
                if pieces:
                    return pieces, source_label
            except Exception:
                logger.warning("Failed to fetch subtitle from %s", sub_url[:80])
                continue

    logger.warning("No subtitles found for %s in language '%s'", video_id, language)
    return [], "none"


# ---------------------------------------------------------------------------
# SRT parsing
# ---------------------------------------------------------------------------

_SRT_TIMESTAMP_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*"
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)

_NOISE_RE = re.compile(r"\[.*?\]|\(.*?\)")


def _parse_srt_content(srt_text: str) -> list[dict[str, Any]]:
    """Parse SRT subtitle content into a list of timed text pieces.

    Args:
        srt_text: Raw SRT file content.

    Returns:
        List of dicts with keys ``text``, ``start``, ``duration``.
    """
    pieces: list[dict[str, Any]] = []
    blocks = re.split(r"\n\s*\n", srt_text.strip())

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue

        match = _SRT_TIMESTAMP_RE.search(block)
        if not match:
            continue

        g = match.groups()
        start = (
            int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3]) / 1000
        )
        end = (
            int(g[4]) * 3600 + int(g[5]) * 60 + int(g[6]) + int(g[7]) / 1000
        )

        # Text is everything after the timestamp line.
        ts_line_idx = next(
            (i for i, ln in enumerate(lines) if _SRT_TIMESTAMP_RE.search(ln)),
            None,
        )
        if ts_line_idx is None:
            continue
        text_lines = lines[ts_line_idx + 1:]
        raw_text = " ".join(ln.strip() for ln in text_lines if ln.strip())
        cleaned = _NOISE_RE.sub("", raw_text).strip()

        if cleaned:
            pieces.append({
                "text": cleaned,
                "start": start,
                "duration": max(end - start, 0),
            })

    return pieces


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_youtube_url(url: str) -> str | None:
    """Extract the 11-character video ID from a YouTube URL.

    Args:
        url: YouTube URL in any common format.

    Returns:
        Video ID string, or ``None`` if not parseable.
    """
    parsed = urlparse(url)
    if "youtube.com" in parsed.netloc:
        return parse_qs(parsed.query).get("v", [None])[0]
    if "youtu.be" in parsed.netloc:
        return parsed.path.lstrip("/").split("/")[0] or None
    return None


def _seconds_to_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format.

    Args:
        seconds: Time in seconds.

    Returns:
        Formatted timestamp string.
    """
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _build_source_ref(url: str, video_id: str, language: str) -> dict[str, Any]:
    """Build the source_ref dict for a YouTube import.

    Args:
        url: Original YouTube URL.
        video_id: Extracted video ID.
        language: Transcript language.

    Returns:
        Source reference dictionary.
    """
    return {
        "type": "youtube",
        "source_url": url,
        "video_id": video_id,
        "video_url": f"https://www.youtube.com/watch?v={video_id}",
        "language": language,
    }
