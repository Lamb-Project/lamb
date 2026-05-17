"""LLM-based concept and relationship extraction for KG-RAG indexing."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import config as config_module
from plugins.base import LLMExtractionFunction, LLMExtractionRegistry


logger = logging.getLogger("lamb-kb")


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    text: str
    parent_text: str
    metadata: Dict[str, Any]


@dataclass(frozen=True)
class ExtractedEntity:
    name: str
    display_name: str
    entity_type: str = "concept"
    description: str = ""
    confidence: float = 1.0


@dataclass(frozen=True)
class ExtractedRelationship:
    source: str
    target: str
    relation: str
    description: str = ""
    evidence: str = ""
    confidence: float = 1.0
    chunk_id: str = ""


@dataclass
class GraphExtraction:
    concepts_by_chunk: Dict[str, List[str]] = field(default_factory=dict)
    entities: Dict[str, ExtractedEntity] = field(default_factory=dict)
    relationships: List[ExtractedRelationship] = field(default_factory=list)

    @property
    def all_concepts(self) -> Set[str]:
        return set(self.entities)


def normalize_concept(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"[^\w\- ]", " ", value.lower(), flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip(" -_")
    return value


def normalize_relation(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"[^\w]+", "_", value.lower(), flags=re.UNICODE)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:64] or "related_to"


def _clean_text(value: Any, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _confidence(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, min(1.0, numeric))


def _is_valid_entity_name(value: str) -> bool:
    cleaned = _clean_text(value, limit=140)
    normalized = normalize_concept(cleaned)
    if len(normalized) < 2 or len(normalized) > 120:
        return False
    if not any(char.isalpha() or char.isdigit() for char in normalized):
        return False
    if cleaned[0].isdigit():
        return False
    if re.search(r"\.[a-z0-9]{1,8}$", cleaned.lower()):
        return False
    if normalized.endswith(" md"):
        return False
    if "\n" in cleaned or cleaned.count(".") > 1:
        return False
    if len(cleaned.split()) > 8:
        return False
    return True


class ConceptExtractor:
    """Extract graph-ready concepts and typed relationships from text chunks."""

    def __init__(
        self,
        kg_config: Optional[Dict[str, Any]] = None,
        backend: Optional[LLMExtractionFunction] = None,
        *,
        vendor: Optional[str] = None,
        model: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """Build an extractor.

        Resolution order for the extraction backend:
          1. An explicit ``backend`` argument (used by tests).
          2. A per-collection ``vendor`` / ``model`` (passed from the
             ingestion pipeline based on the collection's stored config).
          3. The server-level KG_RAG_* env defaults via ``kg_config``.

        ``api_key`` is request-scoped (ADR-4): when None, the chosen
        backend falls back to its env-configured key.
        """
        self.config = kg_config or config_module.get_kg_rag_config()
        self.chat_model = self.config.get("chat_model") or "gpt-4o-mini"
        self.model = model or self.config.get("extraction_model") or self.chat_model
        configured_workers = int(self.config.get("extraction_max_workers") or 1)
        self.max_workers = max(1, min(16, configured_workers))

        timeout_seconds = float(self.config.get("openai_timeout_seconds") or 60.0)

        if backend is not None:
            self.backend: Optional[LLMExtractionFunction] = backend
        else:
            # Default to OpenAI for back-compat with collections created
            # before the vendor field existed.
            resolved_vendor = vendor or "openai"
            resolved_key = (
                api_key
                if api_key is not None
                else (self.config.get("openai_api_key") or "")
            )
            resolved_endpoint = api_endpoint or ""
            try:
                self.backend = LLMExtractionRegistry.build(
                    resolved_vendor,
                    model=self.model,
                    api_key=resolved_key,
                    api_endpoint=resolved_endpoint,
                    timeout_seconds=timeout_seconds,
                )
            except ValueError as exc:
                logger.warning(
                    "KG-RAG: extraction vendor '%s' is not registered: %s",
                    resolved_vendor,
                    exc,
                )
                self.backend = None

    def extract_for_chunks(self, chunks: List[TextChunk]) -> GraphExtraction:
        if not chunks:
            return GraphExtraction()

        extraction = GraphExtraction(
            concepts_by_chunk={chunk.chunk_id: [] for chunk in chunks}
        )
        if self.backend is None:
            return extraction

        parent_groups: Dict[str, List[TextChunk]] = {}
        for chunk in chunks:
            parent_text = chunk.parent_text or chunk.text
            parent_groups.setdefault(parent_text, []).append(chunk)

        groups = list(parent_groups.items())
        if self.max_workers > 1 and len(groups) > 1:
            worker_count = min(self.max_workers, len(groups))
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = [
                    executor.submit(self._extract_parent_group, parent_text, group)
                    for parent_text, group in groups
                ]
                group_results = [future.result() for future in futures]
        else:
            group_results = [
                self._extract_parent_group(parent_text, group)
                for parent_text, group in groups
            ]

        for group, parent_extraction in group_results:

            for entity_name, entity in parent_extraction.entities.items():
                extraction.entities.setdefault(entity_name, entity)
            extraction.relationships.extend(parent_extraction.relationships)

            concept_names = sorted(parent_extraction.entities)
            for chunk in group:
                extraction.concepts_by_chunk[chunk.chunk_id] = concept_names

        return extraction

    def _extract_parent_group(
        self, parent_text: str, group: List[TextChunk]
    ) -> Tuple[List[TextChunk], GraphExtraction]:
        source_labels = [
            str(
                chunk.metadata.get("source_label")
                or chunk.metadata.get("filename")
                or chunk.chunk_id
            )
            for chunk in group
        ]
        payload = self._extract_parent_text(parent_text, source_labels)
        return group, self._parse_payload(payload, group[0].chunk_id)

    def _extract_parent_text(
        self, text: str, source_labels: List[str]
    ) -> Dict[str, Any]:
        system = (
            "You extract knowledge-graph data for GraphRAG indexing. "
            "Work for any domain and any document language. Do not use a fixed vocabulary. "
            "Preserve entity names in the document language. Extract only entities or concepts that are explicit, specific, and useful for retrieval. "
            "Do not output stopwords, generic verbs, generic adjectives, whole sentences, or vague phrases. "
            "Extract persistent relationships only when the text states or strongly implies a typed connection. "
            "Before returning, audit the graph and remove common nouns, example values, filenames, schema/property names, section labels, and entities that would not be meaningful outside this text. "
            "Discard triples whose source or target is merely an example rank, a generic answer/evidence placeholder, a file/container word, or a schema field. "
            "Prefer high-level named entities, technical terms, methods, systems, metrics, and domain concepts that participate in useful relationships. If unsure, omit the item. "
            "Return only valid JSON matching the requested object shape."
        )
        user = {
            "task": "Extract entities and typed relationships from this text unit.",
            "source_labels": source_labels,
            "output_contract": {
                "entities": [
                    {
                        "name": "canonical entity or concept name from the text",
                        "type": "short type such as person, organization, concept, technology, metric, method, place, event",
                        "description": "one short description grounded in the text",
                        "confidence": "number from 0 to 1",
                    }
                ],
                "relationships": [
                    {
                        "source": "entity name exactly as used in entities",
                        "target": "entity name exactly as used in entities",
                        "relation": "short verb phrase such as uses, stores, improves, depends_on, evaluates",
                        "description": "one short explanation grounded in the text",
                        "evidence": "short quote or paraphrase from the text",
                        "confidence": "number from 0 to 1",
                    }
                ],
            },
            # Doubled the per-chunk caps relative to the original
            # legacy budget: small Wikipedia-style paragraphs routinely
            # mention 10+ named entities, and the previous max=5 left
            # bridging entities outside the graph. Cost stays bounded by
            # the per-call ``max_tokens`` of the chat completion.
            "limits": {"max_entities": 12, "max_relationships": 12},
            "text": text[:6000],
        }
        if self.backend is None:
            return {"entities": [], "relationships": []}
        fallback = self.chat_model if self.chat_model != self.model else None
        parsed = self.backend.chat_json(
            system=system,
            user=json.dumps(user, ensure_ascii=False),
            fallback_model=fallback,
        )
        return parsed if isinstance(parsed, dict) else {
            "entities": [],
            "relationships": [],
        }

    def _parse_payload(self, payload: Dict[str, Any], chunk_id: str) -> GraphExtraction:
        entities: Dict[str, ExtractedEntity] = {}
        raw_entities = payload.get("entities", [])
        if not isinstance(raw_entities, list):
            raw_entities = []

        for item in raw_entities[:12]:
            if not isinstance(item, dict):
                continue
            display_name = _clean_text(item.get("name"), limit=120)
            if not _is_valid_entity_name(display_name):
                continue
            name = normalize_concept(display_name)
            entities[name] = ExtractedEntity(
                name=name,
                display_name=display_name,
                entity_type=normalize_relation(item.get("type") or "concept"),
                description=_clean_text(item.get("description"), limit=600),
                confidence=_confidence(item.get("confidence")),
            )

        relationships: List[ExtractedRelationship] = []
        raw_relationships = payload.get("relationships", [])
        if not isinstance(raw_relationships, list):
            raw_relationships = []

        related_names: Set[str] = set()
        for item in raw_relationships[:12]:
            if not isinstance(item, dict):
                continue
            source = normalize_concept(_clean_text(item.get("source"), limit=120))
            target = normalize_concept(_clean_text(item.get("target"), limit=120))
            if source == target or source not in entities or target not in entities:
                continue
            relation = normalize_relation(item.get("relation") or "related_to")
            relationships.append(
                ExtractedRelationship(
                    source=source,
                    target=target,
                    relation=relation,
                    description=_clean_text(item.get("description"), limit=600),
                    evidence=_clean_text(item.get("evidence"), limit=500),
                    confidence=_confidence(item.get("confidence")),
                    chunk_id=chunk_id,
                )
            )
            related_names.update({source, target})

        if related_names:
            entities = {
                name: entity
                for name, entity in entities.items()
                if name in related_names
            }

        return GraphExtraction(
            concepts_by_chunk={chunk_id: sorted(entities)},
            entities=entities,
            relationships=relationships,
        )
