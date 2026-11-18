# Decision: no data and no secrets in the repository

Date: 2026-11-18
Status: Decided

## In one sentence

factordesk downloads market and factor data when it runs and keeps it in an ignored local folder, and keys live only in a local `.env` file that is never committed.

## What we decided

- Data from the Ken French library and Yahoo Finance is downloaded at run time. The `data/` folder, `.env`, parquet files and logs are listed in `.gitignore`.
- The repository ships only `.env.example`, with placeholder names and no real values.
- Secrets are read from `.env` through one configuration module. No keys, tokens or personal paths in code, tests, fixtures or logs.
- Security reports go through GitHub's private reporting, described in `SECURITY.md`.

## Why

Publishing the repository openly means anything committed is public forever. We rejected bundling data because both providers have their own terms of use, the library asks users to follow them and to credit its authors, and, in our reading, a stored copy would go stale as the library revises history. We rejected a committed `.env` or in-code keys because a leaked key must be revoked and cannot be un-published. We rejected relying on contributors' memory: ignore rules and a written policy do the work.

## How it works

- The ignore file contains `.env`, `/data/`, `*.parquet`, `/logs/` plus caches and `node_modules`.
- Factor zips are read in memory and never extracted to disk. A failed download keeps the previous cache. Tickers are checked against a strict pattern before they reach a file name, to prevent path traversal.
- The generated report escapes text and loads no external scripts, styles or fonts.
- If a key is committed by mistake, treat it as leaked: revoke it at the provider first, then tell the maintainers.
- The Alpaca keys in `.env.example` are placeholders only; v1 does not call Alpaca.

## What it costs us

- First runs need internet and take longer.
- Tests that need real data are marked `live` and skipped by default; offline tests rely on synthetic or frozen fixtures.
- Reproducing an old report needs the data vintage. The dataset design keeps raw downloads locally; that is a plan, not yet built as of 2026-11-18.
- The sample report files in `docs/samples/` contain derived numbers from licensed data; the terms for that are not spelled out in the sources and should be confirmed by the owner.
- The ignore rule protects only what is committed; it cannot stop someone pasting a key into an issue.

## What would change our mind

A provider that permits redistribution and offers a stable snapshot, which could allow small bundled test fixtures; or a hosted version that needs a different secrets setup.

## Sources

- [SECURITY.md](../SECURITY.md)
- [CONTRIBUTING.md](../CONTRIBUTING.md), "Data and terms" and the rules list.
- [CODING_STANDARDS.md](../CODING_STANDARDS.md), section 7.
- [docs/references.md](../docs/references.md), terms of use.
- [docs/methodology-datasets.md](../docs/methodology-datasets.md), D4 (local cache layout).

## Related decisions

- [Factor data source](decision-factor-data-source-french-library.md)
- [Prices from Yahoo with adjusted-close care](decision-prices-from-yahoo-with-adjusted-close-care.md)
- [Open source under the MIT license](decision-open-source-mit-license.md)
