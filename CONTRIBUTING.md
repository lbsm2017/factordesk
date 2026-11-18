# Contributing to factordesk

Thanks for helping. Bug reports, statistical review, documentation fixes and new features are all
welcome. This page covers how to get set up and what a good pull request looks like.

## Ways to contribute

- **Report a bug.** Open an issue with the ticker, the command you ran, the output you got and
  the output you expected. Include your operating system and `uv --version`.
- **Challenge a number.** If a statistic looks wrong, open an issue with a small reproducible
  case. Methodology problems are as valuable as code bugs. The definitions live in
  `docs/methodology.md`.
- **Suggest a feature.** Open an issue describing the problem first, not only the solution.
  Check `docs/PLAN.md` for what is planned and what is deferred.
- **Send a pull request.** For anything larger than a small fix, open an issue first so we can
  agree on the approach.
- **Security problems.** Do not file a public issue. Follow [SECURITY.md](SECURITY.md).

## Set up

factordesk works on Windows, macOS and Linux. You only need
[uv](https://docs.astral.sh/uv/getting-started/installation/) and git.

```bash
git clone <repo-url>
cd factordesk
uv sync
```

`uv sync` installs Python 3.12 and every pinned dependency. Copy `.env.example` to `.env` only if
you need to override settings.

## Before you open a pull request

All three commands must pass:

```bash
uv run ruff check .
uv run pyright
uv run pytest
```

The default test run is offline and fast. Tests that call the Ken French library or Yahoo Finance
carry the `live` marker. Run them when you change the data layer:

```bash
uv run pytest -m live
```

CI runs the offline suite on Windows, macOS and Linux, so avoid anything platform-specific:
use `pathlib` for paths, open text files as UTF-8, and do not add shell scripts.

## Code and statistics rules

The full list is in [CODING_STANDARDS.md](CODING_STANDARDS.md). The ones that matter most:

- **No look-ahead.** Every result stamped at date t may use only data up to and including t. No
  negative shifts, no centred windows. New rolling or regime features need a test that proves it.
- **Units.** Returns are decimals (0.01 is 1%), daily and simple. Alphas are annualised and
  labelled as such.
- **Never hide data problems.** Do not drop rows or fill missing values with zero silently.
  Report what was excluded and why.
- **Every statistic carries its sample size and date range**, and says whether it is in-sample.
- **Pure functions with typed inputs and outputs** for analytics. The API exposes only the
  pydantic models in the schema.
- **New statistic means three things:** the code, a test with a known answer (a synthetic dataset
  or an algebraic identity), and an entry in `docs/methodology.md`.
- **No data and no secrets in the repository.** `data/`, `.env` and parquet files are gitignored.
  Keep it that way.

## Branches and pull requests

| Branch | Purpose |
|---|---|
| `prod` | Released code. Every commit here is a release candidate that passed review and CI. Releases are tagged `vX.Y.Z`. |
| `dev` | Integration branch. All finished work lands here first. |
| `feat/<topic>` | A new feature, branched from `dev`. |
| `fix/<topic>` | A bug fix, branched from `dev`. |

Rules:

- Nobody commits directly to `prod` or `dev`. Every change goes through a pull request.
- Branch from `dev`, keep the branch short-lived, and open the pull request against `dev`.
  Name branches in lowercase with hyphens: `feat/rolling-drift-alerts`, `fix/pence-quoted-tickers`.
- A pull request needs a passing CI run and the maintainer's approval before it is merged. Only
  the maintainer merges. Feature and fix branches are squash-merged into `dev`.
- Releases are a pull request from `dev` into `prod`, merged with a merge commit and then tagged.
- An urgent fix for released code branches from `prod` as `fix/<topic>`, goes into `prod` by pull
  request, and is then merged back into `dev` so the branches do not drift.

## Pull request checklist

- [ ] The pull request targets `dev` (or `prod` for a release or hotfix).
- [ ] The change is focused and the description says why it is needed.
- [ ] `ruff`, `pyright` and `pytest` pass locally.
- [ ] New behaviour has tests, including the edge cases (empty input, missing data, short history).
- [ ] Docs updated if behaviour, units or definitions changed.
- [ ] If the change touches the report or dashboard: screenshots in light and dark at desktop
      and phone widths.

Keep commits small and write messages in the imperative ("Add HAC lag rule", not "Added").
A maintainer will review; expect questions about the statistics as well as the code.

## Data and terms

factordesk downloads data at runtime from the Ken French Data Library and Yahoo Finance
(through yfinance). Contributors and users are responsible for following those providers' terms.
Do not commit downloaded data, cached files or screenshots that contain licensed data beyond what
the terms allow.

## License

By contributing you agree that your contribution is released under the project's
[MIT License](LICENSE).
