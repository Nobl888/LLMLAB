# Telco Churn Wind‑Tunnel (Calibration “Reasoning Floor”)

This document explains a small, real‑data “wind‑tunnel” that lets us compare different churn‑probability generators (LLMs, ML models, heuristics) in a fair, repeatable way. The key idea is simple: every candidate model outputs the same artifact (a probabilities CSV), and we score it with the same evaluator and gates.

## Executive summary (what leaders should know)

- **What this is:** a lightweight, CI‑friendly check that answers: “Are this model’s churn probabilities *useful and well‑calibrated* on real data?”
- **Why it matters:** for retention offers, prioritization, and risk tiers, *confidence* matters. Overconfident wrong predictions are costly.
- **How we compare providers/configs:** each provider/config produces a single probs CSV; we run the same evaluator and compare Brier/NLL + pass/fail gates.

## What it measures (metrics)

Given ground‑truth labels in [LLMLAB/telco_churn.csv](telco_churn.csv) (label column: `Churn` with values `Yes`/`No`), each model produces a probability per row:

- $p_i = P(\text{Churn} = \text{Yes} \mid \text{row } i)$ where $p_i \in [0,1]$

The evaluator computes two proper scoring rules (lower is better):

- **Brier score**: mean squared error between $p_i$ and the true label $y_i\in\{0,1\}$.
  - Rewards both accuracy and calibration (well‑scaled probabilities).
- **NLL (negative log-likelihood / log loss)**: punishes confident wrong predictions sharply.
  - Strongly discourages overconfidence.

Interpretation in plain terms:
- **Brier** rewards probabilities that match reality on average.
- **NLL** heavily penalizes being “very sure” and wrong.

## What’s in the setup (files)

### Ground truth
- [LLMLAB/telco_churn.csv](telco_churn.csv)
- Label: `Churn` (`Yes` => 1, `No` => 0)

### Evaluator / gate (the scoring harness)
- [tools/wind_tunnel_tabular/telco_churn_calibration.py](../tools/wind_tunnel_tabular/telco_churn_calibration.py)
- Built-in baselines:
  - `fixed0.5`: predicts 0.5 for every row
  - `empirical_constant`: predicts the empirical churn rate for every row
  - `overconfident_oracle`: predicts 0.9 for churners and 0.1 for non-churners (cheating stress-test)
- Optional external model:
  - `external_model`: loaded from `--probs-csv ...`

### Dummy external model (example probability generator)
- [tools/wind_tunnel_tabular/make_dummy_telco_probs.py](../tools/wind_tunnel_tabular/make_dummy_telco_probs.py)
- Writes example probabilities to [LLMLAB/telco_dummy_probs.csv](telco_dummy_probs.csv)

## How to run (copy/paste)

Generate dummy probabilities:
- `/home/gouldd5/.venv/bin/python tools/wind_tunnel_tabular/make_dummy_telco_probs.py`

Evaluate baselines + external model:
- `/home/gouldd5/.venv/bin/python tools/wind_tunnel_tabular/telco_churn_calibration.py --probs-csv LLMLAB/telco_dummy_probs.csv`

JSON artifact written to:
- `.llmlab_artifacts/wind_tunnel_tabular/telco_churn_calibration.json`

## The probs CSV contract (external_model)

This is the key “provider/config comparison” interface.

**File format (what the evaluator actually expects today):**
- CSV text file
- First non-empty line is treated as a header and ignored (the header name is not validated)
- Each subsequent non-empty line:
  - The evaluator takes the **first comma-separated field** only
  - Parses it as a float probability
  - Clamps into `[0,1]`

**Hard requirements to be evaluated correctly:**
- Row count must equal the number of usable labels read from [LLMLAB/telco_churn.csv](telco_churn.csv)
  - In practice: exactly one probability per data row, in the same order
- Probabilities must be numeric; avoid NaNs/blank lines

**Recommended shape (simple and human-checkable):**
```csv
p_churn
0.470000
0.160000
0.430000
...
```

**Important operational note (ordering):**
- The current evaluator does **not** join on `customerID`.
- It assumes “row 1 prob corresponds to row 1 label”, etc.

## Current gates (already implemented)

The evaluator enforces two steps per model:

1) **Beat or match `fixed0.5` on both metrics**
- `brier <= brier(fixed0.5)` AND `nll <= nll(fixed0.5)`

2) **Close to `empirical_constant` on both metrics**
- `brier <= brier(empirical_constant) + 0.02`
- `nll <= nll(empirical_constant) + 0.02`

This establishes a minimal “reasoning floor”: models must not be worse than doing-nothing baselines, and must be near a sensible constant reference.

### Example numbers (from a recent run)
From `.llmlab_artifacts/wind_tunnel_tabular/telco_churn_calibration.json`:
- `fixed0.5`: Brier = 0.25, NLL = 0.6931
- `empirical_constant`: Brier = 0.19495, NLL = 0.57860
- `external_model` (dummy heuristic): Brier = 0.16147, NLL = 0.49575

## Recommended additional “business gates” (not currently enforced)

These are optional policies that are easy to explain to non-technical stakeholders.

### Gate A: Meaningful improvement vs empirical_constant

Purpose: avoid shipping complexity that is merely “not worse”.

Concrete rule (choose one of the two variants):

- **A1 (strict):** external_model must improve both metrics by at least:
  - ΔBrier ≤ −0.005 and ΔNLL ≤ −0.005

- **A2 (flexible):** external_model must improve at least one metric by a larger amount:
  - (ΔBrier ≤ −0.010) OR (ΔNLL ≤ −0.010)

Where ΔMetric = Metric(external_model) − Metric(empirical_constant).

Rationale: these are absolute deltas and therefore straightforward to communicate (“at least a 0.01 improvement in log loss”).

### Gate B: Segment safety check (no big regressions on obvious slices)

Purpose: prevent a model that improves overall averages while getting much worse for a business-relevant segment.

Concrete rule:
- For each chosen segment (e.g., `Contract`, `SeniorCitizen`, `InternetService`), external_model must not worsen:
  - Brier by more than +0.010 vs empirical_constant, AND
  - NLL by more than +0.010 vs empirical_constant

Notes:
- This requires computing metrics per segment; if added later, keep segment list short and fixed.
- Choose 3–5 segments maximum to keep CI outputs readable.

## How to use this to compare providers/configs

Treat each provider/config (LLM model, prompt, feature extraction, postprocessing) as a “probability generator” that outputs a single probs CSV for the same dataset.

Process:
1) Run your generator to produce `p_churn` for every row in [LLMLAB/telco_churn.csv](telco_churn.csv)
2) Save it as a CSV following the contract above
3) Run the evaluator with `--probs-csv`
4) Compare the resulting Brier/NLL and gate verdicts across providers/configs

This keeps the comparison fair because:
- All candidates are evaluated on the same labels
- Using proper scoring rules discourages “gaming” via overconfident guesses
- The baselines show whether you’re beating trivial references
