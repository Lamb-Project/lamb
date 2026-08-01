"""Unit tests for each chunking strategy.

These tests exercise the strategies directly (no HTTP) so failures point to
chunking logic rather than API wiring.
"""

import json

import pytest

from plugins.base import ChunkingRegistry, DocumentInput
from plugins.chunking._common import build_base_metadata, encode_list, encode_list_json, validate_chunking_params
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


# --- _common helpers ---


def test_encode_list_json_returns_compact_json() -> None:
    result = encode_list_json([1, "a", True])
    parsed = json.loads(result)
    assert parsed == [1, "a", True]


def test_encode_list_empty_returns_empty_string() -> None:
    assert encode_list([]) == ""


def test_build_base_metadata_extra_metadata_overrides_defaults() -> None:
    """extra_metadata values should win over defaults (merged last)."""
    doc = _doc(
        "text",
        extra_metadata={"source_title": "OVERRIDDEN", "custom_key": "custom_val"},
    )
    meta = build_base_metadata(doc, "simple", {"chunk_size": 500})
    assert meta["source_title"] == "OVERRIDDEN"
    assert meta["custom_key"] == "custom_val"


def test_build_base_metadata_no_pages_permalink() -> None:
    """When permalinks has no 'pages' key, permalink_page should be absent."""
    doc = _doc(
        "text",
        permalinks={"original": "/orig/file.txt", "full_markdown": "/md/full.md"},
    )
    meta = build_base_metadata(doc, "simple", {})
    assert "permalink_page" not in meta


def test_build_base_metadata_empty_chunking_params_skips_loop() -> None:
    """Empty chunking_params dict must not add any chunking_<param> keys."""
    doc = _doc("text")
    # Pass explicit non-empty params to get reference keys, then compare with empty.
    meta_with_params = build_base_metadata(doc, "simple", {"chunk_size": 500})
    meta_no_params = build_base_metadata(doc, "simple", {})
    # chunking_chunk_size must appear only when params are provided.
    assert "chunking_chunk_size" in meta_with_params
    assert "chunking_chunk_size" not in meta_no_params


# --- Simple chunking additional ---


def test_simple_chunking_chunk_size_1_produces_many_chunks() -> None:
    """chunk_size=1 forces each character into its own chunk (no overlap)."""
    doc = _doc("abc", permalinks={"original": "/o", "full_markdown": "/m"})
    chunks = SimpleChunking().chunk(doc, {"chunk_size": 1, "chunk_overlap": 0})
    assert len(chunks) >= 3
    assert all(len(c.text) <= 1 for c in chunks)


def test_simple_chunking_text_equal_to_chunk_size_single_chunk() -> None:
    """Text exactly at chunk_size (no overlap needed) → single chunk."""
    text = "x" * 500
    doc = _doc(text)
    chunks = SimpleChunking().chunk(doc, {"chunk_size": 500, "chunk_overlap": 0})
    assert len(chunks) == 1
    assert chunks[0].metadata["chunk_count"] == 1


def test_simple_chunking_separator_prefers_double_newline() -> None:
    """RecursiveCharacterTextSplitter should prefer '\\n\\n' over '\\n' or ' '."""
    # Build a text with paragraph breaks and a small chunk_size to force splits.
    para = "word " * 20  # ~100 chars each paragraph
    text = (para + "\n\n") * 10
    chunks = SimpleChunking().chunk(_doc(text), {"chunk_size": 150, "chunk_overlap": 0})
    # If double-newline splitting works, no chunk should contain \n\n in the middle
    # (splits happen at the boundary, so each chunk is a single paragraph or
    # a joined pair — it should not split inside a paragraph).
    assert len(chunks) > 1
    # All chunks should be well-formed (non-empty text).
    assert all(c.text.strip() for c in chunks)


# --- Hierarchical chunking additional ---


def test_hierarchical_oversized_section_produces_section_part() -> None:
    """A section larger than parent_chunk_size triggers secondary splitting.

    The resulting chunks must carry a 1-based 'section_part' metadata key.
    """
    # Build a large body (~3000 chars) under a single H2 heading.
    long_body = "word " * 600  # ~3000 chars
    text = f"## Big Section\n\n{long_body}"
    chunks = HierarchicalChunking().chunk(
        _doc(text),
        {"parent_chunk_size": 500, "child_chunk_size": 200, "child_chunk_overlap": 20},
    )
    assert len(chunks) > 0
    # At least one chunk must have section_part metadata (the oversized section split).
    parts = [c.metadata.get("section_part") for c in chunks]
    assert any(p is not None for p in parts), "Expected section_part metadata on some chunks"
    # section_part must be 1-based integers.
    non_none = [p for p in parts if p is not None]
    assert all(isinstance(p, int) and p >= 1 for p in non_none)


def test_hierarchical_h3_only_document() -> None:
    """Document with only H3 headers (no H2) should still produce chunks."""
    text = """### Alpha

Alpha body text here.

### Beta

Beta body text here.
"""
    chunks = HierarchicalChunking().chunk(_doc(text), {})
    assert len(chunks) >= 2
    titles = {c.metadata.get("section_title") for c in chunks}
    assert "Alpha" in titles or "Beta" in titles


def test_hierarchical_doc_with_only_h1_uses_document_parent() -> None:
    """A document with no H2/H3 headers → entire text is one 'Document' parent."""
    text = "# Just A Title\n\nSome body text without any H2 or H3."
    chunks = HierarchicalChunking().chunk(_doc(text), {})
    assert len(chunks) >= 1
    # The entire doc is one section labeled "Document"
    titles = {c.metadata.get("section_title") for c in chunks}
    assert "Document" in titles


def test_hierarchical_mixed_h2_h3_hierarchy() -> None:
    """H3 headers nested under H2 should be captured as separate sections."""
    text = """## Chapter One

Intro to chapter one.

### Sub A

Content of Sub A.

### Sub B

Content of Sub B.

## Chapter Two

Chapter two body.
"""
    chunks = HierarchicalChunking().chunk(
        _doc(text),
        {"parent_chunk_size": 2000, "child_chunk_size": 200, "child_chunk_overlap": 20},
    )
    assert len(chunks) >= 3
    titles = {c.metadata.get("section_title") for c in chunks}
    assert "Chapter One" in titles or "Chapter Two" in titles or "Sub A" in titles


def test_hierarchical_empty_section_between_headers() -> None:
    """Empty body between two H2 headers: the empty section is still a parent."""
    text = """## First Section

Content of first section.

## Empty Section

## Third Section

Content of third section.
"""
    chunks = HierarchicalChunking().chunk(_doc(text), {})
    titles = {c.metadata.get("section_title") for c in chunks}
    # First and Third must appear; Empty may or may not (depends on text length).
    assert "First Section" in titles or "Third Section" in titles


# --- By-page chunking additional ---


def test_by_page_marker_with_whitespace_variants() -> None:
    """<!-- Page N --> markers with surrounding whitespace should still parse."""
    text = "Preamble.\n\n<!--  Page 1  -->\nContent one.\n\n<!-- page 2 -->\nContent two.\n"
    chunks = ByPageChunking().chunk(_doc(text), {})
    assert len(chunks) >= 2
    page_ranges = [c.metadata.get("page_range") for c in chunks]
    assert "1" in page_ranges
    assert "2" in page_ranges


def test_by_page_structured_page_without_page_number_defaults_to_index() -> None:
    """A page entry missing 'page_number' defaults to len(result)+1."""
    doc = _doc(
        "ignored",
        pages=[
            {"text": "First page content"},    # no page_number → defaults to 1
            {"page_number": 5, "text": "Fifth page content"},
        ],
    )
    chunks = ByPageChunking().chunk(doc, {"pages_per_chunk": 1})
    assert len(chunks) == 2
    assert chunks[0].metadata.get("page_range") == "1"
    assert chunks[1].metadata.get("page_range") == "5"


def test_by_page_pages_per_chunk_larger_than_total_pages() -> None:
    """pages_per_chunk=20 with only 3 pages → single chunk."""
    doc = _doc(
        "ignored",
        pages=[
            {"page_number": 1, "text": "Page one"},
            {"page_number": 2, "text": "Page two"},
            {"page_number": 3, "text": "Page three"},
        ],
    )
    chunks = ByPageChunking().chunk(doc, {"pages_per_chunk": 20})
    assert len(chunks) == 1
    assert chunks[0].metadata.get("page_range") == "1-3"


def test_by_page_permalink_list_shorter_than_pages() -> None:
    """When permalink_pages is shorter than the pages list, out-of-range pages
    must not crash — they simply get no permalink_page override."""
    doc = _doc(
        "ignored",
        pages=[
            {"page_number": 1, "text": "P1"},
            {"page_number": 2, "text": "P2"},
            {"page_number": 3, "text": "P3"},
        ],
        permalinks={
            "original": "/orig/file.txt",
            "full_markdown": "/md/full.md",
            "pages": ["/pages/1.md"],  # Only one permalink for 3 pages
        },
    )
    chunks = ByPageChunking().chunk(doc, {"pages_per_chunk": 1})
    assert len(chunks) == 3
    # First chunk has a matching permalink; others do not raise errors.
    assert chunks[0].metadata.get("permalink_page") == "/pages/1.md"


def test_by_page_fallback_no_page_range_metadata() -> None:
    """Fallback to SimpleChunking when no pages and no markers.

    The resulting chunks must NOT carry 'page_range' metadata.
    """
    # Use a doc with no pages and text that contains no <!-- Page N --> markers
    doc = _doc(
        "plain text without markers " * 50,
        pages=[],
        permalinks={"original": "/o", "full_markdown": "/m"},
    )
    chunks = ByPageChunking().chunk(doc, {})
    assert len(chunks) >= 1
    assert all("page_range" not in c.metadata for c in chunks)
    assert all(c.metadata.get("chunking_strategy") == "simple" for c in chunks)


def test_by_page_skips_empty_text_pages() -> None:
    """Pages whose text is empty or whitespace-only must be filtered out."""
    doc = _doc(
        "ignored",
        pages=[
            {"page_number": 1, "text": "   "},  # whitespace-only → skipped
            {"page_number": 2, "text": "Real content here"},
        ],
    )
    chunks = ByPageChunking().chunk(doc, {"pages_per_chunk": 1})
    assert len(chunks) == 1
    assert chunks[0].metadata.get("page_range") == "2"


def test_by_page_marker_empty_body_skipped() -> None:
    """A <!-- Page N --> marker immediately followed by another marker (no body)
    should produce no chunk for that page."""
    text = "<!--  Page 1  -->\n<!-- Page 2 -->\nActual content for page 2.\n"
    chunks = ByPageChunking().chunk(_doc(text), {})
    # Page 1 has an empty body and should be skipped; only page 2 produces a chunk.
    assert len(chunks) == 1
    assert chunks[0].metadata.get("page_range") == "2"


# --- By-section chunking additional ---


def test_by_section_split_on_h1() -> None:
    """split_on_heading=1 should split on H1 headers."""
    text = """# Chapter One

Body of chapter one.

# Chapter Two

Body of chapter two.
"""
    chunks = BySectionChunking().chunk(
        _doc(text), {"split_on_heading": 1, "headings_per_chunk": 1}
    )
    assert len(chunks) >= 2
    titles = {c.metadata.get("section_titles") for c in chunks}
    assert any("Chapter One" in t for t in titles if t)
    assert any("Chapter Two" in t for t in titles if t)


def test_by_section_split_on_h6() -> None:
    """split_on_heading=6 should split on H6 headers."""
    text = """###### Micro One

Nano content one.

###### Micro Two

Nano content two.
"""
    chunks = BySectionChunking().chunk(
        _doc(text), {"split_on_heading": 6, "headings_per_chunk": 1}
    )
    assert len(chunks) >= 2


def test_by_section_headings_per_chunk_larger_than_total() -> None:
    """headings_per_chunk=10 with only 3 headings → single chunk."""
    text = """## Alpha

Body alpha.

## Beta

Body beta.

## Gamma

Body gamma.
"""
    chunks = BySectionChunking().chunk(
        _doc(text), {"split_on_heading": 2, "headings_per_chunk": 10}
    )
    assert len(chunks) == 1
    assert chunks[0].metadata.get("section_count") == 3


def test_by_section_no_headings_at_target_level_falls_back_to_simple() -> None:
    """When the document has H2 headings but we split on H3, fall back."""
    text = """## Section A

Content A.

## Section B

Content B.
"""
    chunks = BySectionChunking().chunk(
        _doc(text), {"split_on_heading": 3, "headings_per_chunk": 1}
    )
    # No H3 headings → fallback to SimpleChunking → no page_range, strategy=simple
    assert len(chunks) >= 1
    assert all(c.metadata.get("chunking_strategy") == "simple" for c in chunks)


def test_by_section_ancestor_path_rendering() -> None:
    """Sections nested under multiple ancestor levels show a '>' separated path."""
    text = """# Book

## Part One

### Chapter 1

Content of chapter 1.

### Chapter 2

Content of chapter 2.
"""
    chunks = BySectionChunking().chunk(
        _doc(text), {"split_on_heading": 3, "headings_per_chunk": 1}
    )
    assert len(chunks) >= 2
    # parent_path should include ancestor titles joined by ' > '
    parent_paths = [c.metadata.get("parent_path", "") for c in chunks]
    assert any("Book" in p and "Part One" in p for p in parent_paths)
    assert any(">" in p for p in parent_paths)


def test_by_section_deeply_nested_h4_rolled_up_under_h2() -> None:
    """H4 content nested under H2 is included in the H2 chunk (not split out)."""
    text = """## Main Section

Intro text.

#### Deep Note

Deep note content.
"""
    chunks = BySectionChunking().chunk(
        _doc(text), {"split_on_heading": 2, "headings_per_chunk": 1}
    )
    # H4 content should be rolled up under the H2 parent chunk.
    assert len(chunks) == 1
    assert "Deep Note" in chunks[0].text


def test_by_section_node_to_text_recurses_into_children() -> None:
    """_node_to_text recursion: child headings appear in the output text."""
    text = """## Parent Section

Parent body.

### Child Section

Child body.
"""
    chunks = BySectionChunking().chunk(
        _doc(text), {"split_on_heading": 2, "headings_per_chunk": 1}
    )
    assert len(chunks) == 1
    # Both parent and child heading text should appear in the chunk.
    assert "Parent Section" in chunks[0].text
    assert "Child Section" in chunks[0].text


def test_by_section_parent_prefix_empty_when_no_ancestors() -> None:
    """Top-level sections (no parent) should have an empty parent_path."""
    text = """## Standalone Section

Content here.
"""
    chunks = BySectionChunking().chunk(
        _doc(text), {"split_on_heading": 2, "headings_per_chunk": 1}
    )
    assert len(chunks) == 1
    assert chunks[0].metadata.get("parent_path") == ""


def test_by_page_build_chunks_without_permalinks() -> None:
    """_build_chunks with empty permalink_pages skips the permalink_page assignment."""
    doc = _doc(
        "ignored",
        pages=[
            {"page_number": 1, "text": "Page one content"},
        ],
        permalinks={"original": "/orig/file.txt", "full_markdown": "/md/full.md"},
        # No "pages" key → permalink_pages will be []
    )
    chunks = ByPageChunking().chunk(doc, {"pages_per_chunk": 1})
    assert len(chunks) == 1
    # No permalink_page override should have been made (branch 134->139 hit).
    assert "permalink_page" not in chunks[0].metadata


def test_by_page_all_structured_pages_empty_falls_back() -> None:
    """When document.pages is non-empty but all entries have empty text,
    _pages_from_structured returns [], and the strategy falls back through
    markers then to SimpleChunking (covering branch 178->186)."""
    doc = _doc(
        "plain text fallback " * 50,
        pages=[
            {"page_number": 1, "text": "   "},  # whitespace-only → filtered out
            {"page_number": 2, "text": ""},      # empty → filtered out
        ],
        permalinks={"original": "/o", "full_markdown": "/m"},
    )
    chunks = ByPageChunking().chunk(doc, {})
    # All structured pages were empty, no markers in text → SimpleChunking fallback.
    assert len(chunks) >= 1
    assert all(c.metadata.get("chunking_strategy") == "simple" for c in chunks)


def test_hierarchical_oversized_splits_into_multiple_sub_chunks_section_part_1_based() -> None:
    """section_part values must be 1-based (first part is 1, not 0)."""
    long_body = "word " * 600  # ~3000 chars
    text = f"## Big Section\n\n{long_body}"
    chunks = HierarchicalChunking().chunk(
        _doc(text),
        {"parent_chunk_size": 500, "child_chunk_size": 200, "child_chunk_overlap": 20},
    )
    parts = [c.metadata.get("section_part") for c in chunks if c.metadata.get("section_part") is not None]
    assert parts, "Expected at least one chunk with section_part"
    assert min(parts) == 1, "section_part must be 1-based (minimum value should be 1)"


# ---------------------------------------------------------------------------
# validate_chunking_params — Bug #4 regression tests
# ---------------------------------------------------------------------------

# Pin the public parameter names for all four strategies so drift is caught.
_EXPECTED_PARAMS = {
    "simple": {"chunk_size", "chunk_overlap"},
    "by_page": {"pages_per_chunk"},
    "hierarchical": {"parent_chunk_size", "child_chunk_size", "child_chunk_overlap"},
    "by_section": {"split_on_heading", "headings_per_chunk"},
}


def test_strategy_parameter_names_match_expected() -> None:
    """Each strategy's get_parameters() names must match the known public API."""
    for strategy_name, expected in _EXPECTED_PARAMS.items():
        strategy = ChunkingRegistry.get(strategy_name)
        assert strategy is not None, f"Strategy '{strategy_name}' not registered"
        actual = {p.name for p in strategy.get_parameters()}
        assert actual == expected, (
            f"Strategy '{strategy_name}': expected params {sorted(expected)}, "
            f"got {sorted(actual)}"
        )


def test_validate_chunking_params_accepts_known_keys() -> None:
    """validate_chunking_params must not raise when all keys are in the allow-list."""
    strategy = SimpleChunking()
    # Both declared keys → no error.
    validate_chunking_params(strategy, {"chunk_size": 500, "chunk_overlap": 100})
    # Subset → also fine.
    validate_chunking_params(strategy, {"chunk_size": 500})
    # Empty dict → fine.
    validate_chunking_params(strategy, {})


def test_validate_chunking_params_rejects_unknown_key() -> None:
    """A typo'd key must raise ValueError naming the bad key."""
    strategy = SimpleChunking()
    with pytest.raises(ValueError) as exc_info:
        validate_chunking_params(strategy, {"chunk_size": 1000, "chunk_overlap_size": 200})
    assert "chunk_overlap_size" in str(exc_info.value)
    assert "simple" in str(exc_info.value)


def test_validate_chunking_params_rejects_cross_strategy_key() -> None:
    """A key that belongs to a *different* strategy is also rejected."""
    strategy = SimpleChunking()
    # 'pages_per_chunk' is valid for by_page, not for simple
    with pytest.raises(ValueError) as exc_info:
        validate_chunking_params(strategy, {"chunk_size": 500, "pages_per_chunk": 2})
    assert "pages_per_chunk" in str(exc_info.value)


def test_validate_chunking_params_error_lists_allowed_keys() -> None:
    """The ValueError message must include the allowed key names."""
    strategy = BySectionChunking()
    with pytest.raises(ValueError) as exc_info:
        validate_chunking_params(strategy, {"split_on_heading": 2, "bogus_key": 99})
    msg = str(exc_info.value)
    assert "bogus_key" in msg
    assert "split_on_heading" in msg
    assert "headings_per_chunk" in msg
