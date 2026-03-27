# PhD Research Lines: Agent-Assisted Creator in LAMB

**Context:** PhD program in Education in Sciences, Technology and Mathematics
**Focus:** Design and application of educational technologies
**Platform:** LAMB — Learning Assistants Manager and Builder
**Subproject:** Agent-Assisted Creator (AAC)

---

## Line 1: Conversational Co-Design as Instructional Design Methodology

**How does AI-guided co-design change the way educators create pedagogically effective AI learning assistants — and the quality of what they produce?**

### Problem

The current generation of AI assistant builders presents educators with blank forms: write a system prompt, pick a model, configure settings. This assumes the educator already knows what good prompt engineering looks like, understands how LLM context construction works, and can anticipate how students will interact with the assistant. Most educators — even technically proficient ones — lack this specific expertise. The result is assistants that are functional but pedagogically shallow: generic prompts, untested assumptions, no iteration.

The AAC introduces a fundamentally different paradigm: the educator describes their pedagogical intent in natural language, and a specialized agent translates that intent into technical configuration through iterative dialogue. This is not just a UX improvement — it is a new instructional design methodology where the design artifact (the AI assistant) emerges from a structured conversation between human pedagogical expertise and machine technical capability.

### Research Questions

1. How does the co-design process with an AI agent affect the **pedagogical quality** of the resulting AI learning assistants, compared to traditional form-based creation?
2. What **interaction patterns** emerge in educator-agent design sessions? Which patterns correlate with higher-quality assistants?
3. How does the co-design process change across **successive sessions** — do educators internalize design strategies and become more efficient/effective over time?
4. What role does the agent's ability to **visualize context construction** (showing what the LLM actually sees) play in the educator's design decisions?

### Methodology

**Design-based research (DBR)** over three iterative cycles, combined with mixed-methods analysis.

- **Participants:** 20-30 STEM educators across multiple institutions, varying in AI experience.
- **Intervention:** Educators create AI assistants for their courses using both the traditional form and the AAC, in counterbalanced order.
- **Data sources:**
  - Full AAC session transcripts (conversation logs, tool calls, version history) — rich process data captured automatically by the platform.
  - Assistant version snapshots and diffs — trace the evolution of the design artifact.
  - Student interaction data with the resulting assistants (anonymized chat logs, usage patterns).
  - Semi-structured interviews with educators on their design experience.
  - Expert panel evaluation of assistant quality using a rubric (pedagogical soundness, prompt effectiveness, student appropriateness).
- **Analysis:** Thematic analysis of design conversations, comparative quality scoring of assistants, sequential pattern mining of design sessions, longitudinal tracking of educator skill development.

### Expected Contributions

- A **taxonomy of educator-agent co-design patterns** in educational AI creation.
- Empirical evidence on whether conversational co-design produces **measurably better** educational AI assistants.
- A validated **quality rubric** for evaluating AI learning assistants that integrates both technical and pedagogical dimensions.
- Design principles for **AI co-design tools** in educational contexts — transferable beyond LAMB.

### Technical Requirements from LAMB/AAC

- Full session logging (conversation, tool calls, versions) — already designed into AAC.
- Version-tagged completion data for student interactions — Phase 4 of AAC.
- Export mechanisms for anonymized research data.
- Ability to run the same student test scenarios against assistants created via both methods (controlled comparison).

---

## Line 2: Educator AI Literacy Through Participatory Design of Learning Assistants

**Can the process of designing AI assistants — guided by an AI agent — serve as an effective professional development pathway for building educator AI literacy?**

### Problem

There is broad consensus that educators need AI literacy, but little agreement on what that means in practice or how to develop it. Most current approaches fall into two categories: (a) generic AI awareness workshops ("what is a large language model") that are too abstract to change classroom practice, or (b) tool-specific training ("how to use ChatGPT") that teaches button-clicking without developing transferable understanding.

The AAC offers a third path: **learning by building**. When an educator designs an AI assistant through conversation with the AAC agent, they necessarily engage with concepts like context windows, prompt engineering, retrieval-augmented generation, output evaluation, and iterative refinement — but grounded in their own pedagogical goals, not in abstract technical exercises. The agent's visualization capabilities (showing how the LLM context is constructed, how RAG retrieval works, how prompt processors transform messages) make invisible AI mechanisms visible and concrete.

This research line investigates whether this participatory design process constitutes an effective — and scalable — form of AI literacy professional development.

### Research Questions

1. What **AI literacy competencies** do educators develop through the AAC design process? How do these map to existing AI literacy frameworks (e.g., Long & Magerko, Ng et al.)?
2. How do educators' **mental models of AI** change through the design experience? Specifically, do they move from "magic black box" toward mechanistic understanding?
3. Does AI literacy gained through assistant design **transfer** to other AI-related decisions (tool selection, policy discussions, student guidance on AI use)?
4. What is the role of the agent's **educational visualizations** (context previews, pipeline explanations) in developing conceptual understanding versus procedural skill?
5. How does the design experience differ for educators with **varying levels of prior technical knowledge** — does the agent successfully scaffold across the expertise spectrum?

### Methodology

**Mixed-methods intervention study** with pre/post assessment and longitudinal follow-up.

- **Participants:** 30-40 STEM educators, stratified by prior AI experience (none, basic user, advanced user).
- **Intervention:** A structured 6-session AAC design program where each educator builds an AI assistant for a real course unit. Sessions are spaced over 6-8 weeks to allow reflection and classroom tryout between sessions.
- **Instruments:**
  - Pre/post AI literacy assessment (adapted from validated instruments, extended with LAMB-specific items on prompt engineering, context construction, and evaluation).
  - Concept mapping exercises (pre/post) to capture mental model evolution.
  - Think-aloud protocols during select design sessions.
  - Reflective journals maintained by participants between sessions.
  - Transfer tasks: scenarios requiring AI-related decisions outside the design context.
  - 3-month follow-up interviews on sustained practice change.
- **Data from AAC:** Session transcripts, frequency and nature of visualization requests, version iteration patterns, evaluation sophistication over time.
- **Analysis:** Pre/post comparison of literacy scores, qualitative analysis of mental model evolution, interaction analysis of design sessions (particularly around visualization moments), transfer task scoring.

### Expected Contributions

- An empirically grounded **AI literacy development model** specific to educators in participatory design contexts.
- Evidence on the effectiveness of **"learning by building"** as a professional development strategy for AI literacy — with quantified outcomes.
- Identification of **critical learning moments** in the design process (when do mental models shift? what triggers deeper understanding?).
- Design guidelines for **scaffolding AI literacy** through co-design tools — informing the development of AAC's skill files and agent behavior.
- A validated **AI literacy assessment instrument** for educators that goes beyond awareness to include design and evaluation competencies.

### Technical Requirements from LAMB/AAC

- Detailed logging of which visualization tools are used and when (correlate with learning outcomes).
- Ability to configure the agent's scaffolding level (more/less explanation) for experimental conditions.
- Session replay capability for think-aloud protocol analysis.
- Longitudinal user tracking across sessions (same educator, multiple design sessions over weeks).

---

## Line 3: Iterative Evaluation Practices for Educational AI — From Human Judgment to Hybrid Assessment

**How do educators evaluate AI-generated educational interactions, how does their evaluative practice evolve through iteration, and can human-AI hybrid evaluation produce reliable quality assessments?**

### Problem

The educational AI field has an evaluation problem. Technical benchmarks (BLEU, perplexity, accuracy on standardized tests) capture almost nothing of what makes an AI tutor pedagogically effective. Meanwhile, human evaluation — the gold standard — is expensive, inconsistent, and doesn't scale. The result is that most educational AI assistants are deployed with minimal quality assurance: the creator tries a few prompts, it "looks okay," and it goes live.

The AAC's test-and-evaluate loop generates a unique dataset: educators running structured test conversations against their assistants, evaluating the outputs, and iterating. Over time, the agent learns from these human evaluations and begins suggesting its own assessments. This creates a natural laboratory for studying how educators evaluate AI educational output and whether human-AI hybrid evaluation can become reliable enough to serve as a quality assurance mechanism.

This is simultaneously a study of **educator evaluative expertise** (what do they look for? what do they miss? how do they improve?) and a study of **hybrid evaluation methodology** (can the agent's learned evaluations approximate human judgment? where do they diverge?).

### Research Questions

1. What **evaluation dimensions** do educators spontaneously use when assessing AI-generated educational responses? How do these compare to expert-defined quality frameworks?
2. How does educators' **evaluative practice evolve** across design iterations? Do they become more systematic, more critical, more consistent?
3. What is the **inter-rater reliability** between the agent's learned evaluations and the educator's own judgments? Where do they agree and diverge?
4. Can a **hybrid evaluation protocol** (agent proposes evaluation, educator confirms/overrides) achieve acceptable reliability while reducing evaluator burden?
5. How do evaluation-driven design iterations affect **measurable student outcomes** when the assistants are deployed in real courses?

### Methodology

**Sequential explanatory design** — quantitative analysis of evaluation data followed by qualitative investigation of evaluative reasoning.

- **Participants:** 20-25 STEM educators using the AAC to design and iteratively refine assistants over a full academic term.
- **Phase A — Evaluation data collection (automated):**
  - All test runs, evaluations (user and agent), version changes, and evaluation-triggered refinements are captured by the AAC system.
  - This produces a large structured dataset: (test input, AI response, human evaluation, agent evaluation, subsequent design change).
  - Quantitative analysis: evolution of evaluation dimensions used, inter-rater agreement (human-agent), evaluation consistency over time, correlation between evaluation patterns and version quality improvement.
- **Phase B — Evaluative reasoning (qualitative):**
  - Stimulated recall interviews: show educators their own evaluation history and ask them to explain their reasoning at key decision points.
  - Expert panel independently evaluates a sample of test outputs using a comprehensive rubric — serves as ground truth for calibrating both human and agent evaluations.
  - Comparative analysis: educator evaluations vs. expert evaluations vs. agent evaluations.
- **Phase C — Student impact (field study):**
  - Assistants at various version maturity levels deployed in real courses.
  - Student learning outcomes (pre/post assessments), engagement metrics (conversation length, return rate), and satisfaction surveys.
  - Correlate with version evaluation data: do assistants with more evaluation iterations produce better student outcomes?
- **Analysis:** Longitudinal evaluation pattern analysis, Cohen's kappa for inter-rater reliability, regression modeling (evaluation thoroughness → assistant quality → student outcomes), thematic analysis of evaluative reasoning.

### Expected Contributions

- An **empirically derived taxonomy of evaluation dimensions** for educational AI interactions — what educators actually assess, not what researchers assume they should.
- A **developmental model of evaluative expertise** in educational AI — how educators grow from naive to sophisticated evaluators through practice.
- Quantified analysis of **human-AI evaluation agreement** — where LLM-as-judge works for educational content and where it fails.
- A validated **hybrid evaluation protocol** with documented reliability metrics — practical contribution to quality assurance in educational AI.
- Evidence linking **design iteration depth** (number of test-evaluate-refine cycles) to **student learning outcomes** — the first empirical connection between AI assistant design process quality and educational impact.
- Design requirements for **evaluation support in AI creation tools** — what the agent should and shouldn't automate in the evaluation loop.

### Technical Requirements from LAMB/AAC

- Structured evaluation data with timestamps, dimensions, and confidence levels (Phase 3 of AAC).
- Agent evaluation with transparency (what patterns informed the judgment) for researcher analysis.
- Version-tagged production completions linked to student outcome data (Phase 4 of AAC).
- Export of evaluation datasets in research-friendly formats (CSV/JSON with anonymization).
- Ability to configure evaluation prompts and dimension frameworks (for experimental manipulation).

---

## Cross-Cutting Considerations

### Across All Three Lines

| Concern | Approach |
|---------|----------|
| **Ethics** | All student data anonymized. Educator participation voluntary with informed consent. IRB approval required. AAC session data used for research only with explicit consent. |
| **Platform dependency** | Findings framed as transferable principles, not LAMB-specific results. LAMB is the instrument, not the object of study. |
| **Sample size** | Qualitative depth prioritized over statistical power. Effect sizes estimated for future large-scale studies. |
| **Timeline** | Each line is a 3-4 year program. Phase 1 of AAC needed before data collection begins. Lines 1 and 2 can start with Phase 2; Line 3 requires Phase 3. |

### How the Lines Complement Each Other

```
Line 1 (Co-Design Methodology)
  → Produces quality rubrics and design pattern taxonomy
    → Feeds into Line 3's evaluation framework

Line 2 (AI Literacy)
  → Identifies what educators learn during design
    → Explains WHY certain design patterns (Line 1) emerge
    → Explains WHY evaluation practices (Line 3) evolve as they do

Line 3 (Evaluation Practices)
  → Produces hybrid evaluation protocol
    → Improves the AAC agent's evaluation capabilities
    → Feeds back into tool design (Line 1)
```

A PhD student could focus on one line while the others are pursued by collaborators or future students, creating a coherent research program around the AAC.

---

*Prepared: 2026-03-27*
*Platform: LAMB v2.5 + AAC (in development)*
