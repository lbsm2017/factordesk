# Decision: the Ken French Data Library is our only source of factor data

Date: 2026-11-18
Status: Decided

## In one sentence

Every factor number in factordesk comes from one public library run by Kenneth R. French, and where any other source disagrees with that library about what a factor is, the library wins.

## What we decided

- The Ken French Data Library is the single source of truth for the five factors and the risk-free rate.
- The v1 file is the US daily 5-factor file, downloaded when the tool runs and never stored in the repository.
- We keep one data vintage (the newest) and log any change to past values on refresh.
- Secondary explainers inform wording only, never numbers.

## Why

The library is where the factors are defined and published, so our "value" factor is, by construction, the published one. We rejected `pandas-datareader` because the plan's research found it fragile, with most readers broken; our own parser of about 30 lines is easier to test. We rejected popular web explainers as a source of benchmarks because their figures carry no sample period. The sources do not record why we did not build the factors ourselves; our reading is that it needs paid stock-level data and would not be comparable with the literature.

## How it works

- The file is a zip of a text table in percent. We read it in memory, check the header, treat `-99.99` and `-999` as "missing", and divide by 100.
- Example: a published market value of `-17.44` on 1987-10-19 becomes `-0.1744`, a 17.44% fall.
- The library publishes about monthly, so the newest factor day trails today by one to two months. The file we downloaded on 2026-11-18 ran through 2026-09-30.
- A refresh is attempted when the data is more than 40 days behind and the last attempt was more than 12 hours ago. A failed download keeps the old file.
- The library rebuilds its whole history each month, so old values can change. We log the cells that moved.

## What it costs us

- Results depend on one outside provider. If its URL or layout changes, the parser refuses the file rather than guessing, and factordesk has no new factors until we fix it.
- The lag means the most recent prices cannot be analysed; the report greys out that tail.
- Revised history means the same ticker can give slightly different numbers after a refresh.
- The sources do not state the currency of the US files (dollars is the natural reading; unverified as of 2026-11-18).
- Use is subject to the library's terms; we credit Kenneth R. French and Eugene F. Fama.

## What would change our mind

The library changing its terms or format beyond what we can parse, ceasing updates, or an uncorrected error in a factor series. A better public source with daily data would justify a second source behind the same checks.

## Sources

- [docs/references.md](../docs/references.md): source of truth, URLs, papers, terms.
- [docs/datasets.md](../docs/datasets.md): verified facts about each file, including the 2026-11-18 download.
- [docs/methodology.md](../docs/methodology.md), M1.1 and M1.2 (parser, staleness rule).
- [docs/PLAN.md](../docs/PLAN.md), "Lessons from GitHub analogs".
- Library home: <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html>

## Related decisions

- [Daily returns and robust errors](decision-daily-returns-and-robust-errors.md)
- [European mode and currency](decision-european-mode-and-currency.md)
- [No data and no secrets in the repository](decision-no-data-and-no-secrets-in-the-repo.md)
