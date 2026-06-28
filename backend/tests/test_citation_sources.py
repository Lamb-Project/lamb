"""Tests for mapping LAMB RAG sources to the OpenWebUI citations schema."""

from urllib.parse import parse_qs, urlparse

from lamb.completions.citation_sources import build_owi_sources, build_sources_markdown
from creator_interface.permalink_signing import verify


def _source(n, **over):
    src = {
        "n": n,
        "title": "Doc",
        "score": 0.9,
        "text": "supporting excerpt",
        "permalink_markdown": "/docs/3/lib-1/item-1/content",
        "permalink_original": "/docs/3/lib-1/item-1/original/noa-ventura-cv.pdf",
    }
    src.update(over)
    return src


class TestBuildOwiSources:
    def test_empty_when_no_sources(self):
        assert build_owi_sources({"sources": []}) == []
        assert build_owi_sources(None) == []

    def test_shape_matches_owi_contract(self):
        out = build_owi_sources({"sources": [_source(1)]})
        assert len(out) == 1
        entry = out[0]
        # name == "1" so OWI auto-links the inline [1] marker.
        assert entry["source"]["name"] == "1"
        assert entry["metadata"][0]["name"] == "1"
        # document[] holds the excerpt under the real filename.
        assert entry["document"][0].startswith("**noa-ventura-cv.pdf**")
        assert "supporting excerpt" in entry["document"][0]
        assert entry["metadata"][0]["filename"] == "noa-ventura-cv.pdf"
        assert entry["distances"] == [0.9]

    def test_url_is_absolute_signed_and_verifiable(self):
        out = build_owi_sources({"sources": [_source(1)]})
        url = out[0]["source"]["url"]
        assert url.startswith("http")  # OWI only links http(s) urls
        parsed = urlparse(url)
        assert parsed.path == "/docs/public/3/lib-1/item-1/view"
        sig = parse_qs(parsed.query)["sig"][0]
        assert verify("3", "3/lib-1/item-1/view", sig) is True
        # filename carried for the page title / download
        assert parse_qs(parsed.query)["name"][0] == "noa-ventura-cv.pdf"

    def test_numbering_preserved_across_multiple_sources(self):
        out = build_owi_sources({"sources": [_source(1), _source(2, title="Doc2")]})
        assert [e["source"]["name"] for e in out] == ["1", "2"]

    def test_missing_score_yields_empty_distances(self):
        out = build_owi_sources({"sources": [_source(1, score=None)]})
        assert out[0]["distances"] == []

    def test_no_permalink_leaves_url_empty(self):
        src = {"n": 1, "title": "Doc", "text": "x"}
        out = build_owi_sources({"sources": [src]})
        # No permalink → no signed URL (OWI renders it non-clickable).
        assert out[0]["source"]["url"] == ""
        assert out[0]["document"][0].startswith("**Doc**")


class TestBuildSourcesMarkdown:
    def test_empty_when_no_sources(self):
        assert build_sources_markdown({"sources": []}) == ""
        assert build_sources_markdown(None) == ""

    def test_renders_clickable_numbered_list(self):
        md = build_sources_markdown({"sources": [_source(1)]})
        assert "**Sources**" in md
        # [N] marker plus a clickable markdown link to the signed view page.
        assert "[1] [noa-ventura-cv.pdf](http" in md
        # Not the reference-definition form (OWI strips "[1]: url").
        assert "[1]:" not in md

    def test_groups_chunks_from_same_item_into_one_line(self):
        # Two chunks from the same item → one line listing BOTH numbers so each
        # inline marker resolves: "[1][2] [filename](url)".
        a = _source(1)
        b = _source(2)  # same permalinks/item as _source default
        md = build_sources_markdown({"sources": [a, b]})
        assert md.count("[noa-ventura-cv.pdf](") == 1  # one clickable link
        assert "[1][2] [noa-ventura-cv.pdf](http" in md

    def test_distinct_items_each_listed(self):
        a = _source(1)
        b = _source(
            2,
            permalink_markdown="/docs/3/lib-2/item-2/content",
            permalink_original="/docs/3/lib-2/item-2/original/other.pdf",
        )
        md = build_sources_markdown({"sources": [a, b]})
        assert "noa-ventura-cv.pdf" in md and "other.pdf" in md
        assert "[1]" in md and "[2]" in md
