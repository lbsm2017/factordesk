# Decision: open source under the MIT license

Date: 2026-11-18
Status: Superseded on 2026-11-20 by [A noncommercial licence, with commercial use by consent](decision-noncommercial-license.md). The repository was never public under MIT. The text below is kept as the record of the earlier choice.

## In one sentence

factordesk is released under the MIT License, a short permissive license that lets anyone use, change and share the code if they keep the copyright notice.

## What we decided

- The code is licensed MIT, with the notice "Copyright (c) 2026 factordesk contributors". (Changed on 2026-11-20: see the update below.)
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

## Update 2026-11-20: licence check, then a new licence

- **Dependencies audited.** Every runtime dependency is permissive (MIT, BSD, Apache-2.0, ISC, 0BSD). The Python package certifi is MPL-2.0 and is used unchanged, which MPL allows. MPL-2.0 (lightningcss, axe-core) and CC-BY-4.0 (caniuse-lite) appear only in development tools and are not shipped. No copyleft code is in the product.
- **Third-party notices.** The wheel ships a compiled page that contains ECharts (Apache-2.0), so its NOTICE must travel with it. [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) lists the bundled packages, the OFL fonts and the ECharts notice, and `pyproject.toml` ships it with the licence in the package.
- **Named creator.** The owner asked to be named as the creator. The copyright line names Lorenzo Bassetti and factordesk contributors, and the same name is in `CITATION.cff`, `pyproject.toml` and the README. This replaces the 2026-11-18 choice of "factordesk contributors" alone.
- **MIT replaced.** The same day the owner decided that commercial use must need his consent, which MIT does not provide. The licence is now the factordesk Noncommercial License 1.0; see [the new decision](decision-noncommercial-license.md).

## Related decisions

- [A noncommercial licence, with commercial use by consent](decision-noncommercial-license.md)
- [Making the repository public](decision-going-public.md)

- [Project name: factordesk](decision-project-name-factordesk.md)
- [No data and no secrets in the repository](decision-no-data-and-no-secrets-in-the-repo.md)
- [Branches and pull requests](decision-branches-and-pull-requests.md)
