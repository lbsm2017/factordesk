# World beta: note on the schema v3 contract (a sixth optional section)

Date: 2026-11-18. Branch `feat/world-beta`. Status: proposal for the owner. Nothing here edits `docs/specs/schema-v3-contract.md`; the branch carries on and follows the contract's rules where they apply.

The contract (`docs/specs/schema-v3-contract.md`) lists five optional sections. The world beta is a sixth. The contract's rule SC7 says that a change in a "nobody" file stops the branch and goes through its own pull request. The owner's brief said to write this note and carry on, so the branch made the smallest edits it could. Each is listed below so that the owner can approve them, move them to their own pull request, or ask for a different shape.

## 1. What the branch follows from the contract

- One optional field `world_beta: WorldBetaSection | None = None`, `None` meaning "did not run" (SC1 item 1).
- One section module `report/sections/world_beta.py` with `WorldBetaSection(SectionModel)` and `WORLD_BETA_SECTION`; nested `BetaFit` in the same file (SC1 item 2).
- `status`, `reason`, `sample` from `SectionModel`; status values are the M0.7 four only (`ok`, `insufficient_data`, `not_applicable`, `failed`); a section that is not `ok` carries no float (SC1 item 3). When ACWI cannot be fetched and no cache exists the section is `failed` with the reason "ACWI price data could not be fetched".
- Footnote keys `L-WORLD-PROXY` and `L-WORLD-ASYNC` live in the section's `label_text`; `schema.LabelKey` and `LABEL_TEXT` are not edited (SC1 item 5).
- Display names and `_annual` suffix in API fields (SC1 item 6): `alpha_annual`.
- One hook `section_hooks/world_beta.py`, one analytics file `analytics/world_beta.py`, one static panel `report/panels/world_beta.py`, one React placeholder `WorldBetaPanel.tsx` (SC2 pattern).
- `SCHEMA_VERSION` stays `"4"` (SC5: filling in an additive optional field does not bump it). `SUPPORTED_SCHEMA_VERSIONS` is unchanged. A version 3 file cannot hold the section (the existing check covers every entry of `SECTIONS`).
- Generated files regenerated with the repository commands (SC8).

## 2. Edits to "nobody" files, and why each is needed

| File | Edit | Why it cannot live elsewhere |
| --- | --- | --- |
| `report/schema.py` | One import, one entry in `SECTIONS` (after fragility), one field on `FactorReport` (after `fragility`), a docstring sentence | A new report field and `SECTIONS` are the contract's own extension points (SC3.1); there is no other place for a sixth entry. |
| `report/panels/__init__.py` | One import line | This is how a panel registers (SC3.3). |
| `section_hooks/context.py` | New frozen `WorldBenchmarkInput`; one new optional field `SectionInputs.world_benchmark` | The section needs extra data (the ACWI prices), as the shrunk betas need the portfolio files; `SectionInputs` is the contract's carrier (SC3.2). |
| `section_hooks/__init__.py` | `load_section_inputs` gets an optional `price_provider` argument | ACWI must come through the provider the report uses, so tests inject a fake provider and the run keeps one cache and one throttle. |
| `pipeline.py` | The hook call (between fragility and residual, panel order), the `"world_beta"` entry in `present`, the field in `FactorReport(...)`, `price_provider=provider` in the `load_section_inputs` call | The pipeline calls every hook (SC3.2). |
| `api/deps.py`, `api/service.py` | `AppDeps.load_world_benchmark` (default: refresh ACWI through the real provider) and one call in `ReportService.report` that adds the result to the section inputs | The owner asked that ACWI is refreshed on every ticker load. The dashboard's section inputs are cached per day and vintage, which would hide a failed refresh for the whole day, so the benchmark is loaded on each report build and is not part of that cache. `api/*` is open to the shrunk feature for the same reason (SC7); the same reasoning is applied here. |
| `data/prices.py` | `YFinanceProvider.fetch_incremental`, `HistoryRefresh`, `IncrementalPriceProvider`; the batch download loop takes an optional request and finish function | The price cache is the provider's. Existing methods behave as before (the `test_prices*.py` suites pass unchanged). |
| `tests/fixtures/mock_report.json` | Regenerated (one new key, `"world_beta": null`) | The mock fixture lists every optional field (SC9). |
| `tests/fixtures/sections/__init__.py`, `label_text.json`, new `world_beta.json` | One entry in `SECTION_FILES`, one label block, one synthetic section | The fixture folder is keyed by section (SC9). |
| `tests/test_schema_contract.py`, `tests/test_panel_registry.py` | "Five" becomes "six" (field tuple, test name), the panel order and the panel-follows table get the new entry | These tests pin SC2 and SC4. |
| `frontend/src/api/types.ts`, `panelRegistry.ts`, `panelRegistry.test.tsx`, `test/sectionFixtures.ts` | A type alias, a registry entry at 540 pointing at the placeholder, the order test, the fixture map | SC3.4 lists these as the React extension points. |

The branch edits no `docs/specs`, `docs/methodology*` or test-oracle file.

## 3. Proposed amendments to the contract text (the owner's call)

1. SC0 and SC2: "five" becomes "six"; add section SC2.6 with the table of this note's section 1 (field `world_beta`, module, hook `build_world_beta(ctx) -> WorldBetaSection | None`, panel name `world_beta`, position 540, element id `world-beta`, tests `test_world_beta.py` and `test_section_world_beta.py`, fixture `sections/world_beta.json`).
2. SC3.2: `SectionInputs` has a second field, `world_benchmark`, and `load_section_inputs` takes `price_provider`.
3. SC4: add the row `540 | world_beta | world-beta | world beta` between fragility (530) and returns (600). Reason for the position: the section reads the market beta shown in Exposures against a second market, so it sits with the three panels that qualify the Exposures betas, after them (it is a secondary, quick view), and before Return contribution.
4. SC7: add the owner row `world beta`: `analytics/world_beta.py`, `report/sections/world_beta.py`, `section_hooks/world_beta.py`, `report/panels/world_beta.py`, `tests/test_world_beta.py`, `tests/test_section_world_beta.py`, `tests/test_prices_incremental.py`, `tests/fixtures/sections/world_beta.json`, `frontend/.../sections/WorldBetaPanel.*`; and extend the `api/deps.py`, `api/service.py` and `data/prices.py` permissions of the shrunk row to it.
5. SC6, new item: "A hook may return a section with status `failed` when its extra data cannot be fetched; `None` is only for 'did not run'." (This is what the world beta does; it is the shrunk betas' rule too.)
6. SC2.1 to SC2.5 say each feature owns its React component. The world beta ships only a placeholder (the frame and the reason of a section that is not `ok`); the real panel is built later by someone else.

## 4. Merge notes

- The generated files (`openapi.json`, `types.gen.ts`) and the mock fixture will conflict with the other open branches; follow SC8: take either side and regenerate.
- `schema.py` and `test_schema_contract.py` will conflict with any branch that adds another section; keep both entries and the order of SC4.
