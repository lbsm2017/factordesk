# README research (2026-11-18)

Source: a read-only survey on 2026-11-18 of READMEs of 7 named repos (quantstats, yfinance, Riskfolio-Lib, skfolio, ffn, OpenBB, pyfolio-reloaded) plus 8 extras. Not verified: whether README structure drives star counts.

## Observed on 2026-11-18

- The leanest popular READMEs (ffn 70 lines, yfinance 89) go: title, one line, 3-4 badges, runnable snippet, install.
- Hero visuals are mostly screenshots of real output at 600-1000 px width. quantstats pairs a report screenshot with a link to a hosted sample HTML report.
- No surveyed repo served separate dark and light screenshot heroes.
- Only yfinance, OpenBB and two smaller repos put a data-terms or not-affiliated disclaimer in the README.
- Positioning against alternatives was rare. The best examples were "when to use it and when not" blocks.
- Off-putting: 100-name method dumps, donation and affiliate buttons above the description, 8-12 badges, "coming soon" lines.

## Outline chosen for factordesk (proposal, 90-150 lines)

1. Title, one-liner, 3-4 badges (Python, MIT, CI).
2. Hero: real SPY report screenshot, link to a sample HTML report.
3. Quickstart: install plus 1-3 lines and an output excerpt.
4. What you get: 4-6 bullets.
5. When to use it and when not (sibling tools named).
6. Methodology in numbers, link to `docs/methodology.md`.
7. Data sources and terms: Ken French Data Library, yfinance, not affiliated, personal and research use.
8. Limitations, not investment advice.
9. Install options, contributing, license.

## Update 2026-11-28: the README is short again

By version 1.0.0 the README had grown to about 1,000 lines: a full dashboard tour, the install and usage reference, the method, the data terms, the project layout and the roadmap. That is the "method dump" the survey above found off-putting. The owner asked for a simpler README that points to the wiki for details.

The README now keeps the hero, "Why factordesk", the use-case table with the screenshot grid, the quick start, a four-step "How it works", a documentation table, contributing with starter tasks, the FAQ, "Can I use it?", the author and citation, and the advice disclaimer (about 310 lines). The details live in the user guides listed in the [index](index.md#user-guides). The licence summary and the data-terms pointer stay in the README because they decide whether a reader may use the tool at all.

