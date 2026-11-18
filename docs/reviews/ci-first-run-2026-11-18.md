# First GitHub CI run, 2026-11-18

Run 44344830729 of `.github/workflows/ci.yml` on pull request #1 (branch `feat/report-ui-feedback`), started 16:14:12Z. Conclusion: **failure**, one failing test, which also caused the `e2e` job to be skipped. Everything else passed. Fix: commit `7877202` on `fix/ci-first-run`.

## Results per job and step

Durations come from the step timestamps in the run (whole seconds, so each is accurate to about one second).

### python (windows-latest): success, 1 min 40 s

| Step | Result | Duration |
|---|---|---|
| Set up job | success | 1 s |
| checkout | success | 8 s |
| setup-uv | success | 7 s |
| `uv sync --locked` | success | 8 s |
| `uv run ruff check` | success | 1 s |
| `uv run pyright` | success | 28 s |
| `uv run pytest -q` | success | 40 s |
| post steps | success | 5 s |

### python (ubuntu-latest): failure, 1 min 1 s

| Step | Result | Duration |
|---|---|---|
| Set up job | success | 1 s |
| checkout | success | 1 s |
| setup-uv | success | 2 s |
| `uv sync --locked` | success | 5 s |
| `uv run ruff check` | success | under 1 s |
| `uv run pyright` | success | 17 s |
| `uv run pytest -q` | **failure** | 31 s |
| post setup-uv | skipped (so the uv cache was not saved for this job) | 0 s |
| post checkout | success | 0 s |

### frontend (ubuntu-latest): success, 1 min 49 s

| Step | Result | Duration |
|---|---|---|
| Set up job | success | 2 s |
| checkout | success | 3 s |
| setup-node (node 26.13.1, npm cache) | success | 4 s |
| setup-uv | success | under 1 s |
| `npm ci` | success | 60 s (434 packages) |
| `npm run typecheck` | success | 3 s |
| `npm run lint` | success | 4 s |
| `npm test` | success | 17 s (25 files, 361 tests) |
| `npm run build` | success | 4 s |
| `uv sync --locked` | success | 5 s |
| OpenAPI dump | success | 2 s |
| `npm run gen:types` | success | 1 s |
| `git diff --exit-code frontend/src/api` | success | under 1 s |
| post steps | success | 3 s |

The types-staleness check passes: the committed OpenAPI document and generated types match the backend models.

### e2e: skipped

`needs: [python, frontend]` and the Ubuntu python job failed, so no step ran. It was verified locally instead (see below).

## Failure

**Job python (ubuntu-latest), step `uv run pytest -q`, test `test_fixture_matches_builder`** (`backend/factordesk/tests/test_report.py`).

```
>       assert load_report(FIXTURE) == build_mock_report()
E       AssertionError: assert FactorReport(...be revised.'}) == FactorReport(...be revised.'})
```

The log is cut short because the step runs `pytest -q`, so the field that differs is not in the CI log. It was found by reproducing the failure on Linux (see below).

**Root cause.** The mock report builder computes two-sided p-values with `math.erfc`. That function comes from the platform C library, and glibc (Ubuntu) and the Windows runtime return values that differ in the last bit. The committed fixture `mock_report.json` was generated on Windows, and the test compares it to the builder output with exact float equality. Differences found, all in `regression.factors[*].p`, `p_adj_bh` and the same fields of `five_day_regression`, for example:

```
.regression.factors[1].p  1.8383095009416143e-43  1.838309500941614e-43
.regression.factors[2].p  0.22076751334715763     0.22076751334715766
.regression.factors[4].p  0.5291064416254863      0.5291064416254861
```

No other field differed. Random numbers (`random.Random.gauss`) and the sine waves in the builder match on both platforms. The statistics code is not involved: only the test builder was affected.

**Fix, commit `7877202`.** `_p_from_z` in the test builder now rounds to 12 significant digits (`float(f"{...:.12g}")`), and the fixture was regenerated from the builder. The check still compares the whole report exactly; only the unportable last bits of a synthetic number were removed. The rendered sample `docs/samples/mock_report.html` was not regenerated (the p-values change only at the 12th digit).

## The 205 deselected tests

`pyproject.toml` sets `addopts = "-m 'not live and not slow'"`. Collected with the markers: 3 `live` tests (network: Yahoo and the French library) and 202 `slow` tests (Monte Carlo and seed sweeps). The workflow runs the default selection (505 tests) and no job calls the network, as the workflow comment says. The slow tests are not run in CI. Running them on every pull request would add several minutes, so this was left as is; it is an owner decision whether to add a scheduled or manual job for `-m slow`.

## Cache behaviour on this first run

| Cache | Result |
|---|---|
| uv (windows python) | miss, then saved (key `setup-uv-1-x86_64-pc-windows-msvc-3.12.10-...`) |
| uv (ubuntu python) | miss, not saved (post step skipped after the failure) |
| uv (frontend) | miss |
| npm (frontend) | miss (`npm cache is not found`), saved by the post step |
| Playwright browsers | not reached (e2e skipped) |

Observation: the Ubuntu uv cache key contains Python `3.14.4` although `UV_PYTHON` is 3.12 and the job used CPython 3.12.16. The key reflects the interpreter that setup-uv finds first, so the key is stable but not tied to 3.12. It does not cause a miss or a wrong restore, so it was left alone. The runs on Ubuntu also logged an annotation that `ubuntu-latest` moves to Ubuntu 26 from 2026-10-19 and that the pinned actions run on Node 24 instead of Node 20. Neither failed anything.

A second run is needed to see the warm-cache durations and the hit path of the Playwright cache step.

## Verification done locally

| Check | Environment | Result |
|---|---|---|
| ruff, pyright, `pytest -q` | Windows, Python 3.13 (local venv) | clean, 505 passed, 205 deselected |
| `pytest -vv -k test_fixture_matches_builder` before the fix | Linux container (`uv` image, Python 3.12.12, Debian glibc) | failed, same assertion as CI |
| field-by-field diff of fixture and builder | same container | only the p-value last bits above |
| full `pytest -q` after the fix | same container, Python 3.12 | 505 passed, 205 deselected |
| e2e job steps in order: `uv sync --locked`, `npm ci`, `npm run build`, `npx playwright install --with-deps chromium`, `npm run e2e` with `CI=true` | Linux container (`node:26-bookworm`, Node 26.13.1, uv installed by the official script) | smoke test passed (1 passed, 16 s), Chromium headless shell downloaded |

## Not verified locally

- The e2e job on a real GitHub runner: the container is Debian bookworm, the runner is Ubuntu, so system library details can still differ. The Playwright cache steps (`cache-hit` true and false branches) cannot run in a container.
- Warm-cache timings and the cache keys on a second run.
- The Windows job after the fix: it passed before the fix and the change is a rounding in test code, but it was only run with the local Windows Python 3.13, not 3.12.10.
- The `actions/upload-artifact` step for screenshots (`frontend/shots/`).

All of this needs one more CI run on the pushed `fix/ci-first-run` change.
