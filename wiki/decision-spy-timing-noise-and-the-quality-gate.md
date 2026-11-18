# Decision: SPY timing noise, and a pre-set quality gate

Date: 2026-11-18
Status: Decided-pending-implementation

## In one sentence

SPY fits the factors worse than expected (R-squared 0.967, not about 0.995) because older Yahoo closing prices carry timing noise, so we keep the full sample, show its alpha with a caveat, and add a pre-specified gate that flags this pattern for every ticker.

## What we decided

- Keep the full sample. Do not pick a cleaner period after seeing results.
- Show the alpha number with a caveat, and say "significant at 5% (single test, in-sample)" rather than "reliable".
- Add a gate, written down before use: if residual lag-1 autocorrelation is below -0.2 with a robust z below -4, add a caveat and a 5-day (non-overlapping) estimate. Alpha is called significant only if daily and 5-day estimates both reject at 5%.
- A second check (variance stability across years) reports a break date and each side's alpha, as information only.

As of 2026-11-18 the gate is not in `docs/methodology.md`, so this is pending implementation. Thresholds are untested outside five S&P 500 products.

## Why

The independent validation traced the low R-squared to SPY's pre-2009 closes, which appear to include market moves after the 4:00 pm index close; these reverse the next day. We rejected "use 2010 onward" because choosing a period after seeing the residuals is a forking-paths choice and changes what is being measured. We rejected silence because the report would show "audit: clean" beside a number that hides noisy data.

## How it works

- Evidence: residuals have lag-1 autocorrelation of -0.404. If errors are `u_t - u_(t-1)`, the noise share is about 2 x 0.40 = 0.81. The S&P 500 total-return index gives 0.87.
- R-squared is 0.9673 over 1993 to 2026 and 0.9950 from 2010-01-04. Over 1993 to mid-2009, summing 1, 2, 5 and 10 days lifts SPY's R-squared from 0.948 to 0.969, 0.982 and 0.986, while the index stays at 0.995.
- A variance break sits at 2009-07-21 (4.58% a year before, 1.35% after).
- The noise does not create the alpha: SPY's alpha is -0.58% a year (z -2.24); the index gives -0.53% (z -2.79).
- Gate on SPY: full sample -0.40 fires; the index (-0.06) and a mutual fund priced at 4 pm (-0.11) do not.

## What it costs us

- The mechanism is a hypothesis. A 4:15 pm closing print would fit, but the date it ended and Yahoo's choice of print are unconfirmed (about 85% confidence in the main cause).
- The gate may misfire: it was calibrated on five S&P 500 products only. A panel of ETFs, stocks and ADRs is needed first.
- The caveat adds text to reports, and the 5-day estimate is noisier.
- The full-sample alpha mixes two regimes and mostly describes the index against the factor data, not SPY's management.

## What would change our mind

Calibration showing the gate fires often on clean tickers, a confirmed mechanism that allows a principled data correction, or a better closing-price source.

## Sources

- [docs/validation/spy-slice-validation.md](../docs/validation/spy-slice-validation.md), sections 3 and 3.6, findings F1 and F2.
- [docs/methodology.md](../docs/methodology.md), M3.5 (diagnostics; gate absent as of 2026-11-18).
- [docs/test-oracle.md](../docs/test-oracle.md), T47.

## Related decisions

- [Daily returns and robust errors](decision-daily-returns-and-robust-errors.md)
- [Independent validation and mutation testing](decision-independent-validation-and-mutation-testing.md)
- [Thin slice on SPY first](decision-thin-slice-on-spy-first.md)
