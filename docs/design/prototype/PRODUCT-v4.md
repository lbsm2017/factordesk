# Product

<!-- impeccable:product-schema 1 -->

Written 2026-11-19 for the v4 prototype round. Kept here, not at the repository root, because it
records the product context this prototype round was built against and nothing else reads it yet.
No interview took place: every fact below comes from README.md, docs/overview.md,
docs/specs/dashboard-v2.md (branch feat/ui-v2-spec) and the owner's written review notes on v3.
Lines marked **(inferred)** are assumptions drawn from those sources, not confirmed answers.

## Platform

web

## Users

- Researchers and curious investors who want to see what one stock's or fund's past returns were
  exposed to (market, size, value, profitability, investment) and how much of that can be told
  apart from noise (README).
- They open the dashboard on a desktop or laptop monitor, often next to a broker or a
  spreadsheet, and read a few numbers before deciding whether to look deeper **(inferred)**.
- Some are not statisticians; the owner asked for plain words first and statistics behind a
  switch (spec DV0, goals 2 and 5).

## Product Purpose

One ticker in, one factor profile out: price, factor betas with 95% intervals tagged as clear
evidence or possible noise, return and risk attribution, rolling betas, historical performance, a
quick world beta, deeper checks, and every data caveat. It describes the past; it does not
forecast, rank or recommend. Success: a reader knows within one screen how the security behaved
and whether anything beyond its exposures is real.

## Positioning

A local, open-source factor tearsheet whose every number carries an honest evidence label
(Benjamini-Hochberg corrected, Newey-West errors) and whose data caveats are shown, not hidden.
Factor definitions come from the Ken French Data Library; prices from yfinance.

## Operating Context

- Runs on the user's own machine (FastAPI and React later; this round is a static HTML and CSS
  prototype generated from a mock fixture). No login, nothing hosted.
- The same content is exported as an offline HTML report.
- Readers compare against institutional tearsheet tools they already use; the owner named an
  investment analytics tearsheet (navy icon rail, compact title row with a type badge, analysis
  bar, dense tables with right-aligned numbers) as the craft bar **(reference, not a world)**.

## Capabilities and Constraints

- One scrolling page with sidebar navigation; no tabs (owner, 2026-11-18).
- Sidebar holds the controls: ticker and Factor it, range presets 3Y, 5Y, 10Y, Full history,
  From and To dates, analysed range, factor data freshness, Show statistics switch, section nav.
- Header carries company name, exchange and currency. No regression formula.
- Light theme only. No new runtime dependencies (plain CSS and inline SVG; no chart library or
  CDN in this prototype).
- Minimum text size 14 px; the owner found 12.5 px too small.
- Terms: "Clear evidence" and "Could be noise" are the only two evidence labels.
- World beta uses the ACWI ETF as a stand-in for the MSCI ACWI index; performance, world beta,
  residual, Kalman and shrunk sections are demo values in the fixture.

## Brand Commitments

- Name: factordesk (lower case). Navy sidebar #141A33 with cyan #3CC8E8 used only on navy; teal
  #0B7285 the one accent on light surfaces; IBM Plex Sans with tabular numerals (owner decisions).
- Sentence case, no all-caps, no em dashes, no emoji. No mention of how the product was made.

## Evidence on Hand

- Mock fixture backend/factordesk/tests/fixtures/mock_report.json (SPY, made-up numbers).
- Demo values for performance, world beta and the deeper checks are keyed in the generator and
  labelled as demo values on the page. No real customer, benchmark or performance claim exists and
  none may be invented.

## Product Principles

1. The past, described honestly: every number carries its evidence label and its date range.
2. Plain words first, statistics one switch away; never claim more than the statistics support.
3. Dense and scannable like the tools readers already trust, not a marketing page.
4. Every caveat visible where it applies.

## Accessibility & Inclusion

WCAG 2.2 AA contrast; colour never carries meaning alone (the word is always present); keyboard
reachable controls; minimum 14 px text **(inferred standard from spec DV0 and the v3 contrast
script)**.
