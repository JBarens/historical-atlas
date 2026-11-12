"""Build follow-up eval items (context pairs + inflation computation). Local, no API."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
idx = {int(r[0]): float(r[1]) for r in csv.reader(open(ROOT / "backend/data/reference/cdko.csv"))
       if r and r[0].isdigit() and len(r[0]) == 4}


def conv(amount, year, target=2025):
    return round(amount * idx[target] / idx[year])


pairs = [
    ("mosul", "What was the Mosul dispute about?", "Did Britain accept the League's decision?"),
    ("mosul", "Tell me about the Mosul question after Lausanne.", "What did the government decide about the treaty?"),
    ("upper_silesia", "What happened in the Upper Silesia plebiscite?", "Who got the territory in the end?"),
    ("upper_silesia", "Why were Allied troops stationed in Upper Silesia?", "What was the cost of that, and who paid?"),
    ("vilna", "What was the Vilna dispute?", "Why did the League fail there?"),
    ("aland", "How did the Aaland Islands question reach the League?", "What did the Commission recommend?"),
    ("aland", "Why did the Aaland islanders want to join Sweden?", "Did Finland accept the outcome?"),
    ("greco_bulgarian", "What did Parliament discuss about the League loans to Greece and Bulgaria?", "Did Britain take part?"),
]
items = []
for case, h, q in pairs:
    base = {"question": q, "case": case, "kind": "follow-up"}
    items.append({**base, "history": [],
                  "expected_behaviour": "ask which dispute is meant (or answer briefly per case); no confident single-case answer"})
    items.append({**base, "history": [{"role": "user", "content": h}],
                  "expected_behaviour": f"answer about {case} using retrieved evidence"})

for amount, year, topic in [(600000, 1925, "Mosul"), (2500000, 1921, "Upper Silesia"),
                            (1400000, 1926, "Greek refugee loan"), (250000, 1920, "Aaland")]:
    items.append({
        "kind": "follow-up-computation", "case": None,
        "history": [{"role": "user", "content": f"What did the {topic} commitment cost?"},
                    {"role": "assistant", "content": f"In {year} the figure given in Parliament was £{amount:,}."}],
        "question": "What is that in today's money?",
        "expected": {"amount_gbp": amount, "year": year, "index": "ONS RPI long run (CDKO)",
                     "target_year": 2025, "value": conv(amount, year), "tolerance": 0.05},
        "expected_behaviour": "no retrieval; call the inflation tool with amount and year; name the measure used",
    })

(ROOT / "eval/questions_followup.json").write_text(json.dumps(items, indent=1, ensure_ascii=False))
print(len(items), [(i["expected"]["year"], i["expected"]["value"]) for i in items if "expected" in i])
