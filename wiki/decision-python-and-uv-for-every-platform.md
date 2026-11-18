# Decision: Python and uv for every platform

Date: 2026-11-18
Status: Decided

## In one sentence

The only thing a person needs to install is uv, which then fetches the right Python and every pinned library the same way on Windows, macOS and Linux.

## What we decided

- uv is the only prerequisite. `uv sync` creates a local environment, installs Python 3.12 if missing, and installs pinned versions from `uv.lock`.
- The project requires Python 3.12 or newer. Checks run as `uv run pytest`, `uv run ruff check .` and `uv run pyright`.
- No make files, no conda, no system Python requirement, and no shell scripts in the repository.

## Why

On the owner's Windows machine on 2026-11-18, Python was not installed (only the Microsoft Store stub existed), but uv was, and uv can install Python without administrator rights. The owner compared make, pixi and uv for the three systems. We rejected a system-Python route because it sends newcomers off to install Python themselves. We rejected make because it is not native on Windows (it needs WSL, Git Bash or a package manager). We rejected pixi for now: it uses conda-forge and can lock Python and Node together, but it is heavy, unfamiliar to most Python contributors and adds a second package ecosystem beside PyPI. uv is one small binary that installs Python itself, locks dependencies and works natively on all three systems. Conda is named as unneeded in the README.

## How it works

- One command, `uv sync`, produces the same environment everywhere because `uv.lock` pins every dependency.
- Install uv once: a `curl` line on macOS and Linux, a PowerShell line on Windows, or `brew` or `winget`.
- CONTRIBUTING.md says CI runs the offline test suite on Windows, macOS and Linux, so contributors use `pathlib`, open files as UTF-8 and avoid shell scripts. Whether that CI is set up yet is not documented as of 2026-11-18.
- Tests that use the network are marked `live` and skipped by default.
- Plan, pending as of 2026-11-18: named dev tasks through poethepoet (a Python task runner that runs through uv); once published on PyPI, users run `uvx factordesk report SPY`; a future dashboard bundle ships inside the package so users never need Node.

## What it costs us

- Contributors must be willing to install uv, a newer tool than pip.
- Our tooling depends on uv's behaviour; a breaking change there affects everyone at once.
- The lock file is large (about 392 KB on 2026-11-18).
- A web frontend (not built as of 2026-11-18) needs Node for development. Shipping its bundle inside the package keeps Node away from users.

## What would change our mind

uv becoming unmaintained or unreliable on one of the three platforms, a dependency that cannot be installed without a system library, or a need for pinned Node, in which case pixi is the upgrade path.

## Sources

- [README.md](../README.md), "Setup".
- [pyproject.toml](../pyproject.toml): Python version, dependencies, tool settings.
- [CONTRIBUTING.md](../CONTRIBUTING.md), "Set up" and "Before you open a pull request".
- [docs/PLAN.md](../docs/PLAN.md), "Environment findings".
- uv documentation: <https://docs.astral.sh/uv/>

## Related decisions

- [Branches and pull requests](decision-branches-and-pull-requests.md)
- [No data and no secrets in the repository](decision-no-data-and-no-secrets-in-the-repo.md)
- [Open source under the MIT license](decision-open-source-mit-license.md)
