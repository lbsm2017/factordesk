# Shortcuts for people who prefer make. Every target calls a task in pyproject.toml, which also
# works without make on every system: `uv run poe <task>` (`uv run poe` lists them).
# make is not part of Windows; there, use the uv run poe commands or install make.
#
#   make setup              install everything and build the dashboard page
#   make serve [PORT=8000]  start the dashboard and open it
#   make stop  [PORT=8000]  stop the factordesk server on that port
#   make report T=SPY       write an offline report and open it

PORT ?= 8000
T ?= SPY

.PHONY: help setup build serve stop dev report factors refresh-factors test check e2e ci

help: ; @uv run poe --help
setup: ; uv sync && uv run poe setup
build: ; uv run poe build
serve: ; uv run poe serve --port $(PORT)
stop: ; uv run poe stop --port $(PORT)
dev: ; uv run poe dev
report: ; uv run poe report $(T)
factors: ; uv run poe factors
refresh-factors: ; uv run poe refresh-factors
test: ; uv run poe test
check: ; uv run poe check
e2e: ; uv run poe e2e
ci: ; uv run poe ci
