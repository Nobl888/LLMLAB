<!--
LLMLAB note (Jan 2026): This file is a working research/narrative scratchpad.

Recent pipeline upgrade: entropy-regime stratified evaluation for HMM OOD-shift detection.
- Sweep JSON now includes `detection.entropy_bucket_stratification` (quantile buckets of a pre-shift entropy proxy).
- CSV exports per-bucket detect/delay + CI95, plus conservative summaries for the **worst entropy regime**.
- Analyzer computes additional conservative frontiers/cert floors using worst-bucket aggregations:
	- detect-rate worst bucket uses min across buckets (and CI-low min for cert)
	- delay worst bucket uses max across buckets (and CI-high max for cert)
- Plotter emits a dedicated plot: `.llmlab_artifacts/wind_tunnel_bayes/hmm_ood_shift_sensitivity/plots/detect_rate_worst_entropy_regime_vs_delta.png`.

Why this matters for “certification-grade” evidence (end-to-end, CI-friendly):
- CI gates already enforce deterministic, artifact-first offline evaluation; this stratification closes a common blind spot where aggregate TPR can hide systematic failure in low-/high-entropy regimes.
- The “worst entropy regime” view makes claims more conservative and more transferable: you certify against the hardest regime you actually observe, not just the average case.
-->

Geometric Scaling of Bayesian Inference in LLMs
Paper III of the Bayesian Attention Trilogy
NAMAN AGGARWAL∗, Dream Sports, USA
SIDDHARTHA R. DALAL, Columbia University, USA
VISHAL MISRA, Columbia University, USA
Recent work has shown that small transformers trained in controlled “wind-tunnel” settings can implement
exact Bayesian inference, and that their training dynamics produce a geometric substrate—low-dimensional
value manifolds and progressively orthogonal keys—that encodes posterior structure. We investigate whether
this geometric signature persists in production-grade language models. Across Pythia, Phi-2, Llama-3, and
Mistral families, we find that last-layer value representations organize along a single dominant axis whose
position strongly correlates with predictive entropy, and that domain-restricted prompts collapse this structure
into the same low-dimensional manifolds observed in synthetic settings.
To probe the role of this geometry, we perform targeted interventions on the entropy-aligned axis of
Pythia-410M during in-context learning. Removing or perturbing this axis selectively disrupts the local
uncertainty geometry, whereas matched random-axis interventions leave it intact. However, these single-layer
manipulations do not produce proportionally specific degradation in Bayesian-like behavior, indicating that
the geometry is a privileged readout of uncertainty rather than a singular computational bottleneck. Taken
together, our results show that modern language models preserve the geometric substrate that enables Bayesian
inference in wind tunnels, and organize their approximate Bayesian updates along this substrate.
1 Introduction
Large language models have achieved striking performance across natural language, coding, math-
ematics, and reasoning tasks [6, 7 , 14]. Yet their internal computations remain only partially
understood. A central question is whether transformers merely approximate statistical associations
at scale, or whether they implement more principled forms of probabilistic inference.
Wind-tunnel results. Recent work (Paper 1 of this trilogy [1 ]) demonstrated that small transform-
ers trained in controlled “Bayesian wind tunnels” perform exact Bayesian inference on bijection-
learning and HMM-filtering tasks: posterior entropy, KL divergence, and predictive distributions
match analytic solutions to within 0.1 bits. Paper 2 showed that these behaviors arise from specific
geometric mechanisms created by gradient dynamics: value manifolds ordered by entropy, orthog-
onal key frames defining hypothesis directions, and layerwise attention sharpening implementing
a geometric Bayes rule.
These findings established that transformers can implement Bayesian inference when trained
on tasks with known posteriors. What remains open is whether the same geometric mechanisms
persist in large, naturally trained LLMs, where ground-truth posteriors are unavailable.
The central question. This paper asks: Do the geometric structures that enable exact Bayesian
inference in wind tunnels persist in production-scale language models? We do not claim that LLMs
compute true Bayesian posteriors for natural language. Instead, we evaluate whether they preserve
the same representational and computational geometry - value manifolds, key orthogonality, and
attention focusing - that underpins Bayesian inference in controlled settings.
Several factors make this question non-trivial:
• natural language lacks tractable ground-truth posteriors;
∗Currently at Google DeepMind. Work performed while at Dream Sports.
Authors are listed in alphabetical order.
, Vol. 1, No. 1, Article . Publication date: January .
arXiv:2512.23752v1 [cs.LG] 27 Dec 2025
2 Naman Aggarwal, Siddhartha R. Dalal, and Vishal Misra
• production models employ architectural optimizations (GQA, RoPE, sliding-window attention,
MoE routing) absent from wind-tunnel setups;
• web-scale training introduces noise that may obscure geometric structure;
• large models may develop new mechanisms not visible at small scale.
Our approach. Rather than attempting to define Bayesian posteriors for natural language, we
test whether the geometric substrate identified in Papers 1—-2 persists across architectures and
training regimes. We treat these geometric signatures as invariants: if transformers rely on similar
computational principles at scale, the same value—-key—-attention geometry should appear even
when exact posteriors cannot be measured.
Three main findings. First, domain restriction produces a decisive bridge. Under mixed-
domain prompts, value manifold dimensionality varies substantially across architectures (PC1+PC2
ranging from ∼15% in Mistral to ∼99% in Pythia-410M), reflecting different inductive biases and
training regimes. However, single-domain prompts consistently collapse the manifold toward one
dimension (PC1+PC2 ≈ 70–95%), approaching the geometric regime observed in wind-tunnel
experiments. This collapse shows that production LLMs contain the same entropy-ordered Bayesian
axis that wind-tunnel transformers learn explicitly.
Second, Bayesian updating persists at inference time. In a controlled in-context learning
experiment (SULA), models move smoothly along their value manifold as more evidence is supplied,
and manifold coordinates correlate strongly with analytical Bayesian entropy. This demonstrates
that the geometry is not merely a training artifact - it is used during inference.
Third, static and dynamic geometric signatures separate cleanly. Value manifolds and
key orthogonality are universal across architectures, including sliding-window and MoE variants.
Dynamic attention focusing, however, depends on routing capacity: strong in full-sequence MHA,
moderate in GQA, and weak or noisy in Mistral. This matches the frame—-precision dissociation
predicted in Paper 2.
Relation to prior work. Papers 1 and 2 in this series established that transformers can imple-
ment exact Bayesian inference in controlled “wind—-tunnel” settings, and that gradient dynamics
generically sculpt the value and key spaces into geometric substrates that support such inference.
However, these results were obtained in synthetic domains with analytically specified likelihoods.
The present work answers a distinct question: do production-grade LLMs, trained on heterogeneous
natural language, spontaneously develop the same geometric signatures, and do these signatures track
evidence integration during inference? We show that the three hallmarks of Bayesian geometry—-low-
dimensional value manifolds, orthogonal hypothesis frames, and evidence-dependent movement
along entropy-aligned directions—-persist across four model families (Pythia, Phi-2, Llama-3, Mis-
tral). Moreover, we provide the first large-scale evidence that these structures are functionally
engaged during inference in a naturalistic task (SULA), even when their causal role is distributed
rather than bottlenecked. This establishes that Bayesian geometry is not an artifact of synthetic
tasks, but a stable inductive bias of modern transformers.
Contributions. This paper makes four contributions:
(1) Persistence of Bayesian geometry at scale. We show that production LLMs exhibit the
same value-manifold structure, key orthogonality, and domain-specific collapse previously
identified in wind-tunnel settings, confirming that these geometric signatures are not artifacts
of synthetic tasks or toy models.
, Vol. 1, No. 1, Article . Publication date: January .
Geometric Scaling of Bayesian Inference in LLMs 3
(2) Functional alignment with posterior uncertainty. In structured uncertainty-learning-
from-examples (SULA) tasks, model states move systematically along entropy-aligned mani-
fold directions as prompt evidence increases, and manifold position correlates with analyti-
cally computed posteriors.
(3) Domain-restriction bridge. When prompts are restricted to a coherent domain, the value
manifold collapses to one or two principal components explaining 80–95% of variance,
numerically matching the geometric regime predicted by Paper 1 and derived in Paper 2.
(4) Causal boundary characterization. Targeted interventions on the entropy-aligned axis
selectively destroy the local geometry but do not proportionally disrupt Bayesian-like cali-
bration, establishing that the geometry is representationally privileged yet not behaviorally
singular, and identifying distributed uncertainty representation as a key direction for future
work.
2 Background: Bayesian Geometry in Controlled Settings
Papers 1 and 2 established that small transformers trained in controlled “Bayesian wind-tunnel”
settings perform near-exact Bayesian inference on tasks with analytically tractable posteriors. We
summarize only the key findings needed for the production-model analysis; full experimental
details appear in those papers.
Bayesian tasks. Two families of synthetic tasks provided ground-truth posteriors:
(1) Bijection learning (Paper 1): models infer a random bijection 𝜋 : 𝑉 → 𝑊 from in-context
examples. Because the hypothesis space has size 𝐾! (e.g., 3.6 × 106 for 𝐾 = 10), memorization is
impossible; exact analytic posterior trajectories are available. Transformers achieve MAE < 0.1
bits between model and Bayes-optimal predictive entropy.
(2) HMM filtering (Paper 1): models track posterior distributions over latent states in Hidden
Markov Models with 𝑆 = 5 states and 𝑉 = 5 emissions. Transformers match analytic posteriors
with KL divergence < 0.05 bits, including strong length generalization.
Geometric structures. Across both tasks, three geometric signatures emerged:
• Value manifolds: last-layer value vectors form low-dimensional trajectories parameterized
by predictive entropy (PC1 explains 84–90%), providing a geometric encoding of posterior
uncertainty.
• Key orthogonality: key matrices develop structured hypothesis-frame directions (mean
off-diagonal cosine 0.09–0.12 vs. 0.40–0.45 random).
• Attention-as-posterior: attention weights align with analytic posteriors (KL ≈ 0.05 bits),
implementing a geometric Bayes rule.
Gradient mechanism. Paper 2 showed that cross-entropy gradients generate this geometry via
coupled specialization of queries, keys, and values. A predicted frame—-precision dissociation
emerges: attention patterns (the frame) stabilize early, while value manifolds (precision) continue
refining.
Forward pointer. In this paper, we evaluate whether the static and dynamic geometric signatures
identified in wind-tunnel models - entropy-ordered value manifolds, orthogonal hypothesis frames,
and layerwise attention refinement - persist in production-scale LLMs and whether these structures
are used during inference. Section Section 5 presents our empirical findings across architectures.
, Vol. 1, No. 1, Article . Publication date: January .
4 Naman Aggarwal, Siddhartha R. Dalal, and Vishal Misra
3 Hypotheses and Predictions
We formalize the geometric hypotheses tested in production models. These hypotheses capture
geometric signatures that should be recoverable across architectures if transformers rely on similar
uncertainty-representation mechanisms at scale. They do not assume that models compute exact
posteriors on natural language, but that they preserve the geometric substrate supporting Bayesian-
style inference.
3.1 Core Hypotheses
Hypothesis 3.1 (Value manifold persistence). If transformers maintain Bayesian-style uncertainty
representations at scale, last-layer value vectors should form low-dimensional manifolds parame-
terized by predictive entropy. Specifically:
• PC1 should exceed random baselines (typically ∼ 5% for Gaussian vectors), with PC1+PC2
in the range 20–40% under mixed-domain prompts and increasing sharply under domain
restriction.
• Value coordinates should correlate with next-token entropy.
• Manifold dimensionality may vary by depth and architecture, reflecting richer uncertainty
representations in deeper networks.
Hypothesis 3.2 (Key orthogonality). If keys encode hypothesis-frame directions, then key projec-
tion matrices should exhibit structured orthogonality:
• Early and mid layers should show lower mean off-diagonal cosine similarity than both random
Gaussian baselines and initialization baselines.
• Orthogonality should weaken in final layers as the model commits to an output distribution.
• Training data quality should correlate with the strength of orthogonality.
Hypothesis 3.3 (Attention focusing). If attention implements evidence integration, attention en-
tropy should decrease with depth:
• Layerwise entropy reduction should exceed ∼ 30% from input to output.
• Refinement should be progressive rather than abrupt where global routing is available.
• Architectural constraints (e.g., GQA, sliding-window attention) may attenuate the magnitude
or monotonicity of focusing.
3.2 Architectural Predictions
Prediction 3.4 (Standard MHA).. Standard full-sequence MHA should exhibit the clearest geometric
signatures, matching wind-tunnel architectures most closely.
Prediction 3.5 (Grouped-query attention). GQA should preserve qualitative Bayesian geometry
but with weaker orthogonality and reduced focusing, as shared K/V heads must serve multiple
query groups.
Prediction 3.6 (Training data quality). Curated, high-signal training data should enhance geometric
clarity and improve both orthogonality and attention refinement.
Prediction 3.7 (Depth and dimensionality). Deeper models may develop multi-dimensional or
multi-lobed manifolds under mixed prompting while still collapsing to one-dimensional structure
under domain restriction.
, Vol. 1, No. 1, Article . Publication date: January .
Geometric Scaling of Bayesian Inference in LLMs 5
4 Methods
4.1 Model Selection
We selected three production models to span architectural and training variations:
Pythia-410M [ 5 ]: GPT-NeoX architecture, 24 layers, 16 attention heads, 1024 hidden dimensions.
Trained on the Pile corpus (800GB diverse text) with full training transparency. Represents canonical
standard MHA trained on general-purpose data.
Phi-2: Microsoft Research model, 2.7B parameters, 32 layers, 32 attention heads, 2560 hidden
dimensions. Standard MHA trained on curated textbook-quality and code data. Represents optimal
training conditions for geometric clarity.
Llama-3.2-1B: Meta model, 16 layers, 32 query heads, 8 key-value heads (4:1 grouped-query
attention), 2048 hidden dimensions with rotary position embeddings. Trained on large-scale web
data. Represents efficiency-optimized architecture for production deployment.
4.2 Geometric Extraction Protocol
We extract value manifolds, key orthogonality structure, and attention—-entropy trajectories using
a uniform protocol across all models. All forward passes use each model’s native tokenizer and
positional—-embedding scheme without modification.
Prompt sampling. To avoid selection bias, we adopt a reproducible stratified—-entropy sampling
procedure. We first generate 1,000 candidate prompts from five heterogeneous corpora (Wikipedia
articles, news, fiction excerpts, code repositories, and general—-knowledge QA). For each prompt
we compute the model’s next—-token entropy on the final position and partition the candidates into
quintiles. We then uniformly sample 15 prompts per quintile (total 75 mixed—-domain prompts).
For domain—-restricted experiments (e.g., mathematics, coding, philosophy), we filter the candidate
pool to the relevant domain and apply the same stratified procedure. This ensures that geometric
results do not depend on hand—-chosen or manually curated prompts.
Final-token extraction. For a prompt of length 𝑇 , we perform a single forward pass and extract
geometric quantities from the representations associated with the final input token. Specifically,
for each layer ℓ we extract:
(1) value vectors 𝑣 (ℓ )
𝑇 ,ℎ ∈ R𝑑𝑣 from all attention heads ℎ,
(2) the key projection matrix 𝑊 (ℓ )
𝐾 ∈ R𝑑model ×𝑑𝑘 ,
(3) the attention distribution 𝛼 (ℓ )
𝑇 ,ℎ ∈ [0, 1]𝑇 for each head at query position 𝑇 ,
(4) the next—-token probability distribution 𝑝 (𝑥𝑇 +1 | 𝑥1:𝑇 ).
The final-token choice ensures that the extracted geometry reflects the model’s posterior uncertainty
after processing the entire prompt.
Value manifold computation. For each model, we adopt a canonical PCA protocol on the final-
layer value space. For a prompt of length 𝑇 , we extract the value vectors 𝑣 (𝐿)
𝑇 ,ℎ ∈ R𝑑𝑣 for the final
input token 𝑇 at the last layer 𝐿 from all attention heads ℎ = 1, . . . , 𝐻 . We then concatenate the
head-wise values into a single vector ˜𝑣 (𝐿)
𝑇 ∈ R𝐻𝑑𝑣 per prompt, so that each prompt contributes one
𝐻𝑑𝑣 -dimensional sample. Before PCA, we standardize each coordinate across the prompt batch
to zero mean and unit variance. All reported PC1 and PC1+PC2 statistics are computed from this
standardized covariance matrix, separately for mixed-domain and domain-restricted prompt sets.
Unless otherwise noted, PCA is run independently per model and per layer; cross-model analyses
in Section Section 5.8 use a global PCA basis constructed by concatenating standardized value
vectors across models.
, Vol. 1, No. 1, Article . Publication date: January .
6 Naman Aggarwal, Siddhartha R. Dalal, and Vishal Misra
Effective dimensionality (participation ratio). To complement PC𝑘 explained-variance ratios, we
report the participation ratio (PR) as a continuous measure of effective dimensionality. Let {𝜆𝑖 }
denote the eigenvalues of the standardized covariance matrix in descending order. The participation
ratio is
PR =
 Í𝑖 𝜆𝑖
2
Í𝑖 𝜆2
𝑖
,
which equals the dimensionality for a perfectly isotropic spectrum and decreases as mass con-
centrates on a low-rank subspace. Low PR values co-occur with high PC1+PC2 and provide an
additional check that “manifold collapse” is not an artifact of preprocessing or finite-sample noise.
Correct attention-entropy computation. Because entropy is concave, averaging attention weights
before computing entropy introduces a Jensen bias. We therefore compute attention entropy at the
granularity of individual heads on the final input token 𝑇 :
𝐻 (ℓ )
ℎ (𝑇 ) = −
𝑇∑︁
𝑗=1
𝛼 (ℓ )
𝑇 ,ℎ ( 𝑗) log 𝛼 (ℓ )
𝑇 ,ℎ ( 𝑗),
where 𝛼 (ℓ )
𝑇 ,ℎ denotes the attention distribution over keys for head ℎ in layer ℓ. We then average these
entropies only across heads and report bootstrap 95% confidence intervals across prompts:
𝐻 (ℓ ) = 1
𝐻
𝐻∑︁
ℎ=1
𝐻 (ℓ )
ℎ (𝑇 ).
This protocol aligns attention entropy with the value-vector geometry and predictive entropy at
the same token, and avoids the Jensen bias that arises from averaging distributions prior to entropy
computation.
Key orthogonality. For each layer ℓ and head ℎ, we take the key projection matrix 𝑊 (ℓ,ℎ)
𝐾 ∈
R𝑑model ×𝑑𝑘 , extract its 𝑑𝑘 column vectors, and ℓ2-normalize each column to obtain unit vectors
{ ˆ𝑘𝑖 }𝑑𝑘
𝑖=1 ⊂ R𝑑model . We then compute the mean off-diagonal absolute cosine similarity
Orthog(ℓ,ℎ) = 1
𝑑𝑘 (𝑑𝑘 − 1)∑︁ 𝑖≠𝑗
ˆ𝑘⊤
𝑖 ˆ𝑘𝑗 ,
and report layer-wise means and percentile bands across heads. To interpret these values we use
two baselines:
• Gaussian baseline. If ˆ𝑘𝑖, ˆ𝑘𝑗 were independent random unit vectors in R𝑑model , the expected
absolute cosine would be E[| cos 𝜃 |] ≈√︁ 2/(𝜋𝑑model). For 𝑑model in the 1024–4096 range, this
lies between 0.02 and 0.04 and provides the correct dimensionality-matched reference.
• Initialization baseline. For models with public initialization checkpoints (e.g., Pythia), we
measure Orthog(ℓ,ℎ) at training step 0. These empirical values fall around 0.35–0.45, reflecting
correlations induced by initialization schemes and architectural shared structure rather than
i.i.d. Gaussian randomness.
Trained models consistently achieve mean off-diagonal cosines between 0.034 and 0.18 across
most layers, representing a 2–10× improvement relative to the initialization baseline and confirming
that training sculpts sharper hypothesis frames than either Gaussian or initialization structure
would predict.
, Vol. 1, No. 1, Article . Publication date: January .
Geometric Scaling of Bayesian Inference in LLMs 7
Cross-model PCA analysis. For comparisons across architectures, we standardize all value vectors
per model (zero mean, unit variance per dimension), concatenate them, and compute a global co-
variance matrix. This enables interpretation of shared manifold directions and consistent alignment
of entropy-ordered axes across models.
4.3 In-Context Bayesian Updating Task
To test whether production models perform Bayesian updating during inference, we designed a
controlled in-context learning task. Each prompt contains 𝑘 labeled sentiment examples (e.g., “happy
is positive”, “sad is negative”) followed by a query word. We compute analytical Bayesian posteriors
using a simple generative model with likelihood ratio 0.9:0.1 for consistent vs. inconsistent labels,
generating 250 prompts across 𝑘 ∈ {0, 1, 2, 4, 8} with varying label imbalances.
4.4 Validation Criteria
We establish quantitative thresholds for Bayesian structure validation based on wind tunnel experi-
ments:
• Value manifolds: PC1 > 30% or PC1+PC2 > 30% (vs. 5% baseline for random)
• Key orthogonality: Mean off-diagonal < 0.20 for at least 50% of layers
• Attention focusing: > 30% entropy reduction from Layer 0 to final layer
Models meeting all three criteria exhibit Bayesian geometric signatures. Partial validation (2/3
criteria) suggests preserved qualitative structure with reduced clarity.
Threshold justification. These thresholds are anchored to quantitative baselines from controlled
wind-tunnel settings and random-initialization controls. In bijection and HMM tasks, trained models
produce nearly one-dimensional value manifolds with PC1 = 84–90% of variance explained. Under
mixed-domain prompting in production models, multiple inference modes are simultaneously
active, so we conservatively treat PC1+PC2 values in the 20–40% range as non-trivial structure
over the random baseline of ∼5% for PC1. When prompts are domain-restricted, all models recover
the same collapsed geometry as in wind-tunnel tasks (PC1 ≈ 0.75–0.85; PC1+PC2 ≈ 0.85–0.95).
For key orthogonality, random Gaussian 𝑊𝐾 matrices yield mean off-diagonal cosine values
around 0.40–0.45. Trained models consistently achieve 0.03–0.20 depending on layer depth, so we
adopt < 0.20 as a minimal criterion for structured hypothesis frames.
Wind-tunnel attention mechanisms reduce entropy by 85–90%. Production models face more
heterogeneous workloads and architectural constraints (e.g., GQA), therefore we use a lenient 30%
threshold to require meaningful focusing without expecting full collapse.
These thresholds are conservative: varying them within reasonable ranges does not change any
model’s qualitative classification or the cross-model trends reported in this paper.
4.5 Statistical Validation
We evaluate the significance of geometric structure by comparing trained models against two
distinct baselines: (i) a theoretically grounded high-dimensional Gaussian baseline, and (ii) each
model’s own initialization (when available). These baselines separate geometry induced purely by
dimensionality or initialization from structure learned during training.
Value manifolds. Under the null hypothesis that value vectors are random high-dimensional
embeddings, the expected variance captured by the top principal component is E[PC1] ≈ 1/𝑑 for
𝑑-dimensional Gaussian vectors (typically ≈ 5% for our head-concatenated value dimension). Across
all models, observed PC1 values under mixed-domain prompts are 6—-17× larger, and domain-
restricted prompts yield collapsed 1D manifolds (PC1 ≈ 0.75—-0.85, PC1+PC2 ≈ 0.85—-0.95). These
, Vol. 1, No. 1, Article . Publication date: January .
8 Naman Aggarwal, Siddhartha R. Dalal, and Vishal Misra
differences are statistically significant under paired 𝑡-tests across prompt batches (𝑝 < 0.001 after
Bonferroni correction).
Key orthogonality. We compare trained key matrices against two baselines:
(1) Gaussian baseline. For 𝑑𝑘 -dimensional random Gaussian vectors, the expected absolute
cosine similarity is
E[ | cos(𝜃 )| ] =√︂ 2
𝜋𝑑𝑘
,
which equals ≈ 0.11 for 𝑑𝑘 = 64 and decreases with dimensionality. This provides the correct
reference for high-dimensional orthogonality.
(2) Initialization baseline. For models where initialization checkpoints are publicly available
(e.g., Pythia), we measure the mean off-diagonal cosine similarity of 𝑊𝐾 at step 0. These
values (typically 0.35—-0.45, depending on the initialization scheme) reflect correlations
introduced by weight initialization rather than pure Gaussian randomness.
Trained models achieve mean off-diagonal cosine similarities between 0.034 and 0.18 across most
layers - representing a 2—-10× improvement relative to the appropriate baselines. This confirms
that training sculpts structured hypothesis frames rather than merely preserving initialization
correlations.
Attention entropy. For each model, we compute per-head, per-position attentional entropies
and average across heads and positions. Layerwise entropy reduction is evaluated relative to the
entropy of the bottommost attention layer. All reductions exceeding 30% are significant under paired
comparisons across prompts (𝑝 < 0.01), and the architecture-dependent patterns (Section Section 5)
are robust under bootstrap resampling.
Multiple comparisons. All hypothesis tests involving multiple layers, domains, or prompt buckets
use a Bonferroni correction. All reported results remain significant at the 𝑝 < 0.01 level after
correction.
Entropy-axis definition and interventions. For causal probes of the entropy-aligned manifold, we
first estimate an “entropy axis” 𝑢 (ℓ )
ent at each layer ℓ by computing the first principal component of
the standardized final-token value vectors across SULA prompts, and then taking the sign so that
corr(𝑣 (ℓ ) · 𝑢 (ℓ )
ent, 𝐻model) is non-negative. For a given intervention layer (or set of layers), we apply a
projection-removal operator to the value vectors during the forward pass:
˜𝑣 (ℓ ) = 𝑣 (ℓ ) − (𝑣 (ℓ ) · 𝑢 (ℓ )
ent ) 𝑢 (ℓ )
ent,
leaving all other components unchanged. “True-axis” interventions use 𝑢 (ℓ )
ent as defined above;
“random-axis” controls draw a unit vector from a Gaussian in R𝐻𝑑𝑣 and orthogonalize it against
𝑢 (ℓ )
ent before applying the same projection operator. We report the impact of these interventions
on (i) the correlation between 𝑣 (ℓ ) · 𝑢 (ℓ )
ent and model predictive entropy, and (ii) SULA calibration
metrics (MAE and entropy correlation) relative to the unperturbed baseline.
4.6 Causal Intervention Protocol: Entropy-Axis Ablations
For the causal probes in Section Section 6, we construct entropy-aligned axes and ablate them using
a simple linear projection scheme.
Axis estimation. For each layer ℓ of Pythia-410M we collect last-layer value vectors 𝑣 (ℓ )
𝑇 ,ℎ for
the SULA prompts and compute a layer-specific PCA basis as in Section Section 4.2. We take the
first principal component 𝑢 (ℓ )
ent and orient its sign so that the dot product 𝑣 (ℓ )
𝑇 ,ℎ · 𝑢 (ℓ )
ent is negatively
, Vol. 1, No. 1, Article . Publication date: January .
Geometric Scaling of Bayesian Inference in LLMs 9
Table 1. Value manifold dimensionality under mixed-domain and domain-restricted (mathematics) prompts.
PC1 and PC1+PC2 report variance explained by the top one and two principal components of the final-
layer value space under the canonical PCA protocol. Values are means across bootstrap resamples with 95%
confidence intervals in parentheses. Pythia-410M is an architectural outlier whose value space is nearly
collapsed even under mixed-domain prompts.
Model Mixed-domain Mathematics
PC1 PC1+PC2 PC1 PC1+PC2
Pythia-410M 79.6 (78.4, 80.8) 99.7 (99.6, 99.8) 58.0 (56.0, 60.0) 99.9 (99.8, 100.0)
Phi-2 46.4 (43.9, 48.9) 60.6 (57.5, 63.7) 52.2 (49.4, 55.0) 63.5 (60.0, 67.0)
Llama-3.2-1B 36.6 (34.8, 38.4) 51.4 (49.3, 53.5) 52.5 (50.2, 54.8) 73.6 (70.1, 77.1)
Wind-tunnel (ref.) — 84–90 88–95
correlated with predictive entropy; this defines the entropy axis for that layer. Random control axes
𝑢 (ℓ )
rand are drawn by sampling a Gaussian vector in the same space and normalizing to unit norm.
Single-layer axis cuts. In the axis-cut intervention we remove the component of each value vector
along a chosen axis,
˜𝑣 (ℓ )
𝑇 ,ℎ = 𝑣 (ℓ )
𝑇 ,ℎ − 𝜆 𝑣 (ℓ )
𝑇 ,ℎ · 𝑢 (ℓ )  𝑢 (ℓ ) ,
with 𝜆 = 1 for the hard-ablation experiments reported here. We apply this operation either along
𝑢 (ℓ )
ent (“true” cut) or along 𝑢 (ℓ )
rand (random control), leaving all other layers and parameters unchanged.
Multi-layer axis cuts. For the multi-layer intervention we repeat the same projection at five layers
ℓ ∈ {8, 12, 16, 20, 23}, using independently estimated 𝑢 (ℓ )
ent or 𝑢 (ℓ )
rand at each layer. All axis removals
are applied within a single forward pass before the final logits are computed. We then recompute
SULA calibration metrics and axis–entropy correlations under each intervention and compare them
to the baseline run. This protocol ensures that the interventions target a geometrically privileged
direction at multiple depths while keeping the rest of the computation intact.
5 Results: Geometric Validation Across Production Models
We present our empirical findings in an order that reflects increasing model complexity. We begin
with the domain-restriction result that most directly connects production models to wind-tunnel
behavior; then demonstrate inference-time Bayesian updating; then analyze each architecture; and
finally synthesize cross-architectural patterns.
5.1 Domain Restriction and Value Manifold Geometry
A central prediction from wind-tunnel experiments is that domain restriction should isolate a
single inference mode, collapsing the value manifold toward one dimension. We test this prediction
by comparing mixed-domain prompts (spanning mathematics, coding, philosophy, and general
knowledge) against domain-restricted prompts (mathematics only) across three production models.
Results. Table Table 1 and Figure Figure 1 summarize the findings. The domain-restriction effect
is model-dependent rather than universal:
• Pythia-410M exhibits near-complete dimensionality collapse under both conditions (PC1+PC2
≈ 100%), with no significant difference between mixed and domain-restricted prompts. This
suggests that Pythia’s value manifold operates in a consistently low-dimensional subspace
regardless of domain.
, Vol. 1, No. 1, Article . Publication date: January .
10 Naman Aggarwal, Siddhartha R. Dalal, and Vishal Misra
• Phi-2 shows moderate dimensionality (PC1+PC2 ≈ 60–64%) with minimal domain effect.
The curated training data may induce stable geometric structure that is robust to prompt
domain.
• Llama-3.2-1B displays the clearest domain-restriction effect: mixed-domain prompts yield
PC1+PC2 = 51.4%, while mathematics-only prompts increase this to 73.6%. This 22-percentage-
point increase is consistent with the hypothesis that domain restriction isolates a more
coherent inference mode.
Entropy–manifold correlation. Beyond dimensionality, we examine whether value coordinates
track predictive entropy. Spearman correlations between PC1 and next-token entropy vary sub-
stantially:
• Pythia-410M: 𝜌 = −0.32 (mixed), 𝜌 = −0.14 (math)
• Phi-2: 𝜌 = +0.34 (mixed), 𝜌 = +0.16 (math)
• Llama-3.2-1B: 𝜌 = +0.59 (mixed), 𝜌 = −0.51 (math)
The sign flips across models do not indicate instability so much as a choice of convention. PCA
directions are defined only up to a global sign, and we orient PC1 separately for each model. In
some models higher PC1 coordinates correspond to lower entropy (negative correlation), while in
others they correspond to higher entropy (positive correlation). What matters for our analysis is
the magnitude and monotone relationship between manifold position and predictive entropy, not
the absolute sign; in all three models |𝜌 (PC1, 𝐻 )| is substantial, with Llama showing the strongest
alignment, consistent with its clearer domain-restriction effect.
Interpretation. These results refine the wind-tunnel predictions. Rather than a universal domain-
restriction effect, we observe:
(1) Architecture-dependent geometry: Pythia’s value space is intrinsically collapsed; Llama’s
is distributed and domain-sensitive; Phi-2 occupies an intermediate regime.
(2) Training-data effects: Models trained on diverse web-scale data (Llama) show stronger
domain modulation than models trained on curated corpora (Phi-2) or general text (Pythi-
a/Pile).
(3) Partial wind-tunnel correspondence: Only Llama approaches the wind-tunnel pattern
where domain restriction increases manifold collapse. The other models suggest that produc-
tion training can stabilize value geometry in ways that resist domain-induced variation.
Connecting to wind-tunnel behavior. The wind-tunnel experiments (Paper 1) used tasks with a
single, analytically tractable posterior—effectively a maximally domain-restricted setting. The Llama
results demonstrate that this pattern can emerge in production models when prompt distributions
are similarly constrained. However, the Pythia and Phi-2 results show that not all architectures
exhibit this behavior, suggesting that the mapping from domain restriction to manifold collapse
depends on training dynamics and architectural capacity.
Implications. These findings suggest caution in extrapolating from wind-tunnel behavior to
all production models. The geometric substrate for Bayesian inference (low-dimensional value
manifolds, entropy ordering) is present across architectures, but its sensitivity to domain restriction
is not universal. Future work should investigate whether domain-restriction effects strengthen
with scale, and whether architectural choices (e.g., GQA vs. MHA) systematically modulate this
sensitivity.
Limitations of domain restriction. Domain restriction simultaneously reduces task heterogeneity
and lexical variability. Our results therefore conflate two effects: isolating a single inference mode
and narrowing token and syntax distributions. We view the strong collapse as evidence that some
, Vol. 1, No. 1, Article . Publication date: January .
Geometric Scaling of Bayesian Inference in LLMs 111250
1000
750
500
250
0
250
500
Pythia-410M
Mixed Math-only
20
10
0
10
Phi-2
7.5 5.0 2.5 0.0 2.5 5.0
6
4
2
0
2
Llama-3.2-1B
7.5 5.0 2.5 0.0 2.5 5.0
2
4
6
8
Entropy (bits)
Fig. 1. Domain restriction effects on value manifolds. PCA projections of last-layer value vectors under
mixed-domain (left column) and mathematics-only (right column) prompts for each model. Points are colored
by next-token entropy. Llama-3.2-1B shows the clearest domain-restriction effect; Pythia-410M shows near-
complete collapse in both conditions.
stable uncertainty representation is present, but we do not claim that all of the dimensionality
reduction reflects “pure” inference geometry. Disentangling these factors—for example by matching
token frequencies between mixed and restricted prompts or by applying domain-agnostic synthetic
templates to natural tokens - is an important direction for follow-up work.
5.2 Inference-Time Bayesian Updating in Production Models (SULA)
We next evaluate whether production models use the same geometric substrate during inference. To
do so, we design a controlled in-context learning task - Synthetic Unary Likelihood Augmentation
(SULA) - that supplies explicit symbolic evidence inside the prompt. Because the underlying
generative model is analytically tractable, we can compute exact Bayesian posteriors and compare
them directly to model behavior.
Generative model. Each SULA prompt contains 𝑘 labeled examples of the form “𝑥𝑖 is positive” or
“𝑥𝑖 is negative”, followed by a query word 𝑥query. Labels carry no semantic content; they serve only
as discrete likelihood indicators. We use a simple binary hypothesis model with likelihood ratio
0.9 :0.1. Let 𝑦 ∈ {positive, negative} denote the latent class. The prior is uniform, and each example
contributes independent evidence:
𝑝 (𝑦 | D𝑘 ) ∝ 𝑝0 (𝑦)
𝑘Ö
𝑖=1
ℓ (𝑥𝑖, 𝑦𝑖 ), ℓ (𝑥𝑖, 𝑦𝑖 ) =
(0.9 if 𝑦 = 𝑦𝑖,
0.1 if 𝑦 ≠ 𝑦𝑖 .
The resulting analytical posterior entropy 𝐻Bayes (𝑘) is known in closed form and decreases mono-
tonically with 𝑘.
, Vol. 1, No. 1, Article . Publication date: January .
12 Naman Aggarwal, Siddhartha R. Dalal, and Vishal Misra0 1 2 3 4 5 6 7 8
Number of in-context examples (k)
2000
1500
1000
500
0
500
1000
1500
2000
PC1 coordinate (final-layer values)
SULA controls: EleutherAI_pythia-410m
Main
Lexical remap
Shuffled labels
Evidence ablation
(a) Pythia-410M0 1 2 3 4 5 6 7 8
Number of in-context examples (k)
0
5
10
15
20
PC1 coordinate (final-layer values)
SULA controls: microsoft_phi-2
Main
Lexical remap
Shuffled labels
Evidence ablation (b) Phi-20 1 2 3 4 5 6 7 8
Number of in-context examples (k)
3
2
1
0
1
2
3
PC1 coordinate (final-layer values)
SULA controls: meta-llama_Llama-3.2-1B
Main
Lexical remap
Shuffled labels
Evidence ablation (c) Llama-3.2-1B
Fig. 2. SULA control experiments across models. PC1 coordinates of last-layer value vectors as a function
of the number of in-context examples (𝑘) for the monotone SULA task. Each panel shows the main generative
process (blue), a lexical-remapping control that replaces label tokens with unrelated symbols (orange), a within-
prompt label-shuffling control that breaks the evidence–label correlation (green), and an evidence-ablation
control that removes carrier words (red). Only the main and lexical-remap conditions exhibit monotone
Bayesian trajectories; shuffled and ablated conditions eliminate or reverse the structure, ruling out surface-
statistics explanations.
Experimental setup. We generate 250 prompts for each 𝑘 ∈ {0, 1, 2, 4, 8} with varying label imbal-
ances. For each prompt, we extract: (1) the model’s predictive entropy, (2) last-layer value vectors
projected into a common PCA basis (Section Section 4.2), and (3) attention-entropy trajectories.
This allows us to test whether value-manifold coordinates move along the Bayesian axis as evidence
accumulates.
Main results. Figure Figure 2 summarizes the findings.
Predictive entropy. Model entropy declines monotonically with 𝑘 and tracks analytical Bayesian
entropy:
MAE: 0.44 bits (Pythia-410M), 0.36 bits (Llama-3.2-1B), 0.31 bits (Phi-2).
Although noisier than wind-tunnel calibration, the consistent monotone trend indicates that
production models extract and use likelihood information supplied in the prompt.
Manifold alignment. When all SULA value vectors (across all 𝑘) are embedded into a shared
PCA basis, PC1 coordinates correlate strongly with the analytical Bayesian entropy for each model
(|𝜌 | = 0.65—-0.80). This confirms that the entropy-ordered manifold learned during large-scale
training is the axis along which inference-time updates occur.
Bayesian-axis trajectory. The mean PC1 coordinate shifts monotonically with 𝑘:
𝜌 (𝑘, PC1) = 0.86 (Pythia-410M), 0.60 (Phi-2), 0.32 (Llama-3.2-1B).
This reproduces the wind-tunnel phenomenon in which posterior concentration corresponds to
movement along a one-dimensional entropy axis.
Control conditions (monotone SULA).. To verify that manifold movement reflects likelihood struc-
ture rather than prompt format, we implement three control conditions tailored to the monotone
SULA generative model. In all conditions, the latent label 𝑦 and the number of glimpses 𝑘 are
preserved so that analytic Bayesian entropies remain well-defined.
(1) Lexical remapping. We preserve the latent label 𝑦 and the full 0.9:0.1 noisy-glimpses
generative model but replace the two surface label tokens (𝐿1, 𝐿2) with a different fixed pair
(𝐿′
1, 𝐿′
2). This tests whether manifold trajectories depend on the identity of the nonsense tokens
rather than on the underlying likelihood information. Analytical posteriors are unchanged.
, Vol. 1, No. 1, Article . Publication date: January .
Geometric Scaling of Bayesian Inference in LLMs 13
(a) Value manifold (b) Key orthogonality (c) Attention focusing
Fig. 3. Pythia-410M: Bayesian geometric signatures.
(2) Shuffled labels. We preserve the prompt template but overwrite each example’s surface label
token with an independent draw from {𝐿1, 𝐿2 }, breaking all correlation between glimpses
and the latent label. Under the SULA generative model, this corresponds to providing no
usable evidence, so the analytical posterior collapses to the uniform prior for all 𝑘 (𝐻Bayes = 1
bit). Any systematic manifold movement should therefore disappear.
(3) Evidence ablation. We retain the surface labels and prompt structure but mask the glimpse
content (e.g., replacing carrier tokens with “[MASK]”). This removes the likelihood-bearing
evidence while preserving superficial formatting, again yielding a flat analytical posterior.
This tests whether models move along the manifold only when evidence tokens encode useful
likelihood information.
Across all models, only the lexical-remapping condition reproduces the monotone decrease in
predictive entropy and coherent PC1 movement; both shuffled-label and evidence-ablated prompts
show little or no movement along the Bayesian axis. These findings confirm that the geometry is
sensitive to the likelihood structure supplied by the glimpses rather than to the surface formatting
of labels or examples.
Interpretation. The SULA experiment demonstrates that production models use the same geo-
metric mechanism active in wind-tunnel transformers: evidence supplied in-context drives repre-
sentations along an entropy-ordered manifold. The calibration gap (0.31–0.44 bits vs. < 0.1 bits in
wind tunnels) reflects the fact that (i) production models are not trained on the SULA generative
distribution, and (ii) natural-language prompts introduce semantic ambiguity absent in synthetic
tasks. The key result is the systematic correspondence between analytical Bayesian entropy, model
predictive entropy, and movement along the value manifold.
Together, these findings show that geometric Bayesian updating is an inference-time phenome-
non: transformers navigate the same manifold direction that encodes predictive uncertainty when
supplied with usable likelihood information inside the prompt.
5.3 Standard MHA: Pythia-410M
Pythia-410M provides our canonical production baseline.
Value manifolds. Mixed-domain PC1 ≈ 12–25%; mathematics-only PC1 ≈ 0.81, recovering the
collapsed wind-tunnel manifold.
Key orthogonality. Layers 1–22: mean off-diagonal cosine 0.11–0.13.
Attention focusing. Entropy reduction: 82%, with the characteristic binding → elimination →
refinement pattern.
, Vol. 1, No. 1, Article . Publication date: January .
14 Naman Aggarwal, Siddhartha R. Dalal, and Vishal Misra
(a) Value manifold (b) Key orthogonality (c) Attention focusing
Fig. 4. Phi-2: Sharpened Bayesian geometry from curated training.
(a) Value manifold (b) Key orthogonality (c) Attention focusing
Fig. 5. Llama-3.2-1B: Bayesian structure with GQA efficiency trade-offs.
5.4 Curated Training Enhances Geometry: Phi-2
Phi-2 shows the cleanest geometry among all models evaluated.
Value manifolds. PC1+PC2 = 34%; mathematics-only collapse mirrors Pythia.
Key orthogonality. Exceptional: 0.034–0.051 across 29/32 layers.
Attention focusing. Strongest observed: 86% entropy reduction.
5.5 Efficiency–Interpretability Trade-off: Llama-3.2-1B (GQA)
Llama-3.2-1B employs a 4:1 grouped-query attention mechanism.
Value manifolds. Mixed-domain 2D geometry (PC1=18.5%, PC2=14.8%); mathematics-only col-
lapse recovered.
Key orthogonality. Moderate: 0.15–0.18; weaker than Pythia/Phi-2 but 2× better than random.
Attention focusing. 31% entropy reduction, consistent with KV-sharing constraints.
5.6 Scaling Within a Family: Pythia-12B
Value manifolds. Mixed-domain geometry becomes multi-lobed (PC1+PC2 = 19%), but mathematics-
only prompts recover a near-1D manifold (PC1+PC2 ≈ 0.90).
Key orthogonality. Strong early (0.048–0.055), gradually decreasing with depth.
Attention focusing. Early collapse, mid-layer mixing, late refinement.
5.7 Boundary Case: The Mistral Family
The Mistral family provides an illuminating boundary condition for Bayesian geometry. Across
all three variants we evaluate - Mistral-7B-Base, Mistral-7B-Instruct, and the Mixtral-8×7B MoE
, Vol. 1, No. 1, Article . Publication date: January .
Geometric Scaling of Bayesian Inference in LLMs 15
(a) Value manifold (b) Key orthogonality (c) Attention focusing
Fig. 6. Pythia-12B: Bayesian geometry at larger scale.
- we find that the static geometric signatures (value manifolds and key orthogonality) remain
clean and consistent, while the dynamic signature (progressive attention focusing) is substantially
weakened or noisy. This dissociation reveals how architectural constraints modulate the expression
of Bayesian computations without eliminating the underlying representational substrate.
Static geometry persists. All Mistral variants exhibit low-dimensional value manifolds under
mixed-domain prompts and recover wind-tunnel-style 1D collapse under mathematics-only prompts
(PC1+PC2 ≈ 80%–90%). Key orthogonality is likewise sharp: early and mid layers show mean off-
diagonal cosine values near 0.05–0.06, well below both Gaussian and initialization baselines. These
results indicate that the hypothesis-frame structure and entropy-ordered manifold discovered in
Papers 1–2 persist robustly in Mistral architectures.
Dynamic focusing is attenuated. In contrast, attention entropy decreases only modestly (typically
20%–30%) and often non-monotonically across layers (Figure Figure 7). This stands in sharp contrast
to the binding→elimination→refinement trajectory observed in full-sequence MHA (Sections 5.3–
5.5). The weakened focusing reflects architectural constraints:
• Sliding-window attention restricts global routing, preventing heads from accumulating
evidence across the entire prompt.
• Mixture-of-experts (MoE) routing fragments updates across experts, further reducing the
coherence of evidence aggregation.
These factors disrupt the dynamic refinement of posterior uncertainty while leaving the static
representational geometry intact.
Interpretation without circularity. It is tempting to interpret weak focusing as a failure of Bayesian
inference, but this would be circular: strong progressive focusing is a sufficient mechanism for
Bayesian updating in full-sequence MHA, not a necessary one for all architectures. The Mistral
models demonstrate that:
(1) the representational frame for Bayesian inference (orthogonal keys + value manifold) remains
fully intact,
(2) while the mechanism of evidence refinement (progressive focusing) depends sensitively on
global routing capacity.
This pattern matches the frame–precision dissociation predicted in Paper 2: attention patterns (the
frame) stabilize early and robustly under training, whereas the precision of posterior refinement is
sensitive to architectural bandwidth and routing design.
Conclusion. The Mistral family should therefore be viewed not as a counterexample to Bayesian
geometry but as a boundary case that reveals how architectural constraints selectively modulate
, Vol. 1, No. 1, Article . Publication date: January .
16 Naman Aggarwal, Siddhartha R. Dalal, and Vishal Misra
(a) Mistral-7B (base) (b) Mistral-7B-Instruct (c) Mixtral-8×7B
Fig. 7. Attenuated dynamic focusing in Mistral-style architectures. Attention entropy as a function of
layer depth for three variants of the Mistral family. Unlike models with full-sequence multi-head attention,
entropy decreases only modestly (20%–30%) and often non-monotonically, reflecting weakened dynamic
routing due to (i) sliding-window attention, which prevents global evidence accumulation, and (ii) mixture-
of-experts routing, which fragments updates across experts. Despite reduced focusing dynamics, the static
value-space geometry (Sections Section 5.1–Section 5.2) remains intact, illustrating a dissociation between
representational invariants and the mechanisms that refine them during inference.
Table 2. Bayesian geometric signatures across architectures. Value-manifold dimensionality reports PC1+PC2
under mixed-domain and domain-restricted (mathematics) prompts. Key orthogonality shows mean off-
diagonal cosine in early layers. Attention focusing reports entropy reduction from first to final layer.
Model Arch Training Value Manifold Key Orthog Attn Focus
Mixed Math (early)
Pythia-410M MHA Pile 99.7% 99.9% 0.11–0.13 ↓82%
Phi-2 MHA Curated 60.6% 63.5% 0.034–0.051 ↓86%
Pythia-12B MHA Pile ∼19% ∼90% 0.05–0.10 non-monotone
Llama-3.2-1B GQA Web 51.4% 73.6% 0.15–0.18 ↓31%
Mistral-7B GQA+SW Web 15–20% ∼80% 0.05–0.06 20–30%
Wind-Tunnel MHA Synthetic — 84–90% 0.09–0.12 ↓85–90%
Notes: Value manifold dimensionality varies substantially across architectures under mixed-domain prompts. Pythia-410M
shows near-complete collapse regardless of domain; Llama-3.2-1B shows the clearest domain-restriction effect. All models
achieve key orthogonality 2–10× better than random Gaussian baselines (≈0.11 for 𝑑𝑘 = 64). Attention focusing depends
strongly on architecture: full-sequence MHA achieves strong progressive reduction while GQA and sliding-window
variants show weaker or non-monotone patterns.
dynamic Bayesian computation. Static geometric structure—entropy-ordered manifolds and hy-
pothesis frames—persists across all Mistral variants, while dynamic refinement is diminished by
local attention and MoE routing. This provides a natural explanation for the observed behavior
and connects directly to the theoretical predictions of Paper 2.
5.8 Cross-Architecture Synthesis
Table Table 2 summarizes the unified picture:
• Value manifolds: all models exhibit low-dimensional value geometry. Under mixed-domain
prompts, PC1+PC2 varies substantially across architectures—from ∼15–20% in Mistral to
∼51% in Llama and ∼61% in Phi-2, with Pythia-410M as a notable outlier whose manifold
is nearly collapsed even in the mixed setting (∼100%). Under mathematics-only prompts,
all models move into the 70–95% range, approaching the one-dimensional structure of the
wind-tunnel tasks.
, Vol. 1, No. 1, Article . Publication date: January .
Geometric Scaling of Bayesian Inference in LLMs 17Static Collapse
(PC1+PC2 var)
DR Gain
( (PC1+PC2))
Key Orth.
(1 - mean |cos| norm)
Focusing
( Attn Entropy %)
Pythia-410M
Phi-2
Llama-3.2-1B
Model
0.50 0.00 0.64 -0.10
0.37 0.03 0.63 0.20
0.33 0.22 0.47 0.24
Static geometry is universal; dynamic focusing varies by architecture.
0.0
0.2
0.4
0.6
0.8
1.0
Normalized Strength / Probability
Cross-Model Geometric Signatures
All metrics are normalized to [0,1] per axis to enable cross-model comparison.
Fig. 8. Cross-model geometric signatures. Normalized comparison of four geometric metrics across three
model families. Left: Static signatures—-value manifold collapse (PC1+PC2) and domain-restriction gain—-are
consistently present, indicating that all models internalize a low-dimensional representation of hypothesis
space. Right: Dynamic signatures—-key orthogonality and attention focusing—-vary substantially by architec-
ture: Llama-3.2-1B exhibits strong runtime refinement, whereas Pythia-410M relies on pre-orthogonalized
hypothesis frames and shows weak focusing. This dissociation suggests that representation is universal, but
the mechanism that refines it during inference is architectural.
• Key orthogonality: mean off-diagonal cosine is consistently 2–10× lower (better) than
random baselines or initialization, indicating robust hypothesis-frame structure.
• Attention focusing: layerwise entropy reduction varies systematically by architecture—-
strong in full-sequence MHA, moderate in GQA, and modest and often non-monotone in
sliding-window and MoE variants.
As summarized in Table Table 2, all three geometric signatures show quantitative continuity
from synthetic wind-tunnel tasks to production models.
Static vs dynamic geometry. The stable invariants across every architecture - including Mistral
- are: (1) entropy-ordered value manifolds, and (2) orthogonal key frames. Dynamic focusing is
architecture-dependent, requiring global routing capacity.
This separation is the central representational—-computational split predicted in Paper 2.
6 Analysis and Key Findings
Our cross-architecture validation reveals systematic patterns in how Bayesian geometric structures
scale from wind tunnels to production models.
6.1 Universal core mechanisms
Across the standard MHA and GQA models (Pythia, Phi-2, and Llama), we observe the full set of
Bayesian geometric signatures predicted by the wind tunnel experiments: value manifolds, key
orthogonality, and layerwise attention focusing. In the Mistral family (Section Section 5.7), the static
signatures (value manifolds and key orthogonality) persist, while the dynamic signature (monotone
, Vol. 1, No. 1, Article . Publication date: January .
18 Naman Aggarwal, Siddhartha R. Dalal, and Vishal Misra
attention focusing) is weakened or absent due to architectural and training-objective differences.
This suggests a natural split between universal static structure and architecture-dependent dynamics.
Value manifolds (static). All models, including the Mistral variants, show low-dimensional
value structure, with PC1+PC2 between roughly 16% and 84%, far above random baselines. Entropy
ordering persists in every model evaluated: prompts with higher next-token entropy occupy
systematically different regions of the manifold than low-entropy prompts.
Key orthogonality (static). All models learn hypothesis-frame structure, with mean off-diagonal
cosine between 0.034 and 0.18, consistently 2 - 10 times better than random initialization (0.40 -
0.45). Mistral models show the same early-layer emergence and late-layer collapse of orthogonality
as standard MHA.
Attention focusing (dynamic). Standard MHA and GQA models exhibit a clear layerwise
entropy decrease (31 - 86%), matching the binding → elimination → refinement pattern seen in
wind tunnels. In the Mistral models, this dynamic signature is weak or absent (Section Section 5.7),
consistent with architectural constraints (sliding-window attention, MoE routing) and the effects
of downstream alignment.
The ICL experiment connects the controlled wind-tunnel setting to real-time inference in produc-
tion models. In the wind tunnels, Bayesian structure emerges from the training objective alone: the
model learns to encode posterior uncertainty along a one-dimensional manifold. The ICL setting
demonstrates that the same mechanism is active during inference: when the model is given explicit
symbolic evidence inside the prompt, its value representations move along the same manifold
direction that encodes posterior entropy, and the degree of movement is proportional to the amount
of evidence. In this way, the ICL results show that transformers not only embody Bayesian geometry
as a representational primitive, but also execute Bayesian updates on-the-fly when the prompt
supplies usable likelihood information.
Conclusion. The static components of the Bayesian geometry (value manifolds and hypothesis
frames) are universal across architectures, while strong progressive attention focusing depends on
global routing capacity and training regime.
6.2 Training Data Quality Enhances Clarity
Geometric clarity correlates strongly with training data quality:
• Phi-2 (curated textbooks/code): Orthogonality 0.034 - 0.051, focusing 86%
• Pythia (Pile corpus, diverse): Orthogonality 0.11 - 0.13, focusing 82%
• Llama (web-scale): Orthogonality 0.15 - 0.18, focusing 31%
High-quality, consistent training examples enable gradient dynamics to sculpt sharper hypothesis
frames (better orthogonality) and stronger attention pathways (better focusing). This suggests:
Implication for training: Early training on curated data may establish cleaner geometric
scaffolding that persists through subsequent web-scale training. Curriculum learning - progressing
from structured to diverse data - could enhance both interpretability and reliability.
Causal resolution of the Bayesian manifold. Our final experiment simultaneously ablates the
entropy-aligned value direction across all identified “Bayesian layers” (8, 12, 16, 20, 23) in Pythia-
410M. If this axis encoded a causal bottleneck for Bayesian inference, removing it at every layer
should degrade and ultimately collapse SULA behavior. Instead, we observe the opposite dissociation:
(i) the multi-layer ablation destroys the entropy geometry (axis—-entropy correlation drops from
0.27 to 0.07), yet (ii) SULA calibration remains intact, with MAE and correlation to the Bayesian
posterior changing by less than 1%, and (iii) a matched random-axis ablation improves calibration
metrics despite preserving the original geometry. These results rule out both single-axis and
, Vol. 1, No. 1, Article . Publication date: January .
Geometric Scaling of Bayesian Inference in LLMs 19
multi-axis bottleneck hypotheses and show that the entropy manifold is a representational trace of
inference rather than the substrate that performs it.
6.3 Architectural Trade-offs: Efficiency vs Interpretability
Grouped-query attention demonstrates clear efficiency-interpretability trade-offs:
• Efficiency gains: 4×— reduction in KV cache size, 4×— faster inference
• Clarity costs: 50% weaker orthogonality, 62% weaker focusing (31% vs 82%)
• Functional preservation: Qualitative Bayesian structures persist
The 4:1 query-to-KV ratio forces keys and values to serve multiple query groups simultaneously,
preventing the sharp specialization seen in standard MHA. However, the model compensates by
distributing information across dimensions (2D manifolds, distributed attention patterns) while
maintaining overall Bayesian computational structure.
The Mistral family provides a complementary negative case: sliding-window attention and MoE
routing both weaken dynamic focusing even when static geometry (orthogonality, value manifolds)
remains intact.
Implication for deployment: GQA is suitable for production deployment where efficiency
matters, but researchers studying mechanisms or building interpretability tools should prefer
standard MHA for clearer geometric signatures.
6.4 Depth Drives Richer Representations
Value manifold dimensionality correlates with depth:
• Pythia (24 layers): 1D manifolds (PC1=84%, PC2=4.5%)
• Phi-2 (32 layers): 2D manifolds (PC1=21%, PC2=13%)
• Llama (16 layers, but GQA): 2D manifolds (PC1=18.5%, PC2=14.8%)
Deeper architectures develop richer uncertainty representations requiring additional dimensions.
Crucially, entropy parameterization persists - the additional dimension is not noise but structured
geometry enabling more nuanced posterior modeling.
This suggests depth enables transformers to represent multimodal or high-dimensional uncer-
tainty distributions while shallower models compress to 1D entropy coordinates.
6.5 Layer-wise Functional Specialization
Consistent patterns emerge across models:
Layer 0: Setup phase - high key similarity, moderate attention entropy. Likely initializes repre-
sentations (position embeddings, token embeddings) before geometric structure emerges.
Layers 1 - N-4: Core computation - strong orthogonality, progressive attention focusing. These
layers perform Bayesian hypothesis discrimination and evidence accumulation.
Final 3 - 4 layers: Collapse phase - orthogonality weakens, attention sharpens dramatically.
Hypothesis frames collapse as model commits to output distribution.
The Mistral models follow the same structural pattern for value manifolds and key orthogonality,
but do not show the expected sharpening of attention in the elimination and refinement stages.
This is consistent with constraints on global routing (sliding window) and fragmented updates
(MoE).
This functional stratification mirrors the three-stage inference process: binding context →’
eliminating hypotheses →’ refining output.
Bayes calibration in natural language vs. wind—-tunnel tasks. Entropy calibration errors in the ICL
setting (0.31–0.44 bits across models) are considerably larger than those observed in the controlled
, Vol. 1, No. 1, Article . Publication date: January .
20 Naman Aggarwal, Siddhartha R. Dalal, and Vishal Misra
wind—-tunnel experiments (typically below 0.1 bits). This gap is expected: natural—-language
prompts introduce substantial semantic ambiguity, and production models are not trained on the
synthetic labeling distribution used in our ICL task. The key result is therefore not the absolute
calibration error but the systematic correspondence between value—-manifold coordinates, model
predictive entropy, and the analytical Bayesian posterior as evidence accumulates. This indicates
that the same geometric substrate identified in wind—-tunnel training is actively used by production
models during inference.
6.6 Robustness and Limitations
What transfers robustly. Several geometric signatures persist across all dense, GQA, and sliding-
window/MoE architectures evaluated. First, value manifolds are consistently low-dimensional:
PC1+PC2 remains far above random (ranging from 15below heuristic thresholds. Second, key
orthogonality shows the characteristic pattern predicted by wind-tunnel analyses: sharp early-layer
frames followed by gradual late-layer collapse. Third, layerwise functional structure - setup layers,
a broad computation band, and final collapse layers - appears in all models at the level of static
geometry.
What varies systematically. Quantitative clarity depends on architecture, training data, and depth.
GQA reduces the sharpness of orthogonality and focusing; web-scale training reduces geometric
contrast relative to curated data; and deeper models develop richer or multi-lobed manifolds under
mixed prompting. Dynamic attention focusing depends most sensitively on architecture: strong in
full-sequence MHA, moderate in GQA, and weak or noisy in sliding-window and MoE variants.
What domain restriction isolates. Domain restriction functions as a natural intervention: it reduces
the multiplicity of task-specific inference modes activated by mixed prompts. When prompts come
from a single coherent domain (e.g., mathematics), the model operates in a more homogeneous
inference regime, revealing the same collapsed 1D manifold observed in wind-tunnel settings.
Importantly, domain restriction does not prove that the model performs “true– Bayesian inference
on natural language; rather, it shows that a Bayesian geometric coordinate system is embedded in its
representation space and can be isolated when the prompt distribution reduces task heterogeneity.
Pythia-410M departs from this pattern, exhibiting an intrinsically low-dimensional value space
(PC1+PC2 ≈ 99.7%) under both mixed and mathematics-only prompts (Table Table 1), suggesting
that its final-layer values are effectively collapsed regardless of domain.
Causal limitations. Our findings are correlational. Static and dynamic geometric signatures
co-occur with Bayesian-like behavior, but we do not intervene directly on the geometry to test
necessity. Establishing causal roles would require controlled manipulations - for example:
• degrading or sharpening key orthogonality and measuring effects on calibration,
• perturbing value vectors along or orthogonal to the manifold axes,
• ablating heads responsible for attention refinement.
Developing such interventions without collapsing the model’s function entirely remains technically
challenging. The present results show that geometry aligns with Bayesian computations, but they
do not establish that geometry is required for these computations.
Open representational questions. The emergence of 2D or multi-lobed manifolds in deeper or larger
models is not yet theoretically understood. These structures may encode multimodal uncertainty,
semantic clustering, training-set heterogeneity, or task-mixture effects. Likewise, the interaction
between positional embeddings, local attention kernels, and geometric formation remains an open
problem, especially in sliding-window or hybrid transformer—-SSM architectures.
, Vol. 1, No. 1, Article . Publication date: January .
Geometric Scaling of Bayesian Inference in LLMs 21
Scale and architecture coverage. Our largest dense model is 12B parameters, and our largest MoE
model is Mixtral-8×7B. Although consistent patterns appear from 410M to 12B, evaluating frontier-
scale checkpoints (70B—-400B) is necessary to determine whether new geometric phenomena arise
or whether multi-lobed structure remains the dominant pattern under mixed-domain prompts.
Overall, while the geometric signatures are strikingly robust, a complete causal and mechanistic
account of their formation - and of their architectural modulation - remains an important direction
for future work.
7 Discussion
This paper extends the geometric account of Bayesian inference developed in Papers 1—-2 to
production-scale language models. Three results stand out: domain restriction collapses value
manifolds to the one-dimensional geometry characteristic of exact Bayesian wind-tunnel tasks;
transformers navigate this geometry during inference in the SULA experiment; and static geomet-
ric signatures - entropy-ordered value manifolds and orthogonal key frames - appear across all
architectures evaluated, including GQA, sliding-window, and MoE variants.
Relation to circuit-level work. Our analysis complements circuit-level studies such as induction
heads, copy heads, and pattern-matching mechanisms [ 10, 13]. Those works identify specialized
components; our findings describe the global geometric scaffold in which such components operate.
Attention focusing determines which tokens are consulted; key orthogonality creates separable hy-
pothesis directions; and value manifolds encode uncertainty along low-dimensional axes. Mapping
specific heads onto regions or branches of this geometry is a natural next step.
Connection to wind-tunnel behavior. The wind-tunnel tasks isolate a single Bayesian computation,
yielding a one-dimensional value manifold that parameterizes posterior entropy. Production models
generalize this structure: mixed-domain prompts activate several task-specific inference modes,
yielding distributed or multi-lobed manifolds, while domain restriction recovers the same one-
dimensional axis observed under analytic posteriors. This behavior supports a view in which
transformers hold a repertoire of Bayesian manifolds, with the active manifold determined by the
prompt distribution.
Static vs. dynamic geometry. The consistency of value manifolds and orthogonal key frames across
all models indicates that the representational substrate for Bayesian inference is an architectural
invariant. Dynamic focusing, by contrast, depends on routing capacity: full-sequence attention
exhibits strong progressive sharpening; GQA reduces it; sliding-window attention and MoE routing
weaken or fragment it. This behavior matches the frame—-precision dissociation predicted in
Paper 2: the hypothesis frame (keys) stabilizes early and robustly, whereas the precision of posterior
refinement is sensitive to architectural constraints.
Inference-time Bayesian computation. The SULA experiment demonstrates that these geometric
structures are used during inference rather than merely encoded during training. Value represen-
tations move along the same entropy-ordered manifold as evidence accumulates, and predictive
entropy correlates systematically with analytic posteriors. Although calibration is noisier than in
the wind tunnels, the direction and magnitude of movement confirm active Bayesian updating
within the learned geometric space.
Implications. These findings suggest a geometric foundation for understanding transformer
behavior. Value manifolds offer a representation of uncertainty; orthogonal key frames support
hypothesis discrimination; and attention focusing provides the mechanism for posterior refinement
, Vol. 1, No. 1, Article . Publication date: January .
22 Naman Aggarwal, Siddhartha R. Dalal, and Vishal Misra
when architecture permits it. Together, these components form a scalable, architecture-agnostic
computational template for approximate Bayesian inference in modern LLMs.
7.1 Limitations and Future Directions
Architectural coverage. Our study focuses on dense MHA, GQA, and the first widely deployed
combination of sliding-window attention and MoE routing (Mistral). Other architectures - notably
state-space models such as Mamba and hybrid transformer—-SSM designs - may require specialized
extraction methods, and their geometric structure remains an open question.
Scale. Our largest dense model is 12B parameters, and our largest MoE model is the 8×7B Mixtral.
Although the consistent patterns from 410M to 12B suggest robustness, validation at 70B–400B
scale is necessary to determine whether new geometric effects emerge or whether multi-lobed
manifolds continue to dominate mixed-domain settings.
Task specificity. All models evaluated are general-purpose language models. Domain-specialized
models (e.g., code, mathematics, biomedical, or scientific LMs) may exhibit distinct geometric
patterns. Fine-tuning and RLHF can also reshape geometry; our results for Mistral-7B-Instruct
show modest changes, but richer effects may appear under more aggressive alignment schemes.
Causal probes of the entropy axis. We performed forward-pass value interventions on Pythia-
410M in the SULA setting to test whether the entropy-aligned value axis is merely correlational or
plays a causal role. For each of two “Bayesian” layers (𝐿=12 and 𝐿=23), we first precomputed a unit
direction 𝑢ent whose coefficient 𝑣 · 𝑢ent correlates with predictive entropy. We then applied three
families of interventions at that layer, each with a matched random-axis control: (i) axis-cut, which
removes the component of 𝑣 along 𝑢ent; (ii) axis-only, which projects 𝑣 onto the one-dimensional
subspace spanned by 𝑢ent; and (iii) axis-shift, which adds ±1𝜎 along 𝑢ent based on the empirical
standard deviation of 𝑣 · 𝑢ent.
Representationally, the entropy-aligned axis is clearly special. Cutting along 𝑢ent drives the
correlation between 𝑣 · 𝑢ent and model entropy from 𝜌 ≈ 0.27–0.32 down to nearly zero (and
sometimes slightly negative), whereas cutting along a random axis of equal dimensionality leaves
the correlation largely intact (changes on the order of 10−2). Conversely, axis-only projections
along 𝑢ent preserve or slightly sharpen the correlation, while axis-only projections onto a random
axis almost completely destroy it. Axis-shift interventions along 𝑢ent produce small but directional
changes in SULA calibration (e.g., +1𝜎 shifts slightly improving correlation with the Bayesian
entropy curve), whereas matched random-axis shifts act as near no-ops on both geometry and
calibration.
Behaviorally, however, these single-layer interventions do not yield a clean causal separation.
SULA mean absolute error and correlation with the Bayesian posterior change only modestly
under both true-axis and random-axis cuts, and the true-axis interventions do not consistently
hurt performance more than their random controls. The most conservative interpretation is that
the entropy-ordered manifold is a representationally privileged coordinate system for uncertainty,
but not a singular bottleneck for Bayesian updating: uncertainty information is likely distributed
across multiple dimensions and layers, or the manifold serves as a readout of a more distributed
computation. Establishing stronger causal claims will require multi-layer or multi-axis ablations,
activation patching, or training-time interventions, which we leave for future work.
Theoretical gaps. The emergence of 2D or multi-lobed manifolds in deeper or larger models is not
fully understood. Whether these structures encode multimodal uncertainty, semantic clustering, or
training-set heterogeneity remains an open question. Likewise, the interaction between positional
embeddings, local attention kernels, and geometric formation warrants further study.
, Vol. 1, No. 1, Article . Publication date: January .
Geometric Scaling of Bayesian Inference in LLMs 23
Future directions. Several avenues follow naturally:
• Validate geometric signatures in frontier-scale (70B+) checkpoints and alternative architec-
tures, including SSMs.
• Develop interventional methods for manipulating keys, values, or attention to test causal
roles in uncertainty representation.
• Track geometric evolution during training to identify when and how manifolds, frames, and
focusing emerge.
• Investigate domain-specialized and multilingual models to determine whether Bayesian
manifolds transfer across languages or modalities.
• Apply geometric diagnostics to interpretability and safety, using value-manifold coordinates
or attention entropy as indicators of model reliability or distribution shift.
Overall, the present results motivate a broader research program: understanding transformer
computation through the geometry of hypothesis frames and uncertainty manifolds, and leveraging
this structure for model analysis, interpretability, and principled architecture design.
7.2 Related Work
Our analysis connects to several threads in the interpretability and probabilistic—-mechanistic
modeling literature. We highlight the relationships most relevant to geometric Bayesian structure.
Intermediate predictions and tuned lenses. Tuned-lens methods [4 ] decode intermediate-layer pre-
dictions by training a small linear adapter that maps hidden states back to the model’s output space.
These approaches probe what the model would predict at each layer, whereas our value-manifold
analysis characterizes how the model represents predictive uncertainty. The two perspectives are
complementary: PC1 coordinates correlate with entropy and tuned-lens predictions, suggesting that
uncertainty is encoded geometrically along a small number of directions. Establishing a principled
correspondence between tuned-lens logits and manifold coordinates is an important next step.
Belief-state geometry and computational mechanics. Recent work in computational mechanics
[ 11] shows that belief states in small transformers can be linearly decoded from the residual stream,
revealing simple geometric representations of latent uncertainty. Our results are consistent with
this interpretation: production models appear to maintain analogous belief-state structure, but
encoded predominantly in the value space of the final attention layer. This distinction clarifies
where uncertainty lives in deeper networks and suggests that value manifolds may serve as the
canonical substrate for model beliefs. Preliminary analyses indicate that coordinates along our PC1
axis correlate with tuned-lens predictions and residual-stream belief decoders, but a systematic
alignment between value-manifold axes and decoded belief variables requires additional work and
we leave a full treatment to future work.
Attention entropy, stability, and dynamics. Studies of attention-entropy trajectories [ 8, 15] report
that sharpening can be unstable or highly input-dependent. Our layerwise entropy results align
with these findings: MHA models exhibit strong, stable focusing; GQA models show weaker but
monotone reduction; and sliding-window and MoE architectures often display non-monotone or
noisy behavior. These dynamics reflect architectural constraints on global routing rather than
absence of Bayesian computation, consistent with the separation of static and dynamic geometry
we observe.
Constrained belief-update theories. The constrained-belief-update model of early-layer attention
[ 2 ] predicts that attention patterns should stabilize early, while finer-grained posterior refinements
should occur in value representations. This matches precisely the frame—-precision dissociation
, Vol. 1, No. 1, Article . Publication date: January .
24 Naman Aggarwal, Siddhartha R. Dalal, and Vishal Misra
predicted in Paper 2 and observed empirically here: keys define a stable hypothesis frame, while
values encode uncertainty refinement along low-dimensional axes.
Architectural normalization and geometric structure. Normalization layers and architectural com-
ponents influence geometric clarity. Recent analyses [ 3] show that layer normalization, RoPE
embeddings, and GQA induce characteristic patterns of anisotropy and dimensionality in the
residual stream. Our results refine this picture by showing that such architectural choices modulate
dynamic signatures (especially attention entropy reduction) while leaving the static Bayesian
geometry - value manifolds and orthogonal key frames - largely intact.
Relation to circuit-level interpretability. Circuit-level analyses [9, 12] identify specific mechanisms
such as induction heads, pattern-matchers, and copy circuits. Our work operates at a complementary
scale: we provide a geometric account of the global representational substrate in which such circuits
operate. Attention mechanisms determine which evidence is consulted; key frames define separable
hypothesis directions; and value manifolds encode uncertainty along low-dimensional coordinates.
Mapping specific circuits onto these global geometric structures is a promising direction for future
work.
Overall, the Bayesian geometric lens developed in this series complements prior interpretability
approaches by identifying a stable, architecture-spanning substrate for uncertainty representation
and by revealing how posterior refinement depends on architectural routing. This perspective helps
unify diverse observations in interpretability, probabilistic inference, and model analysis within a
single geometric framework.
8 Conclusion
Transformers trained in tightly controlled settings can implement exact Bayesian inference, and
their gradient dynamics generate a low-dimensional geometric substrate that expresses posterior
structure. In this work, we asked whether this geometric mechanism survives contact with real
language, scale, and heterogeneous training corpora. Our analysis across four model families
shows that it does: large language models organize value vectors along a dominant axis that tracks
predictive entropy, keys remain close to orthogonal frames, and domain restriction reliably collapses
value manifolds into the same low-rank forms observed in synthetic wind-tunnel experiments.
These findings establish that Bayesian-like evidence integration in production models is not a
coincidence of sampling or prompt design. It is supported by a persistent geometric invariant—
an emergent coordinate system along which uncertainty is expressed and evolves as in-context
evidence accumulates. This invariant appears across architectures and training regimes, revealing
a structural inductive bias toward representing inference geometrically, even in the absence of any
explicit Bayesian objective.
Finally, our causal probes refine the mechanistic picture. Interventions that remove or perturb
the entropy-aligned axis selectively disrupt the local geometry of uncertainty, while matched
random interventions do not. Yet, these manipulations do not proportionally degrade Bayesian-like
behavior, implying that no single direction is solely responsible for the computation. The geometric
manifold functions as a stable readout of a distributed inference process rather than a brittle circuit.
Understanding how this distributed mechanism arises, and whether it can be shaped, compressed,
or accelerated, represents an important frontier for both theory and engineering.
LLMs compute Bayesian updates through distributed mechanisms and inscribe the result onto
a low-dimensional entropy-aligned manifold - a representational readout rather than a causal
bottleneck.
, Vol. 1, No. 1, Article . Publication date: January .
Geometric Scaling of Bayesian Inference in LLMs 25
References
[1] Naman Aggarwal, Siddhartha R. Dalal, and Vishal Misra. 2025. The Bayesian Geometry of Transformer Attention.
arXiv:arXiv:2512.XXXXX [cs.LG] https://arxiv.org/abs/2512.XXXXX Paper I of the Bayesian Attention Trilogy.
[2] Naman Aggarwal, Vishal Misra, and Siddhartha R. Dalal. 2025. Gradient Dynamics of Attention: How Cross-Entropy
Sculpts Bayesian Manifolds. arXiv:arXiv:2512.XXXXX [cs.LG] https://arxiv.org/abs/2512.XXXXX Paper II of the
Bayesian Attention Trilogy.
[3] Jimmy Lei Ba, Jamie Ryan Kiros, and Geoffrey E Hinton. 2016. Layer Normalization. arXiv preprint arXiv:1607.06450
(2016).
[4] Nathan Belrose, Minjoon Huh, Anca Dragan, and Dylan Hadfield-Menell. 2023. Tuned Lens: Identifying and Manipu-
lating Interpretable Representations in Language Models. arXiv preprint arXiv:2303.08112 (2023).
[5] Stella Biderman, Hailey Schoelkopf, Quentin Gregory Anthony, Herbie Bradley, Kyle O’Brien, Eric Hallahan, Moham-
mad Aflah Khan, Shivanshu Purohit, USVSN Sai Prashanth, Edward Raff, et al. 2023. Pythia: A suite for analyzing
large language models across training and scaling. International Conference on Machine Learning (2023), 2397–2430.
[6] Tom B. Brown, Benjamin Mann, Nick Ryder, Melanie Subbiah, Jared D. Kaplan, Prafulla Dhariwal, et al . 2020. Language
Models are Few-Shot Learners. Advances in Neural Information Processing Systems 33 (2020), 1877–1901.
[7] Mark Chen, Jerry Tworek, Heewoo Jun, Qiming Yuan, Henrique Ponde de Oliveira Pinto, Jared Kaplan, Harri Edwards,
et al. 2021. Evaluating Large Language Models Trained on Code. arXiv preprint arXiv:2107.03374 (2021).
[8] Kevin Clark, Urvashi Khandelwal, Omer Levy, and Christopher D. Manning. 2019. What Does BERT Look At? An
Analysis of BERT’s Attention. In Proceedings of the 2019 ACL Workshop BlackboxNLP. 276–286.
[9] Nelson Elhage, Neel Nanda, Catherine Olsson, Tom Henighan, Nicholas Joseph, Ben Mann, et al . 2021. A Mathematical
Framework for Transformer Circuits. Transformer Circuits Thread, Anthropic. https://transformer-circuits.pub/2021/
framework/index.html
[10] Nelson Elhage, Neel Nanda, Catherine Olsson, Tom Henighan, Nicholas Joseph, Ben Mann, Amanda Askell, Yuntao
Bai, Anna Chen, Tom Conerly, Nova DasSarma, Dawn Drain, Deep Ganguli, Zac Hatfield-Dodds, Danny Hernandez,
Andy Jones, Jackson Kernion, Liane Lovitt, Kamal Ndousse, Dario Amodei, Tom Brown, Jack Clark, Jared Kaplan,
Sam McCandlish, and Chris Olah. 2021. A Mathematical Framework for Transformer Circuits. Transformer Circuits
Thread, Anthropic. https://transformer-circuits.pub/2021/framework/index.html
[11] Jacob Marks and Max Tegmark. 2024. Computational Mechanics of Transformers: Linear Decomposition of Belief
States. arXiv preprint arXiv:2405.15943 (2024).
[12] Catherine Olsson, Nelson Elhage, Neel Nanda, Nicholas Joseph, Nova DasSarma, et al. 2022. In-Context Learning and
Induction Heads. Transformer Circuits Thread, Anthropic. https://transformer-circuits.pub/2022/in-context-learning-
and-induction-heads/index.html
[13] Catherine Olsson, Nelson Elhage, Neel Nanda, Nicholas Joseph, Nova DasSarma, Tom Henighan, Ben Mann, Amanda
Askell, Yuntao Bai, Anna Chen, Tom Conerly, Dawn Drain, Deep Ganguli, Zac Hatfield-Dodds, Danny Hernandez,
et al . 2022. In-Context Learning and Induction Heads. Transformer Circuits Thread, Anthropic. https://transformer-
circuits.pub/2022/in-context-learning-and-induction-heads/index.html
[14] OpenAI. 2024. OpenAI o1: A New Class of Reasoning Models. OpenAI Technical Report (2024).
[15] Elena Voita, David Talbot, Fedor Moiseev, Rico Sennrich, and Ivan Titov. 2019. Analyzing Multi-Head Self-Attention:
Specialized Heads Do the Heavy Lifting, the Rest Can Be Pruned. In Proceedings of the 57th Annual Meeting of the
Association for Computational Linguistics. 5797–5808.
, Vol. 1, No. 1, Article . Publication date: January .