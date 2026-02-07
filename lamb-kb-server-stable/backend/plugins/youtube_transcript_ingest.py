"""
YouTube Transcript Ingestion Plugin
==================================

Adaptation of the standalone YouTube ingestion script into the unified
ingestion plugin architecture used by the LAMB Knowledge Base Server.

Features:
 - Accepts a single YouTube URL (plugin param: video_url) or a text file whose
   first non-empty line(s) contain YouTube URLs (one per line)
 - Fetches transcript using yt-dlp for robust subtitle extraction
 - Supports manual subtitle ingestion from uploaded `.srt` / `.vtt` / `.txt`
   subtitle files (useful fallback when YouTube returns 429)
 - Supports manual subtitle ingestion from pasted subtitle text via plugin params
 - Supports both manual and automatic captions from YouTube
 - Chunks transcript pieces by target duration (default 60s)
 - Cleans text and preserves original raw text per piece
 - Returns standard chunk objects with rich metadata for downstream storage

Usage (API Example):
  plugin_name: youtube_transcript_ingest
  plugin_params: {
      "video_url": "https://www.youtube.com/watch?v=XXXXXXXXXXX",
      "language": "en",                 # optional (default: en)
      "chunk_duration": 60,               # seconds, optional
      "proxy_url": "http://proxy:8080",   # optional
      "manual_subtitle_text": "...",      # optional manual subtitle content
      "manual_subtitle_format": "auto"    # optional: auto|srt|vtt|plain
  }

If you upload a small text file containing multiple video URLs (one per line)
you may omit video_url; all listed videos will be ingested sequentially and
their chunks aggregated. (Note: current implementation does sequential fetch.)

If you upload an `.srt`, `.vtt`, or subtitle `.txt` file, subtitles are parsed
directly and YouTube fetching is skipped.

Environment Toggle:
  Set PLUGIN_YOUTUBE_TRANSCRIPT_INGEST=DISABLE to disable auto-registration.
"""

from __future__ import annotations

import re
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Iterable
from datetime import datetime

try:
    import yt_dlp
    _YT_DLP_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    _YT_DLP_AVAILABLE = False

from .base import IngestPlugin, PluginRegistry


def _parse_youtube_url(url: str) -> Optional[str]:
    """Extract a YouTube video ID from a URL.

    Returns None if it cannot be parsed.
    """
    url = url.strip()
    # Already an 11-char id?
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url

    pattern_watch = re.compile(r"(?:v=)([A-Za-z0-9_-]{11})")
    pattern_short = re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})")
    pattern_embed = re.compile(r"embed/([A-Za-z0-9_-]{11})")

    for pattern in (pattern_watch, pattern_short, pattern_embed):
        m = pattern.search(url)
        if m:
            return m.group(1)
    return None


def _seconds_to_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def _clean_text(text: str) -> str:
    """Light normalization & artifact removal."""
    text = re.sub(r"\s+", " ", text.strip())
    text = re.sub(r"\[.*?\]", "", text)  # [Music], [Applause]
    text = re.sub(r"\(.*?\)", "", text)  # (inaudible)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"([.!?])\s*([a-z])", r"\1 \2", text)
    return text.strip()


def _chunk_transcript(pieces: List[Dict[str, Any]], chunk_duration: float) -> List[Dict[str, Any]]:
    """Group transcript pieces into chunks not exceeding target duration."""
    chunks: List[Dict[str, Any]] = []
    current = {"start": 0.0, "end": 0.0,
               "text_parts": [], "original_text_parts": []}

    for p in pieces:
        raw_text = p.get("text", "")
        cleaned = _clean_text(raw_text)
        if not cleaned:
            continue
        if not current["text_parts"]:
            current["start"] = p["start"]
        current["text_parts"].append(cleaned)
        current["original_text_parts"].append(raw_text)
        current["end"] = p["start"] + p.get("duration", 0)

        if current["end"] - current["start"] >= chunk_duration:
            chunks.append(current)
            current = {"start": 0.0, "end": 0.0,
                       "text_parts": [], "original_text_parts": []}

    if current["text_parts"]:
        chunks.append(current)
    return chunks


def _fetch_transcript(video_id: str, languages: Iterable[str], proxy_url: Optional[str]) -> List[Dict[str, Any]]:
    """Fetch raw transcript pieces using yt-dlp."""
    if not _YT_DLP_AVAILABLE:
        raise ImportError(
            'yt-dlp not installed. Install with "pip install yt-dlp".'
        )

    # Configure yt-dlp options
    ydl_opts = {
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': list(languages),
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        # Request SRT format subtitles
        'subtitlesformat': 'srt',
        'convert_subs': 'srt',
    }

    if proxy_url:
        ydl_opts['proxy'] = proxy_url

    # Try to extract subtitles using yt-dlp
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            # Extract video info and subtitles
            info = ydl.extract_info(video_url, download=False)

            # Get available subtitles
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})
            native_lang = info.get('language')

            # Try requested languages first, then fall back to English, then any available
            available_subs = None
            selected_lang_code = None
            is_translated = False       # because if true then error 429 is likely

            for lang in languages:
                # Check for manual subtitles (safe)
                if lang in subtitles:
                    available_subs = subtitles[lang]
                    selected_lang_code = lang
                    is_translated = False
                    break
                
                # Check for original automatic captions (also safe)
                orig_key = f"{lang}-orig"
                if orig_key in automatic_captions:
                    available_subs = automatic_captions[orig_key]
                    selected_lang_code = orig_key
                    is_translated = False
                    break
                
                # Check for auto-translated captions (Error 429 likely)
                if lang in automatic_captions:
                    available_subs = automatic_captions[lang]
                    selected_lang_code = lang
                    # If it lacks -orig and isn't the native language, it's certainly translated
                    is_translated = (lang != native_lang)
                    break

            # Fallback to English if requested language not found
            if not available_subs:
                if 'en' in subtitles:
                    available_subs = subtitles['en']
                    selected_lang_code = 'en'
                    is_translated = False
                elif 'en-orig' in automatic_captions:
                    available_subs = automatic_captions['en-orig']
                    selected_lang_code = 'en-orig'
                    is_translated = False
                elif 'en' in automatic_captions:
                    available_subs = automatic_captions['en']
                    selected_lang_code = 'en'
                    is_translated = (native_lang != 'en')
                else:
                    # Take the first available subtitle
                    all_subs = {**subtitles, **automatic_captions}
                    if all_subs:
                        first_key = list(all_subs.keys())[0]
                        available_subs = all_subs[first_key]
                        selected_lang_code = first_key
                        is_translated = not (first_key.endswith('-orig') or first_key in subtitles)

            if not available_subs:
                raise ValueError("No subtitles available for this video")

            # Find the best subtitle format (prefer srt, then others)
            subtitle_url = None
            for sub in available_subs:
                if sub['ext'] == 'srt':
                    subtitle_url = sub['url']
                    break

            if not subtitle_url:
                # Take the first available format
                subtitle_url = available_subs[0]['url']

            # Download and parse the subtitle file
            import requests
            response = requests.get(subtitle_url, proxies={
                                    'http': proxy_url, 'https': proxy_url} if proxy_url else None)
            
            # Handling for 429 error if machine-translated subtitles are requested
            if response.status_code == 429:
                raise ValueError(
                    f"YouTube rate-limited this request (429). "
                    f"This usually happens when requesting auto-translated subtitles ('{selected_lang_code}') "
                    f"for a video natively in '{native_lang}'."
                ) 

            response.raise_for_status()

            return {    # still returning pieces, adding metadata, useful for frontend user-facing warning to work
                "pieces": _parse_srt_content(response.text),
                "metadata": {
                    "is_translated": is_translated,
                    "native_lang": native_lang,
                    "selected_lang_code": selected_lang_code
                }
            }

        except Exception as e:
            raise ValueError(f"Failed to extract subtitles: {e}")


def _parse_srt_content(srt_content: str) -> List[Dict[str, Any]]:
    """Parse SRT subtitle content into transcript pieces."""
    import re

    pieces = []
    lines = srt_content.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Look for timestamp lines (SRT format: 00:00:00,000 --> 00:00:00,000)
        timestamp_match = re.match(
            r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', line)
        if timestamp_match:
            start_time = _srt_timestamp_to_seconds(timestamp_match.group(1))
            end_time = _srt_timestamp_to_seconds(timestamp_match.group(2))

            # Collect text lines until we hit an empty line or another timestamp
            text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r'\d{2}:\d{2}:\d{2},\d{3}', lines[i]):
                text_line = lines[i].strip()
                # Remove SRT formatting tags
                text_line = re.sub(r'<[^>]+>', '', text_line)
                if text_line:
                    text_lines.append(text_line)
                i += 1

            if text_lines:
                pieces.append({
                    'text': ' '.join(text_lines),
                    'start': start_time,
                    'duration': end_time - start_time
                })
        else:
            i += 1

    return pieces


def _srt_timestamp_to_seconds(timestamp: str) -> float:
    """Convert SRT timestamp (HH:MM:SS,mmm) to seconds."""
    return _subtitle_timestamp_to_seconds(timestamp)


def _subtitle_timestamp_to_seconds(timestamp: str) -> float:
    """Convert subtitle timestamps to seconds.

    Supports:
    - SRT: HH:MM:SS,mmm
    - WebVTT: HH:MM:SS.mmm or MM:SS.mmm
    """
    timestamp = timestamp.strip().replace(",", ".")
    parts = timestamp.split(":")
    try:
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
    except ValueError:
        return 0.0
    return 0.0


def _parse_vtt_content(vtt_content: str) -> List[Dict[str, Any]]:
    """Parse WebVTT subtitle content into transcript pieces."""
    pieces: List[Dict[str, Any]] = []
    lines = vtt_content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
            i += 1
            continue

        # Allow cue identifiers: if current line isn't a timestamp but next is,
        # advance to next line.
        if "-->" not in line and i + 1 < len(lines) and "-->" in lines[i + 1]:
            i += 1
            line = lines[i].strip()

        if "-->" not in line:
            i += 1
            continue

        # VTT end timestamp may include settings after a space.
        ts_parts = line.split("-->")
        if len(ts_parts) != 2:
            i += 1
            continue

        start_raw = ts_parts[0].strip().split(" ")[0]
        end_raw = ts_parts[1].strip().split(" ")[0]
        start_time = _subtitle_timestamp_to_seconds(start_raw)
        end_time = _subtitle_timestamp_to_seconds(end_raw)

        text_lines: List[str] = []
        i += 1
        while i < len(lines):
            text_line = lines[i].strip()
            if not text_line:
                break
            # Next cue starts
            if "-->" in text_line:
                i -= 1
                break
            text_line = re.sub(r"<[^>]+>", "", text_line)
            if text_line:
                text_lines.append(text_line)
            i += 1

        if text_lines:
            pieces.append({
                "text": " ".join(text_lines),
                "start": start_time,
                "duration": max(0.0, end_time - start_time),
            })

        i += 1

    return pieces


def _parse_plain_subtitle_content(text_content: str) -> List[Dict[str, Any]]:
    """Parse plain subtitle/transcript text without timestamps.

    We assign synthetic timings so existing duration-based chunking still works.
    """
    pieces: List[Dict[str, Any]] = []
    current_start = 0.0
    synthetic_duration = 5.0

    for raw_line in text_content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        pieces.append({
            "text": line,
            "start": current_start,
            "duration": synthetic_duration,
        })
        current_start += synthetic_duration

    return pieces


def _detect_subtitle_format(
    content: str,
    file_path: Optional[str] = None,
    explicit_format: str = "auto",
) -> str:
    """Detect subtitle format from explicit setting, file extension, or content."""
    if explicit_format in {"srt", "vtt", "plain"}:
        return explicit_format

    suffix = Path(file_path).suffix.lower() if file_path else ""
    if suffix == ".srt":
        return "srt"
    if suffix == ".vtt":
        return "vtt"

    content_stripped = content.lstrip()
    if content_stripped.startswith("WEBVTT"):
        return "vtt"

    if re.search(r"\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}", content):
        return "srt"

    if re.search(r"(?:\d{2}:)?\d{2}:\d{2}\.\d{3}\s*-->\s*(?:\d{2}:)?\d{2}:\d{2}\.\d{3}", content):
        return "vtt"

    return "plain"


def _parse_subtitle_content(content: str, subtitle_format: str) -> List[Dict[str, Any]]:
    """Parse subtitle content into normalized transcript pieces."""
    if subtitle_format == "srt":
        return _parse_srt_content(content)
    if subtitle_format == "vtt":
        return _parse_vtt_content(content)
    return _parse_plain_subtitle_content(content)


def _read_text_file(file_path: str) -> str:
    """Read text from a file, tolerating encoding issues."""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


@PluginRegistry.register
class YouTubeTranscriptIngestPlugin(IngestPlugin):
    """Ingest YouTube video transcript(s) as document chunks.

    Unlike file-based plugins, this can work with a remote resource. A placeholder
    file may still be supplied by the ingestion pipeline; its path is accepted but
    not required if `video_url` param is provided.

    Supports progress reporting for multi-video ingestion.
    """

    name = "youtube_transcript_ingest"
    kind = "remote-ingest"
    description = "Ingest YouTube transcripts via yt-dlp, with manual subtitle upload/paste fallback"
    # We allow providing a text file containing URLs; advertise txt support.
    supported_file_types = {"txt", "srt", "vtt"}
    supports_progress = True  # This plugin supports progress callbacks

    def get_parameters(self) -> Dict[str, Dict[str, Any]]:  # noqa: D401
        return {
            "_manual_subtitles_fallback": {
                "type": "info",
                "description": (
                    "If YouTube returns 429, upload subtitle files (.srt/.vtt/.txt) "
                    "or paste subtitles into manual_subtitle_text. "
                    "Provide video_url optionally to keep YouTube citation links."
                ),
                "required": False,
                "ui_hint": "info",
            },
            "video_url": {
                "type": "string",
                "description": (
                    "Full YouTube video URL. If manual subtitles are provided, this URL is optional and "
                    "used for source metadata/timestamp links. If omitted, uploaded text files are read "
                    "for YouTube URLs (one per line)."
                ),
                "required": False,
            },
            "language": {
                "type": "string",
                "description": "Preferred subtitle language code (ISO 639-1).",
                "default": "en",
                "required": False,
            },
            "chunk_duration": {
                "type": "number",
                "description": "Target chunk duration in seconds.",
                "default": 60,
                "required": False,
            },
            "proxy_url": {
                "type": "string",
                "description": "Optional proxy URL for transcript API calls.",
                "required": False,
            },
            "manual_subtitle_text": {
                "type": "long-string",
                "description": "Optional manual subtitle/transcript content (SRT, VTT, or plain text).",
                "required": False,
            },
            "manual_subtitle_format": {
                "type": "string",
                "description": "Format for manual_subtitle_text or uploaded subtitle text file.",
                "enum": ["auto", "srt", "vtt", "plain"],
                "default": "auto",
                "required": False,
            },
        }

    # Helper -----------------------------------------------------------------
    def _extract_urls_from_file(self, file_path: str) -> List[str]:
        urls: List[str] = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and ("youtu.be/" in line or "youtube.com" in line):
                        urls.append(line)
        except Exception:
            # Ignore file read issues; treat as no URLs
            pass
        return urls

    def ingest(self, file_path: str, **kwargs) -> List[Dict[str, Any]]:  # noqa: D401
        """Ingest YouTube video transcripts.

        Args:
            file_path: Path to optional text file containing URLs
            **kwargs: Plugin parameters
                      May include 'progress_callback' for progress reporting
        Returns:
            List of document chunks with metadata
        """
        video_url: Optional[str] = kwargs.get("video_url")
        language: str = kwargs.get("language", "en")
        chunk_duration: float = float(kwargs.get("chunk_duration", 60))
        proxy_url: Optional[str] = kwargs.get("proxy_url")
        manual_subtitle_text: Optional[str] = kwargs.get("manual_subtitle_text")
        manual_subtitle_format: str = str(
            kwargs.get("manual_subtitle_format", "auto") or "auto"
        ).lower()
        # supplied by ingestion service
        file_url: str = kwargs.get("file_url", "")

        # Manual subtitle ingestion path (highest priority)
        manual_text = manual_subtitle_text.strip() if isinstance(
            manual_subtitle_text, str) else ""
        file_suffix = Path(file_path).suffix.lower()
        uploaded_text_content = ""
        uploaded_urls: List[str] = []

        if file_suffix in {".txt", ".srt", ".vtt"}:
            try:
                uploaded_text_content = _read_text_file(file_path).strip()
            except Exception:
                uploaded_text_content = ""

        if file_suffix == ".txt":
            uploaded_urls = self._extract_urls_from_file(file_path)

        manual_source: Optional[str] = None
        manual_content: str = ""

        if manual_text:
            manual_content = manual_text
            manual_source = "manual_text"
        elif uploaded_text_content:
            # For .txt files, preserve prior behavior:
            # if file includes YouTube URLs, treat as URL list (automatic mode).
            if file_suffix in {".srt", ".vtt"} or (file_suffix == ".txt" and not uploaded_urls):
                manual_content = uploaded_text_content
                manual_source = "uploaded_file"

        if manual_content:
            self.report_progress(kwargs, 0, 1, "Parsing manual subtitles...")
            detected_format = _detect_subtitle_format(
                manual_content,
                file_path=file_path,
                explicit_format=manual_subtitle_format,
            )
            pieces = _parse_subtitle_content(manual_content, detected_format)
            if not pieces:
                raise ValueError(
                    "Manual subtitle content could not be parsed into subtitle segments."
                )

            video_id = _parse_youtube_url(video_url) if video_url else None
            chunk_objs = _chunk_transcript(pieces, chunk_duration)

            all_chunks: List[Dict[str, Any]] = []
            total = len(chunk_objs)
            for idx, c in enumerate(chunk_objs):
                cleaned_text = " ".join(c["text_parts"]).strip()
                original_text = " ".join(c["original_text_parts"]).strip()
                start_seconds = float(c.get("start", 0.0) or 0.0)
                end_seconds = float(c.get("end", start_seconds) or start_seconds)
                start_ts = _seconds_to_timestamp(start_seconds)
                end_ts = _seconds_to_timestamp(end_seconds)

                if video_id:
                    source_url = f"https://youtu.be/{video_id}?t={int(start_seconds)}"
                elif file_url:
                    source_url = file_url
                else:
                    source_url = "manual_subtitles"

                metadata = {
                    "ingestion_plugin": self.name,
                    "source_url": source_url,
                    "video_id": video_id or "",
                    "language": language,
                    "chunk_index": idx,
                    "chunk_count": total,
                    "start_time": start_seconds,
                    "end_time": end_seconds,
                    "start_timestamp": start_ts,
                    "end_timestamp": end_ts,
                    "chunk_duration_target": chunk_duration,
                    "original_text_sample": original_text[:200],
                    "file_url": file_url,
                    "retrieval_timestamp": datetime.utcnow().isoformat(),
                    "plugin_version": "1.1.0",
                    "subtitle_source": manual_source,
                    "subtitle_format": detected_format,
                }

                all_chunks.append({
                    "text": cleaned_text,
                    "metadata": metadata,
                })

            if not all_chunks:
                raise ValueError("No chunks produced from manual subtitle content.")

            self.report_progress(
                kwargs, 1, 1, f"Completed manual subtitle ingestion: {len(all_chunks)} chunks"
            )
            return all_chunks

        urls: List[str] = []
        if video_url:
            urls.append(video_url)
        else:
            urls.extend(self._extract_urls_from_file(file_path))

        if not urls:
            raise ValueError(
                "No video_url provided and no YouTube URLs found in file. Provide plugin param 'video_url' or upload a txt file containing URLs."
            )

        # Report initial progress
        self.report_progress(kwargs, 0, len(
            urls), f"Starting transcript extraction for {len(urls)} video(s)...")

        all_chunks: List[Dict[str, Any]] = []
        for url_idx, url in enumerate(urls):
            video_id = _parse_youtube_url(url)
            if not video_id:
                self.report_progress(
                    kwargs, url_idx + 1, len(urls), f"Skipped invalid URL: {url[:30]}...")
                continue  # skip invalid

            self.report_progress(kwargs, url_idx, len(
                urls), f"Fetching transcript for video {video_id}...")

            try:    
                result = _fetch_transcript(video_id, [language], proxy_url)
                pieces = result["pieces"]
                meta_info = result["metadata"]      # not var metadata as seen below, just info about translation

                # If machine-translated, issue a warning
                if meta_info["is_translated"]:
                    warning_msg = (
                        f"WARNING: Requested language '{language}' requires YouTube Auto-Translation "
                        f"for video {video_id} (Native: '{meta_info['native_lang']}'). "
                        "This frequently triggers '429 Too Many Requests' errors. "
                        f"Consider requesting '{meta_info['native_lang']}' instead for better stability."
                    )
                    self.report_progress(kwargs, url_idx, len(urls), warning_msg)

            except ValueError as e:
                # Skip videos without transcripts or other extraction failures
                if "No subtitles available" in str(e):
                    self.report_progress(
                        kwargs, url_idx + 1, len(urls), f"No subtitles for {video_id}, skipping...")
                    continue
                elif "429" in str(e):
                    self.report_progress(kwargs, url_idx + 1, len(urls), f"Error: {str(e)}")
                    continue
                else:
                    raise e
            except Exception as e:  # pragma: no cover
                raise ValueError(f"Failed to fetch transcript for {url}: {e}")

            chunk_objs = _chunk_transcript(pieces, chunk_duration)

            # Build documents list for this video
            total = len(chunk_objs)
            for idx, c in enumerate(chunk_objs):
                cleaned_text = " ".join(c["text_parts"]).strip()
                original_text = " ".join(c["original_text_parts"]).strip()
                start_ts = _seconds_to_timestamp(
                    c["start"]) if c["start"] else "00:00:00,000"
                end_ts = _seconds_to_timestamp(
                    c["end"]) if c["end"] else start_ts

                # Generate YouTube URL with timestamp using standard format
                # Use youtu.be format with ?t= parameter for clean URLs
                timestamp_seconds = int(c["start"])
                youtube_url_with_timestamp = f"https://youtu.be/{video_id}?t={timestamp_seconds}"

                metadata = {
                    "ingestion_plugin": self.name,
                    "source_url": youtube_url_with_timestamp,
                    "video_id": video_id,
                    "language": language,
                    "chunk_index": idx,
                    "chunk_count": total,
                    "start_time": c["start"],
                    "end_time": c["end"],
                    "start_timestamp": start_ts,
                    "end_timestamp": end_ts,
                    "chunk_duration_target": chunk_duration,
                    "original_text_sample": original_text[:200],
                    "file_url": file_url,
                    "retrieval_timestamp": datetime.utcnow().isoformat(),
                    "plugin_version": "1.0.0",
                }

                all_chunks.append({
                    "text": cleaned_text,
                    "metadata": metadata,
                })

            # Report progress after each video
            self.report_progress(kwargs, url_idx + 1, len(urls),
                                 f"Processed video {video_id}: {total} chunks")

        if not all_chunks:
            raise ValueError(
                "No chunks produced from provided YouTube URL(s).")

        # Report completion
        self.report_progress(kwargs, len(urls), len(
            urls), f"Completed: {len(all_chunks)} chunks from {len(urls)} video(s)")
        return all_chunks
