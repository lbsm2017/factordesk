# Decision: causal-discipline guardrails for factor results

Date: 2026-11-19
Status: Decided, not yet built

## In one sentence

Following López de Prado (2023), reports say clearly that every alpha and beta depends on the model chosen. They show how alpha changes across reasonable choices, and track records state how many months a Sharpe ratio would need before it can be trusted.

## What we decided

- **Wording and model notes**, built in release R1 together with the alpha strip:
  - A caption under the alpha strip: a higher R-squared does not make a model more correct, and alpha depends on the model.
  - Plain associational verbs throughout: "co-moved with", never "driven by" or "earned from".
  - A fixed note for each model (FF5, FF6, macro) saying what it assumes and what it leaves out.
  - The out-of-sample caveat says it rules out hindsight in the betas, not luck and not a missing factor.
  - "Reliable" tags are explained as protection against noise only.
- **Specification curve**, release R3: alpha across model, window and start date, with the share of choices where alpha keeps its sign and its tag. No choice is marked as best.
- **Minimum Track Record Length**, release R3, in the track-record diagnostics: "this Sharpe ratio needs N months to differ from zero; you have M".
- **Not now:**
  - a warning when a holding is a building block of a factor
  - running drift alerts under both FF5 and FF6
  - an analysis-choices card
  - a per-report placebo test
  - an omitted-factor "what it would take" check

## Why

- The book's central point is that factor models are causal models in disguise. A model picked for its fit, or one with a missing factor, gives biased betas and alpha, and these can even flip sign.
- Multiple-testing corrections such as Benjamini-Hochberg protect against noise, but not against a missing or wrongly included factor. More data makes those errors look more significant, not less.
- factordesk describes exposures and makes no claim that a factor earns a premium. So the book's discovery tools (causal graphs, do-calculus, natural experiments) do not apply. Its warning about attribution does.
- A specification curve shows openly how much the answer depends on choices, which is the honest alternative to picking one model.

## How it works

- The specification curve reuses the alpha-strip regressions over a grid of windows and start dates.
- Minimum Track Record Length uses the formula verified against the original paper (research notes, V1).

## What it costs us

- More caveat text in the report, in line with the low-density design.
- The specification curve adds computation: several regressions per report.

## What would change our mind

- If users read the specification curve as a menu to pick the best alpha from, we would show only the summary share.
- The declined guardrails can return if a real case shows the hazard, for example a portfolio holding IEF while being regressed on TERM.

## Sources

- [Research notes, section F](../docs/research/next-stage-research.md)
- [Causal Factor Investing study guide](../docs/research/causal_factor_investing_agent_kb.md), the owner's summary of the book
- [Next-stage spec, E9](../docs/specs/next-stage-track-record-and-portfolio.md)
