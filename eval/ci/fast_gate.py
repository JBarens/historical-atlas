"""Phase 13 fast PR gate: hybrid (nomic exact + BM25, RRF, depth 100) R@20 on dev v2. Deterministic, no API, no model.
Fails if the fingerprint differs or R@20 < baseline (zero tolerance).
Usage: uv run -q --with fastembed --with numpy --with rank-bm25 python eval/ci/fast_gate.py
       ... fast_gate.py --update-baseline --reason "why"
"""
import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
from rank_bm25 import BM25Okapi

from common import BASELINE, FP, INDEX, QVEC, dev_items, fingerprint, load_corpus, rr
from run_hybrid import DEPTH, RRF_K, tok

STALE = "embeddings, chunking or dev questions changed: regenerate with eval/ci/build_ci_cache.py and run the full eval"


def check_fingerprint(built, items):
    want = json.loads(FP.read_text())
    got = fingerprint(built, items)
    got["query_vectors_sha256"] = hashlib.sha256(QVEC.read_bytes()).hexdigest()
    return [k for k in want if want[k] != got.get(k)]


def recall_at_20(docs, built, items, rrf_k=RRF_K, depth=DEPTH):
    text_of = {d["doc_id"]: d["text"] for d in docs}
    X = np.load(INDEX)
    Q = np.load(QVEC)
    assert len(X) == len(built) and len(Q) == len(items)
    bm25 = BM25Okapi([tok(x) for *_, x in built])
    scores = []
    for qi, it in enumerate(items):
        dense = list(np.argsort(((X - Q[qi]) ** 2).sum(1), kind="stable")[:depth])
        lex = list(np.argsort(-bm25.get_scores(tok(it["question"])), kind="stable")[:depth])
        fused = defaultdict(float)
        for lst in (dense, lex):
            for r, ci in enumerate(lst, 1):
                fused[ci] += 1 / (rrf_k + r)
        order = sorted(fused, key=fused.get, reverse=True)
        labels = [(e["doc_id"], rr.passage_spans(e["passage"], text_of[e["doc_id"]])) for e in it["evidence"] if e.get("verified")]
        hit = set()
        for ci in order[:20]:
            d, s, en, _ = built[ci]
            for li, (ld, spans) in enumerate(labels):
                if ld == d and any(s < pe and ps < en for ps, pe in spans):
                    hit.add(li)
        scores.append(len(hit) / len(labels))
    return float(np.mean(scores))


def run(rrf_k=RRF_K, update=False, reason=None):
    """Return (ok, message, value)."""
    docs, built = load_corpus()
    items = dev_items()
    bad = check_fingerprint(built, items)
    if bad:
        return False, f"FINGERPRINT MISMATCH ({', '.join(bad)}): {STALE}", None
    v = round(recall_at_20(docs, built, items, rrf_k=rrf_k), 6)
    if update:
        BASELINE.write_text(json.dumps({"metric": "hybrid_R@20_dev_v2", "value": v, "n": len(items), "rrf_k": RRF_K,
                                        "depth": DEPTH, "reason": reason,
                                        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds")}, indent=1) + "\n")
        return True, f"baseline updated to {v:.6f} (n={len(items)}): {reason}", v
    base = json.loads(BASELINE.read_text())["value"]
    if v < base:
        return False, f"REGRESSION: hybrid R@20 dev {v:.6f} < baseline {base:.6f} (zero tolerance)", v
    return True, f"PASS: hybrid R@20 dev {v:.6f} >= baseline {base:.6f} (n={len(items)})", v


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--reason")
    a = ap.parse_args()
    if a.update_baseline and not a.reason:
        ap.error("--update-baseline requires --reason")
    ok, msg, _ = run(update=a.update_baseline, reason=a.reason)
    print(msg)
    sys.exit(0 if ok else 1)
