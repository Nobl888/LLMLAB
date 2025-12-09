You're starting to use LLMs to help with queries, pipelines, or strategy code, and they speed things up—until it's time to be sure the numbers are actually right. A lot of the work still ends up as careful checking and reruns, even when the code came from an "AI assistant."

This lab treats LLMs, IDEs, and agents as **stochastic code generators inside a controlled experiment**. For each deterministic task, the lab defines a spec, builds a trusted oracle, generates multiple implementations, and validates every result against the oracle with strict numeric checks. The outcome is simple: you know which variants are correct, how fast they run, and whether several independent implementations agree.

---

## What this lab does

For any deterministic task (backtest, BI metric, ETL job), the lab runs the same pattern:

1. **Task spec**  
   Describe inputs, outputs, constraints, temperatures, and validation rules in YAML.

2. **Oracle**  
   Implement a deterministic reference or use a gold‑standard output as the ground truth.

3. **Variants**  
   Generate multiple implementations (often via LLMs) across temperatures and constraint profiles.

4. **Deterministic validation**  
   Compare each variant's output to the oracle with strict tolerances.  
   Log pass/fail, numeric diffs, and runtime to CSV.

5. **KPI summary**  
   Produce `summary.json` and `summary.md` per task with:  
   - total variants, pass rate  
   - baseline vs fastest‑passing runtime  
   - list of passing variants and their speeds.

This pattern is **framework‑agnostic**: it works regardless of which model, IDE, or agent framework generated the code.

---

## Current example tasks

### QQQ SMA strategy (finance)

- Long‑only SMA(20/50) crossover on daily QQQ prices (2001–2025).  
- 92 strategy variants tested; 72 passed strict oracle checks (≈78.3% pass rate).  
- Fastest passing variant runs ≈58.1% faster than the baseline while matching the oracle to machine precision.

Artifacts: `results/qqq/summary.json`, `results/qqq/summary.md`.

### Ecommerce customer–country metrics

- Aggregates 541,909 ecommerce transactions into 4,389 customer–country pairs.  
- 5 implementation variants; 4 passed oracle checks (80% pass rate).  
- Fastest passing variant delivers ≈16.2% speedup vs baseline with exact numeric match on all aggregates.

Artifacts: `results/ecommerce/summary.json`, `results/ecommerce/summary.md`.

### Daily events analytics

- Computes daily active users, signups, purchases, and retention from raw event logs.  
- Baseline implementation validated against a deterministic oracle with 100% match (max absolute difference 0.0 across all metrics).

Artifacts: events task spec + oracle + validator scripts (kept internal for now).

---

## Who this is for

This lab is aimed at people who:

- Own a **deterministic pipeline and metric** (finance, BI, risk, ecommerce, ops).  
- Are already using (or considering) **LLM‑generated code / agents / smart IDEs** to change that pipeline.  
- Want a **framework‑agnostic way** to test and compare implementations before they touch production.

If there is a concrete metric, a sample dataset, and a golden output (or a clear way to build one), this pattern can be adapted to that case.

---

## What we offer right now

If you have one deterministic metric (backtest, BI metric, ecommerce report) and a golden output, we can run a one‑off lab on it and send back a simple report: how many AI‑generated variants passed, and how much faster the best correct one is than your baseline.

---

## If you're interested

If you:

- Have one critical metric or backtest you'd like to validate, and  
- Want to see whether this lab pattern fits,

open an issue briefly describing:

- your domain,  
- the metric or report you care about,  
- whether you have a trusted "golden" output today.

The current focus is on real pipelines, not general experimentation or student projects.

---

Thanks for reading. If this sounds close to the pain you're feeling with AI‑generated pipelines, and you have one real metric you'd like to test, feel free to reach out or open an issue.
