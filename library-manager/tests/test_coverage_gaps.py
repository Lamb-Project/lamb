"""Tests targeting coverage gaps in schemas/common.py, url_import.py,
youtube_transcript_import.py, and markitdown_plus_import.py."""

from unittest.mock import MagicMock, patch

import pytest
from schemas.common import MessageResponse, PaginationParams

# -----------------------------------------------------------------------
# schemas/common.py
# -----------------------------------------------------------------------


class TestPaginationParams:
    def test_defaults(self):
        p = PaginationParams()
        assert p.limit == 20
        assert p.offset == 0

    def test_custom_values(self):
        p = PaginationParams(limit=50, offset=10)
        assert p.limit == 50
        assert p.offset == 10

    def test_limit_min_boundary(self):
        p = PaginationParams(limit=1)
        assert p.limit == 1

    def test_limit_max_boundary(self):
        p = PaginationParams(limit=100)
        assert p.limit == 100

    def test_limit_below_min_rejected(self):
        with pytest.raises(Exception):
            PaginationParams(limit=0)

    def test_limit_above_max_rejected(self):
        with pytest.raises(Exception):
            PaginationParams(limit=101)

    def test_offset_min_boundary(self):
        p = PaginationParams(offset=0)
        assert p.offset == 0

    def test_offset_negative_rejected(self):
        with pytest.raises(Exception):
            PaginationParams(offset=-1)


class TestMessageResponse:
    def test_basic(self):
        r = MessageResponse(message="hello")
        assert r.message == "hello"

    def test_missing_message_rejected(self):
        with pytest.raises(Exception):
            MessageResponse()


# -----------------------------------------------------------------------
# url_import.py — validation, SSRF, _safe_int, get_parameters
# -----------------------------------------------------------------------


class TestUrlImportPluginValidation:
    def setup_method(self):
        from plugins.url_import import UrlImportPlugin
        self.plugin = UrlImportPlugin()

    def test_invalid_url_no_scheme(self):
        with pytest.raises(ValueError, match="Invalid URL"):
            self.plugin.import_content("example.com")

    def test_invalid_url_no_netloc(self):
        with pytest.raises(ValueError, match="Invalid URL"):
            self.plugin.import_content("http://")

    def test_unsupported_scheme(self):
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            self.plugin.import_content("ftp://example.com/file")

    def test_ssrf_localhost(self):
        with pytest.raises(ValueError, match="not allowed"):
            self.plugin.import_content("http://localhost/page")

    def test_ssrf_127(self):
        with pytest.raises(ValueError, match="not allowed"):
            self.plugin.import_content("http://127.0.0.1/page")

    def test_ssrf_0000(self):
        with pytest.raises(ValueError, match="not allowed"):
            self.plugin.import_content("http://0.0.0.0/page")

    def test_ssrf_ipv6_loopback(self):
        with pytest.raises(ValueError, match="not allowed"):
            self.plugin.import_content("http://[::1]/page")

    def test_ssrf_metadata_endpoint(self):
        with pytest.raises(ValueError, match="not allowed"):
            self.plugin.import_content("http://169.254.169.254/latest/meta-data")

    def test_ssrf_google_metadata(self):
        with pytest.raises(ValueError, match="not allowed"):
            self.plugin.import_content("http://metadata.google.internal/computeMetadata")

    def test_get_parameters(self):
        params = self.plugin.get_parameters()
        assert len(params) == 5
        names = [p.name for p in params]
        assert "max_discovery_depth" in names
        assert "limit" in names
        assert "timeout" in names
        assert "description" in names
        assert "citation" in names

    def test_get_parameters_defaults(self):
        params = self.plugin.get_parameters()
        depth_param = next(p for p in params if p.name == "max_discovery_depth")
        assert depth_param.default == 2
        assert depth_param.min_value == 1
        assert depth_param.max_value == 10

    def test_markitdown_fallback_path(self):
        mock_result = MagicMock()
        mock_result.text_content = "# Hello World"
        with patch("markitdown.MarkItDown") as MockMD:
            MockMD.return_value.convert.return_value = mock_result
            result = self.plugin.import_content("https://example.com/page")
        assert result.full_text == "# Hello World"
        assert result.metadata["fetch_method"] == "markitdown"
        assert result.metadata["source_url"] == "https://example.com/page"
        assert result.source_ref["type"] == "url"

    def test_markitdown_fallback_empty_content(self):
        mock_result = MagicMock()
        mock_result.text_content = ""
        with patch("markitdown.MarkItDown") as MockMD:
            MockMD.return_value.convert.return_value = mock_result
            result = self.plugin.import_content("https://example.com/empty")
        assert "No text content" in result.full_text

    def test_markitdown_fallback_with_description_and_citation(self):
        mock_result = MagicMock()
        mock_result.text_content = "Content"
        with patch("markitdown.MarkItDown") as MockMD:
            MockMD.return_value.convert.return_value = mock_result
            result = self.plugin.import_content(
                "https://example.com/page",
                description="A test page",
                citation="Test 2024",
            )
        assert result.metadata["description"] == "A test page"
        assert result.metadata["citation"] == "Test 2024"

    def test_markitdown_fallback_fetch_failure(self):
        with patch("markitdown.MarkItDown") as MockMD:
            MockMD.return_value.convert.side_effect = Exception("Connection refused")
            with pytest.raises(RuntimeError, match="Failed to fetch"):
                self.plugin.import_content("https://example.com/fail")


class TestSafeInt:
    def test_none_returns_default(self):
        from plugins.url_import import _safe_int
        assert _safe_int(None, 42) == 42

    def test_valid_int_string(self):
        from plugins.url_import import _safe_int
        assert _safe_int("10", 0) == 10

    def test_valid_int(self):
        from plugins.url_import import _safe_int
        assert _safe_int(25, 0) == 25

    def test_invalid_string_returns_default(self):
        from plugins.url_import import _safe_int
        assert _safe_int("abc", 99) == 99

    def test_float_string_returns_default(self):
        from plugins.url_import import _safe_int
        assert _safe_int("3.14", 7) == 7


class TestFirecrawlPath:
    def setup_method(self):
        from plugins.url_import import UrlImportPlugin
        self.plugin = UrlImportPlugin()

    def test_firecrawl_no_data_returns_placeholder(self):
        scrape_dict = {}
        with patch("firecrawl.FirecrawlApp") as MockApp:
            MockApp.return_value.scrape.return_value = scrape_dict
            result = self.plugin.import_content(
                "https://example.com",
                api_keys={"firecrawl_key": "test-key"},
            )
        assert "No content" in result.full_text
        assert result.metadata["pages_crawled"] == 0

    def test_firecrawl_with_markdown_object(self):
        mock_meta = MagicMock()
        mock_meta.url = "https://example.com"
        mock_meta.source_url = "https://example.com"
        mock_meta.title = "Example"
        mock_scrape = MagicMock()
        mock_scrape.markdown = "# Example Content"
        mock_scrape.metadata = mock_meta
        mock_scrape.url = "https://example.com"
        with patch("firecrawl.FirecrawlApp") as MockApp:
            MockApp.return_value.scrape.return_value = mock_scrape
            result = self.plugin.import_content(
                "https://example.com",
                api_keys={"firecrawl_key": "test-key"},
            )
        assert "# Example Content" in result.full_text
        assert result.metadata["pages_crawled"] == 1
        assert result.metadata["fetch_method"] == "firecrawl"

    def test_firecrawl_with_dict_result(self):
        scrape_dict = {
            "markdown": "# Dict Content",
            "metadata": {"sourceURL": "https://example.com", "title": "Dict Page"},
        }
        with patch("firecrawl.FirecrawlApp") as MockApp:
            MockApp.return_value.scrape.return_value = scrape_dict
            result = self.plugin.import_content(
                "https://example.com",
                api_keys={"firecrawl_key": "test-key"},
            )
        assert "# Dict Content" in result.full_text

    def test_firecrawl_with_dict_no_markdown(self):
        scrape_dict = {"markdown": "", "metadata": {}}
        with patch("firecrawl.FirecrawlApp") as MockApp:
            MockApp.return_value.scrape.return_value = scrape_dict
            result = self.plugin.import_content(
                "https://example.com",
                api_keys={"firecrawl_key": "test-key"},
            )
        assert "No content" in result.full_text

    def test_firecrawl_scrape_failure(self):
        with patch("firecrawl.FirecrawlApp") as MockApp:
            MockApp.return_value.scrape.side_effect = Exception("API error")
            with pytest.raises(RuntimeError, match="Firecrawl scrape failed"):
                self.plugin.import_content(
                    "https://example.com",
                    api_keys={"firecrawl_key": "test-key"},
                )

    def test_firecrawl_metadata_object_with_dict_meta(self):
        mock_scrape = MagicMock()
        mock_scrape.markdown = "# Content"
        mock_scrape.metadata = {"sourceURL": "https://example.com", "title": "Page"}
        mock_scrape.url = "https://example.com"
        with patch("firecrawl.FirecrawlApp") as MockApp:
            MockApp.return_value.scrape.return_value = mock_scrape
            result = self.plugin.import_content(
                "https://example.com",
                api_keys={"firecrawl_key": "test-key"},
            )
        assert "# Content" in result.full_text

    def test_firecrawl_with_description_and_citation(self):
        mock_scrape = MagicMock()
        mock_scrape.markdown = "# Content"
        mock_scrape.metadata = {"sourceURL": "https://example.com", "title": ""}
        mock_scrape.url = "https://example.com"
        with patch("firecrawl.FirecrawlApp") as MockApp:
            MockApp.return_value.scrape.return_value = mock_scrape
            result = self.plugin.import_content(
                "https://example.com",
                api_keys={"firecrawl_key": "test-key"},
                description="Test desc",
                citation="Test cite",
            )
        assert result.metadata["description"] == "Test desc"
        assert result.metadata["citation"] == "Test cite"

    def test_firecrawl_custom_api_url(self):
        mock_scrape = MagicMock()
        mock_scrape.markdown = "# Content"
        mock_scrape.metadata = {"sourceURL": "https://example.com", "title": ""}
        mock_scrape.url = "https://example.com"
        with patch("firecrawl.FirecrawlApp") as MockApp:
            MockApp.return_value.scrape.return_value = mock_scrape
            self.plugin.import_content(
                "https://example.com",
                api_keys={"firecrawl_key": "test-key", "firecrawl_url": "https://custom.api.com"},
            )
            MockApp.assert_called_once_with(api_key="test-key", api_url="https://custom.api.com")


# -----------------------------------------------------------------------
# youtube_transcript_import.py — helpers and get_parameters
# -----------------------------------------------------------------------


class TestYouTubeHelpers:
    def test_parse_youtube_url_standard(self):
        from plugins.youtube_transcript_import import _parse_youtube_url
        assert _parse_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_parse_youtube_url_short(self):
        from plugins.youtube_transcript_import import _parse_youtube_url
        assert _parse_youtube_url("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_parse_youtube_url_short_with_path(self):
        from plugins.youtube_transcript_import import _parse_youtube_url
        assert _parse_youtube_url("https://youtu.be/dQw4w9WgXcQ/extra") == "dQw4w9WgXcQ"

    def test_parse_youtube_url_invalid(self):
        from plugins.youtube_transcript_import import _parse_youtube_url
        assert _parse_youtube_url("https://example.com/video") is None

    def test_parse_youtube_url_youtu_be_empty(self):
        from plugins.youtube_transcript_import import _parse_youtube_url
        assert _parse_youtube_url("https://youtu.be/") is None

    def test_parse_youtube_url_no_v_param(self):
        from plugins.youtube_transcript_import import _parse_youtube_url
        assert _parse_youtube_url("https://www.youtube.com/channel/abc") is None

    def test_seconds_to_timestamp_no_hours(self):
        from plugins.youtube_transcript_import import _seconds_to_timestamp
        assert _seconds_to_timestamp(125) == "02:05"

    def test_seconds_to_timestamp_with_hours(self):
        from plugins.youtube_transcript_import import _seconds_to_timestamp
        assert _seconds_to_timestamp(3661) == "01:01:01"

    def test_seconds_to_timestamp_zero(self):
        from plugins.youtube_transcript_import import _seconds_to_timestamp
        assert _seconds_to_timestamp(0) == "00:00"

    def test_build_source_ref(self):
        from plugins.youtube_transcript_import import _build_source_ref
        ref = _build_source_ref("https://www.youtube.com/watch?v=abc123", "abc123", "en")
        assert ref["type"] == "youtube"
        assert ref["video_id"] == "abc123"
        assert ref["language"] == "en"
        assert ref["video_url"] == "https://www.youtube.com/watch?v=abc123"

    def test_get_parameters(self):
        from plugins.youtube_transcript_import import YouTubeTranscriptImportPlugin
        plugin = YouTubeTranscriptImportPlugin()
        params = plugin.get_parameters()
        assert len(params) == 2
        names = [p.name for p in params]
        assert "language" in names
        assert "proxy_url" in names
        lang_param = next(p for p in params if p.name == "language")
        assert lang_param.default == "en"

    def test_invalid_youtube_url_raises(self):
        from plugins.youtube_transcript_import import YouTubeTranscriptImportPlugin
        plugin = YouTubeTranscriptImportPlugin()
        with pytest.raises(ValueError, match="Could not extract video ID"):
            plugin.import_content("https://example.com/not-youtube")


class TestResolveLanguageKey:
    def test_exact_match(self):
        from plugins.youtube_transcript_import import _resolve_language_key
        subs = {"en": [{"ext": "srt"}], "es": [{"ext": "srt"}]}
        assert _resolve_language_key(subs, "en") == "en"

    def test_locale_suffix_match(self):
        from plugins.youtube_transcript_import import _resolve_language_key
        subs = {"en-US": [{"ext": "srt"}], "es": [{"ext": "srt"}]}
        assert _resolve_language_key(subs, "en") == "en-US"

    def test_complex_variant_match(self):
        from plugins.youtube_transcript_import import _resolve_language_key
        subs = {"en-nP7-2PuUl7o": [{"ext": "srt"}]}
        assert _resolve_language_key(subs, "en") == "en-nP7-2PuUl7o"

    def test_no_match(self):
        from plugins.youtube_transcript_import import _resolve_language_key
        subs = {"fr": [{"ext": "srt"}]}
        assert _resolve_language_key(subs, "en") is None

    def test_empty_map(self):
        from plugins.youtube_transcript_import import _resolve_language_key
        assert _resolve_language_key({}, "en") is None

    def test_none_map(self):
        from plugins.youtube_transcript_import import _resolve_language_key
        assert _resolve_language_key(None, "en") is None


class TestParseSrtContent:
    def test_basic_srt(self):
        from plugins.youtube_transcript_import import _parse_srt_content
        srt = (
            "1\n"
            "00:00:01,000 --> 00:00:04,000\n"
            "Hello world\n"
            "\n"
            "2\n"
            "00:00:05,000 --> 00:00:08,000\n"
            "Second line\n"
        )
        pieces = _parse_srt_content(srt)
        assert len(pieces) == 2
        assert pieces[0]["text"] == "Hello world"
        assert pieces[0]["start"] == 1.0
        assert pieces[0]["duration"] == 3.0
        assert pieces[1]["text"] == "Second line"

    def test_srt_with_noise_removal(self):
        from plugins.youtube_transcript_import import _parse_srt_content
        srt = (
            "1\n"
            "00:00:01,000 --> 00:00:04,000\n"
            "[applause] Hello [music]\n"
        )
        pieces = _parse_srt_content(srt)
        assert len(pieces) == 1
        assert pieces[0]["text"] == "Hello"

    def test_srt_empty_blocks_skipped(self):
        from plugins.youtube_transcript_import import _parse_srt_content
        srt = (
            "1\n"
            "00:00:01,000 --> 00:00:04,000\n"
            "[noise only]\n"
            "\n"
            "2\n"
            "00:00:05,000 --> 00:00:08,000\n"
            "Real text\n"
        )
        pieces = _parse_srt_content(srt)
        assert len(pieces) == 1
        assert pieces[0]["text"] == "Real text"

    def test_srt_with_hours(self):
        from plugins.youtube_transcript_import import _parse_srt_content
        srt = (
            "1\n"
            "01:30:00,000 --> 01:30:05,000\n"
            "Late content\n"
        )
        pieces = _parse_srt_content(srt)
        assert len(pieces) == 1
        assert pieces[0]["start"] == 5400.0

    def test_srt_empty_string(self):
        from plugins.youtube_transcript_import import _parse_srt_content
        assert _parse_srt_content("") == []

    def test_srt_no_timestamp(self):
        from plugins.youtube_transcript_import import _parse_srt_content
        srt = "Just some text\nwithout timestamps"
        assert _parse_srt_content(srt) == []

    def test_srt_multiline_text(self):
        from plugins.youtube_transcript_import import _parse_srt_content
        srt = (
            "1\n"
            "00:00:01,000 --> 00:00:04,000\n"
            "Line one\n"
            "Line two\n"
        )
        pieces = _parse_srt_content(srt)
        assert len(pieces) == 1
        assert pieces[0]["text"] == "Line one Line two"


class TestFetchTranscript:
    def test_successful_manual_subtitle(self):
        import yt_dlp
        from plugins.youtube_transcript_import import _fetch_transcript
        mock_info = {"subtitles": {"en": [{"ext": "srt"}]}, "automatic_captions": {}}
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=mock_ydl),
            patch("plugins.youtube_transcript_import._download_and_parse") as mock_dl,
        ):
            mock_dl.return_value = [{"text": "Hello", "start": 0, "duration": 1}]
            pieces, source = _fetch_transcript("abc123", "en", None)
            assert len(pieces) == 1
            assert source == "manual"


class TestDownloadAndParse:
    def test_ytdlp_error_prefix_stripped(self):
        import yt_dlp
        from plugins.youtube_transcript_import import _download_and_parse
        mock_ydl = MagicMock()
        mock_ydl.download.side_effect = Exception("ERROR: Video unavailable")
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=mock_ydl),
            pytest.raises(RuntimeError, match="Video unavailable"),
        ):
            _download_and_parse(
                url="https://youtube.com/watch?v=abc",
                language_key="en",
                source_label="manual",
                proxy_url=None,
            )

    def test_no_subtitle_files_found(self):
        import yt_dlp
        from plugins.youtube_transcript_import import _download_and_parse
        mock_ydl = MagicMock()
        mock_ydl.download.return_value = None
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=mock_ydl),
            patch("os.listdir", return_value=["video.mp4"]),
        ):
            result = _download_and_parse(
                url="https://youtube.com/watch?v=abc",
                language_key="en",
                source_label="manual",
                proxy_url=None,
            )
            assert result == []

    def test_with_proxy(self):
        import yt_dlp
        from plugins.youtube_transcript_import import _download_and_parse
        mock_ydl = MagicMock()
        mock_ydl.download.return_value = None
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        with (
            patch.object(yt_dlp, "YoutubeDL", return_value=mock_ydl) as MockYDL,
            patch("os.listdir", return_value=[]),
        ):
            _download_and_parse(
                url="https://youtube.com/watch?v=abc",
                language_key="en",
                source_label="auto",
                proxy_url="http://proxy:8080",
            )
            call_args = MockYDL.call_args[0][0]
            assert call_args["proxy"] == "http://proxy:8080"
            assert call_args["writeautomaticsub"] is True
            assert call_args["writesubtitles"] is False


# -----------------------------------------------------------------------
# markitdown_plus_import.py — get_parameters, _split_into_pages, _image_mime
# -----------------------------------------------------------------------


class TestMarkitdownPlusParameters:
    def test_get_parameters(self):
        from plugins.markitdown_plus_import import MarkItDownPlusPlugin
        plugin = MarkItDownPlusPlugin()
        params = plugin.get_parameters()
        assert len(params) == 3
        names = [p.name for p in params]
        assert "image_descriptions" in names
        assert "description" in names
        assert "citation" in names

    def test_image_descriptions_choices(self):
        from plugins.markitdown_plus_import import MarkItDownPlusPlugin
        plugin = MarkItDownPlusPlugin()
        params = plugin.get_parameters()
        img_param = next(p for p in params if p.name == "image_descriptions")
        assert img_param.choices == ["none", "basic", "llm"]
        assert img_param.default == "basic"

    def test_produces_capabilities(self):
        from plugins.content_handlers.capability import Capability
        from plugins.markitdown_plus_import import MarkItDownPlusPlugin
        assert Capability.TEXT in MarkItDownPlusPlugin.produces_capabilities
        assert Capability.PAGES in MarkItDownPlusPlugin.produces_capabilities
        assert Capability.IMAGES in MarkItDownPlusPlugin.produces_capabilities

    def test_file_extensions(self):
        from plugins.markitdown_plus_import import MarkItDownPlusPlugin
        assert "pdf" in MarkItDownPlusPlugin.file_extensions
        assert "docx" in MarkItDownPlusPlugin.file_extensions
        assert "pptx" in MarkItDownPlusPlugin.file_extensions


class TestSplitIntoPages:
    def test_non_page_aware_type(self):
        from plugins.markitdown_plus_import import _split_into_pages
        assert _split_into_pages("some content", "html") == []

    def test_no_page_breaks(self):
        from plugins.markitdown_plus_import import _split_into_pages
        assert _split_into_pages("just text", "pdf") == []

    def test_horizontal_rule_page_breaks(self):
        from plugins.markitdown_plus_import import _split_into_pages
        content = "Page 1 content\n\n---\n\nPage 2 content\n\n---\n\nPage 3 content"
        pages = _split_into_pages(content, "pdf")
        assert len(pages) == 3
        assert pages[0].text == "Page 1 content"
        assert pages[1].text == "Page 2 content"
        assert pages[2].text == "Page 3 content"
        assert pages[0].page_number == 1
        assert pages[2].page_number == 3

    def test_form_feed_page_breaks(self):
        from plugins.markitdown_plus_import import _split_into_pages
        content = "Page 1\n\fPage 2\n\fPage 3"
        pages = _split_into_pages(content, "docx")
        assert len(pages) == 3

    def test_html_comment_page_breaks(self):
        from plugins.markitdown_plus_import import _split_into_pages
        content = "Page 1\n<!-- page break -->\nPage 2"
        pages = _split_into_pages(content, "pptx")
        assert len(pages) == 2

    def test_empty_pages_filtered(self):
        from plugins.markitdown_plus_import import _split_into_pages
        content = "Page 1\n\n---\n\n\n\n---\n\nPage 3"
        pages = _split_into_pages(content, "pdf")
        assert len(pages) == 2

    def test_single_page_returns_empty(self):
        from plugins.markitdown_plus_import import _split_into_pages
        content = "Just one page\n\n---\n\n"
        pages = _split_into_pages(content, "pdf")
        assert pages == []


class TestImageMime:
    def test_png(self):
        from plugins.markitdown_plus_import import _image_mime
        assert _image_mime("png") == "image/png"

    def test_jpg(self):
        from plugins.markitdown_plus_import import _image_mime
        assert _image_mime("jpg") == "image/jpeg"

    def test_jpeg(self):
        from plugins.markitdown_plus_import import _image_mime
        assert _image_mime("jpeg") == "image/jpeg"

    def test_gif(self):
        from plugins.markitdown_plus_import import _image_mime
        assert _image_mime("gif") == "image/gif"

    def test_bmp(self):
        from plugins.markitdown_plus_import import _image_mime
        assert _image_mime("bmp") == "image/bmp"

    def test_webp(self):
        from plugins.markitdown_plus_import import _image_mime
        assert _image_mime("webp") == "image/webp"

    def test_tiff(self):
        from plugins.markitdown_plus_import import _image_mime
        assert _image_mime("tiff") == "image/tiff"

    def test_svg(self):
        from plugins.markitdown_plus_import import _image_mime
        assert _image_mime("svg") == "image/svg+xml"

    def test_unknown_defaults_to_png(self):
        from plugins.markitdown_plus_import import _image_mime
        assert _image_mime("xyz") == "image/png"

    def test_with_dot_prefix(self):
        from plugins.markitdown_plus_import import _image_mime
        assert _image_mime(".png") == "image/png"

    def test_uppercase(self):
        from plugins.markitdown_plus_import import _image_mime
        assert _image_mime("PNG") == "image/png"


class TestDescribeImage:
    def test_basic_mode(self):
        from plugins.markitdown_plus_import import _describe_image
        desc = _describe_image(b"fake", "img_001.png", "png", "basic", {}, {})
        assert desc == "Image: img_001.png"

    def test_unknown_mode_returns_none(self):
        from plugins.markitdown_plus_import import _describe_image
        desc = _describe_image(b"fake", "img_001.png", "png", "none", {}, {})
        assert desc is None

    def test_llm_mode_no_api_key(self):
        from plugins.markitdown_plus_import import _describe_image
        desc = _describe_image(b"fake", "img_001.png", "png", "llm", {}, {})
        assert desc == "Image: img_001.png"

    def test_llm_mode_success(self):
        from plugins.markitdown_plus_import import _describe_image
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "A blue sky"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 50

        stats: dict = {"images_with_llm_descriptions": 0, "llm_calls": []}
        with patch("openai.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = mock_response
            desc = _describe_image(
                b"fake", "img_001.png", "png", "llm", {"openai_vision": "sk-test"}, stats
            )
        assert desc == "A blue sky"
        assert stats["images_with_llm_descriptions"] == 1
        assert stats["llm_calls"][0]["success"] is True

    def test_llm_mode_failure(self):
        from plugins.markitdown_plus_import import _describe_image
        stats: dict = {"images_with_llm_descriptions": 0, "llm_calls": []}
        with patch("openai.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.side_effect = Exception("API error")
            desc = _describe_image(
                b"fake", "img_001.png", "png", "llm", {"openai_vision": "sk-test"}, stats
            )
        assert desc == "Image: img_001.png"
        assert stats["llm_calls"][0]["success"] is False


class TestExtractImages:
    def test_pymupdf_not_installed(self):
        from pathlib import Path

        from plugins.markitdown_plus_import import _extract_images
        with (
            patch.dict("sys.modules", {"fitz": None}),
            patch("builtins.__import__", side_effect=ImportError("No module named 'fitz'")),
        ):
            result = _extract_images(Path("/fake.pdf"), "basic", {}, {"images_extracted": 0})
            assert result == []

    def test_non_pdf_returns_empty(self):
        from pathlib import Path

        from plugins.markitdown_plus_import import _extract_images
        result = _extract_images(Path("/fake.docx"), "basic", {}, {})
        assert result == []
