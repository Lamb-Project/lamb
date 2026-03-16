# Extended Evaluation Frameworks Analysis — Additional Tools, KG Evaluation & Educational AI

> **Date:** 2026-03-15
> **Companion to:** `llm_evaluation_frameworks_analysis.md` (core 6-framework analysis)
> **Purpose:** Evaluate additional frameworks missed in the initial analysis, KG-specific evaluation tools, and educational AI evaluation methodologies relevant to LAMB.

---

## Table of Contents

1. [Additional General-Purpose Frameworks](#1-additional-general-purpose-frameworks)
   - 1.1 Frameworks Recommended for LAMB (Tier 1)
   - 1.2 Frameworks Worth Noting (Tier 2)
   - 1.3 Frameworks Not Recommended
2. [Knowledge Graph Evaluation Tools](#2-knowledge-graph-evaluation-tools)
3. [Educational AI Evaluation](#3-educational-ai-evaluation)
4. [Extended Comparison Tables](#4-extended-comparison-tables)
5. [Updated Ranking — All Frameworks Combined](#5-updated-ranking--all-frameworks-combined)
6. [Extended Implementation Recommendations](#6-extended-implementation-recommendations)

---

## 1. Additional General-Purpose Frameworks

### 1.1 Frameworks Recommended for LAMB (Tier 1)

---

#### LangWatch

- **Install:** `pip install langwatch` or Docker Compose (self-hosted)
- **GitHub Stars:** ~3.1k
- **License:** MIT (fully self-hostable, no feature gates)
- **Pricing:** Self-hosted: free. Cloud: from ~59 EUR/month
- **Evaluator count:** 38 built-in evaluators

**All metrics:**
- *Expected Answer:* Exact Match, LLM Answer Match, BLEU Score, LLM Factual Match, ROUGE Score, SQL Query Equivalence
- *LLM-as-Judge:* Boolean Evaluator, Category Evaluator, Score Evaluator, Rubrics-Based Scoring
- *RAG Quality (13):* RAGAS Context Precision, RAGAS Context Recall, RAGAS Faithfulness, Context F1, Context Precision, Context Recall, RAGAS Response Context Precision, RAGAS Response Context Recall, RAGAS Response Relevancy, RAGAS Answer Correctness, RAGAS Answer Relevancy, RAGAS Context Relevancy, RAGAS Context Utilization
- *Quality:* Valid Format Evaluator (JSON, markdown, Python, SQL), Lingua Language Detection, Summarization Score, Semantic Similarity
- *Safety:* Azure Content Safety, Azure Jailbreak Detection, Azure Prompt Shield, OpenAI Moderation, Presidio PII Detection
- *Other:* Custom Basic Evaluator (regex/match), Competitor Blocklist/Allowlist/LLM Check, Off-Topic Evaluator, Query Resolution

**RAG-specific:** 13 dedicated RAG evaluators — the most comprehensive RAG evaluator set of any framework analyzed, including both native and RAGAS-integrated metrics.

**Multi-turn:** Agent simulation running thousands of synthetic conversations. Query Resolution evaluator for conversation completion assessment.

**Knowledge Graph:** No native support.

**Custom metrics:** LLM boolean checks, scores, regex, custom functions. Server-side and client-side evaluation.

**Key differentiator for LAMB:** MIT license + full self-hosting aligns perfectly with LAMB's privacy-first design. 13 RAG evaluators exceed even DeepEval's RAG coverage. OpenTelemetry-native tracing. DSPy optimization support. Can be added to LAMB's Docker Compose stack.

---

#### Evidently AI

- **Install:** `pip install evidently`
- **GitHub Stars:** ~7.3k (largest community in extended analysis)
- **License:** Apache 2.0
- **Pricing:** Developer (free, 10k rows/month), Pro ($50/month), Enterprise (custom)
- **Metric count:** 100+ built-in metrics
- **Downloads:** 25M+ (highest adoption of any tool analyzed)

**All metrics:**
- *Text/LLM:* Sentiment, Toxicity, Language Detection, Text Length, Readability, Sentence/Word Count, OOV Percentage, Semantic Similarity (cosine), PII Detection
- *RAG Retrieval:* NDCG, MAP, MRR, Hit Rate, Retrieval Relevance
- *RAG Generation:* Context-Response Grounding (faithfulness)
- *LLM-as-Judge:* Custom prompt-based evaluation via any LLM, professional tone verification
- *Rule-Based:* IncludesWords, BeginsWith, Contains, regex patterns, competitor mention detection, canned response detection
- *Data Quality:* Missing values, duplicates, correlations, range validation
- *Drift Detection (20+):* PSI, KL divergence, Wasserstein, Jensen-Shannon, etc.
- *Classification:* Accuracy, Precision, Recall, F1, ROC AUC, bias detection
- *Regression:* MAE, RMSE, error distribution

**RAG-specific:** Good. NDCG, MAP, MRR, Hit Rate for retrieval (traditional IR metrics that most frameworks lack). Context-Response Grounding for faithfulness.

**Multi-turn:** Not explicitly supported with dedicated metrics. Drift detection can track conversation quality degradation over time.

**Knowledge Graph:** No native support.

**Custom metrics:** Python functions, LLM judge templates, HuggingFace model integration. Extensible descriptor system.

**Key differentiator for LAMB:** The only framework bridging traditional ML monitoring and LLM evaluation. 100+ metrics spanning data drift, ML models, AND LLM outputs. "Run locally, upload summaries" approach is ideal for privacy-sensitive educational data. Visual HTML Reports and Test Suites with pass/fail conditions. Best for detecting quality degradation over time.

---

#### Galileo

- **Install:** SDK available via pip
- **GitHub Stars:** N/A (proprietary platform); open-sourced Agent Control (Apache 2.0)
- **License:** Proprietary (platform); Apache 2.0 (Agent Control)
- **Pricing:** Free tier (5k traces/month), enterprise tiers (contact)

**All metrics:**
- *RAG (chunk-level):* Chunk Attribution (binary), Chunk Utilization (0-1), Chunk Relevance (0-1)
- *Response Quality:* Context Adherence, Completeness, Correctness, Ground Truth Adherence
- *Safety:* Toxicity, Sexism, PII Detection, Prompt Injection, Tone
- *Model Quality:* Instruction Adherence, Prompt Perplexity, Uncertainty (token-level)
- *Agent:* Tool Selection Quality, Tool Error, Action Advancement, Action Completion
- *NLP:* BLEU, ROUGE

**RAG-specific:** Luna evaluation models (fine-tuned DeBERTa-large 440M) provide token-level probability predictions for Adherence, Relevance, and Utilization at 97% cost reduction vs GPT-3.5. Evaluates at the chunk level, not just response level.

**Multi-turn:** State management observability for multi-turn context tracking.

**Knowledge Graph:** **YES — the ONLY framework with KG validation support.** Knowledge Bases feature converts organizational SOPs/policies into custom evaluation metrics. Knowledge graph validation offers structured verification against established relationships.

**Custom metrics:** Custom metrics from knowledge bases and policies. Configurable guardrail thresholds.

**Key differentiator for LAMB:** Only framework with native KG validation. Luna purpose-built evaluation models (not LLM-as-judge — faster, cheaper, deterministic). Token-level probability scoring. Chunk-level RAG evaluation provides more granular diagnostics than response-level metrics.

---

#### Haystack Evaluation Module

- **Install:** `pip install haystack-ai`
- **GitHub Stars:** ~24k (part of Haystack framework)
- **License:** Apache 2.0
- **Pricing:** Free/open-source; Haystack Enterprise available

**All metrics:**
- *Model-Based:* FaithfulnessEvaluator, ContextRelevanceEvaluator, LLMEvaluator (custom criteria)
- *Statistical:* SASEvaluator (Semantic Answer Similarity, multilingual), AnswerExactMatchEvaluator
- *IR Metrics:* DocumentMRREvaluator, DocumentMAPEvaluator, DocumentRecallEvaluator, DocumentNDCGEvaluator
- *Via integrations:* RagasEvaluator (all RAGAS metrics), DeepEvalEvaluator (all DeepEval metrics)

**RAG-specific:** Pipeline-native — evaluators are pipeline components composed alongside production pipelines. Strongest IR metrics suite (MRR, MAP, NDCG, Recall).

**Multi-turn:** Not explicitly dedicated metrics, but framework supports conversational pipelines.

**Knowledge Graph:** No native KG evaluation, but Haystack has KG index capabilities.

**Custom metrics:** LLMEvaluator accepts custom instructions, examples, and output schemas.

**Key differentiator for LAMB:** Pipeline-native evaluators (evaluate exactly how you produce). Best statistical IR metrics (MRR, MAP, NDCG — missing from most competitors). Multilingual Semantic Answer Similarity via cross-encoder (relevant for LAMB's en/es/ca/eu locale support). First-class DeepEval and RAGAS integration as pipeline components.

---

### 1.2 Frameworks Worth Noting (Tier 2)

#### TruLens (by Snowflake/Truera)

- **Install:** `pip install trulens`
- **GitHub Stars:** ~2k | **License:** MIT
- **Core metrics:** RAG Triad (Groundedness, Answer Relevance, Context Relevance) + Coherence, Comprehensiveness, Sentiment, Harmfulness, Stereotypes, Language Match, Toxicity, Moderation, Logical Consistency, Ground Truth Agreement
- **Unique:** Agent's GPA framework (Goal/Plan/Action) for agentic evaluation; native OpenTelemetry compatibility; Snowflake Cortex integration
- **Verdict:** Solid RAG evaluation but smaller metric set than DeepEval/RAGAS. Agent's GPA is unique. Best if already in the Snowflake ecosystem.

#### Continuous Eval (by Relari AI)

- **Install:** `pip install continuous-eval`
- **GitHub Stars:** ~490 | **License:** Apache 2.0
- **Core metrics:** Deterministic Faithfulness (token-level), Context Precision/Recall, Answer Correctness (ROUGE-L, Token Overlap, BLEU), LLM-based Faithfulness/Correctness, Attribution, Code Generation metrics
- **Unique:** Three-tier metric system (deterministic / semantic / probabilistic). Modular per-component evaluation. Synthetic golden dataset generation via Relari Cloud.
- **Verdict:** Interesting modular approach but small community. The deterministic Faithfulness metric (token-level, no LLM needed) is unique and valuable for CI/CD.

#### Braintrust (autoevals)

- **Install:** `pip install autoevals` (OSS library, usable standalone)
- **GitHub Stars:** ~834 (autoevals) | **License:** MIT-style
- **Core metrics:** Battle, Closed QA, Humor, Factuality, Moderation, Security, Summarization, SQL, Translation, RAG metrics (Context Precision/Recall/Faithfulness/Relevancy), BLEU, Levenshtein, Exact Match, Semantic Similarity, JSON Validity
- **Unique:** Most mature managed platform with richest scorer library. `autoevals` OSS lib is usable without the platform.
- **Verdict:** The `autoevals` library alone is a handy addition. Platform is commercial ($249/month Pro). Good complementary scorer library.

#### Athina AI

- **Install:** `pip install athina`
- **GitHub Stars:** ~298 | **License:** Permissive
- **Core metrics:** 50+ preset evaluators — Hallucination, Context Sufficiency, Answer Completeness, Faithfulness, Groundedness, Prompt Injection, PII Detection, OpenAI Moderation, Summarization Accuracy, Conversation Evals, Custom Code/LLM evals, RAGAS integration
- **Unique:** Dedicated "Conversation Evals" category. RAGAS integration built-in. Generous free tier.
- **Verdict:** Good breadth but small community. Conversation evaluation support is a plus.

#### W&B Weave

- **Install:** `pip install weave`
- **GitHub Stars:** ~1.1k | **License:** Apache 2.0
- **Core metrics:** Local scorers (no API calls) — HallucinationScorer (HHEM 2.1), ContextRelevanceScorer (fine-tuned DeBERTa), TrustScorer (composite), SummarizationScorer. Custom scorers via `weave.flow.scorer.Scorer` class.
- **Unique:** Local on-device scorers using small fine-tuned models (zero API cost). Composite trust scoring.
- **Verdict:** Local scorers are compelling for privacy-first LAMB. Requires W&B ecosystem buy-in.

#### Parea AI

- **Install:** `pip install parea-ai`
- **GitHub Stars:** ~82 | **License:** Apache 2.0
- **Core metrics:** Context Relevance, Context Ranking (MAP, listwise), Binary Faithfulness, Token Overlap Faithfulness, Statement Inference Faithfulness, Answer Relevancy, LLM-as-Judge, Uncertainty Assessment, Cross-Examination Hallucination, Goal Success Ratio, Summarization (Factual Consistency, Likert), Levenshtein
- **Unique:** Goal Success Ratio for chatbot evaluation (measures if students achieve learning goals). Cross-Examination hallucination detection.
- **Verdict:** Goal Success Ratio is very relevant for educational assessment. Small community limits reliability.

### 1.3 Frameworks Not Recommended

| Framework | Reason |
|---|---|
| **Humanloop** | Acquired by Anthropic Aug 2025, platform shut down Sep 2025. No longer exists. |
| **Quotient AI** | Acquired by Databricks March 2026. Future as standalone tool uncertain. |
| **Baserun** | Immature — 16 GitHub stars, minimal built-in metrics, tiny community. |
| **Tonic Validate** | UI sunset August 2025. Very narrow scope (RAG only, ~6 metrics). Small community. |
| **UpTrain** | Decent metrics (20+) but community stalled at ~2.3k stars. Root cause analysis is unique but not enough to displace DeepEval/RAGAS. |
| **LlamaIndex Evaluation** | Tightly coupled to LlamaIndex framework. LAMB doesn't use LlamaIndex, so integration overhead is unjustified. Metrics available via DeepEval/RAGAS anyway. |
| **LangChain/OpenEvals** | Same coupling issue — OpenEvals is small (1k stars) and best used within LangChain/LangSmith. LAMB doesn't use LangChain. |
| **Arize Phoenix** | Good observability but Elastic License 2.0 (not OSI-approved) is a concern. Fewer evaluation metrics (6) than Langfuse/Opik. Already covered by Langfuse in our stack. |
| **Patronus AI** | Strong hallucination model but commercial SaaS only. No self-hosting. Privacy concern for educational data. |
| **Maxim AI** | Commercial SaaS. No self-hosting. Similar coverage to Langfuse/Opik. |

---

## 2. Knowledge Graph Evaluation Tools

### 2.1 The KG Evaluation Gap

The initial analysis identified that **all 6 core frameworks** have zero native KG evaluation support. Extended research confirms this gap persists across nearly the entire LLM evaluation ecosystem, with one exception (Galileo).

However, specialized KG tools exist outside the LLM evaluation ecosystem:

### 2.2 KG Embedding Evaluation — PyKEEN (Recommended)

- **Install:** `pip install pykeen`
- **License:** MIT
- **What:** Most comprehensive Python library for training and evaluating KG embedding models
- **Metrics (44):** Hits@1, Hits@3, Hits@5, Hits@10, MRR (Mean Reciprocal Rank), MR (Mean Rank), Adjusted MR, Inverse Harmonic MR, plus classification metrics (Accuracy, F1, Precision, Recall, AUC-ROC), and rank-based evaluators
- **Models:** TransE, RotatE, ComplEx, DistMult, and 30+ others
- **Relevance to LAMB:** If LAMB implements KG embeddings for entity/relation lookup, PyKEEN can evaluate embedding quality. Works as a standalone evaluation layer complementing the LLM evaluation stack.

### 2.3 GraphRAG Benchmarking — GraphRAG-Bench & BenchmarkQED

**GraphRAG-Bench** (ICLR 2026)
- First comprehensive benchmark specifically for evaluating GraphRAG models
- Evaluates: end-to-end output, retrieval correctness, meta-level graph properties, logical coherence of reasoning
- 4 task types: fact retrieval, complex reasoning, contextual summarization, creative generation
- 16 disciplines, 20 core textbooks, tested on 9 GraphRAG methods
- **Repo:** [github.com/GraphRAG-Bench/GraphRAG-Benchmark](https://github.com/GraphRAG-Bench/GraphRAG-Benchmark)

**BenchmarkQED** (by Microsoft Research)
- Companion to Microsoft's GraphRAG library
- **AutoQ:** Automated query generation (local-to-global spectrum)
- **AutoE:** LLM-as-Judge evaluation — pairwise comparison on Comprehensiveness, Diversity, Empowerment, Relevance
- **AutoD:** Automated dataset preparation
- **Repo:** [github.com/microsoft/benchmark-qed](https://github.com/microsoft/benchmark-qed)

### 2.4 KG Extraction Quality — KGGen + MINE Benchmark

- **Install:** `pip install kg-gen`
- **What:** LLM-powered KG extraction from text + first standardized benchmark for evaluating KG extractors
- **MINE-1:** Measures knowledge retention (how much original text the KG captures)
- **MINE-2:** Evaluates RAG effectiveness (how well the KG improves retrieval/reasoning)
- **Outperforms:** OpenIE and GraphRAG by 18% in KG accuracy
- **Repo:** [github.com/stair-lab/kg-gen](https://github.com/stair-lab/kg-gen)
- **Relevance to LAMB:** Directly evaluates KG extraction quality when building knowledge graphs from educational documents.

### 2.5 KG-Based Hallucination Detection — GraphEval (Amazon)

- **What:** Converts LLM output to a KG, evaluates each triple against context using NLI models, identifies specific hallucinated triples
- **Includes:** GraphCorrect for KG-guided hallucination correction
- **Paper:** [arxiv.org/abs/2407.10793](https://arxiv.org/abs/2407.10793)
- **Relevance to LAMB:** Could be adapted to verify KG-grounded responses by checking individual triples rather than treating the response as a text blob.

### 2.6 Summary: KG Evaluation Strategy for LAMB

| KG Evaluation Need | Tool | How |
|---|---|---|
| **KG embedding quality** | PyKEEN | `pip install pykeen`. Train embeddings, evaluate with Hits@k, MRR. Standalone pipeline. |
| **GraphRAG end-to-end** | GraphRAG-Bench | Run benchmark tasks against LAMB's KG-RAG pipeline. Compare against baseline methods. |
| **KG extraction quality** | KGGen MINE | `pip install kg-gen`. Evaluate how much source knowledge the KG captures (MINE-1) and how well it supports retrieval (MINE-2). |
| **KG-based hallucination** | GraphEval methodology | Adapt Amazon's approach: convert response to triples, verify each against context via NLI. Build as custom DeepEval metric. |
| **KG validation against domain** | Galileo | Use Knowledge Bases feature to define educational domain rules, validate KG against them. |
| **Entity/relation P/R/F1** | Custom (DeepEval/RAGAS) | As specified in core analysis — deterministic metrics via `BaseMetric` or `@numeric_metric`. |

---

## 3. Educational AI Evaluation

### 3.1 Educational Evaluation Dimensions

Research across multiple frameworks converges on these pedagogical evaluation dimensions, ordered by relevance to LAMB:

| # | Dimension | Description | How to Evaluate in LAMB |
|---|-----------|-------------|------------------------|
| 1 | **Faithfulness to source content** | Does the RAG-enhanced response stay accurate to the course material? | DeepEval `FaithfulnessMetric` / RAGAS `Faithfulness` on educational content |
| 2 | **Scaffolding quality** | Does the assistant break down problems progressively rather than giving direct answers? | Custom G-Eval with scaffolding criteria or RAGAS `RubricsScore` with pedagogical rubric |
| 3 | **Answer avoidance** | Does the tutor avoid giving away answers, instead guiding the student? | Custom DeepEval G-Eval: "Does the response guide the student without revealing the answer?" |
| 4 | **Mistake identification** | Can the assistant recognize errors in student work? | Custom evaluation dataset with student mistakes; measure detection accuracy |
| 5 | **Adaptive feedback** | Does the response adjust to the learner's demonstrated level? | Custom G-Eval with criteria assessing response appropriateness to student level |
| 6 | **Bloom's cognitive level** | Does the response target the appropriate cognitive depth? | Custom RAGAS `RubricsScore` with Bloom's taxonomy levels as rubric |
| 7 | **Actionability** | Are suggestions clear and actionable for the student? | Custom G-Eval: "Are the suggestions specific enough for the student to act on?" |
| 8 | **Coherence & tone** | Is the dialogue natural, encouraging, and age-appropriate? | Opik `Tone` + `Readability` heuristics + custom G-Eval for encouragement |

### 3.2 Key Educational Benchmarks & Datasets

| Benchmark | Focus | Size | Relevance to LAMB |
|---|---|---|---|
| **MathTutorBench** (EMNLP 2025) | 7 teaching tasks, trained reward model | 3 skills, 7 tasks | High — includes a reward model that could score LAMB math responses |
| **TutorBench** (Oct 2025) | Adaptive explanations, feedback, hints | 1,490 samples | High — AP/high-school level, directly applicable |
| **EduBench** | 9 educational scenarios, bilingual | 4,000+ contexts, 12 metrics | Medium — comprehensive but focuses on Chinese+English |
| **KMP-Bench** (Mar 2026) | K-8 math pedagogy, 6 core principles | Dialogue + Skills modules | Medium — younger audience but pedagogical principles transfer |
| **Khan Academy CoMTA** | Tutoring accuracy in math | 188 conversations | High — real tutoring conversations with accuracy assessment |
| **EducationQ** | Multi-agent teaching evaluation | 1,498 questions, 13 disciplines | High — evaluates teaching capability across disciplines |

### 3.3 Reusable Educational Evaluation Taxonomies

**Unifying AI Tutor Evaluation (NAACL 2025, SAC Award)**
- 8 dimensions: Mistake Identification, Mistake Location, Answer Revelation, Guidance, Actionability, Coherence, Tone, Human-likeness
- Benchmark: MRBench — 192 conversations, 1,596 responses
- **Open source:** [github.com/kaushal0494/UnifyingAITutorEvaluation](https://github.com/kaushal0494/UnifyingAITutorEvaluation)
- **How to use in LAMB:** Adapt the 8-dimension rubric as a RAGAS `RubricsScore` or DeepEval G-Eval criteria set. Use MRBench conversations as a reference evaluation dataset.

**AITutor-EvalKit (MIT License)**
- Two-phase Turing-like evaluation
- 4 dimensions: Mistake Identification, Mistake Location, Providing Guidance, Actionability
- Automated scoring: 0.72 accuracy, 0.60 macro-F1
- **Open source:** [github.com/kaushal0494/AITutor-EvalKit](https://github.com/kaushal0494/AITutor-EvalKit)
- **How to use in LAMB:** Run AITutor-EvalKit directly on LAMB assistant outputs. Complements the LLM evaluation stack with education-specific automated scoring.

---

## 4. Extended Comparison Tables

### 4.1 Tier 1 New Frameworks vs. Core 6

| Capability | LangWatch | Evidently AI | Galileo | Haystack Eval |
|---|---|---|---|---|
| **License** | MIT | Apache 2.0 | Proprietary (+ OSS Agent Control) | Apache 2.0 |
| **Self-hostable** | Yes (Docker) | Yes | No (cloud only) | Yes |
| **RAG metrics** | 13 (most of any framework) | NDCG, MAP, MRR, Hit Rate, Grounding | Chunk-level: Attribution, Utilization, Relevance | MRR, MAP, NDCG, Recall, Faithfulness, Relevance |
| **Multi-turn** | Agent simulation | Drift detection (indirect) | State tracking | Not dedicated |
| **KG evaluation** | No | No | **Yes** (Knowledge Bases validation) | No |
| **Traditional NLP** | BLEU, ROUGE | Sentiment, Readability, Language | BLEU, ROUGE | SAS (multilingual), Exact Match |
| **Safety** | Azure Safety, PII (Presidio), Prompt Shield | Toxicity, PII, Bias | Toxicity, Sexism, PII, Prompt Injection | Via LLMEvaluator (custom) |
| **IR metrics** | Via RAGAS integration | **NDCG, MAP, MRR, Hit Rate** (native) | No | **MRR, MAP, NDCG, Recall** (native) |
| **Custom metrics** | LLM checks, regex, functions | Python functions, LLM templates, HF models | Knowledge base rules | LLMEvaluator with custom instructions |
| **Tracing** | OpenTelemetry-native | No (monitoring dashboards) | Yes | Pipeline-native |
| **Privacy fit** | Excellent (self-hosted MIT) | Excellent (run locally) | Poor (cloud only) | Excellent (self-hosted) |

### 4.2 KG Evaluation Tools Comparison

| Tool | Type | Metrics | Python | Relevance to LAMB |
|---|---|---|---|---|
| **PyKEEN** | KG Embedding Eval | 44 metrics (Hits@k, MRR, MR, classification) | `pip install pykeen` | High — evaluates KG embedding quality |
| **GraphRAG-Bench** | GraphRAG Benchmark | End-to-end, retrieval, reasoning, generation | GitHub | High — benchmarks GraphRAG pipeline |
| **BenchmarkQED** | GraphRAG Eval | Comprehensiveness, Diversity, Empowerment, Relevance | GitHub | Medium — Microsoft GraphRAG companion |
| **KGGen MINE** | KG Extraction Eval | MINE-1 (retention), MINE-2 (RAG effectiveness) | `pip install kg-gen` | High — evaluates KG extraction quality |
| **GraphEval** | KG Hallucination | Triple-level hallucination detection | Paper/code | Medium — methodology adaptable to custom metric |
| **Galileo** | KG Validation | Knowledge Base rules, structured verification | SDK | High — only platform with native KG validation |

---

## 5. Updated Ranking — All Frameworks Combined

Incorporating the new findings, here is the updated ranking for LAMB's use case:

### Tier 1 — Core Stack (Use These)

| # | Framework | Role in LAMB Stack | Why |
|---|---|---|---|
| 1 | **DeepEval** | Primary CI/CD evaluation | 50+ metrics, pytest-native, best multi-turn RAG, G-Eval/DAG for custom KG metrics, `@observe` tracing |
| 2 | **RAGAS** | RAG-specific deep analysis | Deepest RAG metric variants, noise sensitivity, context entities recall, traditional NLP, educational rubrics via `RubricsScore` |
| 3 | **Langfuse** or **LangWatch** | Observability & tracing | Both MIT/self-hostable. LangWatch has more built-in evaluators (38 vs Langfuse's growing catalog). Langfuse has stronger human annotation and production monitoring. **Choose based on priority: evaluator breadth → LangWatch; annotation workflows → Langfuse** |
| 4 | **Opik** | Conversation quality & heuristics | Best multi-turn metrics (coherence, completeness, frustration, degeneration), 22+ heuristic metrics, 5 bias judges |
| 5 | **Giskard** | Red-teaming & safety | 40+ adversarial probes, prompt injection testing (12 variants), sycophancy detection, RAGET component diagnosis |

### Tier 2 — Specialized Additions

| # | Framework | Role | Why |
|---|---|---|---|
| 6 | **Vectara Open RAG Eval** | Reference-free RAG comparison | UMBRELA + AutoNuggetizer for A/B testing RAG strategies without golden answers |
| 7 | **Haystack Evaluation** | IR metrics | Best native MRR, MAP, NDCG, Recall. Pipeline-native. Multilingual SAS for LAMB's 4 locales |
| 8 | **Evidently AI** | Quality monitoring & drift | 100+ metrics, visual dashboards, drift detection for tracking quality degradation over time. Privacy-friendly. |
| 9 | **Galileo** | KG validation (when KG is implemented) | Only platform with native KG validation. Luna models for cheap eval. **Caveat:** cloud-only, privacy concern for student data |

### Tier 3 — KG-Specific Tools (When KG Features Are Built)

| # | Tool | Role |
|---|---|---|
| 10 | **PyKEEN** | KG embedding quality evaluation (44 metrics) |
| 11 | **KGGen MINE** | KG extraction quality evaluation |
| 12 | **GraphRAG-Bench** | End-to-end GraphRAG benchmarking |

### Tier 4 — Educational Evaluation (For Pedagogical Quality)

| # | Tool | Role |
|---|---|---|
| 13 | **AITutor-EvalKit** | Automated pedagogical quality scoring (4 dimensions) |
| 14 | **MathTutorBench reward model** | Pre-trained scoring model for tutoring response quality |
| 15 | **Unifying AI Tutor taxonomy** | Rubric template for educational G-Eval/RubricsScore criteria |

---

## 6. Extended Implementation Recommendations

### 6.1 LangWatch Integration

```python
# Install: pip install langwatch
# Self-host: docker compose up (add to LAMB's docker-compose.yaml)

import langwatch

langwatch.api_key = "your-key"  # or self-hosted URL

# Trace LAMB completions
@langwatch.trace()
def lamb_completion(query: str, assistant_id: str):
    # LAMB's completion pipeline
    response = call_lamb_api(query, assistant_id)

    # Evaluate with built-in RAG evaluators
    langwatch.get_current_trace().evaluate(
        "ragas_faithfulness",
        input=query,
        output=response["content"],
        contexts=response["retrieved_contexts"]
    )
    return response
```

**Setup effort:** Low. Add `langwatch` service to Docker Compose. Decorate completion functions. 13 RAG evaluators available immediately.

### 6.2 Evidently AI for Quality Monitoring

```python
# Install: pip install evidently
from evidently.metrics import TextEvals
from evidently.descriptors import SemanticSimilarity, Sentiment, TextLength
from evidently.report import Report

# Build a monitoring report
report = Report(metrics=[
    TextEvals(column_name="response", descriptors=[
        SemanticSimilarity(with_column="reference"),
        Sentiment(),
        TextLength(),
    ]),
])

# Run on batch of LAMB responses
report.run(reference_data=baseline_df, current_data=current_df)
report.save_html("lamb_quality_report.html")
```

**Setup effort:** Low. Pure Python. No infrastructure. Run locally, view HTML reports. Add drift detection to catch quality degradation after model/prompt changes.

### 6.3 Galileo for KG Validation (Future)

```python
# When LAMB implements Knowledge Graphs:
# 1. Define educational domain rules in Galileo Knowledge Base
# 2. Validate KG-grounded responses against domain rules

# Galileo SDK
import galileo

galileo.init(project="lamb-kg-eval")

# Register educational knowledge base
kb = galileo.KnowledgeBase.from_documents([
    "Course: Biology 101 - Photosynthesis unit",
    "Key concepts: chlorophyll, light reactions, Calvin cycle...",
])

# Evaluate KG-grounded response
result = galileo.evaluate(
    input="What is photosynthesis?",
    output=lamb_kg_response,
    knowledge_base=kb,
    metrics=["context_adherence", "completeness", "correctness"]
)
```

**Setup effort:** Medium. Requires Galileo account (free tier). Cloud-only (not self-hostable — **significant privacy concern** for student data sent to external cloud). Consider using only for non-sensitive evaluation datasets, or negotiate data processing agreement for educational data compliance. API shown above is illustrative — consult Galileo SDK docs for exact interface.

### 6.4 Haystack IR Metrics for Retrieval Quality

```python
# Install: pip install haystack-ai
from haystack.components.evaluators import (
    DocumentMRREvaluator, DocumentMAPEvaluator,
    DocumentNDCGEvaluator, DocumentRecallEvaluator,
    SASEvaluator,
)

# Evaluate LAMB's retriever independently
mrr = DocumentMRREvaluator()
map_eval = DocumentMAPEvaluator()
ndcg = DocumentNDCGEvaluator()
recall = DocumentRecallEvaluator(mode="single_hit")

# Run on test dataset
mrr_result = mrr.run(
    ground_truth_documents=gold_docs,     # list of list of Document
    retrieved_documents=retrieved_docs,    # list of list of Document
)
# mrr_result["individual_scores"] -> per-query MRR
# mrr_result["score"] -> average MRR
```

**Setup effort:** Low. Pure Python evaluators. No infrastructure. Use to evaluate LAMB's retriever (ChromaDB queries) independently from generation.

### 6.5 PyKEEN for KG Embedding Evaluation (Future)

```python
# Install: pip install pykeen
from pykeen.pipeline import pipeline

# Train and evaluate KG embeddings on LAMB's educational KG
result = pipeline(
    dataset="your_lamb_kg_triples.tsv",  # or custom TriplesFactory
    model="RotatE",
    training_kwargs=dict(num_epochs=100),
    evaluation_kwargs=dict(batch_size=256),
)

# Access evaluation metrics
print(result.metric_results.to_df())
# -> hits_at_1, hits_at_3, hits_at_10, mean_rank,
#    mean_reciprocal_rank, adjusted_mean_rank, ...
```

**Setup effort:** Medium. Requires KG triples in standard format. Training takes compute time. Use after LAMB's KG is populated.

### 6.6 KGGen MINE for KG Extraction Evaluation (Future)

```python
# Install: pip install kg-gen
from kg_gen import KGGen

kg = KGGen(model="openai:gpt-4o-mini")

# Extract KG from educational document
result = kg.generate(
    input_data="Photosynthesis is the process by which plants convert "
               "light energy into chemical energy...",
    context="Biology 101 course material"
)

# MINE-1: How much source knowledge does the KG capture?
# MINE-2: How well does the KG support retrieval/reasoning?
# Run MINE benchmark against extracted KG
```

**Setup effort:** Low. `pip install kg-gen`. Evaluate KG extraction quality before using the KG for retrieval.

### 6.7 Educational Rubric via RAGAS RubricsScore

```python
# Adapt the Unifying AI Tutor Evaluation taxonomy
from ragas.metrics import RubricsScore
from ragas.llms import llm_factory

llm = llm_factory("gpt-4o-mini")

pedagogical_rubric = RubricsScore(
    llm=llm,
    rubrics={
        1: "Response gives away the answer directly. No scaffolding. "
           "No attempt to guide the student's thinking.",
        2: "Response provides some guidance but reveals too much. "
           "Minimal scaffolding or questioning.",
        3: "Response balances guidance with discovery. Some Socratic "
           "questioning. Partial scaffolding.",
        4: "Response effectively scaffolds learning. Uses questions to "
           "guide thinking. Identifies student misconceptions.",
        5: "Excellent pedagogical quality. Adaptive scaffolding, "
           "Socratic questioning, builds on student's existing knowledge, "
           "promotes metacognitive reflection."
    }
)

result = await pedagogical_rubric.ascore(
    user_input="Student: I think photosynthesis happens in the mitochondria",
    response="That's an interesting thought! Let me ask you this - what do "
             "you know about the role of chloroplasts in plant cells?",
)
# result.value -> 1-5 pedagogical quality score
```

**Setup effort:** Low. Define rubric once, reuse across all evaluations. Directly maps to LAMB's educational mission.

### 6.8 AITutor-EvalKit for Pedagogical Scoring

```bash
# Clone: git clone https://github.com/kaushal0494/AITutor-EvalKit
# Run automated evaluation on LAMB responses

# Evaluates 4 dimensions:
# 1. Mistake Identification (does tutor spot student errors?)
# 2. Mistake Location (does tutor identify WHERE the error is?)
# 3. Providing Guidance (does tutor guide without giving answers?)
# 4. Actionability (are suggestions specific and actionable?)
```

**Setup effort:** Medium. Requires preparing evaluation dataset in the toolkit's format. Run as a batch evaluation process. Results include spider/radar plots for visual comparison.

---

## Appendix: Decision Matrix — When to Use What

| Question | Answer |
|---|---|
| "I want to run RAG evaluation in CI/CD" | **DeepEval** (pytest-native) + **RAGAS** (metric depth) |
| "I want to trace my multi-step pipeline" | **Langfuse** or **LangWatch** (self-hosted, MIT) |
| "I want to compare two RAG strategies" | **Vectara Open RAG Eval** (reference-free A/B) |
| "I want to test prompt injection resistance" | **Giskard** (12 attack probes) + **DeepTeam** (40+ scanners) |
| "I want to evaluate multi-turn conversations" | **Opik** (coherence, completeness, frustration) + **DeepEval** (turn-level RAG) |
| "I want to monitor quality degradation over time" | **Evidently AI** (drift detection, visual reports) |
| "I want traditional IR metrics (MRR, MAP, NDCG)" | **Haystack** (pipeline-native) or **Evidently** |
| "I want to evaluate my KG embeddings" | **PyKEEN** (44 metrics) |
| "I want to evaluate KG extraction quality" | **KGGen MINE** (MINE-1/MINE-2 benchmarks) |
| "I want to benchmark my GraphRAG pipeline" | **GraphRAG-Bench** (ICLR 2026) |
| "I want to validate KG against domain rules" | **Galileo** (Knowledge Bases feature) |
| "I want to evaluate pedagogical quality" | **RAGAS `RubricsScore`** with educational rubric + **AITutor-EvalKit** |
| "I want to evaluate multilingual responses (en/es/ca/eu)" | **Haystack SASEvaluator** (multilingual cross-encoder) |
| "I want zero-API-cost local evaluation" | **W&B Weave** local scorers or **RAGAS `FaithfulnesswithHHEM`** or **Vectara HHEM** |
| "I want human-in-the-loop review" | **Langfuse** (annotation queues) |
| "I want bias detection" | **Opik** (5 dedicated bias judges) |
