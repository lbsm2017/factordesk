# factordesk specification: fragility score (how many days a significance call rests on)

Status: specification for a new feature, written 2026-11-18. Not yet implemented.
Audience: engineers implementing `backend/factordesk/analytics/fragility.py` (new) and the schema additions; reviewers checking the code against it.
Companions: `docs/methodology.md` (M0-M16, D1-D31, cited unchanged; tags M3.2, gate M3.6), `docs/research-protocol.md`, `docs/test-oracle.md` (style, seeds, tolerances), `docs/validation/spy-slice-validation.md` (finding F4 asked for an influence diagnostic "never used to drop rows"), `docs/skill-review.md` (finding 9: no Cook's-distance cut-off), `docs/specs/lead-lag-betas.md` (sibling).
Section ids: FR0-FR13. Decisions: FRD1-FRD10 (FR11). Tests: TFR01-TFR22 (FR12). Registry entries: FR13.

Rule of precedence: every M0 convention applies unchanged. This feature adds **no hypothesis test, no BH family and no tag**. It measures how sensitive the existing tags of M3.2/M3.6 are to a few trading days. **The report never removes a day from any estimate it shows**; every number here is a "what if" computed beside the headline (FRD9). Proposed changes to `docs/methodology.md` are in FR11.2; this document does not edit it.

Evidence markers: **[V]** = verified by a computation run for this document (scratchpad folder `specs-ll-fr`, not part of the repo) or by a source checked on 2026-11-18; **[U]** = unverified.

---

## FR0. Scope, notation, classification

### FR0.1 What the feature shows

1. **Flip count.** For alpha and for each beta tagged reliable: the smallest number of trading days found whose removal makes the tag flip, the days themselves, and the z-statistic after removal. Shown as "This alpha rests on 7 days".
2. **Leave-one-year-out table.** Alpha and betas re-estimated with each calendar year left out, with their tags.
3. **Influential days.** The ten days that move the estimates most, with dates, returns and residuals, using influence measures scaled by the report's own HAC standard errors.

### FR0.2 Notation (additions to M0.1)

| Symbol | Meaning |
| --- | --- |
| `X`, `A = X'X`, `e` | Design `[1, f]` on `S`, its cross-product, full-sample OLS residuals (M3.1) |
| `g_t = x_t e_t` | Score of row `t`; `S_hat` = M0.5 Bartlett meat with `L = L(n)` |
| `h_i = x_i' A^-1 x_i` | Leverage of row `i` |
| `Delta_i = A^-1 x_i e_i / (1 - h_i)` | Exact change of the OLS estimate when row `i` is removed: `theta_hat - theta_hat_(-i)` |
| `j` | Index of the target coefficient (0 = alpha, 1..5 = betas in canonical order) |
| `tag_j(D)` | Tag of coefficient `j` (M3.2 rule) from the M3.1 regression on `S` minus the rows in `D` |
| `k*_j` | True minimum: the smallest size of a set `D` with `tag_j(D) != tag_j(empty)` |
| `k_j` | Value reported: size of the removal set found by the search of FR2; `k_j >= k*_j` |
| `K_max = ceil(0.01 n)` | Search cap (85 at `n = 8,474`; 6 at `n = 504`) |
| `k_ref(z, n)` | Gaussian reference count (FR6.2) |

### FR0.3 Classification

Every output is in-sample and full-window, stamped `T_end` (M0.2 item 2), labelled L-DESC. Nothing in this feature is a per-date series.

---

## FR1. What "removing a day" means (FRD1)

- Removing a set `D` of rows means refitting M3.1 on `S \ D`: same regressors, OLS with intercept, HAC per M0.5 with the lag `L(n - |D|)` of the smaller sample, rows positional, so the rows on either side of a removed row become adjacent (as for rows excluded by M2; skill-review finding 19).
- Tags after removal follow M3.2 exactly: alpha `p < 0.05`; betas BH within F1 **recomputed on the refit**, so removing days can flip a beta's tag through another beta's p-value. The search stops on whichever happens first.
- When the residual quality gate fires (M3.6), the headline tag is the conjunction "daily test and 5-day test both reject". The flip count is computed on the **daily** test only. Removing the reported days flips the daily test, which flips the conjunction, so for a conjunction tag the count is still an upper bound on the true minimum (label in FR6.4). The 5-day regression is not searched (removing a day changes block composition, which is a different question).

---

## FR2. Flip count for alpha (a)

### FR2.1 Scope (FRD2)

Computed only for coefficients whose headline tag is **reliable**. For a coefficient tagged noise the status is `not_applicable`, reason "Fragility is measured for significant results only." Rationale: the report makes claims only for reliable coefficients; telling a user that removing three days would make an insignificant alpha significant is an instruction for producing a false positive (FR7).

### FR2.2 Search algorithm (FRD3): greedy removal ranked by leave-one-out influence on z, with an exact refit at every step

State: the current kept rows `K` (initially all of `S`), its exact fit (`theta`, `V`, `e`, `L`), the sign `s = sign(z_j)` of the full-sample z.

At each step:

1. **Score every kept row** by its approximate leave-one-out z for coefficient `j` (all rows at once, vectorised):
   - `theta_(-i),j = theta_j - Delta_{i,j}` (exact; Sherman-Morrison).
   - `d_i = A^-1 e_j + (x_i' A^-1 e_j) / (1 - h_i) * A^-1 x_i`, the `j`-th column of `(A - x_i x_i')^-1` (exact).
   - With `p_i(o) = d_i' g_{i+o}` for offsets `o = -L..L` (zero outside the sample):
     `v_i = d_i' S_hat d_i - [ p_i(0)^2 + 2 sum_{l=1..L} w_l p_i(0) (p_i(-l) + p_i(l)) ] + (2/(L+1)) sum_{o1 = -L..-1} sum_{o2 = 1..L, o2 - o1 <= L+1} p_i(o1) p_i(o2)`.
     The bracket removes row `i`'s own and cross terms; the last sum adds the terms of rows that become adjacent once row `i` is gone (their Bartlett weight rises by `1/(L+1)`). With the other residuals and `L` held fixed, `v_i` equals **exactly** the `(j, j)` element of the HAC covariance of the deleted sample (identity; max relative difference in z `2.2e-15` over 270 checks [V]; TFR03). The only approximation is that the other rows' residuals are held at their full-sample values.
   - `z~_i = theta_(-i),j / sqrt(v_i)`.
2. **Pick** the row with the smallest `s * z~_i` (the removal that moves z furthest toward and past zero). Ties: earliest date.
3. **Refit exactly** on `K` minus that row (M3.1, `L(|K| - 1)`), recompute all tags.
4. **Safeguard.** If `|z_exact - z~_picked| > 0.05`, undo the step, refit the 20 best-scored rows exactly, and remove the one with the smallest exact `s * z` (or the first that flips the tag). Count of safeguard steps is reported.
5. **Stop** when the exact tag of `j` differs from its full-sample tag (`status = ok`, `k_j` = number of steps), or after `K_max` steps (`status = not_flipped_within_cap`).

The output always includes the removed days in order, so any reader can refit without them and check the flip (TFR05).

### FR2.3 What the number means, and why greedy is acceptable

- **It is an exact witness, so an upper bound.** The removed set is verified by an exact refit: removing those `k_j` days flips the tag. Therefore `k_j >= k*_j`. The report says "rests on **at most** {k} days" in the drawer and "rests on {k} days" in the headline sentence, with the method note "found by a step-by-step search; a smaller set may exist".
- **Exhaustive search is infeasible.** It needs up to `C(n, k)` refits: `C(8474, 2) = 3.6e7`, `C(8474, 3) = 1.0e11` [V].
- **Greedy equals the true minimum where brute force is feasible.** On 80 borderline-significant samples (40 at `n = 60` with exhaustive search up to 3 days, 40 at `n = 200` up to 2 days), greedy found the exact minimum in **80 of 80** (including the 17 cases at `n = 200` where no set of 2 days flips it) [V]. Greedy with exact refits of the top 20 at every step, and greedy over exact refits of all rows, gave the same 80 results.
- **The leave-one-out ranking is accurate.** Maximum absolute error of `z~` against exact single-row refits (median over 10 borderline samples): 0.091 at `n = 60`, 0.016 at `n = 200`, 0.004 at `n = 504`, 0.001 at `n = 2520`; best single row identical in 9, 8, 10 and 10 of 10 samples [V]. SPY (`n = 8,474`, all rows refitted): maximum error 0.0036, correlation of predicted and exact z changes 0.99999, best single day identical, top-10 sets identical [V].
- **Literature.** Broderick, Giordano and Meager (2020), "An automatic finite-sample robustness metric: when can dropping a little data make a big difference?", arXiv:2011.14999 [V, abstract read]: they "use an approximation to find the most influential subset" based on "the classical influence function", obtain "at minimal extra cost ... an exact finite-sample lower bound on sensitivity" by refitting, and find that "results of several influential economics papers can be overturned by removing less than 1% of the sample". The published version is in two parts, Giordano, Meager and Broderick (2026), *Philosophical Transactions of the Royal Society A* 384(2321), doi:10.1098/rsta.2025.0001 and 10.1098/rsta.2024.0614 [V, Crossref; content of the published parts U]. Differences in FR2.2: we target the HAC z (their metric covers estimates and standard errors), refit after **every** removal instead of once, and re-rank after each refit, which is cheap at `k = 6` parameters.
- **What greedy can miss.** Sets whose members are individually unremarkable but jointly decisive, for example a reversal pair (a day and its reversal next day) where removing either alone barely moves z. No lower bound on `k*` is reported; the oracle bounds the miss rate on small samples (TFR04).

### FR2.4 Cap (FRD4)

`K_max = ceil(0.01 n)`. Beyond 1% of the sample a call is not "resting on a few days" in any sense a user would mean, and 1% is the scale at which the cited work reports published results overturned. When the cap is reached: status `not_flipped_within_cap`, sentence in FR6.1, the z after `K_max` removals reported.

---

## FR3. Flip count for each beta's tag (a, continued)

Identical to FR2 with `j = 1..5`, for betas tagged reliable. The score uses `z_j`; the stopping check uses the full M3.2 rule (BH over the five refitted p-values). Betas of strongly exposed stocks typically do not flip within the cap (SPY: market, SMB, RMW not within 85 days; CMA at 61; HML is noise, so `not_applicable`) [V].

---

## FR4. Leave-one-year-out table (b)

- For each calendar year `Y` with at least one row in `S`: refit M3.1 on `S` minus the rows of `Y` (`L(n - n_Y)`, rows on either side of the gap adjacent).
- Row fields: `year`, `n_Y`, `partial` (`n_Y < 200`, as M6.2), `n_used`, `alpha_ann`, `se_ann`, `z`, alpha tag; five betas with z and BH tags; `alpha_flip` and the list of betas whose tag flips relative to the full sample.
- Row status `insufficient_data` when `n - n_Y < 252`; the table needs at least 3 calendar years with rows in `S`, else the section is `insufficient_data`.
- Summary line: years whose removal flips any tag; range of `alpha_ann` across rows.
- No year is ever "recommended" or highlighted as best; the table is ordered by year.
- Cost: one refit per year (SPY, 34 refits: 0.11-0.14 s) [V].

---

## FR5. Influence diagnostics adapted to HAC (c)

### FR5.1 Definitions

- `Delta_i` exact (FR0.2). For every row `i` and coefficient `j`:
  - **DFBETA-HAC** `= Delta_{i,j} / se_HAC,j`: the shift of coefficient `j`, in its own full-sample HAC standard errors, caused by removing day `i` ("removing this day moves alpha by 0.30 standard errors").
  - **Cook-HAC** `D_i = Delta_i' V_hat^-1 Delta_i / 6`, with `V_hat` the full-sample HAC covariance (M0.5).
- Why not the textbook versions. Cook (1977, *Technometrics* 19(1), 15-18, doi:10.1080/00401706.1977.10489493 [V, Crossref]) scales the shift by `s^2 (X'X)^-1`, and the usual DFBETAS by a homoskedastic leave-one-out se. Both assume constant-variance, uncorrelated errors, which the report does not use for inference (M0.5). Scaling by the HAC covariance measures influence in the units of the report's own intervals.
- **No cut-off** (skill-review finding 9: Cook's D `> 4/n` flagged 144 of 2,512 SPY days). Days are ranked, never classified as outliers.
- `max_ssr_share`: the largest single day's share of the residual sum of squares, with its date (validation finding F4).

### FR5.2 Lists

- **Top 10 days by Cook-HAC** (overall influence on all six coefficients).
- **Top 10 days by |DFBETA-HAC| for alpha**.
- **Top 5 days by |DFBETA-HAC| per beta** (drawer).
- Fields per day: `date`, `xret`, `mkt_rf` (and the other factor returns in the drawer), `fitted`, `resid`, `resid_prev`, `resid_next` (residuals of the neighbouring rows of `S`: a reversal pair shows at a glance), `leverage`, `cook_hac`, `dfbeta_hac` (6), `audit_findings` (M1.4 findings on that date, for example A4 extreme move), `in_flip_set` (whether the day is in any FR2/FR3 removal set).
- Ties: earlier date first.

---

## FR6. Wording and the fragility warning (d)

### FR6.1 Sentences (headline under the alpha tile and in each reliable beta's tooltip)

- `status = ok`: "This alpha rests on {k} day{s}: removing {k} of {n:,} trading days ({k/n:.2%}) makes it statistically indistinguishable from zero (z {z_full:+.2f} -> {z_after:+.2f}). Days: {dates}. The report keeps every day; this only measures how much the result depends on a few of them." For a beta: "...makes the {Factor} beta no longer reliable...".
- `not_flipped_within_cap`: "Removing up to {K_max} days ({1%} of the sample), chosen one at a time to weaken it, did not make this alpha insignificant (z {z_full:+.2f} -> {z_after:+.2f})."
- `not_applicable`: no sentence; tooltip "Fragility is measured for significant results only."
- Gate fired (M3.6): append "With the data-quality gate on, the reliable tag also requires the 5-day test, so {k} is an upper bound for the tag shown."

### FR6.2 Warning threshold (pre-specified, FRD5)

**Fragility warning** when `k <= 5`. It is a warning attached to the tag; it **does not change the tag** (FRD6).

Reasons, stated before calibration:
1. Five days is one trading week. A multi-year significance call that disappears without one week of data is not a property of the stock's normal behaviour; single days such as an earnings surprise, a crash day or a bad tick (validation F4) are exactly the kind of event a user must look at.
2. Under well-behaved (Gaussian) residuals, `k <= 5` happens almost only for alphas barely past the threshold. Simulation, `n = 2520`, true alpha 7e-4 a day, significant runs only [V]: Gaussian residuals: median `k` 5, 14, 24 for `|z|` in 1.96-2.5, 2.5-3.0, 3.0-3.5; share with `k <= 5` 14.2% overall. Student-t(3) residuals: median `k` 3, 8, 15; share with `k <= 5` 17.1% [V]. With Gaussian residuals the median `k` for `|z|` between 2.5 and 3.0 is 14, so a warning there is rare unless the tails are fat.
3. The number does not depend on a model of the residual distribution; the explanation sentence below does.

**Explanation (one sentence appended to the warning).** Gaussian reference count: `k_ref(z, n)` = smallest `k` with `sum_{i=1..k} Phi^-1(1 - (i - 0.5)/n) >= sqrt(n) (|z| - 1.959964)`. Derivation: removing the day with the `i`-th largest residual of a normal sample shifts the estimate by about `sigma Phi^-1(1 - (i - 0.5)/n) / n`, which is `Phi^-1(...)/sqrt(n)` in units of the standard error `sigma/sqrt(n)`; the shrinking standard error is ignored. It matches the simulated Gaussian medians: 5 vs 5, 14 vs 14, 25 vs 24 in the three `|z|` bands [V]. Values: `k_ref(2.0, n) = 1`; `k_ref(2.24, 2520) = 5`, `k_ref(2.5, 2520) = 10`, `k_ref(3.0, 2520) = 19`; `k_ref(2.24, 8474) = 8`, `k_ref(3.0, 8474) = 33` [V].

- If `k < k_ref / 2`: "That is fewer days than expected for an alpha this far past the threshold: a few days with unusually large unexplained returns carry it. Check them in the list of influential days (data errors, earnings, crashes)." Under Gaussian residuals this fires in 7.5% of significant samples, under t(3) residuals in 15.9% [V]; it is a description, not a test.
- Otherwise: "That is about what to expect for an alpha this close to the significance threshold."

Both thresholds (5 and one half) are documented heuristics, fixed before any real-ticker calibration. The placebo calibration (ROADMAP "Next") must register their false-alarm rates before release; changes go through a D-entry and a registry line.

### FR6.3 Leave-one-year-out sentence

"Leaving out {year} alone makes the alpha {insignificant/significant} (z {z:+.2f}). Across the {N} leave-one-year-out fits, alpha ranges from {min:+.2%} to {max:+.2%} a year." Only the first clause is conditional on a flip.

### FR6.4 Labels

L-DESC + "Sensitivity analysis. The report's estimates always use every day; these figures show what would change without some of them." Drawer method note: "Days are removed one at a time, each time the one that weakens the result most, re-estimating after each removal. The count is the smallest found, so the true minimum can only be smaller."

---

## FR7. The danger of inviting users to drop inconvenient days

- **The report never drops a day**, in any estimate, view or export. There is no API parameter, UI control or config key that excludes dates (TFR17). `CODING_STANDARDS.md` section 3 ("rows are never dropped because they are extreme") applies to this feature too.
- **Only significant results are examined** (FR2.1). The reverse question ("which days would I drop to get significance?") is not computed.
- **Wording is about dependence, not error.** Sentences say "rests on" and "depends on", never "outlier", "bad day" or "excluding these days gives". An influential day is flagged for inspection; only the audit (M1.4) calls a price wrong, and its findings are shown next to the day.
- **No alternative headline.** The z after removal is shown, but no alpha or beta "without these days" appears as a number in tiles, charts, attribution or risk panels.
- **No ranking of years.** The leave-one-year-out table is ordered by year; nothing marks a "best" or "cleanest" year (choosing a cleaner period after seeing results is the forking-paths problem of D21).
- **Selecting days is itself a test.** If a user removes days elsewhere and reruns, protocol item 2 applies: every rerun is a registry line, and fragility counts measured here would be invalidated by the selection.

---

## FR8. Computational cost (e)

Measured on the development machine (Windows, Python 3.13 via `uv`, numpy, single thread unless numpy threads) [V]:

| Step | `n = 8,474` (SPY) | `n = 8,000` (synthetic) |
| --- | --- | --- |
| One exact fit (OLS + HAC, `L = 10`) | 1.4-4.3 ms | 2.3 ms |
| Leave-one-out scoring of all rows for one coefficient (FR2.2 step 1) | 26 ms | 16 ms |
| Exact leave-one-out refit of every row (not used; for comparison) | 18-31 s | - |
| Greedy search, alpha (SPY flips at `k = 1`) | 0.1 s | - |
| Greedy search to the cap (80-85 steps), per coefficient, without / with top-20 verification at every step | - / 4.3-5.2 s | 0.8-1.8 s / 3.0-6.7 s |
| Leave-one-year-out (34 refits) | 0.11-0.14 s | 0.10 s (32 refits) |

Complexity per step: scoring `O(n (k^2 + L k + L^2))` (the `L^2` term is the re-join sum), exact refit `O(n k^2 + n L k)`; total `O(K_max n (k^2 + L k + L^2))` per coefficient, with `K_max = 0.01 n`, so `O(n^2)` overall. Worst case for a report (six coefficients all reaching the cap at `n = 8,000`): about 6 x 1.8 = 11 s with the safeguard rarely triggered (FR2.2 step 4 fires only on a prediction error above 0.05; the largest observed error at `n >= 504` is 0.010, so it is not expected to fire on long samples [V]).

Vectorised approach: all rows are scored with array operations on `X A^-1` (n x k), the score matrix `G` (n x k) and `2L + 1` shifted row-wise dot products; no Python loop over rows. Each step's exact refit reuses nothing (it is cheap and avoids drift). Long tickers may compute the beta searches lazily when the drawer is opened; alpha's search and the influence lists are always computed. A worker thread keeps the UI responsive (`factordesk calibrate` will need the same code path multi-core, ROADMAP).

---

## FR9. Status values, minimum samples, schema (f)

### FR9.1 Status (M0.7)

| Output | Condition | Status |
| --- | --- | --- |
| Flip count, coefficient `j` | tag noise | `not_applicable` |
| | flipped within `K_max` | `ok` |
| | not flipped within `K_max` | `not_flipped_within_cap` (a new status value, numeric fields filled; proposal FR11.2) |
| | an exact refit fails the M3.1 design guard (for example removing days leaves a factor constant) | `failed`, reason names the step |
| Leave-one-year-out | fewer than 3 years in `S` | `insufficient_data` |
| Influence lists | M3.1 `ok` | `ok` (always computed) |

Minimum sample: whatever M3.1 needs (`n >= 504`); at `n = 504`, `K_max = 6`, so the `k <= 5` warning can always be decided.

### FR9.2 Schema (`report/schema.py`; optional sub-model `fragility` of `FactorReport`, schema v3 contract)

`FragilitySection`: `status`, `reason`, `sample: SampleInfo` (same as M3), `algorithm_version` (str), `k_max` (int), `alpha: FlipCount`, `betas: list[FlipCount]` (5, canonical order), `leave_one_year_out: LoyoTable`, `influence: InfluenceLists`, `labels` (`["L-DESC", "L-FRAGILITY"]`).

`FlipCount`: `target` (`"alpha"` or factor code), `status`, `reason`, `tag_full` (`"reliable"`/`"noise"`, copied from M3.2/M3.6), `z_full`, `k` (int or `null`), `k_is_upper_bound` (always `true`), `share_of_sample` (`k / n`), `z_after`, `removed_days: list[RemovedDay]` (in removal order; up to `K_max` entries when the cap is hit), `k_ref` (int), `fragile_warning` (bool, `k <= 5`), `explanation` (`"few_unusual_days"` / `"near_threshold"` / `null`), `gate_upper_bound_note` (bool, M3.6 fired), `max_prediction_error` (float, max `|z_exact - z~|` over steps), `safeguard_steps` (int), `sentence` (str).

`RemovedDay`: `date`, `xret`, `resid`, `z_after_step`.

`LoyoTable`: `status`, `reason`, `rows: list[LoyoRow]`, `years_flipping_alpha` (list[int]), `years_flipping_beta` (dict factor -> list[int]), `alpha_ann_min`, `alpha_ann_max`, `sentence`.
`LoyoRow`: `year`, `n_year`, `partial`, `n_used`, `status`, `alpha_ann`, `se_ann`, `z`, `alpha_tag`, `betas` (5), `beta_z` (5), `beta_tags` (5), `alpha_flip` (bool), `beta_flips` (list of factor codes).

`InfluenceLists`: `top_cook: list[InfluentialDay]` (10), `top_alpha: list[InfluentialDay]` (10), `top_by_beta: dict[factor, list[InfluentialDay]]` (5 each), `max_ssr_share`, `max_ssr_share_date`.
`InfluentialDay`: `date`, `xret`, `factors` (5), `fitted`, `resid`, `resid_prev`, `resid_next`, `leverage`, `cook_hac`, `dfbeta_hac` (6), `audit_findings` (list[str]), `in_flip_set` (bool).

No field anywhere accepts a list of dates to exclude.

---

## FR10. Demonstrations [V]

Inputs as `docs/specs/lead-lag-betas.md` LL8 (French zip SHA-256 `e58577223032aa45071a46686f7068900c371b516c9eb04e28e974c34264f84f`; SPY yfinance 1.8.0, `auto_adjust=False, actions=True, repair=False`; `n = 8,474`, 1993-02-01..2026-09-30; alpha -0.576% a year, z -2.237; tags: alpha reliable, betas Mkt, SMB, RMW, CMA reliable, HML noise).

**Correction recorded.** The first runs for this section used an implementation with a wrong Sherman-Morrison term (`x_i' A^-2 e_j` in place of `x_i' A^-1 e_j` in `d_i`). On small samples it mis-ranked rows (greedy matched brute force in only 7 of 40 cases at `n = 60`); the brute-force comparison exposed it. All numbers below come from the corrected code; the superseded runs are registry lines (FR12).

### FR10.1 SPY: flip counts

| Coefficient | Tag | Status | `k` | z full -> after | Days removed (first ones) |
| --- | --- | --- | --- | --- | --- |
| Alpha | reliable | ok | **1** | -2.237 -> -1.938 | 2000-12-08 |
| Mkt-RF | reliable | not flipped within 85 | - | 151.8 -> 96.2 | 2008-10-22, 2008-10-16, 2008-10-07, ... |
| SMB | reliable | not flipped within 85 | - | -23.9 -> -14.6 | 2008-10-14, 2008-10-17, ... |
| HML | noise | not applicable | - | - | - |
| RMW | reliable | not flipped within 85 | - | 9.37 -> 4.98 | 2000-12-11, 2008-10-08, ... |
| CMA | reliable | ok | 61 | 5.42 -> 1.90 | 2000-12-05, 2000-04-03, 2025-04-09, ... |

Sentence for SPY: "This alpha rests on 1 day: removing 1 of 8,474 trading days (0.01%) makes it statistically indistinguishable from zero (z -2.24 -> -1.94). Days: 2000-12-08." Fragility warning on (`k = 1 <= 5`); `k_ref(2.24, 8474) = 8`, so `k < k_ref/2` and the explanation is "a few days with unusually large unexplained returns carry it". 2000-12-08 has residual -2.27% and the next row, 2000-12-11, +2.50%: a reversal pair of the kind M3.6 describes. The gate fires for SPY, so the upper-bound note is appended.

Exact check of the single-day step: all 8,474 one-day refits were run; the smallest `|z|` among them is 1.938 (2000-12-08), the largest 2.461, so exactly one day flips the tag on its own [V].

### FR10.2 SPY: leave-one-year-out

34 years. Alpha stays significant in 33; leaving out **2002** makes it insignificant (z -1.91). Alpha ranges from -0.68% (2026 left out) to -0.50% (2002 left out) a year. Leaving out 2008 makes HML reliable (BH tags `RRRRR`); no other beta tag changes in any row [V].

### FR10.3 SPY: influential days

Top 10 by Cook-HAC (date, excess return, Mkt-RF, residual, leverage, `D`, DFBETA-HAC alpha):

| Date | xret | Mkt-RF | resid | h | Cook-HAC | DFB alpha |
| --- | --- | --- | --- | --- | --- | --- |
| 2008-10-13 | +14.52% | +11.36% | +2.662% | 0.0170 | 0.0545 | +0.159 |
| 2000-12-08 | +0.20% | +2.79% | -2.265% | 0.0043 | 0.0418 | -0.301 |
| 2000-12-11 | +3.45% | +1.15% | +2.499% | 0.0015 | 0.0263 | +0.325 |
| 2000-01-07 | +5.79% | +3.21% | +2.563% | 0.0018 | 0.0239 | +0.289 |
| 2000-04-03 | +0.56% | -1.65% | +1.198% | 0.0122 | 0.0196 | +0.089 |
| 2008-09-22 | -2.27% | -3.93% | +1.573% | 0.0057 | 0.0191 | +0.188 |
| 2008-09-30 | +4.13% | +4.88% | -1.144% | 0.0101 | 0.0148 | -0.126 |
| 2008-10-07 | -4.48% | -5.76% | +1.285% | 0.0076 | 0.0141 | +0.166 |
| 2020-03-16 | -10.95% | -12.01% | +0.942% | 0.0140 | 0.0134 | +0.160 |
| 2008-09-18 | +2.96% | +4.40% | -0.994% | 0.0115 | 0.0128 | -0.121 |

Top alpha days by |DFBETA-HAC|: 2000-12-11 (+0.325), 2000-12-08 (-0.301), 2000-01-07 (+0.290), 2008-10-24 (-0.235), 2000-02-24 (-0.230), 2008-09-22, 1999-02-16, 2008-10-07, 2001-01-02, 2020-03-16. Largest single-day share of SSR 1.9%. Exact leave-one-out point estimates equal the Sherman-Morrison formula to `2.5e-18` [V].

### FR10.4 Simulations with a known planted outlier (DGP-A, `n = 2520`, dates from 2010-01-04)

- **P1, a cluster of 20 planted days** (+10% residual each, every 125 rows from row 60), true alpha 0. Clean sample: alpha +6.2% a year, z +0.99. With the planted days: +26.1%, z **+3.35**. Greedy: `k = 12`, z after 1.86, and **all 12 removed days are planted**. Top 10 by |DFBETA-HAC alpha| are all planted; 19 of the top 20 by Cook-HAC are planted. (Without background noise, 7 removals would suffice: `z(m) = 0.1 m / sqrt(0.01 m + n 0.012^2)` gives 2.67 at `m = 20` and 1.97 at `m = 14`; the clean sample's own +0.99 adds the rest.)
- **P2, one planted bad tick** (+60% on 2015-10-05), true alpha 2e-4 a day. Clean: +13.65% a year, z +2.22, se 6.15%. With the tick: +19.07%, z +2.33, se **8.20%**. The tick is rank 1 by Cook-HAC (`D` 0.146 against 0.0073 for the next day; 48.7% of SSR), but removing it alone leaves z at +2.23: a single huge day raises the standard error almost as much as the estimate, because one day contributes `u` to the numerator and `u^2` to the variance, so its own contribution to z is about `u / sqrt(u^2 + rest)`, below 0.71 here. Greedy needs `k = 6`, including the tick. **Lesson built into the spec:** the flip count and the influence list answer different questions, and both are shown.
- **P3, one moderate planted day** (+8% on 2015-10-05) on a sample with true alpha 6e-4 a day: z +2.28; greedy removes 2015-10-05 **first** and flips at `k = 5`.

### FR10.5 Algorithm checks

Brute force vs greedy, approximation accuracy, and the `k_ref` calibration: FR2.3 and FR6.2.

---

## FR11. Decisions, proposals, open questions

### FR11.1 Decisions

- **FRD1** Removal = refit on `S \ D` with positional HAC and `L(n - |D|)`; tags recomputed by M3.2 (FR1).
- **FRD2** Only reliable tags are examined; no "days to significance" (FR2.1, FR7).
- **FRD3** Greedy one-day-at-a-time search ranked by an influence approximation of the HAC z, exact refit each step, safeguard re-ranking (FR2.2).
- **FRD4** Cap `ceil(0.01 n)` (FR2.4).
- **FRD5** Warning at `k <= 5`; explanation by `k_ref` (FR6.2).
- **FRD6** Fragility never changes a tag.
- **FRD7** Under the M3.6 gate the daily-test count is shown as an upper bound for the conjunction tag (FR1).
- **FRD8** Influence scaled by HAC (DFBETA-HAC, Cook-HAC), no cut-offs (FR5).
- **FRD9** No day is removed from any reported estimate; no exclusion interface exists (FR7).
- **FRD10** Leave-one-year-out by calendar year, positional HAC across the gap (FR4).

### FR11.2 Proposals for `docs/methodology.md` (for the owner; not made here)

1. M0.7: new status value `not_flipped_within_cap` (or reuse `ok` with `k = null` and a flag; owner's choice).
2. M0.9: label key L-FRAGILITY (FR6.4 text).
3. A short M-section pointing here (Definition of Done); answers skill-review decision 3.3 item 3 (influential days) with "top lists, no thresholds".

### FR11.3 Open questions for the owner

1. Is `k <= 5` the right warning level for a tool whose typical sample is 2,500-8,500 days, or should it scale with `n` (for example `k <= max(5, 0.001 n)`)? The placebo calibration should decide; until then 5 is fixed.
2. Should a fragility warning on alpha change the KPI wording from "significant" to "significant, fragile", or stay in the tooltip (current spec)?
3. Compute beta searches eagerly (up to about 11 s on 8,000 days) or lazily when the drawer opens?

---

## FR12. Test oracle (TFR01-TFR22)

Seeds: `rng = default_rng(20261118 + 500 + k)` for TFRk. Tolerances per `docs/test-oracle.md` 0.3.

### DGPs

- **DGP-A** (test-oracle 0.4), `n = 2520` unless stated.
- **DGP-FR-CLUSTER:** DGP-A with `alpha = 0` plus `+0.10` added to `y` on 20 rows `60, 185, ..., 2435`.
- **DGP-FR-TICK:** DGP-A (`alpha = 2e-4`) plus `+0.60` on row 1500.
- **DGP-FR-BORDER:** DGP-A rows with `alpha = 0`, then `y` shifted by a constant so the full-sample alpha z equals a target drawn from `U(2.0, 2.8)` with random sign (the shift changes only the intercept; residuals and betas are unchanged).

### Identities and exactness

- **TFR01 Exact deletion.** For 50 random rows of DGP-A and every coefficient: `theta_hat - Delta_i` equals OLS on `S` minus row `i` (`1e-12` relative or `1e-15` absolute).
- **TFR02 Inverse update.** `d_i` equals column `j` of `inv(A - x_i x_i')` (`1e-10` relative), for 50 rows; mutation `x_i' A^-2 e_j` (the recorded bug) must fail this test.
- **TFR03 Variance identity.** With residuals and `L` held fixed, `v_i` equals the `(j, j)` element of `inv(A_(-i)) S_(-i) inv(A_(-i))`, where `S_(-i)` is the Bartlett meat of the score sequence with row `i` deleted (`1e-12` relative), at `n = 60, 200, 1000`, all six coefficients, 15 rows each (observed `2.2e-15` [V]).
- **TFR04 Approximation accuracy.** DGP-FR-BORDER, 10 samples each: max `|z~ - z_exact|` `<= 0.25` at `n = 60`, `<= 0.08` at `n = 200`, `<= 0.03` at `n = 504`, `<= 0.005` at `n = 2520` (observed maxima 0.146, 0.047, 0.010, 0.001; bounds about 1.7-5 times the observed maximum, because the error scales with the residual-update term, not with a standard error).
- **TFR05 Witness exactness.** For every `ok` flip count, refitting M3.1 without `removed_days` reproduces `z_after` (`1e-12` relative) and the flipped tag exactly; refitting without all but the last removed day does not flip the tag.

### Search quality

- **TFR06 Greedy vs brute force (`slow`).** DGP-FR-BORDER, 40 samples at `n = 60` (exhaustive up to 3 days) and 40 at `n = 200` (up to 2 days): greedy `k` never below the exhaustive minimum (impossible by construction; a failure means a bug), and equal to it in at least 76 of 80 (observed 80 of 80 [V]; 5% slack for seeds).
- **TFR07 Safeguard.** Inject a scoring function that is deliberately wrong for one row (adds 1.0 to its predicted z): the step's prediction error exceeds 0.05, the safeguard runs, `safeguard_steps >= 1`, and the final `k` equals that of the correct scorer.
- **TFR08 Planted cluster.** DGP-FR-CLUSTER: alpha tag reliable; status `ok`; every removed day is a planted row; `k <= 20`; the top 10 by |DFBETA-HAC alpha| are all planted rows. Margin: planted residuals are 8.3 residual sds; the largest unplanted residual in 2,500 normal draws is about 3.9 sds.
- **TFR09 Planted bad tick.** DGP-FR-TICK: the tick row is rank 1 by Cook-HAC with `D` at least 10 times the second (observed 20x); its `max_ssr_share` > 0.3. Bound on one day's own contribution: the tick's DFBETA-HAC for alpha is at most 0.8 (heuristic bound `u / sqrt(u^2 + sum of other squared residuals) = 0.71` for `u = 0.60`, `n = 2520`, `sigma_e = 0.012`, plus 0.09 for leverage and HAC cross terms; observed 0.655 [V]). This is the property behind FR10.4 P2: a single day, however large, moves alpha's z by less than one.
- **TFR10 Cap.** DGP-A with `alpha = 1.5e-3` a day (expected z about 6): status `not_flipped_within_cap`, `len(removed_days) == K_max == 26`, `k` is `null`, sentence is the cap sentence.

### Tags, scope, gate

- **TFR11 Not applicable.** Any coefficient tagged noise: status `not_applicable`, no removed days, no sentence; the module never searches toward significance (mutation: run the search on a noise tag; the test fails if any field is filled).
- **TFR12 BH coupling.** Pure-function case: five p-values where removing a set of rows raises another beta's p-value and so flips beta `j`'s BH tag; the search stops on that flip and reports it. Uses the M3.2 tag function unchanged (`multipletests(..., "fdr_bh")`).
- **TFR13 Gate note.** Fixture where M3.6 fires: `gate_upper_bound_note` is true and the sentence carries the appended clause; the count equals the daily-only search result bitwise.

### Leave-one-year-out and influence

- **TFR14 LOYO rows.** Every row equals M3.1 refitted on `S` without that year (`1e-10` relative) with `L(n - n_Y)`; `partial` iff `n_Y < 200`; a sample starting 2010-07-01 marks 2010 partial; fewer than 3 years gives `insufficient_data`.
- **TFR15 Influence formulas.** DFBETA-HAC and Cook-HAC equal `Delta_i / se_HAC` and `Delta_i' V^-1 Delta_i / 6` built from refits (`1e-10` relative) for 20 random rows; lists sorted descending, ties by date; `resid_prev`/`resid_next` are the neighbouring rows' residuals (`null` at the ends).
- **TFR16 Wording thresholds.** Pure function: `k = 5` gives a warning, `k = 6` none; `k_ref(2.0, n) = 1` for all `n`, `k_ref(2.24, 2520) = 5`, `k_ref(2.5, 2520) = 10`, `k_ref(3.0, 2520) = 19`, `k_ref(2.24, 8474) = 8`, `k_ref(3.0, 8474) = 33` (exact); explanation `few_unusual_days` iff `k < k_ref / 2`.

### Never drop, no look-ahead

- **TFR17 Headline invariance and no exclusion interface.** All M3-M11 outputs are bitwise identical with the module on and off; static check that no schema model, API parameter or config key accepts dates to exclude, and that no function in `fragility.py` returns a fit object to callers outside the module.
- **TFR18 Truncation.** DGP-A truncated at `t* = 1800`: every fragility output is stamped `t*` and is bitwise unchanged when all rows after `t*` are replaced (T103 pattern).
- **TFR19 Uncovered tail.** Adding 30 price rows after the factor `last_date` (M2 step 6) changes nothing.

### Calibration of the warning (`slow`)

- **TFR20 Gaussian reference.** DGP-A with Gaussian residuals, `alpha = 7e-4`, `R = 300`: median `k / k_ref` over significant runs in `[0.8, 1.2]` (observed 0.96); with t(3) residuals in `[0.4, 0.8]` (observed 0.58).
- **TFR21 Cost (benchmark, non-blocking).** `n = 8000` synthetic: alpha search to the cap below 5 s on the reference CI machine; recorded, not asserted in the blocking suite.

### Live (`live`, non-blocking)

- **TFR22 SPY.** Full history: alpha flip count `ok` with `k <= 3`; 2000-12-08 among the removed days; leave-one-year-out flips alpha for at most 3 years. Loose on purpose (Yahoo `Adj Close` drifts between downloads, validation F8).

---

## FR13. Registry entries (demonstrations run for this document)

Format: protocol Appendix A; to be appended to `docs/registry/tests.jsonl` (fresh `test_id`s if these collide) in the change that adds this spec. Nothing was pre-registered; every line has status `run` (or `superseded`) and split role `in_sample_only`; no confirmatory claim is made. Common fields: `created_at` 2026-11-18; `code_version` none (scratch scripts `fragility.py`, `fr_spy.py`, `fr_sim.py`, `fr_sim2.py`, `fr_identity.py`, `fr_debug.py` in `specs-ll-fr/scripts`); dataset `us_ff5_daily` stamp 202609 SHA-256 `e58577223032aa45071a46686f7068900c371b516c9eb04e28e974c34264f84f`; SPY yfinance 1.8.0 downloaded 2026-11-18.

Hypothesis ids: `H-301` "SPY's significant alpha and betas are fragile to a few days" (descriptive). `H-302` "The greedy influence search finds the exact minimum flip count on small samples and recovers planted days" (simulation). `H-303` "`k_ref` reproduces the Gaussian median flip count; fat tails lower `k / k_ref`" (simulation).

| test_id | hypothesis_id | Status | Spec | Result | Notes |
| --- | --- | --- | --- | --- | --- |
| T-20261118-300 | H-301 | superseded by 310 | SPY LOO approximation vs exact, buggy `d_i` | max error 0.0136 | bug: `x_i' A^-2 e_j` |
| T-20261118-301 | H-301 | superseded by 311 | SPY greedy, alpha and 5 betas, cap 85, approximation-only ranking, buggy | alpha `k = 1`; CMA not flipped | |
| T-20261118-302 | H-302 | superseded by 313 | Planted P1-P3, buggy | P1 `k = 12`, P2 `k = 6`, P3 `k = 5` (unchanged after the fix) | |
| T-20261118-303 | H-302 | superseded by 315 | Greedy vs brute force, n 60 (k <= 3) and n 200 (k <= 2), 40 each, seeds +950, +951, buggy | equal in 7/40 and 20/40 | exposed the bug |
| T-20261118-304 | H-303 | superseded by 316 | Flip-count distribution, Gaussian and t(3), alpha 6e-4 and 9e-4, R 200 each, seeds +970..+989, buggy | Gaussian medians 6, 14, 24, 27 by band of abs(z) (alpha 6e-4) | not cited in the text |
| T-20261118-305 | H-302 | superseded by 314 | Approximation accuracy n 60..2520, with and without re-join, buggy | max errors 2.7 / 1.8 / 0.29 / 0.006 | |
| T-20261118-306 | H-302 | superseded by 315 | Greedy variants vs brute force, buggy | approx 0.175 / 0.50; verified M=20 0.75 / 0.775; all-rows exact 1.0 / 1.0 | |
| T-20261118-307 | - | superseded by 317 | Timing n 8000, buggy | - | |
| T-20261118-310 | H-301 | run | SPY LOO approximation vs exact refits of all 8,474 rows, alpha | max error 0.0036; top-10 identical; exact LOO z range [-2.461, -1.938] | |
| T-20261118-311 | H-301 | run | SPY flip counts, alpha and 5 betas, cap 85, verified greedy (M = 20) | FR10.1 | 6 lines in the file (one per coefficient) |
| T-20261118-312 | H-301 | run | SPY influence lists and leave-one-year-out (34 refits) | FR10.2, FR10.3 | 34 LOYO rows are one line (descriptive table) |
| T-20261118-313 | H-302 | run | Planted P1 (cluster), P2 (tick), P3 (moderate day), seeds +960..+962 | FR10.4 | 3 lines |
| T-20261118-314 | H-302 | run | Approximation accuracy, n 60, 200, 504, 2520, 10 samples each, with and without re-join, seeds +980..+983 | FR2.3 | 8 lines |
| T-20261118-315 | H-302 | run | Greedy (approx, M = 20, all rows) vs brute force, n 60 and 200, 40 each, seeds +950, +951 | 80/80 equal for all three | 6 lines |
| T-20261118-316 | H-303 | run | `k / k_ref`, Gaussian and t(3), alpha 7e-4, R 300 each, seeds +990, +991 | FR6.2 | 2 lines |
| T-20261118-317 | - | run | Timing n 8000, plain vs verified greedy, 6 coefficients, LOYO | FR8 | benchmark, not a test |
| T-20261118-318 | H-302 | run | Variance identity check (TFR03), seed +1100 | 2.2e-15 | identity |

Sources checked on 2026-11-18: arXiv API record 2011.14999 (abstract quoted in FR2.3); Crossref records for doi:10.1098/rsta.2025.0001, doi:10.1098/rsta.2024.0614 and doi:10.1080/00401706.1977.10489493.

## Owner decisions (2026-11-18)

- **Warning threshold** (fixed at k ≤ 5 trading days, or scaled with sample size): postponed. Do not implement a warning threshold until the owner decides; the score itself may be built and shown.
