# INTERNAL Command Appendix (Do Not Export)

This file is **internal-only**. It is intentionally not included in export-safe recaps.

Purpose:
- One place to copy/paste the most common dev/CI reproduction commands
- Keep operational muscle memory close to the "Day 1 Bayes" and Topology/Probes work

---

## A) Canonical CI-equivalent offline run

Run the full offline portfolio (GOLD scope):

```bash
python tools/gate_portfolio/run_offline_gate_portfolio.py --mode gold
```

Append a per-run history CSV (best treated as an artifact unless persisted):

```bash
python tools/gate_portfolio/append_portfolio_history.py
```

Generate the single-pane assurance report:

```bash
python tools/assurance_report/generate_assurance_report.py
```

---

## B) Bayes wind-tunnel gates (Day 1 suite)

HMM:

```bash
python tools/wind_tunnel_bayes/ci_gate_hmm.py
```

HMM OOD-shift:

```bash
python tools/wind_tunnel_bayes/ci_gate_hmm_ood_shift.py
```

HMM OOD-shift WITH FP hygiene (CI-friendly defaults; will emit FP artifacts):

```bash
python tools/wind_tunnel_bayes/ci_gate_hmm_ood_shift.py --with-fp-hygiene
```

Coin (Beta–Bernoulli):

```bash
python tools/wind_tunnel_bayes/ci_gate_coin.py
```

Bijection elimination:

```bash
python tools/wind_tunnel_bayes/ci_gate_bijection.py
```

---

## C) OOD-shift sensitivity (research, artifact-first)

Small sanity sweep:

```bash
python tools/wind_tunnel_bayes/sweep_hmm_ood_shift_sensitivity.py \
  --deltas 0,0.5,1.0 \
  --shift-fracs 0.5 \
  --sequences 20 \
  --length 80
```

Analyze into frontier + certification blocks:

```bash
python tools/wind_tunnel_bayes/analyze_hmm_ood_shift_sensitivity.py
```

Summarize to CSV (plotting-friendly):

```bash
python tools/wind_tunnel_bayes/summarize_hmm_ood_shift_sensitivity_to_csv.py
```

---

## D) QQQ canonical indicators (oracle + PASS-only topology)

Build oracles (all 5 canonical indicators):

```bash
python tools/qqq_canonical_indicators/build_oracles.py --input qqq_clean.csv \
  --indicator sma20 --indicator rsi14 --indicator bb20_2 --indicator atr14 --indicator composite_v1
```

Run validator against example candidates for each indicator:

```bash
for ind in sma20 rsi14 bb20_2 atr14 composite_v1; do
  python tools/qqq_canonical_indicators/runner.py \
    --indicator "$ind" \
    --candidates-dir tasks/qqq_canonical_indicators/example_candidates \
    --tolerance 1e-12
done
```

Summarize PASS-only topology (families + AST structural diversity):

```bash
python tools/qqq_canonical_indicators/summarize_topology.py
```

Plot topology curves as dependency-free SVG:

```bash
python tools/qqq_canonical_indicators/plot_topology_svg.py
```

Run topology CI gate (demo thresholds; tune for real corpora):

```bash
python tools/qqq_canonical_indicators/ci_gate_topology.py \
  --temperature 0.3 \
  --min-indicators-covered 5 \
  --min-pass-for-floors 5 \
  --min-effective-families 2.0 \
  --min-ast-diversity 0.2
```

---

## E) Representation probes (Frontier 2 plumbing)

Smoke test (generates synthetic dataset → probe summary → heatmap → assurance report):

```bash
python tools/representation_probes/run_probe_smoketest.py --regen-assurance
```

Train on a real extracted dataset (JSONL):

```bash
python tools/representation_probes/train_family_probe.py \
  --dataset-jsonl .llmlab_artifacts/representation_probes/family_probe_dataset.jsonl \
  --output-json .llmlab_artifacts/representation_probes/probe_summary.json
```

Plot SVG heatmap:

```bash
python tools/representation_probes/plot_probe_heatmap_svg.py \
  --probe-summary .llmlab_artifacts/representation_probes/probe_summary.json \
  --output-svg .llmlab_artifacts/representation_probes/probe_heatmap.svg
```

Entropy PC1 manifold gate (Misra et al. inspired):

```bash
python tools/representation_probes/ci_gate_entropy_pc1.py \
  --dataset-jsonl .llmlab_artifacts/representation_probes/family_probe_dataset.jsonl \
  --layer 12 \
  --pc1-threshold 0.35 \
  --entropy-alignment-threshold 0.55
```

---

## F) Polymarket quant demo (cron → signals CSV → manual backtests)

One-command wrapper (recommended):

```bash
bash tools/polymarket/quant_demo_pipeline.sh
```

Refresh outcomes in the same run (use on Wed/Fri or weekly):

```bash
DO_RESOLVE=1 bash tools/polymarket/quant_demo_pipeline.sh
```

Artifacts:
- `quant_edge_YYYYMMDD.json` (and symlink `quant_edge.json`)
- `.llmlab_artifacts/polymarket/signals_YYYYMMDD.csv` (and symlink `signals_latest.csv`)
- `.llmlab_artifacts/polymarket/entropy_manifold_gate_YYYYMMDD.json` (manifold cert)

Watch metrics (jq):

```bash
jq -r '.headline | {n_signals, vol_worst_bias, vol_worst_bucket_id, js_divergence}' quant_edge.json
```

Entropy manifold gate (Misra et al. inspired — standalone):

```bash
python tools/polymarket/ci_gate_polymarket_entropy.py \
  --input-csv gamma_llmlab.csv \
  --pc1-threshold 0.30 \
  --entropy-alignment-threshold 0.50
```

Watch manifold cert:

```bash
jq -r '"manifold: \(.summary.verdict) pc1=\(.summary.pc1_variance_explained) calib_gap=\(.summary.calibration_gap_by_pc1_residual // "null")"' \
  .llmlab_artifacts/polymarket/entropy_manifold_gate.json
```

Signals CSV schema (minimal export):
- `market_id,snapshot_ts,vol_bucket,entropy_bucket,prob_yes,resolution,bias`
- Buckets are **1..5** by default.

Paste-ready crontab (daily snapshot + Wed/Fri resolve):

```cron
0 9 * * * cd /home/gouldd5 && bash tools/polymarket/quant_demo_pipeline.sh >> logs/polymarket_quant.log 2>&1
15 9 * * 3,5 cd /home/gouldd5 && DO_RESOLVE=1 bash tools/polymarket/quant_demo_pipeline.sh >> logs/polymarket_quant.log 2>&1
```
```
