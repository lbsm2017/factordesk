# Decision: shrunk betas as a second, labelled view

Date: 2026-11-18
Status: Decided-pending-implementation (built on branch `feat/shrunk-betas`; stays here until the independent validation of `docs/validation/shrunk-betas-handoff-2026-11-18.md` has passed)

## In one sentence

We will show, next to each ordinary beta, a second beta that is pulled toward what a typical stock does by an amount that depends on how noisy the ordinary beta is, and keep the ordinary betas as the numbers the rest of the report uses.

## What we decided

- Two views of the five betas, for the whole sample and for the latest rolling window: the ordinary (OLS) beta, and a "pulled toward typical" beta with a 95% credible interval and a pull figure (the share of the way from the OLS beta to the typical value).
- "Typical" is a stock that behaves like the market: market beta 1, the four style betas 0. How far a beta can be pulled comes from how much betas differ across public Ken French portfolios (49 industries and 75 size and characteristic portfolios, the last 2,520 trading days).
- The ordinary betas stay primary. Tags, attribution, risk, dominance and drift never use the shrunk betas. The shrunk view carries no test, no "reliable" tag and no p-value.
- Next to it, a plain-words power statement for each factor: the smallest beta the report's own test would detect with 80% power, and how much more data a beta of 0.05 would need.
- A marker is drawn only when a beta is pulled by 5% or more. When none is, the panel says one line: "Shrinkage moves no beta by a visible amount: this sample is long enough." The words "Moved away from typical" and its explanation show only on a row whose marker is drawn.
- Owner decision, 2026-11-18: download the four extra portfolio files (about 13.4 MB zipped) and keep them fresh together with the factor data: same staleness rule as the factor file, refreshed again when the factor release moves on, checked on a manual refresh. If the site cannot be reached the section says so and the rest of the report is unaffected.

## Why

Style betas of a stock with a short or noisy history are imprecise: a beta of -1.0 with a standard error of 0.3 is far less certain than it looks. Shrinking noisy betas toward a sensible reference is a standard way to reduce estimation error. In the specification's simulations (descriptive, 2026-11-18), when the stated spread is right, the pulled betas have about half the total squared error of the ordinary ones at one to two years of data, and the gain fades with more data. We rejected replacing the ordinary betas, because when the true spread is twice what the portfolios suggest the pulled betas do worse than the ordinary ones (11% to 35% per factor) and the intervals cover only 77% to 91% instead of 95%. Portfolios vary less than single stocks, so that case is plausible. We rejected shrinking alpha, because a prior on alpha is a claim about abnormal returns that this product does not make. We rejected a fixed g-prior, because it would move betas by about 0.2% at two years of data, which nobody would see.

## How it works

- The uncertainty of each ordinary beta is its HAC (Newey-West) covariance, not the plain one, so serial correlation counts as less information. Combining that with the prior (centre and spread) gives the pulled beta by a closed formula (spec section SB3).
- The spread per factor is the larger of two method-of-moments estimates, one per cross-section, never below 0.05. For SPY on 2026-11-18 it is 0.209, 0.764, 0.341, 0.329 and 0.254 for the market, size, value, profitability and investment betas. It is recomputed for each report from rows dated up to the report's end only, so it cannot look ahead (spec SB2.3).
- Real result for SPY (cached files, 2026-11-18): full-sample pulls between 0.007% and 0.2%, last 504 rows up to 0.9%, last 252 rows up to 0.2%. Shrinkage is invisible for SPY, so the panel shows the one-line message.
- Power: the smallest detectable beta is 3.417 times the HAC standard error (80% power, 1% level, the worst case of testing five betas). For SPY's last 504 rows the style betas of about 0.04 to 0.05 are detectable.
- Both panels (the downloadable report and the dashboard) use the same words, pinned by a test on each side.

## What it costs us

- Four more files to download once per data release, and a section that reads "unavailable" when the site cannot be reached.
- The pulled betas can be wrong for an unusual stock, because the spread comes from portfolios (spec SB2.4). The caveat sits in the panel's "How this is computed" text. The owner still has to decide whether to ship with that caveat, widen the spread, or show only the power statement until a peer-based prior exists (spec SB10.4, question 1).
- A second set of betas can be read as a correction of the first. The wording is "pulled toward typical", never "adjusted" or "true".
- A pulled beta can move away from its own typical value when it is estimated together with correlated factors that are pulled hard. The panel explains this only when the effect is large enough to see.
- The model's footnote still says "the bars show the estimates", but the static report has a table. A corrected sentence is proposed in the hand-off document; the owner has not approved it.

## What would change our mind

Evidence that the portfolio spread is far too tight for the stocks people look up (for example once the peer feature lets us test it): then we widen the spread or switch to the peer prior. Evidence that readers take the second beta as the answer: then we drop it from the headline areas or hide it behind a toggle. A validation finding in the hand-off checks.

## Sources

- [docs/specs/shrunk-betas.md](../docs/specs/shrunk-betas.md): SB1 and SB3 (model), SB2 (prior), SB5 (power), SB6 (display rules and labels), SB8 (demonstrations), SB9 (decisions SD1 to SD8), SB10.4 (open questions and the owner decision of 2026-11-18).
- [docs/specs/schema-v3-contract.md](../docs/specs/schema-v3-contract.md): where the section plugs into the report.
- [docs/validation/shrunk-betas-handoff-2026-11-18.md](../docs/validation/shrunk-betas-handoff-2026-11-18.md): what was built, the live numbers and what the validator recomputes.
- Ken French Data Library, daily portfolio files, vintage 202609 (see the [dataset cards](../docs/datasets.md)).
- Müller (2013), Econometrica 81(5), on posteriors built from the sandwich covariance (abstract checked 2026-11-18).

## Related decisions

- [Daily returns with robust errors](decision-daily-returns-and-robust-errors.md)
- [Which betas count as reliable](decision-which-betas-count-as-reliable.md)
- [No look-ahead rule](decision-no-look-ahead-rule.md)
- [One contract for the five new report sections](decision-schema-v3-contract.md)
- [Factor data source: the Ken French Data Library](decision-factor-data-source-french-library.md)
- [Independent validation and mutation testing](decision-independent-validation-and-mutation-testing.md)
