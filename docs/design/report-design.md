# Report design: single-ticker factor profile

Design spec for the one-page HTML report. The prototype is `docs/design/prototype/report.html`,
built from the mock fixture by `docs/design/prototype/build_prototype.py` (stdlib only) with the
stylesheet source `docs/design/prototype/report.css`. Screenshots sit next to it
(`shot_{1440,390}_{light,dark}.png`, `shot_1920_light.png` to check the width cap,
`*_empty.png` for the insufficient-data states, `report-print.pdf` for print). The dashboard
controls mock is `report-controls.html` (`build_prototype.py --controls`,
`shot_1440_light_controls.png`).

Contents: A. palette and tokens. B. type. C. layout. D. panels. E. motion. F. accessibility.
G. self-critique. H. integration notes and schema gaps. I. dashboard controls.

Revision 2 (owner review of the live report, 2026-11-18): density, price cut-off wording, marker
sizes, and range controls. Changes are marked "Rev 2" below.

## Principles

1. **Colour is evidence.** Chrome is ink on neutral surfaces. Colour appears only where it encodes
   data: sign (blue/copper) or factor identity (five categorical hues). There is no brand accent;
   interaction states use the ink colour.
2. **The chart is a table.** Every bar panel is a real `<table>`: one row per factor, the bar lives
   in a cell, the numbers sit in right-aligned tabular columns beside it. Screen readers, print and
   copy-paste get the numbers; sighted readers get the bars.
3. **Uncertainty is visible, never colour-only.** Not significant = faded fill + full-colour
   outline + the word "No" in a "Significant" column (and "not significant" in the equation).
4. **Every panel answers a question** in plain words and ends with one method footnote.
5. **One bold element**: the fitted equation, typeset as mathematics. Everything else is quiet.

## A. Palette and tokens

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

## C. Layout

- Single column, max 1216 px wide (1152 px content). Text is left-aligned; numbers are
  right-aligned.
- **Rev 2: the cap is a hard rule.** The live renderer used 1680 px and stretched every table to
  about 1650 px, which is what read as "too wide and spread apart". Check at 1920 px
  (`shot_1920_light.png`): the content stays 1216 px wide and centred.
- **Rev 2: no stretched columns.** Number columns have a fixed measure (72 to 92 px); no column
  is wider than its content plus 24 px of gap. A table that looks sparse is fixed by dropping a
  column, not by widening the others.
- Two-up panels were rejected because they starve the plot column.
- Spacing scale (dense): 4, 8, 12, 16, 24, 32, 48.
- Bar row height 44 px (30 px plot strip on mobile).
- Shape rule: panels and the KPI strip have a 6 px radius, controls 4 px, bars 2 px, key squares
  1 px. No shadows, no gradients.

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

### 1. Header, range line and data-quality notice

Rev 2: the header was two rows of badges plus a paragraph. It is now three short pieces.

- Row 1: ticker at 44.8/640, "Fama-French five-factor profile", and on the right two chips: "Factor
  data ends 30 Sep 2026 (49 days ago)" (plain) and "2 warnings" (a link to the notice, ink,
  weight 560). No outlined badges, no middle dots.
- Range line: "Analysed 8 Aug 2024 to 30 Sep 2026, 559 trading days. The last 32 price days are charted
  but not analysed." One sentence pair, 76ch maximum.
- Notice (only when `warnings[]` is non-empty): a framed strip with a 3 px ink left rule, the
  warning glyph, and a **two-line plain summary**, for example "Prices look out of step with the
  factor data, so R² and residual volatility are probably understated." A "Details" disclosure
  holds the raw messages (and, in the dashboard, the 5-day estimate line). The hidden prefix
  "Warning:" stays for screen readers.
- The generated time moves to the colophon. Dates in prose read like "8 Aug 2024".
- In the dashboard the range line is replaced by the controls (section I).

### 2. Equation (the memorable element)

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
- **Focus:** a 2 px Graphite `:focus-visible` outline with 2 px offset, on equation links, window
  labels and the scroll region.
- **Table semantics:** bar tables have a hidden `<caption>`, `scope` attributes and explicit ARIA
  roles, because mobile restyles rows as grids. SVGs are `aria-hidden`.
- **Colour independence:**
  - Sign: position + glyph + colour.
  - Significance: fade + outline + the word.
  - Residual: hatch + label.
  - Identity: the name next to every mark.
- **Themes:** `prefers-color-scheme` by default; `<html data-theme>` overrides it both ways
  (verified).
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
7. **Optional security name** for the header.
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
