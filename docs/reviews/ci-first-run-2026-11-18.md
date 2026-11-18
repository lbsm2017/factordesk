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

## Second run, 2026-11-18

Run 44349295423 of `.github/workflows/ci.yml` on pull request #1, with the fix `7877202` pushed. Started 16:37:06Z, finished 16:40:36Z (3 min 30 s wall time). Conclusion: **success, all four jobs green**. No change to the code or the workflow was needed. This is the first time the real e2e job ran on GitHub.

### Results per job

Durations come from the job and step timestamps (whole seconds, each accurate to about one second).

| Job | Result | Duration | First run |
|---|---|---|---|
| python (ubuntu-latest) | success | 1 min 12 s | failure, 1 min 1 s |
| python (windows-latest) | success | 2 min 5 s | success, 1 min 40 s |
| frontend | success | 1 min 44 s | success, 1 min 49 s |
| e2e | success | 1 min 19 s | skipped |

The jobs python and frontend ran in parallel, e2e started at 16:39:17Z when the slowest of them (Windows) ended, so the Windows job sets the wall time.

Step durations that matter:

| Job | Step | Duration |
|---|---|---|
| python (ubuntu) | `uv sync --locked` | 5 s |
| python (ubuntu) | `uv run pyright` | 25 s |
| python (ubuntu) | `uv run pytest -q` | 34 s (519 passed, 205 deselected, 33.27 s in pytest) |
| python (windows) | `uv sync --locked` | 7 s |
| python (windows) | `uv run pyright` | 46 s |
| python (windows) | `uv run pytest -q` | 53 s (519 passed, 205 deselected, 48.51 s in pytest) |
| frontend | `npm ci` | 39 s (60 s on the first run) |
| frontend | `npm test` | 22 s (25 files, 361 tests passed) |
| frontend | typecheck, lint, build | 5 s, 5 s, 5 s |
| frontend | OpenAPI dump, `gen:types`, `git diff --exit-code frontend/src/api` | 3 s, 1 s, under 1 s (types still match the backend) |
| e2e | `uv sync --locked` | 6 s |
| e2e | `npm ci` | 19 s |
| e2e | `npm run build` | 4 s |
| e2e | Playwright cache step | under 1 s (miss) |
| e2e | `npx playwright install --with-deps chromium` | 18 s |
| e2e | `npm run e2e` | 9 s (1 test passed, 7.5 s in Playwright) |
| e2e | upload screenshots (`e2e-shots`) | 1 s |

The same 519 tests pass on Ubuntu and Windows, which matches a local collection on this branch (519 selected of 724); the 505 in the first-run local checks came from an earlier base commit. The 205 deselected tests are the 202 `slow` and 3 `live` tests (see the recommendation below).

### Cache behaviour

| Cache | Ubuntu python | Windows python | frontend | e2e |
|---|---|---|---|---|
| uv (`setup-uv`, key from `uv.lock`) | hit | hit | hit | hit |
| npm (`setup-node`, key from `package-lock.json`) | not used | not used | hit, 68 MB | hit, 68 MB |
| Playwright browsers (`actions/cache`, `~/.cache/ms-playwright`) | not used | not used | not used | **miss**, saved 307 MB (about 5 s upload in the post step) |

- The first run saved the uv caches on Windows and Ubuntu (frontend) and the npm cache; this run restored them. `npm ci` went from 60 s to 39 s in the frontend job, with the npm cache restore at about 1 s.
- The uv cache is tiny: the log shows "Cache Size: ~0 MB (100633 B)". The restore therefore saves almost no time, and `uv sync --locked` still takes 5 to 7 s. This is how `setup-uv` behaves by default (it prunes pre-built wheels from the saved cache). It costs nothing, so it was left alone.
- The Playwright cache step ran for the first time and, as expected, missed (`Cache not found for input keys: playwright-Linux-<hash of package-lock.json>`). The miss branch ran `npx playwright install --with-deps chromium` (downloaded Chrome for Testing 159.0.8154.6, FFmpeg and the headless shell), the "Install system libraries only" step was skipped, and the post step saved the cache. The **hit branch has still not run on GitHub**: it needs a third run with an unchanged `frontend/package-lock.json`. The expected saving is the browser download (about 14 s of the 18 s install step); the apt part of `--with-deps` is then done by the `install-deps` step.

### e2e job

The job passed on its first real run: `npm run e2e` ran `playwright test --grep-invert @shots`, started the fake backend on `127.0.0.1:8848`, and the single test `e2e/smoke.spec.ts` (dashboard smoke on the fake backend) passed in 3.8 s. The screenshot upload step succeeded. The local container run in the first review (Debian bookworm) was therefore a good predictor of the Ubuntu runner.

### Items from "Not verified locally" that are now closed

- The e2e job on a real runner: verified.
- Ubuntu failure fix and the Windows job after the fix (Python 3.12.10 on the runner): verified, both pass.
- Warm-cache durations and keys for uv and npm: verified (above).
- The `actions/upload-artifact` step for `frontend/shots/`: ran and succeeded.

Still open: the Playwright cache hit path (needs a third run, see above).

### Recommendation: nightly workflow for the deselected tests

`pyproject.toml` deselects them by default with `addopts = "-m 'not live and not slow'"`; the markers are `slow` (Monte Carlo and seed sweeps) and `live` (network: French library, Yahoo).

Measured locally on Windows (`uv run pytest -m slow -q --durations=5`): **202 passed in 94 s**. Two tests are 49 of those seconds (`test_regression.py::test_t40_hac_coverage` 30 s, `test_diagnostics.py::test_t120_robust_bg_size_under_garch` 19 s); the rest are under 0.4 s each. The fast suite is about 30 percent faster on the Ubuntu runner than on Windows (33 s against 49 s), so a runner estimate is **about 1 to 1.5 minutes** for the slow tests, plus about 40 s of setup (checkout, setup-uv, `uv sync`). The 3 `live` tests were only collected, not run (they need the network, and Yahoo can rate limit or change); they would take seconds when the services respond.

Recommendation:

1. **Yes, run the slow tests in a scheduled workflow.** They guard the statistical claims (HAC coverage, size under GARCH, structural-break detection) that a quick change can degrade without any fast test noticing, and the cost is about 2 minutes a day of runner time, far below the free allowance. Do not add them to the pull request workflow: they would double the Python job time for little gain. Suggested shape: a separate file `.github/workflows/nightly.yml`, triggers `schedule` (one run a day, off-peak) and `workflow_dispatch`, one job on ubuntu-latest only (the numbers are platform independent, the fixture float issue was a test-builder matter), steps `checkout`, `setup-uv`, `uv sync --locked`, `uv run pytest -m slow -q`, with the same pinned action hashes as `ci.yml`.
2. **Run the live tests in the same scheduled workflow but as a separate job** (`uv run pytest -m live -q`) that is allowed to fail without hiding the slow-test result. They depend on Ken French's site and on Yahoo, so a red result can mean an outside outage. Their purpose is to detect upstream format changes early, which is what a nightly run is good for. Never run them on pull requests.
3. Before enabling, run `pytest -m slow` once on a Linux container to confirm that all 202 pass on glibc (the first run showed that exact-float assumptions can differ by platform), and keep the schedule only on the default branch (GitHub runs schedules from the default branch).

This is a recommendation only; no workflow was added.
