# LLM & RAG Evaluation Frameworks — Complete Analysis for LAMB

> **Date:** 2026-03-17
> **Context:** LAMB (Learning Assistants Manager and Builder) — FastAPI backend, plugin-based RAG pipeline (`simple_rag`, `context_aware_rag`, `rubric_rag`, `single_file_rag`), multi-model LLM support, Docker Compose deployment, privacy-first, educational domain.
> **Future features under evaluation:** Context-Aware RAG (enhanced multi-turn) and Knowledge Graphs (KG).

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Framework Profiles — Core 6](#2-framework-profiles--core-6)
3. [Framework Profiles — Additional Recommendations](#3-framework-profiles--additional-recommendations)
4. [Frameworks Evaluated but Not Recommended](#4-frameworks-evaluated-but-not-recommended)
5. [Evaluation Coverage Matrix](#5-evaluation-coverage-matrix)
6. [Knowledge Graph Evaluation Tools](#6-knowledge-graph-evaluation-tools)
7. [Educational AI Evaluation](#7-educational-ai-evaluation)
8. [Gap Analysis](#8-gap-analysis)
9. [Final Ranking — All Frameworks Combined](#9-final-ranking--all-frameworks-combined)
10. [Recommended Evaluation Stack & Implementation Plans](#10-recommended-evaluation-stack--implementation-plans)
11. [Decision Matrix — When to Use What](#11-decision-matrix--when-to-use-what)
12. [Execution Model — Optimized Metric-to-Model Assignment](#12-execution-model--optimized-metric-to-model-assignment)

---

## 1. Executive Summary

A total of **26+ evaluation frameworks** and specialized tools were researched and analyzed for their fitness to evaluate LAMB's LLM accuracy across three scopes: current RAG features, future context-aware RAG, and future Knowledge Graph integration. This analysis also includes KG-specific evaluation tools and educational AI evaluation methodologies.

### Core Finding

No single framework covers all of LAMB's evaluation needs. The optimal approach is a **layered stack** combining multiple frameworks, each excelling at a specific evaluation dimension. Knowledge Graph evaluation has near-zero native support across the entire LLM evaluation ecosystem — only **Galileo** offers KG validation, and specialized tools like **PyKEEN** (44 KG embedding metrics) and **KGGen MINE** (KG extraction benchmarks) fill the remaining gaps.

### Top 10 Frameworks for LAMB

| # | Framework | Primary Strength | Stars | License | Privacy Fit |
|---|-----------|-----------------|-------|---------|-------------|
| 1 | **DeepEval** | Most metrics (50+), pytest-native, best multi-turn RAG | ~14.1k | Apache 2.0 | Good |
| 2 | **RAGAS** | Deepest RAG metric variants, traditional NLP, educational rubrics | ~13k | Apache 2.0 | Good |
| 3 | **Langfuse** | Best observability, tracing, human annotation, production monitoring | ~23.2k | MIT (except EE) | Excellent (self-hosted) |
| 4 | **Opik** | Best heuristic metrics (22+), conversation-specific metrics, 5 bias judges | ~18.3k | Apache 2.0 | Good |
| 5 | **Giskard** | Best red-teaming/adversarial (40+ probes), RAG component diagnosis | ~5.2k | Apache 2.0 | Good |
| 6 | **Vectara Open RAG Eval** | Best reference-free evaluation, A/B RAG comparison | New | Apache 2.0 | Good |
| 7 | **LangWatch** | 38 evaluators (13 RAG), MIT self-hostable, OTel-native | ~3.1k | MIT | Excellent (self-hosted) |
| 8 | **Haystack Eval** | Best IR metrics (MRR, MAP, NDCG), multilingual SAS | ~24k | Apache 2.0 | Excellent |
| 9 | **Evidently AI** | 100+ metrics, drift detection, visual dashboards, quality monitoring | ~7.3k | Apache 2.0 | Excellent (run locally) |
| 10 | **Galileo** | Only KG validation, Luna eval models (97% cheaper than GPT) | N/A | Proprietary | Poor (cloud-only) |

### Scope of Analysis

- **10 core frameworks** profiled in detail (sections 2-3)
- **16 additional frameworks** evaluated and dismissed with reasons (section 4)
- **6 KG-specific tools** for embedding evaluation, GraphRAG benchmarking, and extraction quality (section 6)
- **6 educational benchmarks** and 2 pedagogical evaluation toolkits (section 7)
- **~70 evaluation needs** mapped across all frameworks in the coverage matrix (section 5)
- **Concrete implementation plans** with code examples for every recommendation (section 10)

---

## 2. Framework Profiles — Core 6

### 2.1 DeepEval (by Confident AI)

- **Install:** `pip install deepeval`
- **Default judge model:** `gpt-4.1`
- **Metric count:** 50+ distinct metrics across RAG, multi-turn, agentic, safety, multimodal, and custom categories
- **Key differentiator:** Native pytest integration (`deepeval test run`), self-explaining metrics (provides reasoning for scores), G-Eval and DAG custom metric frameworks
- **Tracing:** Yes — `@observe` decorator for component-level tracing (spans, LLM calls, retrievers, tool calls). Enhanced visualization via optional Confident AI cloud platform
- **Red-teaming:** Via companion package DeepTeam (`pip install deepteam`) — 40+ vulnerability scanners covering OWASP LLM Top 10
- **CI/CD:** Native pytest plugin; works with any CI/CD environment
- **Traditional NLP:** BLEU, ROUGE, BERTScore available as utility functions via `Scorer` class (not standalone metrics — usable inside custom metrics)
- **Pricing:** Open-source framework is free. Confident AI cloud: Free tier (5 runs/week), Starter ($19.99/user/month), Premium ($79.99/user/month)

### 2.2 RAGAS (Retrieval Augmented Generation Assessment)

- **Install:** `pip install ragas`
- **Metric count:** ~40 distinct metrics/variants across RAG, agent, NLP comparison, traditional NLP, SQL, and general-purpose categories
- **Key differentiator:** Most RAG metric variants (e.g., 4 core Context Precision variants + 2 convenience aliases), purpose-built for RAG evaluation, research-backed metrics
- **Tracing:** Integrations with Arize Phoenix and LangSmith for tracing evaluator LLM calls (not application tracing)
- **Custom metrics:** Highly flexible — `@discrete_metric`, `@numeric_metric`, `@ranking_metric` decorators plus base classes (`MetricWithLLM`, `MultiTurnMetric`, `SingleTurnMetric`)
- **Multi-turn:** Supported via `MultiTurnSample` with `HumanMessage`/`AIMessage` objects. `AspectCritic` is the primary multi-turn metric; agent metrics (`TopicAdherence`, `ToolCallAccuracy`, `AgentGoalAccuracy`) also support multi-turn
- **Safety:** No built-in bias, toxicity, or PII detection metrics (can use `AspectCritic` with custom definitions)
- **Pricing:** 100% free and open-source

### 2.3 Langfuse

- **Install:** `pip install langfuse` (cloud) or Docker Compose (self-hosted)
- **Self-hosting requirements:** Postgres, ClickHouse, Redis/Valkey, S3/Blob Storage
- **Key differentiator:** Full-stack LLM engineering platform — tracing, evaluation, prompt management, experiments, annotation queues, production monitoring
- **Built-in eval metrics:** Growing catalog of managed evaluator templates (examples include Hallucination, Context-Relevance, Toxicity, Helpfulness — catalog is continuously expanded)
- **External integrations:** RAGAS, DeepEval, OpenAI Evals, Langchain Evaluators — scores from any framework can be ingested via `create_score()`
- **Score analytics:** Pearson/Spearman correlation, Cohen's Kappa, F1, MAE, RMSE, confusion matrices
- **Human-in-the-loop:** Annotation queues with reviewer assignment, session-level annotation, dataset curation from production traces
- **Tracing:** OpenTelemetry-compatible; `@observe` decorator for automatic span nesting; scores can attach to traces, observations, or sessions
- **Pricing:** Self-hosted is free (MIT). Cloud: free tier, paid from $29/month

### 2.4 Opik (by Comet)

- **Install:** `pip install opik`
- **Default judge model:** `openai/gpt-5-nano`
- **Key differentiator:** Most heuristic metrics (22+ non-LLM metrics including METEOR, PromptInjection, VADERSentiment), best conversation-specific metrics, 5 dedicated bias judges, LLM Juries for ensemble scoring
- **LLM-as-Judge metrics:** Hallucination (binary), Answer Relevance, Context Precision, Context Recall, Moderation (10 safety categories), Usefulness, Meaning Match, plus G-Eval presets (QA Relevance, Summarization, Compliance Risk, etc.)
- **Heuristic metrics (22+):** Equals, Contains, RegexMatch, IsJson, LevenshteinRatio, SentenceBLEU, CorpusBLEU, GLEU, ROUGE, ChrF, BERTScore, Sentiment, VADERSentiment, Readability, Tone, LanguageAdherence, JSDivergence, JSDistance, KLDivergence, SpearmanRanking, METEOR, PromptInjection
- **Conversation metrics:** ConversationalCoherence, SessionCompletenessQuality, UserFrustration, ConversationDegeneration (heuristic), KnowledgeRetention (heuristic), plus conversation variants of G-Eval judges
- **Tracing:** `@track` decorator, hierarchical spans, distributed tracing, Thread concept for conversation grouping
- **Agent metrics:** AgentTaskCompletionJudge, AgentToolCorrectnessJudge, TrajectoryAccuracy
- **Pricing:** Open-source (full feature set). Comet cloud also available

### 2.5 Giskard

- **Install:** `pip install giskard` (OSS) or Giskard Hub (enterprise platform)
- **Key differentiator:** Best adversarial/red-teaming capabilities. RAGET evaluates 5 RAG components individually. Hub provides 40+ adversarial probes across 11 vulnerability categories
- **RAGET:** Generates 7 question types (Simple, Complex, Distracting, Out of Scope, Situational, Double, Conversational) targeting Generator, Retriever, Rewriter, Router, Knowledge Base
- **OSS detectors (9):** Sycophancy, Control Chars Injection, Faithfulness, Harmfulness, Implausible Outputs, Information Disclosure, Output Formatting, Prompt Injection, Stereotypes
- **Hub red-teaming:** 40+ probes, 11 categories (Harmful Content, Prompt Injection, Excessive Agency, Data Privacy, Hallucination, DoS, Internal Info Exposure, Brand Damage, Misguidance, Training Data Extraction, Legal Risk). Multi-turn attacks via GOAT, Crescendo, TAP methodologies
- **Hub evaluation checks:** Correctness, Conformity, Groundedness, String Matching, Metadata, Semantic Similarity
- **RAGAS integration:** Wrapper metrics — `ragas_context_precision`, `ragas_faithfulness`, `ragas_answer_relevancy`, `ragas_context_recall`
- **Limitations:** No traditional NLP metrics, no standalone retrieval IR metrics, no multi-turn evaluation metrics (beyond RAGET conversational questions)

### 2.6 Vectara Open RAG Eval

- **Install:** `pip install open-rag-eval` (v0.3.0)
- **Key differentiator:** Reference-free evaluation via UMBRELA and AutoNuggetizer (no golden answers needed). Best for A/B comparison of RAG strategies with Streamlit viewer and openevaluation.ai web UI
- **Three evaluator types:**
  - **TRECEvaluator** (reference-free): UMBRELA (retrieval relevance, 0-3 scale), AutoNuggetizer (generation completeness, 6 variants), HHEM hallucination detection (FLAN-T5-based for v2.1), Citation Score
  - **GoldenAnswerEvaluator** (reference-required): Semantic Similarity (embedding cosine), Factual Correctness F1 (claim-based NLI)
  - **ConsistencyEvaluator** (stability): CAI = mean / (1 + std_dev) using BERTScore (xlm-roberta-large) and ROUGE-L
- **Judge providers:** OpenAI (default gpt-4o-mini), Anthropic, Google Gemini, Together AI
- **Limitations:** Single-turn only, no multi-turn support, no safety/bias/toxicity metrics, no KG evaluation, no agent evaluation, limited custom metric documentation

---

## 3. Framework Profiles — Additional Recommendations

### 3.1 LangWatch (Tier 1 — Recommended)

- **Install:** `pip install langwatch` or Docker Compose (self-hosted)
- **GitHub Stars:** ~3.1k | **License:** MIT (fully self-hostable, no feature gates)
- **Evaluator count:** 38 built-in evaluators
- **RAG Quality (13 evaluators):** RAGAS Context Precision, RAGAS Context Recall, RAGAS Faithfulness, Context F1, Context Precision, Context Recall, RAGAS Response Context Precision/Recall, RAGAS Response Relevancy, RAGAS Answer Correctness/Relevancy, RAGAS Context Relevancy/Utilization
- **Safety:** Azure Content Safety, Azure Jailbreak Detection, Azure Prompt Shield, OpenAI Moderation, Presidio PII Detection
- **Multi-turn:** Agent simulation running thousands of synthetic conversations. Query Resolution evaluator.
- **Key differentiator for LAMB:** MIT + self-hosting aligns perfectly with privacy-first design. 13 RAG evaluators (most of any framework). OpenTelemetry-native. Can be added to LAMB's Docker Compose stack.

### 3.2 Evidently AI (Tier 2 — Specialized)

- **Install:** `pip install evidently`
- **GitHub Stars:** ~7.3k | **License:** Apache 2.0 | **Downloads:** 25M+
- **Metric count:** 100+ built-in
- **RAG Retrieval:** NDCG, MAP, MRR, Hit Rate (native IR metrics most frameworks lack)
- **Drift Detection:** 20+ statistical tests (PSI, KL divergence, Wasserstein, Jensen-Shannon, etc.)
- **Key differentiator for LAMB:** Only framework bridging traditional ML monitoring and LLM evaluation. "Run locally, upload summaries" ideal for privacy-sensitive educational data. Visual HTML Reports. Best for detecting quality degradation over time.

### 3.3 Galileo (Tier 2 — KG-Specific)

- **Install:** SDK via pip | **License:** Proprietary | **Pricing:** Free tier (5k traces/month)
- **RAG (chunk-level):** Chunk Attribution, Chunk Utilization, Chunk Relevance — Luna evaluation models (fine-tuned DeBERTa-large 440M) at 97% cost reduction vs GPT-3.5
- **Knowledge Graph:** **YES — the ONLY framework with native KG validation.** Knowledge Bases feature validates against established relationships.
- **Key differentiator:** Only KG validation. Luna purpose-built eval models (not LLM-as-judge). Token-level scoring.
- **Caveat:** Cloud-only — **significant privacy concern** for student data. Use only with non-sensitive datasets or negotiate data processing agreement.

### 3.4 Haystack Evaluation Module (Tier 2 — IR Metrics)

- **Install:** `pip install haystack-ai`
- **GitHub Stars:** ~24k | **License:** Apache 2.0
- **IR Metrics:** DocumentMRREvaluator, DocumentMAPEvaluator, DocumentRecallEvaluator, DocumentNDCGEvaluator
- **Statistical:** SASEvaluator (Semantic Answer Similarity, **multilingual** — relevant for LAMB's en/es/ca/eu)
- **Integrations:** RagasEvaluator (all RAGAS metrics), DeepEvalEvaluator (all DeepEval metrics) as pipeline components
- **Key differentiator:** Pipeline-native evaluators. Best IR metrics suite. Multilingual SAS via cross-encoder.

### 3.5 Tier 2 — Worth Noting (Brief)

| Framework | Install | Stars | Unique Value | Verdict |
|---|---|---|---|---|
| **TruLens** | `pip install trulens` | ~2k | Agent's GPA (Goal/Plan/Action) framework; OTel-native; Snowflake integration | Good if in Snowflake ecosystem |
| **Continuous Eval** | `pip install continuous-eval` | ~490 | Deterministic Faithfulness (token-level, no LLM); three-tier metric system | Unique deterministic faithfulness for CI/CD |
| **Braintrust autoevals** | `pip install autoevals` | ~834 | Most mature OSS scorer library (Battle, Factuality, Moderation, etc.) | Handy complementary scorer library |
| **Athina AI** | `pip install athina` | ~298 | 50+ preset evaluators; dedicated conversation evals; RAGAS integration | Good breadth, small community |
| **W&B Weave** | `pip install weave` | ~1.1k | Local on-device scorers (HHEM 2.1, DeBERTa) — zero API cost | Compelling for privacy-first, requires W&B buy-in |
| **Parea AI** | `pip install parea-ai` | ~82 | Goal Success Ratio (measures if students achieve goals); Cross-Examination hallucination | Relevant for educational assessment, tiny community |

---

## 4. Frameworks Evaluated but Not Recommended

| Framework | Reason |
|---|---|
| **Humanloop** | Acquired by Anthropic Aug 2025, platform shut down Sep 2025. No longer exists. |
| **Quotient AI** | Acquired by Databricks March 2026. Future as standalone tool uncertain. |
| **Baserun** | Immature — 16 GitHub stars, minimal built-in metrics, tiny community. |
| **Tonic Validate** | UI sunset August 2025. Very narrow scope (RAG only, ~6 metrics). |
| **UpTrain** | Decent metrics (20+) but community stalled at ~2.3k stars. Root cause analysis is unique but not enough to displace DeepEval/RAGAS. |
| **LlamaIndex Evaluation** | Tightly coupled to LlamaIndex framework. LAMB doesn't use LlamaIndex. Metrics available via DeepEval/RAGAS. |
| **LangChain/OpenEvals** | Same coupling issue — best used within LangChain/LangSmith. LAMB doesn't use LangChain. |
| **Arize Phoenix** | Good observability but Elastic License 2.0 (not OSI-approved). Fewer eval metrics (6) than Langfuse/Opik. |
| **Patronus AI** | Strong hallucination model but commercial SaaS only. No self-hosting. Privacy concern. |
| **Maxim AI** | Commercial SaaS. No self-hosting. Similar coverage to Langfuse/Opik. |

---

## 5. Evaluation Coverage Matrix

### Legend

| Symbol | Meaning |
|--------|---------|
| **Native** | Built-in metric, ready to use |
| **Partial** | Indirectly supported or limited coverage |
| **Custom** | No built-in metric, but custom metric API can build it |
| **Via integration** | Available through a documented external framework integration |
| **--** | Not supported |

### A. RAG Core Evaluation (Current LAMB)

| Evaluation Need | DeepEval | RAGAS | Langfuse | Opik | Giskard | Vectara |
|---|---|---|---|---|---|---|
| **Faithfulness** | **Native** — `FaithfulnessMetric` | **Native** — `Faithfulness` + `FaithfulnesswithHHEM` (free T5) | **Native** — managed template + RAGAS integration | **Native** — `Hallucination` (binary) | **Partial** — `Groundedness` (Hub); RAGAS wrapper (OSS) | **Native** — HHEM (FLAN-T5, 0-1) |
| **Answer Relevancy** | **Native** — `AnswerRelevancyMetric` | **Native** — `ResponseRelevancy` | **Via integration** — RAGAS or LLM-as-Judge | **Native** — `AnswerRelevance` | **Partial** — RAGAS wrapper | **--** |
| **Context Precision** | **Native** — `ContextualPrecisionMetric` | **Native** — 4 core + 2 convenience variants | **Via integration** — RAGAS | **Native** — `ContextPrecision` | **Partial** — RAGAS wrapper | **Partial** — UMBRELA (0-3 per passage) |
| **Context Recall** | **Native** — `ContextualRecallMetric` | **Native** — 3 core + 1 convenience variant | **Via integration** — RAGAS | **Native** — `ContextRecall` | **Partial** — RAGAS wrapper | **Partial** — AutoNuggetizer vital score |
| **Context Relevancy** | **Native** — `ContextualRelevancyMetric` | **Partial** — NVIDIA `ContextRelevance` | **Custom** — LLM-as-Judge | **--** | **--** | **Native** — UMBRELA |
| **Hallucination Detection** | **Native** — `HallucinationMetric` | **Native** — via Faithfulness (inverse) | **Native** — managed template | **Native** — `Hallucination` (binary) | **Native** — Sycophancy + RAGET + Hub probes | **Native** — HHEM (deterministic) |
| **Noise Sensitivity** | **--** | **Native** — `NoiseSensitivity` (relevant/irrelevant modes) | **Custom** | **--** | **Partial** — RAGET "Distracting" questions | **--** |
| **Context Entities Recall** | **--** | **Native** — `ContextEntityRecall` | **Custom** | **--** | **--** | **--** |
| **Factual Correctness** | **Custom** — G-Eval | **Native** — `FactualCorrectness` (P/R/F1) | **Custom** | **--** | **Native** — `Correctness` (Hub) | **Native** — `FactualCorrectnessF1` |
| **Semantic Similarity** | **Custom** — `Scorer.bert_score()` | **Native** — `SemanticSimilarity` | **Custom** | **Native** — `BERTScore` + `MeaningMatch` | **Native** — Hub `SemanticSimilarity` | **Native** — GoldenAnswerEvaluator |
| **RAG strategy A/B comparison** | **Native** — `pytest.mark.parametrize` | **Native** — `evaluate()` per strategy | **Native** — Experiments | **Native** — Experiment comparison | **Partial** — RAGET per pipeline | **Native** — core use case |

### B. Context-Aware RAG / Multi-Turn Evaluation (Future LAMB)

| Evaluation Need | DeepEval | RAGAS | Langfuse | Opik | Giskard | Vectara |
|---|---|---|---|---|---|---|
| **Multi-turn coherence** | **Native** — `TurnRelevancyMetric` | **Partial** — `AspectCritic` with custom definition | **Partial** — N+1 methodology | **Native** — `ConversationalCoherence` | **Partial** — RAGET "Conversational" | **--** |
| **Query rewriting quality** | **Custom** — G-Eval | **Custom** — `AspectCritic`/`DiscreteMetric` | **Custom** — LLM-as-Judge | **Custom** — G-Eval | **Partial** — RAGET tests Rewriter | **--** |
| **Knowledge retention** | **Native** — `KnowledgeRetentionMetric` | **--** | **Custom** | **Native** — `KnowledgeRetention` (heuristic) | **--** | **--** |
| **Session completeness** | **Native** — `ConversationCompletenessMetric` | **Partial** — `AgentGoalAccuracy` | **Partial** — session scoring | **Native** — `SessionCompletenessQuality` | **--** | **--** |
| **Turn-level faithfulness** | **Native** — `TurnFaithfulnessMetric` | **--** | **Partial** — observation scoring | **--** | **--** | **--** |
| **Turn-level context relevancy** | **Native** — `TurnContextualRelevancyMetric` | **--** | **Partial** | **--** | **--** | **--** |
| **Turn-level context recall** | **Native** — `TurnContextualRecallMetric` | **--** | **Partial** | **--** | **--** | **--** |
| **Turn-level context precision** | **Native** — `TurnContextualPrecisionMetric` | **--** | **Partial** | **--** | **--** | **--** |
| **Role/persona adherence** | **Native** — `RoleAdherenceMetric` + `RoleViolationMetric` | **Custom** — `AspectCritic` | **Custom** | **--** | **--** | **--** |
| **User frustration** | **--** | **--** | **Custom** | **Native** — `UserFrustration` | **--** | **--** |
| **Conversation degeneration** | **--** | **--** | **--** | **Native** — `ConversationDegeneration` (heuristic) | **--** | **--** |
| **Topic adherence** | **Custom** — G-Eval | **Native** — `TopicAdherence` (P/R/F1) | **Custom** | **--** | **--** | **--** |

### C. Knowledge Graph Evaluation (Future LAMB)

| Evaluation Need | DeepEval | RAGAS | Langfuse | Opik | Giskard | Vectara |
|---|---|---|---|---|---|---|
| **Entity extraction P/R/F1** | **Custom** — G-Eval or `BaseMetric` | **Custom** — `@numeric_metric` | **Custom** — push scores via SDK | **Custom** — `BaseMetric` | **--** | **--** |
| **Relation extraction P/R/F1** | **Custom** — G-Eval or `BaseMetric` | **Custom** — `@numeric_metric` | **Custom** — push scores via SDK | **Custom** — `BaseMetric` | **--** | **--** |
| **Graph completeness** | **Custom** — G-Eval | **Custom** | **Custom** — push scores | **Custom** | **--** | **--** |
| **Graph traversal quality** | **Custom** — DAG metric | **Custom** | **Custom** — push scores | **Custom** | **--** | **--** |
| **Triple/fact accuracy** | **Custom** — G-Eval | **Partial** — `FactualCorrectness` on linearized triples | **Custom** | **Custom** | **--** | **--** |
| **KG-grounded faithfulness** | **Partial** — Faithfulness with serialized graph context | **Partial** — same workaround | **Partial** — LLM-as-Judge | **Partial** — Hallucination on graph text | **--** | **Partial** — HHEM |
| **Hybrid retrieval (KG+vector)** | **Partial** — RAG metrics on combined context | **Partial** — same | **Partial** — separate span scores | **Partial** — RAG metrics | **--** | **Partial** — UMBRELA |
| **Structured-unstructured fusion** | **Custom** — G-Eval | **Custom** | **Custom** | **Custom** — G-Eval | **--** | **--** |
| **Ontology alignment** | **Custom** — G-Eval | **Custom** | **Custom** | **Custom** | **--** | **--** |

### D. Safety, Bias & Educational Suitability

| Evaluation Need | DeepEval | RAGAS | Langfuse | Opik | Giskard | Vectara |
|---|---|---|---|---|---|---|
| **Bias detection** | **Native** — `BiasMetric` | **Custom** — `AspectCritic` | **Custom** | **Native** — 5 bias judges | **Native** — `StereotypesDetector` | **--** |
| **Toxicity** | **Native** — `ToxicityMetric` | **Custom** | **Native** — managed template | **Native** — `Moderation` (10 categories) | **Native** — `HarmfulContentDetector` | **--** |
| **PII leakage** | **Native** — `PIILeakageMetric` | **--** | **Custom** | **Partial** — `Moderation` PII | **Native** — `InformationDisclosureDetector` | **--** |
| **Prompt injection resistance** | **Native** — DeepTeam (40+ scanners) | **--** | **--** | **Native** — `PromptInjection` heuristic | **Native** — 12 attack probes (Hub) | **--** |
| **Misuse detection** | **Native** — `MisuseMetric` | **Partial** — `TopicAdherence` | **Custom** | **--** | **Partial** — RAGET "Out of Scope" | **--** |
| **Inappropriate advice** | **Native** — `NonAdviceMetric` | **Custom** | **Custom** | **Partial** — `ComplianceRiskJudge` | **Native** — `UnauthorizedAdvice` (Hub) | **--** |
| **Educational rubric** | **Custom** — G-Eval/DAG | **Native** — `RubricsScore` (1-5 scale) | **Custom** | **Custom** — G-Eval | **Custom** | **--** |
| **Red-teaming** | **Native** — DeepTeam (40+) | **--** | **--** | **--** | **Native** — 40+ probes, GOAT/Crescendo/TAP | **--** |
| **Sycophancy** | **--** | **--** | **--** | **--** | **Native** — `SycophancyDetector` | **--** |

### E. Traditional NLP Baselines & General Metrics

| Metric | DeepEval | RAGAS | Langfuse | Opik | Giskard | Vectara |
|---|---|---|---|---|---|---|
| **BLEU** | **Partial** — `Scorer` utility | **Native** — `BleuScore` | **--** | **Native** — `SentenceBLEU` + `CorpusBLEU` | **--** | **--** |
| **ROUGE** | **Partial** — `Scorer` utility | **Native** — `RougeScore` | **--** | **Native** — `ROUGE` (5 variants) | **--** | **Partial** — ConsistencyEvaluator |
| **BERTScore** | **Partial** — `Scorer` utility | **--** | **--** | **Native** — `BERTScore` | **--** | **Partial** — ConsistencyEvaluator |
| **METEOR** | **--** | **--** | **--** | **Native** | **--** | **--** |
| **ChrF** | **--** | **Native** — `ChrfScore` | **--** | **Native** — `ChrF`/`ChrF++` | **--** | **--** |
| **Exact Match** | **Native** | **Native** | **--** | **Native** — `Equals` | **--** | **--** |
| **String Similarity** | **--** | **Native** — `NonLLMStringSimilarity` (4 algorithms) | **--** | **Native** — `LevenshteinRatio` | **--** | **--** |
| **Summarization** | **Native** — `SummarizationMetric` | **Native** — `SummaryScore` | **Custom** | **Partial** — consistency+coherence judges | **--** | **--** |
| **Readability** | **--** | **--** | **--** | **Native** — Flesch | **--** | **--** |
| **Sentiment** | **--** | **--** | **--** | **Native** — VADER | **--** | **--** |
| **Language detection** | **--** | **--** | **--** | **Native** — `LanguageAdherence` | **--** | **--** |
| **JSON validation** | **Native** — `JsonCorrectnessMetric` | **--** | **Partial** | **Native** — `IsJson` + `StructuredOutputCompliance` | **Partial** — Hub `Metadata` | **--** |
| **Response consistency** | **--** | **--** | **--** | **--** | **--** | **Native** — CAI |
| **Citation accuracy** | **--** | **--** | **--** | **--** | **--** | **Native** — Citation Score |

### F. Agent / Tool Use Metrics

| Metric | DeepEval | RAGAS | Langfuse | Opik | Giskard | Vectara |
|---|---|---|---|---|---|---|
| **Tool call accuracy** | **Native** — `ToolCorrectnessMetric` + `ArgumentCorrectnessMetric` | **Native** — `ToolCallAccuracy` | **Custom** | **Native** — `AgentToolCorrectnessJudge` + `TrajectoryAccuracy` | **Partial** — Hub probes | **--** |
| **Task completion** | **Native** — `TaskCompletionMetric` | **Native** — `AgentGoalAccuracy` (2 variants) | **Custom** | **Native** — `AgentTaskCompletionJudge` | **--** | **--** |
| **Step efficiency** | **Native** — `StepEfficiencyMetric` | **--** | **--** | **--** | **--** | **--** |
| **Plan quality** | **Native** — `PlanQualityMetric` + `PlanAdherenceMetric` | **--** | **--** | **--** | **--** | **--** |
| **Tool call F1** | **--** | **Native** — `ToolCallF1` | **--** | **--** | **--** | **--** |

### G. Observability & Pipeline Tracing

| Capability | DeepEval | RAGAS | Langfuse | Opik | Giskard | Vectara |
|---|---|---|---|---|---|---|
| **Multi-step pipeline tracing** | **Native** — `@observe` | **Partial** — Phoenix/LangSmith integrations | **Native** — full OTel tracing | **Native** — `@track`, distributed | **--** | **--** |
| **Per-span scoring** | **Partial** | **--** | **Native** | **Native** | **--** | **--** |
| **Session grouping** | **--** | **--** | **Native** — `sessionId` | **Native** — Threads | **--** | **--** |
| **Cost/latency tracking** | **--** | **--** | **Native** | **Native** | **--** | **--** |
| **Human annotation** | **--** | **--** | **Native** — annotation queues | **--** | **Native** — Hub | **--** |
| **Production monitoring** | **Partial** — Confident AI cloud | **--** | **Native** | **Native** — 40M+ traces/day | **Partial** — Hub | **--** |

### H. Custom Metric Flexibility

| Framework | Custom API | Flexibility |
|---|---|---|
| **DeepEval** | `BaseMetric` subclass, G-Eval, DAG, ConversationalGEval, ConversationalDAG, Arena G-Eval | Very High |
| **RAGAS** | `@discrete_metric`, `@numeric_metric`, `@ranking_metric` decorators + base classes | Very High |
| **Langfuse** | Custom eval functions → push scores via `create_score()` | High (framework-agnostic) |
| **Opik** | `BaseMetric` subclass + G-Eval (CoT + log-prob weighted) | Very High |
| **Giskard** | `Metric` base class + `@test` decorator | Moderate |
| **Vectara** | Custom evaluator classes (sparse docs) | Low |

---

## 6. Knowledge Graph Evaluation Tools

### The KG Evaluation Gap

All 10 general-purpose LLM evaluation frameworks have zero native KG evaluation, with one exception (Galileo). Specialized tools fill this gap:

### PyKEEN — KG Embedding Evaluation (Recommended)

- **Install:** `pip install pykeen` | **License:** MIT
- **Metrics (44):** Hits@1/3/5/10, MRR, MR, Adjusted MR, Inverse Harmonic MR, classification metrics (Accuracy, F1, Precision, Recall, AUC-ROC), rank-based evaluators
- **Models:** TransE, RotatE, ComplEx, DistMult, and 30+ others
- **Relevance:** Evaluates KG embedding quality if LAMB implements KG embeddings for entity/relation lookup.

### GraphRAG-Bench (ICLR 2026)

- First comprehensive benchmark for evaluating GraphRAG models
- 4 task types: fact retrieval, complex reasoning, contextual summarization, creative generation
- 16 disciplines, 20 core textbooks, tested on 9 GraphRAG methods
- **Repo:** [github.com/GraphRAG-Bench/GraphRAG-Benchmark](https://github.com/GraphRAG-Bench/GraphRAG-Benchmark)

### BenchmarkQED (Microsoft Research)

- Companion to Microsoft's GraphRAG library
- **AutoQ:** Automated query generation | **AutoE:** LLM-as-Judge pairwise evaluation | **AutoD:** Automated dataset preparation
- **Repo:** [github.com/microsoft/benchmark-qed](https://github.com/microsoft/benchmark-qed)

### KGGen + MINE Benchmark

- **Install:** `pip install kg-gen`
- **MINE-1:** Measures knowledge retention (how much source text the KG captures)
- **MINE-2:** Evaluates RAG effectiveness (how well the KG improves retrieval/reasoning)
- Outperforms OpenIE and GraphRAG by 18% in KG accuracy
- **Repo:** [github.com/stair-lab/kg-gen](https://github.com/stair-lab/kg-gen)

### GraphEval (Amazon)

- Converts LLM output to a KG, evaluates each triple against context using NLI models
- Identifies specific hallucinated triples. Includes GraphCorrect for correction.
- **Paper:** [arxiv.org/abs/2407.10793](https://arxiv.org/abs/2407.10793)

### KG Evaluation Strategy Summary

| KG Need | Tool | How |
|---|---|---|
| **KG embedding quality** | PyKEEN | Train embeddings, evaluate with Hits@k, MRR |
| **GraphRAG end-to-end** | GraphRAG-Bench | Run benchmark tasks against LAMB's pipeline |
| **KG extraction quality** | KGGen MINE | MINE-1 (retention) + MINE-2 (RAG effectiveness) |
| **KG-based hallucination** | GraphEval | Convert response to triples, verify via NLI |
| **KG domain validation** | Galileo | Knowledge Bases feature (cloud-only caveat) |
| **Entity/relation P/R/F1** | Custom (DeepEval/RAGAS) | Deterministic `BaseMetric` or `@numeric_metric` |

---

## 7. Educational AI Evaluation

### 7.1 Pedagogical Evaluation Dimensions

| # | Dimension | Description | How to Evaluate |
|---|-----------|-------------|-----------------|
| 1 | **Faithfulness to source content** | RAG response stays accurate to course material | DeepEval `FaithfulnessMetric` / RAGAS `Faithfulness` |
| 2 | **Scaffolding quality** | Breaks down problems progressively | Custom G-Eval or RAGAS `RubricsScore` with pedagogical rubric |
| 3 | **Answer avoidance** | Guides without giving away answers | Custom G-Eval: "Does the response guide without revealing the answer?" |
| 4 | **Mistake identification** | Recognizes errors in student work | Custom evaluation dataset; measure detection accuracy |
| 5 | **Adaptive feedback** | Adjusts to learner's demonstrated level | Custom G-Eval assessing response appropriateness |
| 6 | **Bloom's cognitive level** | Targets appropriate cognitive depth | Custom RAGAS `RubricsScore` with Bloom's taxonomy |
| 7 | **Actionability** | Suggestions are clear and specific | Custom G-Eval: "Are suggestions specific enough to act on?" |
| 8 | **Coherence & tone** | Natural, encouraging, age-appropriate | Opik `Tone` + `Readability` + custom G-Eval |

### 7.2 Key Educational Benchmarks

| Benchmark | Focus | Size | Relevance |
|---|---|---|---|
| **MathTutorBench** (EMNLP 2025) | 7 teaching tasks, trained reward model | 3 skills, 7 tasks | High — reward model could score LAMB math responses |
| **TutorBench** (Oct 2025) | Adaptive explanations, feedback, hints | 1,490 samples | High — AP/high-school level |
| **EduBench** | 9 educational scenarios, bilingual | 4,000+ contexts | Medium — Chinese+English focus |
| **KMP-Bench** (Mar 2026) | K-8 math pedagogy, 6 core principles | Dialogue + Skills | Medium — pedagogical principles transfer |
| **Khan Academy CoMTA** | Tutoring accuracy in math | 188 conversations | High — real tutoring conversations |
| **EducationQ** (ACL 2025) | Multi-agent teaching evaluation | 1,498 questions, 13 disciplines | High — cross-discipline teaching quality |

### 7.3 Reusable Toolkits

**Unifying AI Tutor Evaluation (NAACL 2025, SAC Award)**
- 8 dimensions: Mistake Identification, Mistake Location, Answer Revelation, Guidance, Actionability, Coherence, Tone, Human-likeness
- Benchmark: MRBench — 192 conversations, 1,596 responses
- **Open source:** [github.com/kaushal0494/UnifyingAITutorEvaluation](https://github.com/kaushal0494/UnifyingAITutorEvaluation)
- **Use in LAMB:** Adapt the 8-dimension rubric as a RAGAS `RubricsScore` or DeepEval G-Eval criteria set.

**AITutor-EvalKit (MIT License)**
- 4 dimensions: Mistake Identification, Mistake Location, Providing Guidance, Actionability
- Automated scoring: 0.72 accuracy, 0.60 macro-F1
- **Open source:** [github.com/kaushal0494/AITutor-EvalKit](https://github.com/kaushal0494/AITutor-EvalKit)
- **Use in LAMB:** Run directly on LAMB assistant outputs for education-specific scoring.

---

## 8. Gap Analysis

### Critical Gaps — Zero Native Support Across All Frameworks

| Gap | Impact | Mitigation |
|---|---|---|
| **KG entity extraction P/R/F1** | Cannot evaluate NER accuracy for KG construction | Custom metric in DeepEval (`BaseMetric`) or RAGAS (`@numeric_metric`) |
| **KG relation extraction P/R/F1** | Cannot evaluate relationship extraction quality | Custom deterministic metric comparing triples against gold-standard |
| **Graph completeness scoring** | Cannot evaluate KG knowledge coverage | Custom metric + KGGen MINE-1 benchmark |
| **Graph traversal quality** | Cannot evaluate optimal KG path selection | Custom DeepEval DAG metric for step-by-step evaluation |
| **Ontology alignment** | Cannot evaluate KG structure conformance | Custom metric; Jaccard similarity on type sets |
| **Structured-unstructured fusion** | Cannot evaluate graph+text integration quality | Custom LLM-as-Judge (G-Eval) with fusion criteria |

### Partial Gaps

| Gap | Best Coverage | What's Missing |
|---|---|---|
| **Query rewriting quality** | Giskard RAGET (indirect); all frameworks via custom G-Eval | No direct semantic preservation or intent alignment measurement |
| **Hybrid retrieval evaluation** | All RAG metrics work on combined context | No metric evaluates fusion strategy optimization |
| **KG-grounded faithfulness** | Faithfulness metrics work on serialized graph text | No framework natively understands triples/structured graph context |

### Framework Strengths Summary

| Framework | Strongest For | Weakest For |
|---|---|---|
| **DeepEval** | Most metrics (50+), best multi-turn RAG, best custom flexibility | Traditional NLP only as utilities |
| **RAGAS** | Most RAG metric variants, traditional NLP, SQL, educational rubrics | Weakest multi-turn, no safety metrics |
| **Langfuse** | Best observability, tracing, human annotation, production monitoring | Fewest built-in eval metrics |
| **Opik** | Best heuristics (22+), best conversation metrics, best bias detection | No noise sensitivity, no turn-level RAG |
| **Giskard** | Best adversarial testing (40+ probes), best RAG component diagnosis | No traditional NLP, no IR metrics |
| **Vectara** | Best reference-free evaluation, best A/B comparison, best consistency | Single-turn only, fewest metrics |
| **LangWatch** | Most RAG evaluators (13), MIT self-hosted, OTel-native | Newer, smaller community |
| **Haystack** | Best IR metrics (MRR/MAP/NDCG), multilingual SAS | Not a standalone eval platform |
| **Evidently** | 100+ metrics, drift detection, visual dashboards | No multi-turn, no dedicated RAG metrics beyond IR |
| **Galileo** | Only KG validation, Luna eval models (cheap/fast) | Cloud-only, privacy concern |

---

## 9. Final Ranking — All Frameworks Combined

### Tier 1 — Core Stack (Use These)

| # | Framework | Role in LAMB Stack | Why |
|---|---|---|---|
| 1 | **DeepEval** | Primary CI/CD evaluation | 50+ metrics, pytest-native, best multi-turn RAG, G-Eval/DAG for custom KG metrics, `@observe` tracing |
| 2 | **RAGAS** | RAG-specific deep analysis | Deepest RAG metric variants, noise sensitivity, context entities recall, traditional NLP, educational rubrics via `RubricsScore` |
| 3 | **Langfuse** or **LangWatch** | Observability & tracing | Both MIT/self-hostable. LangWatch: more evaluators (38). Langfuse: stronger annotation + monitoring. **Choose: evaluator breadth → LangWatch; annotation → Langfuse** |
| 4 | **Opik** | Conversation quality & heuristics | Best multi-turn metrics, 22+ heuristic metrics, 5 bias judges |
| 5 | **Giskard** | Red-teaming & safety | 40+ adversarial probes, prompt injection (12 variants), sycophancy, RAGET component diagnosis |

### Tier 2 — Specialized Additions

| # | Framework | Role | Why |
|---|---|---|---|
| 6 | **Vectara Open RAG Eval** | Reference-free RAG comparison | UMBRELA + AutoNuggetizer for A/B testing without golden answers |
| 7 | **Haystack Evaluation** | IR metrics | Best native MRR, MAP, NDCG, Recall. Multilingual SAS for LAMB's 4 locales |
| 8 | **Evidently AI** | Quality monitoring & drift | 100+ metrics, visual dashboards, drift detection. Privacy-friendly |
| 9 | **Galileo** | KG validation (future) | Only native KG validation. Luna models. **Caveat:** cloud-only, privacy concern |

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

## 10. Recommended Evaluation Stack & Implementation Plans

### 10.1 RAG Core Evaluation (Current)

| Need | Framework | Metric(s) | Implementation |
|---|---|---|---|
| **Faithfulness** | DeepEval | `FaithfulnessMetric(threshold=0.7)` | `LLMTestCase(input=q, actual_output=a, retrieval_context=ctx)` → `assert_test(tc, [metric])` in pytest |
| **Faithfulness (free, no API)** | RAGAS | `FaithfulnesswithHHEM` | Uses Vectara's open-source T5 model locally. Zero API cost. |
| **Answer Relevancy** | DeepEval | `AnswerRelevancyMetric(threshold=0.7)` | Same pytest pattern. Only needs `input` + `actual_output`. |
| **Context Precision** | RAGAS | `LLMContextPrecisionWithoutReference` | No gold answers needed: `scorer.ascore(user_input=q, response=a, retrieved_contexts=ctx)` |
| **Context Recall** | RAGAS | `LLMContextRecall` | Requires `reference` (gold answer). Build small gold-standard dataset per course. |
| **Context Relevancy** | DeepEval | `ContextualRelevancyMetric(threshold=0.6)` | Measures fraction of retrieved statements that are relevant. |
| **Hallucination (baseline)** | Vectara | HHEM (TRECEvaluator) | Reference-free, deterministic, fast. YAML config with `hhem` backend. |
| **Noise Sensitivity** | RAGAS | `NoiseSensitivity(mode="relevant")` | Only RAGAS has this. Measures errors from irrelevant context. |
| **RAG strategy comparison** | Vectara | TRECEvaluator via CSV | Export results per strategy to CSV. Run `open-rag-eval eval`. Compare via Streamlit. |
| **IR metrics (retrieval)** | Haystack | `DocumentMRREvaluator`, `DocumentMAPEvaluator`, `DocumentNDCGEvaluator` | Pure Python evaluators. Evaluate retriever independently from generation. |

### 10.2 Context-Aware RAG / Multi-Turn (Future)

| Need | Framework | Metric(s) | Implementation |
|---|---|---|---|
| **Multi-turn coherence** | Opik | `ConversationalCoherence(window_size=8)` | `evaluate_threads(project_name=..., metrics=[...])`. Threads auto-reconstructed. |
| **Turn-level faithfulness** | DeepEval | `TurnFaithfulnessMetric(threshold=0.7)` | `ConversationalTestCase(turns=[...])` where each turn has `retrieval_context`. |
| **Turn-level context relevancy** | DeepEval | `TurnContextualRelevancyMetric` | Same `ConversationalTestCase` pattern. |
| **Knowledge retention** | DeepEval or Opik | DeepEval `KnowledgeRetentionMetric` (LLM) or Opik `KnowledgeRetention` (heuristic, no LLM) | Opik heuristic variant is faster for CI. |
| **Session completeness** | Opik | `SessionCompletenessQuality()` | Extracts all user intentions, evaluates if each was addressed. |
| **Query rewriting quality** | Opik | `GEval(task_introduction="...", evaluation_criteria="...")` | Custom criteria: "Does rewrite preserve intent? More specific? No new assumptions?" |
| **Role adherence** | DeepEval | `RoleAdherenceMetric(chatbot_role="educational learning assistant")` | Checks each assistant turn against defined role. |
| **User frustration** | Opik | `UserFrustration()` | LLM judge evaluates session for confusion/disengagement signals. |
| **Topic adherence** | RAGAS | `TopicAdherence(mode="f1", reference_topics=["course material", ...])` | P/R/F1 against allowed topic list. |

### 10.3 Knowledge Graph (Future)

| Need | Framework | Metric(s) | Implementation |
|---|---|---|---|
| **Entity extraction F1** | DeepEval | Custom `BaseMetric` | Parse `actual_output` (extracted entities JSON) and `expected_output` (gold). Set intersection → TP/FP/FN → F1. Deterministic, no LLM. |
| **Relation extraction F1** | RAGAS | Custom `@numeric_metric` | `@numeric_metric(name="relation_f1", allowed_values=(0,1))`. Parse triples as `set(tuple(t))`. Compute F1. |
| **Graph completeness** | DeepEval | Custom G-Eval | `GEval(name="graph_completeness", criteria="What fraction of key concepts from source docs are captured in the KG?")` |
| **Graph traversal quality** | DeepEval | Custom DAG metric | `TaskNode` (extract path) → `BinaryJudgementNode` (reaches target?) → `NonBinaryJudgementNode` (path optimality) → `VerdictNode` (0-10). |
| **KG embedding quality** | PyKEEN | `pipeline(dataset=triples, model="RotatE")` | `pip install pykeen`. Evaluate Hits@k, MRR after training. |
| **KG extraction quality** | KGGen MINE | MINE-1 + MINE-2 | `pip install kg-gen`. Evaluate retention and RAG effectiveness. |
| **KG-grounded faithfulness** | DeepEval | `FaithfulnessMetric` with serialized triples | Convert triples to natural language: `f"{s} {p} {o}"`. Pass as `retrieval_context`. |
| **Hybrid retrieval fusion** | Langfuse + DeepEval | Separate span scores + combined eval | Trace KG and vector retrieval as separate Langfuse spans. Score each with `ContextualRelevancyMetric`. Compare span vs combined scores. |

### 10.4 Safety & Educational Quality

| Need | Framework | Metric(s) | Implementation |
|---|---|---|---|
| **Bias detection** | Opik | 5 judges: `DemographicBiasJudge`, `GenderBiasJudge`, `PoliticalBiasJudge`, `ReligiousBiasJudge`, `RegionalBiasJudge` | Run all 5 on diverse prompts. Assert all scores < 0.1 in CI. |
| **Toxicity** | DeepEval | `ToxicityMetric(threshold=0.05)` | Low threshold for educational context. Run on every completion. |
| **PII leakage** | DeepEval | `PIILeakageMetric(threshold=0.0)` | Zero tolerance for educational responses. |
| **Prompt injection** | Giskard | `scan(model, only=["prompt_injection"])` | Wrap LAMB endpoint in Giskard `Model`. Run 12 attack probes. |
| **Full adversarial scan** | Giskard Hub | Full scan — 40+ probes, 11 categories | Multi-turn attacks via GOAT, Crescendo, TAP. |
| **Misuse detection** | DeepEval | `MisuseMetric(domain="educational learning assistance")` | Flags out-of-domain responses. |
| **Inappropriate advice** | DeepEval | `NonAdviceMetric(advice_types=["medical", "legal", "financial"])` | Ensures no professional advice. |
| **Sycophancy** | Giskard | `SycophancyDetector` | Critical for education — students may have misconceptions. |
| **Pedagogical rubric** | RAGAS | `RubricsScore(rubrics={1: "Gives answer directly...", 5: "Excellent scaffolding..."})` | Define once, reuse. Maps to LAMB's educational mission. |
| **Educational scoring** | AITutor-EvalKit | 4 dimensions (Mistake ID, Location, Guidance, Actionability) | Clone repo. Prepare dataset. Run batch evaluation. |

### 10.5 Observability & Tracing

| Need | Framework | Implementation |
|---|---|---|
| **Pipeline tracing** | Langfuse or LangWatch | `@observe` / `@langwatch.trace()` on completion pipeline functions. Each step becomes a nested span. |
| **KG+RAG pipeline tracing** | Langfuse | 4 spans: entity-extraction → graph-query → context-fusion → generation. Score each independently. |
| **Push external scores** | Langfuse | `langfuse.create_score(trace_id=..., name="faithfulness", value=metric.score, comment=metric.reason)` |
| **Session grouping** | Langfuse or Opik | `session_id` / `thread_id` on traces. Session replay + analytics. |
| **Quality monitoring** | Evidently AI | `Report(metrics=[TextEvals(...)]).run(reference_data, current_data).save_html("report.html")` — drift detection after model/prompt changes. |
| **Multilingual eval** | Haystack | `SASEvaluator()` with multilingual cross-encoder for LAMB's en/es/ca/eu. |

### 10.6 Bridging Frameworks (DeepEval ↔ Langfuse)

```python
# Run DeepEval metrics, visualize in Langfuse
from deepeval.metrics import FaithfulnessMetric
from deepeval.test_case import LLMTestCase
from langfuse import get_client

langfuse = get_client()
traces = langfuse.api.trace.list(tags="lamb-assistant", limit=100).data

for trace in traces:
    tc = LLMTestCase(input=trace.input, actual_output=trace.output,
                     retrieval_context=trace.metadata.get("contexts", []))
    metric = FaithfulnessMetric(threshold=0.7)
    metric.measure(tc)
    langfuse.create_score(trace_id=trace.id, name="faithfulness",
                          value=metric.score, comment=metric.reason)
langfuse.flush()
```

---

## 11. Decision Matrix — When to Use What

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

---

## 12. Execution Model — Optimized Metric-to-Model Assignment

### 12.1 Judge Model Reliability Data

Based on the Judge's Verdict benchmark (Oct 2025, 54 models tested) and OpenAI benchmarks:

| Model | Cohen's κ | IFEval | MMLU | Cost ($/MTok in/out) | Reliability estimate |
|---|---|---|---|---|---|
| **GPT-4.1** | 0.792 (Tier 1, human-like) | 87.4% | 90.2% | $2.00 / $8.00 | ~98% |
| **GPT-4.1-mini** | Not tested (est. Tier 1) | 84.1% | 87.5% | $0.40 / $1.60 | ~93% |
| **GPT-4o** | 0.728 (below Tier 1) | 81.0% | ~87% | $2.50 / $10.00 | ~90% |
| **GPT-4o-mini** | 0.709 (below Tier 1) | 76.5% | 82.0% | $0.15 / $0.60 | ~85% |
| **GPT-4.1-nano** | Not tested (est. below Tier 1) | 74.5% | 80.1% | $0.10 / $0.40 | ~75% (complex) / ~88% (classification) |

*Human-human Cohen's κ baseline: 0.801. Reliability = estimated agreement with GPT-4.1 as reference judge.*

**Key findings:**
- GPT-4.1-nano is designed for "classification, autocompletion, and tagging" — NOT multi-step reasoning. AIME 2024: 29.4% vs mini's 49.6%
- GPT-4o-mini falls below Tier 1 in judge quality but remains the industry standard for cost-effective evaluation
- GPT-4.1-mini matches or exceeds GPT-4o on most benchmarks at 83% lower cost
- DeepEval warns: "We CANNOT guarantee evaluations will work as expected with custom/smaller models"

### 12.2 Estimated Reliability by Model × Task Complexity

| Model | Complex (multi-step reasoning) | Medium (scoring/evaluation) | Simple (binary classification) |
|---|---|---|---|
| **GPT-4.1** | ~98% | ~99% | ~99% |
| **GPT-4.1-mini** | ~93% | ~95% | ~97% |
| **GPT-4o-mini** | ~85% | ~90% | ~93% |
| **GPT-4.1-nano** | ~70% | ~80% | ~88% |

### 12.3 Complete Metric Inventory with Execution Assignment

#### Group L — Local (deterministic/small model, always free)

| # | Metric | Framework | Execution | Local Model | Params | RAM |
|---|---|---|---|---|---|---|
| L1 | HHEM Hallucination | RAGAS `FaithfulnesswithHHEM` | Local model | `vectara/hallucination_evaluation_model` (FLAN-T5-base) | 250M | <600 MB |
| L2 | BERTScore | Opik / DeepEval `Scorer` | Local model | `roberta-large` | 355M | ~1.5 GB |
| L3 | Semantic Answer Similarity | Haystack `SASEvaluator` | Local model | `paraphrase-multilingual-mpnet-base-v2` | 278M | ~1.1 GB |
| L4 | Embeddings (for RAGAS) | RAGAS `SemanticSimilarity` | Local model | `all-MiniLM-L6-v2` | 22.7M | ~200 MB |
| L5 | Language Adherence | Opik | Local model | fastText lang-id | ~1M | ~2 MB |
| L6 | BLEU | Opik `SentenceBLEU` / RAGAS `BleuScore` | Algorithmic | None | 0 | 0 |
| L7 | ROUGE (5 variants) | Opik `ROUGE` / RAGAS `RougeScore` | Algorithmic | None | 0 | 0 |
| L8 | METEOR | Opik | Algorithmic | None (NLTK) | 0 | 0 |
| L9 | ChrF | Opik `ChrF` / RAGAS `ChrfScore` | Algorithmic | None | 0 | 0 |
| L10 | Levenshtein | Opik `LevenshteinRatio` / RAGAS `NonLLMStringSimilarity` | Algorithmic | None | 0 | 0 |
| L11 | Exact Match | DeepEval / RAGAS / Opik | Algorithmic | None | 0 | 0 |
| L12 | Sentiment | Opik `Sentiment` / `VADERSentiment` | Lexicon | VADER lexicon | ~1M | ~1 MB |
| L13 | Readability | Opik `Readability` | Algorithmic | None (textstat) | 0 | 0 |
| L14 | Tone | Opik `Tone` | Algorithmic | None | 0 | 0 |
| L15 | IsJson | Opik | Algorithmic | None | 0 | 0 |
| L16 | Contains / RegexMatch | Opik | Algorithmic | None | 0 | 0 |
| L17 | MRR | Haystack `DocumentMRREvaluator` | Algorithmic | None | 0 | 0 |
| L18 | MAP | Haystack `DocumentMAPEvaluator` | Algorithmic | None | 0 | 0 |
| L19 | NDCG | Haystack `DocumentNDCGEvaluator` | Algorithmic | None | 0 | 0 |
| L20 | Recall | Haystack `DocumentRecallEvaluator` | Algorithmic | None | 0 | 0 |
| L21 | JsonCorrectness | DeepEval `JsonCorrectnessMetric` | Algorithmic | None | 0 | 0 |
| L22 | ConversationDegeneration | Opik (heuristic) | Algorithmic | None | 0 | 0 |
| L23 | KnowledgeRetention | Opik (heuristic) | Algorithmic | None | 0 | 0 |
| L24 | PromptInjection | Opik (heuristic) | Algorithmic | None | 0 | 0 |
| L25 | Custom Entity F1 | DeepEval `BaseMetric` | Algorithmic | None | 0 | 0 |
| L26 | Custom Relation F1 | RAGAS `@numeric_metric` | Algorithmic | None | 0 | 0 |
| L27 | Consistency (CAI) | Vectara ConsistencyEvaluator | Local model | `xlm-roberta-large` (BERTScore) + ROUGE-L | 560M | ~2.5 GB |

**Group L total: 27 metrics. Cost: 0 €. Peak RAM: ~3.5 GB (if running L1+L2+L3 simultaneously, or ~1.5 GB sequential).**

#### Group A — API: Complex Reasoning (multi-step, claim decomposition, rubrics)

| # | Metric | Framework | LLM Calls/test | Task Complexity |
|---|---|---|---|---|
| A1 | Faithfulness | DeepEval `FaithfulnessMetric` | 2 (claim extraction + verification) | Complex |
| A2 | Noise Sensitivity | RAGAS `NoiseSensitivity` | 1 | Complex |
| A3 | Factual Correctness | RAGAS `FactualCorrectness` | 2 (claim decomposition + NLI) | Complex |
| A4 | ConversationalCoherence | Opik `ConversationalCoherence` | 1 | Complex |
| A5 | SessionCompleteness | Opik `SessionCompletenessQuality` | 1 | Complex |
| A6 | Pedagogical Rubric | RAGAS `RubricsScore` | 1 | Complex |
| A7 | TurnFaithfulness | DeepEval `TurnFaithfulnessMetric` | 2/test | Complex |
| A8 | Giskard RAGET | Giskard (60 questions) | ~4/question | Complex |

**Group A per 100 tests: (2+1+2+1+1+1+2) × 100 + (60×4) = 1,240 calls**
**Tokens: ~2,108,000 input / ~248,000 output**

#### Group B — API: Medium Complexity (direct scoring, evaluation)

| # | Metric | Framework | LLM Calls/test | Task Complexity |
|---|---|---|---|---|
| B1 | Answer Relevancy | DeepEval `AnswerRelevancyMetric` | 1 | Medium |
| B2 | Context Precision | RAGAS `LLMContextPrecisionWithoutReference` | 1 | Medium |
| B3 | Context Recall | RAGAS `LLMContextRecall` | 1 | Medium |
| B4 | Context Relevancy | DeepEval `ContextualRelevancyMetric` | 1 | Medium |
| B5 | Context Entities Recall | RAGAS `ContextEntityRecall` | 1 | Medium |
| B6 | TopicAdherence | RAGAS `TopicAdherence` | 1 | Medium |
| B7 | RoleAdherence | DeepEval `RoleAdherenceMetric` | 1 | Medium |
| B8 | UserFrustration | Opik `UserFrustration` | 1 | Medium |
| B9 | TurnContextualRelevancy | DeepEval `TurnContextualRelevancyMetric` | 1 | Medium |
| B10 | TurnContextualRecall | DeepEval `TurnContextualRecallMetric` | 1 | Medium |

**Group B per 100 tests: 10 × 100 = 1,000 calls**
**Tokens: ~1,700,000 input / ~200,000 output**

#### Group C — API: Simple Classification (binary/categorical)

| # | Metric | Framework | LLM Calls/test | Task Complexity |
|---|---|---|---|---|
| C1-C5 | Bias (5 judges) | Opik `DemographicBiasJudge` etc. | 5 | Simple |
| C6 | Toxicity | DeepEval `ToxicityMetric` | 1 | Simple |
| C7 | PII Leakage | DeepEval `PIILeakageMetric` | 1 | Simple |
| C8 | Misuse | DeepEval `MisuseMetric` | 1 | Simple |
| C9 | NonAdvice | DeepEval `NonAdviceMetric` | 1 | Simple |

**Group C per 100 tests: 9 × 100 = 900 calls**
**Tokens: ~1,530,000 input / ~180,000 output**

---

### 12.4 Three Optimization Profiles

#### Profile 1: ≥95% Reliability Floor

*Every LLM-judged metric achieves ≥95% agreement with GPT-4.1 gold standard.*

| Group | Judge Model | Reliability | Cost ($/MTok in/out) |
|---|---|---|---|
| **L** (local) | No LLM | 100% (deterministic) | $0 |
| **A** (complex) | **GPT-4.1** | ~98% | $2.00 / $8.00 |
| **B** (medium) | **GPT-4.1-mini** | ~95% | $0.40 / $1.60 |
| **C** (simple) | **GPT-4.1-mini** | ~97% | $0.40 / $1.60 |

*Why GPT-4.1-mini for C, not GPT-4o-mini? GPT-4o-mini reliability for classification (~93%) falls below the 95% floor.*

**Cost per full suite (100 test cases):**

| Group | Input tokens | Output tokens | Model | Input cost | Output cost | Total |
|---|---|---|---|---|---|---|
| L | — | — | Local | $0 | $0 | **$0.00** |
| A | 2,108,000 | 248,000 | GPT-4.1 | $4.22 | $1.98 | **$6.20** |
| B | 1,700,000 | 200,000 | GPT-4.1-mini | $0.68 | $0.32 | **$1.00** |
| C | 1,530,000 | 180,000 | GPT-4.1-mini | $0.61 | $0.29 | **$0.90** |
| **TOTAL** | | | | | | **$8.10 (~7.51 €)** |

| Cadence | Cost |
|---|---|
| Per full suite (100 tests) | **7.51 €** |
| Per month (1 suite/day × 30 days) | **225.30 €** |
| Per year | **~2,704 €** |

---

#### Profile 2: ≥90% Reliability Floor (Recommended)

*Every LLM-judged metric achieves ≥90% agreement with GPT-4.1 gold standard.*

| Group | Judge Model | Reliability | Cost ($/MTok in/out) |
|---|---|---|---|
| **L** (local) | No LLM | 100% (deterministic) | $0 |
| **A** (complex) | **GPT-4.1-mini** | ~93% | $0.40 / $1.60 |
| **B** (medium) | **GPT-4o-mini** | ~90% | $0.15 / $0.60 |
| **C** (simple) | **GPT-4o-mini** | ~93% | $0.15 / $0.60 |

*Why GPT-4o-mini for B and C, not GPT-4.1-nano? Nano reliability for medium tasks (~80%) and classification (~88%) both fall below the 90% floor.*

**Cost per full suite (100 test cases):**

| Group | Input tokens | Output tokens | Model | Input cost | Output cost | Total |
|---|---|---|---|---|---|---|
| L | — | — | Local | $0 | $0 | **$0.00** |
| A | 2,108,000 | 248,000 | GPT-4.1-mini | $0.84 | $0.40 | **$1.24** |
| B | 1,700,000 | 200,000 | GPT-4o-mini | $0.26 | $0.12 | **$0.38** |
| C | 1,530,000 | 180,000 | GPT-4o-mini | $0.23 | $0.11 | **$0.34** |
| **TOTAL** | | | | | | **$1.96 (~1.82 €)** |

| Cadence | Cost |
|---|---|
| Per full suite (100 tests) | **1.82 €** |
| Per month (1 suite/day × 30 days) | **54.60 €** |
| Per year | **~655 €** |

---

#### Profile 3: ≥85% Reliability Floor

*Every LLM-judged metric achieves ≥85% agreement with GPT-4.1 gold standard.*

| Group | Judge Model | Reliability | Cost ($/MTok in/out) |
|---|---|---|---|
| **L** (local) | No LLM | 100% (deterministic) | $0 |
| **A** (complex) | **GPT-4o-mini** | ~85% | $0.15 / $0.60 |
| **B** (medium) | **GPT-4o-mini** | ~90% | $0.15 / $0.60 |
| **C** (simple) | **GPT-4.1-nano** | ~88% | $0.10 / $0.40 |

*Why GPT-4o-mini for B, not nano? Nano reliability for medium tasks (~80%) falls below 85%. Only simple classification (C) can use nano safely.*

**Cost per full suite (100 test cases):**

| Group | Input tokens | Output tokens | Model | Input cost | Output cost | Total |
|---|---|---|---|---|---|---|
| L | — | — | Local | $0 | $0 | **$0.00** |
| A | 2,108,000 | 248,000 | GPT-4o-mini | $0.32 | $0.15 | **$0.47** |
| B | 1,700,000 | 200,000 | GPT-4o-mini | $0.26 | $0.12 | **$0.38** |
| C | 1,530,000 | 180,000 | GPT-4.1-nano | $0.15 | $0.07 | **$0.22** |
| **TOTAL** | | | | | | **$1.07 (~0.99 €)** |

| Cadence | Cost |
|---|---|
| Per full suite (100 tests) | **0.99 €** |
| Per month (1 suite/day × 30 days) | **29.70 €** |
| Per year | **~356 €** |

---

### 12.5 Comparison Across Profiles

| | ≥95% Reliability | ≥90% Reliability | ≥85% Reliability |
|---|---|---|---|
| **Group A judge** | GPT-4.1 | GPT-4.1-mini | GPT-4o-mini |
| **Group B judge** | GPT-4.1-mini | GPT-4o-mini | GPT-4o-mini |
| **Group C judge** | GPT-4.1-mini | GPT-4o-mini | GPT-4.1-nano |
| **Cost per suite** | **7.51 €** | **1.82 €** | **0.99 €** |
| **Cost per month** | **225.30 €** | **54.60 €** | **29.70 €** |
| **Cost per year** | **~2,704 €** | **~655 €** | **~356 €** |
| **Reliability range** | 95-98% | 90-93% | 85-90% |
| **Best for** | Production, final release validation | Daily CI/CD, recommended default | Development, rapid iteration |

### 12.6 Execution Time per Full Suite (100 test cases)

API calls can be parallelized. Local models run sequentially. Total time is `max(local_time, api_time)`.

| Step | LG Gram 2022 | MacBook Air M5 16GB |
|---|---|---|
| **Group L (local models)** | | |
| └ HHEM (250M, CPU) | ~5-8 min | ~1.5-2.5 min |
| └ BERTScore (355M, CPU) | ~5-15 min | ~1.5-3 min |
| └ SAS multilingual (278M) | ~3-8 min | ~1-2 min |
| └ Embeddings (22.7M) | ~30 seg | ~10 seg |
| └ Heuristics (BLEU, ROUGE, etc.) | <5 seg | <3 seg |
| └ IR metrics (MRR, MAP, NDCG) | <1 seg | <1 seg |
| **Group L subtotal** | **~14-31 min** | **~4-8 min** |
| **Groups A+B+C (API, 10 concurrent)** | | |
| └ 3,140 calls ÷ 10 × ~3 seg | ~16 min | ~16 min |
| **Groups A+B+C (API, 50 concurrent)** | ~3-5 min | ~3-5 min |
| **Total (sequential local + parallel API)** | **~20-35 min** | **~10-15 min** |
| **Total (all maximally parallel)** | **~16-31 min** | **~5-10 min** |

*API time is identical on both machines (network-bound). The difference is only in local model inference.*

### 12.7 Monthly Summary — Recommended Profile (≥90%)

Running 1 full suite per day (30/month) on current LG Gram:

| Component | Metric count | Execution | Time/suite | Cost/suite | Cost/month |
|---|---|---|---|---|---|
| Group L (local) | 27 metrics | Local (deterministic + small models) | ~14-31 min | 0 € | 0 € |
| Group A (complex) | 8 metrics | API (GPT-4.1-mini) | ~5 min | 1.15 € | 34.50 € |
| Group B (medium) | 10 metrics | API (GPT-4o-mini) | ~5 min | 0.35 € | 10.50 € |
| Group C (simple) | 9 metrics | API (GPT-4o-mini) | ~4 min | 0.32 € | 9.60 € |
| **TOTAL** | **54 metrics** | | **~20-35 min** | **1.82 €** | **54.60 €** |
