# Security policy

## Supported versions

Security fixes go into the latest release only. Update to the newest version before reporting.

## Report a vulnerability

Do not open a public issue for a security problem.

Use GitHub's private reporting instead: open the **Security** tab of this repository and choose
**Report a vulnerability**. Include:

- what you found and where (file, function or endpoint)
- steps or a minimal input that reproduces it
- the impact you expect (for example: file write outside the cache folder, code execution,
  leaked key)
- your operating system and factordesk version

You can expect an acknowledgement within 7 days and a status update within 30 days. If the report
is valid, we fix it, publish a patched release and credit you in the release notes unless you
prefer to stay anonymous.

## What counts as a security issue

In scope:

- Reading or writing files outside the configured cache folder (path traversal through a ticker
  or any other input).
- Code execution or crashes from a crafted download (a malformed Ken French zip or CSV, a
  decompression bomb) or a crafted API request.
- Secrets in the repository, logs or generated reports.
- Cross-site scripting in the generated HTML report or the dashboard.
- Dependencies with a known vulnerability that affects factordesk.

Out of scope:

- Wrong numbers or statistical disagreements. Open a normal issue with a reproducible example.
- Outages or format changes at Ken French's Data Library or Yahoo Finance.
- Findings that need an attacker who already controls your machine or your `.env` file.

## How factordesk handles risky inputs

- Tickers are checked against a strict pattern before they reach a request or a file name.
- Factor data is downloaded over HTTPS, read in memory only (the zip is never extracted to disk),
  size-capped, validated against the expected columns, and written atomically. A failed download
  keeps the previous cache.
- All text in the generated HTML report is escaped, and the report loads no external scripts,
  styles or fonts.
- API keys (for the optional future Alpaca adapter) are read from `.env`. That file is
  gitignored, and the repository ships only `.env.example` with empty values.
- No market or factor data is stored in this repository.

## For contributors

Never commit keys, tokens or `.env` files. If you committed one by mistake, treat it as leaked:
revoke it at the provider first, then tell the maintainers.
