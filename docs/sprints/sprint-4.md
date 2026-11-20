# Sprint 4: European investor complete, and a better "Factor it" experience

Dates: started 2026-11-20, right after approval
Status: closed on 2026-11-20. Release `v0.5.0` is pending the owner's merge of the release PR. The owner approved the plan on 2026-11-20.
Previous: [Sprint 3](sprint-3.md). Release target: `v0.5.0`.

## Context

Sprint 3 shipped the USD/EUR switch: returns, cash and factors can be shown in EUR. The factors are still the US Fama-French factors, converted to EUR. A EUR investor who holds European shares is measured against the wrong market, so the fits are weak.

On 2026-11-20 the owner chose the goal "European investor complete" for Sprint 4, and added one more item: a better look and feel from the moment the user presses **Factor it** until the report is on screen.

## Recap: what changes for the user

1. A **factor set switch (US | Europe)** next to the currency switch. Europe uses the Fama-French Developed Europe factors (five factors plus momentum). It works in USD and in EUR.
2. **Factor it feels fast and clear.** The user sees what is happening step by step (prices, factor data, models), the placeholder page matches the real report, and the panels appear in order. When the user runs again, the old report stays on screen, dimmed, until the new one is ready.
3. The **date ranges are right in EUR.** Today the range endpoint ignores the currency.
4. A short **"What EUR changes"** panel says what the EUR view does: conversion, cash rate, hedged bond lines.

## Sprint plan: Sprint 4

**Team:** at most 6 agent slots. A coordinator on Opus. The owner approves the checkpoint and the demo.

**Sprint goal:** a EUR investor can measure any report against European factors, and every run of Factor it shows clear progress from the click to a complete report.

### Capacity

| Resource | Available | Allocation | Notes |
|---|---|---|---|
| Agent slots | 6 × about 6 h | about 36 pts (1 pt ≈ 1 agent-hour) | Sonnet implements. Opus reviews the statistics and the API change. |
| Owner | 2 touchpoints | — | One checkpoint and the demo sign-off |
| **Committed (P0 + P1)** | | **24 pts, about 67%** | Below the 70–80% guide on purpose: Factor it will need design rounds. |
| Stretch (P2) | | 9 pts | |

### Sprint backlog

| Pri | Item | Pts | Model | Depends on |
|---|---|---|---|---|
| P0 | **S4-0 Checkpoint pack.**<br>• Europe factor method sheet: source files, start dates, conversion to EUR, risk-free rate.<br>• Mockups: the Factor it flow (click, progress, placeholder page, reveal, re-run), the factor set switch, the "What EUR changes" panel.<br>**The owner approves all of this before any build.** | 2 | coordinator + Sonnet | — |
| P0 | **S4-1 Ranges honour the currency.** The ranges endpoint takes `ccy`, and the cache key includes it. A test shows that the EUR and USD ranges differ when the FX series starts later. | 1 | Sonnet | — |
| P0 | **S4-2 Europe factor data.**<br>• Read the Ken French Developed Europe files: five factors and momentum, daily and monthly.<br>• Same cache, credit and stamp check as the US files.<br>• The factors are in USD, so the Sprint 3 formulas convert them to EUR. | 3 | Sonnet; Opus review | — |
| P0 | **S4-3 Factor set in the engine.**<br>• A `factor_set` choice (`us` or `europe`) for ticker, upload and portfolio reports.<br>• Every section that uses the Fama-French factors takes the chosen set: exposures, alpha strip, rolling, return and risk sources.<br>• Macro, energy and world beta stay as they are.<br>• The field is omitted for the US set, so the US report stays bit-identical, and the cache keys include the set. | 4 | Sonnet; Opus review | S4-2 |
| P0 | **S4-4 Factor set UI.** A US \| Europe switch next to the currency switch, a `fs=europe` URL parameter, and the report header names the set in use. | 2 | Sonnet | S4-0 |
| P0 | **S4-5 Factor it experience.**<br>• Real progress: the backend reports its steps (prices, FX, factor data, models, sections), and the page shows them as they happen. A cached report skips this and opens at once.<br>• The placeholder page matches the real panels and their order, including macro, energy and tail risk.<br>• The panels reveal smoothly, with no jump in the layout.<br>• Re-run: the old report stays, dimmed, with a thin progress bar, until the new report is ready.<br>• The button shows a busy state, and a clear error says what to do next.<br>• Reduced-motion users get no animation. | 6 | Sonnet; Opus review of the API change | S4-0 |
| P1 | **S4-6 "What EUR changes" panel.** A short side panel in the EUR view, as in the Sprint 3 mockup. | 2 | Sonnet | S4-0 |
| P1 | **S4-7 Dollar term in EUR: lag or lead.** A small spike, like the energy spike, then a decision. Your open question from Sprint 3. | 1 | Sonnet | — |
| P1 | **S4-8 Validation on real data.**<br>• Run European ETFs (VGK, EXSA.DE) in EUR with both factor sets. The Europe set must give the higher R².<br>• SPY must keep the higher R² on the US set.<br>• SPY in USD must stay identical to `v0.4.0`. | 2 | Sonnet | S4-3 |
| P1 | **S4-9 Wiki and record.** A new page, "decision-europe-factor-set", an update to the reference-currency page, and the sprint record. | 1 | coordinator | — |
| P2 | **S4-10 CHF cash on SARON** (SNB data portal), as for EUR cash on €STR. | 2 | Sonnet | — |
| P2 | **S4-11 TTF gas: data check only.** Find a free daily source. Build it only if one exists. | 1 | Sonnet | — |
| P2 | **S4-12 Dark theme.** Colour tokens for dark mode, plus a switch. | 4 | Sonnet | S4-5 |
| P2 | **S4-13 Hygiene.**<br>• Remove the dead code.<br>• Dependabot for CI.<br>• Remove the old worktrees.<br>• The energy sentence for very small sensitivities. | 2 | Haiku/Sonnet | — |
| P1 | **S4-14 Tail risk panel, compact** (added by the owner on 2026-11-20).<br>• Two groups, VaR and CVaR, with one row per level (VaR 95% and 99%; CVaR 95% and 97.5%).<br>• Two coloured bars per row on one shared scale: Historical, and Forecast. Forecast is the Cornish-Fisher estimate, or the Gaussian one when Cornish-Fisher is not available; a tag says which.<br>• One legend and one axis. The 90% band is an overlay on each bar.<br>• Gaussian and all three methods stay in "How this is computed".<br>• About half the height of the panel before. | 3 | Sonnet | S4-12 |

**Planned capacity:** 36 pts. **Sprint load:** 24 pts committed (67%), plus 9 pts stretch. On 2026-11-20 the owner added S4-14 (3 pts), so the committed load is 27 pts (75%).

**Cut order:**
1. S4-13.
2. S4-12.
3. S4-11.
4. S4-10.
5. S4-6.

S4-1, the Europe factors (S4-2 to S4-4) and Factor it (S4-5) are never cut.

### Execution order (RICE and MoSCoW, 2026-11-20)

The owner asked for easy wins first, no interruptions, and attention to dependencies. RICE = reach × impact × confidence ÷ effort (points). Reach is 0.5 to 3, impact is 0.5 to 3, and confidence is a percentage.

| Item | MoSCoW | R | I | C | E | RICE | Wave |
|---|---|---|---|---|---|---|---|
| S4-1 Ranges honour the currency | Must | 3 | 1 | 100% | 1 | 3.0 | 1 (easy win) |
| S4-4 Factor set UI | Must | 2 | 2 | 90% | 2 | 1.8 | 2 (needs S4-3) |
| S4-8 Validation on real data | Should | 2 | 2 | 90% | 2 | 1.8 | 2 (needs S4-3) |
| S4-7 Dollar term: lag or lead | Should | 1 | 1 | 80% | 1 | 0.8 | 1 (easy win) |
| S4-5 Factor it experience | Must | 3 | 2 | 70% | 6 | 0.7 | 1 backend and mockups, 2 frontend |
| S4-2 + S4-3 Europe factors | Must | 2 | 3 | 80% | 7 | 0.69 | 1 (long pole, starts first) |
| S4-11 TTF data check | Could | 1 | 1 | 50% | 1 | 0.5 | 1 (easy win) |
| S4-6 "What EUR changes" panel | Should | 1 | 1 | 90% | 2 | 0.45 | 2 |
| S4-12 Dark theme | Could | 2 | 1 | 70% | 4 | 0.35 | 3 (after the Factor it UI, same CSS) |
| S4-13 Hygiene | Could | 1 | 0.5 | 100% | 2 | 0.25 | 1 (small, and it must land before the Factor it UI touches the same files) |
| S4-10 CHF cash on SARON | Could | 0.5 | 1 | 80% | 2 | 0.2 | 3 |
| S4-14 Tail risk panel, compact (owner, added 2026-11-20) | Should | 2 | 2 | 90% | 3 | 1.2 | 3 (after the dark theme) |

The checkpoint is run without stopping: the coordinator approves the S4-0 mockups against the design direction, and the owner sees them at the demo, as in Sprint 3.

### Design decisions to approve with this plan

1. **Source of the Europe factors.** The Ken French Developed Europe files: five factors and momentum, daily and monthly. They start in 1990 and are published in USD.
2. **Which set is used.** The user picks the set; the default is US in both currencies. The right set depends on where the holding trades, not on the investor's currency. We do not choose the set automatically.
3. **Risk-free rate.** In USD the French one-month T-bill rate, as today. In EUR the euro cash rate (€STR), as in Sprint 3.
4. **What stays US.** Macro, energy and world beta keep their current inputs. Only the Fama-French sections change with the set.
5. **Progress is real.** The page shows the steps the backend has really finished, not steps timed by a clock. This needs a small API change (a run id plus progress updates). The plain report endpoints keep working as they are.
6. **Feel.** Calm, quick motion (about 150–250 ms) and no spinner, following the design direction already in use: navy sidebar, clear fonts, low density.

### Lanes (at most 6 at once)

| Lane | Sequence |
|---|---|
| A data | S4-1 → S4-2 → S4-10 |
| B engine | S4-3 → S4-8 |
| C Factor it, backend | S4-5 progress API |
| D Factor it, frontend | S4-0 mockups → S4-5 UI → S4-12 |
| E EUR UI | S4-4 → S4-6 → S4-7 → S4-11 → S4-13 |
| F review (Opus) | S4-2, S4-3, the S4-5 API |

Each lane works on its own `feat/` or `fix/` branch, in its own worktree `../factordesk-wt/<lane>`. The branch is pushed and then merged into dev with a merge commit, never fast-forwarded (owner rule, 2026-11-20). Schema and generated types: rebase before each merge and regenerate the types. Never hand-merge them.

### Risks

| Risk | Impact | Mitigation |
|---|---|---|
| The Europe files differ in format or lag the US files | Late or failed load | Use the same parser with a format test. Compare the stamps, and show a notice when the sets are out of step. |
| The progress API changes how the frontend calls the backend | Broken e2e, or a stuck page | Keep the old endpoints. The progress path is extra, with a time limit and a fallback to a plain request. |
| Animation makes the page feel slower | Worse, not better | Keep motion short and keep reduced-motion support. You review the flow at the checkpoint. |
| Factor set × currency × subject gives many combinations | Silent errors | Identity test (US set = today), cache keys with the set, and the S4-8 R² checks |
| Scope grows during the sprint | Overrun | Scope frozen at approval. The cut order applies. |

### Definition of done

- [ ] All 4 CI checks exist and pass on the branch before each merge into dev.
- [ ] Every change goes through its own branch and a merge commit.
- [ ] Opus review of every row marked for it, with the findings fixed.
- [ ] The golden ticker test is unchanged, and the US set in USD is bit-identical to `v0.4.0`.
- [ ] Tests:
  - the EUR ranges;
  - the Europe parser;
  - the set identity;
  - progress steps in order, and a cached report that skips them;
  - the re-run keeps the old report;
  - reduced motion.
- [ ] The owner signs off on the demo screenshots, including a short screen recording of Factor it. Then the dev→prod PR, which the owner merges, and the `v0.5.0` tag.

## Moved to later

- Track records: E2 upload hardening and E3 diagnostics. These are proposed as the Sprint 5 headline.
- Portfolio risk: E7b per-holding CVaR and E8 joint tail.
- Factor view: factor families, FF6 in the FF5-only sections, crowding-lite, the Settings module, and the specification curve (E9b).

## What shipped

| Item | What | PR |
|---|---|---|
| S4-0 Checkpoint pack | Mockups and a build spec for the Factor it flow, the factor set switch and "What EUR changes" ([docs/design/sprint-4](../design/sprint-4/)). The coordinator approved them, because the owner asked for no interruptions. | #39 |
| S4-1 Ranges honour the currency | `/ranges` takes `ccy` (and, later, `factor_set`), and both are in the cache key. | #36 |
| S4-2 Europe factor data | Ken French Developed Europe files: five factors and momentum (`WML` read as Mom), daily from 1990-07-02 and monthly from 1990-07. Same cache, credit and stamp check as the US files. | #38 |
| S4-3 Factor set in the engine | `factor_set` (us or europe) for ticker, ranges, HTML export, portfolio, upload and the stream endpoints. The US output is unchanged. Macro, energy and world beta keep the US factors on their own US-aligned sample for every set (design decision 4, fixed after the Opus review). | #43 |
| S4-4 Factor set UI | A US / Europe switch under Currency, `fs=europe` in the URL, a header pill, an analysis-bar item and a phone chip. | #50 |
| S4-5 Factor it experience | Backend: live progress steps over server-sent events. Frontend: busy button, step card, placeholder page in the real panel order, staged reveal, re-run with the old report dimmed, error page and re-run banner; a cached report opens at once. | #40, #46 |
| S4-6 "What EUR changes" | A right-hand dialog in the EUR view, with focus trap and Escape. | #50 |
| S4-7 Dollar term: lag or lead | A spike. A lead term fits better for VGK, EFA and IEF in EUR, but it is a negative shift, which the no-look-ahead rule forbids. Not built; the decision is the owner's. | #41 |
| S4-8 Validation | 6 of 7 checks pass on real data (see below). | #45 |
| S4-9 Wiki | New pages for the Europe factor set and the Factor it progress flow, and dated updates to the reference-currency and macro pages. | #47 |
| S4-10 CHF cash on SARON | SNB data portal, SARON from 1999-06-21. FXF is the fallback, used only when SARON fails. | #44 |
| S4-11 TTF data check | The only free daily source is Yahoo `TTF=F`, from 2017-10. Build it later (about 2 pts). | #42 |
| S4-12 Dark theme | Dark values for every colour token, a System / Light / Dark switch, no flash on load, and charts that redraw. Tests enforce AA contrast. | #49 |
| S4-13 Hygiene | Dead code removed, Dependabot, and the energy sentence for tiny moves. | #37 |
| S4-14 Tail risk, compact (owner, added mid-sprint) | Two groups (VaR, CVaR), with Historical and Forecast bars per level. Forecast is Cornish-Fisher, or Gaussian when Cornish-Fisher is n/a. One scale, one legend. About half the height of the old panel. | #51, #53 |
| Owner requests | The energy panel became one table with no captions. Macro row notes and sidebar notes moved to mouse-over tooltips. The EUR "factor dates left out" notice is shown once, and only when it touches the analysed window. | #52, #54 |
| CI | GitHub tests pull requests only. The nightly workflow and the CI badge were removed. | #48 |

## Owner decisions during the sprint (2026-11-20)

- The goal is "European investor complete", and a better Factor it experience was added. Track records move to Sprint 5.
- Multi-branch hygiene: every change lives on its own branch and merges into dev with a merge commit, never a fast-forward. A local `pre-push` hook enforces this.
- RICE and MoSCoW ordering, easy wins first, no interruptions, and at most 4 agents at once.
- GitHub Actions stopped because of a billing problem. The owner chose to pause GitHub CI, and the same gates ran locally with a `local-ci` status on each PR. The owner then decided that GitHub tests pull requests only, with no nightly run.
- Tail risk shows two figures per measure: Historical, and Forecast (Cornish-Fisher, or Gaussian when Cornish-Fisher is n/a).
- Open for the owner:
  - the dollar lead term (keep the no-look-ahead rule, allow a labelled lead, or use a fixing nearer the US close);
  - a failed re-run keeps the old report under a banner, which reverses an older rule.

## Validation (real data, 2026-11-20)

6 of 7 checks pass ([note](../research/sprint-4-validation.md), [script](../../scripts/validate_sprint4.py)):

- EXSA.DE in EUR: R² rises from 0.29 with the US set to 0.81 with the Europe set (FF6, daily).
- VGK daily fails (0.73 to 0.70). It is listed in New York, so it is timed against the US close. VGK monthly passes (0.63 to 0.98).
- SPY in USD: R² is 0.97 with the US set and 0.32 with the Europe set. The report is identical to dev before the sprint.
- The EUR market factor matches the hand-built formula exactly.
- The Balanced SAA portfolio ties out with the Europe set.
- World beta, macro and energy are identical for the US and Europe sets.

The localhost demo on real data covered:

- Factor it with live steps (XLE);
- EXSA.DE in EUR with the Europe set;
- the "What EUR changes" dialog;
- the dark theme, switched by a click;
- the phone width.

The demo found two problems: a duplicated, whole-history "factor dates left out" notice, and long sidebar captions. Both were fixed in #54 before the release.

## Retro

**Went well**

- Opus reviews caught a real design breach before merge: macro, energy and world beta moved with the factor set. The real-data validation then showed that the market factor fix alone was not enough, because the sample changed too.
- The streaming contract was fixed before the backend and frontend were built, so the two lanes ran in parallel and met cleanly.
- The local gate held while GitHub CI was down. It caught a contrast test, a flaky e2e race and merge conflicts that the targeted tests missed.

**Problems and fixes**

| Problem | Fix |
|---|---|
| Fast-forward pushes to dev hid the branches from the graph | Merge with `--no-ff` only. A local `pre-push` hook refuses non-merge commits on dev and any push to prod. |
| The release PR followed dev, so new work would have joined the release | Freeze each release on a `release/x.y.z` branch. |
| GitHub Actions stopped for billing, and every check showed a red ✕ | Pause GitHub CI and run the gates locally with a `local-ci` status. GitHub tests pull requests only. |
| A local gate passed, but GitHub refused the merge because dev moved during a 25-minute run | The gate pushes the exact tested merge (PR head + dev) to the PR branch before it merges. |
| Stacked PRs (#43 → #45, #50) needed several conflict rounds | Merge the base PR first, then update the stacked ones. Generated types are always regenerated, never merged by hand. |
| Targeted tests missed a contrast test and an e2e race | Before a PR is marked ready, frontend lanes run the full vitest suite and the full e2e suite once. |

**Backlog for Sprint 5**

- Track records: E2 upload hardening and E3 diagnostics (the headline).
- Decide the dollar lead term.
- TTF gas (Yahoo `TTF=F`), about 2 pts.
- Factor it polish:
  - fade-outs of the card and the bar;
  - the error page for a portfolio's first run;
  - "Change ticker" in all modes.
- Portfolio risk (E7b, E8), factor families, FF6 in the FF5-only sections, crowding-lite, Settings, and the specification curve.
