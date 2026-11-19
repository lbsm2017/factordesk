# Change log

Newest first. This log records changes to the knowledge base (the `wiki/` folder), not to the code.

## Open questions

- May sample reports built from Yahoo data be committed to the public repository? Not yet decided (2026-11-18).
- The README has a stale status line and no not-affiliated note. The owner plans to rewrite the README later (2026-11-18).

## 2026-11-19 (VaR and CVaR)

- The owner added VaR and CVaR for every mode and chose the methods and levels after a research round. Added [the decision page](decision-var-and-cvar.md), section D of the research notes and epic E7 in the spec.

## 2026-11-19 (next stage: track records and portfolios)

- The owner approved the next stage: track-record uploads, an SAA-tree portfolio backtest, a five/six-factor switch with an alpha strip, and a macro section. Added five decision pages, an index section and the research notes. The monthly-uploads page amends the daily-returns decision; it does not replace it.

## 2026-11-18 (performance metrics)

- The owner asked for the stock's own annualised return, volatility, Sharpe ratio and maximum drawdown in the report. Added [the decision page](decision-performance-metrics.md) and an index entry. The section is built on `feat/performance` and not yet independently validated.
## 2026-11-19 (world beta, after validation)

- Updated [the world beta decision page](decision-world-beta.md) after the independent validation: names aligned with the dashboard spec, one short attempt when a cache exists, late dividends and a monthly full download, no alpha t on an exact fit, audit errors only inside the overlap fail the section. "Many non-US stocks" stays (MSCI ACWI factsheet, 30 October 2026: United States 64.63%).

## 2026-11-19 (world beta)

- Added [the world beta decision page](decision-world-beta.md): a quick beta against the iShares MSCI ACWI ETF (a stand-in for the MSCI ACWI index, which has no free daily data), shown next to the US market beta on the same days. Rejected: MSCI index data, a global factor model, a Dimson correction. The ACWI price cache is refreshed incrementally on every report build (owner instruction, 2026-11-18). Built on `feat/world-beta`; not validated yet.
## 2026-11-18 (dashboard v2 specification)

- Added [Dashboard v2: outcome first with a sidebar](decision-dashboard-v2.md) from the owner's answers of 2026-11-18 (sidebar holds controls and section links, formula removed, dashboard first, company name, stack unchanged, performance and world beta sections, fintech-tool palette and IBM Plex Sans). Specified on branch `feat/ui-v2-spec` in `docs/specs/dashboard-v2.md` and `docs/design/report-design.md` revision 3 (commits `dabbff7`, `07d77a7`). Nothing is built; the look waits for the owner's approval of the prototype.

## 2026-11-18 (nightly slow tests)

- The owner approved a nightly GitHub Actions workflow for the slow and live tests. Added [the decision page](decision-nightly-slow-tests.md). The workflow has not yet run on GitHub.

## 2026-11-18 (bibliography)

- References verified: 63 bibliography entries, each checked against Crossref or arXiv (58, by the new script) or by hand against the page or file (5). Of 11 items first listed as unverified, 4 are resolved with a source, 2 partly, and 5 have no source (listed with file and line in the references page). See [references](../docs/references.md), [references.bib](../docs/references.bib) and the rule in [no citation without verification](decision-citations-and-verification.md).
- Findings: Chung (2024) is now published (Critical Finance Review 15(2), 133-155); the Ken French site states a copyright notice and no terms of use or citation request, although three wiki lines say the library asks for both (not changed here); Yahoo's own help page does describe its adjusted close as following CRSP standards; the Newey-West lag rule's attribution to the 1994 paper could not be confirmed.
- Added `scripts/check_references.py` and `CITATION.cff`.

## 2026-11-18 (owner re-rank)

- Rank 7 (one-shot install and run) moved to very later. The work is built and stays in PR #1; only the release is deferred. See [the roadmap](../docs/ROADMAP.md#changes-in-this-update-update-2).

## 2026-11-18 (roadmap update 2)

- Roadmap update 2: PR #1 open with CI green, the SPY hardening, rolling speed-up conditions and schema contract marked Done, three feature agents resumed, confidence re-scored, a nightly workflow proposed (not ranked). See [the roadmap](../docs/ROADMAP.md#changes-in-this-update-update-2).
## 2026-11-18 (shrunk betas)

- Added [Shrunk betas](decision-shrunk-betas.md): a second, labelled beta pulled toward a typical stock, with power statements; ordinary betas stay primary. Built on branch `feat/shrunk-betas` (as of commit `b1331d8`, not merged); status Decided-pending-implementation until the independent validation of `docs/validation/shrunk-betas-handoff-2026-11-18.md` passes. Owner decision of 2026-11-18 recorded: download the four portfolio files and keep them fresh with the factor data.
## 2026-11-18 (Kalman betas, after validation)

- Updated [Kalman-filter betas as an extra line beside the rolling betas](decision-kalman-betas.md) after the independent validation: the drift-rate wording is corrected (the weight of a new day is about the square root of the rate), `ex_ante_betas` is dropped from the section (owner decision, section now about 1.45 MB), and the hook degrades to a failed section on any error. Earlier statements on the page are marked superseded, not rewritten.

## 2026-11-18 (Kalman betas)

- Added [Kalman-filter betas as an extra line beside the rolling betas](decision-kalman-betas.md) (Decided-pending-implementation) after the feature was built on branch `feat/kalman-betas` (stage 3, as of commit `4252e87`, not merged, not independently validated). The handoff for the validator is [docs/validation/kalman-betas-handoff-2026-11-18.md](../docs/validation/kalman-betas-handoff-2026-11-18.md): real SPY numbers, the payload question (`ex_ante_betas` repeats the beta series shifted by one day, about a fifth of the section) and open owner decisions.

## 2026-11-18 (residual alpha built)

- Updated `decision-residual-alpha-analysis.md` with an "As of commit 4518e38" block: the residual return panel is built in both renderers on branch `feat/residual-alpha`, not yet independently validated, owner choice 2 not implemented. The handoff for the validator is `docs/validation/residual-alpha-handoff-2026-11-18.md`.

## 2026-11-18 (owner ranking)

- The owner ranked 16 epics on 2026-11-18. The [priority ranking](../docs/ROADMAP.md#priority-ranking-owner-2026-11-18) is in the roadmap, and Now, Next, Later and Very later follow that order.

## 2026-11-18 (rolling precision)

- Added `decision-rolling-fast-path-precision.md` after the independent validation of the rolling speed-up: precision wording corrected, fast-path check tightened, start-date effect recorded.

## 2026-11-18 (one-shot install)

- Added the one-shot install path on branch `feat/one-shot-install` (as of commit `ce931c7`, not merged, not published): the wheel now ships the built dashboard, two bootstrap scripts (`scripts/install.sh`, `scripts/install.ps1`) pinned to a version argument, an "Install without cloning" section in `docs/dashboard.md` and an owner-run `docs/release-checklist.md`. Details and what was and was not verified are in `decision-python-and-uv-for-every-platform.md`.
## 2026-11-18 (SPY hardening closed)

- The roadmap item "Hardening of the SPY slice" is Done. Every validation finding has a row in [docs/validation/spy-hardening-closure-2026-11-18.md](../docs/validation/spy-hardening-closure-2026-11-18.md): 20 fixed before, 4 fixed on branch `fix/spy-hardening-closure` (audit errors mute the headline, `--start`/`--end` on the report command, min-max thinning of long series, a named cause when no return lines up), 5 deferred with reasons. One wording error found during the closure was fixed: the gate summary now says residual volatility is overstated, not understated.
- Owner decisions still open from the closure: non-USD tickers (warn or refuse, M16 question 2), and adopting the variance-stability check and keeping the gate thresholds after the panel calibration.
- Updated [SPY timing noise and the quality gate](decision-spy-timing-noise-and-the-quality-gate.md) to Decided, with facts as of commit `4c1cb7c`.
## 2026-11-18 (schema v3 contract)

- Added [One contract for the five new report sections](decision-schema-v3-contract.md): where fragility, lead-lag, Kalman, shrunk betas and residual alpha plug into the report, so the four statistical features can be built in parallel. Full contract: `docs/specs/schema-v3-contract.md`.

## 2026-11-18 (dashboard built)

- The dashboard was built as tickets T1 to T10 of `docs/specs/dashboard.md`, all on branch `feat/report-ui-feedback` (25 commits ahead of `dev` as of commit `f36255e`; nothing merged to `dev` yet). T1 API skeleton `5ef6922`, T2 report endpoints `d958ebc`, T3 frontend scaffold `2df0bff`, T4 controls and URL state `380694f`, T5 to T8 panels (`b6d5472`, `534996b`, `b45d6de`, `10ed53c`), T9 serve command `afefd9a` with static serving `32c04f0`, T10 fake backend, browser smoke test and CI `9ae81a9` and `f36255e`. A batch price download (`deca962`) and the reduction of range presets to 3Y, 5Y and Full history (`96f0b2f`) landed on the same branch.
- Pending as of `f36255e`: the T11 design and accessibility review, a smoke test on live Yahoo data, and peer comparison using the batch price fetch. Three follow-up branches (CI action pinning, frontend bundle split, real-data smoke) were started from `f36255e`; none had commits of its own yet.
- Added the runbook [docs/dashboard.md](../docs/dashboard.md) and updated [dashboard server and interface](decision-dashboard-server-and-interface.md) with facts as of `f36255e`. The roadmap moved the dashboard from Next to Now.

## 2026-11-18 (parallel price downloads)

- Added [parallel, throttled price downloads](decision-parallel-throttled-price-downloads.md) after the owner asked for chunked, parallel Yahoo downloads with care over throttling. Status Decided-pending-implementation until merged. No Yahoo limit is claimed: the repo records none as published.

## 2026-11-18 (dashboard)

- Added [dashboard server and interface](decision-dashboard-server-and-interface.md) after the owner approved building it. Spec: `docs/specs/dashboard.md`. Dropped Tailwind and shadcn/ui, dropped the YTD and 1Y chips (the pipeline needs 504 days).
- Static report ported to design revision 2 (commits `fabd702`, `d0cacbb`); API skeleton added (`5ef6922`).

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

## 2026-11-18 (integration)

- Shrunk betas and Kalman betas merged into `integrate/features` (stacked on PR #1); both validated, not merged to prod. Residual alpha is merged later.

## 2026-11-18 (after PRs #1, #2 and #3 merged into dev)

- `docs/ROADMAP.md` updated (update 3): ranks 1, 8, 12 and 14 are Done on `dev`, not on `prod`; the nightly workflow is merged but has not run on GitHub; three new tickets (currency check N1, browser and accessibility pass N2, Kalman screen-reader strings N3) and an open-items list added.
- The nightly `slow` job now sets `FACTORDESK_KB_REPS` to 200 (`.github/workflows/nightly.yml`, `wiki/decision-nightly-slow-tests.md`). Not verified until it runs on GitHub.

## 2026-11-19 (integration of the dashboard v2 branches)

- Company name and currency refusal, performance, world beta, the dashboard v2 specification and the design prototypes merged into `integrate/ui-v2`. Not merged to dev.
- The schema version stays at 4: the `performance` and `world_beta` sections and `data.security` are additive optional fields (contract SC5). The "5" that the security branch wrote was reverted; a version 4 file written before `data.security` still loads.
- `SECTIONS` and the section fields are listed in panel order: world beta (350), performance (450), then the five of the contract.

## 2026-11-19 (Europe benchmark for the world beta)

- The world beta section gets an optional `europe` block (IEUR, stand-in for MSCI Europe), computed by the same hook, cache and refresh as ACWI, with its own status. Schema version stays 4. `wiki/decision-world-beta.md` has the plain-English entry; the hand-off has the field names and live numbers (section 10).
- The static world beta panel moved from position 350 to 505, and the static header company line is now a sentence.
