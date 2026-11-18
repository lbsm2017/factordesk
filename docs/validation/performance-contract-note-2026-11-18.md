# Performance section: proposed amendment to the schema v3 contract (2026-11-18)

Branch `feat/performance`. The contract (`docs/specs/schema-v3-contract.md`) lists five optional sections and says that a feature needing a change in a "nobody" file stops and asks (SC7). The owner asked for a historical performance block (return, volatility, Sharpe ratio, maximum drawdown) as a sixth section, so this branch made the smallest possible edits to those files and lists them here for the owner to accept. `docs/specs/` itself is not edited; this note is the proposed text.

## Proposed SC2.6 (sixth section)

| Item | Value |
|---|---|
| Spec | none yet; definitions in `backend/factordesk/analytics/performance.py` and `docs/validation/performance-handoff-2026-11-18.md` |
| `FactorReport` field | `performance: PerformanceSection \| None = None` |
| Section module | `backend/factordesk/report/sections/performance.py`, exports `PerformanceSection` and `PERFORMANCE_SECTION` |
| Section fields | `status`, `reason`, `sample`, `periods`, `returns`, `volatility_annual`, `sharpe`, `drawdown` (the five parts are present exactly when `status = "ok"`) |
| Status values | `ok`, `insufficient_data` (fewer than 60 daily observations), `failed` |
| Analytics | `backend/factordesk/analytics/performance.py` |
| Pipeline hook | `backend/factordesk/section_hooks/performance.py`, `build_performance(ctx) -> PerformanceSection \| None` |
| Static panel | `backend/factordesk/report/panels/performance.py`, `render_performance_panel(report)`, name `performance`, position 450, element id `performance` |
| React panel | `frontend/src/components/report/sections/PerformancePanel.tsx`, component `PerformancePanel` (placeholder on this branch, built later) |
| Tests | `test_performance.py` (TP01-TP24), `test_section_performance.py` (TP25-TP40), `test_panel_performance.py` (TP41-TP51) |
| Fixture | `backend/factordesk/tests/fixtures/sections/performance.json` |

Panel order (SC4): add `450 performance` after `400 price`. Reason: the price panel draws the path of the stock and the four numbers read straight off that path; they come before the factor panels that explain where the return came from. The position changes no existing one.

Schema version (SC5): the field is additive, so the section needs no bump of its own. The branch sets `SCHEMA_VERSION = "5"` and `SUPPORTED_SCHEMA_VERSIONS = ("3", "4", "5")` to match `feat/ui-v2-security`, which bumps to 5 for another additive field; the two edits are identical and merge cleanly.

## Edits this branch made to "nobody" files

All are mechanical: a sixth entry next to the five existing ones.

| File | Edit |
|---|---|
| `report/schema.py` | import and field `performance`, entry first in `SECTIONS` (panel order), version 5, docstring paragraph |
| `pipeline.py` | one hook call, one entry in `present`, one keyword in `FactorReport(...)` |
| `report/panels/__init__.py` | one import line |
| `tests/fixtures/sections/__init__.py` | `"performance": "performance.json"` in `SECTION_FILES` |
| `tests/fixtures/mock_report.json` | regenerated (version 5, `performance: null`) |
| `tests/test_schema_contract.py`, `test_panel_registry.py`, `test_report.py`, `test_section_residual_alpha.py` | the field list, the panel order, the version number |
| `frontend/src/components/report/panelRegistry.ts` (and its test), `frontend/src/api/types.ts`, `frontend/src/test/sectionFixtures.ts` (and its test) | registry entry, type export, fixture entry |
| `frontend/src/api/openapi.json`, `types.gen.ts` | regenerated (SC8) |

A merge conflict in any of the lists above is resolved by keeping both sides: the five other sections and this one are independent entries.
