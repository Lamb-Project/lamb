"""Unit tests for ``services.concept_extraction``.

Covers the pure validation/normalization helpers, the ``ConceptExtractor``
backend-resolution logic, the sequential and threaded extraction paths, and
the JSON payload parsing (entity validation, relationship pruning, dropping
of entities that participate in no relationship).

A ``FakeBackend`` (a real ``LLMExtractionFunction`` subclass) stands in for
the vendor SDK, so no network or API key is touched.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pytest

from plugins.base import LLMExtractionFunction
from services.concept_extraction import (
    ConceptExtractor,
    ExtractedEntity,
    GraphExtraction,
    TextChunk,
    _clean_text,
    _confidence,
    _is_valid_entity_name,
    normalize_concept,
    normalize_relation,
)


class FakeBackend(LLMExtractionFunction):
    """Returns a payload chosen by matching a substring of the user text."""

    name = "fake"

    def __init__(self, *, by_text: Optional[Dict[str, dict]] = None, default=None):
        super().__init__(model="fake-model")
        self._by_text = by_text or {}
        self._default = default if default is not None else {
            "entities": [],
            "relationships": [],
        }
        self.calls: List[dict] = []

    def chat_json(self, *, system: str, user: str, fallback_model=None):
        self.calls.append(
            {"system": system, "user": user, "fallback_model": fallback_model}
        )
        decoded = json.loads(user)
        text = decoded.get("text", "")
        for needle, payload in self._by_text.items():
            if needle in text:
                return payload
        return self._default


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


def test_clean_text_collapses_whitespace_and_truncates():
    assert _clean_text("  a\n\t b   c ") == "a b c"
    assert _clean_text(None) == ""
    assert _clean_text("x" * 1000, limit=10) == "x" * 10


@pytest.mark.parametrize(
    "value,expected",
    [
        ("0.5", 0.5),
        (1.5, 1.0),  # clamped up
        (-2, 0.0),  # clamped down
        ("not-a-number", 1.0),  # default
        (None, 1.0),
    ],
)
def test_confidence_clamps_and_defaults(value, expected):
    assert _confidence(value) == expected


@pytest.mark.parametrize(
    "name",
    [
        "Machine Learning",
        "GPT-4",
        "Neo4j",
    ],
)
def test_is_valid_entity_name_accepts(name):
    assert _is_valid_entity_name(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "a",  # too short after normalization
        "x" * 200,  # too long
        "!!!",  # no alnum
        "3.14 pies",  # leading digit
        "report.pdf",  # file-extension suffix
        "readme md",  # ends with " md"
        "a. b. c",  # more than one period
        "one two three four five six seven eight nine",  # > 8 words
    ],
)
def test_is_valid_entity_name_rejects(name):
    assert _is_valid_entity_name(name) is False


def test_normalize_helpers_edge_cases():
    assert normalize_concept("Café Society!") == "cafe society"
    assert normalize_relation("Depends On") == "depends_on"
    assert normalize_relation("---") == "related_to"
    assert len(normalize_relation("x" * 200)) == 64


def test_graph_extraction_all_concepts():
    ext = GraphExtraction(
        entities={"a": ExtractedEntity(name="a", display_name="A")}
    )
    assert ext.all_concepts == {"a"}


# ---------------------------------------------------------------------------
# ConceptExtractor.__init__ backend resolution
# ---------------------------------------------------------------------------


def test_init_with_explicit_backend():
    be = FakeBackend()
    ex = ConceptExtractor(kg_config={"extraction_max_workers": 4}, backend=be)
    assert ex.backend is be
    # workers clamped to [1, 16].
    assert ex.max_workers == 4


def test_init_clamps_workers_to_16():
    ex = ConceptExtractor(
        kg_config={"extraction_max_workers": 999}, backend=FakeBackend()
    )
    assert ex.max_workers == 16


def test_init_unregistered_vendor_sets_backend_none(caplog):
    ex = ConceptExtractor(
        kg_config={"extraction_max_workers": 1},
        vendor="totally-unknown-vendor",
    )
    assert ex.backend is None


def test_init_builds_registered_vendor():
    # openai is a registered extraction vendor; building it must succeed even
    # without a key (the key only matters at call time).
    ex = ConceptExtractor(
        kg_config={"extraction_max_workers": 1, "openai_api_key": ""},
        vendor="openai",
        model="gpt-4o-mini",
    )
    assert ex.backend is not None
    assert ex.backend.name == "openai"


# ---------------------------------------------------------------------------
# extract_for_chunks
# ---------------------------------------------------------------------------


def _chunk(cid, text, parent=None, meta=None):
    return TextChunk(
        chunk_id=cid,
        text=text,
        parent_text=parent or "",
        metadata=meta or {},
    )


def test_extract_for_chunks_empty_returns_empty():
    ex = ConceptExtractor(backend=FakeBackend())
    out = ex.extract_for_chunks([])
    assert out.entities == {}
    assert out.concepts_by_chunk == {}


def test_extract_for_chunks_backend_none_returns_skeleton():
    ex = ConceptExtractor(backend=FakeBackend())
    ex.backend = None
    out = ex.extract_for_chunks([_chunk("c1", "hello")])
    assert out.concepts_by_chunk == {"c1": []}
    assert out.entities == {}


def test_extract_for_chunks_sequential_single_group():
    payload = {
        "entities": [
            {"name": "Machine Learning", "type": "concept", "confidence": 0.9},
            {"name": "Neural Network", "type": "concept"},
        ],
        "relationships": [
            {
                "source": "Machine Learning",
                "target": "Neural Network",
                "relation": "uses",
            }
        ],
    }
    be = FakeBackend(by_text={"deep learning": payload})
    ex = ConceptExtractor(kg_config={"extraction_max_workers": 1}, backend=be)
    out = ex.extract_for_chunks([_chunk("c1", "deep learning text")])
    assert set(out.entities) == {"machine learning", "neural network"}
    assert out.concepts_by_chunk["c1"] == ["machine learning", "neural network"]
    assert len(out.relationships) == 1
    assert out.relationships[0].chunk_id == "c1"


def test_extract_for_chunks_threaded_multiple_groups():
    payload_a = {
        "entities": [
            {"name": "Alpha One", "type": "concept"},
            {"name": "Alpha Two", "type": "concept"},
        ],
        "relationships": [
            {"source": "Alpha One", "target": "Alpha Two", "relation": "links"}
        ],
    }
    payload_b = {
        "entities": [
            {"name": "Beta One", "type": "concept"},
            {"name": "Beta Two", "type": "concept"},
        ],
        "relationships": [
            {"source": "Beta One", "target": "Beta Two", "relation": "links"}
        ],
    }
    be = FakeBackend(by_text={"alpha-doc": payload_a, "beta-doc": payload_b})
    ex = ConceptExtractor(kg_config={"extraction_max_workers": 4}, backend=be)
    chunks = [
        _chunk("a", "alpha-doc body", parent="alpha-doc body"),
        _chunk("b", "beta-doc body", parent="beta-doc body"),
    ]
    out = ex.extract_for_chunks(chunks)
    assert "alpha one" in out.entities and "beta one" in out.entities
    assert out.concepts_by_chunk["a"] == ["alpha one", "alpha two"]
    assert out.concepts_by_chunk["b"] == ["beta one", "beta two"]
    # Two parent groups -> two backend calls.
    assert len(be.calls) == 2


def test_extract_groups_chunks_by_parent_text():
    payload = {
        "entities": [
            {"name": "Shared Topic", "type": "concept"},
            {"name": "Other Topic", "type": "concept"},
        ],
        "relationships": [
            {"source": "Shared Topic", "target": "Other Topic", "relation": "rel"}
        ],
    }
    be = FakeBackend(default=payload)
    ex = ConceptExtractor(kg_config={"extraction_max_workers": 1}, backend=be)
    # Two chunks sharing one parent -> a single backend call, both chunks get
    # the same concept list.
    chunks = [
        _chunk("c1", "part one", parent="the parent"),
        _chunk("c2", "part two", parent="the parent"),
    ]
    out = ex.extract_for_chunks(chunks)
    assert len(be.calls) == 1
    assert out.concepts_by_chunk["c1"] == out.concepts_by_chunk["c2"]


# ---------------------------------------------------------------------------
# _extract_parent_text fallback-model wiring
# ---------------------------------------------------------------------------


def test_extract_parent_text_passes_fallback_when_models_differ():
    be = FakeBackend(default={"entities": [], "relationships": []})
    ex = ConceptExtractor(
        kg_config={
            "extraction_max_workers": 1,
            "chat_model": "gpt-4o-mini",
            "extraction_model": "gpt-4o",
        },
        backend=be,
    )
    ex.extract_for_chunks([_chunk("c1", "anything")])
    # model != chat_model -> chat_model is offered as the fallback.
    assert be.calls[0]["fallback_model"] == "gpt-4o-mini"


def test_extract_parent_text_no_fallback_when_models_equal():
    be = FakeBackend(default={"entities": [], "relationships": []})
    ex = ConceptExtractor(
        kg_config={
            "extraction_max_workers": 1,
            "chat_model": "gpt-4o-mini",
            "extraction_model": "gpt-4o-mini",
        },
        backend=be,
    )
    ex.extract_for_chunks([_chunk("c1", "anything")])
    assert be.calls[0]["fallback_model"] is None


def test_extract_parent_text_backend_none_returns_empty_lists():
    # Direct call covering the defensive guard inside _extract_parent_text.
    ex = ConceptExtractor(backend=FakeBackend())
    ex.backend = None
    out = ex._extract_parent_text("some text", ["label"])
    assert out == {"entities": [], "relationships": []}


def test_extract_parent_text_non_dict_payload_is_safe():
    be = FakeBackend(default=["not", "a", "dict"])  # backend returns a list
    ex = ConceptExtractor(kg_config={"extraction_max_workers": 1}, backend=be)
    out = ex.extract_for_chunks([_chunk("c1", "x")])
    assert out.entities == {}


# ---------------------------------------------------------------------------
# _parse_payload edge cases
# ---------------------------------------------------------------------------


def test_parse_payload_filters_invalid_and_prunes_unconnected():
    payload = {
        "entities": [
            {"name": "Valid Concept", "type": "concept"},
            {"name": "Connected A", "type": "concept"},
            {"name": "Connected B", "type": "concept"},
            {"name": "report.pdf"},  # invalid name -> dropped
            "not-a-dict",  # non-dict -> skipped
        ],
        "relationships": [
            # connects A<->B; "Valid Concept" has no relationship -> pruned.
            {"source": "Connected A", "target": "Connected B", "relation": "uses"},
            {"source": "X", "target": "Connected A", "relation": "bad"},  # X unknown
            {"source": "Connected A", "target": "Connected A", "relation": "self"},
            "non-dict-rel",
        ],
    }
    ex = ConceptExtractor(backend=FakeBackend())
    out = ex._parse_payload(payload, "chunk-1")
    # Only the two related concepts survive (pruning of unconnected entities).
    assert set(out.entities) == {"connected a", "connected b"}
    assert len(out.relationships) == 1
    assert out.relationships[0].relation == "uses"


def test_parse_payload_non_list_entities_and_relationships():
    ex = ConceptExtractor(backend=FakeBackend())
    out = ex._parse_payload(
        {"entities": "nope", "relationships": "nope"}, "chunk-1"
    )
    assert out.entities == {}
    assert out.relationships == []
    assert out.concepts_by_chunk == {"chunk-1": []}


def test_parse_payload_keeps_entities_when_no_relationships():
    # With no relationships there is nothing to prune against, so valid
    # entities are retained.
    payload = {
        "entities": [{"name": "Solo Concept", "type": "concept"}],
        "relationships": [],
    }
    ex = ConceptExtractor(backend=FakeBackend())
    out = ex._parse_payload(payload, "chunk-1")
    assert set(out.entities) == {"solo concept"}
