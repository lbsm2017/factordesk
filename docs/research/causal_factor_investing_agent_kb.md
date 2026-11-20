# Causal Factor Investing: Methodology and Scientific Backdrop

**Agent knowledge base, post-doc level. Companion to a close reading of the source text.**

| Item | Detail |
|---|---|
| Source | Marcos M. López de Prado (2023), *Causal Factor Investing: Can Factor Investing Become Scientific?* Cambridge Elements in Quantitative Finance (series editor R. Rebonato). DOI 10.1017/9781009397315. 92 pages, 8 sections plus appendix. |
| Author of this summary | Written by the factordesk project owner (2026). It is an original summary and study guide of the book, not the book itself. The text is paraphrased and reorganised, and extended with outside literature and original tested code. Short quotations are marked with quotation marks. |
| Attribution | Based on López de Prado, M. M. (2023), *Causal Factor Investing: Can Factor Investing Become Scientific?*, Cambridge University Press, DOI 10.1017/9781009397315. The book is published open access under CC BY-NC 4.0. All ideas marked `[B §x]` belong to the book's author. Read the original for authoritative statements. |
| Licence of this file | Released with the factordesk repository under its noncommercial licence (`LICENSE`), which is in line with the book's CC BY-NC 4.0 terms. The attributed ideas and short quotations remain the book author's. |
| Role in factordesk | The book is cited as a source for scientific rigour, out of intellectual honesty and courtesy to its author. None of factordesk's algorithms are taken from it; it informs how results are worded and qualified. |
| Intended reader | A coding or research assistant, or an analyst, who must review, design or critique factor and systematic-investment research, and write Python that respects the book's methodology. |
| Reading order | Part 1 and Part 2 are mandatory (about 150 lines). Parts 3 to 5 are the scientific and mathematical depth. Part 6 is the critical assessment. Parts 7 and 8 are operational. Part 9 is code. Part 10 is references. |

## Provenance tags used throughout

| Tag | Meaning |
|---|---|
| `[B §x.y]` | Stated in the book, section reference given. Paraphrased, not quoted, unless in quotation marks. |
| `[CTX]` | Context knowledge from the wider literature, not in the book. Reasonably standard, but **verify before citing externally**. |
| `[VERIFIED]` | Reproduced numerically in this session (see Part 11 verification log). |
| `[JUDGMENT]` | Analytical assessment by the author of this guide. Contestable. State it as a judgment when relaying it. |

---

# Part 1. The thesis in one page

1. **Factor models are causal models in disguise.** Choosing least squares (Y regressed on X), reading β as a reward for exposure, reporting p-values for H0: β = 0, and building a portfolio on the ranking of X all presuppose that exposure to X *causes* average return differences. Yet the literature states associational claims and never declares a causal graph. `[B §6.1, §6.3]`
2. **Association is not causation, and causation is not a statistical object.** Causation needs the language of interventions, do[X = x], and extra-statistical assumptions (a causal graph). Conditional probabilities cannot express it. `[B §2]`
3. **Science needs three steps**: observe a pattern (phenomenology), propose a falsifiable causal mechanism (theory), then have independent researchers design experiments that try to break each link (falsification). Factor investing has mostly done only step 1. `[B §3]`
4. **Two ways a factor claim can be spurious.**
   - **Type-A**: noise mistaken for signal (p-hacking, backtest overfitting, selection bias under multiple testing). Fixable with multiple-testing corrections. Gets *less* likely as the sample grows.
   - **Type-B**: association mistaken for causation (omitted confounder, controlled collider, controlled mediator, specification searching, ignored temporal structure). **Not** fixable by multiple-testing corrections. Gets *more* likely to be "significant" as the sample grows, because the biased estimand is measured more precisely. `[B §6.4]`
5. **Omitted confounders generate time-varying risk premia.** With constant true effects, a change in the covariance between the intended exposure X and an unhedged exposure Z moves β̂, even flipping its sign. The usual story ("the market stopped paying for value") may simply be a defective product. `[B §6.4.2.1]` `[VERIFIED]`
6. **Over-controlling is as damaging as under-controlling.** Controlling for a collider or a mediator biases β̂. The econometrics habit of "add everything associated with Y" is wrong. `[B §6.4.2.2]`
7. **Explanatory power is the wrong selection criterion for a causal specification.** A misspecified model can have much higher R² than the correct one (adjusted R² 0.784 versus 0.144 in the book's own experiment). Specification searching on R² manufactures false positives. `[B §6.4.2.3, §7.3]` `[VERIFIED]`
8. **Backtests are not causal evidence.** A backtest is not a controlled experiment, not an RCT, not a natural experiment. Replicating a backtest on another market or period does not make a noncausal association causal. `[B §6.4.1.2]`
9. **Hierarchy of evidence** (strongest to weakest): RCT, natural experiment, simulated intervention (causal graph), observational econometrics/backtest, case study, expert opinion. `[B §6.5]`
10. **Practical stakes.** Causal theories give correct risk and performance attribution, transparency, reproducibility, adaptability, extrapolation to unseen scenarios, surveillance of whether the mechanism still holds, and improvability. `[B §8.3]`
11. **The book's empirical hook**: the Bloomberg-Goldman Sachs Asset Management US Equity Multi-Factor Index (long/short momentum, value, quality, low risk) from 2 May 2007 to 2 Dec 2022 shows annualised Sharpe 0.29 (t = 1.16, p = 0.12), average return 1.13% a year before costs, and a negative Sharpe against a 6-month T-bill risk-free rate. `[B §6.4]` (Not independently re-sourced here.)
12. **What the book does not claim**: that factors do not exist. It claims the evidence presented is insufficient by scientific standards. `[B §6.3]`

---

# Part 2. Operating rules for the agent

Apply these whenever the task touches factor research, anomaly claims, systematic strategy evaluation, performance attribution, or "why did X work/stop working" narratives.

**R1. Classify the claim first.** Is it *associational* ("X is correlated with / predicts Y"), *predictive* ("use X to forecast Y out of sample"), or *causal* ("exposure to X earns/produces Y", "X explains returns", "the premium is compensation for risk X")? State the class explicitly. Causal language triggers the full protocol in Part 7.

**R2. Never write "control for everything" or "add more factors to improve fit".** Controls are chosen from a declared causal graph via the backdoor criterion (or front-door / instrument / design-based identification), never by R², adjusted R², AIC/BIC, t-stats or stepwise search.

**R3. Separate discovery from control.** Stage 1: propose or discover the causal graph (domain theory, discovery algorithms, ML variable search). Stage 2: given the graph, pick the adjustment set for *one* treatment-outcome effect. Stage 2 must be informed by Stage 1, never the reverse. `[B §6.4.2.3]`

**R4. Log every trial.** Any search over specifications, windows, quantiles, universes, controls, hyperparameters or dates is a set of trials. Report the count, and use deflated Sharpe / FWER / FDR adjustments. Type-A correction does **not** cure type-B. `[B §6.4.1]`

**R5. A backtest is a phenomenological artefact.** Do not describe a backtest, an in-sample factor regression, or a replication on other markets as evidence of causation or of a risk premium's mechanism. `[B §6.4.1.2]`

**R6. Use the modus tollens asymmetry correctly.** Causation implies association, so *absence* of association falsifies a causal claim; *presence* of association does not confirm it. `[B §6.5]`

**R7. Label evidence tier** (1 to 6, Part 4.8) on every claim you rely on or produce.

**R8. Distinguish book claims from context and from judgment** using the tags above. In particular, the book's argument that FF93/FF15/C97 are likely type-B spurious rests on a *hypothetical* causal graph (its Figure 23), with the burden of proof shifted to the authors. Do not present it as an empirical demonstration. `[B §7.4]` `[JUDGMENT]`

**R9. Predictive work is legitimate but has its own rules.** If the goal is a forecast (including ML factor timing or rotation), biased factor β̂ is not itself the problem; instability, multiple testing, leakage and regime dependence are. Do not interpret coefficients, SHAP values or feature importances as causal effects, and do not do risk attribution with a misspecified model. `[B §6.1, §7.4]` `[CTX]`

**R10. Declare a causal graph for every causal claim.** Minimum deliverable: node list with roles (treatment, outcome, confounder, mediator, collider, instrument, latent), edge list with direction, time index, and for each edge a falsifiable implication and a candidate design. Use the Claim Card template in Part 7.3.

**R11. Prefer designs over models.** If a natural experiment, RDD, DID or randomised execution experiment is available, it dominates a simulated intervention. `[B §4, §6.5]`

**R12. Be honest about uncertainty in the graph.** The causal graph is an *assumption* in simulated interventions. One can disprove a graph (an effect it posits is statistically absent) but cannot prove it. Report robustness across plausible graphs. `[B §4.3]` `[CTX]`

---

# Part 3. Scientific backdrop

## 3.1 Book map

| Book § | Pages | Content |
|---|---|---|
| 1 | 1 to 2 | Thesis, contributions, "factor zoo" |
| 2 | 3 to 5 | Association vs causation, do-operator, confounder example |
| 3 | 6 to 13 | Three steps of scientific discovery, falsification, demarcation, statistical falsification |
| 4 | 14 to 24 | Causal inference: ATE/ATT/SSB, RCT, natural experiments, simulated interventions, causal discovery, do-calculus |
| 5 | 25 to 30 | Causality in econometrics: OLS is causal, meaning of β, Granger causality |
| 6 | 31 to 51 | Causality in factor investing: causal content, mechanism example, type-A/B spuriosity, hierarchy of evidence |
| 7 | 52 to 63 | Monte Carlo: fork, immorality (collider), chain (confounded mediator), alternative explanation of FF factors |
| 8 | 64 to 68 | Conclusions, black-box critique, incentives, dawn of causal factor investing |
| App. | 69 to 72 | Proofs and Python code |

## 3.2 Philosophy of science: the three steps and their logic `[B §3]`

| Step | Activity | Inference type | Output |
|---|---|---|---|
| 1. Phenomenological | Observe a recurrent association or an exception to one. May model P[X,Y], conditionals, E[Y\|X]. | Induction (enumerative or variative) | A "problem situation": an anomaly without explanation |
| 2. Theoretical | Propose a causal mechanism: a system of structural equations along the causal path, each link testable | Abduction (inference to the best explanation, preferring the least extraordinary hypothesis) | A falsifiable theory "X causes Y through mechanism M" |
| 3. Falsification | Researchers *not* involved in the theory deduce implications and design experiments to refute them | Deduction, modus tollens: if A then B, not B, therefore not A | Theory survives (temporarily) or is refuted; surviving theory poses new problems |

Key points:

- **Pauli's trichotomy**: explanations are correct, wrong, or "not even wrong" (unfalsifiable). Economic rationales for factors (risk-based, investment-based, production-based) are plausible but, as written, experimentally unfalsifiable. `[B §6.2]`
- **Theory has extra-statistical content.** Data and tools can assist (machine learning, discovery algorithms), but interpreting measurements already injects subjective assumptions. If theories could be deduced from observations, experiments would be unnecessary. `[B §3.2]`
- **Parsimony** (Occam): simpler theories are easier to falsify because they control for fewer variables; the surviving parsimonious theory is "fitter," not "truer," and poses harder problems. `[B §3.4]`
- **Mathematical theory vs scientific theory.** A mathematical theory (synthetic a priori, axiom-derived, e.g. Markowitz's portfolio theory as theorems) admits no contrary evidence. A scientific theory (synthetic a posteriori) must expose itself to refutation. Asset-pricing "theory" is theory in the mathematical sense; its physical truth was never established through the three steps. `[B §3.2, fn 27]`
- **Socratic vs scientific method.** Both have three steps (problem, hypothesis, refutation), but Socratic problems are definitional ("what is X?"), hypotheses are definitions, and refutation is a counterexample exposing implicit assumptions. Scientific refutation is an experiment against an explicit mechanism. Not all academic debate is scientific, even when it is mathematical, measured and peer-reviewed. `[B §3.4]`
- **Demarcation.** The book does *not* endorse strict Popperian falsificationism (footnote 1, 14). It only requires that theories conform to evidence in some wide or narrow sense, and its results are claimed to hold under competing accounts (Kuhn, Lakatos and others). `[B §1 fn1, §3.4 fn14]`
- **Exemplar theory: PIN** (Easley, Kiefer, O'Hara, Paperman 1996). Mechanism: order-flow imbalance, market impact, mid-price change, realised losses for market makers, wider bid-ask spread, reduced liquidity, higher volatility. Each link is measurable and individually testable. Risky forecasts: it implied liquidity-provision failures about fourteen years before the 2010 Flash Crash, and VPIN-based liquidity strategies were positioned for it. `[B §3.2, §3.3]`

### Three falsification strategies `[B §3.3]`

1. Show P[Y | do[X=x]] = P[Y]: either the association is noncausal or it was a statistical fluke.
2. Deduce a causal prediction from the mechanism and show E[Y | do[X=x]] ≠ predicted y: there may be a mechanism, but not the one theorised (e.g. the true graph is richer).
3. Deduce from the mechanism the *existence of associations* (no do-operation) and show with ML that they are absent.

Popper's "risky forecasts" are counterfactual statements: E[Y_{X=x'} | X=x, Y=y] ≠ y', the expected outcome in an alternative world where X is set to x', for units where X=x, Y=y actually happened. Because the theory was built without (x', y'), this is a genuine out-of-sample test.

### Statistical falsification `[B §3.4]`

Frequentist testing is a stochastic proof by contradiction:

$$H_0 \Rightarrow P[\text{data}\mid H_0] \ge \alpha;\quad P[\text{data}\mid H_0] < \alpha \vdash \neg H_0 \qquad (1)$$

H0 is never proved, only possibly disproved (Fisher). The decisive distinction is between falsifying (a) associational claims, doable on observational data, and (b) causal claims, which always require an experiment (real or simulated). Econometricians are trained almost exclusively on (a).

## 3.3 Association versus causation, formally `[B §2]`

- Statistical independence: P[X=x, Y=y] = P[X=x]P[Y=y] for all (x, y). Association: inequality for some (x, y).
- A **data-generating process** is a system of structural equations. X *causes* Y when Y is a function of X; that function is a **causal mechanism**.
- The **do-operator** (Pearl 1995): do[X=x] denotes *setting* X to x, as opposed to *observing* X=x. Causation is defined as

$$X=x \text{ causes } Y=y \iff P\big[Y=y \mid do[X=x]\big] > P[Y=y]$$

- A causal graph is a **DAG** (directed acyclic graph). A do-operation is graphically the removal of all arrows into X (this is exactly *ceteris paribus*). The graph shows *which* "other things" are held equal.
- **Confounder**: Z with Z → X and Z → Y. It creates association between X and Y with no arrow between them (ice cream sales, drownings, weather).

Five consequences `[B §2]`:

1. Causality is extra-statistical (mechanisms and interventions); conditional probabilities cannot express it.
2. Association does not imply causation; causation does imply association (for direct causes; footnote 6 concedes canceling paths can hide association, i.e. unfaithfulness).
3. Causality is directional (arrows); association is not.
4. Causality is sequential (X is set first, Y adapts).
5. *Ceteris paribus* simulates an intervention and is only interpretable with the causal graph.

`[CTX]` Pearl's "ladder of causation": (1) association, seeing; (2) intervention, doing; (3) counterfactuals, imagining. The book operates mostly at rung 2 and invokes rung 3 for risky forecasts and stress testing.

## 3.4 The fundamental problem of causal inference `[B §4]`

Define ATE as

$$\text{ATE} = E[Y\mid do[X=x_1]] - E[Y\mid do[X=x_0]] \qquad (2)$$

The observed difference decomposes as

$$\underbrace{E[Y\mid X{=}x_1]-E[Y\mid X{=}x_0]}_{\text{observed}} = \underbrace{E[Y_{x_1}\mid X{=}x_1]-E[Y_{x_0}\mid X{=}x_1]}_{\text{ATT}} + \underbrace{E[Y_{x_0}\mid X{=}x_1]-E[Y_{x_0}\mid X{=}x_0]}_{\text{SSB (self-selection bias)}} \qquad (3)$$

The counterfactual E[Y_{x0} | X=x1] is unobservable, so ATT cannot be read off, and SSB can be large enough to mislead. Under random assignment, potential outcomes are independent of the realised X, so SSB = 0 and observed difference = ATT = ATE (eqs 4 to 6). Every causal design is a method to nullify SSB.

`[CTX]` This is the Rubin potential-outcomes framework; the book uses the same objects with Pearl's notation. Identification assumptions in that language: consistency (well-defined interventions), exchangeability (no unmeasured confounding given adjustment set) and positivity (overlap). See Hernán and Robins (2020).

## 3.5 Designs for estimating or falsifying causal effects `[B §4.1 to 4.3]`

| Design | Who performs the do-operation | Key assumption | Generality of conclusion | Examples (book unless tagged) |
|---|---|---|---|---|
| Controlled experiment | Researcher, controlling *all* variables of the DGP | Full ceteris paribus | Highest | Ibn al-Haytham's camera obscura |
| Randomised controlled trial (RCT) | Researcher, random assignment of units | Randomisation works; mechanism persists (a form of induction) | Very high | Algo-wheel broker experiments (rarely published) |
| Natural experiment (quasi-experiment) | Nature, assignment as-if random | As-if randomness of assignment | High | RDD, crossover (COS), difference-in-differences (DID) |
| Simulated intervention | Nobody: observational data plus a hypothesised graph | The causal graph is correct | Medium | Backdoor/front-door/IV adjustment |
| Not natural experiments (no random assignment) | n/a | n/a | Associational | Case-control, cohort, synthetic control |

**Regression discontinuity (RDD).** Compare units just above and just below an assignment threshold; assumes they are comparable except for the treatment. `[CTX]` Finance uses: Russell 1000/2000 reconstitution cutoff, index inclusion, covenant violations, close-election outcomes.

**Crossover (COS).** Units serve as own controls: exposure randomly removed then reinstated. Needs wash-out periods (carryover) and assumes order effects are absent.

**Difference-in-differences (DID).** (Before-after change of treated) minus (before-after change of control). Requires equal (parallel) trends, which can be tested by checking pre-treatment trends. Origin: Ashenfelter and Card (1986).

**Synthetic control.** Linear combination of untreated units best matching the treated unit pre-treatment. Treated by the book as non-experimental because assignment is not random (Abadie 2021).

**Finance-specific sources of randomness suggested by the book** `[B §3.3, §6.2.1]`: random spikes in order-flow imbalance (market-maker reaction); random timing differences in updates of fundamental data across stocks (to test the HML to order-flow link); algorithmic execution wheels; field studies of market-maker algorithms; alternative datasets (text sentiment, surveys, 13F exposures) to test behavioural links.

## 3.6 Graph theory essentials `[B §4.3.2]`

**Elementary structures** (three variables X, Y, Z):

| Structure | Graph | Z is a... | Association X-Y without conditioning | After conditioning on Z |
|---|---|---|---|---|
| Fork | X ← Z → Y | confounder | Yes (noncausal) | Independent (blocked) |
| Chain | X → Z → Y | mediator | Yes (causal) | Independent (blocked): destroys the effect of interest |
| Immorality | X → Z ← Y | collider | None | Association created (Berkson's fallacy) |

**Blocked paths.** A path is blocked if (1) it traverses a collider and the researcher has not conditioned on that collider or any of its descendants, or (2) the researcher conditions on a non-collider on the path. Association flows along unblocked paths. Causal association flows along the unblocked directed path from X to Y. **Association implies causation only if all noncausal paths are blocked.**

**d-separation.** X and Y are d-separated by S if conditioning on S blocks every path. d-separation by S is equivalent to conditional independence given S (global Markov condition). This licenses

$$\text{ATE} = E\big[\,E[Y\mid S, X{=}x_1]-E[Y\mid S, X{=}x_0]\,\big] \qquad (7)$$

provided S is chosen with the graph.

**Backdoor criterion** (eq. 8). S satisfies it for (X, Y) if (i) S blocks every backdoor path (noncausal path with an arrow into X) and (ii) S contains no descendant of X. Then

$$P[Y{=}y\mid do[X{=}x]] = \sum_s P[Y{=}y\mid X{=}x, S{=}s]\,P[S{=}s]$$

Condition (i) blocks noncausal paths; (ii) keeps causal paths open. There can be several sufficient sets. `[B §4.3.2.2]` (Robins's earlier name: g-formula.)

**Front-door criterion** (eq. 9). Needed when the confounder is latent. S satisfies it if (i) all causal paths X → Y go through S, (ii) no backdoor path from X to S, (iii) all backdoor paths from S to Y are blocked by X. Then

$$P[Y{=}y\mid do[X{=}x]] = \sum_s P[S{=}s\mid X{=}x]\sum_{x'}P[Y{=}y\mid S{=}s, X{=}x']\,P[X{=}x']$$

**Instrumental variables.** W is an instrument for (X, Y) if (i) W → X, (ii) W affects Y only through X, (iii) no backdoor path W to Y. In a linear model, with cov-slopes r:

$$\hat\beta_{IV} = \frac{r_{YW}}{r_{XW}},\quad r_{YW}=\frac{\text{cov}[Y,W]}{\text{cov}[W,W]},\ r_{XW}=\frac{\text{cov}[X,W]}{\text{cov}[W,W]}$$

The naive slope cov[X,Y]/cov[X,X] is biased by the latent confounder. IV is one tool; do-calculus is complete (Shpitser and Pearl 2006) and covers far more.

**Which adjustment when** (decision rule, `[B §4.3.2]` plus `[JUDGMENT]`):

| Situation | Method |
|---|---|
| All confounders observed | Backdoor adjustment |
| Latent confounder, but an unconfounded mediator exists | Front-door |
| Latent confounder, no mediator, a valid instrument exists | Instrumental variable |
| Assignment is as-if random for an identifiable group | Natural experiment (RDD, DID, COS) |
| None of the above | Report as associational; do not claim causal effect |

## 3.7 Causal discovery `[B §4.3.1]`

Search for causal structure from the statistical properties of observational data. It rarely suffices to pin down a graph, but it shrinks the set of compatible structures; at minimum the extra-statistical assumptions must be compatible with the data.

| Class | Representative algorithms | Handles latent confounders? | Notes |
|---|---|---|---|
| Constraint-based | PC (Spirtes, Glymour), FCI | PC: no (assumes causal sufficiency). FCI: yes | Use conditional-independence tests; asymptotically correct under assumptions |
| Score-based | GES (Chickering 2003) | No | Searches Markov equivalence classes; consistent asymptotically but not necessarily in finite samples; sensitive to variable ordering |
| Functional causal models (FCM) | LiNGAM (Shimizu et al 2006), additive noise models (Hoyer et al 2009), post-nonlinear (Zhang and Hyvärinen 2009) | Model-dependent | Y = f(X, ε) with ε independent of X only in the true direction; breaks Markov equivalence ties |

Further points:

- **ML for the variable search, decoupled from specification search.** Mean-decrease accuracy, local surrogate models and Shapley values identify relevant variables with minimal specification assumptions; then discovery algorithms propose links and directions. `[B §4.3.1]` (López de Prado 2020, 2022a)
- **Text-derived graphs.** Laudy et al (2022) apply NLP to news in which authors state views X → Y and aggregate them into DAGs of collective, forward-looking, point-in-time causal beliefs. `[B §4.3.1]`
- **Simulated interventions can falsify but not establish.** The graph is an assumption; one can only disprove it by finding a contradiction between an effect the graph claims and the effect estimated with that same graph (modus tollens). This power of elimination is how the structure is gradually discovered. `[B §4.3]`
- `[CTX]` Practical caveats: Markov equivalence classes (CPDAG output) leave many edge directions undetermined; faithfulness violations; conditional-independence tests have low power with heavy tails, volatility clustering, nonstationarity and strong collinearity. See Part 6.

## 3.8 Causality in econometrics `[B §5]`

Chen and Pearl (2013) reviewed six leading econometrics textbooks and found they deviate significantly from modern causal standards.

**(a) Econometricians mistake causality for association.** Consider Y = β0 + β1 X + ε and X = γ0 + γ1 Y + ζ. If regression parameters described the joint distribution, one fit would be recoverable from the other (γ̂1 = 1/β̂1). Least squares does not have that property. The error term encodes a *direction*: ε is the part of Y not attributable to X; the estimator assumes E[ε|X] = 0. So least squares is not "just" a statement about the joint distribution; it injects a causal graph in which X causes Y. Only the Deming (orthogonal, errors-in-variables) regression characterises the joint distribution without directional information (the book's Figure 5 shows three different lines on the same data).

**(b) Econometricians misread β.** Unbiasedness needs exogeneity, E[ε|X] = 0.

- *Implicit exogeneity*: define ε ≡ Y − E[Y|X]; then exogeneity holds by construction and β is merely a regression slope (associational). This is the textbook approach; it cannot answer interventional questions and contradicts the causal use of the model.
- *Explicit exogeneity*: ε collects all causes of Y uncorrelated with X. Then E[Y | do[X]] = Xβ and

$$\beta = \frac{\partial E[Y\mid do[X]]}{\partial X} \qquad (11)$$

This is causal, and it is valid only if the model is correctly specified, which requires a causal graph. Haavelmo (1944) saw this; most textbooks still teach the associational reading while practitioners use the causal reading.

**(c) Granger "causality" is association.** Test whether lags of X are significant in a regression of Y on its own lags and lags of X (eq. 12). The book's four objections `[B §5.3]`:

1. Sequential association is necessary, not sufficient, for causation (the rooster's crow Granger-causes dawn).
2. A common cause Z of X and Y makes Granger's test falsely conclude X causes Y (it is misleading in causally insufficient multivariate series).
3. Lag selection involves multiple testing (stepwise searches), hence selection bias.
4. It assumes the causal relation is linear.

Granger (1969) had over 33,000 citations and 2,294 new ones in 2021 alone (Google Scholar, 1 Dec 2022). Granger causality can at most help to orient the direction between two *unconfounded* variables; discovery methods do that better.

**(d) Specification-search procedures taught in econometrics** (stepwise, general-to-simple, trial and error) are instances of selection bias under multiple testing, and they substitute fit for a causal graph. `[B §5.1]`

**(e) Economists who did take causality seriously**: P. G. Wright (IV, 1928), Haavelmo (1944), Ashenfelter and Card (DID), Angrist and Pischke ("credibility revolution"), and the 2021 Nobel to Card, Angrist and Imbens. Asset pricing remains largely outside this movement. `[B §5.3]`

---

# Part 4. Factor investing through the causal lens

## 4.1 The two canonical empirical procedures `[B §6]`

| Procedure | Inspired by | Mechanics | Target |
|---|---|---|---|
| Cross-sectional regression | Fama and MacBeth (1973) | For each period regress returns Y on factor X and controls Z: Y = Xβ + Zγ + ε; average the β estimates across periods | Explain *differences across securities*, not time-variation |
| Sorted portfolios and factor-mimicking returns | Fama and French (1993) | Rank by characteristic; (a) quantile portfolios and their average returns; (b) long-short portfolio. Then time-series regress (a) on (b) and controls | Same |

Either way the "finding" is a significant β̂, read as: investors holding exposure to X are rewarded beyond what exposure to Z pays.

## 4.2 Causal content: how factor models reveal an undeclared causal structure `[B §6.1]`

The book defines **causal content** as the set of causal assumptions, declared or not, embedded in a model's specification, estimation, interpretation and use. Four tells:

1. **Specification.** The model is built on the claim that exposure X causes above-market returns Y (a single arrow X → Y) strongly enough to be monetised through a portfolio on X. A researcher interested only in the joint law would use nonparametric ML rather than OLS.
2. **Estimation.** Researchers prioritise unbiased β̂ over predictive power. If they wanted prediction they would use shrinkage (ridge, LASSO, elastic net) or optimise a performance loss (e.g. Sharpe). Choosing OLS signals explicit exogeneity.
3. **Inference.** Emphasis on H0: β = 0 and p-values. Machine learners instead judge importance by MDA, MDI, Shapley values.
4. **Portfolio construction.** Portfolios load on the *exposure* X (ranking by book-to-market), not on the model residual ε. Predictive investors build on the residual, where biased β̂ is irrelevant. Factor investors monetise a causal claim. A multifactor portfolio is combined for diversification, not for a joint prediction.

Conclusion: the target is E[Y | do[X]], simulated on observed data by controlling for confounders (Figure 7: Z → X, Z → Y, X → Y), not E[Y | X, Z].

## 4.3 Omitted mediation analysis and the worked example of a mechanism `[B §6.2]`

Existing rationales (Fama-French 1996 distress risk; Berk, Green, Naik 1999; Johnson 2002; Gomes, Kogan, Zhang 2003; Zhang 2005; Sagi and Seasholes 2007; Liu et al 2009 and others) fail three tests: no declared causal relationship; no articulated ideal interventional study (a thought experiment, *Gedankenexperiment*, would do); and no observational substitute (natural experiment or simulated intervention). Hence they are "not even wrong." Value investors may truly be paid for bearing bankruptcy risk, but *how*, and why is book-to-market the best proxy?

**Illustrative mechanism (explicitly "without a claim of accuracy")** `[B §6.2.1]`:

```
Variables: HML (price minus fundamental value divergence), OI (order-flow imbalance),
PC (price convergence over horizon h), MOM (diverging momentum), BAS (bid-ask spread),
LIQ (liquidity), VOL (volatility)

Edges (numbered as in the book's Figure 8):
 (4) MOM -> HML     momentum pushes prices away from fundamentals, raising HML
 (1) HML -> OI      investors bet on convergence, creating order-flow imbalance
 (2) OI  -> PC      persistent OI has permanent impact, pushing price to value
 (3) MOM -> PC      high MOM delays price convergence
 (5) OI  -> BAS     market makers widen spreads when OI is persistent
 (6) PC  -> BAS     price trends cause market-maker losses, hence wider spreads
 (7) BAS -> LIQ
 (8) BAS -> VOL
```

Structural equations (`:=` means causal, asymmetric assignment):

$$OI_t := f_1[\underbrace{p_t - v_t}_{HML_t}] + \varepsilon_{1,t}\qquad (13)$$
$$p_{t+h}-v_t := f_2[OI_t] + f_3[MOM_t] + \varepsilon_{2,t+h}\ \ (=PC_{t+h})\qquad (14)$$
$$HML_t := f_4[MOM_t] + \varepsilon_{3,t}\qquad (15)$$

Roles and consequences:

- MOM is a **confounder** of HML → PC (HML ← MOM → PC). Observable, so use backdoor adjustment. If MOM were latent, OI is a mediator, so a **front-door** adjustment would work.
- OI is a **mediator**; do not control for it when estimating the total effect of HML on PC.
- BAS is a **collider** (OI → BAS ← PC). Controlling for BAS (or its descendants LIQ, VOL) opens a noncausal path and is a mistake. In the book's text the path is printed as "HML ← OI → BAS ← PC"; with the arrows of Figure 8 it is HML → OI → BAS ← PC. `[VERIFIED]` with the tool in Part 9.
- Falsification experiments per link (book's suggestions): link 1 by a natural experiment exploiting random timing of fundamental data updates across stocks (treatment effect = difference in OI between stocks whose HML has updated and those not yet updated); links 2, 5, 6, 7, 8 by controlled and natural experiments of the Part 3.2 type; link 3 is mathematical (no test needed); link 4 by a cohort split of stocks with similar HML into MOM-increasing vs MOM-reducing groups (not random, so verify comparability), measuring differences in sentiment from text, surveys or SEC 13F exposures.
- Contrast: current journals mainly allow (a) in-sample replication of a backtest and (b) structural-break analysis of in-sample vs out-of-sample performance.

## 4.4 Causal denial `[B §6.3]`

- Associational strategies (statistical arbitrage, sentiment analysis, alpha capture) have no causal content; their claims are distributional (stationarity, ergodicity, normality, homoscedasticity, serial independence, linearity).
- Factor strategies make causal claims, which require stronger evidence and disclosure: (i) all causal assumptions explicit via a graph, (ii) the falsifiable mechanism, (iii) empirical evidence for (i) and (ii).
- Benefits of declaring: (1) role of each variable explicit and do-calculus applicable for de-biasing; (2) a theory can be falsified *without backtests*; even a p-hacked factor can be tested link by link with other datasets, so peer review is not reduced to re-running the author's code.
- The logical inconsistency: researchers inject causal content and use models causally, but never state graph or mechanism; they report β̂ stripped of its causal meaning and p-values as if they measured association strength of unknown origin.
- Slogan: **without a causal mechanism there is no investment theory; without theory there is no falsification; without falsification investing cannot be scientific.**

## 4.5 Taxonomy of spurious factor claims `[B §6.4]`

| Attribute | Type-A spuriosity | Type-B spuriosity |
|---|---|---|
| Definition | Mistaking random variability (noise) for signal: a false association | The association is true (not type-A) but mistaken for causation |
| Typical causes | P-hacking, backtest overfitting, selection bias under multiple testing, publication bias | Misspecification: omitted confounder, controlled collider, controlled mediator, specification searching, ignored temporal structure |
| Error types | Type-1 errors (false positives) | Type-1 and type-2 errors (false positives and false negatives) |
| Number of trials needed | Many | **One is enough** |
| Behaviour as sample size grows | Less likely | **More likely** (the noncausal association is estimated more precisely) |
| Correctable by multiple-testing adjustment? | Yes (Hochberg 1988; Romano and Wolf; Benjamini-Hochberg; Bailey and López de Prado 2014) | **No.** Needs extra-statistical information: a causal theory |
| Expected return of the strategy | Zero before costs and fees, absent serial correlation (Bailey et al 2014) | **Misattributed**: part of the return comes from unintended exposures; premia appear time-varying |
| Relationship | Mutually exclusive by definition: type-B requires a true association | |

The two together explain "the disconnect between the unwavering conviction of academic authors and the underwhelming performance experienced by factor investors."

### Type-A in detail `[B §6.4.1]`

- **P-hacking.** Fama-MacBeth and Fama-French procedures involve millions of defensible combinations (fit window and frequency, number of quantiles, long-short definition, controls, factors, universe, data cleaning, outlier rules, dates). Researchers run many regressions and report the best p-value unadjusted. Publication bias adds a second layer (journals ignore the number of rejected and accepted papers). Harvey, Liu and Zhu (2016): most claimed findings in financial economics are likely false. Other fields adjusted long ago: familywise error rate (Hochberg; White 2000; Romano and Wolf 2005) and false discovery rate (Benjamini and Hochberg 1995); US law since 2008 requires clinical-trial results to be published within a year. The book names ignorance and malpractice as the two explanations, and cites Harvey (2022) on commercial incentives.
- **Backtest overfitting.** A backtest is a historical simulation, not an experiment. It cannot prove or disprove a causal mechanism; at best it indicates economic potential *if history repeats* (an inductive, associational belief). Trial counts are rarely reported (Fabozzi and López de Prado 2018). The **False Strategy Theorem** shows it is easy to overfit by selection bias under multiple testing. Two researchers can mistake the same noise for signal, especially with similar linear specifications. Success on other sectors, geographies or periods is not causal evidence.

### Type-B in detail `[B §6.4.2]`

**Under-controlling: the omitted confounder.** DGP: Y := Xβ + Zγ + u with γ ≠ 0. The researcher fits Y = Xβ + ε, so ε = Zγ + u and E[ε|X] = γE[Z|X] ≠ 0 whenever Z correlates with X. Two sub-cases: Z a *mediator* (X → Z → Y): β̂ is biased as a *direct* effect but can still be read as a *total* effect; Z a *confounder* (Z → X, Z → Y): β̂ measures no causal effect at all. For X := Zδ + v, with (u, v, Z) standard normal iid:

$$E[\hat\beta\mid X] = \beta + \theta,\qquad \theta = \gamma\,\delta\,(1+\delta^2)^{-1}\qquad (16)$$

(Proof in the book's Appendix A.1: condition the Gaussian pair (v, X) to get E[v|X] = X/(1+δ²).) Bias requires **both** γ ≠ 0 and δ ≠ 0. `[VERIFIED]` (Part 11).

Consequences:

1. **Misattributed performance and risk.** The investor is exposed to the intended causal association (β) plus an unintended noncausal one (θ) that a correct model would have hedged.
2. **Time-varying risk premia without any change in true premia.** Take β > 0 and γ > 0 constant. Merely changing δ over time moves β̂; for sufficiently negative δ, β̂ < 0. Investors are told the market now punishes X when the true culprit is a changed covariance between X and Z. The literature explains time-varying premia by changing expected returns (Evans 1994, Anderson 2011, Cochrane 2011), and marketing departments by temporary behaviour; the book argues a missing confounder is the more parsimonious explanation. Example: under-controlling MOM in the value strategy (Figure 8) exposes it to changes in cov(MOM, HML), while the direct effects HML → PC and MOM → PC never changed.
3. **Partial correlation** (adding Z as a regressor) is the standard linear implementation of backdoor adjustment, valid for linear effects and elliptical (including multivariate normal), multivariate hypergeometric, negative hypergeometric, multinomial or Dirichlet laws (Baba et al 2004). It is fragile under multicollinearity.

**Over-controlling.** Econometrics textbooks (e.g. Greene 2012 §4.3.3) treat adding irrelevant variables as harmless apart from precision. Do-calculus shows otherwise:

- **Colliders**: conditioning opens the backdoor path the collider was blocking (Berkson's fallacy).
- **Mediators**: conditioning blocks the mediated effect; leaves only the direct effect. The mediated effect can be recovered as total minus direct.
- Over-controlling a collider and under-controlling a confounder have the *same* graphical effect: letting association flow through a noncausal path; hence the same two symptoms (biased β̂, time-varying premia).
- Pearl and MacKenzie: mistaking a mediator for a confounder is among the deadliest sins in causal inference.
- Black-box funds take over-controlling to the extreme, which may explain why they switch from systematic profits to systematic losses with no early warning.

**Specification searching.** Choosing variables and functional forms by explanatory power. FF15 justified adding profitability and investment factors because the five-factor model "performs better when used to explain average returns." This is self-contradictory for a causal model: explanatory power is associational and cannot carry the extra-statistical information needed to deconfound. It merges two sequential stages, **(1) causal discovery** and **(2) control**, whereas stage (2) must be informed by stage (1). The correct specification is not the one that predicts Y best but the one that debiases β̂ for a *single treatment*. Specification searching causes *specification bias*, a different problem from p-hacking's *selection bias*, and is not repaired by multiple-testing corrections. Two defences and their rebuttals: (a) interaction effects are a stage-2 question needing a stage-1 graph; (b) showing two causes are not redundant is better done with mutual information or variation of information (López de Prado 2020, ch. 3).

**Temporal properties.** Independent series appear associated if nonstationary (Granger and Newbold 1974) or if stationary but strongly autocorrelated or smoothed (Granger, Hyung, Jeon 2001), irrespective of sample size. Unit-root and cointegration analyses fix residual distribution concerns but do not address type-B; time-series models still need a causal specification.

**Multicollinearity** note (fn 34): under the Gauss-Markov assumptions it inflates variance only; when they fail, it can amplify the bias of a misspecified model (Kalnins 2022).

## 4.6 Hierarchy of evidence `[B §6.5]`

| Rank | Type | Inference | Rigor | Finance example |
|---|---|---|---|---|
| 1 | Randomised controlled trials | Deduction (with partial induction) | Very high | Algo-wheel experiments |
| 2 | Natural experiments | Deduction with weak assumptions | High | Market-maker reaction to random order-imbalance spikes |
| 3 | Simulated interventions | Deduction with strong assumptions | Medium | Effect of HML estimated with a causal graph |
| 4 | Econometric (observational) studies | Enumerative induction | Low | Factor literature, backtested strategies |
| 5 | Case studies | Variative induction | Very low | Broker report or analysis |
| 6 | Expert opinion | Heuristic | Anecdotal | Investment guru's prediction |

Notes:

- Rows 1 to 3 use the formal language of causal inference and so permit statistical falsification of a causal claim; rows 4 to 6 are associational/phenomenological and highly susceptible to type-A and type-B spuriosity.
- "Strong assumption" means one whose validity implies several weaker ones (a correct causal graph implies invariance, stationarity, ergodicity); the converse fails.
- Controlled experiments on financial systems are presently impossible (complexity, ethics, regulation).
- **Out-of-sample is not an evidence category.** It describes *when* data was collected. It helps against type-A but not necessarily type-B (stock-bond correlation measured out of sample still does not show that one price causes the other).
- Associations are not useless: they drive step 1, and causal mechanisms imply associations whose absence falsifies the theory (modus tollens on C ⇒ A).

## 4.7 The Fama-French critique and Figure 23 `[B §7.4]`

Objections to FF93 (market, size, value), FF15 (adds profitability and investment) and C97 (Carhart adds momentum):

1. Trials not reported or adjusted: likely p-hacking.
2. Specification justified by explanatory power, not a graph: likely specification bias.
3. Known macro confounders ignored (inflation, GDP, business cycle, yield-curve slope). FF93 §2.1.2 itself notes business-cycle confounding of size, yet it is not in the model: a missing confounder.
4. Momentum and value interact (Barroso and Santa-Clara 2015); momentum plausibly confounds value, so is a likely missing confounder. Carhart's justification for adding it was fit, not de-confounding. Moreover adding the highly correlated momentum control exchanges confounder bias for multicollinearity; backdoor adjustment (not partial correlations through an inverted covariance matrix) would avoid that.
5. No causal mechanism, obstructing mediation analysis and falsification.
6. **Collider objection.** If returns and size are independent and both affect book-to-market equity, then book-to-market is a collider; conditioning on it manufactures a negative noncausal association between returns and size, which could make the size factor a false discovery.

Figure 23 (as drawn): Market → Ret (1), Ret → HML (2), SML → HML (3), MOM → HML (4), MOM → Ret (5), with HML shaded as the conditioned variable (a collider of Ret, SML and MOM). `[VERIFIED]` with the Part 9 tool: for the effect of SML on Ret, the empty adjustment set is valid and conditioning on HML is flagged as a bad control.

Caveats stated by the author: the graph "may not be correct, however the burden of proving it wrong belongs to the authors"; these three papers are "as good as any other associational financial econometric study" and remain deeply influential; for a *predictive* purpose biased coefficients would not matter, but factor portfolios rank on the characteristic, not the residual, so the coefficient's meaning does matter.

## 4.8 The Monte Carlo experiments `[B §7]` `[VERIFIED]`

All three use 5,000 observations of standard normal innovations, `np.random.seed(0)`, and OLS through statsmodels. The book's code is in the Appendix B; the version in Part 9 reproduces its output.

| Experiment | DGP (all innovations N(0,1) independent) | Truth | Misspecified model | Result of misspecified model | Correct model |
|---|---|---|---|---|---|
| 7.1 **Fork** (omitted confounder) | Z := ξ; X := Z + ε; Y := Z + ζ | X does not cause Y | Y on X | β̂ ≈ 0.50, t ≈ 40 (false positive), adj. R² 0.247 | Y on X and Z: β̂ ≈ 0.00 |
| 7.2 **Immorality** (controlled collider) | X := ε; Y := ζ; Z := X + Y + ξ | X does not cause Y | Y on X and Z | β̂ ≈ −0.50, t ≈ −40 (false positive), **adj. R² 0.499** | Y on X alone: β̂ ≈ 0.00, adj. R² ≈ 0.000 |
| 7.3 **Chain with confounded mediator** | X := ε; W := η; Z := X + W + ξ; Y := Z + W + ζ | X causes Y with total effect 1 | Y on X and Z | β̂ ≈ −0.48 (wrong sign), **adj. R² 0.784, F 9,069** | Y on X alone: β̂ ≈ 1.01, adj. R² 0.144, F 840.8 |

Lessons:

- Analytical result in 7.2: conditioning on the collider Z gives Cov[X, Y | Z] = −1/3 (Appendix A.2). `[VERIFIED]` (sample about −0.32 at n = 5,000).
- In 7.3, Z is a mediator *and* a collider of X and W, so controlling it opens X → Z ← W → Y: the **mediation fallacy**. This is also a **Simpson's paradox** reversal. By do-calculus the unconditional regression is unbiased because Z already blocks the path via W; adding W would only improve precision.
- In 7.2 and 7.3 the *wrong* model has dramatically higher explanatory power, so a specification-searching researcher selects the false positive.
- Footnote 38 of the book observes that if Z were the treatment, X would be a valid instrument for Z; in this graph Z is a mediator and X is the treatment.

---

# Part 5. Conclusions of the book and the economics of the field

## 5.1 Why theories matter to investors `[B §8]`

1. Theories deter type-A spuriosity: they force researchers to justify modelling choices and open the possibility that others design an experiment where the random variation does not appear.
2. **Causality is a necessary condition for investment efficiency**: correct attribution lets investors hold only rewarded risks and hedge unrewarded ones.
3. **Counterfactual stress testing**: causal models can answer questions about not-yet-observed scenarios (cf. Rebonato 2010; Rebonato and Denev 2014; Denev 2015; Rodríguez-Domínguez 2023), where associational models leave investors exposed to black swans.

## 5.2 The eight attributes of causal factor investing `[B §8.3]`

| Attribute | Meaning |
|---|---|
| Efficiency | Correct risk and performance attribution; concentrate on rewarded risk, hedge the rest |
| Interpretability | Fiduciaries can explain why plans (e.g. retirement) may be delayed |
| Transparency | The graph exposes all assumptions; not a black box |
| Reproducibility | Search space confined to plausible theories (less type-A) and some assurance the phenomenon persists while the mechanism persists (less type-B) |
| Adaptability | Associational profits need the whole joint distribution to be stable; causal strategies are robust to changes that do not touch parameters on the causal path |
| Extrapolation | Only a causal theory can profit from tail events by monitoring their trigger conditions (PIN and the 2010 Flash Crash) |
| Surveillance | Mechanism health can be monitored directly, possibly divesting before a structural-break test fires; enables factor timing, bet sizing, tactical allocation |
| Improvability | Theories can be refined; performance need not decay unavoidably toward zero |

## 5.3 Black box, incentives and institutional implications `[B §8.1, §8.2]`

- Value funds lost heavily between late 2017 and early 2022; investors never got a straight answer to "why", because nobody knows why value should have worked or what flipped the sign of β̂, a hallmark of type-B factors.
- Factor products are sold through inductive arguments, while disclaimers say "past performance is not indicative of future results."
- Scale: J.P. Morgan estimated more than USD 2.5 trillion (above 20% of US equity market cap) in quant-style funds in 2019; BlackRock estimated USD 1.9 trillion in factor investing in 2017, projecting USD 3.4 trillion by 2022. The industry was built on academic output, not on investor results.
- Harvey (2022): economic incentives, not science, may drive the academic agenda, because associational studies are cheaper and easier. Scientific societies (ASA, AMS, RSS) have warned about p-hacking and non-reproducibility.
- Institutions (pensions, sovereign funds, endowments, insurers) should ask whether black-box factor products are investment grade. The author suggests that academics collaborate with non-commercial asset managers (sovereign wealth funds, endowments).

---

# Part 6. Critical assessment (post-doc level)

All of this part is `[JUDGMENT]` unless tagged otherwise. Use it to avoid both uncritical adoption and naive dismissal of the book.

## 6.1 What is robust

- The collider/mediator/confounder analysis is textbook correct and reproduced exactly `[VERIFIED]`. "Control for everything" is demonstrably wrong; R² is not a valid criterion for a causal specification.
- The type-A / type-B taxonomy is a useful diagnostic: it tells you *which remedy* applies (multiple-testing correction versus structural identification) and why a larger sample can worsen the second kind.
- The observation that OLS, p-values on β, and long-short portfolios on a characteristic presuppose a causal reading is a strong argument about the *practice* of the literature.
- The hierarchy of evidence and the demand for link-by-link falsifiable mechanisms are good research-governance rules regardless of how one scores the literature.

## 6.2 What is contestable

1. **Existence proof, not prevalence.** The Monte Carlo shows that type-B spuriosity *can* produce the observed pathologies. It does not show that the actual FF/C97 coefficients are biased. The Figure 23 graph is hypothetical; the "burden of proof" shift is rhetorical. A stronger empirical stance would use **sensitivity analysis** (how strong must an unobserved confounder be to explain away the estimate; Cinelli and Hazlett 2020 `[CTX]`) and **multi-graph robustness** (does the estimate survive across plausible DAGs).
2. **What is the estimand in asset pricing?** In the stochastic-discount-factor view (Cochrane 2005) a factor is a source of covariance with the SDF, and λ is a *risk price*. The question is whether exposure to a priced state variable is compensated, not whether a characteristic "causes" return. Characteristics-versus-covariances debates (Daniel and Titman 1997 `[CTX]`) show rival readings. The book's claim is strongest for characteristic-sorted strategies sold as exposure to a causal premium, weaker as a statement about equilibrium pricing theory itself.
3. **Well-defined interventions.** Book-to-market is a ratio containing *price*; "setting" it intervenes on a quantity mechanically tied to future returns. A usable estimand must be time-indexed (BM_t → R_{t+1}), and the intervention is better defined at the portfolio policy level (a counterfactual allocation rule) than as manipulating a single stock's characteristic. Consistency and no-interference (SUTVA) are doubtful in markets where one asset's treatment moves others through market clearing. `[CTX]`
4. **Equilibrium, feedback and reflexivity.** Markets are systems with simultaneity and learning; acyclic DAGs need time-unrolling (the book's footnote 5 concedes cyclic graphs may be preferable). Mechanisms can erode once discovered (post-publication decay, McLean and Pontiff 2016 `[CTX]`). A causal mechanism in finance may therefore be *non-stationary by design*, which weakens the "invariance gives adaptability" argument. The book argues causal strategies are resilient to changes off the causal path; changes *on* it still bite.
5. **Causal discovery is weak in financial data.** PC/GES assume iid samples, faithfulness and (PC) causal sufficiency; asset data show heavy tails, volatility clustering, nonstationarity, high collinearity and pervasive latent macro states. FCI relaxes sufficiency but returns partial ancestral graphs that are weakly informative. In practice the graph is mostly *theory-driven*, and the data eliminate rather than confirm. `[CTX]`
6. **Natural experiments are local.** RDD identifies a local effect at the threshold; DID identifies effects for the treated; neither maps to a portfolio-level premium without strong extrapolation. They remain the right tools for *individual links* of a mechanism. `[CTX]`
7. **Linearity and constant effects.** The partial-correlation route assumes linear effects and suitable distributions. Nonlinear or heterogeneous effects call for nonparametric or double/debiased ML (Chernozhukov et al 2018 `[CTX]`), whose automated control selection can itself include colliders (Hünermund, Louw, Caspi 2023 `[CTX]`).
8. **Replication debate is open.** Harvey, Liu and Zhu (2016) and Hou, Xue, Zhang (2020) support widespread false discoveries; Jensen, Kelly, Pedersen (2023) and Chen and Zimmermann (2022) argue most documented factors replicate under suitable methods `[CTX]`. Treat the *severity* of type-A as unsettled. The multi-factor index evidence (Sharpe 0.29, 2007 to 2022) is a single implementation and window, dominated by the long drawdown in value, and is illustrative rather than a population estimate.
9. **Predictive use.** For forecasting, the book is right that biased β̂ is not itself disqualifying. But in regime change a predictor tied to non-causal parents tends to be less stable; invariance-based work (Peters, Bühlmann, Meinshausen 2016; Arjovsky et al 2019 `[CTX]`) is the formal route, with its own assumptions.
10. **Taxonomy is definitional.** "Type-A and type-B are mutually exclusive" holds per claim by construction; a real estimate can be a noisy fit of a biased estimand. Use them as diagnostic axes, not a partition of reality.
11. **Table 2 fallacy.** `[CTX]` In a multi-variable regression, only the coefficient of the designated treatment (given an adjustment set for it) has a causal reading; control coefficients are generally not causal effects (Westreich and Greenland 2013). Reading all coefficients of FF-type regressions as risk prices is therefore doubly suspect, and the book's "single treatment" framing is the correct one.
12. **Arithmetic check.** `[VERIFIED]` For an annualised Sharpe of 0.29 under iid Gaussian returns and a one-sided 5% test, the minimum track record is about 8,100 daily observations, i.e. about 32 years, versus "over 31 years" in the book. The difference is rounding or distributional moments; the conclusion is unaffected.

## 6.3 Open research agenda

- Time-indexed causal graphs for characteristics (BM_t, MOM_t, etc.) with explicit lags and latent macro states.
- Natural-experiment catalogue for market mechanisms `[CTX]`: index reconstitution cutoffs, staggered disclosure and fundamental-data timing, short-sale regulation pilots, tick-size pilots, margin-rule changes, randomised execution (algo wheels), ETF-flow shocks.
- Standard sensitivity analysis and multi-DAG robustness in factor papers.
- Pre-registration and trial logs for factor claims; deflated-Sharpe-style reporting by default.
- Causal ML that restricts controls to DAG-admissible sets.
- Mechanism-monitoring dashboards (surveillance) instead of only statistical structural-break tests.

---

# Part 7. Operational protocols and checklists

## 7.1 Causal factor research protocol (use as a pipeline spec)

1. **Define the estimand.** Write it as a do-statement and a portfolio policy: E[R_{t+1} | do(policy = tilt on X)] minus the baseline. Define horizon, universe, rebalancing and costs.
2. **Elicit mechanisms.** List candidate causal chains X → M1 → M2 → … → Y with measurable intermediate variables (the PIN and HML/OI/PC examples are templates).
3. **Draw the DAG.** Time-indexed; mark latent nodes; classify every node's role relative to (X, Y). Use `causal_dag_tools.node_roles`.
4. **Derive falsifiable implications per edge** and attach a design (RCT/algo-wheel, natural experiment, simulated intervention) and a dataset for each.
5. **Select identification.** Backdoor if confounders are observed; front-door if confounder latent with an unconfounded mediator; IV if a valid instrument exists; natural-experiment design where assignment is as-if random. Use `minimal_backdoor_sets`, `is_front_door_set`, `is_instrument`.
6. **Pre-specify the adjustment set** from the DAG. Record excluded variables with the reason (mediator, collider, descendant, instrument).
7. **Check robustness across alternative valid sets and alternative plausible DAGs.** Report where estimates differ. Run sensitivity analysis to unobserved confounding `[CTX]`.
8. **Estimate** with an appropriate estimator (OLS with the adjustment set; IPW or DML for nonlinear effects with DAG-restricted controls). Use HAC or cluster-robust errors; check stationarity and spurious-regression risk.
9. **Account for trials.** Log every variant; compute MinTRL and deflated Sharpe (`multiple_testing_tools`); apply FWER or FDR across the family of claims.
10. **Attempt falsification**: placebo outcomes, negative-control exposures, pre-trend checks (DID), edge-by-edge tests, risky forecasts on data not seen during theory building.
11. **Report** with the Claim Card (7.3): graph, mechanism, evidence tier, trial count, status. Do not describe a result as a "risk premium" unless a mechanism has survived falsification.
12. **Monitor**: track mechanism variables, not just returns, so that weakening of a link can trigger de-risking before a structural-break test does.

## 7.2 "Should I control for Z?" decision table (effect of X on Y)

| Role of Z relative to X → Y | Control? | Reason |
|---|---|---|
| Confounder (Z → X and Z → Y), observed | **Yes** | Blocks a backdoor path (backdoor criterion) |
| Proxy of a latent confounder | Usually yes, with caution | Reduces but does not remove bias `[CTX]` |
| Mediator (X → Z → Y) | **No** for the total effect | Removes the mediated effect; with a shared cause of Z and Y it opens a noncausal path (mediation fallacy) |
| Mediator, when the *direct* effect is the estimand | Yes, but only if Z and Y are unconfounded | Otherwise the direct-effect estimate is biased |
| Collider (X → Z ← Y, or any Z with two arrows pointing in on a path) | **No** | Conditioning opens a path (Berkson) |
| Descendant of a collider | **No** | Partially conditions on the collider |
| Descendant of X (post-treatment) | **No** | Violates backdoor condition (ii) |
| Pre-treatment collider (M-bias: X ← A → M ← B → Y) | **No** | Conditioning opens X ← A → M ← B → Y |
| Cause of Y only (Z → Y) | Optional | Improves precision, safe |
| Cause of X only (an instrument-like Z → X) | **No** (as a covariate) | Costs precision and can amplify residual confounding bias `[CTX]` |
| Variable correlated with Y but role unknown | **Do not add** | Role must come from the graph |

## 7.3 Claim Card template (YAML)

```yaml
claim: "Plain-language statement"
claim_type: causal | predictive | associational
estimand: "E[R_{t+1} | do(policy)] - E[R_{t+1} | do(baseline)], horizon, universe"
dag:
  nodes: {X: treatment, Y: outcome, Z1: confounder, M1: mediator, C1: collider, U: latent}
  edges: ["Z1->X", "Z1->Y", "X->M1", "M1->Y", "X->C1", "Y->C1"]
  time_index: "t for characteristics, t+1 for returns"
assumptions: ["no unmeasured confounding given S", "stable mechanism over sample", "..."]
mechanism: "X -> M1 -> Y with measurable links and signs"
falsifiable_implications:
  - {link: "X->M1", test: "natural experiment on staggered data release", design: natural, data: "..."}
identification:
  strategy: backdoor | front-door | iv | rdd | did | rct
  adjustment_set: ["Z1"]
  excluded_controls: {M1: "mediator", C1: "collider"}
trials:
  n_trials: 0
  log_location: "path/or/url"
multiple_testing: {method: "DSR | BHY | Romano-Wolf", result: "..."}
evidence_tier: 1-6
status: untested | survives | falsified
```

## 7.4 Red-flag checklist for a factor paper, backtest or manager pitch

- [ ] No causal graph, yet the language is causal ("drives", "earns", "compensation for risk").
- [ ] Specification justified by R², adjusted R², AIC, or "the model performs better at explaining returns".
- [ ] More factors added "to improve fit" without a stated de-confounding rationale.
- [ ] Controls include variables downstream of X (valuation ratios, liquidity, spreads, volatility that react to the treatment) or common effects of X and Y.
- [ ] Number of trials, variants, windows, universes not reported; no deflated Sharpe or FWER/FDR.
- [ ] "Robustness" consists of the same backtest on other markets/sectors/periods.
- [ ] Time-varying premium explained by "behavioural change" without examining changes in covariance with omitted exposures.
- [ ] Out-of-sample window is short relative to MinTRL and called conclusive.
- [ ] Granger "causality" presented as causal evidence.
- [ ] Regression coefficients on control variables interpreted as risk prices.
- [ ] No mechanism with testable links; or a mechanism that cannot be falsified.
- [ ] Risk attribution built on a model whose specification was selected by fit.
- [ ] Marketing contradicts the legal disclaimer (inductive promise versus "past performance...").

## 7.5 Due-diligence questions for factor and systematic managers (allocator use)

1. What is the economic mechanism by which the premium arises? Can you draw it as a graph with measurable intermediate variables?
2. Which links have been tested by natural experiments or randomised execution, and with what results?
3. Which variables do you control for, and why is each one neither a mediator nor a collider?
4. How many specifications, windows, universes and variants were tried? What is the deflated Sharpe and the minimum track record length?
5. Why did the strategy underperform in the last drawdown? Which link of the mechanism weakened, and how did you observe it?
6. What would falsify your thesis? What do you monitor now to detect that early?
7. How is risk attributed: by a graph-informed model or a fit-selected regression? What unhedged exposures could be driving returns?
8. Is the product sold as a causal premium or as a predictive signal? Are the fees and sizing consistent with the evidence tier?

## 7.6 Predictive and ML strategies: what this book implies and does not imply `[B §6.1, §7.4]` `[CTX]` `[JUDGMENT]`

- If the deliverable is a forecast or a rotation signal (for example ML models selecting among factor ETFs), the claim class is **predictive**. A biased linear β̂ is not what breaks it. What breaks it: leakage, overlapping labels, multiple testing across features/models/horizons, regime dependence and non-stationarity.
- Do not narrate a predictive result causally ("value works because ..."). If a narrative is needed, build the DAG and test the mechanism separately.
- Feature importance (MDI, MDA, SFI, SHAP) measures predictive association. It cannot tell mediators from confounders from colliders. Use it for variable search (Stage 1 helper), not as a control-selection rule.
- Good predictive hygiene, from the author's earlier work `[CTX]` (Advances in Financial Machine Learning, Machine Learning for Asset Managers): purged and embargoed cross-validation, combinatorial purged CV, deflated Sharpe, probability of backtest overfitting, trial logging, and feature-importance diagnostics.
- A predictive model's profits are only as stable as the joint distribution; document which structural assumptions that stability depends on. Prefer features with a plausible mechanism, since they offer a surveillance channel.

---

# Part 8. Worked mini-cases for the agent

## 8.1 Reading the HML example with the toolkit

Encode Figure 8 and ask the tool. Expected: minimal backdoor set for HML → PC is {MOM}; the empty set is invalid; adding BAS is flagged (post-treatment descendant); adding OI is flagged (mediator); with MOM latent, {OI} satisfies the front-door criterion. (Run `python causal_dag_tools.py` in Part 9; output reproduced in the verification log.)

## 8.2 Diagnosing "the value premium flipped sign"

1. Write the claim as causal: value (HML) earns a premium.
2. List plausible confounders (momentum, profitability, business-cycle state, rates, liquidity regimes) and colliders (valuation ratios of returns-and-size, spreads).
3. Fit the rolling regression without and with the backdoor set; compare β̂ paths. If β̂ tracks cov(X, Z) changes (see `time_varying_premium`), the "regime change in the premium" is likely under-controlling.
4. Report which of the two explanations the data allow you to distinguish, and which needs a natural experiment.

## 8.3 Is this control a collider?

Procedure: draw the arrows *into* the candidate control; if two or more arrows from variables on a path between X and Y point into it (or into its descendants), do not condition on it. If the arrow direction between a candidate and X is unknown from theory, the graph is not identified for this purpose: say so, and run both specifications as a sensitivity check rather than picking by R².

---

# Part 9. Code appendix (tested)

All code below was executed in the session that produced this guide. Requirements: Python 3.10+, `numpy`, `scipy`, `statsmodels`, `networkx >= 3.3`.

## 9.1 `causal_dag_tools.py`

```python
"""
causal_dag_tools.py
Minimal graphical tools for causal factor research (backdoor, front-door, instrument,
role classification, bad-control audit). Pure networkx; no estimation here.

Convention: G is a nx.DiGraph (acyclic). Latent variables are nodes too; pass `observed`
to restrict which nodes may be used as controls.
Requires networkx >= 3.3 (nx.is_d_separator).
"""
from __future__ import annotations
from itertools import combinations
import networkx as nx


def _as_set(v):
    return {v} if isinstance(v, str) else set(v)


def _cut_out_edges(G, nodes):
    """Graph with every edge leaving `nodes` removed (G underbar). Keeps backdoor paths only."""
    H = G.copy()
    H.remove_edges_from([(u, v) for u in nodes for v in list(G.successors(u))])
    return H


def is_backdoor_adjustment_set(G, x, y, S):
    """Pearl backdoor criterion: (i) S has no descendant of X; (ii) S d-separates X,Y once
    all arrows leaving X are deleted (only noncausal paths remain)."""
    X, Y, S = _as_set(x), _as_set(y), _as_set(S)
    desc = set().union(*[nx.descendants(G, n) for n in X])
    if S & (desc | X | Y):
        return False
    return nx.is_d_separator(_cut_out_edges(G, X), X, Y, S)


def minimal_backdoor_sets(G, x, y, observed=None, max_size=4):
    """Brute-force all minimal valid backdoor sets drawn from observed non-descendants of X."""
    X, Y = _as_set(x), _as_set(y)
    desc = set().union(*[nx.descendants(G, n) for n in X])
    pool = sorted((set(observed) if observed is not None else set(G.nodes)) - desc - X - Y)
    found = []
    for k in range(0, max_size + 1):
        for S in combinations(pool, k):
            if any(set(f) <= set(S) for f in found):
                continue  # superset of an already-found minimal set
            if is_backdoor_adjustment_set(G, X, Y, set(S)):
                found.append(S)
    return found


def is_front_door_set(G, x, y, S):
    """Front-door criterion (Pearl 2009; book eq. 9) for singleton X, Y."""
    (X,), (Y,), S = tuple(_as_set(x)), tuple(_as_set(y)), _as_set(S)
    G_wo_S = G.copy(); G_wo_S.remove_nodes_from(S)
    c1 = not (X in G_wo_S and Y in G_wo_S and nx.has_path(G_wo_S, X, Y))        # S intercepts all causal paths
    c2 = nx.is_d_separator(_cut_out_edges(G, {X}), {X}, S, set())               # no backdoor X -> S
    c3 = nx.is_d_separator(_cut_out_edges(G, S), S, {Y}, {X})                   # X blocks backdoor S -> Y
    return c1 and c2 and c3


def is_instrument(G, w, x, y):
    """Graphical IV conditions (book Sec. 4.3.2.4): W->X relevant, no W-Y association
    except through X (W d-separated from Y after deleting arrows leaving X)."""
    relevant = not nx.is_d_separator(G, {w}, {x}, set())
    exclusion = nx.is_d_separator(_cut_out_edges(G, {x}), {w}, {y}, set())
    return relevant and exclusion


def node_roles(G, x, y):
    """Classify every other node relative to treatment X and outcome Y."""
    roles = {}
    desc_x, anc_x = nx.descendants(G, x), nx.ancestors(G, x)
    desc_y, anc_y = nx.descendants(G, y), nx.ancestors(G, y)
    for n in G.nodes:
        if n in (x, y):
            continue
        r = []
        if n in anc_x and n in anc_y:
            r.append("confounder (or ancestor of both)")
        if n in desc_x and n in anc_y:
            r.append("mediator (on a causal path X->..->Y)")
        if n in desc_x and n in desc_y:
            r.append("collider/descendant of both X and Y")
        elif n in desc_x:
            r.append("descendant of X")
        if n in desc_y and n not in desc_x:
            r.append("descendant of Y")
        if not r:
            r.append("other")
        roles[n] = r
    return roles


def audit_controls(G, x, y, controls):
    """Verdict on a proposed control set S for the effect of X on Y.
    Flags: post-treatment mediators, other descendants of X (possible collider bias), and
    pre-treatment colliders (M-bias). `backdoor_paths_open` is True if a noncausal path survives."""
    S = _as_set(controls)
    desc_x, anc_y = nx.descendants(G, x), nx.ancestors(G, y)
    H = _cut_out_edges(G, {x})
    bad = {}
    for c in S:
        if c in desc_x and c in anc_y:
            bad[c] = "mediator: removes the mediated part of the total effect; if mediator and outcome share a cause, it opens a noncausal path (mediation fallacy)"
        elif c in desc_x:
            bad[c] = "post-treatment descendant of X: violates backdoor condition (ii), collider/selection bias risk"
        elif nx.is_d_separator(H, {x}, {y}, S - {c}) and not nx.is_d_separator(H, {x}, {y}, S):
            bad[c] = "pre-treatment collider (M-bias): conditioning opens a noncausal path"
    return {"valid_backdoor_set": is_backdoor_adjustment_set(G, x, y, S),
            "backdoor_paths_open": not nx.is_d_separator(H, {x}, {y}, S & (set(G) - desc_x)),
            "bad_controls": bad}


if __name__ == "__main__":
    # Book Figure 8: HML -> OI -> PC, MOM -> HML, MOM -> PC, OI -> BAS <- PC, BAS -> LIQ, BAS -> VOL
    G = nx.DiGraph([("MOM", "HML"), ("HML", "OI"), ("OI", "PC"), ("MOM", "PC"),
                    ("OI", "BAS"), ("PC", "BAS"), ("BAS", "LIQ"), ("BAS", "VOL")])
    print("Fig.8 minimal backdoor sets HML->PC:", minimal_backdoor_sets(G, "HML", "PC"))
    print("Fig.8 {} valid?   ", is_backdoor_adjustment_set(G, "HML", "PC", set()))
    print("Fig.8 {MOM} valid?", is_backdoor_adjustment_set(G, "HML", "PC", {"MOM"}))
    print("Fig.8 {MOM,BAS}   ", audit_controls(G, "HML", "PC", {"MOM", "BAS"}))
    print("Fig.8 {MOM,OI}    ", audit_controls(G, "HML", "PC", {"MOM", "OI"}))
    print("Fig.8 MOM latent -> front-door {OI}:", is_front_door_set(G, "HML", "PC", {"OI"}))
    print("Fig.8 roles:", node_roles(G, "HML", "PC"))

    # Book Figure 23 (as drawn): Market->Ret, Ret->HML, SML->HML, MOM->HML, MOM->Ret ; HML is the collider
    G2 = nx.DiGraph([("Market", "Ret"), ("Ret", "HML"), ("SML", "HML"), ("MOM", "HML"), ("MOM", "Ret")])
    print("Fig.23 effect SML->Ret, naive (control HML):", audit_controls(G2, "SML", "Ret", {"HML"}))
    print("Fig.23 effect SML->Ret, no control valid?  :", is_backdoor_adjustment_set(G2, "SML", "Ret", set()))

    # M-bias: X <- A -> M <- B -> Y, no X->Y effect. Controlling for M (pre-treatment collider) creates bias.
    G4 = nx.DiGraph([("A", "X"), ("A", "M"), ("B", "M"), ("B", "Y")])
    print("M-bias control M:", audit_controls(G4, "X", "Y", {"M"}))
    print("M-bias no control valid?:", is_backdoor_adjustment_set(G4, "X", "Y", set()))

    # Fig. 4 instrument: W->X, Z->X, Z->Y, X->Y (Z latent)
    G3 = nx.DiGraph([("W", "X"), ("Z", "X"), ("Z", "Y"), ("X", "Y")])
    print("Fig.4 W instrument?", is_instrument(G3, "W", "X", "Y"))
```

Expected output of `python causal_dag_tools.py`:

```text
Fig.8 minimal backdoor sets HML->PC: [('MOM',)]
Fig.8 {} valid?    False
Fig.8 {MOM} valid? True
Fig.8 {MOM,BAS}    {'valid_backdoor_set': False, 'backdoor_paths_open': False, 'bad_controls': {'BAS': 'post-treatment descendant of X: violates backdoor condition (ii), collider/selection bias risk'}}
Fig.8 {MOM,OI}     {'valid_backdoor_set': False, 'backdoor_paths_open': False, 'bad_controls': {'OI': 'mediator: removes the mediated part of the total effect; if mediator and outcome share a cause, it opens a noncausal path (mediation fallacy)'}}
Fig.8 MOM latent -> front-door {OI}: True
Fig.8 roles: {'MOM': ['confounder (or ancestor of both)'], 'OI': ['mediator (on a causal path X->..->Y)', 'descendant of X'], 'BAS': ['collider/descendant of both X and Y'], 'LIQ': ['collider/descendant of both X and Y'], 'VOL': ['collider/descendant of both X and Y']}
Fig.23 effect SML->Ret, naive (control HML): {'valid_backdoor_set': False, 'backdoor_paths_open': False, 'bad_controls': {'HML': 'post-treatment descendant of X: violates backdoor condition (ii), collider/selection bias risk'}}
Fig.23 effect SML->Ret, no control valid?  : True
M-bias control M: {'valid_backdoor_set': False, 'backdoor_paths_open': True, 'bad_controls': {'M': 'pre-treatment collider (M-bias): conditioning opens a noncausal path'}}
M-bias no control valid?: True
Fig.4 W instrument? True
```

## 9.2 `multiple_testing_tools.py`

```python
"""
multiple_testing_tools.py
Type-A spuriosity tools: Minimum Track Record Length and Deflated Sharpe Ratio
(Bailey and Lopez de Prado 2012, 2014). Per-period Sharpe ratios throughout.
"""
import numpy as np
from scipy.stats import norm

EULER_GAMMA = 0.5772156649015329


def min_track_record_length(sr, alpha=0.05, skew=0.0, kurt=3.0, sr_benchmark=0.0):
    """Observations needed (same frequency as `sr`) to reject H0: SR <= sr_benchmark at level alpha."""
    z = norm.ppf(1 - alpha)
    return 1 + (1 - skew * sr + (kurt - 1) / 4 * sr ** 2) * (z / (sr - sr_benchmark)) ** 2


def expected_max_sharpe(n_trials, var_sr):
    """E[max SR] across n_trials independent zero-skill trials with cross-trial SR variance var_sr."""
    return np.sqrt(var_sr) * ((1 - EULER_GAMMA) * norm.ppf(1 - 1 / n_trials)
                              + EULER_GAMMA * norm.ppf(1 - 1 / (n_trials * np.e)))


def deflated_sharpe_ratio(sr, n_obs, n_trials, var_sr_trials, skew=0.0, kurt=3.0):
    """P(true SR > 0 | observed best SR after n_trials). Output in [0,1]; require > 0.95 typically."""
    sr0 = expected_max_sharpe(n_trials, var_sr_trials)
    denom = np.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr ** 2)
    return norm.cdf((sr - sr0) * np.sqrt(n_obs - 1) / denom)


if __name__ == "__main__":
    sr_ann = 0.29
    sr_d = sr_ann / np.sqrt(252)
    n = min_track_record_length(sr_d, alpha=0.05)
    print(f"MinTRL daily obs={n:,.0f}  years={n/252:.1f}  (Gaussian iid, one-sided 5%)")
    print(f"t-stat for SR 0.29 over 15.58y: {sr_ann*np.sqrt(15.58):.2f}")
    # 1000 trials, trial-SR std 0.5 annual, best SR 2.0 annual over 5 years of daily data
    sr0 = expected_max_sharpe(1000, (0.5/np.sqrt(252))**2)
    print(f"E[max SR] over 1000 null trials (annualised): {sr0*np.sqrt(252):.2f}")
    print("DSR:", round(deflated_sharpe_ratio(2.0/np.sqrt(252), 5*252, 1000, (0.5/np.sqrt(252))**2), 3))
```

Expected output:

```text
MinTRL daily obs=8,109  years=32.2  (Gaussian iid, one-sided 5%)
t-stat for SR 0.29 over 15.58y: 1.14
E[max SR] over 1000 null trials (annualised): 1.63
DSR: 0.797
```

## 9.3 `monte_carlo_experiments.py`

```python
"""
monte_carlo_experiments.py
Replicates Lopez de Prado (2023) Section 7 experiments (fork, collider, confounded mediator)
and adds a demonstration of the time-varying "risk premium" that arises from an omitted confounder.
Requires numpy, statsmodels.
"""
import numpy as np
import statsmodels.api as sm

N = 5000


def ols(y, *cols):
    X = sm.add_constant(np.column_stack(cols))
    return sm.OLS(y, X).fit()


def fork(seed=0):
    """Z -> X, Z -> Y. No X -> Y. Omitting Z gives a spurious beta (type-B)."""
    rng = np.random.RandomState(seed)  # legacy stream: reproduces the book (np.random.seed(0))
    z = rng.normal(size=N); x = z + rng.normal(size=N); y = z + rng.normal(size=N)
    return {"omit_Z (wrong)": ols(y, x), "control_Z (right)": ols(y, x, z)}


def collider(seed=0):
    """X -> Z <- Y. No X -> Y. Controlling for Z gives a spurious beta (Berkson)."""
    rng = np.random.RandomState(seed)  # legacy stream: reproduces the book (np.random.seed(0))
    x = rng.normal(size=N); y = rng.normal(size=N); z = x + y + rng.normal(size=N)
    return {"no_control (right)": ols(y, x), "control_Z (wrong)": ols(y, x, z)}


def confounded_mediator(seed=0):
    """X -> Z -> Y with W -> Z and W -> Y. True total effect of X on Y is 1.
    Controlling for Z opens X -> Z <- W -> Y and flips the sign (mediation fallacy)."""
    rng = np.random.RandomState(seed)  # legacy stream: reproduces the book (np.random.seed(0))
    x = rng.normal(size=N); w = rng.normal(size=N)
    z = x + w + rng.normal(size=N); y = z + w + rng.normal(size=N)
    return {"no_control (right)": ols(y, x), "control_Z (wrong)": ols(y, x, z)}


def time_varying_premium(T=2000, beta=0.2, gamma=1.0, window=250, seed=0):
    """Constant causal effects (beta, gamma). Only the X<-Z loading delta changes at T/2.
    A researcher who omits Z sees the 'premium' of X move from positive to negative."""
    rng = np.random.RandomState(seed)  # legacy stream: reproduces the book (np.random.seed(0))
    delta = np.where(np.arange(T) < T // 2, 1.0, -3.0)
    z = rng.normal(size=T); x = delta * z + rng.normal(size=T); y = beta * x + gamma * z + rng.normal(size=T)
    roll = [np.polyfit(x[t - window:t], y[t - window:t], 1)[0] for t in range(window, T)]
    theory = lambda d: beta + gamma * d / (1 + d ** 2)
    return np.array(roll), theory(1.0), theory(-3.0)


def summarize(res_dict, names):
    for tag, r in res_dict.items():
        coefs = "  ".join(f"{n}={b: .3f}(t={t: .1f})" for n, b, t in zip(names, r.params[1:], r.tvalues[1:]))
        print(f"   {tag:20s} {coefs}  adjR2={r.rsquared_adj:.3f} F={r.fvalue:,.0f}")


if __name__ == "__main__":
    print("FORK (true effect X->Y = 0)");              summarize(fork(), ["X", "Z"])
    print("COLLIDER (true effect X->Y = 0)");          summarize(collider(), ["X", "Z"])
    print("CONFOUNDED MEDIATOR (true effect = 1)");    summarize(confounded_mediator(), ["X", "Z"])
    roll, th_a, th_b = time_varying_premium()
    print(f"TIME-VARYING PREMIUM: true beta=0.2 constant. Rolling beta_hat mean regime A={roll[:700].mean():.2f} "
          f"(theory {th_a:.2f}), regime B={roll[-700:].mean():.2f} (theory {th_b:.2f})")
```

Expected output (exactly reproduces the book's adjusted R² 0.784 versus 0.144 and F 9,069 versus 840.8):

```text
FORK (true effect X->Y = 0)
   omit_Z (wrong)       X= 0.496(t= 40.5)  adjR2=0.247 F=1,640
   control_Z (right)    X= 0.001(t= 0.1)  Z= 0.996(t= 49.5)  adjR2=0.495 F=2,447
COLLIDER (true effect X->Y = 0)
   no_control (right)   X= 0.002(t= 0.1)  adjR2=-0.000 F=0
   control_Z (wrong)    X=-0.496(t=-40.4)  Z= 0.499(t= 70.6)  adjR2=0.499 F=2,490
CONFOUNDED MEDIATOR (true effect = 1)
   no_control (right)   X= 1.006(t= 29.0)  adjR2=0.144 F=841
   control_Z (wrong)    X=-0.481(t=-22.6)  Z= 1.490(t= 121.7)  adjR2=0.784 F=9,069
TIME-VARYING PREMIUM: true beta=0.2 constant. Rolling beta_hat mean regime A=0.76 (theory 0.70), regime B=-0.11 (theory -0.10)
```

---

# Part 10. Glossary

| Term | Definition |
|---|---|
| Association | Statistical dependence: P[X,Y] ≠ P[X]P[Y] |
| Causation | P[Y \| do[X=x]] > P[Y]; requires an intervention or a model of one |
| do-operator | Setting a variable by intervention, cutting arrows into it |
| DAG / causal graph | Directed acyclic graph of variables and causal arrows |
| Confounder | Common cause of X and Y (fork) |
| Mediator | Variable on a causal path from X to Y (chain) |
| Collider | Common effect of two variables (immorality); conditioning opens a path |
| Backdoor path | Noncausal path with an arrow into X |
| d-separation | All paths between X and Y blocked given S; equals conditional independence |
| Backdoor / front-door / IV | Graph-based identification strategies |
| ATE / ATT / SSB | Average treatment effect / on the treated / self-selection bias |
| Natural experiment | Observational study where Nature's assignment is as-if random (RDD, DID, COS) |
| Simulated intervention | Observational estimate of a do-effect given an assumed causal graph |
| Causal content | Causal assumptions embedded in a model, declared or not |
| Type-A spuriosity | Noise mistaken for signal |
| Type-B spuriosity | Association mistaken for causation (misspecification) |
| Under-controlling | Omitting a confounder |
| Over-controlling | Conditioning on a collider or mediator |
| Specification searching | Choosing a model by explanatory power |
| Mediation fallacy | Conditioning on a mediator that is confounded with the outcome |
| Berkson's fallacy | Spurious association from conditioning on a common effect |
| Simpson's paradox | Association reverses when groups are pooled or split |
| Falsifiability | Theory exposes implications that experiments could refute |
| Phenomenological stage | Cataloguing associations without causal theory |
| False Strategy Theorem | Selection among many trials makes the best backtest look skilled by chance |
| MinTRL | Minimum track record length for significance at a given Sharpe |
| Deflated Sharpe ratio | Sharpe adjusted for number of trials, sample length and non-normality |
| PIN / VPIN | Probability of informed trading and its volume-synchronised version |
| FCM | Functional causal model: Y = f(X, ε) with ε independent of X |
| Markov equivalence class | Set of DAGs with the same conditional independences |

---

# Part 11. Verification log

| Item | Method | Outcome |
|---|---|---|
| Book text | Full text of all 92 pages read; figures 8 and 23 inspected as images | Edge lists in Part 4.3 and 4.7 follow the drawn figures |
| Fork, collider, confounded mediator | Re-ran the book's Appendix B code with `np.random.seed(0)` | Matches: adj. R² 0.784 vs 0.144 and F 9,069 vs 840.8 in the chain case; false positives of about ±0.50, t about ±40 in fork/collider |
| Cov[X, Y \| Z] = −1/3 | Residualised X and Y on Z, n = 5,000 | −0.323 (theory −0.333) |
| Bias formula θ = γδ/(1+δ²) | n = 400,000, four parameter sets | e.g. β = 0, γ = 1, δ = 1: 0.499 vs 0.500; β = 0.2, γ = 1, δ = −3: −0.1005 vs −0.100 |
| Time-varying premium demo | Constant β = 0.2; δ switches from +1 to −3 | Rolling β̂ about 0.76 then −0.11 (theory 0.70 and −0.10) |
| MinTRL | Bailey-López de Prado formula, Gaussian, one-sided 5% | 8,109 daily obs, about 32.2 years vs book "over 31 years"; t-stat 1.14 vs book 1.16 |
| DAG toolkit | Figure 8, Figure 23, M-bias and Figure 4 graphs | Outputs in Part 9.1 behave as the theory predicts |
| Not verified | Bloomberg-GSAM index statistics, industry AUM figures, all `[CTX]` citations | Taken from the book or from memory. Re-source before external use |

Minor points noted in the text: (i) the printed path "HML ← OI → BAS ← PC" in §6.2.1 conflicts with Figure 8's arrow directions (HML → OI); (ii) in §4.3.2.2 the description of Figure 2 labels the causal path "Y → X" where X → Y is meant. Neither affects the argument.

---

# Part 12. References

## 12.1 Cited in the book and used above `[B]`

- Abadie (2021) synthetic controls, *JEL* 59(2).
- Angrist and Pischke (2008) *Mostly Harmless Econometrics*; (2010) the credibility revolution, NBER WP 15794.
- Ashenfelter and Card (1986) DID origin.
- Bailey and López de Prado (2012) Sharpe ratio efficient frontier; (2014) deflated Sharpe ratio, *JPM* 40(5); (2021) backtest overfitting, *Significance*.
- Bailey, Borwein, López de Prado, Zhu (2014) Pseudo-mathematics and financial charlatanism, *Notices AMS* 61(5).
- Baba, Shibata, Sibuya (2004) partial and conditional correlation.
- Barroso and Santa-Clara (2015) Momentum has its moments, *JFE*.
- Benjamini and Hochberg (1995) false discovery rate, *JRSS B*.
- Berkson (1946) Berkson's fallacy.
- Carhart (1997) four-factor model, *JF*.
- Chen and Pearl (2013) regression and causation in six econometrics textbooks.
- Chickering (2003) GES, *JMLR*.
- Cochrane (2005) *Asset Pricing*; (2011) Discount rates (factor zoo), *JF*.
- Easley, Kiefer, O'Hara, Paperman (1996) PIN; Easley, López de Prado, O'Hara (2010, 2012, 2016) VPIN and flow toxicity.
- Fabozzi and López de Prado (2018) Being honest in backtest reporting, *JPM*.
- Fama and French (1993, 1996, 2015); Fama and MacBeth (1973).
- Glymour, Zhang, Spirtes (2019) causal discovery review, *Frontiers in Genetics*.
- Granger (1969, 1980); Granger and Newbold (1974); Granger, Hyung, Jeon (2001).
- Haavelmo (1944) probability approach in econometrics.
- Harvey (2017) Scientific outlook in financial economics, *JF*; Harvey (2022) pitfalls of asset management research; Harvey, Liu, Zhu (2016) "... and the cross-section of expected returns", *RFS*.
- Hernán and Robins (2020) *Causal Inference: What If*.
- Hoyer et al (2009) additive noise models; Shimizu et al (2006) LiNGAM; Zhang and Hyvärinen (2009).
- Imbens and Lemieux (2008) RDD; Imbens and Wooldridge (2009).
- Laudy et al (2022) causal graphs from news (NLP).
- López de Prado (2018) *Advances in Financial Machine Learning*; (2020) *Machine Learning for Asset Managers*; (2022a, 2022b).
- Pearl (1995, 2009) *Causality*; Pearl, Glymour, Jewell (2016) *Causal Inference in Statistics: A Primer*; Pearl and MacKenzie (2018) *The Book of Why*.
- Peters, Janzing, Schölkopf (2017) *Elements of Causal Inference*.
- Rebonato (2010); Rebonato and Denev (2014); Denev (2015); Rodríguez-Domínguez (2023): counterfactual stress testing and graphical models.
- Romano and Wolf (2005); White (2000); Hochberg (1988) multiple testing.
- Shpitser and Pearl (2006) completeness of do-calculus.
- Spirtes, Glymour, Scheines (2000/2001) causation, prediction and search (PC, FCI).

## 12.2 Context literature `[CTX]` (from memory; verify details before citing)

- Rubin (1974), Rosenbaum and Rubin (1983): potential outcomes and propensity scores. Imbens and Rubin (2015) *Causal Inference for Statistics, Social, and Biomedical Sciences*.
- Cinelli, Forney, Pearl (2022) "A crash course in good and bad controls", *Sociological Methods and Research*.
- Cinelli and Hazlett (2020) sensitivity analysis for omitted variable bias, *JRSS B*.
- Westreich and Greenland (2013) "The Table 2 fallacy", *Am. J. Epidemiology*.
- Chernozhukov et al (2018) double/debiased machine learning, *Econometrics Journal*.
- Hünermund, Louw, Caspi (2023) double machine learning and automated confounder selection, *Journal of Causal Inference*.
- Hünermund and Bareinboim (2019/2023) causal inference and data fusion in econometrics.
- Peters, Bühlmann, Meinshausen (2016) invariant causal prediction, *JRSS B*; Arjovsky et al (2019) invariant risk minimisation.
- Bailey, Borwein, López de Prado, Zhu (2017) The probability of backtest overfitting, *J. Computational Finance*.
- Hou, Xue, Zhang (2015) Digesting anomalies; (2020) Replicating anomalies, *RFS*.
- Jensen, Kelly, Pedersen (2023) Is there a replication crisis in finance?, *JF*.
- Chen and Zimmermann (2022) Open source cross-sectional asset pricing, *Critical Finance Review*.
- McLean and Pontiff (2016) Does academic research destroy stock return predictability?, *JF*.
- Feng, Giglio, Xiu (2020) Taming the factor zoo, *JF*; Kozak, Nagel, Santosh (2020) Shrinking the cross-section, *JFE*.
- Daniel and Titman (1997) Evidence on the characteristics of cross-sectional variation in stock returns, *JF*.
- Gu, Kelly, Xiu (2020) Empirical asset pricing via machine learning, *RFS*.
- López de Prado and Zoonekynd (2024) work on specification errors and factor-investing failure (SSRN); and López de Prado (2023) "Beyond Econometrics: A Roadmap Towards Causal Financial Machine Learning" (SSRN). Check the exact titles and identifiers before citing.
