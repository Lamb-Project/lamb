"""Unit tests for each chunking strategy.

These tests exercise the strategies directly (no HTTP) so failures point to
chunking logic rather than API wiring.
"""


from plugins.base import DocumentInput
from plugins.chunking.by_page import ByPageChunking
from plugins.chunking.by_section import BySectionChunking
from plugins.chunking.hierarchical import HierarchicalChunking
from plugins.chunking.simple import SimpleChunking


def _doc(text: str, **kwargs) -> DocumentInput:
    return DocumentInput(
        source_item_id=kwargs.get("source_item_id", "item-1"),
        title=kwargs.get("title", "Test doc"),
        text=text,
        permalinks=kwargs.get(
            "permalinks",
            {
                "original": "/docs/o/l/i/original/file.txt",
                "full_markdown": "/docs/o/l/i/content/full.md",
                "pages": ["/docs/o/l/i/content/pages/page_001.md"],
            },
        ),
        pages=kwargs.get("pages", []),
        extra_metadata=kwargs.get("extra_metadata", {}),
    )


# --- Simple chunking ---


def test_simple_chunking_splits_text() -> None:
    doc = _doc("a " * 5000)  # ~10k chars
    chunks = SimpleChunking().chunk(doc, {"chunk_size": 500, "chunk_overlap": 50})
    assert len(chunks) > 1
    assert all(c.metadata["source_item_id"] == "item-1" for c in chunks)
    assert all(c.metadata["chunking_strategy"] == "simple" for c in chunks)
    assert all("chunk_index" in c.metadata for c in chunks)
    assert all("chunk_count" in c.metadata for c in chunks)
    assert all(c.metadata["source_title"] == "Test doc" for c in chunks)


def test_simple_chunking_metadata_only_primitives() -> None:
    doc = _doc("short text")
    chunks = SimpleChunking().chunk(doc, {})
    for c in chunks:
        for k, v in c.metadata.items():
            assert isinstance(v, (str, int, float, bool)) or v is None, (
                f"metadata[{k}]={v!r} is not a primitive"
            )


def test_simple_chunking_permalinks_in_metadata() -> None:
    doc = _doc("some text here")
    chunks = SimpleChunking().chunk(doc, {})
    assert chunks[0].metadata.get("permalink_original").endswith("file.txt")
    assert chunks[0].metadata.get("permalink_markdown").endswith("full.md")


# --- Hierarchical chunking ---


def test_hierarchical_chunking_with_headers() -> None:
    text = """# Title

Preamble intro text.

## Section A

Body of section A. Body of section A. Body of section A.

## Section B

Body of section B. More text here for chunking.
"""
    chunks = HierarchicalChunking().chunk(
        _doc(text),
        {"parent_chunk_size": 500, "child_chunk_size": 100, "child_chunk_overlap": 20},
    )
    assert len(chunks) >= 2
    # Every child should carry parent_text + hierarchical metadata.
    for c in chunks:
        assert c.metadata["chunking_strategy"] == "hierarchical"
        assert c.metadata["chunk_level"] == "child"
        assert "parent_text" in c.metadata
        assert isinstance(c.metadata["parent_text"], str) and c.metadata["parent_text"]
        assert "parent_chunk_id" in c.metadata
        assert "child_chunk_id" in c.metadata


def test_hierarchical_chunking_preamble_labeled() -> None:
    text = """This is preamble.

## Later Section

Later content.
"""
    chunks = HierarchicalChunking().chunk(_doc(text), {})
    # At least one chunk belongs to the Preamble parent.
    titles = {c.metadata.get("section_title") for c in chunks}
    assert any("Preamble" in t for t in titles if t)


# --- By-page chunking ---


def test_by_page_uses_pre_split_pages() -> None:
    doc = _doc(
        "ignored full text",
        pages=[
            {"page_number": 1, "text": "Page 1 content"},
            {"page_number": 2, "text": "Page 2 content"},
            {"page_number": 3, "text": "Page 3 content"},
        ],
    )
    chunks = ByPageChunking().chunk(doc, {"pages_per_chunk": 1})
    assert len(chunks) == 3
    assert "Page 1" in chunks[0].text
    assert chunks[0].metadata.get("page_range") == "1"


def test_by_page_merges_pages() -> None:
    doc = _doc(
        "ignored",
        pages=[
            {"page_number": 1, "text": "P1"},
            {"page_number": 2, "text": "P2"},
            {"page_number": 3, "text": "P3"},
            {"page_number": 4, "text": "P4"},
        ],
    )
    chunks = ByPageChunking().chunk(doc, {"pages_per_chunk": 2})
    assert len(chunks) == 2
    assert chunks[0].metadata.get("page_range") == "1-2"
    assert chunks[1].metadata.get("page_range") == "3-4"


def test_by_page_parses_html_markers() -> None:
    text = """Preamble.

<!-- Page 1 -->
Content of page one.

<!-- Page 2 -->
Content of page two.
"""
    chunks = ByPageChunking().chunk(_doc(text), {})
    assert len(chunks) >= 2


def test_by_page_falls_back_to_simple() -> None:
    """When no pages and no markers, should fall back to simple chunking."""
    text = "plain text " * 200
    chunks = ByPageChunking().chunk(_doc(text), {})
    assert len(chunks) >= 1


# --- By-section chunking ---


def test_by_section_splits_on_h2() -> None:
    text = """# Title

Intro text.

## Section One

Body one.

## Section Two

Body two.

## Section Three

Body three.
"""
    chunks = BySectionChunking().chunk(
        _doc(text), {"split_on_heading": 2, "headings_per_chunk": 1}
    )
    assert len(chunks) >= 3
    assert all(c.metadata["chunking_strategy"] == "by_section" for c in chunks)


def test_by_section_falls_back_when_no_headings() -> None:
    chunks = BySectionChunking().chunk(_doc("plain text no headings"), {})
    assert len(chunks) >= 1
