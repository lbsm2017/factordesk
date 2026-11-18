# Decision: branches and pull requests

Date: 2026-11-18
Status: Decided

## In one sentence

Released code lives on `prod`, finished work is collected on `dev`, each change is made on a short-lived `feat/` or `fix/` branch, and only the maintainer approves and merges pull requests.

## What we decided

- `prod` holds released code, tagged `vX.Y.Z`. `dev` is the integration branch. `feat/<topic>` and `fix/<topic>` branch from `dev`.
- Nobody commits straight to `prod` or `dev`. Every change goes through a pull request with a passing CI run and the maintainer's approval.
- Only the maintainer merges. Feature and fix branches are squash-merged into `dev`; a release is a pull request from `dev` to `prod`, merged with a merge commit and then tagged.
- An urgent fix for released code branches from `prod`, goes into `prod` by pull request, and is merged back into `dev`.

## Why

Two long-lived branches give a stable place for released code and a place to test the combination of changes before release. We rejected committing directly to the main line because a published research tool needs review of both code and statistics. The owner set this model on 2026-11-18. Open merging by any contributor is excluded because the owner reviews numbers as well as code; the guide warns contributors to expect statistical questions in review. GitHub does not let a pull-request author approve their own pull request, so the remote should require a pull request and passing CI with zero required approvals, and only the owner merges. A local pre-commit hook blocks direct commits on `prod` and `dev` after the first commit. The sources do not discuss alternatives such as a single `main` branch.

## How it works

- Example: a contributor adds drift alerts on `feat/rolling-drift-alerts`, opens a pull request against `dev`, CI and the maintainer approve, and it is squash-merged as one commit.
- Before opening a pull request, `ruff`, `pyright` and `pytest` must pass. New behaviour needs tests, and docs must be updated when units or definitions change.
- The checklist also asks for screenshots in light and dark, at desktop and phone widths, when the change touches the report.
- Branch names use lowercase and hyphens.

## What it costs us

- The maintainer is a bottleneck: every merge waits for one person.
- Squash merges lose the detailed history of a branch.
- Two long-lived branches can drift if hotfixes are not merged back.
- Not documented as of 2026-11-18: whether the remote rule (pull request plus passing CI, zero required approvals) and the pre-commit hook are in place, and whether CI is configured. The rules are a written policy.

## What would change our mind

More than one trusted maintainer, a release cadence that makes a separate `dev` branch pointless, or a review queue that blocks contributors for weeks.

## Sources

- [CONTRIBUTING.md](../CONTRIBUTING.md), "Branches and pull requests" and the checklist.
- [CODING_STANDARDS.md](../CODING_STANDARDS.md): rules reviewers apply.
- [docs/PLAN.md](../docs/PLAN.md), Definition of Done.

## Related decisions

- [Independent validation and mutation testing](decision-independent-validation-and-mutation-testing.md)
- [Python and uv for every platform](decision-python-and-uv-for-every-platform.md)
- [Open source under the MIT license](decision-open-source-mit-license.md)
