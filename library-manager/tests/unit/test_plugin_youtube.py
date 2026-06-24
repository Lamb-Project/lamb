"""Unit tests for ``YouTubeTranscriptImportPlugin`` and its pure helpers.

The transcript fetch is patched at session scope by ``tests/youtube_cache.py``
(installed in the root conftest), so ``import_content`` for the cached video
ids (``dQw4w9WgXcQ`` and the synthetic ``abc123``) runs fully offline — no
yt-dlp, no network. The URL/timestamp/SRT helpers are exercised directly.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from plugins.base import ImportResult
from plugins.youtube_transcript_import import (
    YouTubeTranscriptImportPlugin,
    _build_source_ref,
    _parse_srt_content,
    _parse_youtube_url,
    _resolve_language_key,
    _seconds_to_timestamp,
)

# ---------------------------------------------------------------------------
# _parse_youtube_url
# ---------------------------------------------------------------------------


class TestParseYoutubeUrl:
    """Video-id extraction across the URL shapes the plugin actually supports."""

    def test_watch_query(self):
        """A standard watch?v= URL yields the id."""
        assert _parse_youtube_url(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        ) == "dQw4w9WgXcQ"

    def test_youtu_be_short(self):
        """A youtu.be short link yields the id from the path."""
        assert _parse_youtube_url("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_youtu_be_with_trailing_path(self):
        """youtu.be takes the first path segment as the id."""
        assert _parse_youtube_url("https://youtu.be/dQw4w9WgXcQ/x") == "dQw4w9WgXcQ"

    def test_youtu_be_empty_path(self):
        """An empty youtu.be path yields None."""
        assert _parse_youtube_url("https://youtu.be/") is None

    def test_watch_without_v_param(self):
        """A youtube.com URL with no v= query yields None."""
        assert _parse_youtube_url("https://www.youtube.com/channel/abc") is None

    def test_embed_url_yields_none(self):
        """An /embed/ URL has no v= query, so the parser returns None.

        (Documented behavior: the parser only reads the v= query param and the
        youtu.be path — it does NOT special-case /embed/ or /shorts/.)
        """
        assert _parse_youtube_url("https://www.youtube.com/embed/dQw4w9WgXcQ") is None

    def test_shorts_url_yields_none(self):
        """A /shorts/ URL likewise yields None (no v= query)."""
        assert _parse_youtube_url("https://www.youtube.com/shorts/dQw4w9WgXcQ") is None

    def test_non_youtube_url(self):
        """A non-YouTube host yields None."""
        assert _parse_youtube_url("https://example.com/video") is None


# ---------------------------------------------------------------------------
# _seconds_to_timestamp
# ---------------------------------------------------------------------------


class TestSecondsToTimestamp:
    """Timestamp formatting with and without an hours component."""

    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (0, "00:00"),
            (59, "00:59"),
            (60, "01:00"),
            (125, "02:05"),
            (3600, "01:00:00"),
            (3661, "01:01:01"),
        ],
    )
    def test_formats(self, seconds, expected):
        """Seconds render as MM:SS, switching to HH:MM:SS past an hour."""
        assert _seconds_to_timestamp(seconds) == expected

    def test_fractional_seconds_floored(self):
        """Fractional seconds are floored to whole seconds."""
        assert _seconds_to_timestamp(5.9) == "00:05"


# ---------------------------------------------------------------------------
# _resolve_language_key
# ---------------------------------------------------------------------------


class TestResolveLanguageKey:
    """Resolving a requested language to the variant the video exposes."""

    def test_exact_match(self):
        """An exact key wins."""
        assert _resolve_language_key({"en": [], "es": []}, "en") == "en"

    def test_locale_suffix_match(self):
        """A locale-suffixed variant (en-US) matches the base code."""
        assert _resolve_language_key({"en-US": [], "es": []}, "en") == "en-US"

    def test_translation_chain_variant(self):
        """A translation-chain variant matches on the prefix before the dash."""
        assert _resolve_language_key({"en-nP7-2PuUl7o": []}, "en") == "en-nP7-2PuUl7o"

    def test_no_match(self):
        """No matching key yields None."""
        assert _resolve_language_key({"fr": []}, "en") is None

    def test_empty_map(self):
        """An empty map yields None."""
        assert _resolve_language_key({}, "en") is None

    def test_none_map(self):
        """A None map yields None."""
        assert _resolve_language_key(None, "en") is None


# ---------------------------------------------------------------------------
# _parse_srt_content (handles SRT and VTT alike)
# ---------------------------------------------------------------------------


class TestParseSrtContent:
    """SRT/VTT parsing into timed text pieces."""

    def test_basic_srt(self):
        """Two cues parse into two pieces with start/duration."""
        srt = (
            "1\n00:00:01,000 --> 00:00:04,000\nHello world\n\n"
            "2\n00:00:05,000 --> 00:00:08,000\nSecond line\n"
        )
        pieces = _parse_srt_content(srt)
        assert len(pieces) == 2
        assert pieces[0]["text"] == "Hello world"
        assert pieces[0]["start"] == 1.0
        assert pieces[0]["duration"] == 3.0

    def test_vtt_dot_separator(self):
        """VTT-style ``.`` millisecond separators parse the same as SRT commas."""
        vtt = "00:00:01.000 --> 00:00:02.500\nVTT cue\n"
        pieces = _parse_srt_content(vtt)
        assert len(pieces) == 1
        assert pieces[0]["start"] == 1.0
        assert pieces[0]["duration"] == 1.5

    def test_noise_removed(self):
        """Bracketed/parenthesised noise is stripped from cue text."""
        srt = "1\n00:00:01,000 --> 00:00:04,000\n[applause] Hello [music]\n"
        pieces = _parse_srt_content(srt)
        assert pieces[0]["text"] == "Hello"

    def test_noise_only_block_skipped(self):
        """A cue whose text is entirely noise is dropped."""
        srt = (
            "1\n00:00:01,000 --> 00:00:04,000\n[noise]\n\n"
            "2\n00:00:05,000 --> 00:00:08,000\nReal\n"
        )
        pieces = _parse_srt_content(srt)
        assert len(pieces) == 1
        assert pieces[0]["text"] == "Real"

    def test_multiline_cue_joined(self):
        """Multiple text lines in a cue are joined with spaces."""
        srt = "1\n00:00:01,000 --> 00:00:04,000\nLine one\nLine two\n"
        assert _parse_srt_content(srt)[0]["text"] == "Line one Line two"

    def test_hours_component(self):
        """Hour-level timestamps are summed into seconds."""
        srt = "1\n01:30:00,000 --> 01:30:05,000\nLate\n"
        assert _parse_srt_content(srt)[0]["start"] == 5400.0

    def test_empty_string(self):
        """Empty input yields no pieces."""
        assert _parse_srt_content("") == []

    def test_no_timestamp(self):
        """A block with no timestamp line is skipped."""
        assert _parse_srt_content("just text\nno timestamps") == []


# ---------------------------------------------------------------------------
# _build_source_ref
# ---------------------------------------------------------------------------


class TestBuildSourceRef:
    """source_ref construction for YouTube imports."""

    def test_shape(self):
        """source_ref carries type, id, canonical url, and language."""
        ref = _build_source_ref(
            "https://www.youtube.com/watch?v=abc123", "abc123", "en"
        )
        assert ref == {
            "type": "youtube",
            "source_url": "https://www.youtube.com/watch?v=abc123",
            "video_id": "abc123",
            "video_url": "https://www.youtube.com/watch?v=abc123",
            "language": "en",
        }


# ---------------------------------------------------------------------------
# import_content (offline via the session YouTube cache)
# ---------------------------------------------------------------------------


class TestImportContent:
    """Full import driven by the offline transcript cache."""

    def setup_method(self):
        """Fresh plugin per test."""
        self.plugin = YouTubeTranscriptImportPlugin()

    def test_invalid_url_raises(self):
        """A non-YouTube URL raises ValueError before any fetch."""
        with pytest.raises(ValueError, match="Could not extract video ID"):
            self.plugin.import_content("https://example.com/not-youtube")

    def test_cached_real_transcript(self):
        """The cached Rick Astley video imports into timestamped Markdown."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = self.plugin.import_content(url)

        assert isinstance(result, ImportResult)
        assert result.full_text.startswith(f"# Transcript: {url}")
        assert "**[" in result.full_text  # timestamped entries
        assert result.metadata["video_id"] == "dQw4w9WgXcQ"
        assert result.metadata["subtitle_source"] == "manual"
        assert result.metadata["import_plugin"] == "youtube_transcript_import"
        assert result.source_ref["type"] == "youtube"
        assert result.source_ref["video_id"] == "dQw4w9WgXcQ"

    def test_cached_synthetic_transcript(self):
        """The synthetic ``abc123`` cache entry imports a single timed piece."""
        url = "https://www.youtube.com/watch?v=abc123"
        result = self.plugin.import_content(url)

        assert "**[00:00]** Hello" in result.full_text
        assert result.metadata["transcript_pieces"] == 1
        assert result.metadata["video_id"] == "abc123"


# ---------------------------------------------------------------------------
# _fetch_transcript / _download_and_parse — yt-dlp mocked at the boundary
# ---------------------------------------------------------------------------


def _mock_ydl(**attrs):
    """Build a context-manager-capable MagicMock standing in for YoutubeDL()."""
    inst = MagicMock()
    for name, value in attrs.items():
        setattr(inst, name, value)
    inst.__enter__ = MagicMock(return_value=inst)
    inst.__exit__ = MagicMock(return_value=False)
    return inst


class TestFetchTranscript:
    """``_fetch_transcript`` source-selection logic with yt-dlp mocked.

    The session cache patches the module-level ``_fetch_transcript`` to read
    from disk; the real implementation is preserved on its ``__wrapped__``
    attribute, which we call here to exercise the live probe/select code.
    """

    def setup_method(self):
        """Resolve the unwrapped (real) implementation under test."""
        import plugins.youtube_transcript_import as yt_mod

        self.fetch = getattr(
            yt_mod._fetch_transcript, "__wrapped__", yt_mod._fetch_transcript
        )

    def test_prefers_manual_subtitle(self):
        """When manual subtitles exist, they are chosen over auto-captions."""
        import yt_dlp

        info = {"subtitles": {"en": [{"ext": "srt"}]}, "automatic_captions": {}}
        ydl = _mock_ydl(extract_info=MagicMock(return_value=info))
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=ydl),
            patch(
                "plugins.youtube_transcript_import._download_and_parse",
                return_value=[{"text": "Hi", "start": 0, "duration": 1}],
            ),
        ):
            pieces, source = self.fetch("abc123", "en", None)

        assert source == "manual"
        assert len(pieces) == 1

    def test_falls_back_to_auto(self):
        """With only auto-captions, the auto source label is returned."""
        import yt_dlp

        info = {"subtitles": {}, "automatic_captions": {"en": [{"ext": "srt"}]}}
        ydl = _mock_ydl(extract_info=MagicMock(return_value=info))
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=ydl),
            patch(
                "plugins.youtube_transcript_import._download_and_parse",
                return_value=[{"text": "Hi", "start": 0, "duration": 1}],
            ),
        ):
            _pieces, source = self.fetch("abc123", "en", None)

        assert source == "auto"

    def test_no_subtitles_raises(self):
        """No tracks in the requested language raises a RuntimeError."""
        import yt_dlp

        info = {"subtitles": {"fr": [{}]}, "automatic_captions": {}}
        ydl = _mock_ydl(extract_info=MagicMock(return_value=info))
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=ydl),
            pytest.raises(RuntimeError, match="No subtitles available"),
        ):
            self.fetch("abc123", "en", None)

    def test_proxy_passed_to_probe(self):
        """A proxy_url is threaded into the yt-dlp probe options."""
        import yt_dlp

        info = {"subtitles": {"en": [{"ext": "srt"}]}, "automatic_captions": {}}
        ydl = _mock_ydl(extract_info=MagicMock(return_value=info))
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=ydl) as mk,
            patch(
                "plugins.youtube_transcript_import._download_and_parse",
                return_value=[{"text": "Hi", "start": 0, "duration": 1}],
            ),
        ):
            self.fetch("abc123", "en", "http://proxy:8080")

        assert mk.call_args_list[0][0][0]["proxy"] == "http://proxy:8080"

    def test_extract_info_failure_raises(self):
        """A yt-dlp probe failure raises a RuntimeError naming the video."""
        import yt_dlp

        ydl = _mock_ydl(extract_info=MagicMock(side_effect=Exception("blocked")))
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=ydl),
            pytest.raises(RuntimeError, match="Failed to fetch video info"),
        ):
            self.fetch("abc123", "en", None)

    def test_rate_limit_message(self):
        """A 429 during download surfaces the rate-limit message."""
        import yt_dlp

        info = {"subtitles": {"en": [{"ext": "srt"}]}, "automatic_captions": {}}
        ydl = _mock_ydl(extract_info=MagicMock(return_value=info))
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=ydl),
            patch(
                "plugins.youtube_transcript_import._download_and_parse",
                side_effect=Exception("HTTP Error 429: Too Many Requests"),
            ),
            pytest.raises(RuntimeError, match="rate-limited"),
        ):
            self.fetch("abc123", "en", None)

    def test_non_429_failure_raises_generic(self):
        """A non-rate-limit download failure yields the generic error."""
        import yt_dlp

        info = {"subtitles": {"en": [{"ext": "srt"}]}, "automatic_captions": {}}
        ydl = _mock_ydl(extract_info=MagicMock(return_value=info))
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=ydl),
            patch(
                "plugins.youtube_transcript_import._download_and_parse",
                side_effect=Exception("network blip"),
            ),
            pytest.raises(RuntimeError, match="Could not download subtitles"),
        ):
            self.fetch("abc123", "en", None)

    def test_all_attempts_empty_raises(self):
        """When every download returns no pieces, a generic error is raised."""
        import yt_dlp

        info = {"subtitles": {"en": [{"ext": "srt"}]}, "automatic_captions": {}}
        ydl = _mock_ydl(extract_info=MagicMock(return_value=info))
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=ydl),
            patch(
                "plugins.youtube_transcript_import._download_and_parse",
                return_value=[],
            ),
            pytest.raises(RuntimeError, match="Could not download subtitles"),
        ):
            self.fetch("abc123", "en", None)


class TestDownloadAndParse:
    """``_download_and_parse`` temp-file handling with yt-dlp mocked."""

    def test_error_prefix_stripped(self):
        """A yt-dlp ``ERROR:`` prefix is trimmed from the bubbled-up message."""
        import yt_dlp
        from plugins.youtube_transcript_import import _download_and_parse

        ydl = _mock_ydl(download=MagicMock(side_effect=Exception("ERROR: Video unavailable")))
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=ydl),
            pytest.raises(RuntimeError, match="^Video unavailable"),
        ):
            _download_and_parse(
                url="https://youtube.com/watch?v=abc",
                language_key="en",
                source_label="manual",
                proxy_url=None,
            )

    def test_error_without_prefix_preserved(self):
        """A download error lacking the ``ERROR:`` prefix is preserved as-is."""
        import yt_dlp
        from plugins.youtube_transcript_import import _download_and_parse

        ydl = _mock_ydl(download=MagicMock(side_effect=Exception("plain failure")))
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=ydl),
            pytest.raises(RuntimeError, match="^plain failure$"),
        ):
            _download_and_parse(
                url="https://youtube.com/watch?v=abc",
                language_key="en",
                source_label="manual",
                proxy_url=None,
            )

    def test_no_subtitle_files_returns_empty(self):
        """A temp dir with no .srt/.vtt files yields no pieces."""
        import yt_dlp
        from plugins.youtube_transcript_import import _download_and_parse

        ydl = _mock_ydl(download=MagicMock(return_value=None))
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=ydl),
            patch("os.listdir", return_value=["video.mp4"]),
        ):
            assert (
                _download_and_parse(
                    url="https://youtube.com/watch?v=abc",
                    language_key="en",
                    source_label="manual",
                    proxy_url=None,
                )
                == []
            )

    def test_listdir_oserror_returns_empty(self):
        """If listing the temp dir fails, no pieces are returned."""
        import yt_dlp
        from plugins.youtube_transcript_import import _download_and_parse

        ydl = _mock_ydl(download=MagicMock(return_value=None))
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=ydl),
            patch("os.listdir", side_effect=OSError("gone")),
        ):
            assert (
                _download_and_parse(
                    url="https://youtube.com/watch?v=abc",
                    language_key="en",
                    source_label="manual",
                    proxy_url=None,
                )
                == []
            )

    def test_open_oserror_returns_empty(self):
        """If the subtitle file cannot be opened, no pieces are returned."""
        import yt_dlp
        from plugins.youtube_transcript_import import _download_and_parse

        ydl = _mock_ydl(download=MagicMock(return_value=None))
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=ydl),
            patch("os.listdir", return_value=["abc.en.srt"]),
            patch("builtins.open", side_effect=OSError("denied")),
        ):
            assert (
                _download_and_parse(
                    url="https://youtube.com/watch?v=abc",
                    language_key="en",
                    source_label="manual",
                    proxy_url=None,
                )
                == []
            )

    def test_proxy_and_auto_options(self):
        """Proxy and auto-only download options are passed to yt-dlp."""
        import yt_dlp
        from plugins.youtube_transcript_import import _download_and_parse

        ydl = _mock_ydl(download=MagicMock(return_value=None))
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=ydl) as mk,
            patch("os.listdir", return_value=[]),
        ):
            _download_and_parse(
                url="https://youtube.com/watch?v=abc",
                language_key="en",
                source_label="auto",
                proxy_url="http://proxy:8080",
            )

        opts = mk.call_args[0][0]
        assert opts["proxy"] == "http://proxy:8080"
        assert opts["writeautomaticsub"] is True
        assert opts["writesubtitles"] is False

    def test_parses_downloaded_srt(self, tmp_storage):
        """A real .srt written to the temp dir is read and parsed.

        ``_download_and_parse`` does ``import tempfile`` inside the function,
        so we patch ``tempfile.TemporaryDirectory`` to hand back a directory we
        pre-populated with a subtitle file matching the language key.
        """
        import yt_dlp
        from plugins.youtube_transcript_import import _download_and_parse

        sub = tmp_storage / "abc.en.srt"
        sub.write_text("1\n00:00:01,000 --> 00:00:03,000\nReal cue\n", encoding="utf-8")

        class _TD:
            def __enter__(self):
                return str(tmp_storage)

            def __exit__(self, *a):
                return False

        ydl = _mock_ydl(download=MagicMock(return_value=None))
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=ydl),
            patch("tempfile.TemporaryDirectory", lambda: _TD()),
        ):
            pieces = _download_and_parse(
                url="https://youtube.com/watch?v=abc",
                language_key="en",
                source_label="manual",
                proxy_url=None,
            )

        assert len(pieces) == 1
        assert pieces[0]["text"] == "Real cue"


class TestGetParameters:
    """``get_parameters`` contract."""

    def test_includes_language_and_proxy(self):
        """Exposes a language param (default 'en') and an advanced proxy_url."""
        params = YouTubeTranscriptImportPlugin().get_parameters()
        names = [p.name for p in params]
        assert names == ["language", "proxy_url"]
        lang = next(p for p in params if p.name == "language")
        assert lang.default == "en"
