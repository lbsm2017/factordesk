# Decision: an Energy & carbon section on oil, gas and carbon prices

Date: 2026-11-20
Status: Decided (Sprint 3, item S3-8)

## In one sentence

Every report gets an Energy & carbon section that shows how the return moved with oil, gas and carbon prices, after taking the market out.

## What we decided

- The section shows "sensitivities": how much the return moved, on average, for each unit of move in a price.
- Three price legs, plus the market as a control:
  - **Oil:** the daily log change of the Brent spot price (FRED `DCOILBRENTEU`).
  - **Gas:** the daily log change of the Henry Hub spot price (FRED `DHHNGSP`).
  - **Carbon:** the KRBN fund return minus the risk-free rate (Yahoo). KRBN holds mainly EU carbon allowances.
  - **Market:** the French Mkt-RF, as in the headline model.
- Two models, each a separate regression with Newey-West errors:
  - **Long model:** market, oil and gas, over the whole analysed window.
  - **Carbon model:** market, oil, gas and carbon, from KRBN's first date. It is labelled "short sample, since <month year>, mainly EU carbon", where the month is the first month of its regression (Aug 2020 on real data). It is hidden when the window holds less than 2 years of carbon data (504 trading days, or 24 months).
- No lag terms.
- Broad commodities (COMM) are not in this section.
- Gas is shown twice: with all rows, and "without the 5 largest" gas moves (5 days for daily data, 5 months for monthly data), each with its t-statistic. Nothing is winsorised. Daily gas sensitivities are labelled descriptive.
- Each leg shows its VIF (how much it overlaps with the others). The section names the series that limits the window, only when that series starts on or after the subject's own start (the same rule as the macro section).
- The section works for every subject (ticker, uploaded track record, portfolio), daily and monthly, under FF5 and FF6.
- Plain-English sentence on screen, for example: "A 10% rise in oil went with a +2.0% move in this fund, after the market." A 10% rise in oil or gas is the log change ln(1.10), because those legs are log changes. A 10% rise in carbon is 0.10.
- If FRED is down, the section shows a notice and nothing else. The report is never blocked. If only KRBN is missing, the long model stays and the carbon model is hidden with a note.
- The report schema stays at version "4": the new `energy` block is optional and absent when it is not computed. The golden ticker report is unchanged.

## Why

- A portfolio's oil, gas and carbon exposure is a common due-diligence question, and the owner asked for it in Sprint 3.
- The market is in the regression so that an equity fund does not look "long oil" only because oil moves with stocks.
- The spike (below) shows the legs barely overlap, so a single regression is safe.

## The data

- Brent and Henry Hub come from FRED, cached per day, with the soft-fail rule of the dollar index. A missing FRED day removes that day and the next one. Nothing is filled.
- KRBN comes through the same price provider and cache as the other funds.
- Monthly subjects compound each leg to month-end first, then take the log.

## What the spike found (2026-11-20, [full note](../docs/research/energy-factor-spike.md))

- Lag terms: 2 of 20 pass |t| > 2, both on gas. That is about what chance gives. So there are no lag terms.
- VIF: at most 1.14 for the long model and 1.17 for the carbon model. Adding COMM would raise oil to 1.6 to 3.1, so COMM stays out.
- The 5 largest gas days hold 31% (2007 on) and 41% (2020-08 on) of the sum of squared gas returns. Without them the only borderline daily gas sensitivities fall to t = 1.3 to 1.5. Monthly data goes the other way for XLE (t from 1.6 to 2.4), so the rule is the same for both frequencies.
- Gas carries almost no signal for SPY, XLE, XLU or a 60/40 portfolio. Carbon matters only for XLE. Oil clearly matters for XLE (positive) and 60/40 (negative).

## What it costs us

- The carbon model is a short sample, in one market regime, and KRBN is mainly EU carbon. Its sensitivities are unstable and the label says so.
- Daily Henry Hub is thin and spiky. Its t-statistics are unreliable at excess kurtosis 115. Treat daily gas sensitivities as descriptive.
- Ken French data ends before the price data, so the window stops at the last factor date.
- Sensitivities are raw and in-sample. They are not a forecast.
- The "without the 5 largest" fit removes rows but does not re-space the Newey-West lag chain. The effect is small next to the shifts it is meant to show.
- European gas (TTF) is not here. It comes with the EUR work.

## What would change our mind

- If a later spike finds lag effects, we would add them for the leg concerned.
- If a cleaner carbon series becomes available, it replaces KRBN and the short-sample label.
- If readers take the gas rows as a signal, we would hide the daily gas row by default.

## Where it lives

- Analytics: `backend/factordesk/analytics/energy.py`. Section model: `backend/factordesk/report/sections/energy.py`. Hook and loader: `backend/factordesk/section_hooks/energy.py`.
- Panel: `frontend/src/components/report/sections/EnergyPanel.tsx`, after Macro sensitivities.
- Related: [factor models and macro](decision-factor-models-and-macro.md), [Sprint 3 plan](../docs/sprints/sprint-3.md).
