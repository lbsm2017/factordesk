# Decision: no citation without verification

Date: 2026-11-18
Status: Decided

## In one sentence

We cite a paper, a dataset or a provider's terms only after we have looked it up in a primary or authoritative source and checked it with a script, and anything we cannot check goes on a visible "unverified" list instead of being quoted from memory.

## What we decided

- Every work that a method rests on is listed in [docs/references.md](../docs/references.md) with authors, year, title, venue, volume, pages and a DOI or stable link, plus the date it was verified.
- The same entries live in [docs/references.bib](../docs/references.bib), one key per work, so the README and other documents can cite by key (for example `fama2015`).
- The script `scripts/check_references.py` asks Crossref about every DOI in the bib file and reports a mismatch in title, year or first author. Run it with `uv run python scripts/check_references.py`.
- A claim that we cannot source is written down under "Unverified citations", with exactly what the repository says and what is missing. We do not fill the gap with a guess, and we do not invent a DOI.
- A spec that quotes a result cites the spec section, not the paper, unless someone has read the paper. The spec's own markers (`[V]` verified, `[U]` unverified) stay.
- [CITATION.cff](../CITATION.cff) at the repository root lets GitHub show "Cite this repository".

## Why

A statistics tool is only as credible as its sources. Before this decision the references page listed five papers and the specs carried their own, differently formatted citations: some with DOIs, some with an author and a year, some with only the name of a test. A reader could not tell which ones had been checked. The checks on 2026-11-18 also found real gaps: a venue marked unknown that is now known (Chung 2024 is in Critical Finance Review), a claim that the Ken French library asks users to follow its terms that we could not find on any library page, and a rule for the Newey-West lag that the repository attributes to a 1994 paper we have not read. Writing these down is cheaper than finding them after publication.

## How it works

- A new reference needs a DOI that resolves in Crossref, or an arXiv identifier, or a page or file that answers an HTTP request. Where Crossref gives only a start page, the end page comes from a second record (RePEc), and the entry says so.
- The script reads the bib file, asks Crossref (or arXiv) for each entry and prints `OK`, `FAIL`, `ERROR` or `SKIP` per line. Exit code 0 means every checked entry matches, 1 a mismatch, 2 that the network failed for some entries. A failed lookup is never counted as a pass, and a network failure prints a message, not a traceback.
- Entries with no DOI (a working paper, a web page) are skipped by the script and checked by hand; `docs/references.md` says how.
- Result on 2026-11-18, after a second pass: 63 bibliography entries, 58 matched by the script, 0 mismatches, 5 checked by hand. Of 11 items first listed as unverified, 4 were resolved with a source, 2 partly, and 5 have no source; those are listed with file and line under "Claims in the repo without a source" in the references page, each with a recommendation (add a source, soften or remove).
- Verification covers bibliographic data only. It does not mean we read the paper or that it says what a spec says it does.

## What it costs us

- Adding a source takes minutes instead of seconds, and the bib file must be kept in step with the markdown list by hand.
- The script checks title, year and first author. It cannot catch a wrong volume or page range, so those are checked by hand against a second record.
- Crossref is occasionally wrong or incomplete (no author list for Müller 2013, a title without ": Comment" for Fowler and Rorke 1983), so some entries carry a note explaining the difference.
- Some good sources stay on the unverified list because we cannot read them (paywalls, pages that refuse scripts).

## What would change our mind

If the checks keep failing for reasons that are not errors in our data (for example, Crossref changing how it records titles), we would loosen the title comparison. If the list of unverified items grew without being worked down, we would assign an owner to it. We would not drop the rule itself.

## Sources

- [docs/references.md](../docs/references.md), including "Unverified citations" and "How the checks were done".
- [docs/references.bib](../docs/references.bib) and `scripts/check_references.py`.
- Crossref REST API: <https://api.crossref.org/>.
- [docs/skill-review.md](../docs/skill-review.md), finding 20 (the earlier gap in the references).

## Related decisions

- [Factor data source: the Ken French Data Library](decision-factor-data-source-french-library.md)
- [Daily returns with robust errors](decision-daily-returns-and-robust-errors.md)
- [Independent validation and mutation testing](decision-independent-validation-and-mutation-testing.md)
- [No data and no secrets in the repository](decision-no-data-and-no-secrets-in-the-repo.md)
