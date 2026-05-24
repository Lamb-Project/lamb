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

from plugins.base import (
    ImportResult,
    LibraryImportPlugin,
    PluginParameter,
    PluginRegistry,
)
from plugins.content_handlers.capability import Capability

logger = logging.getLogger(__name__)


@PluginRegistry.register
class YouTubeTranscriptImportPlugin(LibraryImportPlugin):
    """Import YouTube video transcripts as Markdown."""

    name = "youtube_transcript_import"
    description = "Download YouTube transcripts via yt-dlp and convert to Markdown."
    supported_source_types = {"youtube"}
    required_keys: list[str] = []
    # Transcript is written as the full markdown text only.
    produces_capabilities = [Capability.TEXT]
    # YouTube plugin handles URLs only; never matches a local file extension.
    file_extensions: list[str] = []
    human_label = "Import a YouTube video transcript"

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
        # On failure _fetch_transcript raises a RuntimeError with a
        # user-facing reason; we deliberately do NOT swallow it. The
        # worker catches the exception, marks the item as failed, and
        # records the message — instead of producing a "ready" item with
        # a placeholder body that pretends the import succeeded.
        pieces, subtitle_source = _fetch_transcript(video_id, language, proxy_url)
        fetch_duration_ms = int((time.monotonic() - t0) * 1000)

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

    Prefers manual subtitles, falls back to auto-captions. The actual
    transcript file is downloaded via yt-dlp's own HTTP client (with
    cookies / session context), not a bare ``requests.get`` — direct
    fetches of ``/api/timedtext`` URLs are rate-limited by YouTube
    (HTTP 429 with a "Sorry..." HTML page).

    Args:
        video_id: YouTube video ID (11 characters).
        language: ISO 639-1 language code.
        proxy_url: Optional HTTP proxy URL.

    Returns:
        Tuple of (parsed subtitle pieces, subtitle source label).
    """

    import yt_dlp  # noqa: PLC0415

    url = f"https://www.youtube.com/watch?v={video_id}"

    # Probe what subtitle tracks the video actually exposes so we can
    # distinguish "manual" from "auto" in the returned source label.
    probe_opts: dict[str, Any] = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "quiet": True,
        "no_warnings": True,
    }
    if proxy_url:
        probe_opts["proxy"] = proxy_url

    try:
        with yt_dlp.YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        logger.error("yt-dlp failed for %s: %s", video_id, exc)
        raise RuntimeError(f"Failed to fetch video info for {video_id}: {exc}") from exc

    manual = (info or {}).get("subtitles", {}) or {}
    automatic = (info or {}).get("automatic_captions", {}) or {}

    # YouTube doesn't always key subtitle tracks with a plain ISO code:
    # locale-suffixed ("en-US"), region-suffixed ("en-GB"), and
    # translation-chain variants ("en-nP7-2PuUl7o", "de-en-nP7-...") are
    # all common. Resolve the user's requested code to whatever variant
    # the video actually exposes, preferring exact matches.
    manual_key = _resolve_language_key(manual, language)
    auto_key = _resolve_language_key(automatic, language)

    # Order of attempts: manual first (always higher quality), then auto.
    attempts: list[tuple[str, str]] = []
    if manual_key:
        attempts.append((manual_key, "manual"))
    if auto_key:
        attempts.append((auto_key, "auto"))

    if not attempts:
        raise RuntimeError(f"No subtitles available in language '{language}'.")

    # Track whether any attempt was rate-limited so we can give a more
    # actionable message than a generic "download failed".
    hit_rate_limit = False
    for resolved_lang, source_label in attempts:
        try:
            pieces = _download_and_parse(
                url=url,
                language_key=resolved_lang,
                source_label=source_label,
                proxy_url=proxy_url,
            )
        except Exception as exc:
            msg = str(exc)
            if "429" in msg or "Too Many Requests" in msg:
                hit_rate_limit = True
            # Single-line operator detail in the logs; never appended to
            # the user-facing error_message.
            logger.warning(
                "Subtitle download attempt failed (%s, lang=%s): %s",
                source_label,
                resolved_lang,
                msg,
            )
            continue
        if pieces:
            return pieces, source_label

    if hit_rate_limit:
        raise RuntimeError("YouTube rate-limited the subtitle download. Try again later.")
    raise RuntimeError("Could not download subtitles for this video.")


def _resolve_language_key(
    subs_map: dict[str, list[dict[str, Any]]],
    language: str,
) -> str | None:
    """Return the actual key in ``subs_map`` that matches ``language``.

    Exact match wins; otherwise the first key whose part-before-the-first
    ``-`` equals the requested language (handles ``en-US``, ``en-GB``,
    ``en-nP7-2PuUl7o``, etc.).
    """
    if not subs_map:
        return None
    if language in subs_map:
        return language
    for key in subs_map:
        if key.split("-", 1)[0] == language:
            return key
    return None


def _download_and_parse(
    *,
    url: str,
    language_key: str,
    source_label: str,
    proxy_url: str | None,
) -> list[dict[str, Any]]:
    """Use yt-dlp to download the subtitle for ``language_key`` to a temp
    directory, parse it, and return the pieces.

    Asking yt-dlp to actually download routes the fetch through its own
    HTTP client (cookies, retries, proper UA) — which is what avoids the
    HTTP 429 we'd otherwise hit on direct ``timedtext`` URLs.
    """
    import os  # noqa: PLC0415
    import tempfile  # noqa: PLC0415

    import yt_dlp  # noqa: PLC0415

    only_auto = source_label == "auto"
    only_manual = source_label == "manual"

    with tempfile.TemporaryDirectory() as tmp:
        outtmpl = os.path.join(tmp, "%(id)s.%(ext)s")
        opts: dict[str, Any] = {
            "skip_download": True,  # we only want the subtitle, not the video
            "writesubtitles": not only_auto,
            "writeautomaticsub": not only_manual,
            "subtitleslangs": [language_key],
            "subtitlesformat": "srt/best",
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
        }
        if proxy_url:
            opts["proxy"] = proxy_url

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception as exc:
            # Re-raise with the underlying yt-dlp message preserved.
            # The caller will aggregate per-track errors into a single
            # human-readable message for the item's ``error_message``.
            msg = str(exc).strip() or exc.__class__.__name__
            # Trim noise like yt-dlp's "ERROR: " prefix so the bubbled-up
            # message reads cleanly in the UI.
            if msg.startswith("ERROR:"):
                msg = msg[len("ERROR:") :].strip()
            raise RuntimeError(msg) from exc

        # yt-dlp writes <id>.<lang>.srt (or .vtt). Read the first one we
        # find that matches our language_key; fall back to any subtitle
        # file in the temp dir.
        try:
            files = os.listdir(tmp)
        except OSError:
            return []
        sub_files = [f for f in files if f.endswith((".srt", ".vtt"))]
        if not sub_files:
            return []
        # Prefer files containing the language key in the filename.
        preferred = [f for f in sub_files if f".{language_key}." in f]
        chosen = preferred[0] if preferred else sub_files[0]
        path = os.path.join(tmp, chosen)
        try:
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            return []

        # _parse_srt_content already handles SRT and VTT alike (VTT is a
        # superset that lacks the integer index line — the parser falls
        # back gracefully). If your environment proves otherwise, route
        # by file extension here.
        return _parse_srt_content(content)


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
        start = int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3]) / 1000
        end = int(g[4]) * 3600 + int(g[5]) * 60 + int(g[6]) + int(g[7]) / 1000

        # Text is everything after the timestamp line.
        ts_line_idx = next(
            (i for i, ln in enumerate(lines) if _SRT_TIMESTAMP_RE.search(ln)),
            None,
        )
        if ts_line_idx is None:
            continue
        text_lines = lines[ts_line_idx + 1 :]
        raw_text = " ".join(ln.strip() for ln in text_lines if ln.strip())
        cleaned = _NOISE_RE.sub("", raw_text).strip()

        if cleaned:
            pieces.append(
                {
                    "text": cleaned,
                    "start": start,
                    "duration": max(end - start, 0),
                }
            )

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
