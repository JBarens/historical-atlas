"""Phase 10 metrics CLI: aggregate the JSONL request log written by observability.write_event().

Usage: python backend/metrics.py [path]      (default: $OBS_LOG_PATH or backend/logs/requests.jsonl)
       python backend/metrics.py path --json (machine-readable)
Percentiles: nearest-rank on the sorted values (p = ceil(q*n)-th value), so p50 of [1,2,3,4] is 2.
Cost is an estimate at assumed prices (see observability.PRICE_NOTE).
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import observability as obs  # noqa: E402

STATUSES = ("answered", "insufficient_evidence", "needs_clarification", "error")
STAGES = ("rewrite", "retrieve", "rerank", "generate")


def percentile(values, q):
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    return v[max(1, math.ceil(q * len(v))) - 1]


def load(path):
    recs = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return recs


def compute(recs):
    n = len(recs)
    m = {"requests": n}
    if not n:
        return m
    status = Counter(r.get("status") for r in recs)
    m["status"] = {s: status.get(s, 0) for s in STATUSES} | {s: c for s, c in status.items() if s not in STATUSES}
    errs = Counter(r.get("error_cause") or "unknown" for r in recs if r.get("status") == "error")
    m["error_rate"] = round(status.get("error", 0) / n, 4)
    m["error_rate_by_cause"] = {c: round(k / n, 4) for c, k in errs.items()}
    tot = [r.get("latency_ms_total") for r in recs]
    m["latency_ms"] = {"total": {"p50": percentile(tot, .5), "p95": percentile(tot, .95)}}
    for st in STAGES:
        vals = [r.get("latency_ms", {}).get(st) for r in recs if st in r.get("latency_ms", {})]
        if vals:
            m["latency_ms"][st] = {"n": len(vals), "p50": percentile(vals, .5), "p95": percentile(vals, .95)}
    ti = [r.get("tokens_total", {}).get("input", 0) for r in recs]
    to = [r.get("tokens_total", {}).get("output", 0) for r in recs]
    cost = [r.get("cost_usd_total", 0) or 0 for r in recs]
    m["tokens_avg"] = {"input": round(sum(ti) / n, 1), "output": round(sum(to) / n, 1)}
    m["cost_usd"] = {"avg_per_request": round(sum(cost) / n, 6), "total": round(sum(cost), 6), "note": obs.PRICE_NOTE}
    retries = Counter()
    for r in recs:
        retries.update(r.get("retries") or {})
    m["retries"] = {"total": sum(retries.values()), "by_stage": dict(retries),
                    "requests_with_retry": sum(1 for r in recs if r.get("retries"))}
    m["calculation_share"] = round(sum(1 for r in recs if (r.get("routing") or {}).get("is_calculation")) / n, 4)
    claims = [c for r in recs for c in r.get("claims") or []]
    m["claims"] = {"total": len(claims), "in_range_false": sum(1 for c in claims if c.get("in_range") is False),
                   "in_range_false_share": round(sum(1 for c in claims if c.get("in_range") is False) / len(claims), 4)
                   if claims else None}
    return m


def render(m):
    out = [f"requests: {m['requests']}"]
    if not m["requests"]:
        return "\n".join(out)
    out.append("status: " + ", ".join(f"{k} {v}" for k, v in m["status"].items()))
    out.append(f"error rate: {m['error_rate']:.1%}" + ("  by cause: " + ", ".join(
        f"{k} {v:.1%}" for k, v in m["error_rate_by_cause"].items()) if m["error_rate_by_cause"] else ""))
    out.append("latency ms (p50 / p95):")
    for k, v in m["latency_ms"].items():
        out.append(f"  {k:<9} {v['p50']} / {v['p95']}" + (f"  (n={v['n']})" if "n" in v else ""))
    out.append(f"tokens per request (avg): in {m['tokens_avg']['input']}, out {m['tokens_avg']['output']}")
    out.append(f"est. cost: ${m['cost_usd']['avg_per_request']:.5f} per request, ${m['cost_usd']['total']:.5f} total "
               f"({m['cost_usd']['note']})")
    r = m["retries"]
    out.append(f"retries: {r['total']} total in {r['requests_with_retry']} requests {r['by_stage'] or ''}".rstrip())
    out.append(f"calculation share: {m['calculation_share']:.1%}")
    c = m["claims"]
    out.append(f"claims: {c['total']}, in_range false {c['in_range_false']}"
               + (f" ({c['in_range_false_share']:.1%})" if c["in_range_false_share"] is not None else ""))
    return "\n".join(out)


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    m = compute(load(args[0] if args else obs.log_path()))
    print(json.dumps(m, indent=1) if "--json" in argv else render(m))


if __name__ == "__main__":
    main(sys.argv[1:])
