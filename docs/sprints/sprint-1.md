# Sprint 1: first delivery (R1)

Dates: 2026-11-19 (one day)
Status: Closed. Released as `v0.2.0`, with hotfix `v0.2.1`.
Spec: [next-stage spec](../specs/next-stage-track-record-and-portfolio.md). Next: [Sprint 2 backlog](sprint-2-backlog.md).

## Goal

On localhost, a user can pick a ticker or upload a monthly track record, switch between FF5 and FF6, and read alpha across CAPM, FF3, FF5 and FF6, with honest captions.

## What shipped

| Epic | What | PR |
|---|---|---|
| E0 | Walking skeleton: return-subject seam, monthly path, CSV upload (in memory, 1 MB cap, 422 refusals), Ticker / Track record mode switch | #22 |
| E5 core | Portfolio backtest engine with drift, month-end rebalance, cost on traded securities, Frongello contributions, risk share. No UI yet. | #20 |
| E7a | VaR and CVaR with historical, Gaussian and Cornish-Fisher methods, bootstrap bands and labels | #21, #23 |
| E1 + E9a | FF6 (momentum), alpha strip across CAPM/FF3/FF5/FF6, model notes, associational wording | #24 |
| Demo fixes | Four wording defects found in the R1 demo | #25 |
| Polish | Wider sidebar (#27). Defaults 10Y and FF6, with the API default unchanged (#28). Coverage bar for the analysed range (#29). Alpha strip and World beta side by side (#30). CI on push to dev. | #27-#30 |
| Release | dev to prod | #26, `v0.2.0` |
| Hotfix 0.2.1 | FF5/FF6 selector removed from the sidebar; a `model=ff5` URL still works. Inner scrollbars removed. Always-zero Residual row dropped from Return sources. Price "rose X%" now compounds the same returns as the analysis. | #32, `v0.2.1` |

## Decisions made during the sprint

These are recorded in the spec, the research notes and the wiki.

- Monthly regressions use a small-sample correction: HAC × n/(n−k) and Student-t(n−k). Daily regressions are unchanged.
- The schema version stays "4". The `subject` block is optional and absent from ticker reports.
- A missing momentum value never cuts the FF5 sample. FF6 and the alpha strip drop those rows and say so.
- In the backtest, cash limits the window only when its weight is above 0. Cost is charged on traded securities only.
- Cornish-Fisher figures:
  - The validity guard runs over the range each figure uses.
  - The "indicative" flag applies to z in [−3.5, 3.5].
  - The band is withheld when fewer than 80% of resamples are valid.
- The monthly 95% VaR row needs 2 expected tail observations. All other rows need 3. Bands for historical CVaR and for Cornish-Fisher are labelled "approximate".
- The dashboard opens on 10Y and FF6. The API default stays FF5. FF5-only sections (Kalman, shrunk, fragility, residual, lead-lag) are hidden under FF6 until a Settings module exists.

## Validation

- Localhost demo with real data: SPY market beta 1.01, alpha near 0 under every model, and no errors.
- Every merged PR had green CI (Ubuntu, Windows, frontend, e2e) and an independent correctness review.
- The golden ticker report is unchanged apart from additive sections.
- The annualised return was checked by hand against ACWI adjusted closes for 3Y, 5Y, 10Y and full history.

## Retro

**Went well**

- The pure statistics cores were built in parallel lanes and merged with no code conflicts.
- Reviews caught six real bugs before merge.
- The demo gate caught wording defects before release.

**Problems and fixes**

| Problem | Fix |
|---|---|
| The owner saw the old UI twice, because `serve` uses the prebuilt `frontend/dist` | Run `make build` after pulling frontend changes. A stale-build warning is in the Sprint 2 backlog. |
| Background agents re-sent reports and left local servers running | Briefs now require foreground tests only and stopped servers. |
| One PR merged before its CI started | Merge only when all four checks exist and pass. |
| A float test passed on Windows and failed on Linux | Tests compare floats with a tolerance. |
| Frontend tests flaked under load | Set Vitest `maxWorkers` (Sprint 2). |
| Bundle 2% over budget, not enforced in CI | Enforce the budget or reset it (Sprint 2). |
| The remote `dev` branch was deleted after a release merge | Recreated from prod. Do not delete `dev` after a release PR. |
