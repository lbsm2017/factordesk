# Decision: making the repository public

Date: 2026-11-20
Status: Decided

## In one sentence

Before the repository on GitHub became public, we searched the whole history for names, secrets and data that should not be published, chose the licence, recorded the terms of every data source, and wrote a checklist for the switch.

## What we decided

- The repository becomes public with its full history. We do not rewrite history.
- A search of the whole history found no employer or client name, no secret and no data file, so there was nothing to remove.
- Commits carry the owner's personal email address. We keep them as they are; new commits can use GitHub's private `noreply` address.
- The licence changed from MIT to a noncommercial licence before the switch, while every commit was still the owner's ([decision](decision-noncommercial-license.md)).
- Third-party parts are listed in [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md): the bundled libraries and the fonts (SIL Open Font License).
- The README says plainly who may use factordesk for free, how to ask for commercial use, and that downloaded data stays under each provider's terms.
- Lorenzo Bassetti is named as the creator in `LICENSE`, `CITATION.cff`, `pyproject.toml` and the README, at the owner's request. The README and the licence file give one contact address for commercial requests, chosen by the owner.

## Why

A public repository can be copied, cached and indexed as soon as it opens, and its full history comes with it. Anything wrong has to be found before the switch, not after. Rewriting history breaks every clone and pull request, so we do it only when something must go. The search found nothing that must go.

## What was checked (2026-11-20)

| Check | Scope | Result |
| --- | --- | --- |
| Company and client names | Every tracked file including binaries, all 2,429 file versions in the history of every branch, file names, commit messages, branch and tag names, GitHub issues, pull requests and releases | None found |
| Secrets | `.env` files in history; patterns for cloud keys, GitHub tokens, API keys and private keys | None found |
| Data | Price, factor and parquet files in history | None; test fixtures are synthetic |
| Local paths | Paths into the owner's home folder | Found in four files; removed |
| Licences of dependencies | Python and JavaScript lockfiles | All runtime dependencies permissive ([audit](decision-open-source-mit-license.md)) |
| Data terms | FRED, ECB, SNB added to [docs/references.md](../docs/references.md#data-sources-and-licences) | FRED and ECB: free with citation; SNB: non-commercial; SARON: licensed by SIX |

## The public release

Version 1.0.0, tagged `v1.0.0` on `prod` on 2026-11-21, is the commit that goes public. Earlier versions (0.1.0 to 0.5.0) were private development releases.

## Publish checklist

1. Merge the release to `prod`, tag it and publish a GitHub release (the newest release on GitHub was still 0.1.0).
2. Delete branches that are already merged; keep `prod` and `dev`.
3. Set the description, topics and social preview image.
4. Turn on private vulnerability reporting (SECURITY.md depends on it), secret scanning with push protection, Dependabot alerts, and branch protection on `prod` and `dev`.
5. Switch the visibility to public.

## What it costs us

- The personal email address in old commits is public.
- Every design note, review and sprint record in `docs/` and `wiki/` becomes public. They contain no private data, but they show how the work was done, including mistakes.

## What would change our mind

A secret, client name or licensed dataset found in history. Then we would rewrite history before the switch, rotate the secret, and record it here.

## Related decisions

- [A noncommercial licence, with commercial use by consent](decision-noncommercial-license.md)
- [No data and no secrets in the repository](decision-no-data-and-no-secrets-in-the-repo.md)
- [Branches and pull requests](decision-branches-and-pull-requests.md)
