# Chunking experiment

Status: draft (consolidation). Phase 6 of the brief, run early (Day 2), before the embedding-model swap.

## Strategies (eval/run\_retrieval.py, MODE)

* char500: fixed 500-character windows, 50 overlap, no header (app baseline).
* speech: one chunk per speech with a contextual header \[house, date, debate, speaker]. Long speeches are embedded whole, so the model truncates them.
* speech150: \~150-word pieces cut at sentence ends, header repeated on each piece, no overlap. 9,798 chunks.

## Eval blind spot found first

70% of dev labels sat in the first 150 words of a speech, so truncation looked harmless. 11 deep-passage questions were added (eval/add\_deep\_questions.py, offsets 292-747 words, existing splits untouched, $0.09) (docs/PRACTICUM\_PROGRESS.md).

## Results (MiniLM, eval v1, dev)

|Strategy|Chunks|R@5, n=35 (before deep questions)|R@5, n=39 (after)|
|-|-|-|-|
|char500|-|0.20|0.20|
|speech|5,097|0.23|0.21|
|speech150|9,798|0.21|0.24|

Sources: n=35 speech/speech150 from eval/results/chunking\_run.log, char500 from docs/PRACTICUM\_PROGRESS.md; n=39 from docs/PRACTICUM\_PROGRESS.md.

With nomic-embed-text-v1.5 on speech150 (v1 dev n=39): R@5 0.35, R@20 0.41, MRR 0.29; indexing 2,202 s vs 234 s for MiniLM (eval/results/nomic\_run.log).

## Decision and interpretation

* Jasper: "A2 kept, truncation is a bad default" (docs/PRACTICUM\_PROGRESS.md). speech150 is the chunking in the chosen stack.
* Jasper: too small loses context (who 'he' is; an answer split from its question, as in the Wedgwood/Chamberlain failures). Too large dilutes: one vector averages several topics and the LLM gets more tokens. Overlap solves answers cut at a boundary, but costs more chunks and tokens and can produce duplicate hits that push other relevant chunks out of the top 5. Prediction before the run was not recorded.

## Caveats

* Differences are 0.01-0.04 R@5 at n=35-39, about one question: on this metric chunking alone is not a clear win.
* Measured with MiniLM on eval v1; char500 and speech were not re-run on v2 or with nomic.
* Semantic labels incomplete (lower bound).

