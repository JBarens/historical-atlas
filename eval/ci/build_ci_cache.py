"""Regenerate the CI cache: dev query vectors (nomic, 'search_query: ') + fingerprint.json.
Run after changing embeddings, chunking or dev questions, then run the full eval and update the baseline.
Usage: uv run -q --with fastembed --with numpy --with rank-bm25 python eval/ci/build_ci_cache.py
"""
import json

import numpy as np
from fastembed import TextEmbedding

from common import FP, MODEL, QVEC, dev_items, fingerprint, load_corpus

_, built = load_corpus()
items = dev_items()
Q = np.array(list(TextEmbedding(MODEL).embed(["search_query: " + i["question"] for i in items])), dtype=np.float32)
np.save(QVEC, Q)
fp = fingerprint(built, items)
fp["query_vectors_sha256"] = __import__("hashlib").sha256(QVEC.read_bytes()).hexdigest()
FP.write_text(json.dumps(fp, indent=1) + "\n")
print(f"wrote {QVEC.name} {Q.shape} and {FP.name}")
