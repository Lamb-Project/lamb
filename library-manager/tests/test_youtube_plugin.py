"""Unit tests for ``plugins.youtube_transcript_import``.

``yt_dlp`` is import-mocked so nothing touches YouTube. Covers URL parsing,
SRT/VTT parsing, timestamp formatting, language-key resolution, the
fetch/download orchestration (manual vs auto, rate-limit, all-fail), and the
``import_content`` entry point.
"""

from __future__ import annotations

import os
import sys
import types

import pytest

import plugins.youtube_transcript_import as yt
from plugins.youtube_transcript_import import (
    YouTubeTranscriptImportPlugin,
    _build_source_ref,
    _parse_srt_content,
    _parse_youtube_url,
    _resolve_language_key,
    _seconds_to_timestamp,
)


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=abc12345678", "abc12345678"),
        ("https://youtu.be/xyz98765432", "xyz98765432"),
        ("https://example.com/watch?v=x", None),
        ("https://www.youtube.com/watch", None),
    ],
)
def test_parse_youtube_url(url, expected):
    assert _parse_youtube_url(url) == expected


@pytest.mark.parametrize(
    "seconds,expected",
    [(0, "00:00"), (65, "01:05"), (3661, "01:01:01")],
)
def test_seconds_to_timestamp(seconds, expected):
    assert _seconds_to_timestamp(seconds) == expected


def test_build_source_ref():
    ref = _build_source_ref("https://youtu.be/v", "v", "en")
    assert ref["type"] == "youtube"
    assert ref["video_id"] == "v"
    assert ref["video_url"].endswith("watch?v=v")


@pytest.mark.parametrize(
    "subs,lang,expected",
    [
        ({"en": []}, "en", "en"),          # exact
        ({"en-US": []}, "en", "en-US"),    # prefix
        ({"de": []}, "en", None),          # no match
        ({}, "en", None),                  # empty
    ],
)
def test_resolve_language_key(subs, lang, expected):
    assert _resolve_language_key(subs, lang) == expected


def test_parse_srt_content():
    srt = (
        "1\n"
        "00:00:01,000 --> 00:00:04,000\n"
        "Hello world\n\n"
        "2\n"
        "00:00:05,000 --> 00:00:08,000\n"
        "[music] Second line\n\n"
        "3\n"  # block with no timestamp -> skipped
        "just one line\n"
    )
    pieces = _parse_srt_content(srt)
    assert len(pieces) == 2
    assert pieces[0]["text"] == "Hello world"
    assert pieces[0]["start"] == 1.0
    assert pieces[1]["text"] == "Second line"  # [music] noise stripped


def test_parse_srt_content_empty():
    assert _parse_srt_content("") == []


def test_get_parameters():
    names = {p.name for p in YouTubeTranscriptImportPlugin().get_parameters()}
    assert names == {"language", "proxy_url"}


# ---------------------------------------------------------------------------
# yt_dlp mock + fetch orchestration
# ---------------------------------------------------------------------------

_SRT = (
    "1\n00:00:01,000 --> 00:00:03,000\nhello\n\n"
    "2\n00:00:04,000 --> 00:00:06,000\nworld\n"
)


def _real_fetch():
    """The conftest installs a file-cache wrapper around ``_fetch_transcript``;
    these tests target the real implementation underneath it."""
    return getattr(yt._fetch_transcript, "__wrapped__", yt._fetch_transcript)


def _install_fake_ytdlp(
    monkeypatch, *, info=None, extract_raises=None,
    download_raises=None, write_file=None,
):
    fake = types.ModuleType("yt_dlp")

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            if extract_raises is not None:
                raise extract_raises
            return info

        def download(self, urls):
            if download_raises is not None:
                raise download_raises
            if write_file is not None:
                fname, content = write_file
                outdir = os.path.dirname(self.opts["outtmpl"])
                with open(os.path.join(outdir, fname), "w", encoding="utf-8") as fh:
                    fh.write(content)

    fake.YoutubeDL = FakeYDL
    monkeypatch.setitem(sys.modules, "yt_dlp", fake)


def test_fetch_transcript_extract_info_failure(monkeypatch):
    _install_fake_ytdlp(monkeypatch, extract_raises=RuntimeError("network"))
    with pytest.raises(RuntimeError, match="Failed to fetch video info"):
        _real_fetch()("vid12345678", "en", None)


def test_fetch_transcript_no_subtitles(monkeypatch):
    _install_fake_ytdlp(monkeypatch, info={"subtitles": {}, "automatic_captions": {}})
    with pytest.raises(RuntimeError, match="No subtitles available"):
        _real_fetch()("vid12345678", "en", None)


def test_fetch_transcript_manual_success(monkeypatch):
    info = {"subtitles": {"en": [{}]}, "automatic_captions": {}}
    _install_fake_ytdlp(monkeypatch, info=info)
    # Isolate from _download_and_parse by stubbing it.
    monkeypatch.setattr(
        yt, "_download_and_parse",
        lambda **kw: [{"text": "hi", "start": 0.0, "duration": 1.0}],
    )
    pieces, label = _real_fetch()("vid12345678", "en", "http://proxy")
    assert label == "manual"
    assert pieces[0]["text"] == "hi"


def test_fetch_transcript_falls_back_to_auto(monkeypatch):
    info = {"subtitles": {}, "automatic_captions": {"en": [{}]}}
    _install_fake_ytdlp(monkeypatch, info=info)
    monkeypatch.setattr(
        yt, "_download_and_parse",
        lambda **kw: [{"text": "auto", "start": 0.0, "duration": 1.0}],
    )
    pieces, label = _real_fetch()("vid12345678", "en", None)
    assert label == "auto"


def test_fetch_transcript_rate_limited(monkeypatch):
    info = {"subtitles": {"en": [{}]}, "automatic_captions": {}}
    _install_fake_ytdlp(monkeypatch, info=info)

    def boom(**kw):
        raise RuntimeError("HTTP Error 429: Too Many Requests")

    monkeypatch.setattr(yt, "_download_and_parse", boom)
    with pytest.raises(RuntimeError, match="rate-limited"):
        _real_fetch()("vid12345678", "en", None)


def test_fetch_transcript_all_attempts_fail(monkeypatch):
    info = {"subtitles": {"en": [{}]}, "automatic_captions": {}}
    _install_fake_ytdlp(monkeypatch, info=info)
    monkeypatch.setattr(
        yt, "_download_and_parse",
        lambda **kw: (_ for _ in ()).throw(RuntimeError("generic failure")),
    )
    with pytest.raises(RuntimeError, match="Could not download subtitles"):
        _real_fetch()("vid12345678", "en", None)


# ---------------------------------------------------------------------------
# _download_and_parse
# ---------------------------------------------------------------------------


def test_download_and_parse_success(monkeypatch):
    _install_fake_ytdlp(monkeypatch, write_file=("video.en.srt", _SRT))
    pieces = yt._download_and_parse(
        url="https://youtu.be/v", language_key="en",
        source_label="manual", proxy_url=None,
    )
    assert [p["text"] for p in pieces] == ["hello", "world"]


def test_download_and_parse_no_subtitle_files(monkeypatch):
    # download writes nothing -> no .srt/.vtt files found.
    _install_fake_ytdlp(monkeypatch, write_file=None)
    out = yt._download_and_parse(
        url="https://youtu.be/v", language_key="en",
        source_label="auto", proxy_url=None,
    )
    assert out == []


def test_download_and_parse_download_error_strips_prefix(monkeypatch):
    _install_fake_ytdlp(
        monkeypatch, download_raises=RuntimeError("ERROR: video unavailable")
    )
    with pytest.raises(RuntimeError) as exc:
        yt._download_and_parse(
            url="https://youtu.be/v", language_key="en",
            source_label="manual", proxy_url="http://proxy",
        )
    assert "video unavailable" in str(exc.value)
    assert "ERROR:" not in str(exc.value)


# ---------------------------------------------------------------------------
# import_content
# ---------------------------------------------------------------------------


def test_import_content_invalid_url():
    with pytest.raises(ValueError, match="Could not extract video ID"):
        YouTubeTranscriptImportPlugin().import_content("https://example.com/no-video")


def test_import_content_success(monkeypatch):
    monkeypatch.setattr(
        yt, "_fetch_transcript",
        lambda vid, lang, proxy: (
            [{"text": "hello", "start": 1.0, "duration": 2.0}], "manual"
        ),
    )
    result = YouTubeTranscriptImportPlugin().import_content(
        "https://www.youtube.com/watch?v=abc12345678", language="en"
    )
    assert "Transcript:" in result.full_text
    assert "**[00:01]** hello" in result.full_text
    assert result.metadata["subtitle_source"] == "manual"
    assert result.metadata["video_id"] == "abc12345678"
