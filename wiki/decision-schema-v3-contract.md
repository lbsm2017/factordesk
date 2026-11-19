# Decision: one contract for the five new report sections

Date: 2026-11-18
Status: Decided-pending-implementation

## In one sentence

Before five statistical features are built at the same time, we fix where each one plugs into the report, so that each branch edits only its own files and no merge breaks another branch.

## What we decided

- Each feature (fragility score, lead-lag betas, Kalman betas, shrunk betas, residual alpha analysis) gets one optional field on the report, one schema file, one analytics file, one pipeline hook, one panel in the downloadable HTML report and one panel in the dashboard. The full list of names is in `docs/specs/schema-v3-contract.md`.
- A missing section means "this feature did not run" and shows nothing. A section that ran but could not be computed says so with a status and a reason, like every other statistic.
- The report format number goes from 3 to 4. Files written with version 3 still open; they simply have no new sections.
- Panels are placed by a registry with fixed positions, so adding a panel never edits a shared list.
- The shared files (report schema, pipeline, page layout, styles) are frozen for the feature branches. A needed change there goes through its own small pull request first.

## Why

Without a contract, five branches would all edit the same three or four files, and every merge would conflict. We rejected "build them one after another" because it would take five times as long. We rejected "let each branch edit the shared files and sort it out at merge" because conflicts in the schema also break the dashboard's generated types and the tests of every other branch.

## How it works

- The roadmap calls this the "schema v3 contract", but the number 3 was already used for the residual diagnostics and the quality gate, so the payload number is 4.
- Each new section carries the same three fields as every statistic: status, reason and the sample it used.
- Footnote texts of a new section live with that section and are added to the report only when the section is present.
- Panel positions: lead-lag, shrunk and fragility follow the factor exposures; residual alpha follows risk; Kalman follows the rolling betas.

## What it costs us

- Some specs place their numbers inside existing panels (a sentence under the alpha tile, a marker on the beta row, a line on the rolling chart). For now each feature shows them in its own panel; folding them into the existing panels is one later change.
- A few spec details had to be adjusted to fit (listed in section SC6 of the contract), for example the residual feature's diagnostics model is renamed because the name was taken.
- Methodology text for the new statistics stays in each feature's own specification until the owner folds it into `docs/methodology.md`.

## What would change our mind

If one feature needs a shared file changed often, the split is wrong for that feature and its piece of the shared file should become a file of its own.
