# Bayes From Day 1 (LLMLAB)

This is the simplest way to make “Bayes wind-tunnels” part of LLMLAB from day one **without** leaning on compliance language.
---

## Research Validation (Dec 2025)

LLMLAB's wind-tunnel approach was independently validated by:

> **"The Bayesian Geometry of Transformer Attention"**  
> Aggarwal, Dalal, Misra — arXiv:2512.22471 (Dec 27, 2025)

Key findings from the paper:
- Introduces **"Bayesian wind tunnels"** — controlled environments where the true posterior is known and memorization is provably impossible
- Tests on **HMM state tracking** and **bijection elimination** (both implemented in LLMLAB)
- Transformers reproduce posteriors with **10⁻³–10⁻⁴ bit accuracy**
- MLPs fail by orders of magnitude → clear **architectural separation**

**LLMLAB's position:** We built production-ready CI gates for these tasks *before* the paper. The paper validates the methodology; LLMLAB provides the applied verification layer.

---
## The product shape (what you ship)

**You ship a reliability floor**, not “a paper” and not “a dashboard.”

- Inputs: probabilities (and labels when available)
- Outputs: PASS/FAIL + evidence artifact (JSON) + a tiny summary table
- Delivery: runs locally and in GitHub Actions

## What to run in CI (day 1)

### 1) HMM wind-tunnel (synthetic ground truth)
Purpose: catches **overconfidence** and verifies a model can track uncertainty in a setting where Bayes ground truth exists.

CI gate behavior:
- Bayes mode must PASS
- Overconfident baseline must FAIL

This is wired via:
- `tools/wind_tunnel_bayes/ci_gate_hmm.py`
- GitHub Actions workflow runs it as an offline gate

### 1b) HMM OOD-shift wind-tunnel (synthetic ground truth + change-point)
Purpose: catches **confident-but-wrong drift under distribution shift** by introducing a known change-point in the generative process.

CI gate behavior:
- Bayes-with-shift mode must PASS
- Misspecified filter (assumes pre-shift params forever) must FAIL

This is wired via:
- `tools/wind_tunnel_bayes/ci_gate_hmm_ood_shift.py`

### 1c) Coin-flip wind-tunnel (closed-form Beta-Bernoulli)
Purpose: sanity-checks Bayesian updating in the simplest non-memorizeable setting.

CI gate behavior:
- Bayes mode must PASS
- Fixed-0.5 baseline must FAIL
- Overconfident oracle must FAIL

This is wired via:
- `tools/wind_tunnel_bayes/ci_gate_coin.py`

### 1d) Bijection Elimination wind-tunnel (combinatorial Bayesian elimination)
Purpose: tests whether a system can track posteriors over permutations — the paper's second task.

Based on: arXiv:2512.22471 Section 4.1 (Bijection Elimination)

CI gate behavior:
- Bayes tracker must PASS (exact posterior tracking)
- Uniform baseline must FAIL (ignores observations)
- Random elimination must FAIL (wrong elimination)
- Overconfident tracker must FAIL (premature commitment)

This is wired via:
- `tools/wind_tunnel_bayes/ci_gate_bijection.py`

Why this matters:
- n! bijections → memorization is provably impossible
- Tests combinatorial reasoning, not just sequential updating
- Clear architectural separation (attention vs MLP)

### 2) Telco calibration (real data)
Purpose: sanity check probability quality on a real labeled dataset using Brier/NLL.

CI gate behavior:
- Empirical constant baseline must PASS
- Overconfident-but-wrong baseline must FAIL

This is wired via:
- `tools/wind_tunnel_tabular/ci_gate_telco_churn.py`

## What to say publicly (bold, not cringe)

### One-liner
“LLMLAB adds a reliability floor for probabilistic models: Bayes-style wind-tunnel gates + calibration checks that produce a PASS/FAIL verdict and an evidence pack in CI.”

### Why anyone should care (plain English)
“Accuracy can look fine while a model is dangerously overconfident. We test for that directly and block releases that fail.”

### What makes it different from generic ‘eval platforms’
- “Not a dashboard; it’s a gate.”
- “Not vibes; it emits artifacts you can rerun and file.”
- “Includes synthetic tests with known ground truth, plus real-data calibration.”

## How not to talk (keeps trust)

Avoid:
- “This makes you compliant.”
- “No one else does assurance.”
- “The paper proves everything.”

Prefer:
- “This complements internal validation by producing standardized evidence.”
- “These tests target overconfidence and probability reliability.”

## Research refs (tracking)

Maintain the canonical reference list in:

- `LLMLAB/RESEARCH_REFERENCES.md`

## The sales motion that doesn’t feel pushy

Offer a tiny pilot:
- They send a CSV with `y_true` and `p_hat`
- You return: verdict + evidence JSON + recommendation (thresholding / calibration / ship decision)

Keep it simple: “No integration. One export. Evidence back in a week.”
