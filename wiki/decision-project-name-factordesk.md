# Decision: the project name factordesk, and no implied endorsement

Date: 2026-11-18
Status: Decided

## In one sentence

The project is called factordesk, and we will not use any name, wording or branding that suggests the data provider or the factor researchers endorse it.

## What we decided

- The name is factordesk, used for the repository, the Python package, the command-line tool and the dashboard title.
- The rule: what we publish must not imply that factordesk is affiliated with, or endorsed by, the Ken French Data Library, its authors or Yahoo Finance, and should say it is independent.
- We credit Kenneth R. French and Eugene F. Fama when publishing results, as the library asks, and we say where the data comes from.

## Why

The working name "quantdesk" was rejected as too generic. On 2026-11-18 candidates were checked for a free PyPI name and an exact-name GitHub repository. factorlens and factorlab were taken; betascope, factorscope and factorit had existing repositories; factorprint, factorloom, factordesk, loadingdesk and frenchlens were free. We rejected frenchlens because it could read as affiliated with the data provider, which is why the no-endorsement rule exists. The owner chose factordesk: descriptive, it keeps the "desk" feel of a quant workstation, and it was free on PyPI and GitHub that day. Trademarks were not checked. The "Factor it" button keeps the verb. We also reject leaving data origins vague: the README, the references page and the report name the sources.

## How it works

- The README states the data sources and links to the references page, which names the library as the source of truth for factor definitions.
- A "not affiliated" statement was proposed in the README research of 2026-11-18, which surveyed how comparable projects do it. As of that date the README does not yet contain one, so this is pending.
- Example: "Factor data: Kenneth R. French Data Library. factordesk is an independent project and is not affiliated with or endorsed by its authors" would meet the rule. This wording is an illustration, not agreed text.
- The report footer says "Descriptive statistics on past data; nothing here is a forecast or advice."

## What it costs us

- A non-descriptive name tells newcomers little about what the tool does; the one-line summary has to do that work.
- The word "desk" may suggest a professional trading product. The README and reports say it is a research tool.
- Trademarks were not checked as of 2026-11-18; only PyPI and GitHub name availability was.
- Disclaimers can look defensive, and they do not settle what the providers' terms allow.

## What would change our mind

A trademark conflict, a request from a data provider, or a rebrand tied to a hosted service.

## Sources

- [README.md](../README.md)
- [docs/references.md](../docs/references.md): credit and terms.
- [README research, 2026-11-18](readme-research-2026-11-18.md): the "not affiliated" proposal.
- [docs/design/report-design.md](../docs/design/report-design.md), colophon.
- [docs/PLAN.md](../docs/PLAN.md), Context.

## Related decisions

- [Open source under the MIT license](decision-open-source-mit-license.md)
- [Factor data source](decision-factor-data-source-french-library.md)
- [Report design: colour is evidence](decision-report-design-colour-is-evidence.md)
