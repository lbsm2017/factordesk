# factordesk coding standards

These rules are non-negotiable. Reviewers reject a change that breaks one; there are no exceptions in review comments. If a rule blocks you, change this file (with a reason) before writing the code. The statistical definitions live in `docs/methodology.md`; the tests that enforce them are in `docs/test-oracle.md`.

## 1. Units and naming of return series

- Returns are **simple, daily, decimal** (0.01 = 1%) everywhere in the backend. Percent exists only in the French raw file (converted on parse) and in UI formatting.
- Names say what a series is: `ret` = simple daily return, `xret` = excess return (`ret - rf`), `logret` = log return, suffix `_ann` = annualised (factor 252, `docs/methodology.md` M0.4), `_cum` = compounded cumulative. No bare `r`, `returns2` or `data`.
- Factor columns are exactly `mkt_rf, smb, hml, rmw, cma, rf`, in that order. Display names (`Mkt-RF`, ...) only appear in the API and UI layers.
- Date index: tz-naive, normalised, unique, strictly increasing `DatetimeIndex` named `date`. Validate on entry to every public function.
- Never mix arithmetic contributions with compounded returns in one sum.

## 2. No look-ahead

- A value stamped at date `t` may only use rows dated `<= t`. Anything used to explain day `t` uses rows `<= t-1`.
- Forbidden in `analytics/` and `data/`: negative `shift`, `rolling(..., center=True)`, `bfill`/`backfill`, `interpolate`, whole-sample normalisation inside rolling code, and `pct_change()` without `fill_method=None`. Use the positional `shift(1)` for "previous day".
- Trailing windows contain exactly `W` rows: `rolling(window=W, min_periods=W)`. Test T48 and the look-ahead tests T102-T104 must stay green.

## 3. No silent row dropping or zero-filling

- No `fillna` on prices, returns, factors or betas. NaN is either a reported exclusion (with date and reason in `SampleInfo`) or an error.
- Rows are never dropped because they are extreme. They are flagged by the audit.
- Inner joins must report what they removed: requested vs actual dates, and every excluded row.

## 4. Pure, typed analytics

- Every public function in `backend/factordesk/analytics/` is pure: no I/O, no network, no clock, no globals, no randomness without an injected `numpy.random.Generator`. Inputs are not mutated.
- Inputs and outputs are typed objects (frozen dataclasses or pydantic models with validated frames inside), not loose dicts or tuples. Full type hints; `pyright` strict and `ruff` must pass.
- Clocks, HTTP clients and file paths are injected into `data/` functions so tests can control them.
- Regressions are OLS with an intercept and Newey-West HAC using the lag rule in M0.5, passed explicitly to statsmodels. No regularised or no-intercept fits.

## 5. Every statistic ships with its sample

- Every statistic carries `status`, `reason`, and `SampleInfo` (`n`, actual `start`/`end`, requested dates, excluded rows, factor vintage).
- Below its minimum sample a statistic returns `insufficient_data` with `null` values, never a number computed on too little data.
- Significance is decided only by the rules in M0.6 (HAC p-values, Benjamini-Hochberg families). No ad-hoc `|t| > 2` thresholds.

## 6. API surface

- The frontend sees only the pydantic models in `report/schema.py`. No endpoint returns a DataFrame, a dict built ad hoc, or an untyped JSON blob.
- NaN and infinity are never serialised: use `null` plus a status.
- A new statistic needs: a section in `docs/methodology.md`, a schema, and oracle tests, in the same change.

## 7. Secrets and configuration

- No keys, tokens or personal paths in code, tests, fixtures or logs. Secrets come from `.env` through `config.py` (pydantic-settings); `.env` is gitignored and `.env.example` holds placeholders only.
- URLs and constants (French URL, crisis dates, thresholds) live in one config or constants module, not scattered literals.

## 8. No one-off workarounds

- No ticker-specific branches, hard-coded date patches, or "temporary" fixes for one data glitch. Fix the general rule (parser, audit, alignment) and add a test for the case.
- No silenced warnings or broad `except Exception: pass`. Catch specific errors and turn them into typed errors or reported findings.
- When a convention is broken, fix it before new feature work.
