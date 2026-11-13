"""Consolidation: retrieval in PostgreSQL (pgvector exact search + Postgres FTS), per-stage latency, depth sweep,
optional Haiku rerank. Chunks = speech150, dense = nomic (cached embeddings), BM25 kept as the reference lexical.
Usage: docker compose up -d
       EVALSET=eval_set_v2.jsonl uv run -q --with fastembed --with numpy --with rank-bm25 --with "psycopg[binary]" \
         --with pgvector --with anthropic --with python-dotenv python eval/run_pg.py validation 0,20,50
Never run on split=test.
"""
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import psycopg
from fastembed import TextEmbedding
from pgvector.psycopg import register_vector
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
import run_retrieval as rr  # noqa: E402
from run_hybrid import tok, RRF_K, DEPTH  # noqa: E402

rr.MODE = "speech150"
DSN = "postgresql://atlas:atlas@localhost:5432/atlas"
SWEEP = (5, 10, 20, 50, 100)
KS = (5, 10, 20)


def load_table(conn, built, X):
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.execute("""CREATE TABLE IF NOT EXISTS eval_chunks (
        id int PRIMARY KEY, doc_id text NOT NULL, start_char int, end_char int, text text NOT NULL,
        embedding vector(768) NOT NULL,
        tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED)""")
    conn.execute("CREATE INDEX IF NOT EXISTS eval_chunks_tsv ON eval_chunks USING gin (tsv)")  # FTS index; no ANN index on embedding
    n = conn.execute("SELECT count(*) FROM eval_chunks").fetchone()[0]
    if n != len(built):
        conn.execute("TRUNCATE eval_chunks")
        with conn.cursor().copy("COPY eval_chunks (id, doc_id, start_char, end_char, text, embedding) FROM STDIN") as cp:
            for i, ((d, s, e, x), v) in enumerate(zip(built, X)):
                cp.write_row((i, d, s, e, x, "[" + ",".join(f"{a:.7g}" for a in v) + "]"))
        conn.execute("ANALYZE eval_chunks")
    conn.commit()


Q_DENSE = "SELECT id FROM eval_chunks ORDER BY embedding <-> %s LIMIT %s"   # exact scan, L2 (same as numpy)
Q_FTS_AND = """SELECT id FROM eval_chunks, plainto_tsquery('english', %s) q WHERE tsv @@ q
               ORDER BY ts_rank_cd(tsv, q) DESC, id LIMIT %s"""
# OR variant: same lexemes as plainto_tsquery, joined with | instead of & (natural-language questions rarely match all terms)
Q_FTS_OR = """SELECT id FROM eval_chunks,
               (SELECT nullif(replace(plainto_tsquery('english', %s)::text, ' & ', ' | '), '')::tsquery q) qq
               WHERE tsv @@ q ORDER BY ts_rank_cd(tsv, q) DESC, id LIMIT %s"""


def rrf(lists, depth):
    f = defaultdict(float)
    for lst in lists:
        for r, ci in enumerate(lst[:depth], 1):
            f[ci] += 1 / (RRF_K + r)
    return sorted(f, key=lambda c: (-f[c], c))


def score(order, labels, built):
    hit = {}
    for rank, ci in enumerate(order[:max(KS)], 1):
        d, s, en, _ = built[ci]
        for li, (ld, spans) in enumerate(labels):
            if li not in hit and ld == d and any(s < pe and ps < en for ps, pe in spans):
                hit[li] = rank
    row = {"rr": 1 / min(hit.values()) if hit else 0.0}
    for k in KS:
        row[f"R@{k}"] = sum(v <= k for v in hit.values()) / len(labels)
    return row


def main(split="dev", reranks="0"):
    assert split != "test", "never run on the held-out test split"
    reranks = [int(x) for x in reranks.split(",")]
    docs = []
    for f in ("hansard_speeches.jsonl", "frus_documents.jsonl"):
        docs += [json.loads(l) for l in (ROOT / "backend/data/corpus" / f).read_text().splitlines() if l.strip()]
    built = [(d["doc_id"], s, e, x) for d in docs for (s, e, x) in rr.doc_chunks(d)]
    text_of = {d["doc_id"]: d["text"] for d in docs}
    X = np.load(ROOT / "backend/data/index/nomic-embed-text-v1.5_speech150.npy").astype(np.float32)
    assert len(X) == len(built)
    bm25 = BM25Okapi([tok(x) for *_, x in built])
    conn = psycopg.connect(DSN)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector"); conn.commit()
    register_vector(conn)
    load_table(conn, built, X)

    items = [json.loads(l) for l in (ROOT / "eval" / os.environ.get("EVALSET", "eval_set_v2.jsonl")).read_text().splitlines()]
    items = [i for i in items if i["split"] == split and i.get("score_retrieval", True)
             and any(e.get("verified") for e in i.get("evidence", []))]
    model = TextEmbedding("nomic-ai/nomic-embed-text-v1.5")
    if any(reranks):
        import run_llm_rerank as lr  # creates the Anthropic client (key from .env)

    # warm-up (model, DB cache, BM25), not timed
    w = np.array(next(iter(model.embed(["search_query: warm up"]))), dtype=np.float32)
    conn.execute(Q_DENSE, (w, DEPTH)).fetchall(); conn.execute(Q_FTS_OR, ("warm up league", DEPTH)).fetchall()
    bm25.get_scores(tok("warm up league"))
    if any(reranks):
        lr.llm_rank("warm up", ["a", "b"])

    lat, runs, overlap, fts_and_empty, usage = defaultdict(list), defaultdict(list), [], 0, defaultdict(list)
    for it in items:
        q = it["question"]
        labels = [(e["doc_id"], rr.passage_spans(e["passage"], text_of[e["doc_id"]])) for e in it["evidence"] if e.get("verified")]
        t = time.perf_counter(); qv = np.array(next(iter(model.embed(["search_query: " + q]))), dtype=np.float32)
        lat["embed"].append(time.perf_counter() - t)
        t = time.perf_counter(); dense = [r[0] for r in conn.execute(Q_DENSE, (qv, DEPTH)).fetchall()]
        lat["dense_pg"].append(time.perf_counter() - t)
        t = time.perf_counter(); dense_np = list(np.argsort(((X - qv) ** 2).sum(1))[:DEPTH])
        lat["dense_numpy"].append(time.perf_counter() - t)
        t = time.perf_counter(); fts_and = [r[0] for r in conn.execute(Q_FTS_AND, (q, DEPTH)).fetchall()]
        lat["fts_and_pg"].append(time.perf_counter() - t)
        t = time.perf_counter(); fts_or = [r[0] for r in conn.execute(Q_FTS_OR, (q, DEPTH)).fetchall()]
        lat["fts_or_pg"].append(time.perf_counter() - t)
        t = time.perf_counter(); bm = list(np.argsort(-bm25.get_scores(tok(q)))[:DEPTH])
        lat["bm25"].append(time.perf_counter() - t)
        t = time.perf_counter(); hyb = rrf([dense, bm], DEPTH)
        lat["fusion"].append(time.perf_counter() - t)
        hyb_fts = rrf([dense, fts_or], DEPTH)
        fts_and_empty += not fts_and
        overlap.append(len(set(dense[:20]) & set(int(c) for c in dense_np[:20])) / 20)

        for name, order in (("dense", dense), ("bm25", bm), ("fts_and", fts_and), ("fts_or", fts_or),
                            ("rrf_bm25", hyb), ("rrf_fts_or", hyb_fts)):
            runs[name].append(score(order, labels, built))
        for d in SWEEP:
            runs[f"rrf_bm25@{d}"].append(score(rrf([dense, bm], d), labels, built))
            runs[f"rrf_fts_or@{d}"].append(score(rrf([dense, fts_or], d), labels, built))
        base = lat["embed"][-1] + lat["dense_pg"][-1] + lat["bm25"][-1] + lat["fusion"][-1]
        lat["total_norerank"].append(base)
        for n in reranks:
            if not n:
                continue
            cand = hyb[:n]
            t = time.perf_counter(); order, _, i_t, o_t = lr.llm_rank(q, [built[c][3] for c in cand])
            dt = time.perf_counter() - t
            lat[f"haiku{n}"].append(dt); lat[f"total_haiku{n}"].append(base + dt)
            usage[f"haiku{n}"].append((i_t, o_t))
            top = [cand[k] for k in order]
            runs[f"rrf_bm25+haiku{n}"].append(score(top + [c for c in cand if c not in top] + hyb[n:], labels, built))

    out = {"split": split, "n": len(items), "fts_and_empty": fts_and_empty,
           "dense_top20_overlap_pg_vs_numpy": {"mean": float(np.mean(overlap)), "min": float(np.min(overlap))},
           "metrics": {k: {m: float(np.mean([r[m] for r in v])) for m in v[0]} for k, v in runs.items()},
           "latency_ms": {k: {"p50": float(np.percentile(v, 50) * 1e3), "p95": float(np.percentile(v, 95) * 1e3)} for k, v in lat.items()},
           "haiku_usage": {k: {"in": int(sum(a for a, _ in v)), "out": int(sum(b for _, b in v)),
                               "cost_usd_assumed": sum(a for a, _ in v) * 1e-6 + sum(b for _, b in v) * 5e-6} for k, v in usage.items()}}
    print(f"{split}: n={len(items)}  pg-vs-numpy dense top-20 overlap mean {out['dense_top20_overlap_pg_vs_numpy']['mean']:.3f} "
          f"min {out['dense_top20_overlap_pg_vs_numpy']['min']:.3f}  fts_and empty for {fts_and_empty} questions")
    for k, m in out["metrics"].items():
        print(f"{k:22} R@5={m['R@5']:.2f} R@10={m['R@10']:.2f} R@20={m['R@20']:.2f} MRR={m['rr']:.2f}")
    for k, v in out["latency_ms"].items():
        print(f"latency {k:16} p50 {v['p50']:8.1f} ms  p95 {v['p95']:8.1f} ms")
    for k, v in out["haiku_usage"].items():
        print(f"{k}: tokens in {v['in']} out {v['out']}  cost ${v['cost_usd_assumed']:.3f} (assumed price)")
    (ROOT / f"eval/results/pg_{split}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(*(sys.argv[1:] or ["dev"]))
