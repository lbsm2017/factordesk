# Decision: Kalman-filter betas as an extra line beside the rolling betas

Date: 2026-11-18
Status: Decided-pending-implementation (built, tested and independently validated on branch `feat/kalman-betas`, with fixes of 2026-11-18 below; stays pending until the branch is merged)

## In one sentence

We show a second kind of time-varying beta, estimated by a Kalman filter that learns from the stock's own past how fast its exposures drift, as an additional line with an uncertainty band, and we do not let it replace the rolling betas anywhere.

## What we decided

- The five betas follow a random walk and alpha is held constant. One number, the drift rate (lambda), says how much weight a new day gets (superseded 2026-11-18: the weight is about the square root of the rate, see the update below). It is estimated from the data up to each date, on a grid, and re-estimated once a year (every 252 trading days after the first 504). Spec KB1, KB2.
- The first value is shown at the 504th day. Before that the series is empty on purpose. Spec KB2.3, KB3.
- Only filtered values are shown or exported: each point uses data up to its own date. A smoothed (hindsight) view is not built. Spec KB4.
- A model-based 95% band is shown, labelled as not comparable to the rolling bands. Spec KB5.
- The line is additional. The 126 and 252 day rolling betas stay on the chart, and nothing downstream (tilt and timing, dominance, drift alerts) uses the Kalman betas. Spec KB7.3, KD8.
- The two panels (the static report and the dashboard) use one set of words, kept in one JSON file with a test on each side, so they cannot drift apart.

## Why

A rolling window has a hard edge: an old day drops out suddenly and the line steps. The filter has no edge, is smoother when betas are stable, and gives a band. On SPY and MSTR the filter's one-day-ahead prediction was significantly better than the 126-day window's and slightly better, though not significantly after correction, than the 252-day window's (spec KB7.2, as recorded on 2026-11-18). We rejected the alternatives in the spec: a mean-reverting AR(1) (its better in-sample fit comes from the volatility of daily returns, not from betas reverting; spec KB1.2) and five separate drift rates (not supported on a training sample; spec KB1.3). We rejected a smoother in the main view because it moves a change to before the event that caused it (MSTR, spec KB4.2).

## How it works

- Each day: predict that the betas stay where they were, with a little extra uncertainty; then correct them toward what the day's return says. The size of the correction is set by the drift rate.
- The drift rate is turned into a plain comparison: "behaves like a window of N days" (N is 2 divided by the square root of the rate). On SPY the cached run of 2026-11-18 gives 250 to 501 days up to January 2009 and 128 to 147 days after, because 2008 entered the sample.
- Every re-estimate re-runs the filter from the first day, so the line can jump on the day a new estimate takes over. The chart marks those dates with dashed lines.
- Look-ahead is checked by changing every row after a chosen date and requiring every earlier value to stay the same (to 1e-12; about 1e-15 observed). The same check runs on the real SPY series and on synthetic data. Spec TKB13 to TKB17.

## What it costs us

- It reacts slowly to sudden changes: in the spec's step simulation it needed a median 251 days to reach the midpoint of a jump, against 117 days for the 252-day rolling window. The 126-day line stays on the chart as the reference for breaks. Spec KB7.3, TKB21.
- The band is model-based, not a HAC interval. It is too narrow after a sudden change and for SPY's old closing-price timing noise. Spec KB5, KB6.3.
- It adds time and size. On the cached real SPY history (8474 days) the hook added about 1.5 to 2.3 seconds to building a report (1.35 s without it, 3.6 s with it, median of six runs, on a machine that was busy with other work), and the section is about 1.85 MB, 44 percent of the whole report JSON. About a fifth of the section (`ex_ante_betas`) repeats the beta series shifted by one day. Removing it is an owner decision (handoff document, section 7). All as measured on 2026-11-18. (Superseded 2026-11-18: the field was dropped, see the update below.)
- The line can jump once a year at the re-estimate dates.
- Not built: the smoother (TKB06), the Student-t variant in the report (the code exists), the diagonal drift matrix, the point-in-time AR(1) comparison.

## Update 2026-11-18 (after the independent validation)

The validation (`docs/reviews/kalman-betas-validation-2026-11-18.md`) confirmed the statistics and led to four changes, all on branch `feat/kalman-betas`:

- Correction: the drift rate (lambda) is how fast the model lets the betas wander compared with the daily noise in returns. It is not the weight of a new day. That weight is roughly the square root of the rate, so a rate of 0.0001 gives a new day a weight of about 1 percent, not 0.01 percent. A higher rate means more weight on a new day and a shorter equivalent window. The panels now say this. The earlier sentences on this page are kept above and marked as superseded.
- Decision (owner, 2026-11-18): `ex_ante_betas` is no longer part of the Kalman section. It was the filtered beta shifted by one day and carried no new information. The section on the cached SPY history is now about 1.45 MB, 38 percent of the report JSON (was 1.85 MB, 44 percent). The ex-ante beta for a day is the filtered beta of the day before.
- The Kalman hook now marks its section as failed, with a reason, on any error or non-finite result, so the rest of the report always builds.
- New tests check the drift term against statsmodels and against the single-path likelihood on data where the betas drift, so the default test run catches a broken drift term.

Still open for the owner: sign-off of the edits to contract files, and whether the label keeps its "window of N days" clause.

## What would change our mind

The independent validation finding a difference from the spec's reference values; a better one-day-ahead prediction from the 252-day rolling beta than from the filter on a wider set of stocks; or users reading the extra line as a statement about the present when it is slow to react. Re-estimating every 63 days instead of 252 (spec Q1) is the first change we would try, because the run time no longer rules it out.

## Sources

- [docs/specs/kalman-betas.md](../docs/specs/kalman-betas.md): KB1 to KB5 (model, estimation, bands), KB7 (comparison with rolling betas), KB8 (outputs), KB10 (decisions and open questions), KB11 (tests).
- [docs/reviews/kalman-betas-validation-2026-11-18.md](../docs/reviews/kalman-betas-validation-2026-11-18.md): the independent validation.
- [docs/validation/kalman-betas-handoff-2026-11-18.md](../docs/validation/kalman-betas-handoff-2026-11-18.md): what was built, the real SPY numbers, the payload measurement and what the validator recomputes.
- [docs/methodology.md](../docs/methodology.md): M0.2 (stamping and look-ahead), M4 (rolling betas).
- Durbin and Koopman, *Time Series Analysis by State Space Methods*, 2nd edition (Oxford University Press, 2012): the standard reference for the filter (not re-checked for this page).

## Related decisions

- [No look-ahead rule](decision-no-look-ahead-rule.md)
- [One contract for the five new report sections](decision-schema-v3-contract.md)
- [Which betas count as reliable](decision-which-betas-count-as-reliable.md)
- [Drift alerts and regime betas](decision-drift-alerts-and-regime-betas.md)
- [SPY timing noise and the quality gate](decision-spy-timing-noise-and-the-quality-gate.md)
- [Report design: colour is evidence](decision-report-design-colour-is-evidence.md)
