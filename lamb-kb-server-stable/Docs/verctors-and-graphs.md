# Knowledge Bases: Semantic Graphs + Embeddings

## Overview

This document summarizes the two main approaches to building knowledge bases and how to combine them using Python tools.

---

## 1. Semantic Graph Knowledge Bases (Knowledge Graphs)

Knowledge graphs represent information as a network of entities and relationships, structured as triples: `(subject, predicate, object)`.

**Example:** `(Paris, is_capital_of, France)`

### Characteristics

- **Explicit relationships** — connections between concepts are named and typed
- **Symbolic reasoning** — logical traversal (if A is_parent_of B, and B is_parent_of C, then A is_grandparent_of C)
- **Schema/ontology** — formal structure defining valid entity and relationship types

### Examples

Wikidata, Google's Knowledge Graph, enterprise systems using RDF/OWL or Neo4j.

---

## 2. Embedding-Based Knowledge Bases

Information is represented as dense vectors in high-dimensional space. Similar concepts are geometrically close.

### Characteristics

- **Semantic similarity** — captures fuzzy, contextual relationships
- **No explicit structure** — relationships are implicit in vector geometry
- **Great for retrieval** — finds relevant content based on meaning, not keywords

---

## 3. Combining Both Approaches

Often called **hybrid approaches** or **neuro-symbolic AI**.

### Why Combine?

| Knowledge Graphs Struggle With | Embeddings Struggle With |
|-------------------------------|-------------------------|
| Ambiguity | Precise reasoning |
| Incomplete data | Explainability |
| Natural language understanding | Rare entities |
| Scaling to unstructured text | Factual consistency |

### Integration Patterns

1. **Knowledge graph embeddings** — represent KG entities/relations as vectors (TransE, ComplEx, RotatE)
2. **Graph-enhanced retrieval** — use KG to enrich or filter embedding-based retrieval
3. **Grounding LLMs with KGs** — validate retrieved context with structured facts
4. **Hybrid storage** — store both embeddings and graph, combine at query time

---

## 4. Python Tools (Open Source)

### For Knowledge Graphs

| Tool | Description |
|------|-------------|
| **NetworkX** | Pure Python, in-memory, great for prototyping |
| **RDFLib** | Standard library for RDF/SPARQL |
| **Neo4j** | Popular property graph database with Cypher queries |
| **Kuzu** | Embedded graph database (like SQLite for graphs) |
| **igraph** | Fast graph algorithms |

### For Vector/Embedding Storage

| Tool | Description |
|------|-------------|
| **ChromaDB** | Simple, embedded, designed for LLM apps |
| **Qdrant** | Feature-rich, supports filtering |
| **Weaviate** | Hybrid search (vectors + keywords) |
| **FAISS** | Raw vector index, very fast |
| **LanceDB** | Embedded, good for multimodal |

### For Hybrid Approaches

| Tool | Description |
|------|-------------|
| **LlamaIndex** | Combines KG + vector retrieval with built-in support |
| **LangChain** | General-purpose, integrates both stores |
| **Haystack** | Framework with graph and vector options |

### Recommended Stacks

| Use Case | Stack |
|----------|-------|
| Quick prototyping | NetworkX + ChromaDB |
| Persistent graphs, local | Kuzu + ChromaDB or Qdrant |
| Standards-compliant RDF | RDFLib + FAISS or Qdrant |
| Full-featured | Neo4j Community + Qdrant |
| Integrated framework | LlamaIndex |

---

## 5. LlamaIndex: Combining Knowledge Graphs and Embeddings

LlamaIndex provides abstractions to:
1. Extract a knowledge graph from documents
2. Store embeddings of text chunks
3. Query both and combine results

### Installation

```bash
pip install llama-index
pip install llama-index-llms-openai llama-index-embeddings-openai
pip install llama-index-graph-stores-neo4j  # if using Neo4j
pip install pyvis  # for visualization
```

---

### Approach 1: Pure Knowledge Graph Index

Extracts entities and relationships from text, builds a traversable graph.

```python
from llama_index.core import SimpleDirectoryReader, KnowledgeGraphIndex
from llama_index.core.graph_stores import SimpleGraphStore
from llama_index.llms.openai import OpenAI
from llama_index.core import Settings

# Configure the LLM (used for extraction and querying)
Settings.llm = OpenAI(model="gpt-4o-mini", temperature=0)

# Load your documents
documents = SimpleDirectoryReader("./data").load_data()

# Create a graph store (in-memory for simplicity)
graph_store = SimpleGraphStore()

# Build the knowledge graph index
# LlamaIndex uses the LLM to extract (subject, predicate, object) triples
kg_index = KnowledgeGraphIndex.from_documents(
    documents,
    max_triplets_per_chunk=10,
    graph_store=graph_store,
    include_embeddings=False,  # pure graph, no vectors yet
)

# Query using graph traversal
query_engine = kg_index.as_query_engine()
response = query_engine.query("How is Alice related to Bob?")
print(response)
```

**What happens:** The LLM reads each chunk and extracts structured triples like `(Alice, works_with, Bob)`. Queries traverse this graph to find relevant paths.

---

### Approach 2: Pure Vector Store Index (Standard RAG)

Classic embedding-based retrieval.

```python
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core import Settings

Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")

documents = SimpleDirectoryReader("./data").load_data()

# Build vector index - chunks are embedded and stored
vector_index = VectorStoreIndex.from_documents(documents)

# Query using semantic similarity
query_engine = vector_index.as_query_engine()
response = query_engine.query("What projects is Alice working on?")
print(response)
```

---

### Approach 3: Knowledge Graph with Embeddings (Hybrid)

Include embeddings in the knowledge graph index for both structured traversal and semantic search.

```python
from llama_index.core import SimpleDirectoryReader, KnowledgeGraphIndex
from llama_index.core.graph_stores import SimpleGraphStore
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core import Settings

Settings.llm = OpenAI(model="gpt-4o-mini", temperature=0)
Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")

documents = SimpleDirectoryReader("./data").load_data()
graph_store = SimpleGraphStore()

# Build KG index WITH embeddings
kg_index = KnowledgeGraphIndex.from_documents(
    documents,
    max_triplets_per_chunk=10,
    graph_store=graph_store,
    include_embeddings=True,  # now we have both!
)

# Query engine can use embedding similarity to find relevant 
# subgraphs, then traverse them
query_engine = kg_index.as_query_engine(
    include_text=True,  # include source text in response context
    retriever_mode="hybrid",  # use both embedding and keyword matching
)

response = query_engine.query("What are the main themes in the company's strategy?")
print(response)
```

---

### Approach 4: Explicit Hybrid Retriever (Maximum Control)

Create separate indices and combine their retrievers with fusion.

```python
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, KnowledgeGraphIndex
from llama_index.core.graph_stores import SimpleGraphStore
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core import Settings

Settings.llm = OpenAI(model="gpt-4o-mini", temperature=0)
Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")

# Load documents
documents = SimpleDirectoryReader("./data").load_data()

# Build both indices
vector_index = VectorStoreIndex.from_documents(documents)

graph_store = SimpleGraphStore()
kg_index = KnowledgeGraphIndex.from_documents(
    documents,
    max_triplets_per_chunk=10,
    graph_store=graph_store,
)

# Get retrievers from each
vector_retriever = vector_index.as_retriever(similarity_top_k=5)
kg_retriever = kg_index.as_retriever()

# Combine them with fusion
hybrid_retriever = QueryFusionRetriever(
    retrievers=[vector_retriever, kg_retriever],
    num_queries=1,  # don't generate query variations
    use_async=False,
)

# Build query engine from hybrid retriever
query_engine = RetrieverQueryEngine.from_args(hybrid_retriever)

response = query_engine.query("Explain the relationship between the product team and engineering")
print(response)
```

---

### Using Neo4j for Persistent Storage

For production use beyond prototyping.

```python
from llama_index.core import SimpleDirectoryReader, KnowledgeGraphIndex
from llama_index.graph_stores.neo4j import Neo4jGraphStore
from llama_index.core import StorageContext

# Connect to Neo4j
graph_store = Neo4jGraphStore(
    username="neo4j",
    password="your_password",
    url="bolt://localhost:7687",
    database="neo4j",
)

storage_context = StorageContext.from_defaults(graph_store=graph_store)

documents = SimpleDirectoryReader("./data").load_data()

# Build index - triples are stored in Neo4j
kg_index = KnowledgeGraphIndex.from_documents(
    documents,
    storage_context=storage_context,
    max_triplets_per_chunk=10,
    include_embeddings=True,
)

# Now you can also query Neo4j directly with Cypher if needed
```

---

### Visualizing the Knowledge Graph

Useful for debugging and understanding extracted structure.

```python
from pyvis.network import Network

# Get the networkx graph from the index
g = kg_index.get_networkx_graph()

# Visualize with pyvis
net = Network(notebook=True, directed=True)
net.from_nx(g)
net.show("knowledge_graph.html")
```

---

## 6. How It Works Under the Hood

### During Indexing

1. Documents are split into chunks
2. **For KG:** LLM extracts `(subject, relation, object)` triples from each chunk
3. **For vectors:** each chunk is embedded
4. Both are stored with links between triples and source chunks

### During Querying

1. **KG retrieval:** finds entities in query, traverses graph for related nodes/paths
2. **Vector retrieval:** embeds query, finds similar chunks
3. **Hybrid:** does both, merges/reranks results
4. LLM synthesizes response from retrieved context

---

## Summary

| Approach | Best For |
|----------|----------|
| Pure Knowledge Graph | Explicit relationships, reasoning, explainability |
| Pure Vector/Embeddings | Semantic similarity, fuzzy matching, unstructured text |
| Hybrid | Complex queries needing both structured facts and semantic understanding |

LlamaIndex makes it straightforward to implement any of these approaches and combine them as needed.