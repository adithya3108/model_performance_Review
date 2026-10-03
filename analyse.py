# Run with:  python analyse.py
# (Python 3.8+, standard library only. Run from the folder containing the CSV files.)
#
# Re-scores results.csv after fixing three problems in score.py's measurement:
#   1. answer_key.csv has wrong expected answers for some questions
#      -> recompute every expected answer from the question text itself.
#   2. Some questions appear twice under different IDs
#      -> keep the first ID of each duplicate group, drop the rest.
#   3. score.py needs response == expected exactly, so "2,779", "**2779**",
#      "The answer is 2,779." all count as wrong
#      -> take the last number in the response (commas removed) as the answer.
import csv
import random
import re
from collections import defaultdict

OPS = {"+": lambda a, b: a + b, "-": lambda a, b: a - b, "×": lambda a, b: a * b}


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


questions = {r["question_id"]: r["question"] for r in read("questions.csv")}
key = {r["question_id"]: r["expected"].strip() for r in read("answer_key.csv")}
results = read("results.csv")


# --- 1. wrong answer key -------------------------------------------------------
def true_answer(text):
    m = re.fullmatch(r"What is (\d+) (\S) (\d+)\?", text.strip())
    return str(OPS[m[2]](int(m[1]), int(m[3])))


correct_key = {qid: true_answer(q) for qid, q in questions.items()}
wrong_key_ids = sorted(q for q in questions if key[q] != correct_key[q])

# --- 2. duplicate questions ----------------------------------------------------
first_id = {}
duplicate_ids = []
for qid in sorted(questions):
    text = " ".join(questions[qid].split())
    if text in first_id:
        duplicate_ids.append(qid)
    else:
        first_id[text] = qid
unique_ids = sorted(set(questions) - set(duplicate_ids))


# --- 3. lenient answer extraction ----------------------------------------------
def extract(response):
    nums = re.findall(r"-?\d[\d,]*", response)
    return nums[-1].replace(",", "") if nums else None


# --- scoring -------------------------------------------------------------------
def score(model, expected, ids, parse):
    rows = [r for r in results if r["model"] == model and r["question_id"] in ids]
    hits = sum(parse(r["response"]) == expected[r["question_id"]] for r in rows)
    return hits, len(rows)


def pct(h, n):
    return f"{100 * h / n:.1f}% ({h}/{n})"


models = sorted({r["model"] for r in results})
temps = {m: sorted({r["temperature"] for r in results if r["model"] == m}) for m in models}
strict = lambda s: s.strip()
all_ids = set(questions)

print("Settings per model (temperature):", temps)
print("Wrong answer-key IDs:", ", ".join(wrong_key_ids))
for q in wrong_key_ids:
    print(f"  {q}: {questions[q]}  key says {key[q]}, correct is {correct_key[q]}")
print("Duplicate question IDs (dropped):", ", ".join(duplicate_ids))
for q in duplicate_ids:
    print(f"  {q} repeats {first_id[' '.join(questions[q].split())]}")
print()

steps = [
    ("A. original score.py", key, all_ids, strict),
    ("B. + fixed answer key", correct_key, all_ids, strict),
    ("C. + lenient number parsing", correct_key, all_ids, extract),
    ("D. + duplicates removed  (FINAL)", correct_key, set(unique_ids), extract),
]
for name, exp, ids, parse in steps:
    print(f"{name:36s}", "  ".join(f"{m}: {pct(*score(m, exp, ids, parse)):18s}" for m in models))
print()

# Per-run accuracy (final scoring) to show run-to-run spread.
ok = defaultdict(dict)  # ok[model][(run, qid)] = 1/0
for r in results:
    if r["question_id"] in unique_ids:
        ok[r["model"]][(r["run"], r["question_id"])] = int(
            extract(r["response"]) == correct_key[r["question_id"]]
        )
runs = sorted({r["run"] for r in results})
for m in models:
    per_run = [100 * sum(ok[m][(k, q)] for q in unique_ids) / len(unique_ids) for k in runs]
    print(f"{m} per-run accuracy:", ", ".join(f"run {k}: {v:.1f}%" for k, v in zip(runs, per_run)))

# Per-question accuracy (mean over runs) -> paired comparison on the 50 questions.
qacc = {m: {q: sum(ok[m][(k, q)] for k in runs) / len(runs) for q in unique_ids} for m in models}
a, b = models
diffs = [qacc[a][q] - qacc[b][q] for q in unique_ids]
print(f"\nDifference {a} - {b}: {100 * sum(diffs) / len(diffs):+.1f} points")
print(f"Questions where {a} better / {b} better / tie:",
      sum(d > 0 for d in diffs), "/", sum(d < 0 for d in diffs), "/", sum(d == 0 for d in diffs))

# Bootstrap over questions (questions are the unit of sampling; runs are nested).
random.seed(0)
boot = []
for _ in range(10000):
    s = [random.choice(diffs) for _ in diffs]
    boot.append(100 * sum(s) / len(s))
boot.sort()
print(f"95% bootstrap CI for the difference: [{boot[249]:+.1f}, {boot[9749]:+.1f}] points "
      f"(10,000 resamples of the {len(unique_ids)} questions, seed 0)")

# Sign-flip permutation test on the paired per-question differences.
obs = abs(sum(diffs))
nz = [d for d in diffs if d != 0]
extreme = sum(abs(sum(d if random.random() < 0.5 else -d for d in nz)) >= obs - 1e-12
              for _ in range(10000))
print(f"Paired permutation test p-value: {extreme / 10000:.3f}")

# Error breakdown by operation (final scoring).
print("\nAccuracy by operation:")
for op in OPS:
    ids = [q for q in unique_ids if f" {op} " in questions[q]]
    label = "x" if op == "×" else op  # plain ASCII so every console can show it
    print(f"  {label} ({len(ids)} questions): " + "  ".join(
        f"{m}: {100 * sum(qacc[m][q] for q in ids) / len(ids):.1f}%" for m in models))

# How much of model-b's original loss was only formatting?
fmt = sum(1 for r in results if r["model"] == b and r["question_id"] in unique_ids
          and r["response"].strip() != extract(r["response"]))
print(f"\n{b} responses that are not a bare number: {fmt}; "
      f"{a}: {sum(1 for r in results if r['model'] == a and r['response'].strip() != extract(r['response']))}")
