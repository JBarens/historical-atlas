# Practicum progress

## Where we are (end of day 1)
- Phase 0 done: ADR-001 (docs/adr/) records the real architecture, 7 problems (prod has no RAG: zero vectors), and decisions:
  corpus = League of Nations disputes 1920-1935, six European cases; Hansard main source, FRUS where it covers;
  always-RAG v1 with strict grounding + insufficient-evidence path (router deferred to Phase 8); misroute default = RAG.
- Phase 1 design done (eval/evaluation_methodology.md): cluster split 40/25/25 stratified by tags; labels = document + key passage;
  three tag axes (query form lexical/semantic by string-match rule, evidence single/multi-doc, answerability); ~90 questions, 50/50;
  70% AI-generated (paraphrase controls) + 30% Jasper; review checklist.
- Baseline decision: C = measure current system unchanged (A), then sensible fixes as first measured step (B).

## Running / next
- Hansard coverage probe 1920-1926 is resumable: rerun `cd ~/personal/corpus-probe && python3 hansard_probe.py 1920 1926` (skips finished months) -> hansard_1920_1926.json.
  FRUS coverage counted: Aland 23, Upper Silesia 23, Vilna 23, Corfu 1, Mosul 54, Greco-Bulgarian 1 (volumes 1920-1926, in corpus-probe/).
- Next: read probe results -> confirm case coverage -> ingestion design (Jasper decides selection rules) -> build ingestion -> generate + label eval set.

## Day 2
- Recall/precision/MRR understood (tested).
- Corfu dropped (no coverage). Five cases.
- Ingestion decisions: selection C (body-text filter, candidates = case title OR broad foreign/League title within case window, included if body mentions case >= 2x or title hit) + sampled audit 30 included + 30 excluded (Jasper judges). Document unit = individual speech, with contextual header [house, date, debate title, speaker].
- Built backend/corpus/build.py (stages titles/fetch/parse/frus/audit). FRUS: 15 docs (mosul 7, aland 3, vilna 3, upper_silesia 1, greco_bulgarian 1).
- Pipeline titles -> fetch -> parse -> audit running in background; logs in data_*.log; audit sheet -> eval/corpus_filter_audit.md.
- Speech tags: A2 window 1, multi-label; untagged speeches kept as distractors (debate_cases keeps the debate-level verdict).

## Pause point (Day 2, before side step)
- Corpus done: 5,082 speeches (~1.02M words), 198 tagged (mosul 87, upper_silesia 76, vilna 26, aland 9, greco_bulgarian 2) + 15 FRUS docs. Filter audit: precision 30/30 (CI 0.89-1.00), misses 0/30 (CI 0-0.11).
- AI questions: 64 in eval/questions_ai_draft.jsonl (generate_questions.py uses forced tool use; retag.py local rule A + header; triage.py: 56 keep / 3 check / 5 drop). Cost so far ~$1.6.
- Hermes-drafted 27 questions (why/out-of-corpus/ambiguous/cross-case) in eval/questions_hermes_draft.json (deviation recorded in methodology).
- OPEN (Jasper): review eval/review_ai_questions.md (REVIEW lines; start with DROP/CHECK) + approve/edit questions_hermes_draft.json.
- NEXT (Hermes): ground the answerable Hermes questions (~$0.50), merge, cluster split 40/25/25 stratified, freeze eval set -> Phase 2.
- Taught/tested so far: embeddings, cosine/IP/L2 equivalence, HNSW, recall/precision/MRR, leakage + group split, lexical vs dense (BM25, inverted index), reranking/cross-encoder intuition, structured output via tool use.

## Day 2 (cont.): eval set v1
- Review applied (5 AI questions dropped). Follow-ups (decision C) + inflation tool items (decision B, ONS RPI CDKO). Recall fix per case (see methodology). Grounding cost total ~$2.50.
- eval/eval_set_v1.jsonl: 106 items, 92 clusters (all-MiniLM-L6-v2 via fastembed, cosine >= 0.80, history included in the embedded text; follow-up pairs forced together). Split dev 49 / validation 28 / test 29, stratified by category.
- Bug caught: embedding only the question put all 4 computation items (identical text, different history) in one cluster -> all in dev. Fixed by embedding history + question.
- NEXT: Jasper sanity-checks threshold; freeze v1; Phase 2 baseline (current dense retriever on dev).

- Phase 2 baseline (dev, n=35 labelled): MiniLM, 500/50 char chunks, no header, L2. R@5=0.20, R@20=0.31, MRR=0.19. Lexical R@5 0.19 vs semantic 0.20 (R@20 0.38 vs 0.27). Jasper predicted R@5 ~0.20 (correct) and lexical clearly lower (not supported). eval/results/baseline_dev.json

- Chunking (Jasper: A2 kept, truncation is a bad default). Eval blind spot: 70% of dev labels in first 150 words; fixed with 11 deep-passage questions (eval/add_deep_questions.py, offsets 292-747 words, existing splits untouched, $0.09). Dev R@5 after fix: char500 0.20, speech 0.21, speech150 0.24. Next: embedding model.

- Model (speech150, dev n=39): nomic-embed-text-v1.5 R@5 0.35 / R@20 0.41 / MRR 0.29 vs MiniLM 0.24 / 0.32 / 0.17. Lexical 0.57 (MiniLM 0.33), semantic 0.20 (0.17). Index time 2202s vs 234s (~9x). Jasper predicted 0.5.

## Pause point (end Day 2)
- Best so far (dev): speech150 + nomic-embed-text-v1.5, R@5 0.35 (index cached: backend/data/index/nomic-embed-text-v1.5_speech150.npy; run: eval/run_retrieval.py dev speech150 nomic-ai/nomic-embed-text-v1.5). Semantic = lower bound.
- OPEN DECISION (Jasper): fusion for BM25+dense: A RRF / B weighted alpha / C routing; plus predictions for BM25-alone and hybrid R@5, lexical vs semantic. Also measure BM25 alone.
- Later: few-shot judge (generation phase), query rewriting for follow-ups, inflation tool.

- Day 3: BM25 vs nomic vs RRF (k=60, depth 100) on speech150, dev n=38. R@5: bm25 0.36, nomic 0.36, rrf 0.35. R@20: 0.46 / 0.43 / 0.56. Lexical R@20 rrf 0.82. Semantic: bm25 0.27 > nomic 0.20 at R@5. Jasper predicted bm25 0.20, hybrid 0.40, gain on lexical. eval/run_hybrid.py
