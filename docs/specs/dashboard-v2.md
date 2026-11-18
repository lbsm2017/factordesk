# factordesk specification: dashboard v2 (sidebar, plain-language outcomes, switches)

Status: implementation specification, written 2026-11-18 (Stage 0 of the approved plan). Not yet
implemented. The owner approved the plan on 2026-11-18; the look still needs the owner's approval
of the Stage 1 prototype before any React work starts (DV10).
Audience: the Stage 2 agents A to F, the performance and world-beta agents, the integrator, and
reviewers checking the work against it.
Companions: `docs/specs/dashboard.md` (DB0 to DB10, still in force where this file says nothing),
`docs/design/report-design.md` rev 3 (sections C, D, J, K, L and M carry the look), the rev 3
prototype in `docs/design/prototype/` (files named `*-v3*`), `docs/specs/schema-v3-contract.md`,
`docs/methodology.md`, `docs/methodology-residual-analysis.md`, and the wiki page
`wiki/decision-dashboard-v2.md`.
Section ids: DV0 to DV11, appendix A. Tickets: V1 to V16 (DV9). Verdict rules: DV4 (called the
V-rules elsewhere). Open questions: DV11.

---

## DV0. Scope

**Goals.**

1. A full-width page with a dark navy left sidebar that holds the controls and the section
   navigation (owner answer, 2026-11-18).
2. The verdict in the first screen, in plain words a non-statistician can follow, with the
   evidence one click or one switch away.
3. Bigger, easier type: nothing under 14 px; body 16 px; panel outcome sentences 19 px.
4. Colour and highlighted areas in the owner's fintech-tool palette, with evidence colours that
   keep their meaning (design rev 3, M).
5. Toggle switches: "Show statistics", in the URL. (The "Dark theme" switch was dropped by the
   owner on 2026-11-19; light only, see DV11 item 6.)
6. The company name, exchange and currency in the header (owner request).
7. Historical performance (return, volatility, Sharpe ratio, largest fall) and a quick world beta,
   each as an optional report section (owner additions, 2026-11-18).
8. The regression formula is removed (owner answer: "beautiful but useless for non-nerds").

**Non-goals.**

- **The static report port is later.** `backend/factordesk/report/render_html.py` keeps design
  rev 2 apart from three additive pieces that come from the schema: the company name line (V6),
  the performance panel (V13) and the world beta panel (V15). The full port is roadmap epic 18.
- **No Tailwind, no shadcn/ui.** Plain CSS tokens stay (`docs/specs/dashboard.md`, owner decision
  4). Switch, segmented control and drawer are small native-element components.
- **No new runtime dependency.** Icons are an inline SVG set. IBM Plex Sans ships as local WOFF2
  files (a font, not a package dependency).
- No tabs; the page is one scrolling page (owner decision 5 of `docs/specs/dashboard.md` stands).
  The sidebar navigates; it does not hide panels.
- No online ticker or name search (owner decision 3 of `docs/specs/dashboard.md`).
- No change to any statistic or methodology rule. Every sentence in DV4 reads existing fields; the
  only new numbers come from the two new optional sections, whose methods belong to their own
  branches.

---

## DV1. Architecture delta

- **Shell.** `App.tsx` renders `Shell` = skip link + `Sidebar` (`<aside>`) + `<main id="report">`.
  Every report panel stays a direct child of `<main>` in registry order. The controls of
  `components/controls/*` move into the sidebar with their props unchanged.
- **Panel props.** `PanelHostProps` (in `components/report/panelRegistry.ts`) gains
  `stats: boolean` (the Show statistics switch). Panels read it through props, never from
  `location`. No other prop changes.
- **Registry (React) after v2.** Positions follow contract SC4; the changes are marked.

| Position | Name | Element id | Change |
|---|---|---|---|
| 100 | `header` | `header` | company name line (V5) |
| 200 | `verdict` | `verdict` | **new**, replaces `equation`; holds the outcome tiles and the performance row |
| 250 | `notice` | `notice` | **moved** from 150, now the amber band under the performance row |
| 300 | `factors` | `factors` | **new**, replaces `kpis` |
| 350 | `world_beta` | `world-beta` | **new** optional section (V15, V16) |
| 400 | `price` | `price` | outcome line |
| 450 | `performance` | `performance` | **new** optional section (V13, V14) |
| 500 to 1000 | as SC4 | as SC4 | outcome lines, statistics columns |
| 1100 | `colophon` | `colophon` | unchanged |

- **Contract amendment (SC4).** Until epic 18 the two registries differ: React has `verdict`,
  `notice` (250) and `factors`; the static report keeps `equation` (200) and `kpis` (300). Both
  registries get `world_beta` (350) and `performance` (450) with the same ids. `panelRegistry.test`
  replaces its parity check with an explicit, commented list of React-only and static-only names.
- **Contract amendment (SC3.1, SC5).** Two new optional sections, `performance` and `world_beta`,
  join the `SECTIONS` tuple with their own modules under `report/sections/` and their own pipeline
  hooks, the same pattern as the five sections of the contract. They are additive and do not
  bump the version by themselves (SC5). The version bump to 5 comes from `data.security` (DV2.1).
- **Verdict text is derived in the frontend** (`frontend/src/text/verdict.ts`), from fields that
  exist. Only the name, currency and exchange, and the two new sections, are new data.

---

## DV2. API and schema delta

### DV2.1 `data.security` (ticket V6)

```python
class SecurityInfo(FrozenModel):
    name: str | None       # Yahoo long_name, falling back to short_name; None when unknown
    currency: str | None   # ISO code as Yahoo reports it, for example "USD"
    exchange: str | None   # Yahoo exchange label, for example "NMS" mapped to "NASDAQ" (DV2.2)

class DataInfo(FrozenModel):
    ...
    security: SecurityInfo | None = None   # new, optional, last field
```

- **Source.** One Yahoo metadata read per ticker in `backend/factordesk/data/prices.py`, next to
  the price fetch: `long_name` (fallback `short_name`), `currency`, `exchange`, `quote_type`.
  Cached beside the price cache with the same refresh rule (same-day cache). Never blocking: if
  the read fails, is throttled or times out, the report builds with `security = None` (or with
  null members) and one log line; no warning is added to the report.
- **Version.** No bump (decided 2026-11-19, following SC5): `SCHEMA_VERSION` stays `"4"` and
  `SUPPORTED_SCHEMA_VERSIONS` stays `("3", "4")`. The new fields `data.security`, `performance` and
  `world_beta` are additive and optional, and feature branches do not bump (SC5). A version 3 or 4
  file loads with the new fields `None`. A reader cannot tell "written before names existed" from
  "name not found"; both show the ticker only. Regenerate
  `frontend/src/api/openapi.json` and `types.gen.ts` once, in V6.
- **Colophon.** "factordesk report, schema v4. ..." stays as it is, no wording change.

### DV2.2 Exchange labels

`exchange` stores a reader label, mapped in `prices.py` from Yahoo's code: `NMS`, `NGM`, `NCM` to
"NASDAQ"; `NYQ` to "NYSE"; `ASE` to "NYSE American"; `PCX` to "NYSE Arca"; `BTS` to "Cboe BZX";
any other code is stored as Yahoo gives it. The table lives in one constant with a test.

### DV2.3 Currency check (roadmap ticket N1, folded into V6)

- Owner decision of 2026-11-18 (F13): refuse non-USD tickers until European factors exist.
- Rule: when `currency` is known and not `"USD"`, the request fails before any regression with a
  new `ApiError` code `unsupported_currency`, HTTP 422, message "ASML.AS is quoted in EUR; factordesk
  analyses US dollar prices only, because the factors are in US dollars." and action "Choose a
  US-listed ticker, for example ASML." The CLI prints the same one line and exits 2.
- When `currency` is unknown (metadata read failed), the report builds and carries the warning
  `currency_unknown`: "The trading currency could not be checked; the analysis assumes US
  dollars." (`WARN_PLAIN` gets the same text.)
- M1.5's `currency_mismatch` warning is replaced by the refusal; the D-entry that M1.5 lacks is
  written in V6 (roadmap N1).

### DV2.4 Ticker suggestions with names

`TickerSuggestion` gains `name: str | None = None`, read from the cached metadata of DV2.1 (no
network call). The combobox shows the name after the symbol in `--ink-2` when present.

### DV2.5 Optional section `performance` (ticket V13, branch `feat/performance`)

Definitions (owner, 2026-11-18). The copy in DV4.7 matches them; the backend spec owns the exact
field names, and the names below are the ones this spec reads (V14 maps any rename).

| Field (proposed) | Definition |
|---|---|
| `cagr_annual` | Compound annual growth over the analysed trading days: `(prod(1 + r_t))^(252 / n) − 1`, on the same total-return series the regression uses (adjusted close, the rows of the analysis sample) |
| `vol_annual` | Sample standard deviation of daily returns times `sqrt(252)` |
| `sharpe` | Mean daily excess return over the risk-free rate (`RF` of the factor file) divided by the standard deviation of daily excess returns, times `sqrt(252)` |
| `sharpe_se`, `sharpe_ci_low`, `sharpe_ci_high` | Standard error and 95% interval of the Sharpe ratio (method in the `feat/performance` spec) |
| `max_drawdown` | Largest fall of the compounded return path from its running peak, as a negative decimal |
| `max_drawdown_peak`, `max_drawdown_trough` | Dates of that peak and trough |
| `max_drawdown_recovery` | First date the path is back at the peak; `None` when not recovered by the sample end |
| `drawdowns` | The largest falls (up to five), each with peak, trough, recovery or `None`, depth, days down, days to recover |
| `drawdown_series` | Dates and drawdown values for the chart |
| `start`, `end`, `n` | The span used (the analysis sample) |

Status values follow M0.7. With `status != "ok"` the tiles and the panel show the reason.

### DV2.6 Optional section `world_beta` (ticket V15, branch `feat/world-beta`)

Definition (owner, 2026-11-18): a single-factor OLS of the stock's daily excess returns on the
iShares MSCI ACWI fund's (Yahoo `ACWI`, history from March 2008) daily excess returns over the
common dates, HAC standard error (M0.5), 95% interval, R², number of days, plus the beta of the
same overlap against the US market (`Mkt-RF`) and a plain comparison.

| Field (proposed) | Meaning |
|---|---|
| `proxy` | `"ACWI"` |
| `beta`, `se`, `ci_low`, `ci_high`, `r2`, `n`, `start`, `end` | World fit over the overlap |
| `us_beta`, `us_se`, `us_ci_low`, `us_ci_high` | `Mkt-RF` fit over the same overlap |
| `comparison` | `"about_the_same"` when the two 95% intervals overlap, else `"higher"` or `"lower"` (world against US) |

Statuses (decided 2026-11-19, DV11 question 3): only the existing M0.7 values are used, with no
new literal.

- `ok`.
- `insufficient_data` when the overlap is under 252 days.
- `failed`, with the reason "The world fund's prices could not be fetched.", when the ACWI fetch
  fails and there is no cached copy. The report still builds.
- A stale cache (the refresh failed but cached prices exist) gives `ok`, with a note "ACWI data
  ends {date}" (the last cached date) in the section note.

Refresh rule (owner instruction, 2026-11-19): ACWI is refreshed incrementally on every ticker load,
that is, only the days after the last cached date are fetched, through the existing price provider
and cache.

---

## DV3. Shell, sidebar and navigation

### DV3.1 Behaviour

Look in design rev 3, J. Behaviour: the sidebar is sticky with its own scroll at 900 px and wider;
under 900 px a top bar opens it as a `<dialog>` drawer (`showModal()`); scroll-spy with one
`IntersectionObserver` (`rootMargin: "-20% 0px -70% 0px"`); a nav click scrolls, focuses the panel
`h2` and updates the hash with `history.replaceState`; `prefers-reduced-motion` disables smooth
scrolling and transitions. jsdom has no `showModal`; tests stub it.

### DV3.2 Navigation items

One item per panel that rendered, in registry order. A panel that renders nothing (for example
`lead_lag` while its section is null) has no item.

| Panel | Target | Label | Icon |
|---|---|---|---|
| `verdict` | `#verdict` | Summary | summary |
| `factors` | `#factors` | What drives it | drivers |
| `world_beta` | `#world-beta` | World beta | globe |
| `price` | `#price` | Price | line |
| `performance` | `#performance` | Performance | trend |
| `exposures` | `#exposures` | Exposures | bars |
| `lead_lag` | `#lead-lag` | Lead-lag betas | clock |
| `shrunk` | `#shrunk` | Shrunk betas | shrink |
| `fragility` | `#fragility` | Fragility | alert |
| `returns` | `#returns` | Return sources | coins |
| `risk` | `#risk` | Risk sources | gauge |
| `residual_alpha` | `#residual` | Residual return | wave |
| `rolling` | `#rolling` | Over time | history |
| `kalman` | `#kalman` | Kalman betas | filter |
| `data` | `#data` | Data and audit (badge) | check |
| `regression_detail` | `#regression-detail` | Regression detail | table |

`header`, `notice` and `colophon` have no item. Badge on "Data and audit": the number of audit
findings with severity `warning` or `error`; hidden when zero; error styling when any is an error.
Other icons in the set: menu, search, download.

### DV3.3 Header

Ticker (32 px), then the name line from `data.security` (design D.1 rev 3): name; then exchange
and currency joined by a comma ("NASDAQ, USD"). Missing parts are left out with their comma; all
missing means no line. On the right: the factor-data chip and the warnings chip (unchanged copy,
plural fix of V9 applies). "Download report" moves to the sidebar.

---

## DV4. Verdict rules (the V-rules)

These rules turn the report JSON into every generated sentence of the page. They are implemented
once, in `frontend/src/text/verdict.ts`, as pure functions of `FactorReport`, and unit-tested
against the mock fixture and the edge cases of appendix A. Panels never write their own outcome
text.

### DV4.1 Inputs

`ticker`; `regression.status`, `reason`, `factors[].name/beta/z/tag/ci_low/ci_high`,
`alpha_annual`, `alpha_tag`, `alpha_z`, `alpha_p`, `alpha_ci_low_annual`, `alpha_ci_high_annual`,
`alpha_sentence`, `r2`, `adj_r2`, `sigma_e_annual`; `risk_contribution.total_vol_annual`,
`factors`, `idiosyncratic`, `order`; `return_contribution.factors`, `alpha`,
`total_annualised_mean_excess_return`; `average_beta` (and `derive.ts` for the other window);
`data.audit_status`, `audit_findings`, `actual_start`, `actual_end`, `n_obs`, `n_excluded`,
`uncovered.n`; `price_series`; `quality_gate.fired`; the optional sections `residual`,
`shrunk_betas`, `kalman_betas`, `performance`, `world_beta`.

The tags already include every statistical rule: BH across five betas (M0.6, M3.2), the 5% single
test for alpha (M3.2) and the gate's conjunction rule (M3.6). **The frontend reads `tag` and
`alpha_tag` and never recomputes significance.**

### DV4.2 Wording rules (apply to every sentence)

1. **Never say more than the statistics support.** A coefficient whose tag is not `reliable` is
   described as "not distinguishable from zero", "not clear" or "no reliable ...". Never "no
   alpha", "no exposure", "zero" or "none".
2. Alpha is "the return beyond its exposures" in sentences. "Alpha" appears only in the
   Show statistics view and the regression detail. The phrase "no reliable return beyond its
   exposures" is the not-significant form; "not distinguishable from zero" stays for the alpha
   tile.
3. **No causation.** Use "moved with", "came with", "tended to do better when", "accounts for"
   (arithmetic), never "because of", "driven by" for a beta, "makes", "causes".
   ("Drives" is used only for the risk shares, which are an exact arithmetic split, M7.)
4. **No forecast.** Past tense or "over this range" for results; never "will", "expect", "should
   return". The verdict band always ends with "Descriptive, in-sample, not predictive." (L-DESC,
   M0.9); the performance row always carries the past-performance caption (DV4.7).
5. **Hedge** when the quality gate fired (`quality_gate.fired === true`, M3.6) or the audit has
   errors (`data.audit_status === "errors"`, M1.4 and validation F4), exactly as DV4.4 to DV4.8 say.
6. Market beta reading (existing rule of `exposureReading` in `text/plain.ts`, design H.2):
   `|beta − 1| < 0.1` reads "moves with the market"; `beta ≥ 1.1` "amplifies"; `0 < beta ≤ 0.9`
   "moves less"; `beta < 0` "moves against" (new product choice; `exposureReading` has no
   negative case).
7. Style tilts use the `TILT` pairs of `text/plain.ts` (positive beta = first phrase, negative =
   second) and the plain names of `PLAIN`, lower case inside sentences.
8. Plain words for numbers: "about 1.42 times as much", "12.6% a year", "out of 17.0% in total".
   No Greek letters, no "t", "p" or "R²" outside the Show statistics view and the tile labels.
9. Sentence case, no exclamation marks, no emoji, no all-caps.

### DV4.3 Number formats

Built on `format/numbers.ts` (true minus U+2212, `+` on signed values, zero unsigned).

| Name | Rule | Example |
|---|---|---|
| `pct1s(x)` | `pct(x, 1)`, signed | +0.8%, −3.4% |
| `pct1(x)` | `pct(x, 1, false)` | 17.0% |
| `times(b)` | `num(b, 2)` | 1.42 |
| `share(x)` | whole percent; when that would read 0% or 100%, one decimal; when one decimal still reads 100.0% or 0.0%, "more than 99.9%" or "less than 0.1%" | 37%, 99.9% |
| `days(n)` | grouped integer with "day" or "days" (fixes "1 days") | 1 day, 1,254 days |
| `date(d)` | "8 Aug 2024" (existing `dateLong`) | 30 Sep 2026 |
| `sharpe(x)` | `num(x, 2)` | 0.74 |
| lists | two items "a and b"; three or more "a, b and c" (no serial comma) | |
| headline join | the headline's parts use a serial comma: "A, B, and C" (the parts contain "and" themselves) | |

### DV4.4 Headline

Built from up to three parts, joined with the headline join of DV4.3, subject = ticker:

**Part M (market), from `factors["Mkt-RF"]`** (omitted when `beta` or `tag` is null):

| Condition | Text |
|---|---|
| tag not `reliable` | shows no reliable link to the market |
| `|beta − 1| < 0.1` | moves with the market (about one-for-one) |
| `beta ≥ 1.1` | amplifies market moves (about {times(beta)} times as much) |
| `0 < beta ≤ 0.9` | moves less than the market (about {times(beta)} times as much) |
| `beta < 0` | tends to move against the market (about {times(|beta|)} times as much, in the opposite direction) |

**Part S (style).** Tilts = for SMB, HML, RMW, CMA in that order, each `reliable` factor with a
non-null, non-zero beta gives `TILT[name][beta > 0 ? 0 : 1]`. If there is at least one:
"leans toward {list(tilts)}". If none: "has no clear tilt toward size, value, profitability or
investment".

**Part A (return beyond exposures)**, omitted when `alpha_annual` is null:

| Condition | Text |
|---|---|
| `alpha_tag === "reliable"` and `alpha_annual > 0` | earned {pct1(alpha)} a year more than its exposures explain over this range |
| `alpha_tag === "reliable"` and `alpha_annual < 0` | earned {pct1(|alpha|)} a year less than its exposures explain over this range |
| otherwise (`noise` or null tag) | shows no reliable return beyond its exposures |

**Assembly and hedges.**

- Normal: "{T} {M}, {S}, and {A}." (with fewer parts, "{T} {X} and {Y}." or "{T} {X}.").
- Audit errors: "The price audit found errors in {T}'s prices, so these results are not
  interpretable until the errors are explained. Taken at face value, {T} {M} and {S}." Part A is
  dropped (alpha carries no claim under audit errors, as the rev 2 KPI rule F4).
- Gate fired (and no audit errors): the normal headline, then the hedge sentence at lead size:
  "Its closing prices look out of step with the factor data, so the share the model explains is
  probably understated." (M3.6: R² falls and residual volatility rises when the gate fires; the
  tags are already conservative.)
- Regression not ok: "factordesk could not fit the five-factor model for {T} over this range:
  {reason}." No tiles except the world beta and performance tiles if those sections are ok; no
  factor cards (the `factors` panel shows its empty state).
- Length guard: at most 40 words before the hedge sentence (words counted by spaces). The longest
  possible normal headline (market against, four tilts, a significant alpha) is 43 words. When the
  headline would exceed 40 words, Part S lists only the two tilts with the largest `|beta|` (in
  canonical order) and ends "and {n} other style {tilt / tilts}" (new product choice; the cards
  list all of them). The mock headline is 23 words; A.5 is 32.

### DV4.5 Outcome tiles

| Tile (label) | Value | Note | Show statistics line |
|---|---|---|---|
| Return beyond its exposures | `{pct1s(alpha_annual)} a year`, or "n/a" | `reliable`: "Distinguishable from zero at the 5% level". `noise`: "Not distinguishable from zero". Null tag: "Significance not available". Audit errors: "Not interpretable: the price audit found errors". When `alpha_sentence` is not null, a "Why?" disclosure under the note shows it (M3.2 large-but-insignificant rule) | "t {tstat(alpha_z)}, p {pval(alpha_p)}, 95% interval {pct1s(lo)} to {pct1s(hi)}" |
| How much the model explains | `share(r2)` with the gauge | "of the day-to-day variation in {T}'s return; {share(1 − r2)} is specific to {T}". Gate: add ". Probably understated: closing prices look out of step with the factor data". Audit errors: "Not interpretable: the price audit found errors" | "Adjusted R² {num(adj_r2, 4)}" |
| Stock-specific risk | `pct1(sigma_e_annual)` | "a year of swings the factors do not explain, out of {pct1(total_vol_annual)} in total". Gate: add ". Probably overstated: closing prices look out of step with the factor data". Audit errors: as above | none |
| World beta (quick estimate) | DV4.8 | DV4.8 | DV4.8 |

`1 − r2` equals the idiosyncratic risk share exactly in real reports (M7). The mock fixture is
synthetic and does not obey it (`r2` 0.9987, `idiosyncratic` 0.0047), so tiles read `r2` and the
risk outcome reads `idiosyncratic`, each from one field.

### DV4.6 Factor cards

For each factor in canonical order:

- **Pill:** `reliable` and `beta > 0`: "Positive" (up arrow, `--pos`); `reliable` and `beta < 0`:
  "Negative" (down arrow, `--neg`); otherwise "Not clear" (dash, `--neutral`). Null beta or tag:
  "Not available" and no bar.
- **Strength bar domain:** symmetric `±D`, `D = max(1, ceil(max_i |beta_i| / 0.5) × 0.5)` over the
  five betas (new product choice: one scale so bars compare; at least ±1 so a market beta near 1
  fills about half a card).
- **Sentence**, market:

| Condition | Sentence |
|---|---|
| not `reliable` | No reliable link to the market over this range. |
| `|beta − 1| < 0.1` | Moves with the market: on average, a 1% market move came with a {times(beta)}% move in {T}. |
| `beta ≥ 1.1` | Amplifies the market: on average, a 1% market move came with a {times(beta)}% move in {T}. |
| `0 < beta ≤ 0.9` | Moves less than the market: on average, a 1% market move came with a {times(beta)}% move in {T}. |
| `beta < 0` | Moves against the market: on average, a 1% market rise came with a {times(|beta|)}% fall in {T}. |

- **Sentence**, style factor with `TILT[name] = [A, B]`:

| Condition | Sentence |
|---|---|
| not `reliable` | No clear tilt toward {A} or {B} over this range. |
| `reliable`, `beta > 0` | Leans toward {A}: {T} tended to do better when {A} beat {B}, and worse when they lagged. |
| `reliable`, `beta < 0` | Leans toward {B}: {T} tended to do better when {B} beat {A}, and worse when they lagged. |

- **How sure:** "Significant" (`reliable`), "Not significant" (`noise`), "Not available" (null).
  Audit errors: "Not interpretable", and the sentence gets " Unconfirmed: the price audit found
  errors." appended; the card is muted (bar faded, top rule `--neutral`).
- **Show statistics:** "beta {signed(beta, 3)}, 95% interval {signed(ci_low, 3)} to
  {signed(ci_high, 3)}, t {tstat(z)}".
- "See the detail" links to `#beta-{name}` with the scroll-and-focus behaviour of the old
  `Equation.tsx` (`focusRow`), moved to a shared helper.

### DV4.7 Performance tiles and wording (section `performance`)

Caption under the row, always: "Past performance over the analysed range. It does not predict
future returns."

| Tile | Value | Note | Show statistics line |
|---|---|---|---|
| Return a year | `pct1s(cagr_annual)` | "Compound growth a year from {date(start)} to {date(end)}, dividends reinvested" | none |
| Volatility a year | `pct1(vol_annual)` | "How widely daily returns swung, scaled to a year" | none |
| Sharpe ratio | `sharpe(sharpe)` | "Return above the factor file's risk-free rate, per unit of volatility." Then: interval includes 0: "Cannot be told apart from zero." Interval above 0: "Above zero at the 5% level." Interval below 0: "Below zero at the 5% level." Interval null: "No interval available." | "standard error {num(sharpe_se, 2)}, 95% interval {num(lo, 2)} to {num(hi, 2)}" |
| Largest fall | `pct1s(max_drawdown)` | Recovered: "From {date(peak)} to {date(trough)}; back at the peak by {date(recovery)}". Not recovered: "From {date(peak)} to {date(trough)}; not recovered by {date(end)}" | none |

Rules: never "will", "expected" or "likely" with these numbers; "not recovered" is said in those
words whenever `max_drawdown_recovery` is null; the Sharpe ratio is always "above the factor
file's risk-free rate", never "above zero return". Audit errors: every value in `--ink-2` and each
note gains " Unconfirmed: the price audit found errors." Status not ok: one wide tile with the
reason.

### DV4.8 World beta wording (section `world_beta`)

Comparison phrase from `comparison` (the frontend also computes it from the intervals and the
unit test checks they agree): `about_the_same`: "about the same as"; `higher`: "higher than";
`lower`: "lower than". **When the intervals overlap the phrase is always "about the same as"**,
whatever the point estimates; a difference is never claimed from overlapping intervals.
Non-overlap is an informal, conservative reading, not a test of the difference (the two betas use
the same stock returns); the panel's "How this is computed" says so.

| Status | Tile value | Tile note | Panel |
|---|---|---|---|
| `ok` | `times(beta)` | "Against world stocks, with the ACWI fund standing in for the index; {phrase} its US market beta of {times(us_beta)}"; with a stale cache the note gains ". ACWI data ends {date}" | outcome line below |
| `insufficient_data` | "n/a" | "Too few days overlap with the world fund: {n}, at least 252 needed" | empty state, reason as given, action "Choose a longer range." |
| `failed` | "n/a" | "The world fund's prices could not be fetched; nothing else in the report is affected" | empty state, action "Try again later." |
| section null | tile hidden | | panel hidden |

Show statistics line (tile): "standard error {num(se, 3)}, R² {num(r2, 2)}". Gate fired: the note
gains ". Daily prices look out of step with the factor data, so this daily beta may be biased"
(M3.6 notes that late-recorded moves bias daily betas). Audit errors: " Unconfirmed: the price
audit found errors." Every world beta text says "quick estimate" (tile label, panel title) and
names ACWI as a stand-in (tile note, panel caption of design L.7).

### DV4.9 Outcome line of every panel

One sentence (two when stated) under each panel title. `{T}` is the ticker. A panel in its empty
state has no outcome line.

| Panel | Rule and copy |
|---|---|
| Price | `ch = adj_close(actual_end) / adj_close(actual_start) − 1` from `price_series`. "With dividends reinvested, {T} {rose / fell} {pct1(|ch|)} over the analysed range ({date(actual_start)} to {date(actual_end)})." (`ch = 0`: "ended where it started"). When `uncovered.n > 0`: " The last {n} price {day is / days are} charted but not analysed." Null when either price is missing. |
| World beta | `ok`: "Against world stocks, {T}'s beta was {times(beta)} over {date(start)} to {date(end)} ({days(n)}), {phrase} its beta against the US market on the same days ({times(us_beta)})." When `start` differs from `data.actual_start`: " This covers a shorter span than the five-factor model, because the fund's history starts in March 2008." (only when the overlap start is the fund's first date; otherwise "because the two price histories overlap only from {date(start)}"). |
| Performance | "{T} {grew / shrank} {pct1(|cagr_annual|)} a year over the analysed range; its largest fall was {pct1(|max_drawdown|)}, from {date(peak)} to {date(trough)}, {and it was back at the peak by {date(recovery)} / and it had not recovered by {date(end)}}." (`cagr_annual = 0`: "was flat") |
| Exposures | `k` reliable factors, `q` noise factors (plain names, "market" for Mkt-RF). `k = 0`: "None of the five exposures is distinguishable from zero over this range." Else: "{K} of the five exposures {is / are} clear ({list(k)}); {list(q)} {is / are} not distinguishable from zero." (second clause only when `q > 0`; `K` spelled out: One to Five) |
| Shrunk betas | Full-sample scope. `d = max |beta_shrunk − beta_ols|`, at factor `f`. "Pulled toward a typical stock, the betas move by at most {num(d, 2)} (the largest change is {plain(f)}: {signed(ols, 2)} to {signed(shrunk, 2)}); the ordinary betas stay the headline numbers." When any `moved_away` is true: " {Plain} moved away from the typical value, because the factors overlap." |
| Return sources | Largest `|component|` among the factor contributions and `alpha`; `tot` = total. If `|largest| ≥ 0.5 × |tot|`: "{Label} accounts for most of the {pct1(|tot|)} a year {T} earned {above / below} cash ({pct1s(largest)})." Else: "No single source accounts for most of the {pct1(|tot|)} a year {T} earned {above / below} cash; the largest is {label} ({pct1s(largest)})." Label: "{plain} exposure", or "the return beyond its exposures" for alpha. If the largest is alpha and not `reliable`: replace the final full stop with ", and it is not distinguishable from zero."; if it is a factor whose beta is not `reliable`: ", but that exposure is not distinguishable from zero." "Cash" means the risk-free rate of the factor file. |
| Risk sources | `top = order[0]`. If `top` is "Idiosyncratic": "Most of {T}'s day-to-day risk is specific to {T} ({pct1(idiosyncratic)})." Else: "{Plain} exposure drives {pct1(share)} of {T}'s day-to-day risk; {pct1(idiosyncratic)} is specific to {T}." |
| Residual return | Keyed by `residual.gap.verdict` (R4.8): `no_reliable_alpha` "Neither residual line can be told apart from zero; read both as noise." `point_in_time_only` "Only the point-in-time residual return is distinguishable from zero; the full-period one is not." `concentrated_in_warmup` "Most of the in-sample return beyond exposures comes from the first {W} trading days, which cannot be checked point-in-time." `reversed` "The in-sample return beyond exposures does not survive point-in-time betas: its sign flips." `mostly_disappears` "Most of the in-sample return beyond exposures disappears with point-in-time betas." `survives_not_significant` "Most of the in-sample return beyond exposures survives point-in-time betas, but it is not distinguishable from zero." `survives` "The in-sample return beyond exposures holds up with point-in-time betas and is distinguishable from zero." Gap not ok: "Only the in-sample line is available: {point_in_time_reason}." The panel body keeps `gap.message` (R4.8 exact copy). |
| Over time | Window on screen `W` (primary from `average_beta`, other from `derive.ts`). "In 80% of the {W}-day windows the market beta was between {num(p10, 2)} and {num(p90, 2)}." Plus, for style factors with `p10 < 0 < p90`: " The {list(plain names)} {exposure / exposures} spent long stretches on both sides of zero." Descriptive, not a drift test (L-OVERLAP; M9 is not built). |
| Kalman betas | First match: any vintage `lam_at_bound === "upper"`: "For at least one yearly re-estimate the filter follows daily noise; the estimate is not meaningful." (existing `kalman_text.json` warning). All vintages `"zero"`: "The filter found no drift in the betas over this range." Else, `L = latest["Mkt-RF"]`, `b` = full-range market beta: `L.band_low ≤ b ≤ L.band_high`: "The filter's latest market beta ({times(L.beta)}) is in line with the full-range estimate ({times(b)})." Otherwise: "The filter's latest market beta ({times(L.beta)}, band {times(L.band_low)} to {times(L.band_high)}) differs from the full-range estimate ({times(b)})." |
| Data and audit | `e`, `w` = findings of severity error, warning. `errors`: "The price audit found {e} {error / errors}; the results above are not interpretable until {it is / they are} explained." `warnings`: "The price audit flagged {w} unusual {item / items}; none stops the analysis." `clean`: "The price audit found no problems." Then always: " {n_obs grouped} trading days analysed, {n_excluded or "none"} excluded." |
| Regression detail | "{K} of the five betas {is / are} significant after allowing for testing five at once; the return beyond the exposures is {distinguishable / not distinguishable} from zero." Gate fired: " Because the quality gate fired, a term counts as significant only when the 5-day estimate agrees." (`K` = None to Five; "None ... is") |
| Lead-lag, Fragility | Not built; when their sections land, their specs add a row here before their panels ship. |

Copy fixes that land with the outcome lines (V9): every count uses `days()`-style plurals
("1 days with |daily return| > 40%" becomes "1 day with a daily return beyond ±40%"); a p-value
below 0.001 prints "p < 0.001" (not "p = <0.001"); the requested-versus-analysed pair reads
"Analysed 8 Aug 2024 to 30 Sep 2026 (you asked for 1 Nov 2024 to 13 Nov 2026)." in the Data and
audit coverage list.

### DV4.10 Thresholds and their sources

| Threshold | Value | Source |
|---|---|---|
| Beta significance (tag) | BH at q = 0.05 over the five betas | methodology M0.6, M3.2 |
| Alpha significance (tag) | single test, p < 0.05 | M3.2, M0.6 |
| Gate conjunction | daily and 5-day both reject | M3.6 item 3 (already inside the tags) |
| Gate hedge | `quality_gate.fired` (rho_1 < −0.2 and z < −4) | M3.6 |
| Audit hedge | `audit_status === "errors"` | M1.4; validation F4 (rule of the rev 2 KPI strip) |
| Market reading band | `|beta − 1| < 0.1` | existing product choice: design H.2 and `exposureReading` in `text/plain.ts`; a reading band, not a test |
| Negative market beta wording | `beta < 0` | new product choice |
| "Accounts for most" | at least 50% of `|total|` | new product choice: the plain meaning of "most", as R4.8 reads "mostly disappears" (`s < 0.5`) |
| "Both sides of zero" | `p10 < 0 < p90` | M5 percentiles (the Middle 80% column); descriptive, L-OVERLAP |
| Large-alpha "Why?" | `alpha_sentence` present (`|alpha| ≥ 3%`, `p ≥ 0.05`) | M3.2 |
| Share format | whole percent, one decimal near 0% or 100% | new product choice (format only) |
| Strength bar domain | `D = max(1, ceil(max |beta| / 0.5) × 0.5)` | new product choice |
| Headline length | 40 words before the hedge | new product choice (verdict size, design L.1) |
| Sharpe hedge | 95% interval includes 0 | owner rule, 2026-11-18; interval method in the `feat/performance` spec |
| World beta comparison | 95% intervals overlap means "about the same" | owner rule, 2026-11-18; informal and conservative, not a test |
| World beta minimum | 252 overlapping days | owner rule, 2026-11-18 (`world_beta` spec) |
| Kalman warning and "no drift" | `lam_at_bound` "upper" / all "zero" | Kalman spec and `report/kalman_text.json` |
| Residual verdict | G1 to G7 | `docs/methodology-residual-analysis.md` R4.8 |

---

## DV5. Show statistics: column map

Off is the default. Hidden columns are not rendered (not hidden by CSS), so screen readers and copy
follow what is on screen. **Never hidden:** the "Significant" word column, faded marks, interval
whiskers and bands (design principle 3: uncertainty is never colour-only and never switched off).
With statistics off every table has at most six columns (design rev 3 density rule 6).

| Panel or block | Off (visible) | Added when on |
|---|---|---|
| Outcome tiles | label, value, note | the statistics line of DV4.5 and DV4.8 |
| Factor cards | name, pill, bar, sentence, how sure | beta, 95% interval, t |
| Performance tiles | label, value, note | Sharpe: standard error, 95% interval |
| World beta table | Index, chart, Beta, 95% interval, Days | Standard error, R² |
| Price table | First, End of factor data, Latest, After factor data | nothing |
| Performance summary table | Measure, Value, Meaning | Standard error, 95% interval (Sharpe row) |
| Drawdown periods table | Peak, Trough, Recovered, Fall, Days down, Days to recover | nothing |
| Exposures | Factor, chart, Beta, Significant | t, Avg {W}d |
| Shrunk betas | Factor, chart, OLS beta, Shrunk beta | se, 95% credible interval, Pull |
| Return sources | Component, chart, % a year, Significant | nothing |
| Risk sources | Source, chart, Share | Beta, Factor vol, Corr. |
| Residual: summary | Line, Cumulative at the end, Residual return a year | t-statistic |
| Residual: non-overlapping windows | Window, Alpha a year, Reading | z, Adjusted p |
| Residual: split half | Alpha a year (first, second half) | interval rows, difference, z, p |
| Residual: calendar years | Year, In-sample sum, Point-in-time sum | nothing |
| Residual: diagnostics | hidden | the whole table |
| Over time | Factor, chart, Latest, Average | Middle 80% |
| Kalman betas | Factor, chart, Latest | sd, 95% band (the band stays drawn) |
| Kalman vintages table | hidden | the whole table |
| Data and audit | unchanged | nothing |
| Regression detail, main | Term, Estimate, Significant | Std. error, t, p, p adjusted, 95% interval, VIF |
| Regression detail, 5-day | Term, Estimate, Significant | Std. error, t, p, p adjusted, 95% interval |
| Residual diagnostics (M3.5) | Test, Reading | Statistic, Reference, p |

---

## DV6. Switches and URL state

- `UrlState` gains `stats: boolean` (default false) and `theme: "light" | "dark"` (default
  `"light"`).
- `parseUrl`: `stats` is true only for `stats=1`; any other value is dropped and the cleaned URL
  replaces the entry (existing cleaning rule). `theme` is dark only for `theme=dark`; `theme=light`
  is accepted and dropped (canonical form omits defaults).
- `toSearch` writes, in order: `t`, `range` or `start`/`end`, `win`, `stats=1` (when on),
  `theme=dark` (when dark). Example: `/?t=ZM&range=5Y&stats=1&theme=dark`.
- Switch changes use `history.replaceState` (view preferences, not navigation). Ticker, range and
  window changes keep `stats` and `theme` in the URL they push.
- Theme: `<html data-theme>` is set before first paint from the URL (a small inline-free module
  run at the top of `main.tsx`), and on every change. The `prefers-color-scheme` block leaves
  `tokens.css`; the OS setting is ignored (plan, confirm at Stage 1).
- `Switch` (`ui/Switch.tsx`): `<button type="button" role="switch" aria-checked>`; Space and Enter
  toggle; visible label is the accessible name. `Segmented` (`ui/Segmented.tsx`): native radios in
  a `fieldset` with a `legend`; arrow keys; disabled options keep a visible reason.

---

## DV7. Bundle plan

- Budget unchanged: initial script at most **400 kB raw / 125 kB gzip** (`frontend/scripts/size.mjs`).
  The plan's exploration measured 395.8 kB raw on 2026-11-18 (4.2 kB headroom); V9 re-measures
  before and after its changes.
- Freed: `KalmanPanel` and `ShrunkBetasPanel` (with their CSS and text) become `React.lazy`
  chunks, loaded only when their section is non-null; the registry entry wraps them in `Suspense`
  with a panel skeleton of fixed height. `PerformancePanel` loads with the lazy ECharts chunk.
  The equation and KPI strip code is deleted.
- Added (estimates, not measurements): shell, sidebar, navigation and drawer about 6 kB raw; icon
  set about 4 kB; switches and segmented control about 2 kB; `verdict.ts`, verdict band and factor
  cards about 8 kB; world beta tile and panel about 2 kB. About 22 kB raw in total.
- Acceptance (V10): the integrated build stays within budget with at least 8 kB raw of headroom;
  if not, the integrator lazy-loads the residual diagnostics and the regression detail tables next.
- Fonts are not in the script budget. IBM Plex Sans in four weights (Latin subset WOFF2) replaces
  Instrument Sans and the three STIX files; V3 records the before and after font bytes.

---

## DV8. Tests

**Tests to update** (owner of the change in brackets):

| Test | Change |
|---|---|
| `frontend/src/test/tokens.test.ts` (V3) | new token names and values; every required pair of design M.3 at its threshold; minimum font size 14 px; no hex outside `tokens.css`; canvas cap 1560 px instead of the 1216 px column |
| `frontend/src/styles/busyContrast.test.ts` (V3) | loading placeholder contrast on `--surface` and `--page` with the new values |
| `components/report/lead.test.tsx` (V5) | equation tests (six) removed; header name line; verdict band and factor card cases |
| `components/report/kpiGap.test.tsx` (V5) | KPI cells replaced by the outcome tiles |
| `components/report/busy.test.tsx` (V5) | `aria-busy` placeholders on the headline, tile values and card bars instead of KPI values and equation |
| `components/report/LoadingFrame.test.tsx` (V1) | one set of skeleton heights (no measured tiers), sidebar present in the frame |
| `components/report/panelRegistry.test.tsx` (V5) | new names and positions; parity with the static registry replaced by the documented difference list (DV1) |
| `components/report/ReportView.test.tsx` (V1) | panels still direct children of `<main>`; sidebar outside `<main>` |
| `components/controls/controlsStyle.test.ts` (V7) | segmented control and rail styling instead of the chip strip |
| `frontend/e2e/smoke.spec.ts` (V10) | wait for the verdict band instead of the KPI strip; toggle Show statistics and check a t column appears and `stats=1` is in the URL; toggle Dark theme and check `data-theme`; open the drawer at 390 px; `scrollWidth <= clientWidth` at 390 |

**New tests:** `text/verdict.test.ts` (V4: every row of DV4.4 to DV4.9 and appendix A, word for
word, on the mock fixture and mutated copies; a banned-words check that no generated string
contains "no alpha", "will ", "expect", "because of" or "causes"); `ui/Switch.test.tsx` and
`ui/Segmented.test.tsx` (V7: role, `aria-checked`, Space and Enter, arrow keys, visible label);
`state/url.test.ts` additions (V7: `stats` and `theme` round trip and cleaning);
`SectionNav.test.tsx` (V2: items follow rendered panels, `aria-current`, focus on activation,
badge count); `Drawer.test.tsx` (V2: open, Escape, focus return, closes on navigation); backend
`test_security_metadata.py` (V6: offline fake provider, throttled and failing reads give
`security = None`, no exception; exchange label table; currency refusal and unknown-currency
warning; version 3 and 4 fixtures still load); the section tests of V13 and V15 on their branches.

`uv run pytest -q` stays green apart from the intended changes of V6, V13 and V15.

---

## DV9. Tickets

Work lands on `feat/ui-v2-*` branches from `dev` in separate worktrees, one pull request per
agent or as the integrator decides; the owner merges. Paths under `api/`, `data/`, `report/` and
`tests/` are inside `backend/factordesk/`; other paths are under `frontend/src/` unless stated.
Size hint: haiku mechanical, sonnet standard, opus hard.

| Id | Agent | Scope (files owned) | Acceptance criteria | Depends on | Size |
|---|---|---|---|---|---|
| V1 | A shell | `App.tsx`, new `components/shell/{Shell,Sidebar,TopBar}.tsx`, `styles/frame.css`, `styles/shell.css`, `LoadingFrame.test.tsx`, `ReportView.test.tsx` | Design J.1, J.2, J.4 skeleton; controls moved into the rail with unchanged props; panels stay direct children of `<main>`; one set of skeleton heights; skip link first in tab order; `scrollWidth <= clientWidth` at 390 | Stage 1 approval | sonnet |
| V2 | A shell | new `components/shell/{SectionNav,Drawer,icons}.tsx`, `SectionNav.test.tsx`, `Drawer.test.tsx` | DV3.1, DV3.2; scroll-spy marks the panel in view; `aria-current="location"`; nav activation focuses the `h2`; drawer traps focus, closes on Escape and on navigation; reduced motion respected | V1 | sonnet |
| V3 | B tokens | `styles/tokens.css`, `styles/fonts.css`, `styles/report.css` and every panel CSS file (type-size and token pass only), `assets/fonts/*` (add IBM Plex Sans, remove STIX and Instrument Sans), `test/tokens.test.ts`, `styles/busyContrast.test.ts` | Design M.1 and M.2 in both themes; nothing under 14 px (test scans CSS); rows at least 48 px; prefers-color-scheme block removed; every required pair of M.3 passes in the test; font bytes before and after recorded in the PR | Stage 1 approval | sonnet |
| V4 | C verdict | new `text/verdict.ts`, `text/verdict.test.ts`; `text/plain.ts` (reuse only, no wording change) | DV4 in full; appendix A reproduced word for word; banned-words check; thresholds as constants with a comment citing DV4.10 | none (can start at once) | opus |
| V5 | C verdict | new `components/report/{VerdictBand,OutcomeTiles,FactorCards,PerformanceTiles,WorldBetaTile}.tsx` (the last two as stubs returning null for V14 and V16 to fill), `Header.tsx`, `panelRegistry.ts`, delete `Equation.tsx` and `KpiStrip.tsx`, `lead.test.tsx`, `kpiGap.test.tsx`, `busy.test.tsx`, `panelRegistry.test.tsx` | Design L.1 to L.3 and D.1; registry of DV1; card links focus the exposures row; empty and hedged states; `aria-busy` placeholders; density rule 1 (four per row) at every width | V4, V3 | sonnet |
| V6 | F backend | `data/prices.py`, `report/schema.py` (`SecurityInfo`, no version bump, `TickerSuggestion.name`), `pipeline.py`, `api/routes_factors.py`, `api/errors.py` (`unsupported_currency`), `report/render_html.py` (name line only), `cli.py` (refusal line), `tests/test_security_metadata.py`, regenerated `openapi.json` and `types.gen.ts`, the N1 D-entry in `docs/methodology.md` | DV2.1 to DV2.4; never blocks on metadata; non-USD refused with the DV2.3 copy; unknown currency warns; old fixtures load; static header shows the name; pytest, ruff, pyright green. Merged first | none (starts at once) | sonnet |
| V7 | D switches | new `ui/Switch.tsx`, `ui/Segmented.tsx`, their tests, `state/url.ts`, `state/useUrlState.ts`, `state/url.test.ts`, theme bootstrap in `main.tsx`, `components/controls/{RangeChips,CustomRange}.tsx` (segmented style), `controlsStyle.test.ts` | DV6 and design K; keyboard and `aria-checked` tests; `stats` and `theme` round trip; no theme flash on reload with `theme=dark` | V3 | sonnet |
| V8 | E panels | `PricePanel`, `ExposuresPanel`, `ReturnPanel`, `RiskPanel`, `RollingPanel`, `DataAuditPanel`, `RegressionDetail`, `Panel.tsx` (outcome line slot) and their tests | Outcome line from `verdict.ts` on each (DV4.9); DV5 columns for these panels; at most six columns with statistics off; empty states unchanged | V4, V5 (`stats` prop), V7 | sonnet |
| V9 | E panels | `sections/{ResidualAlphaPanel,ResidualAlphaBody,KalmanPanel,ShrunkBetasPanel}.tsx` and tests; lazy loading of Kalman and Shrunk in the registry entries | Outcome lines and DV5 columns for these three; Kalman and Shrunk in lazy chunks; copy fixes of DV4.9; size measured before and after | V8 | sonnet |
| V10 | Integrator | merge order F (V6), V13, V15, B (V3), A (V1, V2), D (V7), C (V4, V5), E (V8, V9), V14, V16; one types regeneration after the backend merges; `e2e/smoke.spec.ts`; skeleton heights | All frontend gates (`typecheck`, `lint`, `test`, `build`, `size`, `e2e`) and `uv run pytest -q` green on the integration branch; DV7 headroom | V1 to V9, V13 to V16 | sonnet |
| V11 | Reviewer | read-only | Independent opus design and accessibility review: contrast recomputed by the M.3 script, keyboard path of design J.5, 390 px, print, reduced motion, the seven density rules; plain-language review of every generated sentence against the numbers for SPY, ZM and an all-insignificant case; findings filed as fix tickets | V10 | opus |
| V12 | Integrator | screenshots only (`frontend/shots/`, gitignored) and `docs/dashboard.md` runbook notes | Real run (`uv run factordesk serve`, SPY and ZM, 5Y and Full) at 1920, 1440, 1024 and 390, light and dark, statistics on and off; compared point by point with the owner's screenshots (sidebar, font sizes, formula gone, verdict first, switches); real-data images stay out of the repository | V11 fixes | sonnet |
| V13 | Performance backend | branch `feat/performance`: `analytics/performance.py`, `report/sections/performance.py`, the pipeline hook, the static panel in `report/panels/`, tests, a methodology section | DV2.5 definitions exactly; Sharpe standard error and interval documented and tested; drawdown recovery `None` when not recovered; status values per M0.7; static panel draws the drawdown table; independent check of the four numbers on a synthetic series | none | sonnet |
| V14 | Performance frontend | `PerformanceTiles.tsx` (fill the V5 stub), new `sections/PerformancePanel.tsx` (lazy), registry entry 450, tests | Design L.4 and L.6; DV4.7 copy word for word; DV5 columns; "not recovered" case tested | V5, V13 | sonnet |
| V15 | World beta backend | branch `feat/world-beta`: `analytics/world_beta.py`, `report/sections/world_beta.py`, ACWI fetch through the existing price provider and cache, the pipeline hook, the static panel, tests | DV2.6; HAC per M0.5; overlap under 252 days gives `insufficient_data`; a failed fetch never fails the report; `comparison` from interval overlap | none | sonnet |
| V16 | World beta frontend | `WorldBetaTile.tsx` (fill the V5 stub), new `sections/WorldBetaPanel.tsx`, registry entry 350, tests | Design L.7; DV4.8 copy word for word; "about the same as" whenever the intervals overlap (test with crossing point estimates); DV5 columns | V5, V15 | sonnet |

**Parallel groups.** V4, V6, V13 and V15 start at once (no look dependency). After the Stage 1
gate: V1, V3 and V7 in parallel; then V2, V5; then V8, V9, V14, V16; then V10, V11, V12.
`App.tsx` belongs to V1; `panelRegistry.ts` to V5 (V9, V14 and V16 add their entries in their own
commits, rebased by the integrator); `report/schema.py` edits by V6, V13 and V15 are additive and
merged in that order.

---

## DV10. Stages and gates

- **Stage 0 (this document, design rev 3, the wiki page, the roadmap):** done when merged.
- **Stage 1 (prototype):** the rev 3 prototype and screenshots at 1920, 1440, 1024 and 390, light
  and dark: top of page with sidebar, verdict band, factor cards, one dense panel with statistics
  off and on, the mobile drawer. No image generator is available, so the HTML prototype plus
  screenshots is the visual target. **Gate: the owner approves the look before Stage 2.**
- **Stage 2 (React port):** agents A to F plus the performance and world-beta agents (DV9).
- **Stage 3 (integration and review):** V10, V11, V12; then one pull request for the owner.

---

## DV11. Open questions for the owner

1. **Light sign pair under deuteranopia.** `#0A7A55` and `#C23345` separate by 6.6 OKLab units,
   under the rev 2 floor of 8 (design M.3). Meaning is also carried by position, sign and words.
   Recommended: darken the green slightly at the Stage 1 gate.
   **Decided 2026-11-19:** the owner has no preference, so the recommendation is applied. The
   light `--pos` is now `#007862` (was `#0A7A55`): 27.2 normal, 8.9 protanopia, 8.5
   deuteranopia, 31.3 tritanopia (floor 8), and every text pair stays at least 4.5:1 (on white
   5.44, on the page 5.02, on its tint 4.88). Design M.3 holds the numbers and the method.
2. **Schema version 5 for an additive field** (DV2.1) departs from SC5's own rule. Recommended:
   accept, because it marks files that could carry a name.
   **Decided 2026-11-19:** no bump. `SCHEMA_VERSION` stays `"4"`; `data.security`, `performance`
   and `world_beta` are additive and optional (SC5); the colophon keeps "schema v4".
3. **`unavailable` status for `world_beta`** is not an M0.7 value. Recommended: use `failed` with
   the reason "The world fund's prices could not be fetched.", keeping the status set closed.
   **Decided 2026-11-19:** `world_beta` uses the existing M0.7 statuses only. A fetch failure
   with no cache gives `failed` with that reason; a stale cache gives `ok` with the note "ACWI
   data ends {date}"; and ACWI is refreshed incrementally on every ticker load (owner
   instruction). See DV2.6.
4. **Verdict headline at 28 px under 600 px** instead of 36 to 40 (design L.1). Recommended:
   accept; 36 px fills the first phone screen.
   **Decided 2026-11-19:** the owner has no preference; accepted as written (28 px under 600 px).
5. **Market card on its own row** to keep at most four cards per row (design L.3). Recommended:
   accept.
   **Decided 2026-11-19:** the owner has no preference; accepted as written.
6. **Dark theme ignores the OS setting** (plan default). Confirm at Stage 1.
   Decided 2026-11-19: the owner said "skip dark theme". Dashboard v2 ships light only: no
   "Dark theme" switch, no `theme` URL parameter, no dark token set, and the OS setting is ignored.
   This supersedes every dark-theme item elsewhere in this spec and in design rev 3.
7. **Company name fallback:** when Yahoo throttles the metadata read, the header shows the ticker
   only, with no error. Recommended: accept (plan default).
   Decided 2026-11-19: accepted by the owner.
8. **Residual verdict copy G2** in R4.8 says "check the Exposures tab"; the page has no tabs. The
   dashboard shows its own outcome line (DV4.9) but the body still shows the R4.8 copy. Recommended:
   the methodology owner changes "tab" to "section" in R4.8.
   **Decided 2026-11-19:** yes. The G2 copy now says "check the Exposures section" in R4.8, the
   test oracle, the verdict message in `analytics/residual.py` and its test.

## Owner decisions

On 2026-11-18 the owner answered as follows. These override any earlier text in this file and in
`docs/specs/dashboard.md` where they differ.

1. **Sidebar = controls plus section navigation.**
2. **The regression formula is removed.**
3. **Dashboard first, static report later** (epic 18).
4. **Company name added** (with exchange and currency), from one Yahoo metadata read.
5. **Stack unchanged:** plain CSS tokens, no Tailwind or shadcn/ui, no new runtime dependency.
6. **Historical performance** added as the optional section `performance` (definitions DV2.5).
7. **A quick world beta** against the ACWI fund as a stand-in for the MSCI All Country World index,
   as the optional section `world_beta` (DV2.6).
8. **Fintech-tool palette and IBM Plex Sans** (design rev 3, M and B), with the density rules of
   design C rev 3, and a dark navy icon-and-label sidebar after the owner's references (Altoo and
   an investment analytics tearsheet tool).
9. **10Y range preset** (owner, 2026-11-19): the range control offers 3Y, 5Y, 10Y and Full history,
   in that order. This extends the owner decision of 2026-11-18 in `docs/specs/dashboard.md` (3Y, 5Y and
   Full history only). Code: `RangePreset` and `RANGE_PRESETS` in `backend/factordesk/report/schema.py:459`,
   the start-date rule in `backend/factordesk/api/ranges.py` (ten calendar years back, same
   29 February rule as 3Y and 5Y), the `range` URL value in `frontend/src/state/url.ts`, the
   segmented control, the availability reason when the history is shorter than ten years, the
   OpenAPI types, and the tests of each. It ships with ticket V4 (controls in the sidebar).

---

## Appendix A. Example sentences (computed from the mock fixture)

Produced on 2026-11-18 by a reference implementation of DV4 (a short Python script run on
`backend/factordesk/tests/fixtures/mock_report.json` and edited copies of it); V4's unit tests must
reproduce these strings exactly. The mock is synthetic SPY data: `regression` 0.998 market beta,
SMB −0.141 and RMW +0.027 reliable, HML and CMA noise, alpha +0.81% a year (noise), R² 0.9987,
quality gate fired, audit status `warnings`.

### A.1 Mock fixture as committed

- Headline: "SPY moves with the market (about one-for-one), leans toward large companies and highly
  profitable firms, and shows no reliable return beyond its exposures." Hedge: "Its closing prices
  look out of step with the factor data, so the share the model explains is probably understated."
- Tile, return beyond its exposures: "+0.8% a year", "Not distinguishable from zero".
- Tile, how much the model explains: "99.9%", "of the day-to-day variation in SPY's return; 0.1% is
  specific to SPY. Probably understated: closing prices look out of step with the factor data".
- Tile, stock-specific risk: "0.6%", "a year of swings the factors do not explain, out of 17.0% in
  total. Probably overstated: closing prices look out of step with the factor data".
- Card, market: Positive; Significant; "Moves with the market: on average, a 1% market move came with
  a 1.00% move in SPY."
- Card, size: Negative; Significant; "Leans toward large companies: SPY tended to do better when
  large companies beat small companies, and worse when they lagged."
- Card, value: Not clear; Not significant; "No clear tilt toward value stocks or growth stocks over
  this range."
- Card, profitability: Positive; Significant; "Leans toward highly profitable firms: SPY tended to do
  better when highly profitable firms beat weakly profitable firms, and worse when they lagged."
- Card, investment: Not clear; Not significant; "No clear tilt toward firms that invest
  conservatively or firms that invest aggressively over this range."
- Price: "With dividends reinvested, SPY rose 30.5% over the analysed range (8 Aug 2024 to 30 Sep
  2026). The last 32 price days are charted but not analysed."
- Exposures: "Three of the five exposures are clear (market, size and profitability); value and
  investment are not distinguishable from zero."
- Return sources: "Market exposure accounts for most of the 12.6% a year SPY earned above cash
  (+11.6%)."
- Risk sources: "Market exposure drives 99.4% of SPY's day-to-day risk; 0.5% is specific to SPY."
- Over time: "In 80% of the 252-day windows the market beta was between 0.99 and 1.01. The value,
  profitability and investment exposures spent long stretches on both sides of zero."
- Data and audit: "The price audit flagged 1 unusual item; none stops the analysis. 559 trading days
  analysed, 1 excluded."
- Regression detail: "Three of the five betas are significant after allowing for testing five at
  once; the return beyond the exposures is not distinguishable from zero. Because the quality gate
  fired, a term counts as significant only when the 5-day estimate agrees."

### A.2 Edge case 1: all five factors not significant

Edit: every factor tag set to `noise`; gate set to not fired.

- Headline: "SPY shows no reliable link to the market, has no clear tilt toward size, value,
  profitability or investment, and shows no reliable return beyond its exposures."
- Card, market: Not clear; Not significant; "No reliable link to the market over this range."
- Card, size: Not clear; Not significant; "No clear tilt toward small companies or large companies
  over this range."
- Exposures: "None of the five exposures is distinguishable from zero over this range."
- Return sources: "Market exposure accounts for most of the 12.6% a year SPY earned above cash
  (+11.6%), but that exposure is not distinguishable from zero."
- Regression detail: "None of the five betas is significant after allowing for testing five at
  once; the return beyond the exposures is not distinguishable from zero."

### A.3 Edge case 2: audit errors present

Edit: `audit_status` set to `errors` and one error finding added (gate still fired).

- Headline: "The price audit found errors in SPY's prices, so these results are not interpretable
  until the errors are explained. Taken at face value, SPY moves with the market (about
  one-for-one) and leans toward large companies and highly profitable firms."
- Every outcome tile note: "Not interpretable: the price audit found errors".
- Card, market: Positive; Not interpretable; "Moves with the market: on average, a 1% market move
  came with a 1.00% move in SPY. Unconfirmed: the price audit found errors."
- Data and audit: "The price audit found 1 error; the results above are not interpretable until it
  is explained. 559 trading days analysed, 1 excluded."

### A.4 Edge case 3: negative alpha that is significant

Edit: `alpha_annual` −0.034, `alpha_tag` `reliable`; gate set to not fired.

- Headline: "SPY moves with the market (about one-for-one), leans toward large companies and highly
  profitable firms, and earned 3.4% a year less than its exposures explain over this range."
- Tile, return beyond its exposures: "−3.4% a year", "Distinguishable from zero at the 5% level".
- Regression detail: "Three of the five betas are significant after allowing for testing five at
  once; the return beyond the exposures is distinguishable from zero."

### A.5 Extra: amplified market, growth tilt, positive significant alpha

Edit: market beta 1.42; HML −0.31 and `reliable`; alpha +0.052 `reliable`; gate not fired.

- Headline: "SPY amplifies market moves (about 1.42 times as much), leans toward large companies,
  growth stocks and highly profitable firms, and earned 5.2% a year more than its exposures explain
  over this range."
- Card, market: "Amplifies the market: on average, a 1% market move came with a 1.42% move in SPY."
- Card, value: Negative; Significant; "Leans toward growth stocks: SPY tended to do better when
  growth stocks beat value stocks, and worse when they lagged."

### A.6 Performance and world beta (illustrative inputs, not in the fixture)

The fixture has no `performance` or `world_beta` section yet (V13 and V15 add fixture data). These
use made-up inputs to show the templates; V14 and V16 test them on the real fixture once it exists.

- Performance, inputs `cagr_annual` 0.1347, `vol_annual` 0.170, `sharpe` 0.74 (95% interval 0.05
  to 1.43, standard error 0.35), `max_drawdown` −0.084 from 19 Feb 2025 to 8 Apr 2025, recovered 27
  Jun 2025, span 8 Aug 2024 to 30 Sep 2026:
  - Tiles: "+13.5%", "Compound growth a year from 8 Aug 2024 to 30 Sep 2026, dividends reinvested";
    "17.0%", "How widely daily returns swung, scaled to a year"; "0.74", "Return above the factor
    file's risk-free rate, per unit of volatility. Above zero at the 5% level."; "−8.4%", "From 19
    Feb 2025 to 8 Apr 2025; back at the peak by 27 Jun 2025".
  - Panel: "SPY grew 13.5% a year over the analysed range; its largest fall was 8.4%, from 19 Feb
    2025 to 8 Apr 2025, and it was back at the peak by 27 Jun 2025."
- Performance, not recovered and Sharpe interval −0.40 to 0.90 (inputs `cagr_annual` −0.062,
  `sharpe` 0.25, `max_drawdown` −0.412 from 10 Feb 2021 to 12 Oct 2022, recovery null):
  - Sharpe note: "Return above the factor file's risk-free rate, per unit of volatility. Cannot be
    told apart from zero."
  - Largest fall note: "From 10 Feb 2021 to 12 Oct 2022; not recovered by 30 Sep 2026".
  - Panel: "ZM shrank 6.2% a year over the analysed range; its largest fall was 41.2%, from 10 Feb
    2021 to 12 Oct 2022, and it had not recovered by 30 Sep 2026."
- World beta, intervals overlap (inputs `beta` 0.91, 95% interval 0.80 to 1.02; `us_beta` 0.88,
  0.78 to 0.98; 1,254 days, 1 Oct 2021 to 30 Sep 2026):
  - Tile: "0.91", "Against world stocks, with the ACWI fund standing in for the index; about the
    same as its US market beta of 0.88".
  - Panel: "Against world stocks, ZM's beta was 0.91 over 1 Oct 2021 to 30 Sep 2026 (1,254 days),
    about the same as its beta against the US market on the same days (0.88)."
- World beta, intervals apart (inputs `beta` 0.95, 0.93 to 0.97; `us_beta` 1.00, 0.99 to 1.01):
  - Tile: "0.95", "Against world stocks, with the ACWI fund standing in for the index; lower than
    its US market beta of 1.00".
- World beta, `insufficient_data` with 180 overlapping days: tile "n/a", "Too few days overlap with
  the world fund: 180, at least 252 needed".
