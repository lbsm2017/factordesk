# Decision: Python and uv for every platform

Date: 2026-11-18
Status: Decided

## In one sentence

The only thing a person needs to install is uv, which then fetches the right Python and every pinned library the same way on Windows, macOS and Linux.

## What we decided

- uv is the only prerequisite. `uv sync` creates a local environment, installs Python 3.12 if missing, and installs pinned versions from `uv.lock`.
- The project requires Python 3.12 or newer. Checks run as `uv run pytest`, `uv run ruff check .` and `uv run pyright`.
- No make files, no conda, no system Python requirement, and no shell scripts for development. The only scripts are the two user-facing bootstrap scripts in `scripts/` (see "As of commit ce931c7" below).

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

## As of commit ce931c7 (2026-11-18): one-shot install

Built and tested locally; not yet published, because PyPI and a tagged release do not exist yet.

- **The wheel carries the dashboard.** `npm --prefix frontend run build:package` builds the page and copies it to `backend/factordesk/web/` (gitignored). The wheel includes that folder, the report stylesheet and the fonts; tests are left out. A small hatch hook (`hatch_build.py`) stops a wheel build when the page is missing, so a silent wheel without a dashboard cannot happen. We chose a documented two-step build over a hook that runs Node: someone building from the source archive may not have Node, and the failure we fear is a missing page, which the hook catches.
- **Where `serve` looks.** `--static DIR` first; otherwise `frontend/dist` in a checkout if it has an `index.html`, else the packaged `factordesk/web`. In a wheel with no page, the error says to reinstall instead of naming npm.
- **Clean-machine test, 2026-11-18.** Wheel 522,285 bytes, 53 files (the source archive is 601,144 bytes). Installed into a fresh Python 3.12 environment outside the repository: `factordesk --help` worked, `factordesk serve` answered `/api/health` and `/` (200, page security headers), all five page scripts and styles and the four fonts answered 200, and the report renderer read its stylesheet and fonts from the installed package. This needed no network for those requests. Not tested: a report or dashboard query with live Yahoo and French library data from the wheel.
- **Bootstrap scripts.** `scripts/install.sh` and `scripts/install.ps1` install uv only if missing, using uv's official installer at a pinned uv version (<https://docs.astral.sh/uv/getting-started/installation/>), saved to a file and never piped. They then run `uvx --from factordesk==VERSION factordesk serve --open`. The version is a required argument. They print their plan first and support a dry run. The owner publishes a SHA-256 for each script (a `SHA256SUMS` file on the release) and the script can check itself against it; this catches a damaged or swapped copy but not a compromised release page. Our docs never show an unpinned `curl | sh`.
- **Open points.** The default uv version in the scripts (0.11.28) is the one on the owner's machine; whether its installer URL exists on astral.sh was not checked offline. The scripts have been run only as dry runs (`bash`, `dash`, Windows PowerShell 5.1); a real install on a machine without uv was not run.
- Release steps for the owner: [docs/release-checklist.md](../docs/release-checklist.md).

## Sources

- [README.md](../README.md), "Setup".
- [pyproject.toml](../pyproject.toml): Python version, dependencies, tool settings.
- [CONTRIBUTING.md](../CONTRIBUTING.md), "Set up" and "Before you open a pull request".
- [docs/release-checklist.md](../docs/release-checklist.md), [docs/dashboard.md](../docs/dashboard.md) ("Install without cloning"), `scripts/install.sh`, `scripts/install.ps1`, `hatch_build.py`.
- [docs/PLAN.md](../docs/PLAN.md), "Environment findings".
- uv documentation: <https://docs.astral.sh/uv/>

## Related decisions

- [Branches and pull requests](decision-branches-and-pull-requests.md)
- [No data and no secrets in the repository](decision-no-data-and-no-secrets-in-the-repo.md)
- [Open source under the MIT license](decision-open-source-mit-license.md)
