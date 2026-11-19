# Dashboard prototype, rev 4: tearsheet (v4a) and compact dashboard (v4b)

Written 2026-11-19, after the owner's review of rev 3: the layout looked templated, and the look
and feel should be more professional and less dispersed. Two variants from one generator so the
owner can choose. Rev 3 files (`*-v3*`) are unchanged.

| File | What it is |
|---|---|
| `build_prototype_v4.py` | Generator. `--variant a` or `b` (default both), `--on stats,menu,win126`, `--out PATH` |
| `report-v4.css` | Shared tokens and components; per-variant rules under `.v-a` and `.v-b` sections |
| `report-v4a.html` | Variant a, tearsheet |
| `report-v4b.html` | Variant b, compact dashboard |
| `shoot_v4.py` | Screenshots (`shot_v4a_*`, `shot_v4b_*`) and `measure` (horizontal overflow check) |
| `preflight_v4.py` | Mechanical slop and contrast pre-flight over the CSS and both pages |
| `PRODUCT-v4.md` | Product context this round was built against (inferred, see the last section) |

```
python docs/design/prototype/build_prototype_v4.py
python docs/design/prototype/shoot_v4.py
python docs/design/prototype/preflight_v4.py
```

Same mock fixture, same plain-language rules and demo values as rev 3 (imported, not copied).

## The two variants

**v4a, tearsheet.** Title row (ticker, name, type badge, Download report), then an analysis bar
(analysis period, observations, factor data date, benchmark ACWI), then one Summary panel: the
verdict as one 16 px sentence, the data notes in one caution line, and two columns: a key metrics
table (Performance: annualised return, volatility, Sharpe ratio, max drawdown; Factor model:
alpha, R², residual volatility, beta to US market, beta to ACWI; columns Value and Reading, plus
t and 95% interval when statistics are on) beside the price chart with the analysed window
shaded. Below: drawdown with the largest falls, factor exposures, world beta, return and risk
sources side by side, exposure over time, the deeper checks, data and audit, regression detail.

**v4b, compact dashboard.** Title row with the analysed range in the listing line, a one-line
summary bar (verdict and data notes), a strip of six key figures in one bordered row (label above
value, one short reading below, no paragraphs), then two-up panels: Price beside Drawdown; Factor
exposures and Return sources beside World beta and Risk sources; then the same lower sections.

Both: the first screen at 1440 x 900 shows the verdict, every key metric and at least one chart
(`shot_v4a_1440.png`, `shot_v4b_1440.png`).

Three lines to choose between them:

- v4a reads like an institutional tearsheet: one dense summary table you scan top to bottom, the
  price chart beside it, and every reading in the same column.
- v4b reads like a monitoring dashboard: six figures at a glance, then two charts side by side;
  faster to skim, but the readings are spread over six cells instead of one column.
- v4a holds more in the first screen (nine metrics with readings); v4b shows two charts in it.

## Critique: rev 3 against rev 4

What read as templated in rev 3, and what rev 4 does instead:

| Rev 3 | Why it read as templated | Rev 4 |
|---|---|---|
| A 38 px, three-line verdict used as a hero | The marketing hero pattern on a working tool | One 16 px sentence inside the summary (v4a) or a one-line bar (v4b) |
| Big number + unit + paragraph tiles, repeated in rows | The KPI-card trope; numbers set apart from each other | A key metrics table with right-aligned tabular numbers (v4a); one bordered strip of six compact cells (v4b) |
| Explanatory prose under every number | Reads like a tutorial, not a tool | Explanations in column-header and row-label tooltips (dotted underline), "How this is computed" at the panel foot, statistics behind the switch |
| Dot-on-a-range and meter mini-charts inside tiles | Decorative instruments standing in for data | Removed; intervals live in the t and 95% interval columns and in the inline bar tables |
| Coloured left rule on the hero card and the notice | A stock "callout" device | Gone; the data notes are one caution-coloured line with an icon and the word "data notes" |
| Every section a floating panel with 24 to 32 px padding, 40 px gutters | Dispersed; one idea per screen | 8 px radius, 16 to 20 px padding, 16 px gutters, 12-column grid, two panels side by side from 1280 px |
| Labels such as "Beyond its risks", "How much the model explains" | Cute rather than standard | Standard finance labels: Annualised return, Volatility, Sharpe ratio, Max drawdown, Alpha (annual), R², Residual volatility, Beta to US market, Beta to ACWI |
| A panel outcome sentence at 19 px with a side column of reading notes | Two layers of prose per panel | One 15 px takeaway line under the title row; the title row carries the period or the control on the right |

What still reads as less than professional, honestly:

- The panel takeaway lines are still prose. They are kept because the owner's readers include
  non-statisticians (PRODUCT-v4.md, principle 2); deleting them is a one-line change in `panel()`.
- At 390 px the inline bar columns are hidden and the tables show numbers and readings only
  (exposure over time keeps its small multiples). A phone layout with bars under each row is
  possible but adds CSS for a secondary use.
- Panels in one row stretch to equal height, so the shorter one carries some blank space at the
  bottom (Drawdown beside Price in v4b, Risk sources in v4b's right column).
- v4b's six cells hold seven figures: residual volatility sits under volatility and the market
  beta under R², so the first screen still shows every key metric.

## Tokens

| Token | Value | Use |
|---|---|---|
| `--page` | #F4F6FA | Page ground |
| `--surface` | #FFFFFF | Panels, analysis bar, KPI strip, summary bar |
| `--soft` | #F7F8FB | Table row hover, segmented hover |
| `--line` | #DDE2EC | Panel borders, dividers |
| `--grid` | #EBEEF4 | Table row rules, chart grid |
| `--rule` | #0E1430 | Table header rule, total row rule |
| `--mark-ns` | #C3CAD9 | Bars that could be noise, specific-risk bar, tooltip underline |
| `--axis` | #7A839E | Axis and zero lines (never text) |
| `--ink` | #0E1430 | Text, price line |
| `--ink-2` | #4A5470 | Secondary text, labels, axis labels, clear-evidence bars |
| `--accent` | #0B7285 | The one accent on light surfaces: links, buttons, selected segment, end-of-data line |
| `--accent-50` | #EDF6F8 | Analysed-window shade |
| `--rail` | #141A33 | Sidebar and phone top bar |
| `--rail-cyan` | #3CC8E8 | Cyan, only on navy |
| `--pos` / `--neg` / `--caution` | #007862 / #C23345 / #8A5A00 | Evidence; the word is always present |
| `--neg-50` | #FBE9EC | Drawdown area |
| `--f1` to `--f5` | as rev 3 | Factor identity, exposure-over-time chart only |

## Shape, grid and type

- **Radius rule:** panels, analysis bar, KPI strip and summary bar 8 px; inputs, buttons, nav
  items, segmented control and type badge 6 px; segmented inner items 4 px; chart marks 2 px;
  switch track and thumb fully round; everything else square. One 1 px border per box, no shadow.
- **Grid:** 12 columns, 16 px gutters (12 px on phones), 24 px page margin (16 px under 900 px).
  From 1280 px panels pair as 6 + 6 or 7 + 5; the Kalman and shrunk panels pair only from
  1680 px because their tables are wide. Under 1280 px every panel spans 12.
- **Panel:** title row (18 px title left, period, unit or control right), an optional 15 px
  takeaway line, the body, then "How this is computed". Padding 16 px by 20 px.
- **Tables:** 36 px rows, 15 px text, 14 px header with a 1 px ink rule, numbers right-aligned in
  tabular figures, a 1 px hairline between rows, row hover on `--soft`.
- **Type scale (IBM Plex Sans, tabular numerals):** 14 captions, table headers, axis labels |
  15 body and tables | 16 verdict and sub-heads | 18 panel titles | 22 KPI values | 26 page title
  (22 on phones). Weights 400, 500, 600; 700 only on the ticker.

## Slop pre-flight (`python docs/design/prototype/preflight_v4.py`)

| Check | Count | Target |
|---|---|---|
| Accent hue families | 1 | 1 |
| Grey families | 1 | 1 |
| Radii outside the shape rule | 0 | 0 (used: 8, 6, 4, 999 px; SVG rx 2 and 6) |
| Emoji | 0 | 0 |
| Gradients | 0 | 0 |
| Shadows | 0 | 0 |
| Pills outside the segmented control and switch | 0 | 0 |
| Duplicate labels for one intent | 0 | 0 (only "Clear evidence" and "Could be noise") |
| Nested bordered boxes (v4a, v4b) | 0, 0 | 0 |
| Hero headlines | 0 | 0 |
| Text under 14 px | 0 | 0 |
| Em dashes, all-caps text | 0, 0 | 0 |
| Text colour pairs under 4.5:1 | 0 of 17 | 0 |

`shoot_v4.py measure`: no horizontal page scroll at 390, 1024, 1440 or 1920 px, statistics on or off.

## Mechanical detector

`impeccable detect --json` on report-v4a.html, report-v4b.html and report-v4.css, after fixes:

- Fixed: low contrast on the en dash placeholder in table cells (was `--axis` on the hover
  ground, 3.6:1; now `--ink-2`).
- Not changed: "cramped padding" on the segmented control (the 2 px inset is the control's
  frame; each option has its own 10 px padding and the selected fill, as in native segmented
  controls).
- Not changed, advisory: "flat type hierarchy", measured at the phone size (14, 16, 18, 22 px).
  The steps follow the owner's pinned sizes and the product-UI ratio of 1.125 to 1.2; the
  heading levels are also separated by weight. At desktop the title to panel step is 26 to 18.

## Screenshots

`shot_v4{a,b}_1440.png` first screen, `_1440_full`, `_1920`, `_1024`, `_1024_full`, `_390`
and `_390_full` (rendered in a 390 px frame and cropped), `_390_crop_tables`, `_1440_stats_on`
and `_1440_full_stats_on`.

## Process notes

- No product interview took place; PRODUCT-v4.md was inferred from README.md, docs/overview.md,
  docs/specs/dashboard-v2.md and the owner's notes, with every assumption labelled. It sits here,
  not at the repository root.
- The direction was pinned whole by the owner's brief (palette, type, sidebar, references and
  both layouts), so no concept roll was run, no surface brief or DESIGN.md was written, and the
  build was code-first. The critique above was done in the same pass, not by a separate reviewer.
- No new runtime dependency: plain CSS and inline SVG, the bundled IBM Plex Sans, no chart
  library, no CDN. Interactions (statistics switch, range presets, window toggle, phone drawer,
  disclosures) are native inputs and CSS `:has()`.
