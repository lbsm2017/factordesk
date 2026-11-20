# Decision: a nightly run of the slow and live tests

Date: 2026-11-18
Status: Superseded on 2026-11-20 (see the update at the end)

## In one sentence

A scheduled workflow runs the tests that normal checks skip: the statistical tests, which can fail only over many random draws, and the three tests that call Yahoo and the Ken French library.

## What we decided

- `.github/workflows/nightly.yml` runs every day at 03:17 UTC and can also be started by hand.
- Job `slow` runs `pytest -m slow` (Monte Carlo and seed sweeps, about 200 tests, about 1.5 minutes on Ubuntu as of 2026-11-18). A failure fails the run, and GitHub emails the owner about failed scheduled runs.
- Job `live` runs `pytest -m live` (3 tests). It is allowed to fail, and its summary says whether it passed.
- The workflow can only read the repository and uses no secrets. Two nightly runs never overlap.
- The Kalman simulation tests run at their default replication count. The setting that raises them to the specification's 200 is not on this branch, so the workflow does not use it.
- 2026-11-18 (later, after PR #2 merged into `dev`): the `slow` job sets `FACTORDESK_KB_REPS` to 200 in `.github/workflows/nightly.yml`, so the Kalman simulation tests run at the specification's 200 replications. The previous bullet describes the state before this change. About 11 minutes on a developer machine for the Kalman tests alone; not yet measured on a GitHub runner. The 45-minute limit stays.

## Why

- A statistical test with a fixed seed passes or fails the same way every time. A real fault in a statistic can show up only on some seeds, so the seed sweeps and Monte Carlo checks of [the test oracle](../docs/test-oracle.md) matter, but they are too many to run on every pull request.
- A format change at Yahoo or at the Ken French library breaks nothing in the offline tests, because those use fakes. Only a run against the real services shows it. We rejected running those tests on every pull request because a provider outage would block unrelated work.
- The live job may fail because a network error at a provider is not a bug in our code. A red live job is a prompt to look at the provider, not a reason to stop a merge.

## What it costs

The workflow uses the free minutes included in the GitHub plan (unlimited on standard runners for public repositories; a monthly allowance for private ones). As of 2026-11-18 the slow job takes about 1.5 minutes, so the run uses about 45 minutes a month. The 45-minute and 15-minute limits stop a hung run.

## What we have not verified

As of commit `047baac` (the base of this branch), the workflow has not run on GitHub. It must be merged, then started once with the manual trigger, before we rely on it. See [the CI section of the dashboard document](../docs/dashboard.md#ci).

## Update 2026-11-20: nightly removed, GitHub tests pull requests only

On 2026-11-20 the owner decided that GitHub runs tests for pull requests only, with no nightly run. This followed a day when GitHub Actions refused to start jobs because of a billing block, and every run showed as failed. In the branch `fix/ci-pr-only`:

- `.github/workflows/nightly.yml` is deleted;
- `.github/workflows/ci.yml` runs on pull requests to `dev` and `prod` only, with no push trigger;
- the CI badge is removed from the README, because pull-request-only runs cannot show the state of `prod`.

The slow and live tests now run by hand before each release: `uv run pytest -m slow` and `uv run pytest -m live`. The claims above about the 03:17 UTC schedule are superseded.
