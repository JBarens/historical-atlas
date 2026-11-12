# ADR-001: Current architecture and problem definition

Status: accepted (Phase 0)
Owner: Jasper Barens

## Context

Historical Atlas is a FastAPI + React app that answers questions about 20th-century European history and drives a map (countries highlighted per year). It was built as a learning project. The practicum treats it as a production system from here on.

Current system (repo state at commit 558ae9b):

```
Ingest (ingest.py, manual)
  one hardcoded WW1 text -> fixed 500-character chunks, 50 overlap
  -> all-MiniLM-L6-v2 (384 dims); zero vectors if the model is not installed
  -> Postgres/pgvector: documents(text, embedding, source), no ANN index

Query (POST /query)
  question -> embed -> ORDER BY embedding <-> q (L2) LIMIT 3
  -> context + question -> pydantic-ai Agent (Claude Sonnet), output_type=QueryResponse
     (answer, regions, year_start/end, 3-5 moments, citations)
  -> stored in queries -> SSE: metadata, then answer replayed char by char (12 ms/char)

Country click (POST /country/): separate Claude agent, no retrieval
Borders (GET /borders/{year}): GeoJSON from historical-basemaps
Deploy: Render; sentence-transformers excluded in production
```

## Problems found

1. **Production does not do RAG.** Without sentence-transformers, `embed()` returns zero vectors. All distances are equal, so retrieval order is undefined (physical row order). Answers come from Claude's training data.
2. **No grounding.** The prompt never tells Claude to answer from the context or to say when evidence is missing. `citations` are generated text, not references to stored chunks.
3. **Map contract is unchecked.** `regions` are free strings constrained only by a name list in the prompt. A name not present in `borders` for that year silently highlights nothing.
4. **Fake streaming.** The full answer is generated, then replayed at 12 ms/char. Time to first token is hidden; perceived latency = generation time + replay time.
5. **Chunking ignores structure.** Fixed character windows split sentences and paragraphs.
6. **Not measurable.** No evaluation set, no tests, no CI, no latency or cost measurement.
7. **Corpus adds little.** A few Wikipedia paragraphs on topics Claude already knows well, so retrieval cannot visibly change answer quality.

Not a problem yet: L2 vs cosine. MiniLM outputs normalised vectors, so `<->` ranks identically to `<=>`. No ANN index is needed at this corpus size (exact scan).

## Decision: problem definition

- **Corpus (option B):** UK Hansard (parliamentary debates) and FRUS (Foreign Relations of the United States documents), both public. Reason: detailed primary sources Claude does not know at document level, so retrieval quality decides answer quality. Hansard covers European history directly; FRUS behaves like a company's internal document archive.
- **Provenance policy:** v1 is always-RAG with strict grounding and an insufficient-evidence path (no router). Routing (P3: general questions from Claude's own knowledge, shown as unsourced) is deferred to Phase 8 and added only if measurements show general questions perform badly or cost too much.

## Why

- Always-RAG first: one evaluation, no misroutes, no extra component until it earns its place. If routing is added later, under P3 each route has a simple, separate evaluation (correctness for the general route; retrieval metrics + faithfulness for the RAG route). Per-claim provenance labelling (P2) would make the evaluation harder and the labels arbitrary.
- The corpus choice makes retrieval improvements visible in answer quality, which is the whole point of the practicum.

## Trade-offs accepted

- Routing becomes a new failure mode and needs its own evaluation (see below).
- Two corpora with different formats mean more ingestion work.
- General-route answers have no citations by design.

## Open items (decided by Jasper before Phase 1)

- Misroute policy (decided): a specific question answered from memory (hallucination risk) is worse than a general question sent to RAG (extra latency or an insufficient-evidence answer). When uncertain, the router defaults to RAG.
- Period (decided): interwar Europe, 1919-1939. Fits existing map years 1920/1930/1938; less famous in detail than WW2, so retrieval should visibly matter. Frontend upgrade is in scope but implemented by Hermes; API/map contract decisions stay with Jasper.
- Corpus slice (decided): the League of Nations in action, 1920-1935 (five European disputes: Aaland Islands 1920-21, Upper Silesia 1921-22, Vilna 1920-23, Mosul 1924-26, Greco-Bulgarian incident 1925; Corfu 1923 dropped after a coverage check: 1 FRUS mention, no Hansard debate title; non-European cases excluded to keep the map European), Hansard as the main source, FRUS only where it covers a case (Aaland, Upper Silesia, Vilna, Mosul: the US was not a League member, so FRUS barely mentions Corfu or the Greco-Bulgarian incident). Uneven coverage across cases is accepted as realistic and reported per case. A few thousand chunks. Reasons: spread across many countries (good for the map), less famous in detail (retrieval should matter), and broad and messy like real company data. Hypothesis (Jasper): lexical wins on years, specific names, article numbers and treaty names; dense wins on vague, why/how and broad questions.

## Revisit when

- Routing accuracy on the validation set is too low to trust → reconsider P1 (strict grounding everywhere).
- The corpus turns out to be well known to the model (it answers source-specific questions correctly without retrieval) → pick a more obscure source.
