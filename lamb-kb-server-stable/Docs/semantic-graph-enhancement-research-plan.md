# Semantic Graph Enhancement: Research & Evaluation Plan

**Version:** 0.1.0  
**Created:** December 22, 2025  
**Status:** Research Planning  
**Related Document:** `semantic-graph-enhancement.md`

---

## Table of Contents

1. [Research Overview](#1-research-overview)
2. [Research Questions & Hypotheses](#2-research-questions--hypotheses)
3. [Evaluation Framework](#3-evaluation-framework)
4. [Experimental Design](#4-experimental-design)
5. [Datasets & Benchmarks](#5-datasets--benchmarks)
6. [Experimental Protocol](#6-experimental-protocol)
7. [Statistical Analysis Plan](#7-statistical-analysis-plan)
8. [Paper Structure](#8-paper-structure)
9. [Related Work Landscape](#9-related-work-landscape)
10. [Publication Strategy](#10-publication-strategy)
11. [Resource Requirements](#11-resource-requirements)
12. [Timeline](#12-timeline)
13. [Risk Assessment](#13-risk-assessment)

---

## 1. Research Overview

### 1.1 Research Context

Retrieval-Augmented Generation (RAG) systems have become the dominant paradigm for grounding Large Language Models in external knowledge. However, current RAG implementations rely primarily on vector similarity search, which has inherent limitations:

- **Vocabulary mismatch**: Query terms may differ from document terms
- **Implicit relationships**: Conceptual connections not captured by embedding proximity
- **Multi-hop reasoning**: Information spanning multiple documents poorly retrieved
- **Context blindness**: Embeddings don't capture domain-specific concept structures

### 1.2 Proposed Innovation

We propose enhancing vector retrieval with a **lightweight, corpus-derived semantic graph** that:

1. Extracts concepts from documents during ingestion
2. Builds relationship edges based on co-occurrence and semantic similarity
3. Pre-computes expansion tables for query-time efficiency
4. Enables user curation to refine the knowledge structure

### 1.3 Key Claims to Validate

| Claim | Type | Priority |
|-------|------|----------|
| Graph enhancement improves retrieval relevance | Effectiveness | P0 |
| Pre-computation keeps query latency acceptable | Efficiency | P0 |
| Corpus-derived graphs outperform generic KGs for domain tasks | Comparative | P1 |
| User curation provides measurable improvement | Effectiveness | P1 |
| Approach generalizes across domains | Generalization | P2 |

---

## 2. Research Questions & Hypotheses

### 2.1 Primary Research Questions

**RQ1: Retrieval Effectiveness**
> Does semantic graph augmentation improve retrieval relevance compared to pure vector search in RAG knowledge base scenarios?

**RQ2: Efficiency Trade-offs**
> What is the trade-off between query latency and retrieval quality gains when using graph enhancement?

**RQ3: Query Characteristics**
> For which types of queries does graph enhancement provide the most benefit?

**RQ4: Curation Value**
> Does human curation of the concept graph improve retrieval quality beyond automatic extraction, and what is the effort-benefit ratio?

**RQ5: Domain Generalization**
> How does the approach perform across different domain types (technical, scientific, general)?

### 2.2 Hypotheses

```
H1: RETRIEVAL IMPROVEMENT
    Graph-enhanced retrieval achieves statistically significant higher 
    Precision@10 and MRR than vector-only retrieval (α = 0.05).
    
    Expected effect size: Cohen's d ≥ 0.5 (medium effect)

H2: QUERY TYPE DEPENDENCY
    The performance improvement is significantly larger for multi-concept 
    queries (requiring 2+ concepts) than single-concept queries.
    
    Expected: ΔPrecision@10 ≥ 15% for multi-concept vs. ≤ 5% for single-concept

H3: LATENCY BOUNDS
    Graph enhancement adds less than 50ms (p95) to query latency when 
    using pre-computed expansion tables.
    
    Measurement: p50, p95, p99 latency distributions

H4: CURATION IMPACT
    Curated graphs achieve ≥10% relative improvement in MRR over 
    auto-generated graphs after 2 hours of expert curation.
    
    Expected: Diminishing returns after ~4 hours of curation

H5: EXPANSION DEPTH
    1-hop expansion provides >80% of the benefit of 2-hop expansion 
    with significantly lower complexity.
    
    Measurement: Compare performance at expansion_depth = 1, 2, 3
```

### 2.3 Null Hypotheses (for Statistical Testing)

```
H0_1: There is no difference in Precision@10 between graph-enhanced 
      and vector-only retrieval.

H0_2: Query type (single vs. multi-concept) does not moderate the 
      effectiveness of graph enhancement.

H0_3: Graph enhancement latency overhead exceeds 50ms at p95.

H0_4: Curated graphs do not outperform auto-generated graphs.
```

---

## 3. Evaluation Framework

### 3.1 Evaluation Dimensions

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        EVALUATION DIMENSIONS                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐   │
│  │    RETRIEVAL      │  │    EFFICIENCY     │  │   USER-CENTRIC    │   │
│  │    QUALITY        │  │                   │  │                   │   │
│  ├───────────────────┤  ├───────────────────┤  ├───────────────────┤   │
│  │ • Precision@k     │  │ • Query latency   │  │ • Task completion │   │
│  │ • Recall@k        │  │ • Ingestion time  │  │ • Time to answer  │   │
│  │ • MRR             │  │ • Storage overhead│  │ • Satisfaction    │   │
│  │ • nDCG@k          │  │ • Memory usage    │  │ • Explainability  │   │
│  │ • MAP             │  │                   │  │ • Preference      │   │
│  └───────────────────┘  └───────────────────┘  └───────────────────┘   │
│                                                                         │
│  ┌───────────────────┐  ┌───────────────────┐                          │
│  │  GRAPH-SPECIFIC   │  │   ROBUSTNESS      │                          │
│  ├───────────────────┤  ├───────────────────┤                          │
│  │ • Expansion util. │  │ • Cross-domain    │                          │
│  │ • Concept coverage│  │ • Corpus size     │                          │
│  │ • Path relevance  │  │ • Noise tolerance │                          │
│  │ • Serendipity     │  │ • Edge cases      │                          │
│  └───────────────────┘  └───────────────────┘                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Primary Metrics

#### Retrieval Quality Metrics

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **Precision@k** | `\|relevant ∩ retrieved_k\| / k` | Accuracy of top-k results |
| **Recall@k** | `\|relevant ∩ retrieved_k\| / \|relevant\|` | Coverage of relevant docs |
| **MRR** | `mean(1 / rank_first_relevant)` | How quickly relevant docs appear |
| **nDCG@k** | Normalized DCG with graded relevance | Quality-weighted ranking |
| **MAP** | Mean of precision at each relevant doc | Overall ranking quality |

#### Efficiency Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Query Latency (p50)** | < 150ms | Timer around query function |
| **Query Latency (p95)** | < 250ms | 95th percentile |
| **Graph Overhead** | < 50ms | Total - vector_only latency |
| **Ingestion Throughput** | > 10 docs/sec | Documents per second |
| **Storage Overhead** | < 20% increase | Graph tables / total storage |

#### Graph-Specific Metrics

| Metric | Definition | Purpose |
|--------|------------|---------|
| **Expansion Utility** | % of final results from graph expansion | Is expansion finding useful docs? |
| **Concept Hit Rate** | % of query concepts found in graph | Graph coverage of query space |
| **Serendipity Score** | Relevant results not in vector top-k | Unique value of graph |

### 3.3 Secondary Metrics (User Study)

| Metric | Scale | Collection |
|--------|-------|------------|
| **Perceived Relevance** | 1-7 Likert | Post-query rating |
| **Result Diversity** | 1-7 Likert | Post-query rating |
| **System Preference** | Forced choice | End of session |
| **Trust** | 1-7 Likert | Post-session questionnaire |
| **Explainability** | 1-7 Likert | "I understand why these results appeared" |

---

## 4. Experimental Design

### 4.1 Experimental Conditions

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      EXPERIMENTAL CONDITIONS                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  BASELINES                                                              │
│  ─────────                                                              │
│  B0: BM25 (Lexical)                                                     │
│      Traditional keyword matching with TF-IDF weighting                 │
│                                                                         │
│  B1: Vector-Only                                                        │
│      ChromaDB dense retrieval with OpenAI/Ollama embeddings             │
│      (Current lamb-kb-server implementation)                            │
│                                                                         │
│  B2: Hybrid (BM25 + Vector)                                             │
│      Reciprocal Rank Fusion of B0 and B1                                │
│      (Common strong baseline in literature)                             │
│                                                                         │
│  B3: Vector + External KG                                               │
│      Vector search with entity linking to ConceptNet/Wikidata           │
│      (Alternative graph approach)                                       │
│                                                                         │
│  EXPERIMENTAL CONDITIONS                                                │
│  ───────────────────────                                                │
│  E1: Vector + Auto-Graph                                                │
│      Our approach with automatic concept extraction                     │
│      No human curation                                                  │
│                                                                         │
│  E2: Vector + Auto-Graph + Suggestions                                  │
│      Auto-graph with system suggestions automatically applied           │
│                                                                         │
│  E3: Vector + Curated-Graph                                             │
│      Graph refined by domain expert (2 hours curation)                  │
│                                                                         │
│  E4: Vector + Heavily-Curated-Graph                                     │
│      Graph refined by domain expert (8 hours curation)                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Independent Variables

| Variable | Levels | Type |
|----------|--------|------|
| **Retrieval Method** | B0, B1, B2, B3, E1, E2, E3, E4 | Between-condition |
| **Graph Weight** | 0.0, 0.1, 0.3, 0.5, 0.7 | Parameter sweep |
| **Expansion Depth** | 0, 1, 2 | Parameter sweep |
| **Query Type** | Single-concept, Multi-concept, Implicit | Stratification |
| **Domain** | Technical, Scientific, General | Dataset factor |
| **Corpus Size** | Small (1K), Medium (10K), Large (100K) | Scalability factor |

### 4.3 Dependent Variables

| Variable | Measurement |
|----------|-------------|
| Precision@k (k=1,5,10,20) | Automated calculation |
| Recall@k | Automated calculation |
| MRR | Automated calculation |
| nDCG@k | Automated calculation |
| Query Latency | System timer |
| User Satisfaction | Likert scale |

### 4.4 Control Variables

| Variable | Control Method |
|----------|----------------|
| Embedding Model | Fixed (text-embedding-3-small) for main experiments |
| Chunk Size | Fixed (1000 tokens, 200 overlap) |
| Hardware | Same machine for all timing experiments |
| Query Set | Same queries across all conditions |

### 4.5 Ablation Studies

| Ablation | Purpose |
|----------|---------|
| No concept extraction | Isolate value of concepts |
| No co-occurrence edges | Value of automatic edge detection |
| No centrality weighting | Value of concept importance |
| No expansion (graph_weight=0) | Pure vector baseline |
| No pre-computation | Measure pre-computation benefit |
| Random concept assignment | Validate concept extraction quality |

---

## 5. Datasets & Benchmarks

### 5.1 Dataset Selection Criteria

| Criterion | Rationale |
|-----------|-----------|
| **Domain relevance** | Should represent RAG knowledge base use cases |
| **Size** | Large enough for statistical power (>1000 queries) |
| **Relevance judgments** | Must have or allow creation of gold labels |
| **Concept density** | Should have extractable concept structure |
| **Reproducibility** | Publicly available or clearly defined |

### 5.2 Primary Datasets

#### Dataset 1: Technical Documentation (Custom)

```
Name: TechDocs-KB
Domain: Software/ML documentation
Source: PyTorch docs, Scikit-learn docs, FastAPI docs
Size: ~5,000 documents, ~50,000 chunks
Queries: 200 manually created + 300 synthetic
Relevance: Expert annotation (3 annotators)

Rationale: Directly represents lamb-kb-server use case
```

#### Dataset 2: Scientific Papers (Custom)

```
Name: ArXiv-ML-Subset
Domain: Machine Learning research
Source: ArXiv CS.LG papers (2020-2024)
Size: ~10,000 abstracts + introductions
Queries: 150 research questions
Relevance: Citation-based + expert annotation

Rationale: Technical domain with rich concept structure
```

#### Dataset 3: BEIR Subset (Standard Benchmark)

```
Name: BEIR-Selected
Datasets: 
  - SciFact (scientific claim verification)
  - NFCorpus (nutrition/medical)
  - FiQA (financial QA)
Size: Varies by subset
Queries: Standard benchmark queries
Relevance: Provided by benchmark

Rationale: Enables comparison with published results
```

### 5.3 Query Set Construction

#### Query Taxonomy

| Type | Definition | Example | Expected % |
|------|------------|---------|------------|
| **Single-concept** | One clear topic | "What is dropout?" | 30% |
| **Multi-concept** | Multiple explicit topics | "How does dropout prevent overfitting?" | 40% |
| **Implicit relationship** | Concepts implied, not stated | "Techniques for training stability" | 20% |
| **Comparative** | Requires connecting docs | "Batch norm vs layer norm" | 10% |

#### Query Generation Methods

```
Method 1: Expert Creation
├── Domain experts write realistic queries
├── Ensure coverage of query types
└── 50-100 queries per dataset

Method 2: Template-Based
├── "[Concept] explanation"
├── "How does [Concept A] relate to [Concept B]"
├── "[Task] using [Method]"
└── 100-200 queries per dataset

Method 3: User Log Mining (if available)
├── Extract real queries from system logs
├── Anonymize and filter
└── Most realistic but limited availability
```

### 5.4 Relevance Judgment Protocol

#### Annotation Guidelines

```
Relevance Scale (0-3):
─────────────────────
0 - Not Relevant: Document does not address the query topic
1 - Marginally Relevant: Document mentions query topic but doesn't answer
2 - Relevant: Document partially answers the query
3 - Highly Relevant: Document directly and completely addresses the query

Annotation Process:
1. Annotator reads query
2. Annotator reads document chunk
3. Annotator assigns relevance score
4. Annotator provides brief justification (optional)

Quality Control:
- 3 annotators per query-document pair
- Fleiss' Kappa for inter-annotator agreement (target: κ > 0.6)
- Adjudication for disagreements
```

#### Annotation Effort Estimate

| Dataset | Query-Doc Pairs | Annotators | Total Judgments | Est. Hours |
|---------|-----------------|------------|-----------------|------------|
| TechDocs-KB | 500 queries × 20 docs | 3 | 30,000 | 100 |
| ArXiv-ML | 150 queries × 20 docs | 3 | 9,000 | 30 |
| BEIR | Provided | - | - | 0 |

---

## 6. Experimental Protocol

### 6.1 Offline Evaluation Pipeline

```python
"""
Evaluation Pipeline Pseudocode
"""

class RetrievalEvaluator:
    def __init__(self, metrics=['precision', 'recall', 'mrr', 'ndcg']):
        self.metrics = metrics
        self.k_values = [1, 5, 10, 20]
    
    def evaluate_system(
        self, 
        system: RetrievalSystem, 
        dataset: EvaluationDataset,
        num_runs: int = 5  # For latency stability
    ) -> EvaluationResults:
        
        results = {
            'per_query': [],
            'aggregate': {},
            'latency': {'values': [], 'p50': 0, 'p95': 0, 'p99': 0}
        }
        
        for query_id, query_text, relevant_docs in dataset:
            query_results = {'query_id': query_id}
            
            # Multiple runs for latency measurement
            latencies = []
            for _ in range(num_runs):
                start = time.perf_counter()
                retrieved = system.query(query_text, top_k=max(self.k_values))
                latencies.append(time.perf_counter() - start)
            
            results['latency']['values'].extend(latencies)
            
            # Calculate metrics
            for k in self.k_values:
                retrieved_k = retrieved[:k]
                query_results[f'precision@{k}'] = self.precision_at_k(
                    retrieved_k, relevant_docs
                )
                query_results[f'recall@{k}'] = self.recall_at_k(
                    retrieved_k, relevant_docs
                )
                query_results[f'ndcg@{k}'] = self.ndcg_at_k(
                    retrieved_k, relevant_docs
                )
            
            query_results['mrr'] = self.mrr(retrieved, relevant_docs)
            query_results['query_type'] = self.classify_query(query_text)
            
            results['per_query'].append(query_results)
        
        # Aggregate results
        results['aggregate'] = self.aggregate(results['per_query'])
        results['latency']['p50'] = np.percentile(results['latency']['values'], 50)
        results['latency']['p95'] = np.percentile(results['latency']['values'], 95)
        results['latency']['p99'] = np.percentile(results['latency']['values'], 99)
        
        return results
    
    def compare_systems(
        self, 
        systems: Dict[str, RetrievalSystem],
        dataset: EvaluationDataset
    ) -> ComparisonResults:
        
        all_results = {}
        for name, system in systems.items():
            all_results[name] = self.evaluate_system(system, dataset)
        
        # Statistical comparisons
        comparisons = self.statistical_tests(all_results)
        
        return ComparisonResults(
            individual=all_results,
            comparisons=comparisons
        )
```

### 6.2 Experiment Execution Plan

#### Phase 1: Baseline Establishment

```
Duration: 1 week

Tasks:
□ Implement BM25 baseline (using rank_bm25 or similar)
□ Verify vector-only baseline (current system)
□ Implement hybrid baseline (RRF fusion)
□ Run all baselines on all datasets
□ Verify metrics calculation against known benchmarks
□ Establish latency baselines

Deliverable: Baseline performance table
```

#### Phase 2: Graph System Evaluation

```
Duration: 2 weeks

Tasks:
□ Deploy graph-enhanced system (E1)
□ Run E1 on all datasets
□ Parameter sweep: graph_weight ∈ {0.1, 0.2, 0.3, 0.4, 0.5}
□ Parameter sweep: expansion_depth ∈ {1, 2}
□ Ablation studies
□ Latency profiling

Deliverable: Graph enhancement performance table, ablation results
```

#### Phase 3: Curation Impact Study

```
Duration: 2 weeks

Tasks:
□ Recruit domain expert(s) for curation
□ Record baseline (E1) performance
□ Curation session 1 (2 hours) → Measure E3
□ Curation session 2 (2 hours) → Measure intermediate
□ Curation session 3 (2 hours) → Measure intermediate  
□ Curation session 4 (2 hours) → Measure E4
□ Analyze curation effort vs. improvement curve

Deliverable: Curation impact analysis
```

#### Phase 4: User Study (Optional)

```
Duration: 2 weeks

Participants: 30-50 (students or practitioners)
Design: Within-subjects, counterbalanced

Protocol:
1. Consent and demographics (5 min)
2. Training on system (10 min)
3. Search tasks - 10 queries total (40 min)
   - 5 with graph enhancement (random selection)
   - 5 without graph enhancement
   - Order counterbalanced
4. Post-task questionnaire per query (2 min each)
5. Final questionnaire and preference (10 min)

Measures:
- Task completion (binary)
- Time to answer
- Clicks/reformulations
- Perceived relevance (1-7)
- System preference (forced choice)

Deliverable: User study results and analysis
```

### 6.3 Reproducibility Checklist

```
□ All code in version control with tagged releases
□ Requirements.txt with pinned versions
□ Random seeds fixed and documented
□ Dataset splits saved and versioned
□ Hyperparameters documented
□ Hardware specifications recorded
□ Evaluation scripts included
□ Statistical analysis scripts included
□ Raw results data preserved
```

---

## 7. Statistical Analysis Plan

### 7.1 Sample Size Justification

```
Power Analysis for Paired Comparison:
─────────────────────────────────────
Effect size (Cohen's d): 0.5 (medium, conservative)
α (Type I error rate): 0.05
Power (1 - β): 0.80

Required sample size: n ≈ 34 queries per condition

With 200+ queries per dataset, we have sufficient power
to detect medium effects.
```

### 7.2 Statistical Tests

| Comparison | Test | Assumptions | Alternative |
|------------|------|-------------|-------------|
| A vs B (paired) | Paired t-test | Normality | Wilcoxon signed-rank |
| Multiple systems | Repeated measures ANOVA | Sphericity | Friedman test |
| Effect of query type | Two-way ANOVA | Normality, homogeneity | Aligned Rank Transform |
| Correlation analysis | Pearson's r | Linearity | Spearman's ρ |

### 7.3 Multiple Comparison Correction

```
With multiple comparisons, apply correction:

Primary analysis (6 pairwise comparisons):
- Bonferroni correction: α_adj = 0.05 / 6 = 0.0083
- Or Holm-Bonferroni (step-down, more powerful)

Exploratory analysis:
- False Discovery Rate (FDR) control
- Benjamini-Hochberg procedure
```

### 7.4 Effect Size Reporting

```
For each significant result, report:

1. Effect size (Cohen's d for continuous, odds ratio for binary)
   d = (M1 - M2) / SD_pooled
   
   Interpretation:
   - d = 0.2: Small
   - d = 0.5: Medium
   - d = 0.8: Large

2. 95% Confidence Interval
   CI = M ± 1.96 × SE

3. Practical significance discussion
```

### 7.5 Analysis Scripts

```python
"""
Statistical Analysis Pseudocode
"""

from scipy import stats
import numpy as np

def paired_comparison(system_a_results, system_b_results, metric='precision@10'):
    """Compare two systems on same query set."""
    
    a_scores = [r[metric] for r in system_a_results]
    b_scores = [r[metric] for r in system_b_results]
    
    # Check normality
    _, p_normal_a = stats.shapiro(a_scores)
    _, p_normal_b = stats.shapiro(b_scores)
    
    if p_normal_a > 0.05 and p_normal_b > 0.05:
        # Parametric test
        t_stat, p_value = stats.ttest_rel(a_scores, b_scores)
        test_name = "Paired t-test"
    else:
        # Non-parametric test
        t_stat, p_value = stats.wilcoxon(a_scores, b_scores)
        test_name = "Wilcoxon signed-rank"
    
    # Effect size
    diff = np.array(a_scores) - np.array(b_scores)
    cohens_d = np.mean(diff) / np.std(diff, ddof=1)
    
    # Confidence interval (bootstrap)
    ci_low, ci_high = bootstrap_ci(diff)
    
    return {
        'test': test_name,
        'statistic': t_stat,
        'p_value': p_value,
        'mean_a': np.mean(a_scores),
        'mean_b': np.mean(b_scores),
        'difference': np.mean(diff),
        'cohens_d': cohens_d,
        'ci_95': (ci_low, ci_high),
        'significant': p_value < 0.05
    }


def stratified_analysis(results, stratify_by='query_type'):
    """Analyze results stratified by query characteristics."""
    
    strata = {}
    for r in results:
        stratum = r[stratify_by]
        if stratum not in strata:
            strata[stratum] = []
        strata[stratum].append(r)
    
    analysis = {}
    for stratum, stratum_results in strata.items():
        analysis[stratum] = {
            'n': len(stratum_results),
            'mean_precision@10': np.mean([r['precision@10'] for r in stratum_results]),
            'std_precision@10': np.std([r['precision@10'] for r in stratum_results]),
            # ... other metrics
        }
    
    return analysis
```

---

## 8. Paper Structure

### 8.1 Target Venues

| Venue | Type | Fit | Typical Deadline |
|-------|------|-----|------------------|
| **SIGIR** | Conference | Core IR | January |
| **EMNLP** | Conference | NLP + Retrieval | May |
| **CIKM** | Conference | Knowledge Management | May |
| **ECIR** | Conference | European IR | October |
| **NAACL** | Conference | NLP | December |
| **IRJ** | Journal | Information Retrieval | Rolling |
| **TACL** | Journal | Computational Linguistics | Rolling |

### 8.2 Paper Outline

```
Title: "Beyond Vectors: Lightweight Semantic Graphs for Enhanced 
        RAG Retrieval in Knowledge Base Systems"

Alternative Titles:
- "Graph-Augmented Retrieval with Pre-computed Concept Expansion"
- "Bridging Concepts: Corpus-Derived Graphs for Knowledge Base Search"

Abstract (250 words)
────────────────────
• Context: RAG systems, vector search limitations
• Problem: Multi-concept queries, implicit relationships
• Approach: Corpus-derived semantic graph, pre-computed expansions
• Key results: X% improvement in Precision@10, <50ms overhead
• Significance: Practical enhancement for production RAG systems

1. Introduction (1.5 pages)
───────────────────────────
1.1 RAG systems and their growing importance
1.2 Limitations of pure vector retrieval
1.3 Our approach: lightweight semantic graphs
1.4 Contributions:
    • Novel architecture for graph-augmented retrieval
    • Pre-computation strategy for query-time efficiency
    • User curation interface with automatic suggestions
    • Comprehensive evaluation across domains
1.5 Paper organization

2. Related Work (1.5 pages)
───────────────────────────
2.1 Dense Passage Retrieval
    • DPR, ColBERT, Contriever
2.2 Knowledge Graphs in Information Retrieval
    • Entity linking approaches
    • KGAT, knowledge-enhanced retrievers
2.3 Hybrid Retrieval Systems
    • BM25 + dense combinations
    • Reciprocal Rank Fusion
2.4 RAG Systems
    • Original RAG, REALM, FiD
    • Recent improvements
2.5 Positioning of our work

3. Approach (3 pages)
─────────────────────
3.1 System Overview
    • Architecture diagram
    • Design principles (query-time efficiency)
3.2 Concept Extraction
    • Extraction methods (TF-IDF, NER, patterns)
    • Normalization and deduplication
3.3 Graph Construction
    • Co-occurrence edge building
    • Edge weighting
3.4 Pre-computed Expansions
    • Expansion table design
    • Update strategy
3.5 Query-time Integration
    • Algorithm pseudocode
    • Ranking combination
3.6 User Curation Interface
    • Curation operations
    • Suggestion generation

4. Experimental Setup (2 pages)
───────────────────────────────
4.1 Research Questions
4.2 Datasets
    • Description and statistics
    • Query taxonomy
4.3 Baselines
4.4 Evaluation Metrics
4.5 Implementation Details
    • Embedding model
    • Chunking strategy
    • Hardware

5. Results (2.5 pages)
──────────────────────
5.1 Overall Retrieval Performance
    • Table: All systems × All metrics
    • Statistical significance
5.2 Performance by Query Type
    • Stratified analysis
    • Where graph helps most
5.3 Ablation Studies
    • Component contributions
    • Parameter sensitivity
5.4 Efficiency Analysis
    • Latency breakdown
    • Scalability

6. Analysis & Discussion (1.5 pages)
────────────────────────────────────
6.1 When Does Graph Enhancement Help?
    • Query characteristics
    • Corpus characteristics
6.2 Failure Cases
    • When graph hurts
    • Mitigation strategies
6.3 Curation Impact
    • Effort vs. benefit curve
    • Recommendations
6.4 Limitations
    • Concept extraction quality
    • Domain dependency
    • Scalability bounds

7. Conclusion (0.5 pages)
─────────────────────────
• Summary of contributions
• Key findings
• Future work directions

References (1-2 pages)

Appendix
────────
A. Implementation details
B. Additional results tables
C. User study protocol (if applicable)
D. Example queries and results
```

### 8.3 Key Figures and Tables

```
Figure 1: System Architecture
- High-level architecture diagram
- Data flow for ingestion and query

Figure 2: Query-time Algorithm
- Flowchart or pseudocode visualization

Figure 3: Performance by Query Type
- Grouped bar chart showing improvement varies by query type

Figure 4: Parameter Sensitivity
- Line plots for graph_weight and expansion_depth

Figure 5: Latency Breakdown
- Stacked bar chart showing time components

Figure 6: Curation Impact Curve
- X: curation hours, Y: performance improvement

Table 1: Dataset Statistics
Table 2: Overall Performance Comparison
Table 3: Ablation Study Results
Table 4: Latency Statistics
```

---

## 9. Related Work Landscape

### 9.1 Key Papers to Cite

#### Dense Retrieval

```
[1] Karpukhin et al. (2020) "Dense Passage Retrieval for Open-Domain QA"
    - DPR baseline, dual encoder architecture

[2] Khattab & Zaharia (2020) "ColBERT: Efficient and Effective Passage 
    Search via Contextualized Late Interaction"
    - Late interaction, token-level matching

[3] Izacard et al. (2022) "Unsupervised Dense Information Retrieval 
    with Contrastive Learning" (Contriever)
    - Unsupervised dense retrieval
```

#### Knowledge Graphs in IR

```
[4] Liu et al. (2020) "K-BERT: Enabling Language Representation with 
    Knowledge Graph"
    - Integrating KG into language models

[5] Zhang et al. (2019) "ERNIE: Enhanced Language Representation with 
    Informative Entities"
    - Entity-enhanced pre-training

[6] Xiong et al. (2017) "Explicit Semantic Ranking for Academic Search"
    - Semantic graphs for academic search
```

#### RAG Systems

```
[7] Lewis et al. (2020) "Retrieval-Augmented Generation for Knowledge-
    Intensive NLP Tasks"
    - Original RAG paper

[8] Izacard & Grave (2021) "Leveraging Passage Retrieval with Generative 
    Models for Open Domain Question Answering" (FiD)
    - Fusion-in-Decoder

[9] Guu et al. (2020) "REALM: Retrieval-Augmented Language Model 
    Pre-Training"
    - Pre-training with retrieval
```

#### Hybrid Retrieval

```
[10] Lin et al. (2021) "Pyserini: A Python Toolkit for Reproducible 
     Information Retrieval Research with Sparse and Dense Representations"
     - Hybrid retrieval toolkit

[11] Ma et al. (2021) "A Replication Study of Dense Passage Retriever"
     - BM25 + DPR fusion analysis
```

### 9.2 Differentiation Statement

```
Our work differs from prior approaches in several key ways:

1. CORPUS-DERIVED vs. EXTERNAL KGs
   Prior: Entity linking to Wikidata/ConceptNet
   Ours: Build domain-specific graph from corpus itself
   Advantage: Domain adaptation without external resources

2. PRE-COMPUTATION vs. QUERY-TIME GRAPH OPS
   Prior: Graph traversal at query time (expensive)
   Ours: Pre-computed expansion tables (O(1) lookup)
   Advantage: Predictable, low latency

3. USER CURATION INTERFACE
   Prior: Fully automatic or fully manual KG construction
   Ours: Automatic with human-in-the-loop refinement
   Advantage: Best of both worlds

4. PRACTICAL SYSTEM FOCUS
   Prior: Often research prototypes
   Ours: Production-ready integration with RAG pipeline
   Advantage: Immediate practical applicability
```

---

## 10. Publication Strategy

### 10.1 Submission Timeline

```
Option A: Conference Track (SIGIR 2026)
──────────────────────────────────────
Oct 2025: Implementation complete
Nov 2025: Experiments running
Dec 2025: Analysis and writing
Jan 2026: Submission deadline
Apr 2026: Notification
Jul 2026: Conference

Option B: Workshop First (Faster Feedback)
──────────────────────────────────────────
Submit to workshop at EMNLP/ACL 2025
- Shorter paper (4-6 pages)
- Faster turnaround
- Get feedback before full submission
- Examples: KnowledgeNLP, AKBC workshop

Option C: Journal Track
───────────────────────
Submit to IRJ or TACL
- No deadline pressure
- More space for details
- Longer review cycle (3-6 months)
```

### 10.2 Backup Plans

```
If rejected from top venue:
1. Address reviewer feedback
2. Submit to next tier (CIKM, ECIR, COLING)
3. Consider journal submission with extended results

If results are negative/mixed:
1. Reframe as "understanding when graph helps"
2. Focus on efficiency contribution
3. Publish as short paper / negative results track
```

### 10.3 Supplementary Materials

```
Prepare for submission:
□ Anonymized code repository
□ Dataset documentation
□ Evaluation scripts
□ Pre-trained models / checkpoints
□ Supplementary appendix with additional results
```

---

## 11. Resource Requirements

### 11.1 Computational Resources

| Resource | Specification | Purpose |
|----------|---------------|---------|
| **Development Machine** | 32GB RAM, 8 cores | Development, small experiments |
| **Evaluation Server** | 64GB RAM, 16 cores, GPU | Large-scale experiments |
| **GPU** | NVIDIA A100 or equivalent | Embedding generation |
| **Storage** | 500GB SSD | Datasets, embeddings, results |

### 11.2 Human Resources

| Role | Effort | Tasks |
|------|--------|-------|
| **Lead Researcher** | 50% FTE, 6 months | Design, implementation, analysis, writing |
| **Research Assistant** | 25% FTE, 3 months | Data preparation, annotation coordination |
| **Domain Expert** | 10 hours total | Curation study, query creation |
| **Annotators** | 100-150 hours total | Relevance judgments |

### 11.3 Budget Estimate

| Item | Cost | Notes |
|------|------|-------|
| **Cloud Compute** | $500-1000 | GPU hours for embeddings |
| **Annotation** | $1500-2500 | Crowdsourcing platform |
| **API Costs** | $200-500 | OpenAI embeddings |
| **Publication Fee** | $0-500 | Open access if required |
| **Total** | $2200-4500 | |

---

## 12. Timeline

### 12.1 Gantt Chart Overview

```
                    Month 1    Month 2    Month 3    Month 4    Month 5    Month 6
                    ────────   ────────   ────────   ────────   ────────   ────────
Implementation      ████████   ████████
Baseline Eval                  ████████   ████
Graph System Eval                         ████████   ████
Curation Study                                       ████████   
User Study (opt)                                     ████████   ████
Analysis                                                        ████████   ████
Writing                                                         ████████   ████████
Revision                                                                   ████████
```

### 12.2 Detailed Milestones

| Week | Milestone | Deliverable |
|------|-----------|-------------|
| 1-2 | Dataset preparation | Processed datasets, query sets |
| 3-4 | Baseline implementation | Working BM25, hybrid baselines |
| 5-6 | Graph system deployment | E1 condition ready |
| 7-8 | Baseline experiments | Baseline results table |
| 9-10 | Graph experiments | Graph enhancement results |
| 11-12 | Parameter sweeps | Optimal parameters identified |
| 13-14 | Ablation studies | Component contribution analysis |
| 15-16 | Curation study | Curation impact data |
| 17-18 | User study (if doing) | User study results |
| 19-20 | Statistical analysis | Complete analysis |
| 21-22 | Paper drafting | Full draft |
| 23-24 | Revision and polish | Submission-ready paper |

---

## 13. Risk Assessment

### 13.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Graph doesn't improve retrieval | Medium | High | Stratify by query type; publish as analysis paper |
| Latency overhead too high | Low | High | Focus on pre-computation; accept partial benefits |
| Concept extraction noisy | Medium | Medium | Include curation condition; compare extraction methods |
| Scalability issues | Low | Medium | Test at multiple corpus sizes; document limits |

### 13.2 Resource Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Annotation budget exceeded | Medium | Medium | Use smaller judged set + automatic metrics |
| Expert unavailable for curation | Low | Medium | Use research team members as backup |
| Compute costs exceed budget | Low | Low | Use local resources; optimize experiments |

### 13.3 Publication Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Rejection from top venue | Medium | Medium | Have backup venues; incorporate feedback |
| Similar work published first | Low | High | Monitor ArXiv; emphasize unique contributions |
| Reviewers request more experiments | High | Low | Plan for revision cycle; have backup experiments |

---

## Appendix A: Evaluation Metrics Implementation

```python
"""
Standard IR Metrics Implementation
"""

import numpy as np
from typing import List, Dict, Set


def precision_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    """Precision at k."""
    if k == 0:
        return 0.0
    retrieved_k = retrieved[:k]
    relevant_retrieved = len(set(retrieved_k) & relevant)
    return relevant_retrieved / k


def recall_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    """Recall at k."""
    if len(relevant) == 0:
        return 0.0
    retrieved_k = retrieved[:k]
    relevant_retrieved = len(set(retrieved_k) & relevant)
    return relevant_retrieved / len(relevant)


def reciprocal_rank(retrieved: List[str], relevant: Set[str]) -> float:
    """Reciprocal rank of first relevant document."""
    for i, doc in enumerate(retrieved):
        if doc in relevant:
            return 1.0 / (i + 1)
    return 0.0


def dcg_at_k(relevances: List[float], k: int) -> float:
    """Discounted Cumulative Gain at k."""
    relevances = relevances[:k]
    if not relevances:
        return 0.0
    return relevances[0] + sum(
        rel / np.log2(i + 2) for i, rel in enumerate(relevances[1:])
    )


def ndcg_at_k(
    retrieved: List[str], 
    relevance_scores: Dict[str, float], 
    k: int
) -> float:
    """Normalized DCG at k."""
    # Get relevances for retrieved docs
    retrieved_relevances = [
        relevance_scores.get(doc, 0.0) for doc in retrieved[:k]
    ]
    
    # Ideal ranking
    ideal_relevances = sorted(relevance_scores.values(), reverse=True)[:k]
    
    dcg = dcg_at_k(retrieved_relevances, k)
    idcg = dcg_at_k(ideal_relevances, k)
    
    if idcg == 0:
        return 0.0
    return dcg / idcg


def mean_average_precision(
    queries_results: List[tuple]  # [(retrieved, relevant), ...]
) -> float:
    """Mean Average Precision across queries."""
    aps = []
    for retrieved, relevant in queries_results:
        if not relevant:
            continue
        
        precision_sum = 0.0
        relevant_count = 0
        
        for i, doc in enumerate(retrieved):
            if doc in relevant:
                relevant_count += 1
                precision_sum += relevant_count / (i + 1)
        
        if relevant_count > 0:
            aps.append(precision_sum / len(relevant))
        else:
            aps.append(0.0)
    
    return np.mean(aps) if aps else 0.0
```

---

## Appendix B: Query Type Classification

```python
"""
Heuristic Query Type Classification
"""

import re
from typing import List


class QueryClassifier:
    """Classify queries by type for stratified analysis."""
    
    def __init__(self):
        # Patterns for different query types
        self.comparison_patterns = [
            r'\bvs\.?\b', r'\bversus\b', r'\bcompare\b', r'\bdifference\b',
            r'\bbetter\b', r'\bworse\b'
        ]
        self.implicit_patterns = [
            r'\btechniques?\b', r'\bmethods?\b', r'\bapproaches?\b',
            r'\bways?\b', r'\bstrategies?\b'
        ]
    
    def classify(self, query: str) -> str:
        """
        Classify query into types:
        - single_concept: One clear topic
        - multi_concept: Multiple explicit topics
        - implicit: Implicit relationships
        - comparative: Comparison queries
        """
        query_lower = query.lower()
        
        # Check for comparison
        for pattern in self.comparison_patterns:
            if re.search(pattern, query_lower):
                return 'comparative'
        
        # Check for implicit
        for pattern in self.implicit_patterns:
            if re.search(pattern, query_lower):
                return 'implicit'
        
        # Count potential concepts (simplified heuristic)
        # In practice, use NLP to extract noun phrases
        words = query_lower.split()
        content_words = [w for w in words if len(w) > 3 and w.isalpha()]
        
        if len(content_words) <= 2:
            return 'single_concept'
        else:
            return 'multi_concept'
    
    def classify_batch(self, queries: List[str]) -> dict:
        """Classify a batch of queries and return distribution."""
        classifications = [self.classify(q) for q in queries]
        
        distribution = {}
        for c in classifications:
            distribution[c] = distribution.get(c, 0) + 1
        
        return {
            'classifications': classifications,
            'distribution': distribution
        }
```

---

**Document Version:** 0.1.0  
**Status:** Research Planning  
**Last Updated:** December 22, 2025

