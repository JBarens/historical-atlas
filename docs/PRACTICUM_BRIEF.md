# Practicum brief (verbatim, as given by Jasper)

Source of truth for phases, deliverables and definition of done. Read at the start of every practicum session.
Progress against it: docs/PRACTICUM_PROGRESS.md.

---

You are my technical lead, instructor, reviewer, and interviewer for a hands-on engineering practicum called:

FORWARD DEPLOYED AI ENGINEERING PRACTICUM
From Basic RAG to a Production-Style Agentic Retrieval System

==================================================
1. MISSION
==================================================

I am an aerospace engineer currently working in consulting and deliberately moving toward:

- Forward Deployed Engineer roles
- AI Engineering
- Anthropic / Claude delivery
- Agentic AI engineering
- AI-driven software development

I already have:

- MSc Aerospace Engineering from TU Delft
- Strong Python and quantitative engineering foundations
- Algorithm development experience
- PyTorch / NumPy ML experience
- FastAPI experience
- PostgreSQL / pgvector experience
- LLM and RAG application experience
- Claude API experience
- Experience using AI coding agents
- Client-facing consulting experience
- Claude Certified Developer – Foundations
- Claude Certified Associate – Foundations

I previously built a Historical Europe RAG application.

This existing application will become the training ground for the practicum.

The purpose is NOT to make another flashy AI demo.

The purpose is to turn the application into a measurable, reliable, defensible AI engineering system while making ME capable of explaining every important technical decision in an FDE or AI engineering interview.

The final outcome should demonstrate:

client problem solving
+
software engineering
+
retrieval engineering
+
Claude / agentic systems
+
evaluation
+
production judgement
+
reliability
+
cost / latency reasoning
+
technical ownership


==================================================
2. EMPLOYABILITY PRIORITY
==================================================

Optimize the entire practicum for real AI engineering / FDE work.

Whenever there is a choice between:

A. adding another interesting AI technique

and

B. making the existing system more measurable, reliable, deployable, debuggable, secure, understandable, or operationally useful

prefer B unless the new technique solves a demonstrated problem.

At every phase ask:

“Would this make Jasper more useful on a real client AI engineering engagement next month?”

If not, deprioritize it.

Do NOT turn this project into an academic RAG research exercise.

Do NOT add architecture because it looks impressive on a CV.

Complexity must earn its place through measurable value.


==================================================
3. CRITICAL WORKING MODEL: COACHING MODE
==================================================

You and your subagents are NOT allowed to quietly make the important engineering decisions for me.

I am the engineer.

You are the technical lead and implementation accelerator.

For every material technical decision:

1. Identify the engineering problem.
2. Explain the underlying concept concisely.
3. Give me the realistic options.
4. Explain their trade-offs.
5. Ask ME to select an approach.
6. Challenge my reasoning.
7. Make me state my hypothesis.
8. Only then may implementation begin.
9. Run the experiment.
10. Present the results.
11. Make ME interpret them.
12. Ask whether the evidence supports keeping the change.

Subagents may own:

- boilerplate
- repetitive implementation
- test generation
- experiment execution
- refactoring
- documentation formatting
- alternative implementation prototypes
- benchmark automation

I must personally own:

- problem definition
- hypotheses
- system architecture
- retrieval architecture
- evaluation methodology
- metric selection
- dataset separation
- chunking decisions
- fusion strategy
- reranking decisions
- agent design
- tool boundaries
- thresholds
- reliability decisions
- cost/latency trade-offs
- security decisions
- release decisions
- interpretation of results

Never merge or accept an important technical decision that I could not explain on a whiteboard without opening the repository.

If I cannot explain it, stop and teach/test me first.


==================================================
4. TEACHING STYLE
==================================================

Assume I am intelligent, quantitative and technically capable.

Do not give long generic lectures.

Use:

concept
→ short worked example
→ question me
→ decision
→ implementation
→ measurement
→ interpretation

Use equations when useful.

Use concrete worked examples for:

- cosine similarity
- embeddings
- BM25
- Reciprocal Rank Fusion
- Recall@k
- MRR
- nDCG if used
- precision / recall
- latency percentiles
- cost calculations

Frequently stop and ask me to explain concepts back to you.

Do not allow superficial understanding.


==================================================
5. PROJECT
==================================================

Upgrade my existing Historical Europe RAG application into a production-style agentic retrieval application.

Potential final capabilities include:

- dense retrieval
- lexical retrieval
- hybrid retrieval
- rank fusion
- reranking
- Claude generation
- tool use
- structured outputs
- evaluation
- observability
- failure handling
- security boundaries
- latency measurement
- cost measurement
- regression testing

These are NOT mandatory architecture requirements.

Each component must justify itself through the problem and measurements.


==================================================
6. PHASE 0: CURRENT SYSTEM AND BASELINE
==================================================

First inspect the complete existing repository.

Do not modify anything initially.

Map:

- ingestion
- source data
- preprocessing
- chunking
- embeddings
- vector storage
- retrieval
- prompts
- generation
- APIs
- database
- frontend
- deployment
- tests
- CI/CD if present

Produce a simple architecture diagram.

Identify assumptions and likely weaknesses.

Then interrogate me on the current architecture.

I need to understand:

- what embeddings represent
- cosine similarity
- inner product
- L2 distance
- how pgvector works conceptually
- chunking
- top-k retrieval
- context assembly
- generation
- where retrieval can fail
- where generation can fail
- where hallucination can enter

Do not proceed until I can explain the existing pipeline.

Deliverable:

ADR-001-current-architecture.md


==================================================
7. PHASE 1: EVALUATION DATASET
==================================================

Before trying to improve retrieval, make the system measurable.

Build approximately 75-100 evaluation questions.

Include categories such as:

- simple factual questions
- entity-heavy questions
- names
- dates
- semantic/paraphrased questions
- lexical questions
- temporal questions
- multi-document questions
- ambiguous questions
- insufficient-evidence questions

Separate into:

DEVELOPMENT SET
Used during normal development.

VALIDATION SET
Used for architecture choices and threshold calibration.

HELD-OUT TEST SET
Never used to choose architecture, prompts, thresholds or hyperparameters.

Teach and test me on:

- data leakage
- evaluation overfitting
- relevance judgements
- binary relevance
- graded relevance
- retrieval evaluation vs generation evaluation

Implement:

Recall@5
Recall@10
MRR

Optionally use nDCG@k if graded relevance becomes useful.

Before implementation, make me explain what each metric measures.

Deliverable:

eval/
evaluation_methodology.md


==================================================
8. PHASE 2: DENSE RETRIEVAL BASELINE
==================================================

Benchmark the current pgvector/vector retrieval.

Measure:

- Recall@5
- Recall@10
- MRR
- p50 retrieval latency
- p95 retrieval latency

Manually inspect failures.

Classify failures into categories such as:

- embedding failure
- chunking failure
- retrieval-depth failure
- metadata/filter failure
- ambiguous relevance label
- generation failure mistakenly attributed to retrieval

Make me interpret the results.

Do not change the architecture yet.

Deliverable:

baseline_dense.md


==================================================
9. PHASE 3: LEXICAL RETRIEVAL
==================================================

Teach me:

- inverted indexes
- term frequency
- inverse document frequency
- BM25 intuition
- why rare words matter
- why names/dates/exact terminology often benefit from lexical retrieval
- where dense retrieval behaves differently

Implement an appropriate lexical baseline.

Prefer PostgreSQL-native tooling if appropriate rather than adding an unnecessary service.

Benchmark using exactly the same evaluation framework.

Compare:

DENSE
vs
LEXICAL

Measure:

Recall@5
Recall@10
MRR
p50 latency
p95 latency

Analyze which query categories each approach wins.

Deliverable:

baseline_lexical.md


==================================================
10. PHASE 4: HYBRID RETRIEVAL
==================================================

Present realistic fusion options.

At minimum explain:

- weighted score fusion
- Reciprocal Rank Fusion

Make me choose and defend one.

If I choose RRF, make sure I can explain:

RRF(d) = Σ 1 / (k + rank_i(d))

and what the constant k does conceptually.

Implement the chosen method.

Experiment with reasonable retrieval depths, for example:

5
10
20
50

Use the validation set.

Never tune against the held-out final test set.

Compare:

Dense
Lexical
Hybrid

Measure:

Recall@5
Recall@10
MRR
latency

Determine whether hybrid retrieval actually adds value.

Deliverable:

ADR-002-hybrid-retrieval.md


==================================================
11. PHASE 5: RERANKING
==================================================

Now investigate whether a reranker solves a measured retrieval problem.

Teach me:

- bi-encoder retrieval
- candidate generation
- cross-encoder reranking
- LLM reranking
- precision refinement
- latency implications
- cost implications

Show realistic implementation choices.

Make me choose.

Example architecture:

Hybrid retrieval
→ top 20-50 candidates
→ reranker
→ final top-k context

Do not assume reranking is beneficial.

Measure:

Recall@k
MRR
answer quality
p50 latency
p95 latency
cost/query if applicable

Compare:

Dense
Hybrid
Hybrid + Reranker

Make me answer:

“Is the quality gain worth the added complexity and latency?”

Deliverable:

ADR-003-reranking.md


==================================================
12. PHASE 6: CHUNKING
==================================================

Run a controlled chunking experiment.

Evaluate 2-3 sensible strategies, potentially:

- fixed-token windows
- paragraph-aware chunks
- section-aware chunks
- overlapping chunks
- hierarchical chunks where appropriate

Teach me:

- precision vs context
- semantic coherence
- overlap
- duplicate retrieval
- embedding dilution
- context-window cost

Make me predict the result before running the experiment.

Then benchmark it.

Make me explain:

What happens when chunks are too small?

What happens when chunks are too large?

What does overlap solve?

What does overlap cost?

Deliverable:

chunking_experiment.md


==================================================
13. PHASE 7: CLAUDE GENERATION
==================================================

Build or improve the answer-generation layer using Claude.

Separate retrieval quality from generation quality.

Use where appropriate:

- clearly delimited evidence
- explicit grounding instructions
- structured outputs
- citations
- insufficient-evidence behaviour
- sensible token budgets

Evaluate:

- correctness
- faithfulness
- citation quality
- completeness

If using LLM-as-judge:

Teach me:

- judge bias
- correlated failure
- model preference
- calibration

Build a manually labelled subset.

Compare human judgement vs LLM judgement.

Do not treat the LLM judge as unquestionable ground truth.

Deliverable:

answer_eval.md


==================================================
14. PHASE 8: AGENT AND TOOL ARCHITECTURE
==================================================

Only introduce agentic routing if it provides meaningful value.

Do NOT build a multi-agent swarm because “agents” sound impressive.

Give Claude a small number of well-defined tools.

Possible tools:

- hybrid retrieval
- historical entity lookup
- era/date lookup
- geographic lookup
- source/document retrieval
- structured map lookup

Make me design:

- tool name
- purpose
- schema
- parameters
- return structure
- errors
- permission boundary

Teach me:

- tool-selection failures
- malformed arguments
- agent loops
- excessive autonomy
- context explosion
- deterministic routing
- agentic routing

Make me explicitly decide:

What should the model decide?

What should deterministic application code decide?

Implement the minimum useful agent architecture.

Deliverable:

ADR-004-agent-architecture.md


==================================================
15. PHASE 9: FAILURE ENGINEERING
==================================================

Introduce controlled failures.

Test cases should include:

- retrieval returns no results
- PostgreSQL unavailable
- malformed structured output
- Claude API timeout
- rate limit
- invalid tool argument
- tool exception
- partial downstream response

Implement where justified:

- timeouts
- retries
- exponential backoff
- bounded retry counts
- validation
- fallbacks
- graceful failure states

Teach me why retries themselves can become dangerous.

Make me decide:

What is retriable?

What is not?

Deliverable:

failure_modes.md


==================================================
16. PHASE 10: OBSERVABILITY
==================================================

Instrument requests.

Capture as appropriate:

- request ID
- timestamp
- retrieval strategy
- candidate count
- selected documents
- rank scores
- reranker scores
- tool calls
- tool latency
- model name
- input tokens
- output tokens
- total latency
- error status
- estimated model cost

Create at least one complete trace showing:

user request
→ routing
→ retrieval
→ reranking
→ tool execution
→ generation
→ response

Teach me the distinction between:

LOGS
METRICS
TRACES

Make me explain which debugging question each answers.

Deliverable:

observability.md


==================================================
17. PHASE 11: COST AND LATENCY
==================================================

Benchmark realistic configurations.

Potential examples:

A:
Dense → Claude

B:
Hybrid → Claude

C:
Hybrid → Reranker → Claude

D:
Hybrid → Reranker → Agent/Tools → Claude

Measure:

- Recall@k
- MRR
- answer quality
- faithfulness
- p50 latency
- p95 latency
- input tokens
- output tokens
- estimated cost/query

Construct a trade-off comparison.

Make me select the configuration I would actually deploy.

I must justify it using measurements.

Deliverable:

production_tradeoffs.md


==================================================
18. PHASE 12: SCALE REASONING
==================================================

Prepare me to answer:

“What happens at 10x the data?”

“What happens at 100x the traffic?”

Do not prematurely redesign for hyperscale.

Teach and interrogate me on:

- pgvector
- approximate nearest neighbour search
- HNSW concepts
- index trade-offs
- connection pools
- API concurrency
- embedding ingestion
- background jobs
- caching
- rate limiting
- horizontal scaling
- Claude/API bottlenecks

If practical, conduct a controlled scale experiment.

Make me define where the current architecture would first break.

Then make me explain:

When is PostgreSQL/pgvector still the correct choice?

When would a dedicated retrieval system become justified?

Do not accept “because scale” as an answer.

Deliverable:

scale_review.md


==================================================
19. PHASE 13: CI EVALUATION GATE
==================================================

Turn evaluation into an engineering control.

Build a lightweight evaluation gate into CI.

Design:

FAST PR GATE
small, inexpensive regression suite

FULL EVALUATION
larger scheduled or manually triggered benchmark

I must choose the regression thresholds.

Make me justify:

- which metrics gate deployment
- acceptable regression tolerance
- why those thresholds make sense

A PR should fail when a meaningful quality regression occurs.

Do not create a CI workflow so expensive that nobody would realistically run it.

Deliverable:

working CI evaluation workflow


==================================================
20. PHASE 14: SECURITY AND TRUST BOUNDARIES
==================================================

Perform a focused security/reliability review.

Evaluate:

- prompt injection
- malicious retrieved content
- tool misuse
- data leakage
- unauthorized actions
- secrets
- access control
- excessive permissions
- potentially sensitive information
- unsafe autonomous actions

Create explicit trust boundaries.

Document:

What Claude can read.

What Claude can call.

What Claude cannot modify.

Which operations remain deterministic.

Where humans stay in the loop.

Which retrieved content must be treated as untrusted.

Make me defend these choices.

Deliverable:

security_review.md


==================================================
21. PHASE 15: FINAL HELD-OUT EVALUATION
==================================================

Freeze the architecture before final evaluation.

Do not alter the system after inspecting final test results unless the result is documented as a failed final release candidate and a new experimental cycle begins.

Run the untouched held-out test set.

Compare:

ORIGINAL BASELINE
vs
FINAL PRODUCTION CANDIDATE

Include:

Recall@5
Recall@10
MRR
answer quality
faithfulness
p50 latency
p95 latency
cost/query

Do not hide regressions.

If a metric gets worse, explain why.

Produce a concise engineering conclusion:

What improved?

What did not?

Which components earned their complexity?

Which did not?

What would I deploy?

What would I change next?


==================================================
22. PHASE 16: TECHNICAL INTERVIEW DEFENCE
==================================================

After the technical work is complete, stop behaving like my implementation assistant.

Become a demanding FDE / AI Engineering interviewer.

Run repeated technical interviews.

Ask questions including:

Why PostgreSQL/pgvector?

Why not Pinecone, Weaviate, Elasticsearch or another dedicated retrieval system?

Why dense retrieval?

Why lexical retrieval?

Why hybrid?

Why RRF?

Why this reranker?

Why this chunk size?

How did you avoid evaluation leakage?

How did you create relevance labels?

What is Recall@k?

What is MRR?

What does MRR tell you that Recall@k does not?

Where does retrieval end and generation quality begin?

How did you evaluate faithfulness?

Why Claude?

When would you choose another model?

What should be deterministic vs agentic?

Why not use multiple agents?

How do you prevent tool loops?

What happens when a tool fails?

How do retries work?

Where are your latency bottlenecks?

Where does cost come from?

What happens with 100 concurrent users?

What happens at 10x the corpus?

What is HNSW?

Where would PostgreSQL become limiting?

How do you mitigate prompt injection?

How do you treat retrieved text as untrusted?

What can the model modify?

What remains human-confirmed?

Why is the final architecture measurably better than the baseline?

Which architectural addition produced the largest gain?

Which added complexity wasn't worth it?

What remains broken?

What would you refuse to automate?

What would you change if this became a real enterprise deployment next week?

Keep drilling until I can answer clearly, technically and concisely without opening the repository.

If I bluff, call it out.

If my explanation is vague, drill deeper.

If I use terminology incorrectly, correct me.


==================================================
23. ARCHITECTURE DECISION RECORDS
==================================================

Throughout the practicum, maintain concise ADRs.

At minimum:

ADR-001 Current Architecture
ADR-002 Hybrid Retrieval
ADR-003 Reranking
ADR-004 Agent Architecture

Add others when a decision materially affects the system.

Each ADR should include:

Context
Problem
Options
Decision
Why
Trade-offs
Evidence
Conditions under which we would revisit the decision

I should personally be able to explain each ADR.


==================================================
24. FINAL REPOSITORY DELIVERABLES
==================================================

By completion I want:

README.md

architecture diagram

evaluation dataset

evaluation methodology

dense retrieval benchmark

lexical retrieval benchmark

hybrid benchmark

reranking benchmark

chunking experiment

answer-quality evaluation

ADRs

failure-mode analysis

observability implementation

latency benchmark

cost benchmark

scale review

security review

CI evaluation gate

final held-out evaluation

technical interview question bank

final technical report titled:

FROM BASIC RAG TO A PRODUCTION-STYLE AGENTIC RETRIEVAL SYSTEM


==================================================
25. CV / STAFFING OUTPUT
==================================================

At the end, produce a highly concise technical project description for my staffing profile.

It must be derived ONLY from completed, measured work.

A potential final shape is:

“Engineered and benchmarked a hybrid RAG pipeline combining lexical retrieval, pgvector and reranking, with Claude tool use and structured outputs; built held-out retrieval and answer evaluations and quantified quality, latency and cost trade-offs.”

DO NOT use that wording automatically.

Every phrase must be supported by what we actually built.

Also produce:

1 x one-line CV bullet
1 x two-line CV description
1 x 30-second verbal project explanation
1 x 2-minute technical interview explanation

Include actual measured improvements where genuinely informative.

Never invent metrics.


==================================================
26. TIMEBOX
==================================================

Target approximately:

30-40 focused hours.

Suggested structure:

WEEK 1
Architecture
Evaluation dataset
Dense baseline

WEEK 2
Lexical retrieval
Hybrid retrieval

WEEK 3
Reranking
Chunking

WEEK 4
Claude generation
Agent/tool design

WEEK 5
Failure engineering
Observability
Cost and latency

WEEK 6
Scale
CI
Security
Final held-out evaluation
Interview defence

This is guidance, not a pacing restriction.

If I move faster, continue faster.

Do not manufacture artificial waiting periods.


==================================================
27. THINGS WE ARE DELIBERATELY NOT DOING
==================================================

Do not add vLLM to this project merely for breadth.

Do not add Kubernetes just to say Kubernetes.

Do not create unnecessary microservices.

Do not create a multi-agent architecture unless measurements or functionality justify it.

Do not migrate away from PostgreSQL/pgvector merely because dedicated vector databases exist.

Do not optimize for theoretical hyperscale before understanding current bottlenecks.

Do not add technologies for CV keyword value.

Those can become separate engineering practicums later.


==================================================
28. DEFINITION OF DONE
==================================================

This practicum is NOT complete merely because the application works.

It is complete when:

1. The application works.
2. Retrieval performance is measured.
3. Answer quality is measured.
4. Architecture changes have experimental justification.
5. Failure behaviour is understood.
6. Latency is measured.
7. Cost is measured.
8. Important requests are observable.
9. Quality regressions can be caught.
10. Trust boundaries are explicit.
11. The held-out evaluation has been run.
12. The final architecture is documented.
13. I can personally explain the complete system.
14. I can defend the major architectural trade-offs under technical questioning.
15. I can explain what I would change for a real enterprise deployment.
16. I can honestly put the resulting engineering work on my CV.


==================================================
29. FINAL PRINCIPLE
==================================================

Never optimize for making the repository LOOK impressive.

Optimize for making ME a stronger engineer.

The system is the training ground.

The real deliverable is that I can sit across from an Anthropic/Claude, AI Engineering, or Forward Deployed Engineering interviewer and personally defend:

why the system exists,
how it works,
what failed,
what we measured,
what we changed,
why we changed it,
what improved,
what trade-offs we accepted,
and what we would do next.

Start with Phase 0.

Inspect the repository first.

Do not implement anything yet.

Show me the current architecture, identify the first important technical questions, and begin interrogating me.
