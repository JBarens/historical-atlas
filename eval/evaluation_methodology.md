# Evaluation methodology (Phase 1, in progress)

## Decisions so far
- Split: group split by question cluster (near-duplicate questions cluster together and go to one set). Not by case: six cases are too coarse.
- Sets: development (free use), validation (architecture and threshold choices), held-out test (run once on a frozen system).
- Question generation (option A): ~70% AI-generated with paraphrase instructions (no exact source terms in part of the set, some generated from case summaries rather than single chunks), ~30% written by Jasper (vague/why questions, out-of-corpus questions). Every question reviewed by Jasper.

- Relevance labels: source document + key passage (verbatim text). A retrieved chunk is relevant if it overlaps a labelled passage. Labels survive re-chunking (needed for Phase 6). AI proposes passages, Jasper verifies. Multi-document questions have several passages; out-of-corpus questions have none and are excluded from retrieval metrics (scored on answer behaviour: correct insufficient-evidence response).

- Review checklist: hard requirements (1) answerable from the labelled passage(s), else relabel as out-of-corpus; (2) correct category/tags. Efficiency checks (3) duplicate/cluster assignment, (4) wording leakage vs its category. Ambiguous questions are allowed; for them the expected behaviour (clarify, or cover the interpretations) must be written down.

- Tags on three independent axes (one value each):
  - Query form: lexical = question contains at least one exact rare term (name, year, article number, treaty name) that also appears in a labelled passage (checked by string match); semantic = otherwise.
  - Evidence: single-doc / multi-doc (more than one labelled passage needed).
  - Answerability: answerable / ambiguous (expected behaviour written down) / out-of-corpus (no passage).
  - Fallback for genuine borderline cases: semantic, multi-doc.
- Size and mix: ~90 questions, lexical/semantic ~50/50. Results always reported per tag. Expectation (Jasper): real users ask mostly why/how questions; revisit the mix once real query logs exist (Phase 10).
- Split: ~40 dev / 25 validation / 25 test, by question cluster, stratified by tags.

## Open

## Parked for later phases
- Runtime off-topic guard (Jasper): reject out-of-scope questions, e.g. via a similarity threshold. Caveat: raw similarity scores are not calibrated; decide in Phase 7/9 with validation data.

## Corpus filter audit (done)
- Sample 30 included + 30 excluded debates, judged by Jasper. Method: debates with an unambiguous case title judged on title; ambiguous titles (e.g. peace treaties) judged by reading the debate.
- Result: precision 30/30 (95% Wilson CI 0.89-1.00); misses among excluded 0/30 (CI 0.00-0.11, i.e. up to ~100 of 938 excluded debates could still be relevant).
- Caveat: title-based judgements use the same signal as the filter, so precision may be optimistic.
- Conclusion: the filter is not the bottleneck; coverage of these cases is genuinely thin.
- Decisions: excluded debates kept as untagged distractors (realistic haystack). Aaland and Greco-Bulgarian kept as thin cases (mainly test insufficient-evidence behaviour).

## Deviation (Day 2)
- The ~30% human-written questions were drafted by Hermes in "user voice" instead of by Jasper (time). Jasper approves/edits them.
  Risk: same model family as the generator and the answering model, so the independence intended by the 30% split is weaker.
  Mitigation: these questions are written without looking at the corpus (vague/why, out-of-corpus, ambiguous, cross-case), and results are reported separately for source=ai vs source=hermes.
- Triage (local, no API): 56 keep / 3 check / 5 drop suggestions; Jasper decides.

## Follow-up questions (Day 2, decision C + B)
- Context-dependent questions appear twice: without history (expected: ask which case) and with one prior user turn (expected: answer that case). 8 pairs = 16 items in eval/questions_followup.json (eval/make_followups.py).
- Follow-up computation ("what is that in today's money?"): a deterministic inflation tool over ONS long-run RPI (CDKO, 1800-2025, backend/data/reference/cdko.csv). History is synthetic (the assistant turn states amount and year) so the item tests the computation path independent of retrieval. Pass = no retrieval call, tool called with the right amount and year, value within 5%, measure named.
- CDKO is RPI, which runs above CPI; prices only (wage or GDP-share conversions give much larger multiples).
- Hypothesis (Jasper): without a tool Claude often gets the conversion wrong. Measured later as a no-tool baseline vs the tool.

## Corpus recall fix (Day 2)
- Grounding found 7/22 Hermes questions without evidence, all asking for outcomes. Per-case check: Aaland outcome never debated (true gap); Upper Silesia and Greco-Bulgarian had filter misses that the 30+30 random audit could not see (small strata). Lesson: audit per segment, not only overall.
- Fixes in backend/corpus/build.py: (1) greco_bulgarian body pattern widened to any Bulgaria mention in the window (Jasper, A: case = incident and its aftermath incl. refugee loans); (2) speeches in a debate whose title matches the strict case pattern inherit the tag. Tags: vilna 26->42, upper_silesia 76->113, mosul 87->102, greco_bulgarian 2->28, aland 9. No speech lost a tag.
- Split model: BAAI/bge-small-en-v1.5 (deliberately not the retriever model MiniLM; first attempt wrongly used MiniLM). Threshold 0.79, hand-calibrated on the bge band. Exact duplicates between the ambiguous set and follow-up pairs removed. Eval set v1 frozen; test set not looked at until final evaluation.
