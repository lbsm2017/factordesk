# Report design: single-ticker factor profile

Design spec for the one-page HTML report. The prototype is `docs/design/prototype/report.html`,
built from the mock fixture by `docs/design/prototype/build_prototype.py` (stdlib only) with the
stylesheet source `docs/design/prototype/report.css`. Screenshots sit next to it
(`shot_{1440,390}_{light,dark}.png`, `shot_1920_light.png` to check the width cap,
`*_empty.png` for the insufficient-data states, `report-print.pdf` for print). The dashboard
controls mock is `report-controls.html` (`build_prototype.py --controls`,
`shot_1440_light_controls.png`).

Contents: A. palette and tokens. B. type. C. layout. D. panels. E. motion. F. accessibility.
G. self-critique. H. integration notes and schema gaps. I. dashboard controls. Rev 3 adds:
J. app shell and sidebar. K. switches and segmented controls. L. verdict band, outcome tiles,
factor cards and outcome lines. M. rev 3 tokens, type scale and contrast.

Revision 2 (owner review of the live report, 2026-11-18): density, price cut-off wording, marker
sizes, and range controls. Changes are marked "Rev 2" below.

Revision 3 (owner review of the live dashboard on `dev`, 2026-11-18, screenshots of ZM at 5Y):
full-width page with a left sidebar, bigger type, an outcome-first top of page in plain words, a
white panels, a dark navy sidebar, colour and highlighted areas (palette replaced by the owner's
fintech-tool palette later the same day, M.1), toggle switches, the company name,
historical performance and a quick world beta. The formula is removed (owner answer). Changes are
marked "Rev 3" below. A superseded rule is kept in place, struck through in words: it says
"Superseded 2026-11-18 (rev 3)" and gives the new rule, so the history stays readable.

**Scope of rev 3.** Rev 3 applies to the React dashboard (`frontend/`). The static HTML report
(`backend/factordesk/report/render_html.py`) keeps rev 2 until the static port (roadmap epic 18),
with two additive exceptions that come from the schema: the company name line (D.1) and the two
new optional panels (performance and world beta, L.6 and L.7). Behaviour, tickets and acceptance
criteria for rev 3 are in `docs/specs/dashboard-v2.md`; the visual target is the rev 3 prototype in
`docs/design/prototype/` (files named `*-v3*`, built in parallel, owner approval pending).

## Principles

1. **Colour is evidence.** Chrome is ink on neutral surfaces. Colour appears only where it encodes
   data: sign (blue/copper) or factor identity (five categorical hues). There is no brand accent;
   interaction states use the ink colour.
   **Superseded 2026-11-18 (rev 3) for the dashboard.** New rule: **colour has two jobs.**
   (a) Evidence colours keep their meaning: positive, negative, caution, neutral and the five
   factor hues encode data and nothing else; the sign pair moves from blue/copper to green/red
   (M.1). (b) Wayfinding and highlight colours never encode a number: teal on light surfaces
   (links, buttons, focus ring, switches, selected segments), bright cyan only on the dark navy
   sidebar (active section, switches and segments there, the "Factor it" button), and indigo with
   its tint for the verdict band. Colour is never the only signal: every coloured meaning also has
   a word, a glyph or a position. (The first rev 3 draft named one ultramarine accent; the owner
   replaced it on 2026-11-18 with this fintech-tool palette, see M.)
2. **The chart is a table.** Every bar panel is a real `<table>`: one row per factor, the bar lives
   in a cell, the numbers sit in right-aligned tabular columns beside it. Screen readers, print and
   copy-paste get the numbers; sighted readers get the bars.
3. **Uncertainty is visible, never colour-only.** Not significant = faded fill + full-colour
   outline + the word "No" in a "Significant" column (and "not significant" in the equation).
4. **Every panel answers a question** in plain words and ends with one method footnote.
5. **One bold element**: the fitted equation, typeset as mathematics. Everything else is quiet.
   **Superseded 2026-11-18 (rev 3).** New rule: the one bold element is the **verdict band**
   (L.1): one plain headline sentence on an accent tint with the outcome tiles under it. The
   equation is removed from the dashboard (owner answer, 2026-11-18: "beautiful but useless for
   non-nerds"). Its job, linking each coefficient to its detail row, moves to the factor cards.
6. **Rev 3: outcome first.** Every panel opens with one plain sentence that states its result
   (L.5), then the evidence. Statistics columns appear only with "Show statistics" on (K.1).
7. **Rev 3: never say more than the statistics support.** Generated sentences follow the verdict
   rules of `docs/specs/dashboard-v2.md` (V-rules): no claim of causation, no forecast, and
   "not distinguishable from zero" rather than "no alpha".

## A. Palette and tokens

**Rev 3:** the tables of this section stay the static report's tokens until epic 18. For the
dashboard they are **superseded 2026-11-18 (rev 3)** by section M: a dark navy sidebar with a
bright cyan accent, a cool grey page with white panels, deep navy ink, teal for interaction,
indigo for the verdict highlight, and a green/red/amber/slate evidence set with tints. The five factor hues below are kept unchanged in both themes (re-checked against the new
surfaces in M.3). The validation method below (OKLab distance with the Machado simulation) is the
one M.3 reuses.

### Named palette (6)

| Name | Light | Dark | Role |
|---|---|---|---|
| Chalk | `#edf0f3` | `#0e1318` | page |
| Sheet | `#ffffff` | `#151b22` | panel surface |
| Graphite | `#16202b` | `#e8edf2` | primary ink, focus ring, selected control |
| Slate | `#465361` | `#b0bbc6` | secondary ink |
| Cobalt | `#2a5bc0` | `#5f8ae6` | positive sign |
| Copper | `#b4560c` | `#d27c2e` | negative sign |

One cool grey family (blue-slate). Graphite is a deliberate blue-black chosen for 16.5:1 on Sheet,
not a tinted `#111` stand-in for black.

### Semantic tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `--page` | Chalk | Chalk | body background |
| `--surface` | Sheet | Sheet | panels, KPI strip |
| `--sunk` | `#f5f7f9` | `#1b232c` | empty states, tail zone, row target |
| `--border` | `#d3d9e0` | `#2c3743` | panel frame, table header rule (hairline) |
| `--grid` | `#e5e9ee` | `#212a34` | gridlines, row rules |
| `--axis` | `#8a95a2` | `#66727f` | zero line, plot baseline, equation brackets |
| `--ink` | Graphite | Graphite | primary text, CI whiskers, total marker |
| `--ink-2` | Slate | Slate | secondary text, labels |
| `--ink-3` | `#5f6b78` | `#8f9ba8` | muted text: ticks, footnotes, hatch ink |
| `--ink-faded` | `#777e85` | `#8a929b` | not-significant equation terms (large text) |
| `--accent` / `--focus` | Graphite | Graphite | focus ring, selected segment (no hue accent by design) |
| `--pos` | Cobalt | Cobalt | positive bars |
| `--neg` | Copper | Copper | negative bars |
| `--f1` Mkt-RF | `#7559c5` | `#7053be` | violet |
| `--f2` SMB | `#066e33` | `#19783c` | green |
| `--f3` HML | `#c25078` | `#cb587f` | rose |
| `--f4` RMW | `#1995ba` | `#1493b8` | cerulean |
| `--f5` CMA | `#a18a21` | `#aa932d` | ochre |

- **Insignificant:** the sign colour at `fill-opacity: 0.3` with a 1 px full-colour outline.
- **Residual / idiosyncratic:** 45 degree hatch (1.6 px `--ink-3` lines every 5 px on `--surface`)
  with a 1 px `--ink-3` outline.

**Where colours are used:**

- **Sign pair** (exposures, return contribution). Sign is also carried by position (left or right
  of a labelled zero line) and by an explicit `+` or `−` (U+2212) on every number. Text never wears
  the data colour.
- **Factor hues** (risk bars, rolling lines and bands, 8 px key squares beside factor names in
  those two panels). They are never mixed with the sign pair in one panel. Their hue windows avoid
  cobalt (about 240 to 275 degrees in OKLCH) and copper (about 40 to 75 degrees), so a factor never
  looks like a sign.
- **Status** has no colour. Info, warning and error use distinct outline glyphs (circle, triangle,
  square) plus the word.

### Validation (run, not eyeballed)

- **Method:** OKLab distance with the Machado (2009) colour-vision-deficiency simulation at
  severity 1.0, using a palette validator script. Checks: lightness band, chroma floor,
  colour-blind separation, normal-vision floor, contrast.
- **How the factor hues were found:** a random search over OKLCH, using light and dark steps of the
  same hues. Only candidates passing every gate were kept; among those, the one with the best
  all-pairs minimum was chosen.

| Set | Mode / surface | Pairs | Worst CVD ΔE (≥8) | Worst normal ΔE (≥15) | Band, chroma, ≥3:1 |
|---|---|---|---|---|---|
| Factors | light #ffffff | adjacent | 10.2 (HML↔SMB, protan) | 21.0 | pass |
| Factors | light | **all** | 10.2 | 17.6 (RMW↔Mkt-RF) | pass |
| Factors | dark #151b22 | adjacent | 10.0 (HML↔SMB, protan) | 21.6 | pass |
| Factors | dark | **all** | 10.0 | 18.2 (RMW↔Mkt-RF) | pass |
| Sign pair | light | – | 26.1 | 30.5 | pass |
| Sign pair | dark | – | 25.7 | 27.9 | pass |

- Passing on **all pairs** means the risk panel can sort rows by share without re-validating.
- Mark contrast on the surface:
  - Factors, light: 5.26 / 6.39 / 4.46 / 3.47 / 3.40.
  - Factors, dark: 3.03 / 3.13 / 4.33 / 4.87 / 5.71.
  - Sign pair: light 6.26 / 4.91, dark 5.17 / 5.50.
- The faded fill is about 1.6:1 by design; the full-colour outline and the word "No" carry the
  meaning.
- A first dark sign pair (`#6b95ee`, `#e08a3c`) failed the dark lightness band (L 0.68 and 0.71,
  above 0.67) and was stepped down.

## B. Typography

- **Instrument Sans** (OFL 1.1, variable weight 400 to 700) for everything that is not
  mathematics.
- **STIX Two Text** (OFL 1.1) only inside the fitted equation, as a math face: italic variables
  (*r*, *ε*), upright numerals and factor names.
- The split is a role rule, not decoration: serif means "this is the model". Greek letters appear
  only in `<var>` in the math face; prose says "beta".

**Superseded 2026-11-18 (rev 3) for the dashboard: STIX Two is dropped, and IBM Plex Sans
replaces Instrument Sans.** STIX's only job was the equation, which is removed. The owner chose
IBM Plex Sans on 2026-11-18 for the fintech-tool look. New rule: IBM Plex Sans only (OFL 1.1),
bundled as local WOFF2 files in weights 400, 500, 600 and 700 (Latin subset), with
`font-feature-settings: "tnum", "lnum"` for tabular lining figures and `font-display: swap`. No
external font host. Fallback stack: `"IBM Plex Sans", "Instrument Sans", "Segoe UI", system-ui,
sans-serif`; if the Plex files cannot be bundled (licence text, size or subsetting problem found
in ticket V3), Instrument Sans stays as the face and the ticket says why. The three STIX files
(`stix-r`, `stix-il`, `stix-ig`, 15.9 KB together) and the `--math` token leave `frontend/`; the
static report keeps STIX and Instrument Sans until epic 18. Greek letters do not appear in the
dashboard; prose says "beta" and "alpha" only where the Show statistics view needs them. Check in
V3: Plex Sans's zero is plain in the default set (the dotted-zero problem of Mona Sans, G, must not
come back); weights 560 named elsewhere in this document round to 500 or 600 with Plex's static
files (outcome lines 500, tile values 600).

Why these:

- Instrument Sans has true tabular lining figures with a plain zero and a calm texture at small
  sizes.
- STIX Two is the scientific-publishing face, so the equation reads like a paper.
- The first choice, Mona Sans, was dropped after the first render: its tabular zero is dotted,
  which made every number look like code.

**Embedding** (base64 WOFF2 in `<style>`):

| File | Source | Size |
|---|---|---|
| `instrument-sans.woff2` | fontsource Latin subset, as published | 30.1 KB |
| `stix-r.woff2` | STIX upright: ASCII plus − · × and U+2009 | 8.6 KB |
| `stix-il.woff2` | STIX italic: A-Z, a-z | 5.9 KB |
| `stix-ig.woff2` | STIX italic Greek: α β ε ρ σ (separate `unicode-range`) | 1.4 KB |

- The STIX subsets were made with fonttools `pyftsubset`.
- Total is 46.0 KB WOFF2, about 61 KB as base64, under the 120 KB budget.

Why embed instead of a system stack:

- The report is opened by double-click on unknown machines. A system stack would give different
  figure widths per OS.
- No machine reliably has a math italic.

Fallbacks remain: `"Segoe UI", system-ui, -apple-system, sans-serif` and
`"Cambria Math", Cambria, serif`. Ship the licence files from `prototype/fonts/` with the
renderer.

**Figures:**

- `font-variant-numeric: tabular-nums lining-nums` on `body`, so every number is tabular.
- True minus sign everywhere; `+` on every signed value; zero prints unsigned.

**Scale** (ratio 1.2, base 15 px):

| Token | px | Use |
|---|---|---|
| `--fs-1` | 12.5 | ticks, footnotes, legends, equation annotations, KPI labels |
| `--fs-2` | 15 | body, reading lines, table numbers, factor names |
| `--fs-3` | 18 | panel titles (weight 600), subtitle beside the ticker |
| `--fs-4` | 21.6 | KPI values (560) |
| `--fs-5` | 26 (24 under 720 px) | the equation |
| `--fs-6` | 44.8 (37 under 720 px) | the ticker (640, tracking −0.025em) |

- Line height: 1.5 for prose, 1.35 for annotations, 1.15 for display.
- Prose is capped at 76ch.
- Emphasis is by weight only, staying in the same family.

**Superseded 2026-11-18 (rev 3) for the dashboard: the `--fs-1` to `--fs-6` scale and the 12.5 px
floor.** The owner found the page "too small and too hard to understand"; `--fs-1` (12.5 px) was the
most used size (about 50 rules). New rule: the role-named scale of M.2 (caption 14, body 16, table
15, lead 19, h2 24, KPI 32, verdict 36 to 40), and **no text under 14 px anywhere**, including chart
ticks, legends, footnotes and the shrunk-table labels that were 11 px. Line height 1.5 for body,
1.35 for headings. Prose is capped at 72ch. No all-caps labels, no monospace, no eyebrows; sentence
case everywhere (kept).

## C. Layout

- Single column, max 1216 px wide (1152 px content). Text is left-aligned; numbers are
  right-aligned.
- **Rev 2: the cap is a hard rule.** The live renderer used 1680 px and stretched every table to
  about 1650 px, which is what read as "too wide and spread apart". Check at 1920 px
  (`shot_1920_light.png`): the content stays 1216 px wide and centred.
- **Superseded 2026-11-18 (rev 3) for the dashboard: the single column and the 1216 px hard
  cap.** The owner asked for a full page with a left sidebar. New rule: an app shell of a fixed
  280 px sidebar plus a fluid content canvas, full width, with the canvas capped at **1560 px** and
  40 px gutters (24 px under 1100 px, 16 px under 600 px). At 1440 px and wider, a panel that has a
  chart and a reading part sits **two-up inside the panel**: chart-table on the left, reading rail
  (outcome detail, legend, "How this is computed") on the right, 360 px wide. Panels themselves
  never sit side by side (see "two-column grid" in G, rev 3). Under 1100 px everything stacks;
  under 900 px the sidebar becomes a top bar with a drawer (J.4). The rev 2 rule against stretched
  columns still holds: number columns keep their fixed measure, and extra width goes to the plot
  column and the reading rail, never to number columns.
- **Rev 2: no stretched columns.** Number columns have a fixed measure (72 to 92 px); no column
  is wider than its content plus 24 px of gap. A table that looks sparse is fixed by dropping a
  column, not by widening the others.
- Two-up panels were rejected because they starve the plot column. (Rev 3: still true for
  panels side by side at 1216 px; the rev 3 two-up is inside one panel on a canvas of at least
  1100 px, so the plot column keeps at least 640 px.)
- Spacing scale (dense): 4, 8, 12, 16, 24, 32, 48.
- Bar row height 44 px (30 px plot strip on mobile). **Superseded 2026-11-18 (rev 3) for the
  dashboard:** at least 48 px (density rule 3 below).
- Shape rule: panels and the KPI strip have a 6 px radius, controls 4 px, bars 2 px, key squares
  1 px. No shadows, no gradients.
  **Superseded 2026-11-18 (rev 3) for the dashboard.** New shape rule, deliberately not one value
  for everything: 12 px on feature surfaces (verdict band, outcome tiles, factor cards, panels),
  6 px on tables and inputs, 8 px on buttons, 999 px on switches, pills and badges, 2 px on bars,
  1 px on key squares. No gradients. One shadow token, used only by the mobile drawer and the
  suggestion list, because they float over content: `--shadow-float: 0 8px 24px rgb(20 26 51 / 0.14)`
  (dark: `0 8px 24px rgb(0 0 0 / 0.45)`). Highlight areas are flat tints, never washes.
- Rev 3 spacing: the dense scale is kept and two steps are added for the roomier page: 64 (between
  the outcome area and the first panel) and 80 (above the colophon). Panel padding 24 px (16 px
  under 600 px).

**Rev 3 density rules (owner, 2026-11-18). These are hard rules for the dashboard; a review
(ticket V11) checks each one.**

1. At most **4 tiles or cards per row**, at any width.
2. **24 px** between blocks inside a panel; **32 px** between panels.
3. Table rows at least **48 px** tall (rev 2 bar rows were 44 px) with 15 to 16 px text.
4. **One idea per block**: a block (tile, card, table, chart, paragraph) answers one question;
   a second idea gets a second block.
5. Every panel opens with a **19 px outcome sentence** (L.5).
6. At most **6 visible table columns** with Show statistics off (the column map in
   `docs/specs/dashboard-v2.md` keeps every table within it).
7. Prose at most **72 characters** a line (`max-width: 72ch`).

The page is `--page` (cool grey `#F4F6FA`); panels, tiles and cards are white `--surface` with a
1 px `--hairline` border, so each block reads as one card on the grey page.

Alignment rules:

- In every bar table the label column is 176 px, the plot column takes the rest, and number
  columns are 92 px (132 px for ranges). Zero lines and number columns therefore align down a
  panel.
- Axis labels sit in a `tfoot` row. Labels at the plot edges anchor inward.
- Under 720 px and in print, every other tick label hides; the zero tick always stays.
- Panel head: title and question on the left, legend or control on the right; it wraps on narrow
  screens.

### 1440 wide

```text
+-- page (Chalk) ---------------------------------------------------------------+
| SPY  Fama-French five-factor profile     [Factor data ends 30 Sep ...] [2 warn] |
| Analysed 8 Aug 2024 to 30 Sep 2026, 559 trading days. Last 32 not analysed.   |
| /!\ Two-line plain summary of the warnings.                  + Details         |
| r - r_f =  0.81%  + 0.998 Mkt-RF  - 0.141 SMB  + 0.012 HML  + 0.027 RMW ... +e |
|           |____|  |___________|   |_________|  |_________|  |_________|       |
|           alpha   market          size         value        profitability     |
|           n.s.    signif, t 475   signif ...   not signif.  signif, t 2.2     |
| +---------------------------------------------------------------------------+ |
| | Alpha, a year | R2 | Residual vol | Observations | Analysed range        | |
| +---------------------------------------------------------------------------+ |
| +- Price -------------------------------------------------------------------+ |
| |  line chart, shaded tail ##            | First / End of data / Latest     | |
| +---------------------------------------------------------------------------+ |
| +- Factor exposures ---------------------------------------- legend --------+ |
| | question; reading line (76ch)                                             | |
| | Factor   |   plot: zero line, bars, CI whiskers  | Beta | t | Sig | Avg   | |
| | footnote                                                                  | |
| +---------------------------------------------------------------------------+ |
| Where the return came from (same grid + Alpha, Residual hatched, Total |--| ) |
| Where the risk comes from  (Share | Beta | Factor vol | Corr.)                |
| Exposure over time [Window: 126 days | 252 days], 5 small-multiple rows       |
| Data and audit: Coverage | Findings + Caveats; Regression detail table        |
+-------------------------------------------------------------------------------+
```

### 390 wide

```text
| SPY / subtitle / chips / range line / notice     |
| r - r_f =                                        |
| 0.81%            + 0.998 Mkt-RF   (2 terms/line, |
| alpha, a year    market            each keeps    |
| - 0.141 SMB      + 0.012 HML       its bracket)  |
| KPI strip as 2 columns, last cell spans both     |
| Factor    Beta    t   Sig.  Avg                  |
| Mkt-RF   +0.998  475  Yes  +0.998   <- line 1    |
| |=========================|         <- line 2    |
| Risk: beta/vol/corr move to a line under name    |
```

- No horizontal page scroll at 390 (measured `scrollWidth` 390).
- The only sideways scroller is the regression table, inside a labelled, focusable
  `role="region"`.

### Rev 3: 1440 wide (dashboard)

The wireframes above stay the static report's. The dashboard at 1440 px (the ZM text is
illustrative, not a computed result):

```text
+-- rail 280 (navy) -----+-- canvas (grey page, white panels), 40 px gutters, cap 1560 ---------+
| factordesk              | ZM  Zoom Communications Inc.          [Factor data 30 Sep] [2 warn] |
| [ ZM         ][Factor it]| NASDAQ, USD                                                          |
| [3Y | 5Y | Full]        | +-- verdict band (highlight-50) ------------------------------------+ |
| From [date] To [date]   | | ZM moves less than the market (about 0.88 times as much), leans   | |
| Analysed 1 Oct 2021 to  | | toward growth stocks, and shows no reliable return beyond its     | |
|  30 Sep 2026, 1,254 days| | exposures.                                                         | |
| Factor data: 30 Sep     | | [Beyond its exposures] [Model explains] [Stock-specific] [World]  | |
|  [Check for newer data] | | Descriptive, in-sample, not predictive.                            | |
| (o) Show statistics     | +--------------------------------------------------------------------+ |
| (o) Dark theme          | How it performed: [Return a year][Volatility][Sharpe][Largest fall]   |
| ---------------------   | /!\ amber notice band, two lines + Details                             |
| Summary         <active>| What drives it: [Market .................. wide card ...........]      |
|                 [Size] [Value] [Profitability] [Investment]           |
| What drives it          | +- World beta (quick estimate) --------------------------------------+ |
| World beta              | +- Price ------------- chart -------------- | reading rail 360 ------+ |
| Price ...               | +- Exposures ---------- bar table --------- | outcome, legend, how --+ |
| Data and audit  (2)     | ...                                                                   |
| [Download report]       |                                                                       |
+-------------------------+-----------------------------------------------------------------------+
```

### Rev 3: 390 wide (dashboard)

```text
| [=] ZM  Zoom Communications Inc.     | <- top bar 56 px, menu button opens the drawer
| NASDAQ, USD   [Factor data] [2 warn] |
| verdict band: headline at 28 px      |
| tiles, one per row                   |
| performance tiles, two per row       |
| factor cards, one per row            |
| panels stacked, outcome line first   |
```

- No horizontal page scroll at 390 (`scrollWidth <= clientWidth`), as in rev 2.

## D. Panels

**Common anatomy:** `h2` title (18/600), question subtitle (`--ink-2`), optional legend or control
on the right, optional reading line, the chart-table, and one footnote (12.5 px, `--ink-3`,
hairline above).

**Rev 2: footnotes show one or two sentences.** Method detail (test names, lags, formulas) folds
into a native `<details class="how">` labelled "How this is computed". No JavaScript. Print
expands it (`details::details-content` forced visible, summary hidden); checked in Chrome 157.

**Empty state** (any statistic with `status != "ok"`):

- The title and question stay.
- The chart becomes a `--sunk` box showing `reason` in ink and one next step in `--ink-2`.
- The footnote is dropped.

**Rev 3 additions to the common anatomy (dashboard).** Under the title sits the **outcome line**
(L.5): one sentence at `--fs-lead` (19 px), weight 500, ink, that states the result. The question
subtitle moves under it in `--ink-2` at body size. Titles are 24 px / 600. Footnotes are 14 px
`--ink-3`. Columns marked "statistics" in `docs/specs/dashboard-v2.md` (the column map) render
only with Show statistics on (K.1).

### 1. Header, range line and data-quality notice

Rev 2: the header was two rows of badges plus a paragraph. It is now three short pieces.

**Rev 3: company name line.** Under the ticker sits one line with the company name, then the
exchange and the currency, from the optional `data.security` field (schema version 5,
`docs/specs/dashboard-v2.md` section V2): for example "Zoom Communications Inc." on the name line
and "NASDAQ, USD" in `--ink-2` beside it at caption size. In the dashboard the ticker is 32 px / 640
and the name 19 px / 500 in ink. Rules: the name is plain text, never a link; a name longer than
the line truncates with an ellipsis and carries the full name in `title`; when `data.security` is
missing or `name` is null, the line shows exchange and currency alone, and when all three are
null the line is omitted (no placeholder). The static report gets the same line (additive, from
the schema). "Fama-French five-factor profile" moves to the sidebar title in the dashboard.

- Row 1: ticker at 44.8/640, "Fama-French five-factor profile", and on the right two chips: "Factor
  data ends 30 Sep 2026 (49 days ago)" (plain) and "2 warnings" (a link to the notice, ink,
  weight 560). No outlined badges, no middle dots.
- Range line: "Analysed 8 Aug 2024 to 30 Sep 2026, 559 trading days. The last 32 price days are charted
  but not analysed." One sentence pair, 76ch maximum.
- Notice (only when `warnings[]` is non-empty): a framed strip with a 3 px ink left rule, the
  warning glyph, and a **two-line plain summary**, for example "Prices look out of step with the
  factor data, so R² is probably understated and residual volatility overstated." A "Details" disclosure
  holds the raw messages (and, in the dashboard, the 5-day estimate line). The hidden prefix
  "Warning:" stays for screen readers.
- The generated time moves to the colophon. Dates in prose read like "8 Aug 2024".
- In the dashboard the range line is replaced by the controls (section I).
- **Rev 3 (dashboard):** the range line moves to the sidebar (J.2). The notice becomes an **amber
  highlight band** under the performance tiles: `--caution-50` fill, a 3 px `--caution` left rule,
  the triangle glyph in `--caution`, text in ink, still two lines plus "Details". The warnings chip
  in the header links to it. The rev 2 copy rules are unchanged.

### 2. Equation (the memorable element)

**Superseded 2026-11-18 (rev 3) for the dashboard: removed.** Owner answer: the formula is
"beautiful but useless for non-nerds". New rule: no equation in the dashboard. Its two jobs move:
the plain reading of each coefficient goes to the factor cards (L.3), and the link from a
coefficient to its detail row goes to the card's "See the detail" link, which keeps the
scroll-and-focus behaviour of the old term links. The static report keeps the equation until
epic 18; the text below describes that static panel.

- STIX at 26 px, one line at 1440.
- Each term links to its table row (`#beta-SMB`, `#ret-alpha`). The target row gets a `--sunk` wash
  and a 2 px ink rule.
- Under each term: a hairline bracket (`--axis`) and two sans annotation lines: the plain name,
  then "significant, t −13.8" or "not significant, t 1.2".
- Insignificant terms are set in `--ink-faded` and say so in words.
- The leading alpha term is unsigned when positive. ε shows residual volatility a year.
- The figure carries a full `aria-label`. Wrapped lines hang under the first term.
- Caption: "The fitted daily model, in-sample. Faded terms are not statistically significant. Select a
  term to see its detail."
- Empty: omitted.

### 3. KPI strip

**Superseded 2026-11-18 (rev 3) for the dashboard: folded into the outcome tiles.** New rule:
alpha, R² and residual volatility become the three verdict tiles (L.2); observations and the
analysed range move to the sidebar's analysed-range line (J.2). The static report keeps the strip
until epic 18; the text below describes it.

- One framed strip with **five** cells split by hairlines (not cards). Rev 2: six became five;
  Adjusted R² and the Data audit cell moved out (adjusted R² sits in the regression footnote;
  audit status is the warnings chip and the Data and audit panel).
  - Alpha, a year: value, then one plain line, "Not distinguishable from zero" or
    "Distinguishable from zero at 5%". The value is in `--ink-2` when not significant. t and p
    live in the equation and the regression table, not here.
  - R²: "Share of daily variance the factors explain".
  - Residual volatility: "A year, left unexplained by the factors".
  - Observations: "Trading days; 1 excluded".
  - Analysed range: month range at 18 px, with the requested range below.
- Every cell is a label, a value and at most one line of 12.5 px text.
- Narrow screens: 2 columns, the last cell spans both.
- Empty: one box with `regression.reason` and "Widen the date range ... and run the report
  again."

### 4. Price

- Question: "How has the price moved over the window? Shaded days are not in the analysis."
- 1.5 px ink line, 3 to 4 y ticks, quarterly x ticks.
- **Rev 2: both ends of the non-analysed region are marked.** Days after `factor_coverage_end`
  and days before the analysed start sit on a `--grid` band (darker than the old `--sunk`, which
  was nearly invisible), with a 1 px dashed `--ink-3` rule at the cut. The analysed window is the
  unshaded part. The band keeps its true width: it is a time axis, so it is never widened to look
  bigger; the dashed rule and the label carry a thin tail.
- **Rev 2: the label says what it means.** "Not analysed: factor data ends 30 Sep 2026" (right
  end) and "Not analysed: before 8 Aug 2024" (left end, when present). The old label, "no factor
  data", was internal jargon and said nothing about the consequence.
- Right-hand table: First, End of factor data, Latest, and a muted "After factor data: 32 days,
  raw, not analysed +1.23%".
- Footnote: "for context only; no statistic uses the price line."
- Empty: "No prices were returned..." / "Check the ticker symbol or choose a later start date."

### 5. Factor exposures

- Question: "What is this stock exposed to, and how sure are we?"
- Legend: Positive, Negative, Faded: not significant, 95% interval, Average 252d beta (a small
  diamond).
- Reading line built from the tags (template in H).
- Rows in canonical order, each with its code and plain name.
- Bar from zero (36% of row height), sign colour.
- CI whisker: 1.5 px ink. **Rev 2:** caps are 3 px tall (they were 8 px on a 16 px bar and read
  as an "H" on narrow intervals), and are omitted when the interval is narrower than 1.2% of the
  plot width, about 6 px.
- **Rev 2: average rolling beta marker.** A 7 px diamond centred on the row's centre line (never
  below the bar), ink fill with a 0.75 px surface outline. It is the only marker besides the
  whisker; the bar (16 px at 44 px row height) stays the strongest mark. The Avg 252d column
  keeps the number.
- Domain: a nice range over the CI ends and 0. Solid hairline gridlines; zero line in `--axis`.
- Columns: Beta (bold unless not significant), t, Significant (Yes/No), Avg 252d.
- Native `<title>` gives beta, interval, t and adjusted p.
- Footnote: "In-sample, descriptive, not predictive. Significant means the adjusted p is below
  0.05." Folded: "OLS on daily excess returns with Newey-West standard errors ({hac_lags} lags).
  Significant means the Benjamini-Hochberg adjusted p is below 0.05 across the {bh_family_size}
  betas. The diamond and the Avg 252d column are the mean of the overlapping rolling
  estimates."

### 6. Where the return came from

- Question: "How much of the average yearly return does each factor explain?"
- Rows:
  - The five factors.
  - Alpha ("Unexplained average").
  - Residual ("Zero by construction"), hatched.
  - Total: a 2 px ink rule from zero with a 3 px cap, separated by a `--border` rule.
- Factor and alpha bars fade with their tag.
- Columns: % a year, Significant.
- "Not in the sum" memo list below the table.
- Reading: "Of the 12.64% ..., market exposure accounts for 11.57%. Alpha adds +0.81%, but it is not
  significant."
- Footnote: "...full-sample beta times the factor's average return, times 252. Arithmetic, not
  compounded, so the rows add up exactly to the total."

### 7. Where the risk comes from

- Question: "What share of the day-to-day variance does each factor drive?"
- Rows follow `risk_contribution.order`, each with a key square and plain name.
- Bars in factor hues; idiosyncratic is hatched.
- Domain: at least 0 to 100%, extended left for negative shares.
- Columns: Share, Beta, Factor vol, Corr. The exposure x vol x correlation detail is visible text,
  not hover-only.
- Under 720 px these collapse to a second line: "Beta +0.998, vol 10.0%, corr +0.50".
- `<title>` repeats the decomposition.
- Reading: top share, idiosyncratic share, total volatility, then `sentences[]`.
- Footnote: Euler decomposition; shares add to 100% and can be negative.

### 8. Exposure over time (small multiples)

- Question: "Have the exposures been stable, or did they drift?"
- Control: Window [126 days | 252 days]; the default is `average_beta.window`.
- Five rows of 56 px:
  - Line at 1.75 px in the factor hue, over a pointwise 95% band in the same hue at 16%.
  - Zero line when it is in range; January gridlines.
- **Common vertical span, own centre:** every row spans the same beta range, so wiggles compare
  across factors while Mkt-RF sits near 1. Top and bottom (and 0 when there is room) are labelled.
- X starts at the first full window; the caption gives that date.
- Columns: Latest, Average, Middle 80% (p10 to p90). Rev 2: the Middle 80% cell carries a
  `title` with the spread, lowest, highest and the share of windows above zero, so the live
  renderer's eight-column "Average 252-day beta" table is not needed.
- Footnote: pointwise band, overlapping windows, common span.

**Toggle without JavaScript:**

- Hidden radios `#win-126` and `#win-252` precede `#rolling`; the labels use `for`.
- `#win-126:checked ~ #rolling .w-126 { display: block }`.
- Arrow keys switch windows; the focused radio styles its label.
- Verified in Chromium with JavaScript disabled.
- Print shows both windows, each captioned.
- Empty: the per-window reason, plus "Choose an earlier start date."

### 9. Data and audit

- Question: "What went into these numbers, and what was left out?"
- Left column, Coverage (a `dl`): requested range, analysed range, excluded rows with reasons,
  dropped price days, factor end date and lag, download time, price source. The factor source URL
  is plain text, not a link.
- Right column: Audit findings (glyph + severity word + message + dates), then Caveats (`notes`
  plus the vintage label).
- Below: Regression detail table (estimate, std. error, t, p, adjusted p, 95% interval, VIF,
  significant), with R², residual vol, lags and condition number in a footnote.
- Closing note: "Audit findings are reported, never acted on." Empty: "No findings. Prices passed
  every check."
- Colophon: "factordesk report, schema v{n}. Descriptive statistics on past data; nothing here is a
  forecast or advice."

## E. Motion

- None. A report is read, printed and compared; the toggle is instant.
- A `prefers-reduced-motion` block still neutralises any transition added later.
- **Superseded 2026-11-18 (rev 3) for the dashboard.** New rule: motion only in answer to the
  user, 150 to 200 ms, `ease-out`: the switch thumb (150 ms), the drawer sliding in (200 ms), the
  scroll-spy highlight moving (150 ms) and smooth scrolling to a section. Nothing moves on load and
  nothing loops. With `prefers-reduced-motion: reduce` every duration is 0 and scrolling jumps.

## F. Accessibility

Measured contrast (WCAG ratio):

| Pair | Light | Dark |
|---|---|---|
| ink on surface | 16.46 (APCA Lc 103) | 14.71 (APCA Lc −94) |
| ink-2 on surface / page | 7.86 / 6.88 | 8.89 / 9.57 |
| ink-3 on surface / page / sunk | 5.44 / 4.76 / 5.06 | 6.12 / 6.60 / 5.61 |
| ink-faded on page (26 px text) | 3.59 | 5.92 |
| axis on surface | 3.04 | 3.53 |
| selected toggle text | 16.46 | 14.71 |
| border / grid (non-essential) | 1.42 / 1.22 | 1.43 / 1.19 |

- **Text size:** minimum 12.5 px, always at least 4.76:1.
  **Superseded 2026-11-18 (rev 3) for the dashboard:** minimum 14 px, and every text and background
  pair at least 4.5:1 (table in M.3).
- **Focus:** a 2 px Graphite `:focus-visible` outline with 2 px offset, on equation links, window
  labels and the scroll region.
  **Superseded 2026-11-18 (rev 3) for the dashboard:** a 2 px outline with 2 px offset on every
  focusable element: `--accent` teal on light surfaces (5.59:1 on white, 5.16:1 on the grey page)
  and `--rail-accent` cyan in the navy sidebar (8.67:1).
- **Table semantics:** bar tables have a hidden `<caption>`, `scope` attributes and explicit ARIA
  roles, because mobile restyles rows as grids. SVGs are `aria-hidden`.
- **Colour independence:**
  - Sign: position + glyph + colour.
  - Significance: fade + outline + the word.
  - Residual: hatch + label.
  - Identity: the name next to every mark.
- **Themes:** `prefers-color-scheme` by default; `<html data-theme>` overrides it both ways
  (verified).
  **Superseded 2026-11-18 (rev 3) for the dashboard:** light by default whatever the OS says; dark
  only through the "Dark theme" switch (K.1) or `theme=dark` in the URL. `<html data-theme>` is
  always set explicitly, and the `prefers-color-scheme` block leaves `tokens.css`. Confirm at the
  Stage 1 gate (open item of the plan).
- **Print (A4):**
  - Light tokens are forced even from a dark OS.
  - `print-color-adjust: exact`.
  - KPI strip in three columns (3 cells, then 2).
  - Price, exposure, return and risk panels are kept whole.
  - Both rolling windows are shown and the toggle is hidden.
  - The mock prints on 8 pages.

Not verified: screen readers, Firefox and Safari, forced-colors mode, real long-history data.

## G. Self-critique

Defaults caught and removed:

- **Dotted-zero font.** It made numbers read like a code font; swapped from Mona Sans to
  Instrument Sans.
- **Big-number hero.** The stat-tile hero was replaced by the equation; KPIs are one ruled strip.
- **Card kit.** No shadows, no gradients, a stated radius rule. Header and equation are unframed.
- **Accent colour.** None; colour encodes data only.
- **Template chrome.** No eyebrows, all-caps labels, section numbers, middle-dot meta strings,
  "WORD - fragment" labels, link arrows or monospace. Everything is sentence case.
- **Inspiration.** Kept the ideas of a bar plus a number column, fading for non-significance,
  hatching for residual, question subtitles and a window toggle. Did not reuse colours, heatmaps,
  layout, chrome or wording. Rolling exposure is small multiples with bands, not a heatmap.
- **Broadsheet look.** Hairlines were kept, but with rounded frames, 44 px rows and a single wide
  column, not newspaper columns.

**Revision 2 (owner review of the live report):**

- The live renderer had drifted from this spec: 1680 px width, monospace everywhere, tiles and
  tables stretched. The spec was right; the checklist in H.12 lists what to port.
- Where the spec was not enough: the header and KPI strip were still dense (five panels' worth of
  numbers above the first chart), the data-quality notice was a 120-word paragraph, the price
  cut-off wording was jargon, and the interval caps were too large. Those are changed above.
- Rejected: widening the post-factor band so it is "visible". It would misstate the time axis.
- Kept: the owner's words "reliable" and "noise" are not in this spec; the legend text "Faded: not
  significant" already defines the faded mark, so no extra definition is added.

**One memorable element:** the fitted regression typeset as mathematics. Each coefficient is
bracketed and labelled with its plain name and evidence, faded where the evidence is weak, and
linked to its detail row.

**Revision 3 (owner review of the live dashboard, 2026-11-18):**

- The owner found the dashboard too small, too dense and not saying the outcome for the client,
  and asked for a full page with a sidebar, colour and highlighted areas, a white background and
  toggle switches. Rev 2 was right about honesty (tables, visible uncertainty, plain words) and
  wrong about who reads first: an investor wants the verdict, then the evidence.
- **One memorable element (rev 3):** the verdict band. The equation is gone.
- Defaults checked and rejected for rev 3: cream and terracotta; dark with acid green; a uniform
  rounded-card kit (the radius rule in C uses four values on purpose); gradient washes; tracked
  all-caps eyebrows; monospace labels; numbered section markers; a big-number hero with no
  sentence. Colour does two jobs only (principle 1, rev 3).
- **Rejected: a two-column dashboard grid at 1216 px** (panels side by side). It starves the plot
  column again (C), breaks the reading order, and the owner asked for full width, not more density.
- **Rejected: tabs.** The sidebar is navigation over one scrolling page; nothing is hidden behind a
  tab (DB10 question 5 and owner decision 5 stand).
- **Rejected: keeping the formula behind a disclosure.** It would keep three font files, six tests
  and three stylesheets alive for a view the owner called useless to the target reader; the
  regression detail table already holds every coefficient.
- **Rejected: Tailwind and shadcn/ui.** Owner decision 4 of `docs/specs/dashboard.md` stands; the
  switch, segmented control and drawer are small native-element components.
- Known weak point: the light sign pair (green `#0A7A55`, red `#C23345`, owner values of
  2026-11-18) separates by only 6.6 OKLab units under deuteranopia, under the rev 2 floor of 8
  (M.3). Position, the sign glyph and the direction word carry the meaning as well; the owner
  decides at the Stage 1 gate whether to darken the green.
- **Sidebar references (owner, 2026-11-18):** a dark navy icon-and-label rail, after Altoo and an
  investment analytics tearsheet tool the owner pointed to. Taken: the dark rail with a bright
  accent for the current place, labels next to icons, a light content area with white cards.
  Not taken: their charts, wording or data.

**Deliberate deviations from common charting guidance:**

- Tabular figures on KPI values.
- Hatch shown by default for residual and idiosyncratic, because it encodes a category.
- No JavaScript crosshair; values are in the number columns and in `<title>`.

## H. Integration notes and schema gaps

**Already in the schema:**

- Significance (`tag`, `alpha_tag`).
- CIs and BH-adjusted p.
- Primary-window `average_beta`.
- Return `residual`.
- Total vol and risk details.
- Uncovered tail and audit findings.
- `labels` / `label_text` and `caption`.

**Gaps:**

1. **Average beta per window.** Only the primary window has it; the 126-day view needs mean / p10 /
   p90. The prototype computes them. Suggest a list of `AverageBetaPanel` keyed by window.
2. **Panel reading sentences.** Suggest `regression.reading` and `return_contribution.reading`,
   owned by analytics. Prototype template:
   - Mkt-RF reads "moves roughly one-for-one with / amplifies / moves less than the market".
   - Other reliable factors read "leans toward small/large companies, value/growth stocks,
     highly/weakly profitable firms, firms that invest conservatively/aggressively".
   - Then "There is no clear tilt to {noise factors}."
3. **Plain factor names** (`FACTOR_PLAIN`: Market, Size, Value, Profitability, Investment).
4. **Empty-state codes:** a `reason_code` plus the minimum data needed, so the renderer can say
   "needs N days, has M".
5. **`ReportWarning.severity`**, used to pick the glyph.
6. **Final caption wording.** Fixture captions are placeholders. Compose each footnote as caption
   + `label_text[labels]` + numbers (`hac_lags`, `bh_family_size`).
7. **Optional security name** for the header. Rev 3: resolved by the additive field
   `data.security` (`name`, `currency`, `exchange`), schema version 5, ticket V6 in
   `docs/specs/dashboard-v2.md`.
8. **t vs z.** The schema says `z` (HAC, normal reference) but the UI says "t"; keep them
   consistent.
9. **Plain warning summaries.** The notice shows a plain two-line summary; the prototype maps
   `warnings[].code` to text (`WARN_PLAIN`). Suggest `ReportWarning.summary` (plain, one
   sentence) next to `message` (technical), owned by analytics. Unknown codes fall back to
   `message`.
10. **Range and ticker parameters** for the dashboard (section I): the report endpoint in
    `backend/factordesk/api/` (currently empty) takes `ticker`, `start`, `end` and returns the
    same schema.
11. **Minimum sample per range chip** comes from the pipeline's existing threshold (the mock uses
    252 days for 1Y and so on); confirm the exact numbers when the API is written.
12. **Port checklist (live renderer to this spec):** width cap 1216; Instrument Sans and
    tabular figures instead of `--mono`; five-cell KPI strip; collapsed notice; price labels and
    band; 3 px caps and 7 px diamond; rolling panel as five rows with three number columns;
    footnotes with folded method detail.
13. **Renderer-derivable:** first and last in-sample price, first full rolling window, audit
   counts, ticks.

**Renderer notes:**

- Bar charts: one inline SVG per table cell with **percentage coordinates** (`x="37.5%"`,
  `y="32%"`), so marks and patterns stay crisp without a distorting viewBox.
- Line charts: `viewBox="0 0 1000 100"` with `preserveAspectRatio="none"` and
  `vector-effect: non-scaling-stroke`. Labels as HTML overlays.
- One shared `<pattern id="hatch">`.
- Rolling series with more than 400 stamps are decimated to every second point.
- Page weight: 233 KB with fonts (Rev 2).
- `add_roles()` in the generator shows the ARIA roles to emit.
- `report.css` is final for the static report; the controls styles (`.controls`, `.chip-opt`) are
  specified for the dashboard and only mocked here.

## I. Dashboard controls (design only)

**Superseded 2026-11-18 (rev 3) for the dashboard: the framed controls strip above the header.**
New rule: the same controls live in the sidebar (J.2), the range chips become a segmented control
(K.2) with 3Y, 5Y and Full history only (owner decision 1 of `docs/specs/dashboard.md`), and the
selected segment is `--accent` on white instead of ink. The behaviour rules below (visible reasons
for unavailable presets, no blanking while loading, error wording, 44 px targets) still hold.

The static report cannot recompute a regression, so it only states its range (the range line in
panel 1). The date range and ticker controls belong to the dashboard (FastAPI + React, roadmap
"Next"). The mock is `report-controls.html`; it uses real form controls but no behaviour.

**Anatomy**, one framed strip above the header (surface, 6 px radius, 16 px by 24 px padding):

```text
+-----------------------------------------------------------------------------------+
| [ SPY        ] [Factor it]   [YTD|1Y|3Y|5Y|Full history]   From [date]  To [date]  |
| Analysed 8 Aug 2024 to 30 Sep 2026, 559 trading days. The last 32 ... not analysed. |
| Factor data ends 30 Sep 2026, so later dates cannot be chosen.                      |
| 3Y and 5Y need more trading days than SPY has in this sample (559). Choose shorter. |
+-----------------------------------------------------------------------------------+
```

- **Ticker search:** a text field (uppercase, 148 px) plus a filled "Factor it" button. Enter
  submits. Recent tickers appear in a list under the field when it has focus.
- **Range chips:** YTD, 1Y, 3Y, 5Y, Full history, one connected segmented radio group in the same
  style as the rolling-window toggle. The selected chip is ink on surface. "Factor lens
  history" from the reference screenshot is deliberately not included.
- **Custom range:** two date fields, From and To. They fill with the analysed dates when a chip is
  chosen, and choosing a date clears the chip. `max` is the last factor date.
- **Analysed range label:** always visible, dates and trading-day count, plus the factor cut-off
  sentence. It reads the same as the static report's range line.
- **Unavailable chips:** disabled (`--sunk` fill, `--ink-3` text, not-allowed cursor) with the
  reason as visible text under the strip, never only in a tooltip. The reason names the minimum
  and what the sample has.
- **Loading:** the strip stays interactive; the KPI values and equation show a `--grid`
  placeholder while `aria-busy="true"`, and the previous page is not blanked. No spinner and no
  motion beyond the placeholder.
- **Errors:** an unknown ticker or a range with too few days puts a sentence in the notice
  style: what went wrong, then what to do ("No prices were returned for XYZ. Check the ticker
  symbol.").
- **Narrow screens:** the search row is full width, chips fill the width in one row, every target
  is at least 44 px tall.
- **Accessibility:** a `form` with a labelled `fieldset` and hidden `legend` "Date range"; chips
  are native radios, so arrow keys work; focus ring as elsewhere; the analysed-range label is
  announced when it changes (`aria-live="polite"`).
- **Print:** hidden. The range line prints.

## J. App shell and sidebar (rev 3, dashboard)

### J.1 Shell

- `<body>` holds a skip link ("Skip to the report", first focusable element, visible on focus),
  then `<div class="shell">` with two children: `<aside class="sidebar">` and `<main id="report">`.
  The sidebar lives outside `<main>`, so every report panel stays a direct child of `<main>` in
  registry order (the panel tests rely on it).
- Sidebar: a **dark navy icon-and-label rail** (owner, 2026-11-18; references in G, rev 3), 280 px,
  `position: sticky; top: 0; height: 100dvh`, its own vertical scroll, `--rail` background, no
  border. The rail stays navy in both themes (darker in dark, M.1).
- Canvas: `--page` (grey), fluid, content capped at 1560 px and left-aligned next to the rail
  (not centred in the remaining space, so the eye does not jump on wide screens). Panels, tiles and
  cards on it are white `--surface`.
- Breakpoints: 1440 px and up, two-up inside panels (C, rev 3); 1100 to 1439 px, stacked panels;
  900 to 1099 px, rail still visible, gutters 24 px; under 900 px, top bar and drawer (J.4).

### J.2 Sidebar contents, top to bottom

All text on the rail is `--rail-ink` (white) or `--rail-ink-2`; the only colour is `--rail-accent`
(cyan). Cyan never appears on a white or grey surface (1.98:1 on white).

1. Product mark: the word "factordesk" (19 px / 600, `--rail-ink`) and under it "Fama-French
   five-factor profile" (14 px, `--rail-ink-2`). No logo image.
2. Ticker search: label "Ticker" (visible, 14 px, `--rail-ink-2`), the combobox (field
   `--rail-field`, 1 px `--rail-ink-2` border, white text, 6 px radius, 44 px tall) and the
   button "Factor it": `--rail-accent` fill with `--rail-on-accent` (navy) text, 8 px radius,
   44 px tall, weight 600. The suggestion list opens over the canvas as a white `--surface` card
   with `--shadow-float`; each row shows the symbol and, when known, the company name in `--ink-2`.
3. Range: label "Date range", a segmented control 3Y | 5Y | Full history (K.2), then From and To
   date fields side by side (stacked when the drawer is narrower than 300 px). Reasons for
   unavailable presets show as visible text under the control.
4. Analysed-range line, one sentence, `aria-live="polite"`: "Analysed 1 Oct 2021 to 30 Sep 2026,
   1,254 trading days." Plus, when days were excluded, "1 excluded." and, when the price runs past
   the factor data, "The last 32 price days are charted but not analysed." This line replaces the
   KPI cells Observations and Analysed range.
5. Factor data: "Factor data ends 30 Sep 2026 (49 days ago)" and a quiet text button "Check for
   newer data" (`--rail-accent` text, existing refresh behaviour).
6. A 1 px rule (`--rail-ink-2` at 25% opacity, decorative), then the two switches (K.1): "Show
   statistics" and "Dark theme".
7. A rule, then the section navigation (J.3), heading "On this page" (14 px, `--rail-ink-2`).
8. At the bottom, pinned to the rail's end when the list is short and after it when long:
   "Download report", an outline button (1 px `--rail-ink-2` border, `--rail-ink` text, download
   icon).

**Icons.** One inline SVG set, about 16 icons, 20 by 20 px, 1.5 px stroke, `currentColor`, each
`aria-hidden="true"` next to a visible label (never an icon alone, except the menu button, which
has the accessible name "Menu"). No icon font and no new dependency.

### J.3 Section navigation and scroll-spy

- A `<nav aria-labelledby>` with a plain `<ul>` of links to panel ids. Items are listed in
  registry order for every panel that rendered (a panel whose section is null, for example
  `lead_lag` today, has no item). Labels, icons and targets are fixed in
  `docs/specs/dashboard-v2.md` (V3.2).
- Each item is 40 px tall: icon, then the label (15 px, `--rail-ink-2`). Hover: `--rail-ink` text.
  The active item: `--rail-ink` text, weight 600, `--rail-active` background, the icon in
  `--rail-accent`, a 3 px `--rail-accent` bar on its left edge, and `aria-current="location"`.
  Colour is not the only signal: weight, background and the bar change too.
- "Data and audit" carries a count badge when the audit has warnings or errors: a 999 px pill,
  14 px / 600, `--caution-50` fill with `--caution` text for warnings and `--neg-50` with `--neg`
  for errors (both tints read on the navy as solid chips), with the hidden text "audit findings"
  (for example "2 audit findings").
- Scroll-spy: one `IntersectionObserver` on the panel elements with `rootMargin: "-20% 0px -70% 0px"`;
  the active item is the last panel in registry order whose top has passed 20% of the viewport.
  At the very bottom of the page the last item is active. The highlight moves with a 150 ms
  background transition (0 ms with reduced motion).
- Activating a link scrolls the panel to the top of the canvas (smooth unless reduced motion),
  moves focus to the panel's `h2` (which gets `tabindex="-1"`), and updates the hash with
  `history.replaceState` so Back is not filled with section jumps.

### J.4 Mobile: top bar and drawer (under 900 px)

- Top bar, 56 px, `--rail` background, sticky: a menu button (44 by 44 px, three-line icon,
  accessible name "Menu"), the ticker (19 px / 600, `--rail-ink`) and the company name truncated
  (`--rail-ink-2`).
- The menu button opens the rail as a native `<dialog>` drawer via `showModal()`: 320 px wide
  (100% under 360 px), sliding from the left in 200 ms, `--shadow-float`, a scrim of
  `rgb(20 26 51 / 0.5)`. The button has `aria-expanded` and `aria-controls`.
- The dialog gives focus trapping and Escape for free; focus starts on the search field and
  returns to the menu button on close. Choosing a section link or pressing "Factor it" closes the
  drawer. The page behind is inert while it is open.

### J.5 Keyboard path

Tab order: skip link, then the rail from top to bottom (search, Factor it, range segments, From,
To, Check for newer data, Show statistics, Dark theme, each section link, Download report), then
the report. `/` focuses the search unless focus is already in a text field (kept). Every target
in the rail is at least 44 px tall except section links (40 px, with no gap but a full-width hit
area, so the 24 px minimum target rule of WCAG 2.2 is met with room).

## K. Switches and segmented controls (rev 3, dashboard)

### K.1 Switches

Two switches, both in the rail, both stored in the URL:

| Label | Default | URL | Off means | On means |
|---|---|---|---|---|
| Show statistics | off | `stats=1` when on, absent when off | plain words, bars and verdicts; statistics columns hidden | t-statistics, p-values, intervals, standard errors, VIF and the other statistics columns appear in tiles, cards and tables (column map in `docs/specs/dashboard-v2.md`, V5) |
| Dark theme | off | `theme=dark` when on, absent when off | light tokens | dark tokens |

- Markup: `<button type="button" role="switch" aria-checked="false|true">` containing the visible
  label text and the track. The label is the accessible name; no separate `aria-label`.
- Track 40 by 24 px, 999 px radius. On the rail: off is a 1.5 px `--rail-ink-2` border on
  `--rail` with an 18 px `--rail-ink-2` thumb at the left (8.21:1); on is a `--rail-accent` fill
  with a `--rail-on-accent` thumb moved 16 px to the right. A switch placed on a light surface
  (none in rev 3, kept for later) uses `--neutral` off and `--accent` teal on. The thumb position
  carries the state as well as colour. The whole row (label plus track) is the hit target, 44 px.
- Keyboard: Space and Enter toggle (native button). Focus ring as F, rev 3.
- Changing a switch updates the URL with `history.replaceState` (a view preference, not a
  navigation; Back still goes to the previous ticker or range). Theme applies to `<html
  data-theme>` at once, before the next paint, so there is no flash.
- Under each switch, one 14 px `--rail-ink-2` line: "Plain words only" or "t, p and intervals
  shown"; "Light" or "Dark". It changes with the state and is `aria-hidden`, since `aria-checked`
  already announces it.

### K.2 Segmented controls

- Used for the range presets (3Y | 5Y | Full history) in the rail and the rolling window
  (126 days | 252 days) in its panel.
- Native radios in a `fieldset` with a visible `legend` (kept from rev 2), drawn as one connected
  control, 8 px outer radius, segments 36 px tall (44 px under 900 px), at least 48 px wide.
- In the rail: track `--rail-field` with a 1 px `--rail-ink-2` border; selected segment
  `--rail-accent` fill, `--rail-on-accent` text, weight 600; unselected `--rail-ink-2` text.
- On a white panel: track `--sunk` with a 1 px `--hairline` border; selected segment `--accent`
  teal fill, `--on-accent` text, weight 600; unselected `--ink-2` text.
- Disabled: 50% opacity text plus a strike-free "not available" in the visible reason line under
  the control; `not-allowed` cursor. Arrow keys move and select (native radio behaviour).

## L. Verdict band, outcome tiles, factor cards and outcome lines (rev 3, dashboard)

The words come from the verdict rules (V-rules) of `docs/specs/dashboard-v2.md`; this section is
the look. Every row here obeys the density rules of C (at most four tiles or cards per row).

### L.1 Verdict band (the one bold element)

- Registry position 200, id `verdict`, replaces the equation. A section with `aria-labelledby`
  pointing at a visually hidden `h2` "Summary".
- `--highlight-50` fill (indigo tint), a 4 px `--highlight` rule on the left edge, 12 px radius,
  32 px padding (20 px under 600 px), no shadow.
- The headline: `--fs-verdict`, 36 px at 900 px wide rising to 40 px at 1440 px (`clamp(36px,
  0.74vw + 29.3px, 40px)`), weight 600, line height 1.25, `--ink`, at most 30 words, max width
  36ch. **Exception, new product choice:** under 600 px the headline is 28 px, because a 36 px
  sentence of 25 words fills more than the first screen at 390 px. Still well above the 14 px
  floor.
- Under a gate or audit hedge (V-rules), the hedge sentence follows the headline at `--fs-lead`
  (19 px), weight 500, `--ink`.
- Then the four outcome tiles (L.2) in one row at 1100 px and wider, two by two from 600 px, one
  per row under 600 px.
- Last line of the band, 14 px `--ink-2`: "Descriptive, in-sample, not predictive." (L-DESC,
  methodology M0.9). Always shown.

### L.2 Outcome tiles

- Four tiles inside the band: "Return beyond its exposures", "How much the model explains",
  "Stock-specific risk", "World beta (quick estimate)". Each is white `--surface`, 12 px radius,
  20 px padding, no border (the tint around it frames it).
- Anatomy: label (15 px / 500, `--ink-2`), value (`--fs-kpi`, 32 px / 600, tabular, `--ink`), one
  plain note (15 px, `--ink`, at most two lines), and with Show statistics on, one statistics line
  (14 px, `--ink-2`).
- A 10 px dot left of the label carries the evidence colour: `--pos` or `--neg` for a
  distinguishable alpha by sign, `--neutral` when not distinguishable, `--caution` when the gate or
  the audit hedges the tile. The note says the same thing in words.
- "How much the model explains" draws a gauge under the value: a 6 px bar, 999 px radius, `--sunk`
  track, `--highlight` fill to the R² share. The gauge is decoration for a number that is printed.
- A tile whose number is not interpretable (audit errors) keeps the value in `--ink-2` and says so
  in the note (validation F4, as the rev 2 KPI strip did).

### L.3 What drives it: factor cards

- Registry position 300, id `factors`, replaces the KPI strip. `h2` "What drives it".
- Five cards in canonical order. To keep four per row at most: at 1100 px and wider the market card
  takes a full row as a wide card (sentence beside the bar), and the four style cards (size,
  value, profitability, investment) sit four across under it; two per row from 600 px; one per row
  below. The market card is the widest because it is usually the largest exposure, not to rank it.
- Card: white `--surface`, 1 px `--hairline` border, 12 px radius, 20 px padding, and a 4 px top
  rule in the direction colour (`--pos`, `--neg` or `--neutral`).
- Anatomy, top to bottom (one idea per block): the plain name (19 px / 600) with the factor code
  after it in `--ink-2` ("Size (SMB)"); the direction pill (999 px radius, 14 px / 600, tint fill,
  evidence-colour text, plus a glyph: up arrow for "Positive", down arrow for "Negative", a dash
  for "Not clear"); the strength bar; the plain sentence (16 px, `--ink`); the "How sure" line
  (15 px: "How sure: Significant" or "How sure: Not significant"); and the link "See the detail"
  (15 px, `--accent`) to the factor's row in the exposures table (`#beta-{name}`), which scrolls to
  and focuses that row exactly as the old equation terms did.
- Strength bar: 8 px tall, centred zero tick in `--axis`, bar from zero in the direction colour,
  faded (`fill-opacity: 0.3` with a full-colour 1 px outline) when not significant, as in rev 2.
  All five bars share one symmetric domain (V-rules, V4.6), so bar lengths compare across cards.
- With Show statistics on, the card adds "beta +0.998, 95% interval +0.994 to +1.002, t 475" in
  14 px `--ink-2` above "How sure".

### L.4 How it performed: performance tiles

- Shown when the optional `performance` section is present (ticket V13), under the verdict band
  and above the notice band, as a row titled "How it performed" (`h3`, 19 px / 600).
- Four white tiles with a 1 px `--hairline` border, same anatomy as L.2: "Return a year",
  "Volatility a year", "Sharpe ratio", "Largest fall". Only the Sharpe tile has an evidence dot.
  Four across at 1100 px and wider, two by two below.
- Caption under the row, 14 px `--ink-2`, always shown: "Past performance over the analysed range.
  It does not predict future returns."

### L.5 Outcome line rule (every panel)

- Every panel's first line under the title is one sentence that states the result for a reader
  who will read nothing else. Lead size (19 px), weight 500, `--ink`, max 2 lines at 1440 px, at
  most 72 characters a line.
- It states a result, not a description of the chart ("Market exposure drives 99.4% of SPY's
  day-to-day risk", not "This chart shows the risk shares").
- It obeys the V-rules: no causation, no forecast, "not distinguishable from zero" for anything
  not significant, a hedge when the gate fired or the audit has errors.
- The copy for every panel is fixed in `docs/specs/dashboard-v2.md`, V4.9. A panel in its empty
  state has no outcome line; the empty state's reason takes its place.

### L.6 Performance panel

- Registry position 450, id `performance`, after Price. Title "Historical performance", question
  "How did the stock do over the analysed range, and how deep were its falls?"
- Body: a drawdown chart (ECharts, in the lazy chart chunk like the price chart): the fall from the
  running peak over time, an area below zero in `--neg-50` with a 1.5 px `--neg` line, the zero line
  in `--axis`, and the largest fall marked by two labelled ticks (peak and trough) plus a dashed
  `--ink-3` line to the recovery date or the label "Not recovered by 30 Sep 2026". Beside it
  (reading rail at 1440 px and wider, below it otherwise) a table of the five largest falls: Peak,
  Trough, Recovered, Fall, Days down, Days to recover (six columns, the density limit).
- A summary table under the chart repeats the four tile numbers with their plain meaning; the
  Sharpe row gains "Standard error" and "95% interval" columns only with Show statistics on.

### L.7 World beta (quick estimate)

- Tile: the fourth outcome tile (L.2). Panel: registry position 350, id `world-beta`, right after
  "What drives it". Title "World beta (quick estimate)", question "How much does the stock move
  with world stocks, compared with the US market?"
- Body: a two-row bar table in the rev 2 style (one row "World stocks (ACWI fund)", one row "US
  market (Mkt-RF), same days"), bars from zero with 95% interval whiskers, so the reader sees
  whether the intervals overlap. Columns: Beta, 95% interval, Days; with Show statistics on, also
  Standard error and R².
- A fixed caption, always shown, 14 px `--ink-2`: "A quick estimate. The iShares MSCI ACWI fund
  (ACWI) stands in for the MSCI All Country World index, which has no free daily data. Past
  co-movement, not a forecast."

## M. Rev 3 tokens, type scale and contrast (dashboard)

### M.1 Colour tokens

**Palette history.** The first rev 3 draft (2026-11-18, from the approved plan) used a white page,
a grey-white sidebar and one ultramarine accent `#2B4EFF`. Later the same day the owner replaced
it with a fintech-tool palette: dark navy rail with bright cyan, grey page with white panels, teal
for interaction, indigo for the verdict highlight. **The table below is the owner's palette.**
Values the owner gave are marked "owner"; the rest (`--ink-3`, `--axis`, `--sunk`, `--rail-active`,
`--rail-field`, `--neutral-50`, the whole dark set except the rail inks and cyan) were derived for
this revision and checked by the script in M.3. Factor hues are unchanged from section A except
dark `--f1`, stepped from `#7053be` to `#775ACA` because it measured 3.0:1 (just under 3:1) on the
navy dark surface.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--page` | `#F4F6FA` (owner) | `#0B1024` | canvas behind the panels |
| `--surface` | `#FFFFFF` (owner) | `#141A33` | panels, tiles, cards, suggestion list |
| `--sunk` | `#F4F6FA` | `#1A2142` | empty states, gauge track, row target wash |
| `--hairline` | `#DDE2EC` (owner) | `#2A3358` | borders, gridlines, rules (decorative) |
| `--ink` | `#0E1430` (owner) | `#EEF1FA` | primary text |
| `--ink-2` | `#4A5470` (owner) | `#A9B3D1` | secondary text, labels |
| `--ink-3` | `#5A6482` | `#929CBD` | footnotes, ticks, captions |
| `--axis` | `#808AA5` | `#6C7699` | zero lines, plot baselines (UI) |
| `--accent` | `#0B7285` (owner, teal) | `#3CC8E8` | links, buttons, focus ring, switches and selected segments on light surfaces |
| `--on-accent` | `#FFFFFF` (owner) | `#141A33` | text on `--accent` |
| `--accent-50` | `#EAF6F8` (owner, teal tint) | `#123247` | selected row, link hover wash |
| `--highlight` | `#3A3F9E` (owner, indigo) | `#A9AEF5` | verdict band rule, R² gauge |
| `--highlight-50` | `#EEEFFB` (owner) | `#22275A` | verdict band fill |
| `--pos` | `#0A7A55` (owner) | `#5ED6AC` | positive sign: bars, pills, top rules |
| `--pos-50` | `#E8F6EF` (owner) | `#0F2E2A` | positive pill fill |
| `--neg` | `#C23345` (owner) | `#EC6876` | negative sign; drawdown line |
| `--neg-50` | `#FCECEE` (owner) | `#3A1A26` | negative pill fill, drawdown area, audit error badge |
| `--caution` | `#8A5A00` (owner) | `#EBB24E` | warnings: notice rule and glyph, hedged tiles |
| `--caution-50` | `#FFF5E0` (owner) | `#302714` | notice band, warning badge |
| `--neutral` | `#4A5470` (owner) | `#A9B3D1` | not significant, "Not clear" pill |
| `--neutral-50` | `#EEF0F5` | `#1F2747` | "Not clear" pill fill |
| `--rail` | `#141A33` (owner, navy) | `#080C1C` | sidebar and mobile top bar |
| `--rail-ink` | `#FFFFFF` (owner) | `#FFFFFF` | text on the rail |
| `--rail-ink-2` | `#A9B3D1` (owner) | `#A9B3D1` | secondary text, icons, borders on the rail |
| `--rail-accent` | `#3CC8E8` (owner, cyan) | `#3CC8E8` | active section, switch on, selected segment, "Factor it" fill, focus ring on the rail. Only on the rail |
| `--rail-on-accent` | `#141A33` (owner) | `#141A33` | text on cyan |
| `--rail-active` | `#232B52` | `#182046` | active nav item background |
| `--rail-field` | `#1C2342` | `#121833` | input and segmented-control track on the rail |
| `--f1` to `--f5` | as section A | as section A, `--f1` `#775ACA` | factor identity (risk, rolling, Kalman) |

Mapping from rev 2 names, so the panel CSS port is mechanical: `--page`, `--surface` and `--sunk`
keep their names with new values; `--border` and `--grid` become `--hairline`; `--ink`, `--ink-2`,
`--ink-3` and `--axis` keep their names with new values; `--ink-faded` becomes `--ink-2`; `--focus`
becomes `--accent`; `--pos` and `--neg` keep their names with new values; the named palette
(`--chalk`, `--sheet`, `--graphite`, `--slate`, `--cobalt`, `--copper`) leaves `frontend/`. Print
keeps forcing the light set with a white page.

### M.2 Type scale (IBM Plex Sans)

| Token | px | Weight | Use |
|---|---|---|---|
| `--fs-caption` | 14 | 400 | footnotes, captions, ticks, legends, badges, statistics lines (the floor) |
| `--fs-table` | 15 | 400 | table cells and headers, tile labels and notes, nav items; tabular figures |
| `--fs-body` | 16 | 400 | prose, card sentences, inputs, buttons |
| `--fs-lead` | 19 | 500 | outcome lines, hedge sentence, card titles (600), company name |
| `--fs-h2` | 24 | 600 | panel titles |
| `--fs-kpi` | 32 | 600 | tile values, the ticker |
| `--fs-verdict` | 36 to 40 (28 under 600 px) | 600 | the verdict headline |

Line height 1.5 for body and table, 1.35 for headings, lead and tile values, 1.25 for the
verdict. `font-variant-numeric: tabular-nums lining-nums` stays on `body`. Table text is 15 px in
rows at least 48 px tall (density rule 3).

### M.3 Contrast and colour-vision check

Computed on 2026-11-18 with the stdlib script below (WCAG 2 relative luminance; OKLab distance
times 100 after the Machado, Oliveira and Fernandes (2009) simulation at severity 1.0, the method
of section A). Requirement: text at least 4.5:1, UI marks at least 3:1. Rows marked "info" have no
requirement. **No required pair fails.** The owner's own figures (for example ink 18.1:1, teal
5.6:1, cyan on navy 8.7:1, indigo 8.8:1) agree with these to the rounding shown.

| Kind | Pair | Light | Dark |
|---|---|---|---|
| text | `--ink` on `--page` | 16.71 | 16.70 |
| text | `--ink` on `--surface` | 18.08 | 15.18 |
| text | `--ink` on `--sunk` | 16.71 | 13.88 |
| text | `--ink` on `--accent-50` | 16.39 | 11.82 |
| text | `--ink` on `--highlight-50` | 15.82 | 12.35 |
| text | `--ink` on `--pos-50` | 16.24 | 12.87 |
| text | `--ink` on `--neg-50` | 15.82 | 13.72 |
| text | `--ink` on `--caution-50` | 16.69 | 13.04 |
| text | `--ink` on `--neutral-50` | 15.86 | 12.92 |
| text | `--ink-2` on `--page` | 6.95 | 9.03 |
| text | `--ink-2` on `--surface` | 7.52 | 8.21 |
| text | `--ink-2` on `--highlight-50` | 6.58 | 6.68 |
| text | `--ink-2` on `--caution-50` | 6.94 | 7.05 |
| text | `--ink-3` on `--page` | 5.42 | 6.92 |
| text | `--ink-3` on `--surface` | 5.87 | 6.29 |
| text | `--accent` on `--page` | 5.16 | 9.53 |
| text | `--accent` on `--surface` | 5.59 | 8.67 |
| text | `--accent` on `--accent-50` | 5.06 | 6.75 |
| text | `--on-accent` on `--accent` | 5.59 | 8.67 |
| text | `--highlight` on `--highlight-50` | 7.71 | 6.68 |
| text | `--highlight` on `--surface` | 8.81 | 8.21 |
| text | `--pos` on `--surface` | 5.35 | 9.54 |
| text | `--pos` on `--page` | 4.94 | 10.50 |
| text | `--pos` on `--pos-50` | 4.80 | 8.09 |
| text | `--neg` on `--surface` | 5.45 | 5.56 |
| text | `--neg` on `--page` | 5.04 | 6.11 |
| text | `--neg` on `--neg-50` | 4.77 | 5.02 |
| text | `--caution` on `--surface` | 5.93 | 8.99 |
| text | `--caution` on `--page` | 5.48 | 9.89 |
| text | `--caution` on `--caution-50` | 5.47 | 7.72 |
| text | `--neutral` on `--surface` | 7.52 | 8.21 |
| text | `--neutral` on `--page` | 6.95 | 9.03 |
| text | `--neutral` on `--neutral-50` | 6.59 | 6.99 |
| text | `--rail-ink` on `--rail` | 17.14 | 19.45 |
| text | `--rail-ink-2` on `--rail` | 8.21 | 9.31 |
| text | `--rail-ink` on `--rail-active` | 13.65 | 15.74 |
| text | `--rail-ink-2` on `--rail-active` | 6.53 | 7.54 |
| text | `--rail-ink` on `--rail-field` | 15.35 | 17.44 |
| text | `--rail-ink-2` on `--rail-field` | 7.35 | 8.35 |
| text | `--rail-accent` on `--rail` | 8.67 | 9.84 |
| text | `--rail-on-accent` on `--rail-accent` | 8.67 | 8.67 |
| UI | `--accent` on `--surface` | 5.59 | 8.67 |
| UI | `--accent` on `--page` | 5.16 | 9.53 |
| UI | `--axis` on `--surface` | 3.44 | 3.83 |
| UI | `--axis` on `--page` | 3.18 | 4.21 |
| UI | `--pos` on `--surface` | 5.35 | 9.54 |
| UI | `--neg` on `--surface` | 5.45 | 5.56 |
| UI | `--neutral` on `--surface` | 7.52 | 8.21 |
| UI | `--rail-accent` on `--rail` | 8.67 | 9.84 |
| UI | `--rail-accent` on `--rail-active` | 6.90 | 7.96 |
| UI | `--rail-ink-2` on `--rail` (switch off, field border) | 8.21 | 9.31 |
| UI | `--rail-ink-2` on `--rail-field` | 7.35 | 8.35 |
| UI | `--f1` on `--surface` | 5.26 | 3.35 |
| UI | `--f2` on `--surface` | 6.39 | 3.10 |
| UI | `--f3` on `--surface` | 4.46 | 4.28 |
| UI | `--f4` on `--surface` | 3.47 | 4.81 |
| UI | `--f5` on `--surface` | 3.40 | 5.65 |
| info | `--hairline` on `--surface` | 1.30 | 1.40 |
| info | `--hairline` on `--page` | 1.20 | 1.54 |
| info | `--rail-accent` on `--surface` (why cyan stays on the rail) | 1.98 | 8.67 |

Sign pair separation (OKLab x 100; rev 2 floor: 8 under any simulation, 15 normal):

| Theme | Normal | Protanopia | Deuteranopia | Tritanopia | OKLab L (pos, neg) |
|---|---|---|---|---|---|
| Light (`#0A7A55` / `#C23345`) | 27.6 | 9.2 | **6.6 (below 8)** | 31.3 | 0.514, 0.545 |
| Dark (`#5ED6AC` / `#EC6876`) | 30.2 | 23.0 | 10.9 | 35.5 | 0.796, 0.682 |

- The light pair has almost the same lightness, so a deuteranope sees two similar browns. The
  owner set these two values, so they are kept and the miss is recorded: sign is also carried by
  position (left or right of zero), the `+` or `−` on every number, the pill word and its arrow
  glyph, so no reading depends on the hue. Owner question at the Stage 1 gate: darken the green
  (a lightness gap of about 0.1 in OKLab L passes, as the dark pair shows) or accept.
- Dark `--neg` was first `#F07A88` (deuteranopia 7.4) and was stepped to `#EC6876`.
- `tokens.test.ts` (ticket V3) asserts every required pair of this table with the same thresholds,
  and `busyContrast.test.ts` re-checks the loading placeholder on the new surfaces.

The script (stdlib only, `python contrast.py`; it prints every pair and exits with the number of
failures):

```python
import math, sys
LIGHT = {"page": "#F4F6FA", "surface": "#FFFFFF", "sunk": "#F4F6FA", "hairline": "#DDE2EC",
         "ink": "#0E1430", "ink-2": "#4A5470", "ink-3": "#5A6482", "axis": "#808AA5",
         "accent": "#0B7285", "on-accent": "#FFFFFF", "accent-50": "#EAF6F8",
         "highlight": "#3A3F9E", "highlight-50": "#EEEFFB", "pos": "#0A7A55", "pos-50": "#E8F6EF",
         "neg": "#C23345", "neg-50": "#FCECEE", "caution": "#8A5A00", "caution-50": "#FFF5E0",
         "neutral": "#4A5470", "neutral-50": "#EEF0F5", "rail": "#141A33", "rail-ink": "#FFFFFF",
         "rail-ink-2": "#A9B3D1", "rail-accent": "#3CC8E8", "rail-on-accent": "#141A33",
         "rail-active": "#232B52", "rail-field": "#1C2342", "f1": "#7559c5", "f2": "#066e33",
         "f3": "#c25078", "f4": "#1995ba", "f5": "#a18a21"}
DARK = {"page": "#0B1024", "surface": "#141A33", "sunk": "#1A2142", "hairline": "#2A3358",
        "ink": "#EEF1FA", "ink-2": "#A9B3D1", "ink-3": "#929CBD", "axis": "#6C7699",
        "accent": "#3CC8E8", "on-accent": "#141A33", "accent-50": "#123247",
        "highlight": "#A9AEF5", "highlight-50": "#22275A", "pos": "#5ED6AC", "pos-50": "#0F2E2A",
        "neg": "#EC6876", "neg-50": "#3A1A26", "caution": "#EBB24E", "caution-50": "#302714",
        "neutral": "#A9B3D1", "neutral-50": "#1F2747", "rail": "#080C1C", "rail-ink": "#FFFFFF",
        "rail-ink-2": "#A9B3D1", "rail-accent": "#3CC8E8", "rail-on-accent": "#141A33",
        "rail-active": "#182046", "rail-field": "#121833", "f1": "#775ACA", "f2": "#19783c",
        "f3": "#cb587f", "f4": "#1493b8", "f5": "#aa932d"}
def lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def rgb(h): return [int(h[i:i + 2], 16) for i in (1, 3, 5)]
def lum(h):
    r, g, b = (lin(c) for c in rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)
def oklab(v):
    r, g, b = v
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)
MACHADO = {"protan": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216],
                      [-0.003882, -0.048116, 1.051998]],
           "deutan": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413],
                      [-0.011820, 0.042940, 0.968881]],
           "tritan": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602],
                      [0.004733, 0.691367, 0.303900]]}
def sim(h, kind):
    v = [lin(c) for c in rgb(h)]
    if kind == "normal": return v
    m = MACHADO[kind]
    return [min(1, max(0, sum(m[i][j] * v[j] for j in range(3)))) for i in range(3)]
def delta_e(a, b, kind): return 100 * math.dist(oklab(sim(a, kind)), oklab(sim(b, kind)))
TEXT = ([("ink", x) for x in ("page", "surface", "sunk", "accent-50", "highlight-50", "pos-50",
                              "neg-50", "caution-50", "neutral-50")]
        + [("ink-2", x) for x in ("page", "surface", "highlight-50", "caution-50")]
        + [("ink-3", "page"), ("ink-3", "surface"), ("accent", "page"), ("accent", "surface"),
           ("accent", "accent-50"), ("on-accent", "accent"), ("highlight", "highlight-50"),
           ("highlight", "surface")]
        + [(c, x) for c in ("pos", "neg", "caution", "neutral") for x in ("surface", "page", c + "-50")]
        + [("rail-ink", "rail"), ("rail-ink-2", "rail"), ("rail-ink", "rail-active"),
           ("rail-ink-2", "rail-active"), ("rail-ink", "rail-field"), ("rail-ink-2", "rail-field"),
           ("rail-accent", "rail"), ("rail-on-accent", "rail-accent")])
UI = ([("accent", "surface"), ("accent", "page"), ("axis", "surface"), ("axis", "page"),
       ("pos", "surface"), ("neg", "surface"), ("neutral", "surface"), ("rail-accent", "rail"),
       ("rail-accent", "rail-active"), ("rail-ink-2", "rail"), ("rail-ink-2", "rail-field")]
      + [(f"f{i}", "surface") for i in range(1, 6)])
fails = 0
for name, p in (("light", LIGHT), ("dark", DARK)):
    for kind, pairs, need in (("text", TEXT, 4.5), ("UI", UI, 3.0)):
        for fg, bg in pairs:
            r = ratio(p[fg], p[bg])
            fails += r < need
            print(name, kind, fg, "on", bg, f"{r:.2f}", "pass" if r >= need else "FAIL")
    print(name, "sign pair", {k: round(delta_e(p["pos"], p["neg"], k), 1)
                              for k in ("normal", "protan", "deutan", "tritan")})
sys.exit(fails)
```

