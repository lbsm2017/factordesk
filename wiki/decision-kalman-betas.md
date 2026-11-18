# Decision: Kalman-filter betas as an extra line beside the rolling betas

Date: 2026-11-18
Status: Decided-pending-implementation (built and tested on branch `feat/kalman-betas`; stays pending until the independent validation in `docs/validation/kalman-betas-handoff-2026-11-18.md` is done and the branch is merged)

## In one sentence

We show a second kind of time-varying beta, estimated by a Kalman filter that learns from the stock's own past how fast its exposures drift, as an additional line with an uncertainty band, and we do not let it replace the rolling betas anywhere.

## What we decided

- The five betas follow a random walk and alpha is held constant. One number, the drift rate (lambda), says how much weight a new day gets. It is estimated from the data up to each date, on a grid, and re-estimated once a year (every 252 trading days after the first 504). Spec KB1, KB2.
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
- It adds time and size. On the cached real SPY history (8474 days) the hook added about 1.5 to 2.3 seconds to building a report (1.35 s without it, 3.6 s with it, median of six runs, on a machine that was busy with other work), and the section is about 1.85 MB, 44 percent of the whole report JSON. About a fifth of the section (`ex_ante_betas`) repeats the beta series shifted by one day. Removing it is an owner decision (handoff document, section 7). All as measured on 2026-11-18.
- The line can jump once a year at the re-estimate dates.
- Not built: the smoother (TKB06), the Student-t variant in the report (the code exists), the diagonal drift matrix, the point-in-time AR(1) comparison.

## What would change our mind

The independent validation finding a difference from the spec's reference values; a better one-day-ahead prediction from the 252-day rolling beta than from the filter on a wider set of stocks; or users reading the extra line as a statement about the present when it is slow to react. Re-estimating every 63 days instead of 252 (spec Q1) is the first change we would try, because the run time no longer rules it out.

## Sources

- [docs/specs/kalman-betas.md](../docs/specs/kalman-betas.md): KB1 to KB5 (model, estimation, bands), KB7 (comparison with rolling betas), KB8 (outputs), KB10 (decisions and open questions), KB11 (tests).
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
