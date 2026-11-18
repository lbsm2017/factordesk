# Prior art review (2026-11-18)

What we learned on 2026-11-18 from reading open-source projects that do similar work. Source: the section "Lessons from GitHub analogs" in [docs/PLAN.md](../docs/PLAN.md), plus a deeper read of one end-user Fama-French application. Each lesson became a rule or a test in factordesk.

## Projects read

pyfolio-reloaded and empyrical-reloaded, quantstats, skfolio, equity-risk-model, KrishKPs/GS_QUANT (the closest analog: a FastAPI and React app), quant-lab-alpha, aistatcharts, factorlens, portfolio-tracker, open-climate-investing, pandas-datareader, and open issues in yfinance.

## Ideas we adopted

- **A small parser of our own for the French file** (about 30 lines), instead of pandas-datareader, which is fragile. We also diff old and new values on every refresh to catch revised history.
- **Tilt versus timing** (pyfolio): split return contribution into the average exposure and the effect of exposure changing over time.
- **An explicit "unattributed" row** (skfolio): alpha, residual and uncovered dates are shown, never folded in.
- **Exposure, volatility and correlation view** (skfolio) behind each risk bar.
- **A "disagreement" sentence** (GS_QUANT) when a factor ranks higher by risk than by beta.
- **Reliable versus noise tags** and text only for significant coefficients (portfolio-tracker), with an explanation of why a large alpha can be insignificant.
- **Two rolling windows overlaid** (quantstats, quant-lab-alpha), with opacity by window length.
- **A style-drift number** (factorlens): the size of the change in the beta vector.
- **Requested versus actual dates** on every result, because three analogs truncated silently.
- **Residual diagnostics** in a details drawer, and shareable state in the URL.

## Bugs we avoid, each now a test

- Rolling window off by one (pyfolio returned one extra observation).
- `fillna(0)` on returns or betas (quantstats: beta collapsed towards zero).
- Compounding components separately and expecting them to add up (pyfolio, aistatcharts).
- Regressing raw returns without subtracting the risk-free rate (quantstats, open-climate-investing).
- Factor risks that do not sum (equity-risk-model); we use the Euler method.
- Lasso or no-intercept loadings (skfolio default); we use plain OLS with an intercept.
- Dropping extreme rows (open-climate-investing removed real crash days); we flag, never drop.
- A factor cache that never expires (portfolio-tracker), and a currency mismatch between returns and factors.

## Deeper review of one end-user Fama-French app

Problems found: monthly data only; plain OLS errors with no robust correction; a monthly alpha that was not annualised; no download timeout or cache; dropped dates never reported; rolling windows stamped one period late (a look-ahead-style error); and a risk dashboard that ignored the selected region and currency. Two useful ideas: a robust parser that scans for the header line, and encoding several rolling windows in one overlay.

## Where this shows up in the wiki

- [Daily returns and robust errors](decision-daily-returns-and-robust-errors.md)
- [No look-ahead rule](decision-no-look-ahead-rule.md)
- [Return and risk attribution](decision-return-and-risk-attribution.md)
- [Factor data source](decision-factor-data-source-french-library.md)
- [Which betas count as reliable](decision-which-betas-count-as-reliable.md)
