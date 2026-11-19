# README fact-check, 2026-11-18

Date: 2026-11-18.
Object: `README.md` on branch `docs/readme-overview`, commit `d73df5c`, 358 lines,
sha256 `1d9e50020523c556711f50e5f07f87d9512fbd8c826fc1715160dfb2783dba2d`.
Reviewer: independent of the README's author. Read-only on every file except this one.

Standard: the README claims nothing the repository cannot back, does not overstate what is built,
validated or merged, and cites only verified references.

Severity: **blocker** (must not merge as is), **major** (must change for ACCEPT), **minor**
(should change; factual precision, consistency or form).

## Environment and what was run

- `uv sync --locked` in the worktree: "Resolved 61 packages, Checked 60 packages". The existing
  `.venv` was reused (not a clean clone). Interpreter: Python 3.13.14.
- `uv run factordesk --help`, `report --help`, `factors --help`, `factors refresh --help`,
  `factors status --help`, `serve --help`: all exit 0. Output quoted in section 1.
- Offline error paths run: `factors status` (no cache), `report SPY --start 2020-01-01 --end 2019-01-01`,
  `report SPY --start 2020-13-01`, `factordesk bogus`, `serve --port 8765` (page not built).
- Not run because they download: `report SPY/AAPL/BRK-B`, `factors refresh`, `serve --open` with a built
  page, `npm --prefix frontend ci`, `npm --prefix frontend run build`, `npm --prefix frontend test`
  (needs `node_modules`, which needs `npm ci`), `uv run pytest -m live`. Their behaviour was read
  from the code instead.
- `uv run pytest`: **541 passed, 205 deselected** (122 s). `uv run pytest -m slow`: **202 passed**
  (215 s). `uv run pytest --collect-only -q -m ""`: 746 tests; `-m live`: 3 tests (not run).
  `uv run ruff check .`: all checks passed. `uv run pyright`: 0 errors, 0 warnings.
- Network: available. Crossref answered for every DOI (section 6). `gh pr view 1` and
  `gh repo view` were read (no writes).

## 1. Commands

| Id | Severity | README line | Quote | Evidence | Suggested replacement |
| --- | --- | --- | --- | --- | --- |
| C0 | ok | 186-189, 216-224, 239-244, 255-256, 278-285 | "You should see the `report`, `factors` and `serve` commands"; options table; `serve` defaults; `factors status/refresh`; test commands | `--help` lists `report`, `factors`, `serve`; `report --help` lists `--out`, `--open`, `--json`, `--start YYYY-MM-DD`, `--end YYYY-MM-DD` with the same defaults as the table; `serve --help`: `--host` default 127.0.0.1, `--port` default 8000; `factors` has `refresh` and `status`; start after end gives `factordesk: error: --start 2020-01-01 is after --end 2019-01-01`, exit 2; summary line format matches `backend/factordesk/cli.py:283-289`; the sample numbers (n 8,474, R2 0.9673, factors through 2026-09-30) match `docs/reviews/real-data-smoke-2026-11-18.md` and `docs/data-source-comparison.md:200`; pytest, ruff, pyright pass as above; Node and npm minimums match `frontend/package.json:47-50` | none |
| C1 | minor | 158-160, 178-180 | "which also installs the right Python (3.12) for you"; "downloads Python 3.12 if it is missing" | `pyproject.toml`: `requires-python = ">=3.12"`; no `.python-version` file; the worktree `.venv` runs Python 3.13.14. uv picks any interpreter that satisfies `>=3.12`, not 3.12 specifically. Owner's retained text, unchanged by the author | "which also installs a suitable Python (3.12 or newer) for you"; "and downloads a Python 3.12 or newer if none is installed" |
| C2 | minor | 264-265 | "Every failure prints one line starting with `factordesk: error:`" | `report SPY --start 2020-13-01` printed three usage lines, then `factordesk report: error: argument --start: '2020-13-01' is not a date in the form YYYY-MM-DD` (exit 2). Command-level errors from `cli.py:91` do start with `factordesk: error:`. Owner's retained text | "Every failure ends with one line containing `error:` that says what to do (usage errors print the usage first), and the exit code tells scripts what kind of problem it was:" |
| C3 | minor | 271 | "2 \| Wrong command or option" | `cli.py:388-405`: `serve` also returns 2 for an invalid port, a page that is not built, and a busy port. Observed: `serve --port 8765` gave "the dashboard is not built; run 'npm --prefix frontend run build' first, or use --dev (API only)", exit 2. Relevant now that the author added `serve` | "\| 2 \| Wrong command or option, or `serve` cannot start (page not built, port in use) \|" |
| C4 | minor | 285 | "Frontend checks: `npm --prefix frontend test`." | `frontend/package.json:13`: `"test": "vitest run"`; it needs `frontend/node_modules`, absent in a fresh checkout, so `npm --prefix frontend ci` must run first | "Frontend checks, after `npm --prefix frontend ci`: `npm --prefix frontend test`." |
| C5 | minor | 242 | "and is built once" | `cli.py:393-399` serves `frontend/dist`; a stale build is served without warning after a `git pull` that changes the frontend | "and is built once (build again after pulling frontend changes)" |

## 2. Method statements

| Id | Severity | README line | Quote | Evidence | Verdict / replacement |
| --- | --- | --- | --- | --- | --- |
| M1 | ok | 53-56 | "fitted by OLS on daily excess returns over the days where prices and factors overlap" | `docs/methodology.md:236` (M3.1), `:213-226` (M2 alignment and exclusions); `analytics/sample.py` | supported |
| M2 | ok | 59-60 | "Newey-West HAC standard errors (Bartlett kernel, lag `floor(4 (m/100)^(2/9))` for `m` observations), normal p-values" | `docs/methodology.md:65-72`; `analytics/regression.py:5-7, 52-53, 114` | supported |
| M3 | ok | 61-62 | "The five betas form one family corrected with Benjamini-Hochberg at 5%. Alpha is a single test at 5%" | `docs/methodology.md:80, 87` (F1, m = 5), `:97`; `analytics/regression.py:231` (`fdr_bh`). Not stated: `m` falls when a beta cannot be tested (`:84`) | supported |
| M4 | ok | 64 | "Each point uses only the previous 126 or 252 trading days ending on that date." | `docs/methodology.md:324, 328`, `:43-47` (window includes row t); `analytics/rolling.py:33` | supported |
| M5 | ok | 65-67 | "Return contributions are annualised arithmetic means ... sum to the total. Risk contributions are Euler shares of variance ... idiosyncratic share is `1 - R-squared`" | `docs/methodology.md:344-345` (M6.1), `:377` (M7); `analytics/attribution.py:155-162` | supported |
| M6 | ok | 69-74 | gate: "below -0.2 with a robust z below -4 ... 5-day-block estimate ... reliable only if the daily and the 5-day tests both reject ... checked on five S&P 500 products only" | `docs/methodology.md:294, 297, 300-302`; `analytics/diagnostics.py:58-60, 246-248`; audit on every report: `pipeline.py:746` | supported |
| M7 | ok | 231-232 | "about two years of daily history that overlaps the factor data; shorter histories are refused" | `docs/methodology.md:105, 226` (n >= 504); `analytics/sample.py:38`; `cli.py:238-243` message "(about two years)" | supported |
| M8 | minor | 106 | "Claims are called significant only after correction." | `docs/methodology.md:97`: alpha, 5-day alpha and residual diagnostics are single tests at nominal 5%, not corrected; README line 62 says so itself | overstated. "Betas are called significant only after Benjamini-Hochberg correction; alpha is a single, uncorrected test at 5%." |
| M9 | minor | 127 | "Betas are estimated over the whole window and describe that window." | Rolling betas (lines 37, 64) are not whole-window | imprecise. "Full-sample betas are estimated over the whole window and describe that window." |
| M10 | minor | 129 vs 250 | "with a lag of a month or more" vs "with a lag of about a month" | `docs/methodology.md:169` "typical one-month publication lag"; on 2026-11-18 the file ended 2026-09-30 (49 days) | inconsistent. Use "a month or more" in both places |
| M11 | minor | 131-132 | "Yahoo's SPY closes before about 2009 carry a transient timing error, which is why SPY's R-squared is 0.967 and not higher." | `docs/validation/spy-slice-validation.md:228, 233` (R2 0.9673 full, 0.9950 from 2010), section 3.3; `docs/data-source-comparison.md:55-64, 170`: whether the noise is a Yahoo property or a property of SPY's consolidated close is unanswered (H1 abandoned) | partly overstated. "SPY's closing prices from Yahoo before about 2009 carry a transient timing error (whether other vendors share it is untested). It lowers SPY's full-sample R-squared to 0.967; from 2010 it is 0.995. The gate flags it; it does not remove it." |
| M12 | minor | 133-134 | "Non-US tickers are not supported." | `pipeline.py:116-119`: a non-US ticker still gets a report with a general caveat, and "this version does not check the ticker's currency"; closure F13 deferred | imprecise. "The factors are US factors in USD. A non-US ticker still gets a report, with a general caveat but no currency check; whether to warn or refuse is an open owner decision (F13 in the hardening closure)." |
| M13 | minor | 136-137 | "come from an unofficial route, and the adjusted close is not reproducible from the stored inputs" | `docs/validation/spy-slice-validation.md:184` (F8: "not reproducible across downloads"); `wiki/decision-prices-from-yahoo-with-adjusted-close-care.md:31-32` (unofficial; two same-day downloads differed by up to 1.8e-4); closure D-3 (no price hash) | wording. "...come from an unofficial route, and the adjusted close can differ between two downloads (up to 1.8e-4 seen); the report stores no hash of the price input." |

## 3. Method status versus roadmap and git

Git facts (2026-11-18): `docs/readme-overview` = `feat/report-ui-feedback` (`ca66dc1`) + 5 commits.
`dev` and `prod` are at `948dc5b`. PR #1 (`feat/report-ui-feedback` into `dev`) is OPEN, not merged
(`gh pr view 1`). Not ancestors of HEAD: `feat/residual-alpha` (13 commits ahead), `feat/shrunk-betas`
(17), `feat/kalman-betas` (11) and their `-static-panel` and `-react-panel` branches (6 to 8 each).
No fragility or lead-lag branch exists. In this branch the five section hooks return `None`
(`backend/factordesk/section_hooks/{residual_alpha,shrunk,kalman,fragility,lead_lag}.py`) and
`report/schema.py:60` sets `SCHEMA_VERSION = "4"`.

| Id | Severity | README line | Quote | Evidence | Suggested replacement |
| --- | --- | --- | --- | --- | --- |
| S1 | ok | 79, 85-87 | "'Not in this branch' means the report has an empty slot for the section (schema version 4) and no analytics behind it." | as above | supported; the table does not imply the feature branches ship |
| S2 | minor | 20-21 | "the SPY slice, the offline report, the CLI and the dashboard are built" | PR #1 open, not merged into `dev`; `docs/ROADMAP.md:14-15` "In review" | "Status (2026-11-18): the SPY slice, the offline report and the CLI are built; the dashboard is built and in review in PR #1, not yet merged into `dev`; the newer analytics sections are not built (see [Method status](#method-status))." |
| S3 | minor | 84 | "run against live Yahoo data for one ticker only" | `docs/reviews/real-data-smoke-2026-11-18.md:3`: SPY, plus "One extra Yahoo call ... for QQQ" | "Tested against a fake backend; smoke-tested on real data for SPY, plus one QQQ request ([review](docs/reviews/real-data-smoke-2026-11-18.md))" |
| S4 | minor | 85-86 | "analytics in progress on a feature branch"; "both in progress on feature branches" | git: the feature branches also carry static and React panel work. `docs/ROADMAP.md:146-147` ("None has commits yet") is contradicted by git; the README understates, it does not overstate | optional: "in progress on unmerged feature branches (analytics and panels)" |
| S5 | minor | 78, 88 | "from docs/ROADMAP.md"; "Dominant-factor shading ... not scheduled or later" | `docs/ROADMAP.md:129-130` lists cointegration, drift alerts and regime betas as not scheduled; dominant-factor shading is not in the roadmap (only `docs/PLAN.md:7, 101-104`) | "[Methodology](docs/methodology.md) M8 to M11; drift alerts, regime betas and cointegration are listed as not scheduled; shading is not on the roadmap" |
| S6 | minor | 78, 82, 85-87, 332, 335 | "for this branch"; "Not in this branch" | Once merged, "this branch" no longer names anything | "Not merged" in the status column, and line 78: "As of 2026-11-18, from docs/ROADMAP.md and git. 'Not merged' means the report has an empty slot ..." |
| S7 | minor | 296 | "Specifications of the features not yet in the report" | `docs/specs/` also holds `dashboard.md`, `schema-v3-contract.md` and `handoff-statistical-features.md` | "Feature specifications: dashboard, schema contract, and the sections not yet built" |

## 4. Scientific rigour

| Id | Severity | README line | Quote | Evidence | Suggested replacement |
| --- | --- | --- | --- | --- | --- |
| R1 | **major** | 96-99 | "For any new statistic, the claim, the null, the exact test and the result that would count against it are written down first, and entered in the append-only test registry before the first run." | `docs/research-protocol.md:11-18` states this as a checklist rule. `docs/registry/tests.jsonl` (20 lines, all `H-001`): T-20261118-001 to -013 are "Inspection run[s] ... before the gate rule was written"; -014 (the rule) is "Written AFTER the inspection runs"; -017 to -020 were "Computed while choosing the anchoring rule". The one rule registered so far was not pre-registered. The registry records this honestly; the README presents the rule as practice | "**Hypothesis before results (the rule).** The protocol requires the claim, the null, the exact test and the result that would count against it to be written down and entered in the append-only [test registry](docs/registry/tests.jsonl) before the first run; every run, including abandoned ones, is a registry line. The registry (20 lines on 2026-11-18) records that the quality-gate threshold was written after 13 inspection runs, so it is a documented heuristic, not a pre-registered test." |
| R2 | minor | 100-101 | "Sample size, first and last date, in-sample flag and status (CODING_STANDARDS.md, section 5)" | `CODING_STANDARDS.md:32-36` lists status, reason and `SampleInfo`; `report/base.py:85-95` (`SampleInfo`) has no in-sample flag; in-sample is a label (`report/base.py:39`, L-DESC) and a protocol item (`docs/research-protocol.md:70`) | "Sample size, first and last date, requested dates, excluded rows, factor vintage and status (CODING_STANDARDS.md, section 5); every panel is labelled in-sample." |
| R3 | ok | 103-105 | "A result dated `t` uses only rows dated `t` or earlier ... Static scans and perturbation tests enforce it" | `docs/methodology.md:35-41`; `tests/test_lookahead.py:120` (T102 perturbation), `:154` (T103 truncation), `:194, 229` (T104, T95/T99 static scans); `analytics/rolling.py:304` (`shift(1)`) | supported |
| R4 | ok | 107-108 | "about 18% a year at 20% residual volatility over 10 years" | `docs/research-protocol.md:130` (17.7%), `:134` | supported |
| R5 | ok | 109-112 | "headline numbers matched to about 1e-7 ... 17 deliberate bugs: 12 were caught ... 5 survived; the tests were then tightened at those boundaries" | `docs/validation/spy-slice-validation.md:18-20, 501-527` ("12 of 17 mutants caught, 5 survived"); `docs/validation/spy-hardening-closure-2026-11-18.md:47-52` (S1-S6 fixed with named tests). The mutants were not re-run after the fixes; the README does not claim they were | supported |
| R6 | minor | 113-114, 295 | "The tests are specified in advance"; "The tests, written before the code" | `docs/test-oracle.md:3` ("written 2026-11-18"); git history starts at `948dc5b`, which adds the oracle and the code together, so the order cannot be checked from history | unsupported by history. Line 113: "The tests are specified in a written oracle, with tolerances derived from standard errors"; line 295: "The tests and their tolerances" |
| R7 | minor | 117-119 | "Simulated data uses fixed seeds (test `k` uses `numpy.random.default_rng(20261118 + k)`), never the global generator." | `tests/fixtures/dgp.py:23, 38-39` (policy; "sweeps pass `seed`"); `docs/test-oracle.md:20-22` (sweeps use seeds 1 to 50); `tests/test_rolling_adversarial.py:76` (`default_rng(seed + 1000)`). No global `np.random.seed` found | mostly supported. "(policy: test `k` uses `numpy.random.default_rng(20261118 + k)`; seed sweeps use seeds 1 to 50)" |
| R8 | ok | 117-118 | lockfiles and `uv sync --locked` | `uv.lock`, `frontend/package-lock.json` exist; `.github/workflows/ci.yml:36, 69, 94` (`uv sync --locked`), `:58` (`npm ci`) | supported |
| R9 | ok | 121-123 | "Every source in the bibliography was looked up and checked by a script or by hand; what could not be checked is listed as unverified" | `docs/references.bib`: 52 entries, 52 with `verified`; `docs/references.md:600-627` (U1-U11); `scripts/check_references.py` | supported |
| R10 | ok | all | test counts | The README states no test count. Counted: 746 tests, 541 in the default run, 202 `slow`, 3 `live`; registry 20 lines | nothing to change |

Every file or folder the README links to exists (each path checked with `test -e`). In-page anchors
`#method-status` and `#tests-and-checks` match headings. Links of the form `[M3.1](docs/methodology.md)`
open the file, not the section (T3).

## 5. Data sources and licences

| Id | Severity | README line | Quote | Evidence | Suggested replacement |
| --- | --- | --- | --- | --- | --- |
| D1 | **major** | 146 | "Yahoo's terms and the yfinance notice limit use to personal and research use." | `docs/references.md:46-52`: the yfinance README says yfinance "is intended for research and educational purposes" (about the tool) and "the Yahoo! finance API is intended for personal use only"; Yahoo's terms forbid reuse "for any commercial purpose" and collecting data "using any automated means" without permission. No text grants research use; the sentence implies a permission the sources do not give | "Yahoo's terms forbid commercial use and collecting data by automated means without permission. The yfinance README says the Yahoo Finance API is 'intended for personal use only'. factordesk obtains no permission from Yahoo for you." |
| D2 | ok | 145 | "no terms page was found on 2026-11-18. We credit them." | `docs/references.md:36, 83-87`, U7 (`:613`) | supported; no redistribution is implied |
| D3 | ok | 148-151 | "Neither dataset is committed: `data/` and `.env` are gitignored" | `.gitignore:2-3` | supported |
| D4 | minor | 153-154 | no-affiliation statement | Present and consistent with `wiki/decision-project-name-factordesk.md:13`. yfinance is named in the README but not in the statement. (That wiki page, line 23, still says the README has no such statement; stale, not a README issue) | optional: "...not affiliated with, endorsed by or vetted by Yahoo, the yfinance project, Dartmouth College, Kenneth R. French or Eugene F. Fama" |

## 6. Key references

Crossref, live, 2026-11-18 (`https://api.crossref.org/works/<doi>`): HTTP 200 for all nine DOIs.
Authors, year, title, journal, volume and issue match README and `docs/references.bib` for all nine.
Start pages match. End pages match for six; for the three JSTOR DOIs (Newey and West, Vasicek,
Engle and Granger) Crossref gives only the start page, and the end pages rest on the bib's
RePEc check, which was not repeated here. Entry 3 (French Data Library) has no DOI; it matches
`frenchlibrary` in the bib.

| Id | Severity | README line | Quote | Evidence | Suggested replacement |
| --- | --- | --- | --- | --- | --- |
| K1 | ok | 311-338 | ten entries | as above | supported |
| K2 | minor | 321 | "Controlling the false discovery rate" | `docs/references.bib` (`benjamini1995`) and Crossref: "Controlling the false discovery rate: a practical and powerful approach to multiple testing" | use the full title |
| K3 | ok | 312-338 | roles: "The model implemented", "The HAC standard errors", "Lead-lag betas (specified, not built)" ... | Each line names the repository's use, not a finding of the paper; consistent with the "Used for" lines in `docs/references.md`. Lines 308-309 say verification does not cover the papers' content (consistent with U3, U5, U6) | supported |

## 7. Tone and form

| Id | Severity | README line | Quote | Evidence | Suggested replacement |
| --- | --- | --- | --- | --- | --- |
| T1 | **major** | 1-358 | 358 lines | Target 280 for a high-level README (owner request) | Move or cut about 80 lines, see the list below |
| T2 | minor | 111 | "review also injected 17 deliberate bugs: 12 were caught by the tests and 5 survived; the tests were then tightened at those" | 125 characters; the rest of the prose wraps at 100 | rewrap at 100 |
| T3 | minor | 55, 60, 62, 68, 73, 105 | `[M3.1](docs/methodology.md)` and similar | link to the file, not the section | add anchors, for example `docs/methodology.md#m31-model-and-estimates`, `#m05-inference-ols-with-newey-west-hac`, `#m06-multiple-testing-benjamini-hochberg`, `#m02-date-stamping-and-the-no-look-ahead-rule` (GitHub slug rule; rendering not checked) |
| T4 | minor | 46-48 | "A synthetic example (made-up numbers, not real data) is docs/samples/mock_report.html" | The file dates from `948dc5b` and shows an earlier layout (tiles "Alpha, annualised", "Window", "Data audit"; the renderer now uses "Alpha, a year", "Analysed range", `report/render_html.py:629-640`). It labels itself "MOCK DATA" only in its caveats | "A synthetic example of an earlier layout (made-up numbers, not real data) is ..." |
| T5 | ok | all | tone | No emoji, no non-ASCII characters, no marketing superlatives. "yet" (lines 32, 128, 296) is scoped; status lines carry a date. No personal names or emails, except the account name inside the clone URL (line 173, owner's text). The README makes no public or private claim; the repository is private on 2026-11-18 (`gh repo view`), so the clone command works only with access | none required |

Line budget (358 to about 280):

- Lines 304-338, Key references (35 lines): keep a 6-line pointer to `docs/references.md` with
  entries 1, 3, 4 and 5; the rest is already in `docs/references.md`. About -25.
- Lines 26-39, panel list (14 lines): one short paragraph; the panel order lives in
  `docs/design/report-design.md`. About -9.
- Lines 91-123, Scientific rigour (33 lines): one or two lines per practice, details behind the
  existing links. About -14.
- Lines 51-74, Method on one screen (24 lines): keep the equation and one line each for inference,
  correction, rolling, attribution and the gate; move the gate mechanics to the decision link. About -9.
- Lines 81-89, status table: merge the three "specified" rows for fragility, lead-lag and M8-M11
  into one row. About -3.
- Lines 340-345, How to cite: one line inside "Contributing, security and licence". About -4.
- Lines 41-49, "Two ways to read it": about -3.
- Owner's retained sections (156-285) are left as they are, apart from the factual fixes above.

## 8. Owner's retained sections (Setup, How to run it, Tests and checks)

Base: the committed parent (`5f47837`) holds the 60-line initial README, with no "How to run it"
section. The retained sections match the uncommitted `README.md` in the main checkout
(`feat/report-ui-feedback`, 138 lines, sha256 `3f61035f9b375cbd669bb3eb408f0bf5b2aab25d3402fe148ac2e5c7b6a3d05b`,
read only), so that copy is taken as the seed. `diff` of seed against `d73df5c`, limited to these
sections:

| Id | README line | Old text (seed) | New text | Factual fix? |
| --- | --- | --- | --- | --- |
| O1 | 189 | "You should see the `report` and `factors` commands." | "You should see the `report`, `factors` and `serve` commands." | yes: `--help` lists `serve` |
| O2 | 196 | "factordesk is a command-line tool for now; the dashboard comes later." | "factordesk is a command-line tool and a local dashboard." | yes for this branch (`serve` exists); PR #1 is not merged (S2) |
| O3 | 223-224 | (no rows) | `--start YYYY-MM-DD` and `--end YYYY-MM-DD` rows | yes: wording matches `report --help` |
| O4 | 234-244 | (no section) | "Start the dashboard": `npm --prefix frontend ci`, `npm --prefix frontend run build`, `uv run factordesk serve --open`; Node 26 / npm 12; `127.0.0.1:8000` | yes, supported by `frontend/package.json:8, 47-50` and `serve --help`; npm commands not run (network); see C3, C5 |
| O5 | 284-285 | "`uv run pytest -m live`." | adds "Monte Carlo and seed-sweep tests are marked `slow`; run them with `uv run pytest -m slow`. Frontend checks: `npm --prefix frontend test`." | yes: `pyproject.toml` markers; 202 slow tests passed; see C4 |
| O6 | removed | "## Run the API (once it exists)" with `uv run uvicorn factordesk.api.main:app --reload` | removed | yes: `api/main.py` has no module-level `app` (only `create_app`, line 23, and `create_dev_app`, line 41), so the old command would fail; `serve --dev` replaces it |

Unchanged retained text with factual problems: C1 (Python 3.12), C2 (one error line), C3 (exit 2).

## Verdict

**ACCEPT WITH CHANGES.** Blockers 0, major 3 (R1, D1, T1), minor 25 (C1-C5, M8-M13, S2-S7, R2,
R6, R7, D4, K2, T2-T4). The method statements, link targets, status of unmerged features and the
ten references hold up; the problems are one overstated practice, one licence paraphrase that
implies a permission, and length.

## Edits needed for ACCEPT

Required (majors and factual minors):

1. Lines 96-99: replace with the R1 text.
2. Line 146, Terms cell: replace with the D1 text.
3. Line 106: replace the first sentence with the M8 text.
4. Lines 131-132: replace with the M11 text.
5. Lines 133-134: replace with the M12 text.
6. Lines 136-137: replace with the M13 text.
7. Lines 20-21: replace with the S2 text.
8. Line 84, third cell: replace with the S3 text.
9. Line 88, third cell: replace with the S5 text.
10. Lines 100-101: replace with the R2 text.
11. Line 113 and line 295: R6 texts.
12. Line 321: full Benjamini-Hochberg title (K2).
13. Lines 158-160 and 178-180: C1 texts (owner's section; factual).
14. Lines 264-265 and 271: C2 and C3 texts (owner's section; factual).
15. Line 285: C4 text.
16. Shorten to about 280 lines along the line budget in section 7 (T1).

Optional: C5, M9, M10, S4, S6, S7, R7, D4, T2, T3, T4.

## What could not be checked

- Commands that download: `report` for SPY, AAPL and BRK-B, `factors refresh`, `serve --open` with a
  built page, `npm ci`, `npm run build`, `npm test`, and `pytest -m live` (3 tests). Read from code only.
- A clean-clone `uv sync`: the existing `.venv` was reused.
- The providers' live terms pages: the quotations in `docs/references.md` were taken as recorded there.
- End pages of the three JSTOR DOIs (Crossref gives start pages only); RePEc was not re-checked.
- The independent validation itself (the 1e-7 match and the mutant runs): taken from the validation
  document, not repeated; mutants were not re-run after the test fixes.
- Whether the test oracle was written before the code: git history cannot show it.
- Dashboard behaviour (range chips, custom dates, refresh) beyond the code and the smoke review.
- PR #1's CI status, and how GitHub renders the methodology anchors suggested in T3.
