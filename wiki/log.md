# Change log

Newest first. This log records changes to the knowledge base (the `wiki/` folder), not to the code.

## Open questions

- May sample reports built from Yahoo data be committed to the public repository? Not yet decided (2026-11-18).
- The README has a stale status line and no not-affiliated note. The owner plans to rewrite the README later (2026-11-18).

## 2026-11-18 (report review)

- Added [report density, width cap and range controls](decision-report-density-and-range-controls.md) after the owner's review of the live SPY report. The design spec and prototype were revised to match.
- Linked it from the [colour decision](decision-report-design-colour-is-evidence.md) and the [application stack](decision-application-stack.md).

## 2026-11-18 (follow-up)

- Filled the "Why" sections of [MIT license](decision-open-source-mit-license.md), [project name](decision-project-name-factordesk.md), [Python and uv](decision-python-and-uv-for-every-platform.md) and [branches and pull requests](decision-branches-and-pull-requests.md) with the owner's reasoning.
- Added [application stack](decision-application-stack.md) (20th decision) and the [prior art review](prior-art-review-2026-11-18.md).
- [No look-ahead rule](decision-no-look-ahead-rule.md): recorded that the owner accepted the causal shading filter, and that non-USD tickers get a warning until European mode ships.
- [Residual alpha analysis](decision-residual-alpha-analysis.md): stated that "holds up out-of-sample" means point-in-time betas, not a true holdout.

## 2026-11-18

- Added decision pages for 19 decisions, each in the same template (one sentence, what we decided, why, how it works, what it costs us, what would change our mind, sources, related decisions).
  - Data: [factor data source](decision-factor-data-source-french-library.md), [prices from Yahoo](decision-prices-from-yahoo-with-adjusted-close-care.md), [European mode and currency](decision-european-mode-and-currency.md) (Proposed).
  - Statistics: [daily returns and robust errors](decision-daily-returns-and-robust-errors.md), [which betas count as reliable](decision-which-betas-count-as-reliable.md), [no look-ahead rule](decision-no-look-ahead-rule.md), [return and risk attribution](decision-return-and-risk-attribution.md), [SPY timing noise and the quality gate](decision-spy-timing-noise-and-the-quality-gate.md), [residual alpha analysis](decision-residual-alpha-analysis.md), [cointegration design](decision-cointegration-design.md), [drift alerts and regime betas](decision-drift-alerts-and-regime-betas.md).
  - Product and design: [report design](decision-report-design-colour-is-evidence.md).
  - Engineering and process: [thin slice on SPY first](decision-thin-slice-on-spy-first.md), [Python and uv](decision-python-and-uv-for-every-platform.md), [no data and no secrets](decision-no-data-and-no-secrets-in-the-repo.md), [branches and pull requests](decision-branches-and-pull-requests.md), [independent validation and mutation testing](decision-independent-validation-and-mutation-testing.md).
  - Open source: [MIT license](decision-open-source-mit-license.md), [project name](decision-project-name-factordesk.md).
- Added the [glossary](glossary.md) with 25 plain-English terms.
- Rewrote the [index](index.md) as a categorised list.
- Status of the decisions on this date: 4 are Decided-pending-implementation (SPY quality gate, residual analysis, cointegration, drift and regime), 1 is Proposed (European mode), and the rest are Decided. Pending items are marked on each page.
- Facts that came from `docs/` on this date may change while those documents are being edited. Each page links to its sources rather than restating fine detail.
- The earlier flat list [decisions log, 2026-11-18](decisions-2026-11-18.md) and the [README research](readme-research-2026-11-18.md) were kept as they were, with a pointer added to the first.

## 2026-11-18 (owner decisions)

- Resolved open question: only the synthetic mock report is committed. The README may show a screenshot of a real SPY report. Users generate real reports locally with `factordesk report SPY`. Real-data sample files are gitignored.
- Pull requests will live in a private GitHub repository named factordesk, made public later by the owner.

## 2026-11-18 (data-quality decisions)

- factordesk will compute total returns from raw Close plus Dividends for every source; vendor adjusted close becomes a cross-check. See `docs/data-quality-plan.md`, "Owner decisions".
- Tiingo stays a Later option for paid licences only; its free-plan terms forbid this use.
- No shipped list of known vendor errors; they are documented in the wiki instead.
- Data-quality and calibration tests use a frozen, stratified panel of 32 tickers.

## 2026-11-18 (spec decisions)

- Scholes-Williams estimator approved as a cross-check beside Dimson lead-lag betas.
- The quality-gate caveat will not blame late vendor closes; the reversal persists on official closes.
- Postponed: the fragility warning threshold, and whether a lead-lag beta may ever replace the headline beta (until then it never does).
