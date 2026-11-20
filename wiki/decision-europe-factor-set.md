# Decision: a Europe factor set next to the US one

Date: 2026-11-20
Status: Decided; built and validated on feature branches, not yet on `dev` (PRs #38, #43 and #45 were open on 2026-11-20)

## In one sentence

A report can be measured against the Ken French Developed Europe factors (five factors plus momentum) instead of the US factors; the user picks the set, the default stays US, and macro, energy and world beta always keep the US factors.

## What we decided

- On 2026-11-20 the owner approved Sprint 4 with the goal "European investor complete" ([sprint record](../docs/sprints/sprint-4.md)). Sprint 3 had shown the euro view, but the factors were still the US ones converted to euros, so a euro investor holding European shares was measured against the wrong market.
- Design decision 1, 2026-11-20: the source is the Ken French Developed Europe files, five factors and momentum, daily and monthly. They start in 1990 and are published in US dollars.
- Design decision 2, 2026-11-20: the user picks the set, and the default is US in both currencies. The right set depends on where the holding trades, not on the investor's currency. We do not choose the set automatically.
- Design decision 3, 2026-11-20: the risk-free rate is the French one-month T-bill rate in USD and the euro cash rate in EUR, as in Sprint 3.
- Design decision 4, 2026-11-20: macro, energy and world beta keep the US factors, and their own US-aligned sample, for every factor set. Only the Fama-French sections change with the set.
- On 2026-11-20 the first review of the engine branch (commit a65f080) found that those three sections had been rebuilt on the Europe sample, and that the world beta row had read the Europe market factor. The coordinator fixed this in commit 9474d2e: with Europe selected, the three sections run on their own US-aligned sample with the US market factor, and their output is identical to the US set ([validation](../docs/research/sprint-4-validation.md), check 7, rerun).
- The report field `factor_set` appears only for Europe. The US report is bit-identical to `dev` at 8d70ed5 (validation check 3).

## How it works

All claims in this section are about the code as described in the pull requests on 2026-11-20.

- PR #38 (S4-2) reads the four Europe files with the same loader as the US files. The Europe files name the database "Bloomberg" in the preamble (the US files say "CRSP") and call the momentum column `WML`; the loader reads that column as `Mom`. The factors stay in USD with the US T-bill as risk-free rate, and the Sprint 3 formulas convert them to euros without change.
- PR #43 (S4-3) adds `factor_set` (`us` or `europe`) to the ticker, ranges, export, portfolio and upload requests. An unknown value gives 400. Cache keys include the set. Every French-factor section reads the chosen frame: exposures, alpha strip, rolling, return and risk sources, tail risk, residual, Kalman and lead-lag.
- Choices made in PR #43 where the plan was silent: shrunk betas are left out for Europe (their prior uses the US 25 portfolios); a portfolio cash leaf earns the US daily risk-free rate; if the Europe files fail to load, the Europe report fails and the US report is not affected; an upload falls back to the Europe five factors when Europe momentum is missing.
- Ranges and coverage use the Europe dates, so the files' 1990 start applies.

## Why

- A European fund is driven by European size, value and momentum moves. Against US factors the fit is weak, and the alpha is then partly the market difference.
- The set follows the listing, not the investor, because the factors describe the market the holding trades in. A euro investor in a US fund still wants the US set.
- Keeping macro, energy and world beta on US inputs keeps those sections comparable across sets. They would otherwise lose the days that the Europe file does not cover (304 days for SPY).

## What the real data showed

On 2026-11-20 the validation ran on real data, last price date 2026-11-19, both files at release 202609 ([results](../docs/research/sprint-4-validation.md), PR #45):

- EXSA.DE (a European-listed fund) in euros, daily, FF6: R-squared 0.294 with the US set and 0.806 with the Europe set.
- VGK (a European fund listed in New York) in euros, daily, FF6: 0.730 with the US set and 0.703 with the Europe set. The Europe set is worse. VGK closes after the European markets, so its daily return holds US afternoon news that the Europe factors show only the next morning. It is the same close-time effect found for SXR8 in Sprint 3 ([reference currency](decision-reference-currency.md)). The Europe set also drops about 200 days on which Europe has no row.
- VGK monthly, in euros, uploaded as a record, FF6: 0.626 with the US set and 0.978 with the Europe set.
- SPY in USD, FF6: 0.967 with the US set and 0.323 with the Europe set. The sprint expectation holds.
- Guidance from the validation: for a European fund listed in the US, read the Europe set on monthly data.

## What it costs us

- The user has to choose. A wrong choice gives a poor fit, and the report only names the set in use. It does not warn.
- Daily fits of US-listed European funds are worse with the Europe set than with the US set (VGK, 2026-11-20). The product does not say so on screen.
- A US-listed subject is analysed on fewer days with the Europe set, because the Europe file lacks some US trading days.
- Shrunk betas do not exist for Europe.
- History starts in 1990, not 1963.

## What would change our mind

- Users picking the wrong set in practice: then we would add an automatic choice from the listing suffix.
- A second Europe-listed fund that fits worse with the Europe set at daily frequency.
- The Europe file lagging the US file by more than a release. The plan was to show a notice when the sets are out of step.

## Sources

- [Sprint 4 record](../docs/sprints/sprint-4.md): plan and design decisions 1 to 4.
- [Sprint 4 validation](../docs/research/sprint-4-validation.md): PR #45, and the rerun after commit 9474d2e.
- PRs #38 (Europe files) and #43 (factor set in the engine).
- Related: [European mode, regional factors and currency](decision-european-mode-and-currency.md), [USD or EUR reference currency](decision-reference-currency.md), [Factor data source](decision-factor-data-source-french-library.md), [Factor models and macro](decision-factor-models-and-macro.md)
