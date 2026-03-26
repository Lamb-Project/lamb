# Semantic Graph Enhancement for lamb-kb-server

**Version:** 0.1.0 (Planning Document)  
**Created:** December 22, 2025  
**Status:** Proposal / Design Phase

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Goals and Constraints](#2-goals-and-constraints)
3. [Architecture Overview](#3-architecture-overview)
4. [Data Model](#4-data-model)
5. [Query-Time Optimization](#5-query-time-optimization)
6. [Concept Extraction Pipeline](#6-concept-extraction-pipeline)
7. [API Design](#7-api-design)
8. [User Curation Workflow](#8-user-curation-workflow)
9. [Graph Maintenance & Recalculation](#9-graph-maintenance--recalculation)
10. [Improvement Suggestions Engine](#10-improvement-suggestions-engine)
11. [Integration with LAMB](#11-integration-with-lamb)
12. [Implementation Roadmap](#12-implementation-roadmap)
13. [Open Questions](#13-open-questions)

---

## 1. Executive Summary

### The Problem

Current vector search in lamb-kb-server operates as **point-to-point retrieval**:

```
Query → Embedding → Nearest Neighbors → Results
```

This approach misses:
- **Conceptual relationships** between chunks
- **Topic clustering** that could expand results
- **Multi-hop reasoning** connecting disparate information
- **User knowledge** about domain-specific relationships

### The Solution

Enhance the knowledge base with a **semantic graph layer** that:
- Extracts concepts from chunks during ingestion
- Builds relationships between concepts automatically
- Allows users to curate and improve the graph
- Uses the graph to enhance query results without sacrificing speed

### Key Design Principle

```
┌─────────────────────────────────────────────────────────────────┐
│  INGESTION TIME: Heavy computation allowed                      │
│  • NLP extraction                                               │
│  • Graph construction                                           │
│  • Pre-computation of expansions                                │
├─────────────────────────────────────────────────────────────────┤
│  QUERY TIME: Must be fast (target: <50ms overhead)              │
│  • Indexed lookups only                                         │
│  • No NLP or computation                                        │
│  • Pre-computed data retrieval                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Goals and Constraints

### Primary Goals

| Goal | Priority | Description |
|------|----------|-------------|
| **Query Speed** | P0 | Graph enhancement must add <50ms to query time |
| **Better Results** | P0 | Improve relevance through concept expansion |
| **User Curation** | P1 | Allow users to edit/improve the concept graph |
| **LAMB Integration** | P1 | Expose via REST API for LAMB consumption |
| **Transparency** | P2 | Users can understand why results were returned |

### Constraints

| Constraint | Rationale |
|------------|-----------|
| No external graph DB | Keep deployment simple; use SQLite |
| No query-time NLP | Speed requirement |
| Embeddings immutable | Vector consistency; graph is separate layer |
| Backwards compatible | Existing collections should work without graph |

### Non-Goals (for v1)

- Real-time graph updates during query
- Complex reasoning chains (>2 hops)
- Cross-collection graph relationships
- Automatic re-indexing on graph changes

---

## 3. Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        lamb-kb-server with Semantic Graph                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         FastAPI Application                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐   │   │
│  │  │   System    │  │ Collections │  │   Graph     │  │   Query    │   │   │
│  │  │   Router    │  │   Router    │  │   Router    │  │  (Enhanced)│   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────┼────────────────────────────────────┐   │
│  │                          Service Layer                               │   │
│  │  ┌──────────────────┐  ┌───────┴───────┐  ┌───────────────────────┐  │   │
│  │  │  GraphService    │  │IngestionSvc   │  │   QueryService        │  │   │
│  │  │  (NEW)           │  │ + Extraction  │  │   + Graph Expansion   │  │   │
│  │  └──────────────────┘  └───────────────┘  └───────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌──────────────────┐     ┌────────┴────────┐    ┌───────────────────┐      │
│  │     SQLite       │     │    ChromaDB     │    │   File System     │      │
│  │   + Graph Tables │◄────┤   (Vectors)     │    │   (Documents)     │      │
│  │   (NEW)          │     │                 │    │                   │      │
│  └──────────────────┘     └─────────────────┘    └───────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow: Ingestion with Concept Extraction

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   File      │────►│  Ingest Plugin  │────►│  Text Chunks    │
│   Upload    │     │  (existing)     │     │                 │
└─────────────┘     └─────────────────┘     └────────┬────────┘
                                                     │
                    ┌────────────────────────────────┼────────────────────────────────┐
                    │                                │                                │
                    ▼                                ▼                                ▼
           ┌───────────────┐              ┌─────────────────┐              ┌─────────────────┐
           │   ChromaDB    │              │ Concept         │              │ File Registry   │
           │   (Vectors)   │              │ Extraction      │              │ (existing)      │
           │   (existing)  │              │ (NEW)           │              │                 │
           └───────────────┘              └────────┬────────┘              └─────────────────┘
                                                   │
                                                   ▼
                                         ┌─────────────────┐
                                         │ Graph Builder   │
                                         │ • concepts      │
                                         │ • edges         │
                                         │ • chunk_concepts│
                                         │ • expansions    │
                                         └─────────────────┘
```

### Data Flow: Query with Graph Enhancement

```
┌─────────────────────────────────────────────────────────────────┐
│                    Query: "How does dropout work?"              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Vector Search (ChromaDB) - ~100ms                      │
│  → Returns top-10 chunks                                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: Concept Lookup (SQLite) - ~5ms                         │
│  → Get concepts from result chunks                              │
│  → ["dropout", "regularization", "neural_networks"]             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 3: Expansion Lookup (SQLite) - ~5ms                       │
│  → Get pre-computed related concepts                            │
│  → ["overfitting", "batch_normalization", "training"]           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 4: Additional Chunks (SQLite) - ~10ms                     │
│  → Find chunks with expanded concepts not in original results   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 5: Merge & Re-rank - ~5ms                                 │
│  → Combine vector similarity + graph relevance                  │
│  → Return enhanced results                                      │
└─────────────────────────────────────────────────────────────────┘

Total Graph Overhead: ~25ms
```

---

## 4. Data Model

### 4.1 New SQLite Tables

#### concepts

Stores extracted concepts/terms for each collection.

```sql
CREATE TABLE concepts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NOT NULL,
    frequency INTEGER DEFAULT 1,
    centrality_score FLOAT DEFAULT 0.0,
    cluster_id INTEGER,
    is_user_verified BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
    UNIQUE(collection_id, normalized_name)
);

CREATE INDEX idx_concepts_collection ON concepts(collection_id);
CREATE INDEX idx_concepts_normalized ON concepts(collection_id, normalized_name);
CREATE INDEX idx_concepts_cluster ON concepts(collection_id, cluster_id);
```

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `collection_id` | INTEGER | FK to collections |
| `name` | VARCHAR(255) | Display name (original case) |
| `normalized_name` | VARCHAR(255) | Lowercase, stemmed for matching |
| `frequency` | INTEGER | Number of chunks containing this concept |
| `centrality_score` | FLOAT | Pre-computed importance (0-1) |
| `cluster_id` | INTEGER | Topic cluster assignment |
| `is_user_verified` | BOOLEAN | User has reviewed/confirmed |

#### concept_edges

Stores relationships between concepts.

```sql
CREATE TABLE concept_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    from_concept_id INTEGER NOT NULL,
    to_concept_id INTEGER NOT NULL,
    edge_type VARCHAR(50) DEFAULT 'related',
    weight FLOAT DEFAULT 1.0,
    is_user_defined BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
    FOREIGN KEY (from_concept_id) REFERENCES concepts(id) ON DELETE CASCADE,
    FOREIGN KEY (to_concept_id) REFERENCES concepts(id) ON DELETE CASCADE,
    UNIQUE(collection_id, from_concept_id, to_concept_id, edge_type)
);

CREATE INDEX idx_edges_from ON concept_edges(from_concept_id);
CREATE INDEX idx_edges_to ON concept_edges(to_concept_id);
CREATE INDEX idx_edges_collection ON concept_edges(collection_id);
```

| Column | Type | Description |
|--------|------|-------------|
| `from_concept_id` | INTEGER | Source concept |
| `to_concept_id` | INTEGER | Target concept |
| `edge_type` | VARCHAR(50) | Relationship type (see below) |
| `weight` | FLOAT | Edge strength (0-1) |
| `is_user_defined` | BOOLEAN | User created this edge |

**Edge Types:**
- `related` - General co-occurrence relationship
- `contains` - Hierarchical (A contains B)
- `similar` - Semantic similarity
- `contrasts` - Opposing concepts
- `requires` - Prerequisite relationship

#### chunk_concepts

Links chunks to their extracted concepts.

```sql
CREATE TABLE chunk_concepts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    chunk_id VARCHAR(64) NOT NULL,
    concept_id INTEGER NOT NULL,
    relevance_score FLOAT DEFAULT 1.0,
    is_user_added BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
    FOREIGN KEY (concept_id) REFERENCES concepts(id) ON DELETE CASCADE,
    UNIQUE(collection_id, chunk_id, concept_id)
);

CREATE INDEX idx_chunk_concepts_chunk ON chunk_concepts(chunk_id);
CREATE INDEX idx_chunk_concepts_concept ON chunk_concepts(concept_id);
CREATE INDEX idx_chunk_concepts_collection ON chunk_concepts(collection_id);
```

| Column | Type | Description |
|--------|------|-------------|
| `chunk_id` | VARCHAR(64) | ChromaDB document ID |
| `concept_id` | INTEGER | FK to concepts |
| `relevance_score` | FLOAT | How relevant concept is to chunk (0-1) |
| `is_user_added` | BOOLEAN | User manually added this link |

#### concept_expansions

**The Speed Secret:** Pre-computed concept expansions for instant query-time lookup.

```sql
CREATE TABLE concept_expansions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL,
    concept_id INTEGER NOT NULL,
    expanded_concept_id INTEGER NOT NULL,
    expansion_score FLOAT NOT NULL,
    hop_distance INTEGER DEFAULT 1,
    
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
    FOREIGN KEY (concept_id) REFERENCES concepts(id) ON DELETE CASCADE,
    FOREIGN KEY (expanded_concept_id) REFERENCES concepts(id) ON DELETE CASCADE,
    UNIQUE(collection_id, concept_id, expanded_concept_id)
);

CREATE INDEX idx_expansions_concept ON concept_expansions(concept_id);
CREATE INDEX idx_expansions_collection ON concept_expansions(collection_id);
```

| Column | Type | Description |
|--------|------|-------------|
| `concept_id` | INTEGER | Source concept |
| `expanded_concept_id` | INTEGER | Related concept to expand to |
| `expansion_score` | FLOAT | Relevance of expansion (0-1) |
| `hop_distance` | INTEGER | Graph distance (1 = direct, 2 = via intermediate) |

### 4.2 Enhanced Chunk Metadata

ChromaDB metadata can be enriched (without re-embedding):

```json
{
  // Existing fields
  "source": "/path/to/file.pdf",
  "filename": "document.pdf",
  "chunk_index": 3,
  "chunk_count": 25,
  
  // NEW: Graph-related fields
  "concept_ids": [1, 5, 12],
  "primary_concept": "machine_learning",
  "cluster_id": 2,
  
  // NEW: User annotations
  "user_tags": ["important", "reviewed"],
  "user_notes": "Key definition of backpropagation",
  "verified_at": "2025-12-22T10:30:00"
}
```

---

## 5. Query-Time Optimization

### 5.1 The Zero-Computation Principle

At query time, **no NLP or graph algorithms run**. Everything is pre-computed.

| Operation | Method | Expected Time |
|-----------|--------|---------------|
| Vector search | ChromaDB native | 50-150ms |
| Get chunk concepts | SQL IN query | 1-5ms |
| Get expansions | SQL IN query | 1-5ms |
| Get expansion chunks | SQL IN query | 5-10ms |
| Merge & rank | In-memory sort | 1-5ms |

**Total target: <50ms graph overhead**

### 5.2 Query Algorithm

```python
async def graph_enhanced_query(
    query_text: str,
    collection_id: int,
    top_k: int = 5,
    use_graph: bool = True,
    expansion_depth: int = 1,  # 1 or 2 hops
    graph_weight: float = 0.3  # How much to weight graph results
) -> QueryResult:
    """
    Enhanced query with graph expansion.
    
    Args:
        query_text: The search query
        collection_id: Target collection
        top_k: Number of results to return
        use_graph: Whether to use graph expansion
        expansion_depth: 1 = direct relations, 2 = include 2-hop
        graph_weight: Weight for graph-sourced results (0-1)
    """
    
    # Step 1: Standard vector search (fetch extra for merging)
    vector_results = await vector_search(
        query_text, 
        collection_id, 
        n_results=top_k * 2 if use_graph else top_k
    )
    
    if not use_graph:
        return QueryResult(results=vector_results[:top_k])
    
    # Step 2: Get concepts from result chunks (single query)
    chunk_ids = [r['id'] for r in vector_results]
    chunk_concepts = await db.fetch_all("""
        SELECT chunk_id, concept_id 
        FROM chunk_concepts 
        WHERE chunk_id IN :chunk_ids
    """, {'chunk_ids': tuple(chunk_ids)})
    
    concept_ids = list(set(cc['concept_id'] for cc in chunk_concepts))
    
    if not concept_ids:
        return QueryResult(results=vector_results[:top_k])
    
    # Step 3: Get pre-computed expansions (single query)
    expansions = await db.fetch_all("""
        SELECT expanded_concept_id, MAX(expansion_score) as score
        FROM concept_expansions 
        WHERE concept_id IN :concept_ids 
          AND hop_distance <= :max_hops
        GROUP BY expanded_concept_id
        ORDER BY score DESC
        LIMIT 20
    """, {'concept_ids': tuple(concept_ids), 'max_hops': expansion_depth})
    
    expanded_concept_ids = [e['expanded_concept_id'] for e in expansions]
    
    # Step 4: Find additional chunks via expanded concepts
    additional_chunks = await db.fetch_all("""
        SELECT chunk_id, MAX(relevance_score) as score
        FROM chunk_concepts 
        WHERE concept_id IN :concept_ids 
          AND chunk_id NOT IN :existing
        GROUP BY chunk_id
        ORDER BY score DESC
        LIMIT :limit
    """, {
        'concept_ids': tuple(expanded_concept_ids),
        'existing': tuple(chunk_ids),
        'limit': top_k
    })
    
    # Step 5: Merge and re-rank
    final_results = merge_results(
        vector_results, 
        additional_chunks, 
        graph_weight,
        top_k
    )
    
    return QueryResult(
        results=final_results,
        graph_expansion_used=True,
        concepts_found=len(concept_ids),
        concepts_expanded=len(expanded_concept_ids)
    )
```

### 5.3 Ranking Formula

```python
def calculate_final_score(
    vector_similarity: float,
    graph_score: float,
    graph_weight: float = 0.3
) -> float:
    """
    Combine vector similarity with graph relevance.
    
    vector_similarity: 0-1 from ChromaDB (1 - distance)
    graph_score: 0-1 from concept relevance
    graph_weight: How much to weight graph signal
    """
    return (
        vector_similarity * (1 - graph_weight) +
        graph_score * graph_weight
    )
```

---

## 6. Concept Extraction Pipeline

### 6.1 Extraction Strategy

Concepts are extracted during ingestion using lightweight NLP (no external APIs required).

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Chunk Text  │────►│  Concept        │────►│  Concepts +      │
│              │     │  Extractor      │     │  Relationships   │
└──────────────┘     └─────────────────┘     └──────────────────┘
                              │
                              │ Uses:
                              ├── TF-IDF for key terms
                              ├── Pattern matching for entities
                              ├── N-gram extraction
                              └── Optional: spaCy NER
```

### 6.2 Extractor Implementation

```python
class ConceptExtractor:
    """
    Extracts concepts from text using lightweight NLP.
    No external API calls required.
    """
    
    def __init__(self, 
                 min_term_frequency: int = 2,
                 max_concepts_per_chunk: int = 10,
                 use_spacy: bool = False):
        self.min_term_frequency = min_term_frequency
        self.max_concepts_per_chunk = max_concepts_per_chunk
        self.use_spacy = use_spacy
        
        # Load stopwords and common terms to ignore
        self.stopwords = self._load_stopwords()
        
        # Optional: Load spaCy model for NER
        if use_spacy:
            import spacy
            self.nlp = spacy.load("en_core_web_sm")
    
    def extract_from_chunk(self, text: str) -> List[ExtractedConcept]:
        """Extract concepts from a single chunk."""
        concepts = []
        
        # Method 1: Key term extraction (TF-based)
        key_terms = self._extract_key_terms(text)
        concepts.extend(key_terms)
        
        # Method 2: N-gram patterns (noun phrases)
        ngrams = self._extract_ngrams(text, n_range=(2, 3))
        concepts.extend(ngrams)
        
        # Method 3: Named entities (if spaCy enabled)
        if self.use_spacy:
            entities = self._extract_entities(text)
            concepts.extend(entities)
        
        # Deduplicate and rank
        return self._dedupe_and_rank(concepts)[:self.max_concepts_per_chunk]
    
    def extract_from_collection(
        self, 
        chunks: List[Dict],
        build_edges: bool = True
    ) -> ExtractionResult:
        """
        Extract concepts from all chunks and optionally build edges.
        """
        all_concepts = {}  # normalized_name -> ConceptData
        chunk_concept_links = []
        
        for chunk in chunks:
            chunk_concepts = self.extract_from_chunk(chunk['text'])
            
            for concept in chunk_concepts:
                # Aggregate concept data
                if concept.normalized_name not in all_concepts:
                    all_concepts[concept.normalized_name] = ConceptData(
                        name=concept.name,
                        normalized_name=concept.normalized_name,
                        frequency=0,
                        chunk_ids=[]
                    )
                
                all_concepts[concept.normalized_name].frequency += 1
                all_concepts[concept.normalized_name].chunk_ids.append(chunk['id'])
                
                chunk_concept_links.append({
                    'chunk_id': chunk['id'],
                    'concept_name': concept.normalized_name,
                    'relevance_score': concept.score
                })
        
        # Filter by minimum frequency
        filtered_concepts = {
            k: v for k, v in all_concepts.items() 
            if v.frequency >= self.min_term_frequency
        }
        
        # Build edges from co-occurrence
        edges = []
        if build_edges:
            edges = self._build_cooccurrence_edges(filtered_concepts, chunks)
        
        return ExtractionResult(
            concepts=list(filtered_concepts.values()),
            chunk_concept_links=chunk_concept_links,
            edges=edges
        )
    
    def _build_cooccurrence_edges(
        self, 
        concepts: Dict[str, ConceptData],
        chunks: List[Dict]
    ) -> List[ConceptEdge]:
        """Build edges based on concept co-occurrence in chunks."""
        cooccurrence = defaultdict(int)
        
        for chunk in chunks:
            # Get concepts in this chunk
            chunk_concepts = [
                c for c in concepts.values() 
                if chunk['id'] in c.chunk_ids
            ]
            
            # Count co-occurrences
            for i, c1 in enumerate(chunk_concepts):
                for c2 in chunk_concepts[i+1:]:
                    key = tuple(sorted([c1.normalized_name, c2.normalized_name]))
                    cooccurrence[key] += 1
        
        # Create edges for significant co-occurrences
        edges = []
        for (c1, c2), count in cooccurrence.items():
            if count >= 2:  # Minimum co-occurrence threshold
                weight = min(1.0, count / 10)  # Normalize
                edges.append(ConceptEdge(
                    from_concept=c1,
                    to_concept=c2,
                    edge_type='related',
                    weight=weight
                ))
        
        return edges
```

### 6.3 Integration with Ingestion Pipeline

```python
# In services/ingestion.py

class IngestionService:
    
    def __init__(self):
        self.concept_extractor = ConceptExtractor()
        self.graph_service = GraphService()
    
    async def ingest_file(
        self, 
        collection_id: int,
        file_path: str,
        plugin_name: str,
        extract_concepts: bool = True,  # NEW parameter
        **kwargs
    ):
        # Existing ingestion logic...
        plugin = get_plugin(plugin_name)
        chunks = plugin.ingest(file_path, **kwargs)
        
        # Add to ChromaDB (existing)
        chroma_collection = get_chroma_collection(collection_id)
        chroma_collection.add(
            ids=[c['id'] for c in chunks],
            documents=[c['text'] for c in chunks],
            metadatas=[c['metadata'] for c in chunks]
        )
        
        # NEW: Extract concepts and build graph
        if extract_concepts:
            extraction_result = self.concept_extractor.extract_from_collection(chunks)
            await self.graph_service.add_extraction_result(
                collection_id, 
                extraction_result
            )
            
            # Update chunk metadata with concept IDs
            await self._enrich_chunk_metadata(
                chroma_collection,
                extraction_result.chunk_concept_links
            )
        
        return IngestionResult(
            documents_added=len(chunks),
            concepts_extracted=len(extraction_result.concepts) if extract_concepts else 0
        )
```

---

## 7. API Design

### 7.1 Graph Router Endpoints

New router: `routers/graph.py`

#### Concept Management

```python
# ==================== CONCEPTS ====================

@router.get("/collections/{collection_id}/concepts")
async def list_concepts(
    collection_id: int,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    verified_only: bool = False,
    min_frequency: int = 1,
    cluster_id: Optional[int] = None,
    token: str = Depends(verify_token)
) -> ConceptListResponse:
    """
    List concepts in a collection with filtering options.
    
    Returns:
        total: Total count matching filters
        items: List of concepts
    """
    pass


@router.get("/collections/{collection_id}/concepts/{concept_id}")
async def get_concept(
    collection_id: int,
    concept_id: int,
    include_chunks: bool = True,
    include_edges: bool = True,
    token: str = Depends(verify_token)
) -> ConceptDetailResponse:
    """
    Get detailed concept information.
    
    Returns:
        - Concept metadata
        - List of chunks containing this concept
        - Related concepts (edges)
    """
    pass


@router.post("/collections/{collection_id}/concepts")
async def create_concept(
    collection_id: int,
    concept: ConceptCreate,
    token: str = Depends(verify_token)
) -> ConceptResponse:
    """
    Manually create a concept.
    
    Use case: User wants to add a domain-specific term
    that wasn't auto-extracted.
    """
    pass


@router.put("/collections/{collection_id}/concepts/{concept_id}")
async def update_concept(
    collection_id: int,
    concept_id: int,
    update: ConceptUpdate,
    token: str = Depends(verify_token)
) -> ConceptResponse:
    """
    Update concept properties.
    
    Updatable fields:
        - name (display name)
        - is_user_verified
    
    Does NOT require graph recalculation.
    """
    pass


@router.delete("/collections/{collection_id}/concepts/{concept_id}")
async def delete_concept(
    collection_id: int,
    concept_id: int,
    token: str = Depends(verify_token)
) -> DeleteResponse:
    """
    Delete a concept and all its relationships.
    
    Triggers: Partial expansion table recalculation.
    """
    pass


@router.post("/collections/{collection_id}/concepts/merge")
async def merge_concepts(
    collection_id: int,
    merge_request: ConceptMergeRequest,
    token: str = Depends(verify_token)
) -> ConceptResponse:
    """
    Merge multiple concepts into one.
    
    Request:
        source_ids: [1, 2, 3]  # Concepts to merge
        target_name: "machine learning"  # Final name
    
    Behavior:
        - All chunk links transferred to merged concept
        - Edges combined (weights averaged)
        - Source concepts deleted
    
    Triggers: Partial expansion table recalculation.
    """
    pass
```

#### Edge Management

```python
# ==================== EDGES ====================

@router.get("/collections/{collection_id}/concepts/{concept_id}/edges")
async def get_concept_edges(
    collection_id: int,
    concept_id: int,
    direction: str = "both",  # "outgoing", "incoming", "both"
    token: str = Depends(verify_token)
) -> List[ConceptEdgeResponse]:
    """Get all edges for a concept."""
    pass


@router.post("/collections/{collection_id}/edges")
async def create_edge(
    collection_id: int,
    edge: ConceptEdgeCreate,
    token: str = Depends(verify_token)
) -> ConceptEdgeResponse:
    """
    Create a relationship between concepts.
    
    Request:
        from_concept_id: int
        to_concept_id: int
        edge_type: str = "related"
        weight: float = 1.0
    
    Triggers: Partial expansion table recalculation.
    """
    pass


@router.put("/collections/{collection_id}/edges/{edge_id}")
async def update_edge(
    collection_id: int,
    edge_id: int,
    update: ConceptEdgeUpdate,
    token: str = Depends(verify_token)
) -> ConceptEdgeResponse:
    """
    Update edge properties (weight, type).
    
    Triggers: Partial expansion table recalculation.
    """
    pass


@router.delete("/collections/{collection_id}/edges/{edge_id}")
async def delete_edge(
    collection_id: int,
    edge_id: int,
    token: str = Depends(verify_token)
) -> DeleteResponse:
    """
    Delete an edge.
    
    Triggers: Partial expansion table recalculation.
    """
    pass
```

#### Chunk-Concept Linking

```python
# ==================== CHUNK-CONCEPT LINKS ====================

@router.get("/collections/{collection_id}/chunks/{chunk_id}/concepts")
async def get_chunk_concepts(
    collection_id: int,
    chunk_id: str,
    token: str = Depends(verify_token)
) -> List[ChunkConceptResponse]:
    """Get all concepts linked to a chunk."""
    pass


@router.post("/collections/{collection_id}/chunks/{chunk_id}/concepts")
async def add_concept_to_chunk(
    collection_id: int,
    chunk_id: str,
    link: ChunkConceptLink,
    token: str = Depends(verify_token)
) -> ChunkConceptResponse:
    """
    Link a concept to a chunk.
    
    Request:
        concept_id: int  # OR
        concept_name: str  # Creates concept if doesn't exist
        relevance_score: float = 1.0
    
    NO graph recalculation needed.
    """
    pass


@router.delete("/collections/{collection_id}/chunks/{chunk_id}/concepts/{concept_id}")
async def remove_concept_from_chunk(
    collection_id: int,
    chunk_id: str,
    concept_id: int,
    token: str = Depends(verify_token)
) -> DeleteResponse:
    """
    Remove concept link from chunk.
    
    NO graph recalculation needed.
    """
    pass
```

#### Direct Chunk Access

```python
# ==================== CHUNK METADATA ====================

@router.get("/collections/{collection_id}/chunks/{chunk_id}")
async def get_chunk(
    collection_id: int,
    chunk_id: str,
    include_concepts: bool = True,
    include_similar: bool = False,
    token: str = Depends(verify_token)
) -> ChunkDetailResponse:
    """
    Get full chunk details.
    
    Returns:
        - id
        - text content
        - metadata (from ChromaDB)
        - concepts (from graph)
        - similar_chunks (optional, via embedding)
    """
    pass


@router.patch("/collections/{collection_id}/chunks/{chunk_id}/metadata")
async def update_chunk_metadata(
    collection_id: int,
    chunk_id: str,
    metadata: Dict[str, Any],
    merge: bool = True,
    token: str = Depends(verify_token)
) -> ChunkDetailResponse:
    """
    Update chunk metadata directly in ChromaDB.
    
    Important: NO re-embedding required!
    ChromaDB supports metadata-only updates.
    
    Args:
        metadata: Fields to update
        merge: True = merge with existing, False = replace
    
    Use cases:
        - Add user tags
        - Mark as reviewed
        - Add notes
        - Update relevance scores
    """
    pass
```

#### Graph Maintenance

```python
# ==================== GRAPH MAINTENANCE ====================

@router.post("/collections/{collection_id}/graph/recalculate")
async def recalculate_graph(
    collection_id: int,
    scope: str = "expansions",
    token: str = Depends(verify_token)
) -> GraphRecalculationResponse:
    """
    Trigger graph recalculation.
    
    Scopes:
        - "expansions": Rebuild expansion table (fast)
        - "metrics": Recalculate centrality scores (medium)
        - "edges": Rebuild co-occurrence edges (medium)
        - "full": Complete rebuild from chunks (slow)
    
    Returns:
        - scope
        - items_processed
        - duration_ms
    """
    pass


@router.get("/collections/{collection_id}/graph/stats")
async def get_graph_stats(
    collection_id: int,
    token: str = Depends(verify_token)
) -> GraphStatsResponse:
    """
    Get graph statistics.
    
    Returns:
        - concept_count
        - edge_count
        - chunk_links_count
        - avg_concepts_per_chunk
        - cluster_count
        - last_recalculation
    """
    pass
```

### 7.2 Enhanced Query Endpoint

```python
# In routers/collections.py - Enhanced query

@router.post("/collections/{collection_id}/query")
async def query_collection(
    collection_id: int,
    query: QueryRequest,
    plugin_name: str = "simple_query",
    # NEW parameters
    use_graph: bool = True,
    expansion_depth: int = 1,
    graph_weight: float = 0.3,
    token: str = Depends(verify_token)
) -> QueryResponse:
    """
    Query collection with optional graph enhancement.
    
    Args:
        query: Standard query request (query_text, top_k, threshold)
        use_graph: Enable semantic graph expansion
        expansion_depth: 1 = direct relations, 2 = include 2-hop
        graph_weight: How much to weight graph results (0-1)
    
    Response includes:
        - results: Enhanced result list
        - graph_info: {
            expansion_used: bool,
            concepts_found: int,
            concepts_expanded: int
          }
    """
    pass
```

---

## 8. User Curation Workflow

### 8.1 Curation Interface (LAMB Frontend)

The LAMB frontend can provide a curation interface:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Knowledge Base: "ML Research Papers"                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐  ┌──────────────────────────────────────────────┐  │
│  │ Concepts (156)  │  │  Selected: "neural networks"                 │  │
│  │ ───────────────│  │  ────────────────────────────────────────────│  │
│  │ ● neural net...│  │  Frequency: 47 chunks                        │  │
│  │ ○ machine lea..│  │  Centrality: 0.82                            │  │
│  │ ○ deep learni..│  │  Cluster: Deep Learning                      │  │
│  │ ○ backpropaga..│  │  Status: ✓ Verified                          │  │
│  │ ○ gradient de..│  │                                              │  │
│  │ ○ overfitting │  │  Related Concepts:                           │  │
│  │ ○ dropout     │  │  ├── deep learning (0.9) ─────────[Edit]     │  │
│  │ ○ batch norm  │  │  ├── backpropagation (0.8) ──────[Edit]      │  │
│  │               │  │  ├── machine learning (0.7) ─────[Edit]      │  │
│  │ [+ Add]       │  │  └── [+ Add Relationship]                    │  │
│  │               │  │                                              │  │
│  └─────────────────┘  │  Sample Chunks (5 of 47):                   │  │
│                       │  • "Neural networks are computational..."   │  │
│  ┌─────────────────┐  │  • "The architecture of deep neural..."     │  │
│  │ Suggestions (8) │  │  • "Training neural networks requires..."   │  │
│  │ ───────────────│  │                                              │  │
│  │ ⚠ Merge:       │  │  Actions:                                   │  │
│  │   "NN" → "neu..│  │  [Rename] [Merge] [Delete] [View All Chunks]│  │
│  │ ⚠ Missing edge:│  │                                              │  │
│  │   dropout ↔ ov..│  └──────────────────────────────────────────────┘  │
│  │ ℹ Orphan:      │                                                     │
│  │   "LSTM"       │                                                     │
│  └─────────────────┘                                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Curation Actions

| Action | API Endpoint | Recalculation |
|--------|--------------|---------------|
| Rename concept | `PUT /concepts/{id}` | None |
| Verify concept | `PUT /concepts/{id}` | None |
| Delete concept | `DELETE /concepts/{id}` | Partial |
| Merge concepts | `POST /concepts/merge` | Partial |
| Add relationship | `POST /edges` | Partial |
| Edit relationship | `PUT /edges/{id}` | Partial |
| Delete relationship | `DELETE /edges/{id}` | Partial |
| Add concept to chunk | `POST /chunks/{id}/concepts` | None |
| Remove concept from chunk | `DELETE /chunks/{id}/concepts/{cid}` | None |
| Update chunk metadata | `PATCH /chunks/{id}/metadata` | None |

### 8.3 Batch Operations

For efficiency, support batch operations:

```python
@router.post("/collections/{collection_id}/graph/batch")
async def batch_graph_operations(
    collection_id: int,
    operations: List[GraphOperation],
    token: str = Depends(verify_token)
) -> BatchOperationResponse:
    """
    Execute multiple graph operations in a single transaction.
    
    Recalculation happens once at the end, not per operation.
    
    Request:
        operations: [
            {"type": "merge_concepts", "params": {...}},
            {"type": "create_edge", "params": {...}},
            {"type": "delete_concept", "params": {...}}
        ]
    """
    pass
```

---

## 9. Graph Maintenance & Recalculation

### 9.1 Recalculation Matrix

| User Action | Edges Table | Expansion Table | Centrality | Embeddings |
|-------------|-------------|-----------------|------------|------------|
| Add concept to chunk | ❌ | ❌ | ❌ | ❌ |
| Remove concept from chunk | ❌ | ❌ | ❌ | ❌ |
| Update chunk metadata | ❌ | ❌ | ❌ | ❌ |
| Create concept | ❌ | ❌ | ❌ | ❌ |
| Rename concept | ❌ | ❌ | ❌ | ❌ |
| Verify concept | ❌ | ❌ | ❌ | ❌ |
| Delete concept | ✅ Cascade | ✅ Partial | ⚡ Optional | ❌ |
| Merge concepts | ✅ Repoint | ✅ Partial | ⚡ Optional | ❌ |
| Add edge | ❌ | ✅ Partial | ⚡ Optional | ❌ |
| Edit edge weight | ❌ | ✅ Partial | ❌ | ❌ |
| Delete edge | ❌ | ✅ Partial | ⚡ Optional | ❌ |

**Key insight: Embeddings are NEVER affected by graph changes.**

### 9.2 Partial Recalculation Strategy

```python
class GraphMaintenanceService:
    """Handles incremental graph updates."""
    
    async def on_concept_deleted(self, collection_id: int, concept_id: int):
        """Minimal recalculation after concept deletion."""
        
        # 1. Find concepts that had this in their expansion
        affected = await self.db.fetch_all("""
            SELECT DISTINCT concept_id 
            FROM concept_expansions
            WHERE expanded_concept_id = :concept_id
        """, {'concept_id': concept_id})
        
        # 2. Cascade deletes handled by FK constraints
        
        # 3. Recalculate only affected concepts
        for concept in affected:
            await self._recalculate_expansions_for_concept(
                collection_id, concept['concept_id']
            )
    
    async def on_edge_changed(
        self, 
        collection_id: int,
        from_concept_id: int, 
        to_concept_id: int
    ):
        """Minimal recalculation after edge add/edit/delete."""
        
        # Only recalculate for the two affected concepts
        await self._recalculate_expansions_for_concept(
            collection_id, from_concept_id
        )
        await self._recalculate_expansions_for_concept(
            collection_id, to_concept_id
        )
    
    async def _recalculate_expansions_for_concept(
        self, 
        collection_id: int, 
        concept_id: int
    ):
        """Recalculate expansions for a single concept."""
        
        # Delete old expansions
        await self.db.execute("""
            DELETE FROM concept_expansions 
            WHERE concept_id = :concept_id
        """, {'concept_id': concept_id})
        
        # Get direct neighbors (1-hop)
        neighbors = await self.db.fetch_all("""
            SELECT 
                CASE WHEN from_concept_id = :concept_id 
                     THEN to_concept_id 
                     ELSE from_concept_id END as neighbor_id,
                weight
            FROM concept_edges
            WHERE from_concept_id = :concept_id 
               OR to_concept_id = :concept_id
        """, {'concept_id': concept_id})
        
        expansions = []
        
        # 1-hop expansions
        for n in neighbors:
            expansions.append({
                'concept_id': concept_id,
                'expanded_concept_id': n['neighbor_id'],
                'expansion_score': n['weight'],
                'hop_distance': 1
            })
            
            # 2-hop expansions (neighbors of neighbors)
            second_neighbors = await self.db.fetch_all("""
                SELECT 
                    CASE WHEN from_concept_id = :neighbor_id 
                         THEN to_concept_id 
                         ELSE from_concept_id END as neighbor_id,
                    weight
                FROM concept_edges
                WHERE (from_concept_id = :neighbor_id OR to_concept_id = :neighbor_id)
                  AND from_concept_id != :original_id 
                  AND to_concept_id != :original_id
            """, {
                'neighbor_id': n['neighbor_id'],
                'original_id': concept_id
            })
            
            for sn in second_neighbors:
                expansions.append({
                    'concept_id': concept_id,
                    'expanded_concept_id': sn['neighbor_id'],
                    'expansion_score': n['weight'] * sn['weight'] * 0.5,  # Decay
                    'hop_distance': 2
                })
        
        # Batch insert
        if expansions:
            await self.db.execute_many("""
                INSERT OR REPLACE INTO concept_expansions 
                (collection_id, concept_id, expanded_concept_id, expansion_score, hop_distance)
                VALUES (:collection_id, :concept_id, :expanded_concept_id, :expansion_score, :hop_distance)
            """, [
                {**e, 'collection_id': collection_id} for e in expansions
            ])
```

### 9.3 Background Recalculation

For full recalculations, use background processing:

```python
@router.post("/collections/{collection_id}/graph/recalculate")
async def recalculate_graph(
    collection_id: int,
    scope: str = "expansions",
    background: bool = True,
    token: str = Depends(verify_token)
):
    """Trigger graph recalculation."""
    
    if background and scope in ["full", "edges"]:
        # Queue for background processing
        job_id = await background_jobs.enqueue(
            'recalculate_graph',
            collection_id=collection_id,
            scope=scope
        )
        return {"status": "queued", "job_id": job_id}
    else:
        # Synchronous for fast operations
        result = await graph_service.recalculate(collection_id, scope)
        return result
```

---

## 10. Improvement Suggestions Engine

### 10.1 Suggestion Types

| Type | Description | Severity |
|------|-------------|----------|
| `potential_duplicate` | Similar concept names | Medium |
| `missing_edge` | Concepts co-occur but aren't linked | Low |
| `orphan_concept` | Concept has no relationships | Info |
| `low_coverage` | Chunk has no concepts | Info |
| `unverified_high_frequency` | Popular concept not verified | Low |

### 10.2 Suggestion API

```python
@router.get("/collections/{collection_id}/graph/suggestions")
async def get_suggestions(
    collection_id: int,
    types: Optional[List[str]] = None,
    limit: int = 20,
    token: str = Depends(verify_token)
) -> SuggestionsResponse:
    """
    Get improvement suggestions for the graph.
    
    Returns actionable suggestions that users can approve/apply.
    """
    pass


@router.post("/collections/{collection_id}/graph/suggestions/{suggestion_id}/apply")
async def apply_suggestion(
    collection_id: int,
    suggestion_id: str,
    token: str = Depends(verify_token)
) -> ApplySuggestionResponse:
    """Apply a single suggestion."""
    pass


@router.post("/collections/{collection_id}/graph/suggestions/apply-batch")
async def apply_suggestions_batch(
    collection_id: int,
    suggestion_ids: List[str],
    token: str = Depends(verify_token)
) -> BatchApplyResponse:
    """
    Apply multiple suggestions at once.
    
    Recalculation happens once at the end.
    """
    pass
```

### 10.3 Suggestion Generation

```python
class SuggestionEngine:
    """Generates improvement suggestions for concept graphs."""
    
    async def generate_suggestions(
        self, 
        collection_id: int,
        types: List[str] = None
    ) -> List[Suggestion]:
        suggestions = []
        
        if not types or 'potential_duplicate' in types:
            suggestions.extend(await self._find_duplicates(collection_id))
        
        if not types or 'missing_edge' in types:
            suggestions.extend(await self._find_missing_edges(collection_id))
        
        if not types or 'orphan_concept' in types:
            suggestions.extend(await self._find_orphans(collection_id))
        
        return suggestions
    
    async def _find_duplicates(self, collection_id: int) -> List[Suggestion]:
        """Find concepts with similar names."""
        concepts = await self.db.fetch_all("""
            SELECT id, name, normalized_name, frequency
            FROM concepts
            WHERE collection_id = :collection_id
        """, {'collection_id': collection_id})
        
        suggestions = []
        seen_pairs = set()
        
        for i, c1 in enumerate(concepts):
            for c2 in concepts[i+1:]:
                pair_key = tuple(sorted([c1['id'], c2['id']]))
                if pair_key in seen_pairs:
                    continue
                
                similarity = self._name_similarity(
                    c1['normalized_name'], 
                    c2['normalized_name']
                )
                
                if similarity > 0.8:
                    seen_pairs.add(pair_key)
                    suggestions.append(Suggestion(
                        id=f"dup_{c1['id']}_{c2['id']}",
                        type='potential_duplicate',
                        severity='medium',
                        message=f"'{c1['name']}' and '{c2['name']}' may be duplicates",
                        data={
                            'concept_ids': [c1['id'], c2['id']],
                            'similarity': similarity
                        },
                        action={
                            'type': 'merge',
                            'params': {
                                'source_ids': [c1['id'], c2['id']],
                                'target_name': c1['name'] if c1['frequency'] > c2['frequency'] else c2['name']
                            }
                        }
                    ))
        
        return suggestions
    
    async def _find_missing_edges(self, collection_id: int) -> List[Suggestion]:
        """Find concept pairs that co-occur but have no edge."""
        cooccurrences = await self.db.fetch_all("""
            SELECT 
                cc1.concept_id as c1_id,
                cc2.concept_id as c2_id,
                COUNT(*) as count
            FROM chunk_concepts cc1
            JOIN chunk_concepts cc2 
                ON cc1.chunk_id = cc2.chunk_id 
                AND cc1.concept_id < cc2.concept_id
            WHERE cc1.collection_id = :collection_id
            GROUP BY cc1.concept_id, cc2.concept_id
            HAVING count >= 3
        """, {'collection_id': collection_id})
        
        suggestions = []
        for co in cooccurrences:
            # Check if edge exists
            edge = await self.db.fetch_one("""
                SELECT id FROM concept_edges
                WHERE collection_id = :collection_id
                  AND ((from_concept_id = :c1 AND to_concept_id = :c2)
                    OR (from_concept_id = :c2 AND to_concept_id = :c1))
            """, {
                'collection_id': collection_id,
                'c1': co['c1_id'],
                'c2': co['c2_id']
            })
            
            if not edge:
                c1 = await self._get_concept_name(co['c1_id'])
                c2 = await self._get_concept_name(co['c2_id'])
                
                suggestions.append(Suggestion(
                    id=f"edge_{co['c1_id']}_{co['c2_id']}",
                    type='missing_edge',
                    severity='low',
                    message=f"'{c1}' and '{c2}' co-occur {co['count']} times but aren't linked",
                    data={
                        'concept_ids': [co['c1_id'], co['c2_id']],
                        'cooccurrence_count': co['count']
                    },
                    action={
                        'type': 'create_edge',
                        'params': {
                            'from_concept_id': co['c1_id'],
                            'to_concept_id': co['c2_id'],
                            'weight': min(1.0, co['count'] / 10)
                        }
                    }
                ))
        
        return suggestions
    
    async def _find_orphans(self, collection_id: int) -> List[Suggestion]:
        """Find concepts with no edges."""
        orphans = await self.db.fetch_all("""
            SELECT c.id, c.name, c.frequency
            FROM concepts c
            WHERE c.collection_id = :collection_id
              AND c.frequency >= 2
              AND NOT EXISTS (
                  SELECT 1 FROM concept_edges e
                  WHERE e.from_concept_id = c.id 
                     OR e.to_concept_id = c.id
              )
        """, {'collection_id': collection_id})
        
        return [
            Suggestion(
                id=f"orphan_{o['id']}",
                type='orphan_concept',
                severity='info',
                message=f"'{o['name']}' has no relationships (appears in {o['frequency']} chunks)",
                data={'concept_id': o['id']},
                action={
                    'type': 'review',
                    'params': {'concept_id': o['id']}
                }
            )
            for o in orphans
        ]
```

---

## 11. Integration with LAMB

### 11.1 LAMB Backend Integration

LAMB can use the graph API for:

1. **Enhanced RAG queries** - Pass `use_graph=true` in query requests
2. **Knowledge base curation UI** - Build curation interface using graph endpoints
3. **Quality metrics** - Use graph stats for KB quality reporting

### 11.2 Configuration

```python
# LAMB organization config
{
    "kb_server": {
        "url": "http://localhost:9090",
        "api_key": "...",
        "default_graph_settings": {
            "use_graph": true,
            "expansion_depth": 1,
            "graph_weight": 0.3
        }
    }
}
```

### 11.3 Query Integration Example

```python
# In LAMB's RAG pipeline
async def query_knowledge_base(
    collection_id: int,
    query: str,
    use_graph: bool = True
) -> List[RetrievedChunk]:
    """Query KB with optional graph enhancement."""
    
    response = await kb_client.post(
        f"/collections/{collection_id}/query",
        json={
            "query_text": query,
            "top_k": 5
        },
        params={
            "use_graph": use_graph,
            "expansion_depth": 1,
            "graph_weight": 0.3
        }
    )
    
    return response.json()['results']
```

---

## 12. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

- [ ] Create database schema (new tables)
- [ ] Implement `ConceptExtractor` class
- [ ] Implement `GraphService` for CRUD operations
- [ ] Add graph router with basic endpoints
- [ ] Integration tests

### Phase 2: Ingestion Integration (Week 2-3)

- [ ] Modify ingestion pipeline to extract concepts
- [ ] Implement co-occurrence edge building
- [ ] Implement expansion table pre-computation
- [ ] Add `extract_concepts` parameter to ingestion endpoints

### Phase 3: Query Enhancement (Week 3-4)

- [ ] Implement graph-enhanced query algorithm
- [ ] Add graph parameters to query endpoint
- [ ] Performance testing and optimization
- [ ] Ensure <50ms overhead target

### Phase 4: User Curation (Week 4-5)

- [ ] Implement concept management endpoints
- [ ] Implement edge management endpoints
- [ ] Implement chunk-concept linking endpoints
- [ ] Implement partial recalculation logic

### Phase 5: Suggestions & Polish (Week 5-6)

- [ ] Implement suggestion engine
- [ ] Add batch operations
- [ ] Documentation
- [ ] LAMB integration testing

---

## 13. Open Questions

### Technical Questions

1. **Concept extraction quality**: Should we use spaCy for better NER, or keep it pure Python?
2. **Embedding consistency**: Should concepts have their own embeddings for smarter matching?
3. **Cross-collection graphs**: Future feature to link concepts across collections?

### Product Questions

1. **Default behavior**: Should graph enhancement be opt-in or opt-out?
2. **Curation workflow**: How much curation is expected? Should we auto-apply suggestions?
3. **Visualization**: Should we provide a graph visualization API/endpoint?

### Performance Questions

1. **Scale limits**: At what collection size does the graph become a bottleneck?
2. **Memory usage**: Should expansion table be cached in memory?
3. **Incremental extraction**: Can we extract concepts for new chunks without reprocessing all?

---

## Appendix A: Pydantic Schemas

```python
# schemas/graph.py

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class EdgeType(str, Enum):
    RELATED = "related"
    CONTAINS = "contains"
    SIMILAR = "similar"
    CONTRASTS = "contrasts"
    REQUIRES = "requires"


class SuggestionSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# ==================== CONCEPTS ====================

class ConceptBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ConceptCreate(ConceptBase):
    pass


class ConceptUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_user_verified: Optional[bool] = None


class ConceptResponse(ConceptBase):
    id: int
    collection_id: int
    normalized_name: str
    frequency: int
    centrality_score: float
    cluster_id: Optional[int]
    is_user_verified: bool
    created_at: datetime
    updated_at: datetime


class ConceptDetailResponse(ConceptResponse):
    chunks: Optional[List[str]] = None
    edges: Optional[List['ConceptEdgeResponse']] = None


class ConceptListResponse(BaseModel):
    total: int
    items: List[ConceptResponse]


class ConceptMergeRequest(BaseModel):
    source_ids: List[int] = Field(..., min_length=2)
    target_name: str


# ==================== EDGES ====================

class ConceptEdgeCreate(BaseModel):
    from_concept_id: int
    to_concept_id: int
    edge_type: EdgeType = EdgeType.RELATED
    weight: float = Field(default=1.0, ge=0.0, le=1.0)


class ConceptEdgeUpdate(BaseModel):
    edge_type: Optional[EdgeType] = None
    weight: Optional[float] = Field(None, ge=0.0, le=1.0)


class ConceptEdgeResponse(BaseModel):
    id: int
    from_concept_id: int
    to_concept_id: int
    from_concept_name: Optional[str] = None
    to_concept_name: Optional[str] = None
    edge_type: EdgeType
    weight: float
    is_user_defined: bool


# ==================== CHUNK-CONCEPT ====================

class ChunkConceptLink(BaseModel):
    concept_id: Optional[int] = None
    concept_name: Optional[str] = None
    relevance_score: float = Field(default=1.0, ge=0.0, le=1.0)


class ChunkConceptResponse(BaseModel):
    concept_id: int
    concept_name: str
    relevance_score: float
    is_user_added: bool


# ==================== CHUNKS ====================

class ChunkDetailResponse(BaseModel):
    id: str
    text: str
    metadata: Dict[str, Any]
    collection_id: int
    concepts: Optional[List[ChunkConceptResponse]] = None
    similar_chunks: Optional[List[str]] = None


class ChunkMetadataUpdate(BaseModel):
    metadata: Dict[str, Any]
    merge: bool = True


# ==================== SUGGESTIONS ====================

class Suggestion(BaseModel):
    id: str
    type: str
    severity: SuggestionSeverity
    message: str
    data: Dict[str, Any]
    action: Dict[str, Any]


class SuggestionsResponse(BaseModel):
    suggestions: List[Suggestion]
    total: int


# ==================== GRAPH STATS ====================

class GraphStatsResponse(BaseModel):
    concept_count: int
    edge_count: int
    chunk_links_count: int
    avg_concepts_per_chunk: float
    cluster_count: int
    verified_concept_count: int
    user_defined_edge_count: int
    last_recalculation: Optional[datetime]


class GraphRecalculationResponse(BaseModel):
    scope: str
    concepts_processed: int
    edges_processed: int
    expansions_generated: int
    duration_ms: float


# ==================== QUERY ENHANCEMENT ====================

class GraphEnhancedQueryParams(BaseModel):
    use_graph: bool = True
    expansion_depth: int = Field(default=1, ge=1, le=2)
    graph_weight: float = Field(default=0.3, ge=0.0, le=1.0)


class GraphQueryInfo(BaseModel):
    expansion_used: bool
    concepts_found: int
    concepts_expanded: int
    expansion_depth: int
```

---

## Appendix B: API Quick Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/collections/{id}/concepts` | GET | List concepts |
| `/collections/{id}/concepts` | POST | Create concept |
| `/collections/{id}/concepts/{cid}` | GET | Get concept detail |
| `/collections/{id}/concepts/{cid}` | PUT | Update concept |
| `/collections/{id}/concepts/{cid}` | DELETE | Delete concept |
| `/collections/{id}/concepts/merge` | POST | Merge concepts |
| `/collections/{id}/edges` | POST | Create edge |
| `/collections/{id}/edges/{eid}` | PUT | Update edge |
| `/collections/{id}/edges/{eid}` | DELETE | Delete edge |
| `/collections/{id}/chunks/{chid}` | GET | Get chunk detail |
| `/collections/{id}/chunks/{chid}/metadata` | PATCH | Update chunk metadata |
| `/collections/{id}/chunks/{chid}/concepts` | GET | List chunk concepts |
| `/collections/{id}/chunks/{chid}/concepts` | POST | Add concept to chunk |
| `/collections/{id}/chunks/{chid}/concepts/{cid}` | DELETE | Remove concept |
| `/collections/{id}/graph/stats` | GET | Get graph statistics |
| `/collections/{id}/graph/recalculate` | POST | Trigger recalculation |
| `/collections/{id}/graph/suggestions` | GET | Get improvement suggestions |
| `/collections/{id}/graph/suggestions/{sid}/apply` | POST | Apply suggestion |
| `/collections/{id}/query` | POST | Query (with graph params) |

---

**Document Version:** 0.1.0  
**Status:** Proposal  
**Next Review:** TBD

