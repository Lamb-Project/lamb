# LLM & RAG Evaluation Frameworks — Comprehensive Analysis for LAMB

> **Date:** 2026-03-15
> **Context:** LAMB (Learning Assistants Manager and Builder) — FastAPI backend, plugin-based RAG pipeline (`simple_rag`, `context_aware_rag`, `rubric_rag`, `single_file_rag`), multi-model LLM support, Docker Compose deployment, privacy-first, educational domain.
> **Future features under evaluation:** Context-Aware RAG (enhanced multi-turn) and Knowledge Graphs (KG).

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Framework Profiles](#2-framework-profiles)
3. [Evaluation Coverage Matrix](#3-evaluation-coverage-matrix)
   - A. RAG Core Evaluation
   - B. Context-Aware RAG / Multi-Turn Evaluation
   - C. Knowledge Graph Evaluation
   - D. Safety, Bias & Educational Suitability
   - E. Traditional NLP Baselines & General Metrics
   - F. Agent / Tool Use Metrics
   - G. Observability & Pipeline Tracing
   - H. Custom Metric Flexibility
4. [Gap Analysis](#4-gap-analysis)
5. [Recommended Evaluation Stack for LAMB](#5-recommended-evaluation-stack-for-lamb)

> **See also:** [`llm_evaluation_frameworks_extended.md`](llm_evaluation_frameworks_extended.md) — covers 20+ additional frameworks, KG-specific evaluation tools (PyKEEN, GraphRAG-Bench, KGGen MINE), educational AI evaluation methodologies (EducationQ, AITutor-EvalKit, MathTutorBench), and the updated combined ranking across all tools.

---

## 1. Executive Summary

Six evaluation frameworks were analyzed for their fitness to evaluate LAMB's LLM accuracy across current RAG features, future context-aware RAG, and future Knowledge Graph integration:

| # | Framework | Primary Strength | GitHub Stars | License |
|---|-----------|-----------------|-------------|---------|
| 1 | **DeepEval** | Most metrics (~50+), best multi-turn RAG, pytest-native | ~14.1k | Apache 2.0 |
| 2 | **RAGAS** | Deepest RAG metric variants, traditional NLP, SQL | ~13k | Apache 2.0 |
| 3 | **Langfuse** | Best observability, tracing, human annotation | ~23.2k | MIT (except EE) |
| 4 | **Opik** | Best heuristic metrics (22+), conversation-specific metrics, bias judges | ~18.3k | Apache 2.0 |
| 5 | **Giskard** | Best red-teaming/adversarial (40+ probes), RAG component diagnosis | ~5.2k | Apache 2.0 |
| 6 | **Vectara Open RAG Eval** | Best reference-free evaluation, A/B RAG comparison | New (v0.3.0) | Apache 2.0 |

**Key finding:** No single framework covers all of LAMB's evaluation needs. Knowledge Graph evaluation has **zero native support** across all six frameworks and requires custom metric development. The optimal approach is a layered stack combining multiple frameworks. Extended analysis (see companion document) identified **Galileo** as the only platform with native KG validation, and specialized tools like **PyKEEN** (44 KG embedding metrics) and **KGGen MINE** for KG extraction evaluation.

---

## 2. Framework Profiles

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
- **Built-in eval metrics:** Growing catalog of managed evaluator templates (examples include Hallucination, Context-Relevance, Toxicity, Helpfulness — not limited to these four)
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

## 3. Evaluation Coverage Matrix

### Legend

| Symbol | Meaning |
|--------|---------|
| **Native** | Built-in metric, ready to use |
| **Partial** | Indirectly supported or limited coverage |
| **Custom** | No built-in metric, but custom metric API can build it |
| **Via integration** | Available through a documented external framework integration |
| **--** | Not supported, not even via custom metrics |

---

### A. RAG Core Evaluation (Current LAMB)

| Evaluation Need | DeepEval | RAGAS | Langfuse | Opik | Giskard | Vectara |
|---|---|---|---|---|---|---|
| **Faithfulness** (answer grounded in retrieved context) | **Native** — `FaithfulnessMetric`: truthful claims / total claims | **Native** — `Faithfulness` + `FaithfulnesswithHHEM` (free T5 variant) | **Native** — managed evaluator template + RAGAS integration | **Native** — `Hallucination` metric (binary: 0=faithful, 1=hallucinated) | **Partial** — `Groundedness` check (Hub); RAGAS `ragas_faithfulness` wrapper (OSS) | **Native** — HHEM hallucination model (FLAN-T5-based, 0-1 score) |
| **Answer Relevancy** (response addresses the question) | **Native** — `AnswerRelevancyMetric`: relevant statements / total | **Native** — `ResponseRelevancy`: reverse-generated questions + cosine similarity | **Via integration** — RAGAS integration or LLM-as-Judge template | **Native** — `AnswerRelevance` (0-1, LLM judge) | **Partial** — RAGAS wrapper `ragas_answer_relevancy` | **--** |
| **Context Precision** (relevant chunks ranked higher) | **Native** — `ContextualPrecisionMetric`: weighted cumulative precision. Requires `expected_output` | **Native** — 4 core variants + 2 convenience aliases: LLM w/ref, LLM w/o ref, NonLLMWithReference, ID-based | **Via integration** — RAGAS integration | **Native** — `ContextPrecision` (LLM judge) | **Partial** — RAGAS wrapper `ragas_context_precision` | **Partial** — UMBRELA scores per-passage relevance (0-3), ranking derivable |
| **Context Recall** (all needed info retrieved) | **Native** — `ContextualRecallMetric`: attributable statements / total | **Native** — 3 core variants + 1 convenience alias: LLM, NonLLM, ID-based | **Via integration** — RAGAS integration | **Native** — `ContextRecall` (LLM judge) | **Partial** — RAGAS wrapper `ragas_context_recall` | **Partial** — AutoNuggetizer vital score measures completeness |
| **Context Relevancy** (retrieved chunks relevant to query) | **Native** — `ContextualRelevancyMetric`: relevant statements / total | **Partial** — NVIDIA `ContextRelevance` metric (not a core RAGAS metric) | **Custom** — via LLM-as-Judge template | **--** | **--** | **Native** — UMBRELA (0-3 relevance per passage) |
| **Hallucination Detection** (fabricated info not in context) | **Native** — `HallucinationMetric` (uses `context`, not `retrieval_context`): contradicted contexts / total | **Native** — via Faithfulness (inverse); FaithfulnesswithHHEM | **Native** — managed evaluator "Hallucination" template | **Native** — `Hallucination` (binary LLM judge) | **Native** — Sycophancy detector + RAGET hallucination questions + Hub probes (4) | **Native** — HHEM model (deterministic) |
| **Noise Sensitivity** (errors from irrelevant context) | **--** | **Native** — `NoiseSensitivity` with relevant/irrelevant modes | **Custom** — via LLM-as-Judge | **--** | **Partial** — RAGET "Distracting" questions test this indirectly | **--** |
| **Context Entities Recall** (entity overlap in retrieval) | **--** | **Native** — `ContextEntityRecall`: entity set intersection | **Custom** — via RAGAS integration | **--** | **--** | **--** |
| **Factual Correctness** (accuracy vs reference) | **Custom** — via G-Eval | **Native** — `FactualCorrectness`: claim decomposition + NLI, P/R/F1 modes | **Custom** — via RAGAS integration or LLM-as-Judge | **--** | **Native** — `Correctness` check (Hub, LLM-as-judge vs reference) | **Native** — `FactualCorrectnessF1` in GoldenAnswerEvaluator |
| **Semantic Similarity** (embedding-based comparison) | **Custom** — via `Scorer.bert_score()` in custom metric | **Native** — `SemanticSimilarity`: cosine over embeddings | **Custom** — via external scorer | **Native** — `BERTScore` + `MeaningMatch` | **Native** — Hub `SemanticSimilarity` check | **Native** — embedding cosine in GoldenAnswerEvaluator |
| **RAG strategy A/B comparison** | **Native** — `pytest.mark.parametrize` across strategies | **Native** — run `evaluate()` per strategy, compare DataFrames | **Native** — Experiments feature with side-by-side comparison | **Native** — Experiment comparison in UI | **Partial** — RAGET runs per pipeline, manual comparison | **Native** — core use case; YAML config + Streamlit + openevaluation.ai |

---

### B. Context-Aware RAG / Multi-Turn Evaluation (Future LAMB)

| Evaluation Need | DeepEval | RAGAS | Langfuse | Opik | Giskard | Vectara |
|---|---|---|---|---|---|---|
| **Multi-turn conversation coherence** | **Native** — `TurnRelevancyMetric` (sliding window) | **Partial** — `AspectCritic` with custom coherence definition on `MultiTurnSample` | **Partial** — N+1 methodology + LLM-as-Judge with custom rubric | **Native** — `ConversationalCoherence` (sliding window, LLM judge) | **Partial** — RAGET "Conversational" question type tests context preservation | **--** |
| **Query rewriting quality** | **Custom** — via G-Eval with custom criteria | **Custom** — via `AspectCritic` or `DiscreteMetric` | **Custom** — via LLM-as-Judge evaluator | **Custom** — via G-Eval with custom criteria | **Partial** — RAGET tests Rewriter component indirectly via "Double"/"Conversational" questions | **--** |
| **Knowledge retention across turns** | **Native** — `KnowledgeRetentionMetric`: turns without knowledge attrition / total | **--** | **Custom** — via LLM-as-Judge | **Native** — `KnowledgeRetention` heuristic metric (no LLM needed) | **--** | **--** |
| **Session-level completeness** (all user intents addressed) | **Native** — `ConversationCompletenessMetric`: satisfied intentions / total | **Partial** — `AgentGoalAccuracy` evaluates goal achievement | **Partial** — session-level scoring + annotation queues | **Native** — `SessionCompletenessQuality` (extracts + evaluates all user intentions) | **--** | **--** |
| **Turn-level faithfulness** (per-turn grounding) | **Native** — `TurnFaithfulnessMetric`: averaged per-turn faithfulness | **--** | **Partial** — observation-level scoring on per-turn spans | **--** | **--** | **--** |
| **Turn-level context relevancy** | **Native** — `TurnContextualRelevancyMetric`: averaged per-turn | **--** | **Partial** — observation-level scoring | **--** | **--** | **--** |
| **Turn-level context recall** | **Native** — `TurnContextualRecallMetric`: averaged per-turn | **--** | **Partial** — observation-level scoring | **--** | **--** | **--** |
| **Turn-level context precision** | **Native** — `TurnContextualPrecisionMetric` | **--** | **Partial** — observation-level scoring | **--** | **--** | **--** |
| **Role/persona adherence** (assistant stays in character) | **Native** — `RoleAdherenceMetric` (multi-turn) + `RoleViolationMetric` (single-turn) | **Custom** — via `AspectCritic` | **Custom** — via LLM-as-Judge | **--** | **--** | **--** |
| **User frustration detection** | **--** | **--** | **Custom** — via LLM-as-Judge | **Native** — `UserFrustration` (LLM judge on full session) | **--** | **--** |
| **Conversation degeneration** (repetitive/low-entropy) | **--** | **--** | **--** | **Native** — `ConversationDegeneration` heuristic (no LLM) | **--** | **--** |
| **Topic adherence** (stays within allowed domains) | **Custom** — via G-Eval | **Native** — `TopicAdherence`: P/R/F1 modes against allowed topic list | **Custom** — via LLM-as-Judge | **--** | **--** | **--** |

---

### C. Knowledge Graph Evaluation (Future LAMB)

| Evaluation Need | DeepEval | RAGAS | Langfuse | Opik | Giskard | Vectara |
|---|---|---|---|---|---|---|
| **Entity extraction accuracy** (NER P/R/F1) | **Custom** — G-Eval with entity criteria or `BaseMetric` subclass for deterministic F1 | **Custom** — `@numeric_metric` decorator for deterministic F1 | **Custom** — push external scores via SDK | **Custom** — `BaseMetric` subclass | **--** | **--** |
| **Relation extraction accuracy** (relation P/R/F1) | **Custom** — G-Eval or `BaseMetric` subclass | **Custom** — `@numeric_metric` decorator | **Custom** — push external scores via SDK | **Custom** — `BaseMetric` subclass | **--** | **--** |
| **Graph completeness** (KG covers all relevant knowledge) | **Custom** — G-Eval | **Custom** — custom metric | **Custom** — push external scores via SDK | **Custom** — `BaseMetric` | **--** | **--** |
| **Graph traversal quality** (correct path through KG) | **Custom** — DAG metric with decision tree nodes | **Custom** — custom metric | **Custom** — push external scores via SDK | **Custom** — `BaseMetric` | **--** | **--** |
| **Triple/fact accuracy** (KG triples are correct) | **Custom** — G-Eval | **Partial** — `FactualCorrectness` on linearized triples | **Custom** — push external scores via SDK | **Custom** — `BaseMetric` | **--** | **--** |
| **KG-grounded faithfulness** (answer supported by graph triples) | **Partial** — Faithfulness works if graph context passed as `retrieval_context` | **Partial** — Faithfulness works if graph context serialized as text | **Partial** — LLM-as-Judge on graph-retrieved text | **Partial** — Hallucination metric on graph-retrieved text | **--** | **Partial** — HHEM on graph-retrieved text |
| **Hybrid retrieval quality** (KG + vector fusion) | **Partial** — RAG metrics evaluate final `retrieval_context` regardless of source | **Partial** — RAG metrics evaluate final context, agnostic to source | **Partial** — trace and score each retrieval source separately | **Partial** — RAG metrics on combined context | **--** | **Partial** — UMBRELA on combined passages |
| **Structured-unstructured fusion** | **Custom** — G-Eval with fusion criteria | **Custom** — custom metric | **Custom** — LLM-as-Judge | **Custom** — G-Eval | **--** | **--** |
| **Ontology alignment** | **Custom** — G-Eval | **Custom** — custom metric | **Custom** — push scores via SDK | **Custom** — `BaseMetric` | **--** | **--** |

---

### D. Safety, Bias & Educational Suitability

| Evaluation Need | DeepEval | RAGAS | Langfuse | Opik | Giskard | Vectara |
|---|---|---|---|---|---|---|
| **Bias detection** (gender, racial, political) | **Native** — `BiasMetric`: biased opinions / total | **Custom** — via `AspectCritic` with bias definition | **Custom** — via LLM-as-Judge | **Native** — 5 bias judges (Demographic, Gender, Political, Religious, Regional) | **Native** — `StereotypesDetector` + `EthicalBiasDetector` | **--** |
| **Toxicity detection** | **Native** — `ToxicityMetric`: toxic opinions / total | **Custom** — via `AspectCritic` | **Native** — managed "Toxicity" template | **Native** — `Moderation` (10 safety categories) | **Native** — `HarmfulContentDetector` (17 probes in Hub) | **--** |
| **PII leakage** | **Native** — `PIILeakageMetric`: detects names, SSN, credit cards, etc. | **--** | **Custom** — via LLM-as-Judge | **Partial** — via `Moderation` PII category | **Native** — `InformationDisclosureDetector` + PII Leak probe | **--** |
| **Prompt injection resistance** | **Native** — via DeepTeam (40+ vulnerability scanners) | **--** | **--** | **Native** — `PromptInjection` heuristic metric | **Native** — `PromptInjectionDetector` (12 attack probes in Hub) | **--** |
| **Misuse detection** (off-topic queries) | **Native** — `MisuseMetric`: flags out-of-domain responses | **Partial** — `TopicAdherence` checks domain boundaries | **Custom** — via LLM-as-Judge | **--** | **Partial** — RAGET "Out of Scope" questions test router | **--** |
| **Inappropriate advice prevention** | **Native** — `NonAdviceMetric`: flags professional advice by type | **Custom** — via `AspectCritic` | **Custom** — via LLM-as-Judge | **Partial** — `ComplianceRiskJudge` (G-Eval preset) | **Native** — `UnauthorizedAdvice` probe (Hub) | **--** |
| **Educational rubric adherence** | **Custom** — G-Eval or DAG with pedagogical criteria | **Native** — `RubricsScore` (1-5 scale, with/without reference) | **Custom** — LLM-as-Judge with rubric prompt | **Custom** — G-Eval with rubric criteria | **Custom** — custom metric | **--** |
| **Red-teaming / adversarial testing** | **Native** — DeepTeam: 40+ OWASP LLM Top 10 scanners | **--** | **--** | **--** | **Native** — 40+ probes, 11 categories, multi-turn attacks (GOAT, Crescendo, TAP) | **--** |
| **Sycophancy detection** | **--** | **--** | **--** | **--** | **Native** — `SycophancyDetector` | **--** |

---

### E. Traditional NLP Baselines & General Metrics

| Evaluation Need | DeepEval | RAGAS | Langfuse | Opik | Giskard | Vectara |
|---|---|---|---|---|---|---|
| **BLEU** | **Partial** — `Scorer.bleu_score()` utility (not standalone metric) | **Native** — `BleuScore` | **--** | **Native** — `SentenceBLEU` + `CorpusBLEU` | **--** | **--** |
| **ROUGE** | **Partial** — `Scorer.rouge_score()` utility | **Native** — `RougeScore` (rouge1, rougeL; P/R/F) | **--** | **Native** — `ROUGE` (rouge1, rouge2, rougeL, rougeLsum, rougeW) | **--** | **Partial** — ROUGE-L in ConsistencyEvaluator only |
| **BERTScore** | **Partial** — `Scorer.bert_score()` utility | **--** (uses `SemanticSimilarity` instead) | **--** | **Native** — `BERTScore` (precision, recall, F1) | **--** | **Partial** — in ConsistencyEvaluator (xlm-roberta-large) |
| **METEOR** | **--** | **--** | **--** | **Native** — `METEOR` | **--** | **--** |
| **ChrF** | **--** | **Native** — `ChrfScore` | **--** | **Native** — `ChrF` + `ChrF++` | **--** | **--** |
| **Exact Match** | **Native** — `ExactMatchMetric` | **Native** — `ExactMatch` | **--** | **Native** — `Equals` | **--** | **--** |
| **Levenshtein / String Similarity** | **--** | **Native** — `NonLLMStringSimilarity` (Levenshtein, Hamming, Jaro, Jaro-Winkler) | **--** | **Native** — `LevenshteinRatio` | **--** | **--** |
| **Summarization quality** | **Native** — `SummarizationMetric` (min of alignment, coverage) | **Native** — `SummaryScore` (QA + conciseness) | **Custom** — via LLM-as-Judge | **Partial** — `SummarizationConsistencyJudge` + `SummarizationCoherenceJudge` | **--** | **--** |
| **Readability** | **--** | **--** | **--** | **Native** — `Readability` (Flesch Reading Ease + Flesch-Kincaid) | **--** | **--** |
| **Sentiment** | **--** | **--** | **--** | **Native** — `Sentiment` (VADER) + `VADERSentiment` | **--** | **--** |
| **Language adherence** | **--** | **--** | **--** | **Native** — `LanguageAdherence` (ISO code matching via fasttext) | **--** | **--** |
| **JSON schema validation** | **Native** — `JsonCorrectnessMetric` (deterministic) | **--** | **Partial** — runtime validation patterns | **Native** — `IsJson` + `StructuredOutputCompliance` (G-Eval) | **Partial** — Hub `Metadata` check on JSON paths | **--** |
| **Response consistency** (across multiple runs) | **--** | **--** | **--** | **--** | **--** | **Native** — CAI = mean / (1 + std_dev) via BERTScore + ROUGE-L |
| **Citation accuracy** | **--** | **--** | **--** | **--** | **--** | **Native** — Citation Score (Full=1.0, Partial=0.5, No=0.0) |

---

### F. Agent / Tool Use Metrics

| Evaluation Need | DeepEval | RAGAS | Langfuse | Opik | Giskard | Vectara |
|---|---|---|---|---|---|---|
| **Tool call accuracy** | **Native** — `ToolCorrectnessMetric` + `ArgumentCorrectnessMetric` | **Native** — `ToolCallAccuracy` (sequence + argument correctness) | **Custom** — via LLM-as-Judge on tool spans | **Native** — `AgentToolCorrectnessJudge` + `TrajectoryAccuracy` | **Partial** — Hub function calling probes test misuse, not accuracy | **--** |
| **Task completion** | **Native** — `TaskCompletionMetric` (trace-based) | **Native** — `AgentGoalAccuracy` (with/without reference) | **Custom** — via LLM-as-Judge | **Native** — `AgentTaskCompletionJudge` | **--** | **--** |
| **Step efficiency** | **Native** — `StepEfficiencyMetric` (penalizes unnecessary steps) | **--** | **--** | **--** | **--** | **--** |
| **Plan quality** | **Native** — `PlanQualityMetric` + `PlanAdherenceMetric` | **--** | **--** | **--** | **--** | **--** |
| **Tool call F1** | **--** | **Native** — `ToolCallF1` (unordered matching) | **--** | **--** | **--** | **--** |

---

### G. Observability & Pipeline Tracing

| Capability | DeepEval | RAGAS | Langfuse | Opik | Giskard | Vectara |
|---|---|---|---|---|---|---|
| **Multi-step pipeline tracing** | **Native** — `@observe` decorator (spans, LLM calls, retrievers) | **Partial** — integrations with Phoenix/LangSmith for evaluator tracing | **Native** — full OpenTelemetry tracing (spans, generations, events) | **Native** — `@track` decorator, hierarchical spans, distributed tracing | **--** | **--** |
| **Per-span/observation scoring** | **Partial** — via trace-based agentic metrics | **--** | **Native** — scores attach to individual observations | **Native** — span-level metrics | **--** | **--** |
| **Session grouping** | **--** | **--** | **Native** — `sessionId` grouping with replay | **Native** — Threads with auto-close | **--** | **--** |
| **Cost & latency tracking** | **--** | **--** | **Native** — per-model cost dashboards | **Native** — per-request cost tracking | **--** | **--** |
| **Human annotation workflows** | **--** | **--** | **Native** — annotation queues with reviewer assignment | **--** | **Native** — Hub annotation interface | **--** |
| **Production monitoring** | **Partial** — Confident AI cloud dashboard | **--** | **Native** — real-time dashboards | **Native** — scales to 40M+ traces/day | **Partial** — Hub continuous scanning | **--** |

---

### H. Custom Metric Flexibility

| Capability | DeepEval | RAGAS | Langfuse | Opik | Giskard | Vectara |
|---|---|---|---|---|---|---|
| **Custom metric API** | `BaseMetric` subclass, G-Eval (natural language), DAG (decision trees), ConversationalGEval, ConversationalDAG, Arena G-Eval (comparative) | `@discrete_metric`, `@numeric_metric`, `@ranking_metric` decorators + base classes (`MetricWithLLM`, `MultiTurnMetric`) | Custom eval functions → push scores via `create_score()` SDK/API | `BaseMetric` subclass + G-Eval (CoT + log-prob weighted) | `Metric` base class + `@test` decorator | Custom evaluator classes (sparse docs) |
| **Flexibility rating** | Very High | Very High | High (framework-agnostic) | Very High | Moderate | Low |

---

## 4. Gap Analysis

### 4.1 Critical Gaps — Zero Native Support Across All 6 Frameworks

| Gap | Impact for LAMB | Best Mitigation Path |
|---|---|---|
| **KG entity extraction P/R/F1** | Cannot evaluate NER accuracy for KG construction | Build deterministic custom metric in DeepEval (`BaseMetric`) or RAGAS (`@numeric_metric`) |
| **KG relation extraction P/R/F1** | Cannot evaluate relationship extraction quality | Build deterministic custom metric comparing extracted triples against gold-standard |
| **Graph completeness scoring** | Cannot evaluate whether KG captures all domain knowledge | Build custom metric; compare graph node/edge coverage against reference corpus |
| **Graph traversal quality** | Cannot evaluate whether system follows optimal KG paths | Build custom metric using DeepEval DAG for step-by-step traversal evaluation |
| **Ontology alignment** | Cannot evaluate KG structure conformance to domain ontology | Build custom metric; structural comparison against reference ontology |
| **Structured-unstructured fusion quality** | Cannot evaluate how well graph facts and free-text context integrate | Build custom LLM-as-Judge metric (G-Eval) with fusion-specific criteria |

### 4.2 Partial Gaps — Some Coverage But Incomplete

| Gap | Best Available Coverage | What's Missing |
|---|---|---|
| **Query rewriting quality** | Giskard RAGET tests Rewriter indirectly; all frameworks support custom G-Eval judges | No framework directly measures semantic preservation, intent alignment, or expansion quality |
| **Hybrid retrieval evaluation** | All RAG metrics work on combined context | No metric evaluates whether KG results and vector results were optimally combined or weighted |
| **KG-grounded faithfulness** | DeepEval/RAGAS Faithfulness works if graph context is serialized to text | No framework natively understands triples or structured graph context |
| **Multi-turn + RAG combined** | DeepEval has Turn-level RAG metrics; Opik has conversation metrics | Only DeepEval combines per-turn RAG evaluation with conversation-level metrics in one framework |

### 4.3 Framework Strength Summary

| Framework | Strongest For | Weakest For |
|---|---|---|
| **DeepEval** | Most metrics overall (50+), best multi-turn RAG (Turn* metrics), best custom flexibility (G-Eval + DAG), strong safety (DeepTeam) | Traditional NLP only as utilities, not standalone |
| **RAGAS** | Most RAG metric variants (6 context precision classes), best traditional NLP coverage, SQL metrics, flexible custom decorators | Weakest multi-turn (only via AspectCritic), no safety/bias metrics |
| **Langfuse** | Best observability + tracing, best human annotation, best production monitoring, framework-agnostic score ingestion | Fewest built-in eval metrics (relies on external frameworks) |
| **Opik** | Best heuristic metrics (22+), best conversation-specific metrics (degeneration, frustration), best bias detection (5 dedicated judges) | No noise sensitivity, no context entities recall, no turn-level RAG metrics |
| **Giskard** | Best adversarial testing (40+ probes), best RAG component diagnosis (RAGET 5 components), strongest prompt injection testing | No traditional NLP, no standalone retrieval IR metrics, limited multi-turn |
| **Vectara** | Best reference-free evaluation (UMBRELA + AutoNuggetizer), best A/B comparison UX, best consistency measurement | Single-turn only, fewest metrics overall, no safety/bias, no KG |

---

## 5. Recommended Evaluation Stack for LAMB

For every evaluation need identified across LAMB's current and future features, this section specifies the **exact framework(s), metric(s), and implementation approach**.

---

### 5.1 RAG Core Evaluation (Current)

| Evaluation Need | Primary Framework | Metric(s) | Compatibility | Implementation Sketch |
|---|---|---|---|---|
| **Faithfulness** | **DeepEval** | `FaithfulnessMetric(threshold=0.7)` | Native | `LLMTestCase(input=q, actual_output=a, retrieval_context=ctx)` → `assert_test(tc, [metric])`. Run via `pytest`. |
| **Faithfulness (free, no API)** | **RAGAS** | `FaithfulnesswithHHEM` | Native | Uses Vectara's open-source T5 model locally. `pip install ragas`, load `FaithfulnesswithHHEM`, score with `ascore()`. Zero API cost. |
| **Answer Relevancy** | **DeepEval** | `AnswerRelevancyMetric(threshold=0.7)` | Native | Same pytest pattern. Only needs `input` + `actual_output`. |
| **Context Precision** | **RAGAS** | `LLMContextPrecisionWithoutReference` | Native | Use the without-reference variant to avoid needing gold answers: `scorer.ascore(user_input=q, response=a, retrieved_contexts=ctx)`. |
| **Context Recall** | **RAGAS** | `LLMContextRecall` | Native | Requires `reference` (gold answer): `scorer.ascore(user_input=q, retrieved_contexts=ctx, reference=gold)`. Build a small gold-standard dataset per course. |
| **Context Relevancy** | **DeepEval** | `ContextualRelevancyMetric(threshold=0.6)` | Native | Measures what fraction of retrieved statements are relevant. Needs `input`, `actual_output`, `retrieval_context`. |
| **Hallucination Detection** | **Vectara** | HHEM (TRECEvaluator) | Native | Reference-free, deterministic, fast. Configure in YAML with `hallucination_metric.backend_type: "hhem"`. Use as always-on baseline. |
| **Noise Sensitivity** | **RAGAS** | `NoiseSensitivity(mode="relevant")` | Native | Only RAGAS has this. Measures errors from irrelevant context. Needs `user_input`, `response`, `reference`, `retrieved_contexts`. |
| **Context Entities Recall** | **RAGAS** | `ContextEntityRecall` | Native | Only RAGAS has this. LLM extracts entities from `reference` and `retrieved_contexts`, computes intersection recall. |
| **Factual Correctness** | **RAGAS** | `FactualCorrectness(mode="f1")` | Native | Claim decomposition + NLI. Needs `response` + `reference`. Supports precision/recall/F1 modes. |
| **RAG strategy comparison** | **Vectara** | TRECEvaluator via CSV | Native | Export results from each LAMB RAG strategy to CSV. Create YAML config per strategy. Run `open-rag-eval eval --config strategy_X.yaml`. Compare via `open-rag-eval plot` or openevaluation.ai. |

---

### 5.2 Context-Aware RAG / Multi-Turn (Future)

| Evaluation Need | Primary Framework | Metric(s) | Compatibility | Implementation Sketch |
|---|---|---|---|---|
| **Multi-turn coherence** | **Opik** | `ConversationalCoherence(model="gpt-4o", window_size=8)` | Native | Use `evaluate_threads(project_name=..., metrics=[ConversationalCoherence()])`. Threads are auto-reconstructed from traces sharing a `thread_id`. |
| **Turn-level faithfulness** | **DeepEval** | `TurnFaithfulnessMetric(threshold=0.7)` | Native | Create `ConversationalTestCase(turns=[...])` where each turn has `retrieval_context`. Metric averages per-turn faithfulness. |
| **Turn-level context relevancy** | **DeepEval** | `TurnContextualRelevancyMetric(threshold=0.6)` | Native | Same `ConversationalTestCase` pattern. Each turn needs `retrieval_context`. |
| **Turn-level context recall** | **DeepEval** | `TurnContextualRecallMetric(threshold=0.6)` | Native | Each turn needs `retrieval_context` + `expected_output`. |
| **Turn-level context precision** | **DeepEval** | `TurnContextualPrecisionMetric` | Native | Each turn needs `retrieval_context` + `expected_output`. |
| **Knowledge retention** | **DeepEval** + **Opik** | DeepEval `KnowledgeRetentionMetric` (LLM) or Opik `KnowledgeRetention` (heuristic, no LLM) | Native (both) | DeepEval: `ConversationalTestCase(turns=[...])` → metric checks each turn for knowledge attrition. Opik: heuristic variant requires no LLM calls — faster for CI. |
| **Session completeness** | **Opik** | `SessionCompletenessQuality(model="gpt-4o")` | Native | Extracts user intentions from full conversation, evaluates whether each was addressed. Use via `evaluate_threads()`. |
| **Query rewriting quality** | **Opik** | `GEval(task_introduction="...", evaluation_criteria="...")` | Custom (G-Eval) | Define criteria: "Does the rewrite preserve intent? Is it more specific for retrieval? Does it avoid introducing assumptions?" Pass `output="ORIGINAL: {q}\nREWRITTEN: {rq}"`. Score 0-1. |
| **Role/persona adherence** | **DeepEval** | `RoleAdherenceMetric(chatbot_role="educational learning assistant")` | Native | `ConversationalTestCase(turns=[...])` → metric checks each assistant turn against the defined role. |
| **User frustration** | **Opik** | `UserFrustration(model="gpt-4o")` | Native | LLM judge evaluates entire session for confusion, annoyance, disengagement signals. Use via `evaluate_threads()`. |
| **Conversation degeneration** | **Opik** | `ConversationDegeneration()` | Native | Heuristic (no LLM): detects repetitive phrases, low variance, low-entropy responses across turns. Fast, deterministic. |
| **Topic adherence** | **RAGAS** | `TopicAdherence(mode="f1", reference_topics=["course material", "assignments", ...])` | Native | Evaluates whether AI stays within predefined topic domains. Supports precision, recall, and F1 modes against an allowed topic list. |

---

### 5.3 Knowledge Graph Evaluation (Future)

| Evaluation Need | Primary Framework | Metric(s) | Compatibility | Implementation Sketch |
|---|---|---|---|---|
| **Entity extraction P/R/F1** | **DeepEval** | Custom `BaseMetric` subclass | Custom (deterministic) | Subclass `BaseMetric`. In `measure()`: parse `actual_output` (extracted entities as JSON) and `expected_output` (gold entities). Compute set intersection for TP, differences for FP/FN. Return F1. No LLM needed. |
| **Relation extraction P/R/F1** | **RAGAS** | Custom `@numeric_metric` | Custom (deterministic) | `@numeric_metric(name="relation_f1", allowed_values=(0,1))` decorator. Parse predicted and gold triples as `set(tuple(t))`, compute precision/recall/F1 via set intersection. |
| **Graph completeness** | **DeepEval** | Custom G-Eval | Custom (LLM-as-Judge) | `GEval(name="graph_completeness", criteria="Given the source documents in 'input' and the KG summary in 'actual_output', what fraction of key concepts and relationships are captured?", evaluation_params=[INPUT, ACTUAL_OUTPUT])`. |
| **Graph traversal quality** | **DeepEval** | Custom DAG metric | Custom (LLM-as-Judge) | Define `DAGMetric` with nodes: (1) `TaskNode` to extract traversal path from output, (2) `BinaryJudgementNode` to check if path reaches target entity, (3) `NonBinaryJudgementNode` to rate path optimality (shortest, relevant intermediate nodes). |
| **Triple/fact accuracy** | **RAGAS** | `FactualCorrectness` on linearized triples | Partial (workaround) | Convert triples to sentences: `f"{s} {p} {o}"`. Pass as `response` and `reference` to `FactualCorrectness(mode="f1")`. Claim decomposition maps naturally to individual triples. |
| **KG-grounded faithfulness** | **DeepEval** | `FaithfulnessMetric` with serialized graph context | Partial (workaround) | Serialize relevant KG triples as text: `"Marie Curie discovered radium. Radium is a chemical element."`. Pass as `retrieval_context`. Standard Faithfulness metric evaluates grounding. |
| **Hybrid retrieval quality** | **Langfuse** + **DeepEval** | Separate span scores + combined context evaluation | Partial (composition) | Langfuse: trace KG retrieval and vector retrieval as separate spans, score each with DeepEval's `ContextualRelevancyMetric`. Then score the combined context. Compare span-level vs combined scores to evaluate fusion strategy. Push all scores to Langfuse via `create_score()`. |
| **Structured-unstructured fusion** | **DeepEval** | Custom G-Eval | Custom (LLM-as-Judge) | `GEval(name="fusion_quality", criteria="Does the response naturally integrate structured facts (from KG) with narrative context (from documents)? Are graph-derived facts seamlessly woven into the answer without awkward transitions?")`. |
| **Ontology alignment** | **DeepEval** | Custom `BaseMetric` | Custom (deterministic) | Subclass `BaseMetric`. Compare extracted KG schema (node types, edge types) against reference ontology. Compute Jaccard similarity on type sets + structural similarity on allowed relationships. |
| **Entity retrieval overlap** | **RAGAS** | `ContextEntityRecall` | Native | Directly applicable: `reference` = gold answer with expected entities, `retrieved_contexts` = KG-retrieved passages. LLM extracts entities from both and computes recall. |

---

### 5.4 Safety, Bias & Educational Suitability

| Evaluation Need | Primary Framework | Metric(s) | Compatibility | Implementation Sketch |
|---|---|---|---|---|
| **Bias detection** | **Opik** | `DemographicBiasJudge()`, `GenderBiasJudge()`, `PoliticalBiasJudge()`, `ReligiousBiasJudge()`, `RegionalBiasJudge()` | Native | Run all 5 judges on assistant outputs. Each returns 0-1 score. Use in `opik.evaluation.evaluate()` with a dataset of diverse prompts. For CI: assert all scores < 0.1. |
| **Toxicity detection** | **DeepEval** | `ToxicityMetric(threshold=0.05)` | Native | Evaluates personal attacks, mockery, hate, dismissive statements, threats. Low threshold for educational context. Run on every completion in CI. |
| **PII leakage** | **DeepEval** | `PIILeakageMetric(threshold=0.0)` | Native | Zero tolerance for PII in educational responses. Detects names, SSN, credit cards, medical info, government IDs. |
| **Prompt injection resistance** | **Giskard** | `scan(model, only=["prompt_injection"])` | Native | Wrap LAMB endpoint in Giskard `Model(model_fn, model_type="text_generation")`. Run scan with 12 attack probes (DAN, encoding, framing, etc.). Generate test suite from results. |
| **Comprehensive adversarial testing** | **Giskard Hub** | Full scan — 40+ probes, 11 categories | Native | Run Hub scanner against LAMB endpoint. Tests: harmful content (17 probes), prompt injection (12), excessive agency (6), data privacy (4), hallucination (4), DoS (2), info exposure (2), brand damage (2), misguidance (2), training data extraction (1), legal risk (1). Multi-turn attacks via GOAT, Crescendo, TAP. |
| **Misuse detection** (off-topic) | **DeepEval** | `MisuseMetric(domain="educational learning assistance for university courses")` | Native | Flags responses outside the defined domain. Use with prompts designed to elicit off-topic responses. |
| **Inappropriate advice prevention** | **DeepEval** | `NonAdviceMetric(advice_types=["medical", "legal", "financial"])` | Native | Ensures the educational assistant doesn't provide professional advice. |
| **Educational rubric adherence** | **RAGAS** | `RubricsScore(rubrics={1: "Incorrect or misleading", 2: "Partially correct", 3: "Correct but incomplete", 4: "Correct and well-explained", 5: "Excellent pedagogical quality"})` | Native | Define rubric matching your educational standards. Score per response. Aggregate to track quality over time. |
| **Sycophancy detection** | **Giskard** | `SycophancyDetector` | Native | Detects tendency to agree with user bias rather than providing accurate information. Critical for educational context where students may have misconceptions. |
| **Role violation** | **DeepEval** | `RoleViolationMetric(role="A helpful educational assistant that explains concepts clearly, stays on topic, and never provides harmful content")` | Native | Binary (1.0 = no violation, 0.0 = violation). Single-turn check per response. |

---

### 5.5 Traditional NLP Baselines

| Evaluation Need | Primary Framework | Metric(s) | Compatibility | Implementation Sketch |
|---|---|---|---|---|
| **BLEU** | **Opik** | `SentenceBLEU()` or `CorpusBLEU()` | Native | Use for regression testing: establish baseline BLEU on gold QA pairs, assert new model versions don't regress. `opik.evaluation.evaluate(dataset, task_fn, [SentenceBLEU()])`. |
| **ROUGE** | **Opik** | `ROUGE(rouge_type="rougeL")` | Native | Best for summarization quality in educational responses. Opik has the most ROUGE variants (rouge1, rouge2, rougeL, rougeLsum, rougeW). |
| **BERTScore** | **Opik** | `BERTScore()` | Native | Semantic similarity via contextual embeddings. Better than BLEU/ROUGE for open-ended educational responses. Returns precision, recall, F1. |
| **METEOR** | **Opik** | `METEOR()` | Native | Only Opik has METEOR as a standalone metric. Accounts for synonyms and stemming — better than BLEU for educational text. |
| **ChrF** | **RAGAS** or **Opik** | RAGAS `ChrfScore()` or Opik `ChrF()` | Native (both) | Character n-gram F-score. Better for multilingual evaluation (LAMB supports en, es, ca, eu). |
| **String similarity** | **RAGAS** | `NonLLMStringSimilarity(distance_measure="levenshtein")` | Native | Supports Levenshtein, Hamming, Jaro, Jaro-Winkler. Use for exact answer verification in structured QA. |
| **Readability** | **Opik** | `Readability()` | Native | Flesch Reading Ease + Flesch-Kincaid grade level. Verify responses match target student reading level. Only Opik provides this. |
| **Language detection** | **Opik** | `LanguageAdherence(expected_language="en")` | Native | Verify LAMB responds in the correct locale (en/es/ca/eu). Uses fasttext for detection. |
| **Response consistency** | **Vectara** | ConsistencyEvaluator (CAI) | Native | Submit same query 3-5 times, measure CAI = mean/(1+std_dev). Catches non-deterministic behavior across RAG strategies. |

---

### 5.6 Observability & Pipeline Tracing

| Evaluation Need | Primary Framework | Approach | Compatibility | Implementation Sketch |
|---|---|---|---|---|
| **Multi-step pipeline tracing** | **Langfuse** | `@observe` decorator on each pipeline step | Native | Decorate LAMB's completion pipeline functions: connector selection, RAG processing (`before_completion`, `run_completion`, `after_completion`), LLM call. Each creates a nested span. Trace visualized in Langfuse UI. |
| **KG+RAG pipeline tracing** (future) | **Langfuse** | `@observe` on entity extraction, graph query, context fusion, generation | Native | Four spans: `entity-extraction` → `graph-query` → `context-fusion` → `llm-generation`. Each captures inputs/outputs/timing. Score each span independently via observation-level scoring. |
| **Per-span evaluation scoring** | **Langfuse** | `create_score(trace_id, observation_id, name, value)` | Native | After running DeepEval/RAGAS metrics externally, push scores to specific observations (e.g., retrieval span gets context precision score, generation span gets faithfulness score). |
| **Session grouping** | **Langfuse** or **Opik** | `session_id` parameter on traces | Native (both) | Group all traces from a single student conversation. Langfuse: `session_id` in trace creation. Opik: `thread_id` in `@track`. Enables session-level analytics and replay. |
| **Cost tracking** | **Langfuse** | Automatic per-model cost calculation | Native | Langfuse automatically tracks token usage and costs per LLM call. Dashboard shows cost by model, user, session, time period. |
| **Human annotation** | **Langfuse** | Annotation queues | Native | Create annotation queue for educational domain experts. Assign traces for review. Experts score for pedagogical quality, correctness, appropriateness. Scores feed back into automated evaluator calibration. |
| **Production monitoring** | **Langfuse** | Real-time dashboards + automated evaluators | Native | Set up automated LLM-as-Judge evaluators that run on every production trace. Dashboard alerts when quality scores drop below thresholds. |

---

### 5.7 Bridging DeepEval ↔ Langfuse (Combining Evaluation + Observability)

| Need | Approach | Implementation Sketch |
|---|---|---|
| **Run DeepEval metrics, visualize in Langfuse** | Fetch traces from Langfuse → run DeepEval metrics → push scores back | `traces = langfuse.api.trace.list(tags="lamb").data` → for each trace, create `LLMTestCase` from trace data → `metric.measure(test_case)` → `langfuse.create_score(trace_id=trace.id, name=metric.__name__, value=metric.score, comment=metric.reason)`. Langfuse official docs describe this exact pattern. |
| **Run RAGAS metrics, visualize in Langfuse** | Same pattern with RAGAS scorers | `scorer = Faithfulness(llm=llm)` → `result = scorer.score(...)` → `langfuse.create_score(trace_id=..., name="ragas_faithfulness", value=result.value)`. Langfuse has a dedicated RAGAS cookbook. |
| **Combined CI pipeline** | pytest with DeepEval + RAGAS in same test session | Both are Python libraries; no conflicts. DeepEval via `deepeval.evaluate()`, RAGAS via `scorer.score()`. Assert thresholds on both. Run in GitHub Actions. |

---

### 5.8 Filling KG Evaluation Gaps — Custom Metric Implementations

Since no framework natively supports Knowledge Graph evaluation, here are the recommended custom implementations:

| KG Metric | Framework | Custom API | Implementation Sketch |
|---|---|---|---|
| **Entity Extraction F1** | **DeepEval** | `BaseMetric` subclass | Parse `actual_output` (JSON list of entities) and `expected_output` (gold entities). Compute set intersection → TP, FP, FN → P/R/F1. Set `self.score = f1`. Deterministic, no LLM. |
| **Relation Extraction F1** | **RAGAS** | `@numeric_metric` decorator | `@numeric_metric(name="relation_f1", allowed_values=(0,1))`. Parse triples as `set(tuple(t))`. Compute F1 via set operations. |
| **Graph Completeness** | **DeepEval** | G-Eval | `GEval(name="graph_completeness", criteria="What fraction of key concepts and relationships from the source documents are captured in the KG?", evaluation_params=[INPUT, ACTUAL_OUTPUT])`. LLM judges coverage. |
| **Graph Traversal Quality** | **DeepEval** | DAG metric | Define decision tree: `TaskNode` (extract path) → `BinaryJudgementNode` (path reaches target?) → `NonBinaryJudgementNode` (path optimality: shortest? relevant intermediates?) → `VerdictNode` (0-10 scores). |
| **Ontology Alignment** | **DeepEval** | `BaseMetric` subclass | Compare extracted KG schema against reference ontology. Jaccard similarity on node/edge types. Structural comparison on allowed relationships. Deterministic. |
| **Hybrid Retrieval Fusion** | **Langfuse** + **DeepEval** | Composition | Trace KG and vector retrieval as separate Langfuse spans. Score each with `ContextualRelevancyMetric`. Score combined context separately. Compare scores to evaluate whether fusion improved quality. |
| **KG-Grounded Faithfulness** | **DeepEval** | `FaithfulnessMetric` (workaround) | Serialize KG triples as natural language sentences. Pass as `retrieval_context`. Standard faithfulness evaluation applies. Verified approach — works because the LLM judge evaluates text, not structure. |

---

### 5.9 Complete Stack Summary

| Layer | Framework | Purpose | When to Use |
|---|---|---|---|
| **Primary CI/CD evaluation** | **DeepEval** | RAG metrics, multi-turn metrics, safety, custom KG metrics, pytest integration | Every PR / deployment gate |
| **RAG-specific deep analysis** | **RAGAS** | Noise sensitivity, context entities recall, factual correctness, traditional NLP, SQL, educational rubrics | Periodic deep evaluation, dataset-level analysis |
| **Observability & tracing** | **Langfuse** | Pipeline tracing, per-span scoring, session management, human annotation, production monitoring, cost tracking | Always-on in production |
| **Conversation quality** | **Opik** | Multi-turn coherence, session completeness, user frustration, degeneration, bias judges, heuristic metrics | Context-aware RAG evaluation, conversation-level CI |
| **Red-teaming & safety** | **Giskard** | Adversarial probes, prompt injection, sycophancy, RAG component diagnosis (RAGET) | Pre-release security scans, periodic safety audits |
| **RAG strategy comparison** | **Vectara Open RAG Eval** | Reference-free A/B comparison, consistency measurement, hallucination baseline (HHEM) | When comparing `simple_rag` vs `context_aware_rag` vs future KG-RAG |
| **KG-specific metrics** | **Custom (DeepEval + RAGAS)** | Entity/relation extraction F1, graph completeness, traversal quality, ontology alignment | When KG features are implemented |
