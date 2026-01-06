# Research R&D — Next Direct Tests (OOD-shift + Temperature/Family Topology)

Created: 2026-01-03

This doc converts the Dec-31 research/R&D prompts into **direct, runnable next tests**. It focuses on:
- **OOD-shift sensitivity** (how much prior/parameter change is needed before detection)
- **Temperature ↔ algorithm family mapping** (QQQ solver diversity across $T$)
- **Topology mapping** (difficulty × temperature × family)

Scope: export-safe framing; implementation details stay deterministic/offline unless explicitly marked.

---

## 0) Canonical starting points (existing work)

- Bayes wind-tunnel overview + what is already wired into CI:
  - [LLMLAB/BAYES_FROM_DAY1.md](BAYES_FROM_DAY1.md)
  - HMM OOD-shift wind-tunnel implementation: [tools/wind_tunnel_bayes/hmm_ood_shift_wind_tunnel.py](../tools/wind_tunnel_bayes/hmm_ood_shift_wind_tunnel.py)
  - CI gate: [tools/wind_tunnel_bayes/ci_gate_hmm_ood_shift.py](../tools/wind_tunnel_bayes/ci_gate_hmm_ood_shift.py)

- Temperature sweep + family classification:
  - Workflow guide: [README_COMPLETE_WORKFLOW.txt](../README_COMPLETE_WORKFLOW.txt)
  - Results write-up: [TEMPERATURE_SWEEP_RESULTS.md](../TEMPERATURE_SWEEP_RESULTS.md)
  - Family classifier: [classify_families_ast.py](../classify_families_ast.py)
  - Topology summary helper: [tools/generate_topology_summary.py](../tools/generate_topology_summary.py)

---

## 1) OOD-shift sensitivity (HMM) — what to measure, exactly

### Goal
Go beyond “PASS/FAIL”: quantify **when** shift becomes detectable and how robust detection is under configuration choices.

### Ground-truth setting
Use a known change-point $t_0$ where the generative parameters change. Evaluate filters against known latent states and known generative params.

### Primary metric (recommendation)
Report both:
- **Filtering quality:** mean KL divergence (or NLL) between predicted state posterior and true state posterior across time.
- **Shift detection signal:** a scalar score per timestep (e.g., Bayes factor / log-likelihood ratio between pre-shift model and a model with shift).

A simple, defensible definition:
- Define a shift score $S_t$ (monotone): $S_t = \log p(x_{1:t} \mid \text{shift}) - \log p(x_{1:t} \mid \text{no-shift})$.
- Declare “detected” at first time $t$ where $S_t \ge \tau$.

### What is “the threshold”?
We need $\tau$ such that false alarms are rare.

Protocol:
1) Generate many **no-shift** sequences (control) → compute max score $\max_t S_t$.
2) Choose $\tau$ so control false positive rate is <= 1% (or 0.1% for stricter).
3) On shifted sequences, measure:
   - detection rate (TPR)
   - detection delay (median $t_{detect} - t_0$)

This yields a clean “at what prior change does detection work?” curve.

---

## 2) OOD-shift sensitivity sweep — concrete experiment matrix

### Variables to sweep
Minimum useful sweep (keeps runtime reasonable):
- **Shift magnitude** $\Delta$:
  - emission mean shift (Gaussian emissions) or
  - transition matrix perturbation magnitude or
  - prior over states perturbation magnitude
- **Change-point location** $t_0$ (e.g., 25%, 50%, 75% of sequence)
- **Sequence length** $T$ (e.g., 100, 300, 1000)

Suggested grid (start small):
- $\Delta \in \{0.0, 0.25, 0.5, 0.75, 1.0\}$ (or an equivalent normalized scale)
- $t_0/T \in \{0.33, 0.5, 0.66\}$
- $T \in \{200, 500\}$
- seeds: 100 per cell

### Outputs to produce (evidence-friendly)
For each cell, output a single JSON summary:
- config (Δ, t0, T, seed count)
- chosen threshold τ (from controls)
- TPR, FPR, median delay
- mean KL/NLL pre/post shift

This is “research-grade” but still artifact-first.

Copy/paste runner (small sanity run):

```bash
python tools/wind_tunnel_bayes/sweep_hmm_ood_shift_sensitivity.py \
  --deltas 0,0.5,1.0 \
  --shift-fracs 0.5 \
  --sequences 20 \
  --length 80
```

Convert the JSON summary to a plotting-friendly CSV:

```bash
python tools/wind_tunnel_bayes/summarize_hmm_ood_shift_sensitivity_to_csv.py
```

---

## 3) Does temperature affect detection sensitivity?

Two interpretations (pick one depending on what you can run):

### A) Model-temperature (probability sharpening/flattening) — offline, deterministic
If you don’t have access to internal model sampling at inference time, you can still study *calibration temperature*:
- Take a baseline posterior $p(z_t)$ and apply temperature scaling:
  $$p_T(z_t) \propto p(z_t)^{1/T}$$
- Study how detection thresholding behaves as $T$ varies.

This answers: “How sensitive is shift detection to over/underconfidence?”

### B) LLM sampling temperature — requires generating candidates
If you are testing an LLM’s *produced* filter/tracker across decoding temperatures:
- For fixed prompts/tasks, generate outputs at $T_{LLM} \in \{0.2, 0.4, 0.7, 1.0, 1.3\}$
- Convert outputs into comparable probability traces
- Evaluate using the same shift-score and threshold protocol above

This answers: “Does creative sampling make the model less reliable under shift?”

---

## 4) Can we predict detection from internal representations?

This requires model internals (hidden states/attn) from a local model.

Minimum viable probing study:
- Data: per-token/per-timestep hidden state vectors $h_t$ from the model while it emits $p(z_t)$ (or a structured trace)
- Label: “shift detected within next K steps” or “OOD present”
- Probe: logistic regression / linear SVM
- Report: AUC + calibration curve + stability across seeds

If you **don’t** have internals, skip probing and focus on observable traces (probabilities + entropy + margin).

---

## 5) Temperature sweep analysis — formal clustering of QQQ families

### Goal
Convert the existing family classifier outputs into a **clustering story** across full temperature range.

### Inputs
From your sweep logs/artifacts:
- algorithm family label (AST-based)
- runtime
- max numeric error
- constraint profile
- temperature

### Feature set (simple but effective)
- One-hot family label
- normalized runtime
- log10(max_error + eps)
- constraint profile categorical

Optionally add:
- AST node histogram (counts of key nodes/calls) as a vector embedding

### Outputs
- Heatmap: P(family | temperature, profile)
- Cluster map: family clusters across temperature (e.g., hierarchical clustering)
- “Family transition points”: temperatures where distribution shifts materially

---

## 6) Implementation-space topology (difficulty × temperature × family)

### Define “difficulty” in a way that’s measurable
A defensible composite difficulty score could be:
- constraints severity (ordinal, from profile)
- % of candidates failing correctness
- median runtime (or runtime penalty)

### Deliverable
A CI-friendly artifact (no proprietary code):
- CSV/JSON with rows:
  - temp, profile, family, pass_rate, median_runtime, median_error
- Optional 3D plot generation stays local; CI can upload just the table.

---

## 7) New wind-tunnel tasks (roadmap, not required for next test pass)

These are “next tasks” once sensitivity curves exist:

- **Gaussian HMM wind-tunnel** (continuous emissions):
  - objective: posterior tracking under continuous noise
  - shift modes: mean shift, variance shift

- **POMDP / partial observability**:
  - objective: belief-state tracking when observations are aliased

Key: define one scalar PASS/FAIL gate first, then graduate to sensitivity analysis.

---

## 8) Recommended next 48-hour direct test plan

1) Run the **OOD-shift sensitivity sweep** (small grid, 100 seeds/cell) and emit JSON summaries.
2) Choose a threshold protocol (control FPR <= 1%) and publish the TPR/delay curves.
3) For QQQ, produce:
   - P(family | temperature, profile)
   - one “transition temperature” summary
4) Only then decide whether to build:
   - deeper probing (requires internals)
   - Gaussian HMM / POMDP extensions
