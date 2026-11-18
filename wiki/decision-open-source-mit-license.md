# Decision: open source under the MIT license

Date: 2026-11-18
Status: Decided

## In one sentence

factordesk is released under the MIT License, a short permissive license that lets anyone use, change and share the code if they keep the copyright notice.

## What we decided

- The code is licensed MIT, with the notice "Copyright (c) 2026 factordesk contributors".
- Contributors agree that their contributions are released under the same license (stated in `CONTRIBUTING.md`).
- The license covers our code only. The Ken French library and Yahoo Finance data stay under their providers' own terms, and users must follow them.

## Why

The owner asked on 2026-11-18 to compare MIT and Apache-2.0; both are permissive. Apache-2.0 adds an explicit patent grant with a patent-retaliation clause, a NOTICE-file and changed-files requirement, and an explicit no-trademark clause, and it is incompatible with GPLv2. We rejected Apache-2.0 because factordesk is standard econometrics (OLS, Newey-West errors, Euler risk decomposition) on public data, so patent exposure is low and its main advantage matters little. MIT is short, is the common default for Python data tools, and lets people reuse a function without reading four pages. The copyright line reads "factordesk contributors", so no personal name or email is published. The sources do not discuss copyleft licenses; we did not choose one because the project has no stated aim to force changes to be shared (our reading).

## How it works

- Anyone may use, copy, modify, merge, publish, distribute, sublicense and sell the software, provided the copyright and permission notice stay in all copies.
- The software is provided "as is", with no warranty. Neither MIT nor Apache-2.0 limits liability for investment decisions, so the README is to carry a separate not-investment-advice note (pending: the README is to be rewritten, and it has no such note as of 2026-11-18).
- Example: a company may embed factordesk in an internal tool without sharing its changes, provided it keeps the notice.
- Dependencies keep their own licenses; we have not recorded a license audit of dependencies as of 2026-11-18.

## What it costs us

- Others can build closed, commercial products from our code without giving anything back.
- MIT has no patent grant. If someone contributes code covered by their patent, MIT is less explicit than Apache-2.0.
- Strong liability disclaimers do not replace clear statements in the README and reports that results are descriptive and not advice.
- A change to another license later would need agreement from every contributor.

## What would change our mind

Corporate contributors arriving, the name becoming commercially important, a contributor or user with a legal need for a patent grant, or a dependency whose license cannot be combined with MIT.

## Sources

- [LICENSE](../LICENSE)
- [CONTRIBUTING.md](../CONTRIBUTING.md), "License" and "Data and terms".
- [docs/references.md](../docs/references.md), data terms and credit.
- MIT text: <https://opensource.org/license/mit>

## Related decisions

- [Project name: factordesk](decision-project-name-factordesk.md)
- [No data and no secrets in the repository](decision-no-data-and-no-secrets-in-the-repo.md)
- [Branches and pull requests](decision-branches-and-pull-requests.md)
