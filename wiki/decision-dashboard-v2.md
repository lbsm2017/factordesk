# Decision: dashboard v2, outcome first with a sidebar

Date: 2026-11-18
Status: Decided-pending-implementation (specified on branch `feat/ui-v2-spec` as of commits
`dabbff7` and `07d77a7`; nothing is built yet; the look waits for the owner's approval of the
prototype)

## In one sentence

The dashboard becomes a full-width page with a dark navy sidebar for the controls and section
links, opens with one plain sentence that says what drives the stock and whether it earned anything
beyond those exposures, uses bigger type and a fintech-tool palette, hides the statistics behind a
"Show statistics" switch, and drops the regression formula.

## What we decided

All decisions below were given by the owner on 2026-11-18, after testing the dashboard on `dev`
(PRs #1 to #3 merged) with screenshots of ZM over 5 years.

- **Sidebar = controls plus section navigation.** The ticker search, the date range, the switches,
  the factor-data line and a list of links to every section live in a left sidebar. The current
  section is highlighted as you scroll. On a phone the sidebar opens as a drawer.
- **The formula is removed.** The fitted equation was the design's "one bold element" in revision 2
  of `docs/design/report-design.md`. Its place goes to a verdict band: one headline sentence and four
  outcome tiles (return beyond its exposures, how much the model explains, stock-specific risk, world
  beta). Five factor cards under it say, in plain words, how the stock leans on each factor.
- **Outcome first, statistics on demand.** Every panel opens with one sentence that states its
  result. A "Show statistics" switch adds t-statistics, p-values, intervals and the other detail
  columns. The words "significant" and "not significant", and the faded marks for weak evidence,
  stay visible with the switch off.
- **Never more than the statistics support.** The sentences come from fixed rules in
  `docs/specs/dashboard-v2.md` section DV4. They say "shows no reliable return beyond its exposures",
  never "no alpha"; they never imply cause or forecast; and they add a caution when the price audit
  found errors or the quality gate fired.
- **Company name.** The header shows the company name, exchange and currency from one Yahoo metadata
  read per ticker (a new optional report field, `data.security`, report format unchanged at version 4). The same
  read lets factordesk refuse a ticker quoted in a currency other than US dollars (roadmap ticket N1).
- **Historical performance and a quick world beta**, added by the owner later the same day, as two
  new optional report sections: return a year (compound), volatility, Sharpe ratio and largest fall;
  and the stock's beta against world stocks, with the iShares ACWI fund standing in for the MSCI All
  Country World index.
- **Look.** The owner replaced the plan's first palette (white page, one ultramarine accent) with a
  fintech-tool palette: a dark navy sidebar with bright cyan, a grey page with white panels, teal for
  buttons and links, indigo for the verdict band, and green, red, amber and slate for evidence. The
  font is IBM Plex Sans. Nothing is smaller than 14 px. Density rules: at most four tiles per row,
  table rows at least 48 px tall, one idea per block, at most six table columns with statistics off,
  prose at most 72 characters a line.
- **Sidebar references.** The owner pointed to Altoo and to an investment analytics tearsheet tool
  for the dark navy icon-and-label sidebar. We took the idea of a dark rail with labels next to icons
  and a light content area; we did not copy their charts, wording or data.
- **Dashboard first, static report later.** The offline HTML report keeps its revision 2 look,
  apart from the company name line and the two new panels. Its port is roadmap epic 18.
- **Stack unchanged.** Plain CSS tokens, no Tailwind or shadcn/ui, no new runtime dependency.
- **Factor exposure colours (2026-11-19, later the same day).** On approving prototype v4a the owner
  asked for betas in neutral ink. After testing the dashboard on localhost the owner asked for green
  and red in the Factor exposures chart: bars above zero are green, below zero red, not-significant
  bars faded in the same hue, and beta values coloured only when significant. This supersedes
  "betas neutral" for that panel only; shrunk betas and the Summary table keep neutral ink.

## Why

The owner found the fonts too small, some blocks too dense, and the page not saying what the result
means for the client. The formula, while accurate, does not help a reader who is not a statistician.
An investor reads the verdict first and the evidence second, so the page now does the same. The
switch keeps the rigour one click away instead of deleting it.

The verdict sentences are generated from the existing significance tags, so they cannot claim more
than the tests found. The thresholds come from the methodology (five-beta Benjamini-Hochberg, the 5%
alpha test, the quality gate) or are marked in the spec as new product choices.

## What we rejected

- **Tabs.** They would hide panels; the owner decided on one scrolling page on 2026-11-18, and the
  sidebar is navigation over that page, not tabs.
- **Tailwind and shadcn/ui.** The owner approved plain CSS tokens on 2026-11-18
  (`docs/specs/dashboard.md`, owner decision 4); moving now would mean rewriting every stylesheet
  without changing what the user sees.
- **Keeping the formula behind a disclosure.** It would keep three font files, six tests and three
  stylesheets alive for a view the target reader does not use; the regression detail table already
  holds every coefficient.
- **A two-column grid of panels at the old 1216 px width.** It starves the charts again and breaks
  the reading order. At 1440 px and wider the page puts a chart and its reading side by side inside
  one panel instead.

## What it costs us

- Two renderers drift further apart until epic 18: the React page and the static report no longer
  have the same panels at positions 200 and 300.
- One more Yahoo request per new ticker for the name; when it fails, the header shows the ticker only.
- The owner's light green and red differ less than our earlier colour-vision floor for people with
  deuteranopia (6.6 against 8, measured 2026-11-18 in design section M.3). Position, the plus or
  minus sign and the direction word still carry the meaning; the owner decides at the prototype gate.
- About 14 agent sessions of work (estimate in `docs/ROADMAP.md`, epic 17).
- Not verified as of 2026-11-18: everything. No React code, no prototype approval and no review yet.

## What would change our mind

If readers say the plain sentences hide something they need, the default of the statistics switch
could change. If the two renderers become costly to keep apart, the static port (epic 18) moves up.

## Sources

- [docs/specs/dashboard-v2.md](../docs/specs/dashboard-v2.md): verdict rules (DV4), column map
  (DV5), tickets V1 to V16 (DV9), owner decisions.
- [docs/design/report-design.md](../docs/design/report-design.md) revision 3: sections C, J, K, L
  and M, and the superseded rules marked in place.
- [docs/specs/dashboard.md](../docs/specs/dashboard.md): the version 1 dashboard spec, still in force
  where version 2 is silent.
- The approved plan of 2026-11-18 and the owner's messages of the same day.

## Related decisions

- [Dashboard server and interface](decision-dashboard-server-and-interface.md)
- [Report design: colour is evidence](decision-report-design-colour-is-evidence.md) (partly
  superseded for the dashboard: colour now also marks navigation and highlights)
- [Report density, width cap and range controls](decision-report-density-and-range-controls.md)
  (the 1216 px cap is superseded for the dashboard)
- [Which betas count as reliable](decision-which-betas-count-as-reliable.md)
- [SPY timing noise and the quality gate](decision-spy-timing-noise-and-the-quality-gate.md)
- [European mode, regional factors and currency](decision-european-mode-and-currency.md)
