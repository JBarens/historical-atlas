"""Shared loading + fingerprint for the CI gate (Phase 13). No embedding model needed."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eval"))
import run_retrieval as rr  # noqa: E402

rr.MODE = "speech150"
CI = ROOT / "eval/ci"
MODEL = "nomic-ai/nomic-embed-text-v1.5"
INDEX = ROOT / "backend/data/index/nomic-embed-text-v1.5_speech150.npy"
QVEC = CI / "dev_query_vectors.npy"
FP = CI / "fingerprint.json"
BASELINE = CI / "baseline.json"
SPLIT = "dev"


def load_corpus():
    docs = []
    for f in ("hansard_speeches.jsonl", "frus_documents.jsonl"):
        docs += [json.loads(l) for l in (ROOT / "backend/data/corpus" / f).read_text().splitlines() if l.strip()]
    built = [(d["doc_id"], s, e, x) for d in docs for (s, e, x) in rr.doc_chunks(d)]
    return docs, built


def dev_items():
    items = [json.loads(l) for l in (ROOT / "eval/eval_set_v2.jsonl").read_text().splitlines() if l.strip()]
    return [i for i in items if i["split"] == SPLIT and i.get("score_retrieval", True)
            and any(e.get("verified") for e in i["evidence"])]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def fingerprint(built, items):
    return {
        "chunks_sha256": sha("\n\x1e".join(x for *_, x in built).encode()),
        "chunk_count": len(built),
        "embedding_model": MODEL,
        "index_npy_sha256": sha(INDEX.read_bytes()),
        "dev_questions_sha256": sha("\n\x1e".join(i["question"] for i in items).encode()),
        "dev_question_count": len(items),
    }
