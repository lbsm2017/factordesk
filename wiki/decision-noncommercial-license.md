# Decision: a noncommercial licence, with commercial use by consent

Date: 2026-11-20
Status: Decided. Replaces [Open source under the MIT license](decision-open-source-mit-license.md).

## In one sentence

factordesk is published under the factordesk Noncommercial License 1.0: anyone may read, run, change and share it for personal and other noncommercial use if they keep the copyright notice, and any commercial use needs the written consent of the licensor, Lorenzo Bassetti.

## What we decided

- The licence is the [factordesk Noncommercial License 1.0](../LICENSE). The licensor is Lorenzo Bassetti.
- **Free:** personal study and research, and use by schools, universities, public research organisations, charities and similar noncommercial organisations.
- **Consent needed:**
  - any commercial use;
  - use by a government institution that is not a school, university or public research organisation;
  - use by any organisation in the course of managing, advising on or overseeing investments. This covers central banks, sovereign wealth funds, pension funds, endowments and insurers, whatever their legal form.
- **Credit:** every copy must carry the licence and the line "Required Notice: Copyright (c) 2026 Lorenzo Bassetti and factordesk contributors". Citation in published work is a request, made in the README and in `CITATION.cff`; no licence can force it.
- **Commercial licences** are granted by the licensor on request, at the address in the README and the licence file.
- **Contributors** release their work under the same licence and also grant the licensor the right to license it under other terms. They keep their copyright. The pull request template has a box for this.
- We call factordesk **source-available**, never open source.

## Why

The owner wants three things: to be credited, to leave the software free for personal use, and to decide case by case who may use it commercially. The MIT licence gives the first two but allows any commercial use without asking. A noncommercial licence is the standard way to get all three.

The change was easy at this moment and would be hard later. On 2026-11-20 the repository had never been public and every commit was the owner's, so no one held a copy under MIT and no contributor had to agree.

## How the text was made

The text starts from the PolyForm Noncommercial License 1.0.0, a plain-language licence written by licensing lawyers. Its authors allow changes on one condition: a changed text must not use their name. So the licence file carries its own name and does not mention the original.

We changed four things:

1. **Noncommercial Organizations.** "Government institution" was removed from the list of organisations that may always use the software.
2. **Excluded Uses** (new). Government institutions other than schools, universities and public research organisations, and any organisation's investment management, are not permitted purposes.
3. **Consent for Other Uses** (new). Commercial and excluded uses need the licensor's prior written consent in a separate licence.
4. **Definitions.** The licensor is named.

The owner asked for change 1 and 2 on 2026-11-20: the standard text would let central banks, public pension funds and sovereign wealth funds use a finance tool for free, and they are among its most likely professional users.

## What we looked at and did not choose

| Option | Why not |
| --- | --- |
| MIT (the earlier choice) | Allows commercial use without consent. |
| PolyForm Noncommercial 1.0.0, unchanged | Standard and well known, but government institutions and public funds use it free. |
| PolyForm Strict 1.0.0 | Same free list as above, and it also forbids changing and sharing the code, which blocks academic use. |
| Creative Commons BY-NC | Written for texts and images; Creative Commons advises against using it for software. |
| Business Source License, Functional Source License | Aimed at companies that stop a competing hosted service and convert to open source later. Not our case. |
| AGPL with a paid exception | Still allows commercial use by anyone who shares their changes. |

We searched the skills registry for a licensing skill on 2026-11-20. None met the quality bar; the most used one (`oss-license-strategy`) was read as background and agrees on two points used here: use a recognised text where possible, and do not call a source-available licence open source.

## What it costs us

- **Not open source.** The licence is not approved by the Open Source Initiative. GitHub shows it as "Other", some package indexes and company allow-lists will not accept it, and people who only use open-source software will stay away.
- **A custom text.** The changed clauses were not written by a lawyer. They are short and follow the style of the original, but a company's legal team has to read this licence itself; it cannot rely on a text it already knows. A lawyer should read the "Excluded Uses" clause before the first commercial licence is sold.
- **Grey zones.** "Commercial" is not defined line by line. The README has a plain table, but the licence text decides.
- **Fewer contributors.** The extra grant to the licensor will put some people off.
- **Enforcement is on the owner.** A licence does not stop misuse by itself.

## What stays the same

- The dependency audit of 2026-11-20: every runtime dependency is permissive, so nothing conflicts with the new licence. Fonts stay under the SIL Open Font License. See [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).
- Data is not covered by the licence. A commercial licence from the owner covers the code only; the user still needs their own rights to Yahoo, SNB and other data ([data terms](../docs/references.md#data-sources-and-licences)).
- The López de Prado (2023) book is cited as a source for scientific rigour. None of factordesk's algorithms are taken from it ([guardrails](decision-causal-discipline-guardrails.md)).

## What would change our mind

- Wide academic use held back by the licence: move to an open-source licence. Moving toward more freedom is always possible and is well received.
- Regular commercial requests: have a lawyer write a standard commercial licence and review this one.
- Outside contributors in number: replace the paragraph in `CONTRIBUTING.md` with a signed contributor agreement.

## Sources

- [LICENSE](../LICENSE)
- [CONTRIBUTING.md](../CONTRIBUTING.md), "License".
- PolyForm Noncommercial 1.0.0: <https://polyformproject.org/licenses/noncommercial/1.0.0>, and the terms for changing it: `LICENSE.md` in <https://github.com/polyformproject/polyform-licenses> (read 2026-11-20).

## Related decisions

- [Open source under the MIT license](decision-open-source-mit-license.md) (superseded)
- [Making the repository public](decision-going-public.md)
- [No data and no secrets in the repository](decision-no-data-and-no-secrets-in-the-repo.md)
