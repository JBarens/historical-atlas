"""Generate the demo-mode conversations by running the real pipeline once (costs a few cents).

Run: uv run -q --with anthropic --with python-dotenv --with fastembed --with numpy --with rank-bm25 --with fastapi \
       python backend/scripts/generate_demo.py
Writes backend/data/static/demo_conversations.json with the same response shape as POST /api/ask.
"""
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
import main as M  # noqa: E402

CONVERSATIONS = [
    # dev-split questions that answered correctly in eval/results/rerank_depth_e2e_20.json (never test items)
    ["Who were the three members of the committee established in September 1920 to propose a final settlement of "
     "the Aaland Islands question, and which countries did they represent?"],
    ["Why was the conference to resolve the territory's fate in the partition of Upper Silesia (Germany-Poland) "
     "repeatedly delayed through mid-1921?",
     "Did the British government accept the League's partition?"],
    ["What authority did the Ambassadors' Conference cite in March 1923 when awarding Vilna to Poland?"],
    ["What position did Ramsay MacDonald take in the February 1926 Commons debate on extending British obligations "
     "to Iraq until 1928?"],
    # kept deliberately: the corpus does not hold the answer, so the honest result is insufficient_evidence
    ["How did the League of Nations respond to the Greek incursion into Bulgaria near Petrich in 1925?"],
    ["In 1922 Parliament was told that the Iraq garrison cost about \u00a320,000,000 a year. Which measure would you use "
     "to compare that with today?",
     "What would \u00a320,000,000 from 1922 be worth in 2023?"],
]
CAP = 0.12

out, total = [], 0.0
for turns in CONVERSATIONS:
    history, conv = [], {"title": turns[0], "turns": []}
    for q in turns:
        r = M.pipeline().answer(q, history)
        cost = M.cost_of(r)
        total += cost
        shaped = M.shape(r, history)
        conv["turns"].append({"question": q, "response": shaped})
        print(f"{shaped['status']:22} case={shaped['case']} ${cost:.4f} {q[:60]}", flush=True)
        history += [{"role": "user", "content": q}, {"role": "assistant", "content": shaped["answer"] or shaped["message"] or ""}]
        if total > CAP:
            sys.exit(f"spend cap {CAP} reached at ${total:.4f}; nothing written")
    out.append(conv)
(BACKEND / "data/static/demo_conversations.json").write_text(json.dumps(
    {"generated_with": M.pipeline().MODEL, "cost_usd": round(total, 4), "conversations": out}, ensure_ascii=False, indent=1))
print(f"total ${total:.4f}")
