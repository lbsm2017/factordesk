# Dashboard v2 prototype (rev 3)

The visual target for Dashboard v2, for owner approval before the React port. It is a static
HTML page built from the mock fixture; the statistics switch, the segmented controls and the phone
drawer work in a browser without JavaScript. Light theme only (owner, 2026-11-19). The rev 2 files
next to it (`build_prototype.py`, `report.css`, `report*.html`, `shot_*.png`) are unchanged.

| File | What it is |
|---|---|
| `build_prototype_v3.py` | Generator (stdlib only). Reads `backend/factordesk/tests/fixtures/mock_report.json`, writes `report-v3.html` and `report-v3-empty.html`. Imports formatting helpers from `build_prototype.py`. |
| `report-v3.css` | Stylesheet, inlined by the generator. Token block and shape rule at the top. |
| `report-v3.html` | The prototype with the full mock data. Open it in Chrome or Edge. |
| `report-v3-empty.html` | Every statistic set to "not enough data", and a short price history (10Y disabled). |
| `contrast_v3.py` | Contrast of every text and UI pair, read from the tokens. |
| `preflight_v3.py` | Mechanical slop pre-flight: the counts below. |
| `shoot_v3.py` | Screenshots and layout measurements with headless Chrome. |
| `fonts/ibm-plex-sans.woff2` | IBM Plex Sans, Latin subset, variable weight 400 to 700. Licence: `fonts/IBMPlexSans-OFL.txt`. |
| `shot_v3_*.png` | Screenshots, listed below. |

## Design plan

**Subject, audience, job.** A factor profile of one stock for an investor or an adviser's
client who does not read statistics. The first screen gives the verdict in words; the evidence is
one scroll or one switch away.

**Palette.** One accent family, one cool grey family, evidence colours kept for meaning.

| Token | Value | Role |
|---|---|---|
| `--rail` | `#141A33` | navy sidebar |
| `--rail-cyan` | `#3CC8E8` | the accent on navy: current section, switch on, "Factor it", selected range; never text on white |
| `--accent` | `#0B7285` | the accent on light surfaces: links, verdict rule, focus ring, selected segment |
| `--page` / `--surface` | `#F4F6FA` / `#FFFFFF` | grey page, white panels |
| `--ink` / `--ink-2` / `--ink-3` | `#0E1430` / `#4A5470` / `#5A6482` | text; ink also draws estimates, dots and meters |
| `--line` / `--grid` | `#DDE2EC` / `#EBEEF4` | hairlines |
| `--pos` / `--neg` / `--caution` | `#007862` / `#C23345` / `#8A5A00` | evidence: direction words and bars, warnings |
| `--f2` to `--f5` | rev 2 validated set | factor identity in the risk and rolling charts only; market uses ink |

**Type.** IBM Plex Sans only. Body 16, captions and the smallest text 14, tables 15 tabular,
outcome lines 19, panel titles 24, figures 32, verdict 38 (32 under 1100 px, 28 on phones).
Weights 400, 500, 600; 700 only for the ticker. Sentence case, no all-caps, no monospace.

**Shape rule** (stated in `report-v3.css`, checked by `preflight_v3.py`):

- Panels and the verdict band: 10.
- Inputs, buttons, nav items, the segmented control: 6; segmented items inside it: 4.
- Chart marks, key squares, icons: 2. The product mark: 6.
- Switch track and thumb: fully round. Nothing else is round; there are no capsules.
- No shadows anywhere.

**Layout.**

```text
+-- navy rail 280 ------+-- canvas, grey page, max 1560, 40 px gutters -----------------+
| factordesk            | SPY  SPDR S&P 500 ETF Trust                                   |
| [SPY      ][Factor it]| Listed on NYSE Arca, priced in US dollars. Factor data to ... |
| [3Y|5Y|10Y|Full hist.]| 2 warnings (link)                                             |
| From [..]  To [..]    | +-- verdict band: white, 4 px teal left rule ---------------+ |
| Analysed ... 559 days | | One plain headline sentence, 38 px                        | |
| Factor data ... old   | | 559 trading days, dates. Past data, not a forecast.       | |
| Check for newer data  | | | amber rule: two plain sentences, Details                | |
| Show statistics  (o-) | | ---------------------------------------------------------| |
| Sections (icons)      | | Beyond its risks | How much it explains | Specific risk    | |
|  > Summary            | +-----------------------------------------------------------+ |
|    ...                | How it performed: 4 figures split by hairlines                |
| [Download report]     | What drives it: Market (wide) | World beta; then 4 factors    |
+-----------------------+  Panels: outcome sentence, chart-table left, reading right   |
```

Under 1100 px the figures stack and the factors go two by two; under 900 px the rail becomes a
navy top bar with a menu button and a drawer; under 720 px bar tables become stacked rows.

**Principles.**

1. Outcome first: every panel opens with one plain sentence that states the result.
2. One memorable element, the verdict band; everything else is white panels and hairlines.
3. Flat inside panels: figures, factors and lists are separated by hairlines, never boxed.
4. One label per intent: significance is always "Clear evidence" or "Could be noise".
5. Statistics on demand: "Show statistics" adds t, p, intervals, VIF and extra columns; with it
   off no table shows more than 6 columns.
6. Colour is never the only signal: words, signs and position carry the meaning too.
7. Motion only answers an action (switch thumb, drawer); none with reduced motion.

**Review against the generic defaults, and what changed.**

- First pass: the five factor cards in one row of identical tiles became a wide market card next to
  the world beta and four style factors below; the big-number hero became a sentence.
- Owner review of v3 ("remove the typical AI elements"), applied with the ui-taste anti-slop laws:
  - indigo dropped: one accent family (teal on light, cyan on navy);
  - cards inside the verdict band and inside "What drives it" replaced by flat rows with hairline
    dividers;
  - the tinted warning card (icon, bold lead-in, chevron) became a quiet note with an amber rule;
  - every filled pill became a plain weight-600 label; coloured card stripes removed;
  - header chips became plain subline text; "How sure:" prefixes removed;
  - one radius rule; all shadows removed; dark theme and its switch removed.
- ui-taste asks for a generated target image first. No image generator was available, so these
  screenshots are the target.

## Rebuild

```sh
python docs/design/prototype/build_prototype_v3.py          # report-v3.html
python docs/design/prototype/build_prototype_v3.py --empty  # report-v3-empty.html
python docs/design/prototype/contrast_v3.py                 # contrast table, exit 1 on a failure
python docs/design/prototype/preflight_v3.py                # slop counts, exit 1 on a failure
```

`--on stats,menu,win126 --out PATH` pre-checks inputs for the screenshot variants.

## Screenshots

```sh
python docs/design/prototype/shoot_v3.py           # every shot
python docs/design/prototype/shoot_v3.py measure   # scrollWidth, clientWidth, scrollHeight
```

Headless Chrome CLI only (`--screenshot`, `--dump-dom`). On Windows the headless window is at least
500 px wide, so 390 px shots render the page in a 390 px iframe and crop the PNG with a small
stdlib PNG decoder in `shoot_v3.py`. Set `CHROME` if Chrome is not at the default path.

Shots: `shot_v3_1920_light`, `shot_v3_1440_light`, `shot_v3_1440_stats_on`, `shot_v3_1024_light`,
`shot_v3_390_light`, `shot_v3_390_drawer`, `shot_v3_1440_full_light`, `shot_v3_390_full_light`,
`shot_v3_1440_empty` (10Y disabled with its reason), and tall crops: `shot_v3_crop_drivers`,
`shot_v3_crop_exposures_stats_off`, `shot_v3_crop_exposures_stats_on`, `shot_v3_crop_performance`,
`shot_v3_crop_risk_rolling`, `shot_v3_crop_deeper`, `shot_v3_crop_audit_stats_on`,
`shot_v3_390_crop_tables`.

## Checks

**Slop pre-flight** (`preflight_v3.py`):

| Check | Count | Target |
|---|---|---|
| Accent hue families | 1 (teal `#0B7285`, cyan `#3CC8E8`, tint `#EAF6F8`) | 1 |
| Grey families | 1 (15 cool neutrals, hue 150 to 270) | 1 |
| CSS radii outside the rule | 0 (used: 10, 6, 4, 2, round) | 0 |
| SVG corner radii outside the rule | 0 (used: 2, 6) | 0 |
| Emoji in the page | 0 | 0 |
| Gradients | 0 | 0 |
| Shadows | 0 | 0 |
| Filled capsules outside the switch | 0 | 0 |
| Pill elements | 0 | 0 |
| Duplicate labels for significance | 0 ("Clear evidence" x13, "Could be noise" x20) | 0 |
| Nested boxes in the content | 0 | 0 |
| Em dashes, middle-dot meta strings | 0, 0 | 0 |
| Weights above 600 | 1 (the ticker) | 1 |

**Contrast** (`contrast_v3.py`, WCAG 2 ratio; text 4.5, UI 3.0). All pairs pass.

| Pair | Ratio | Use |
|---|---|---|
| ink on page / surface | 16.71 / 18.08 | text, verdict headline |
| ink-2 on page / surface | 6.95 / 7.52 | sublines, secondary text |
| ink-3 on surface / soft | 5.87 / 5.42 | ticks, footnotes |
| teal on surface / page / tint | 5.59 / 5.16 / 5.06 | links, Details |
| white on teal | 5.59 | selected segment |
| positive / negative / caution on surface | 5.44 / 5.45 / 5.93 | labels, worst fall, warning |
| caution on page | 5.48 | warnings link |
| rail text / secondary / cyan on navy | 17.14 / 8.21 / 8.67 | rail |
| cyan / white on rail highlight | 7.38 / 14.59 | current section |
| navy on cyan | 8.67 | "Factor it", selected range |
| UI: control line, switch track off, zero line | 3.77 / 3.78 / 3.77 | borders, marks |

**Horizontal scroll** (`shoot_v3.py measure`: a script in the page writes
`scrollWidth x clientWidth x scrollHeight` into a meta tag, read back with `--dump-dom`; at 390 px
the page posts it from the iframe): 390 px 390/390, 1024 px 1008/1008, 1440 px 1424/1424, with
statistics off, on, and the drawer open. No horizontal scroll.

**Smallest font size** in `report-v3.css`: 14 px (`--fs-cap`); no em, rem or percentage sizes.
The four range presets (3Y, 5Y, 10Y, Full history) fit the 240 px inside the rail at 14 px.

**Vercel web interface guidelines** (fetched from `vercel-labs/web-interface-guidelines`). Fixed:
skip link, heading order, field names and an example placeholder, transform-only motion,
`touch-action` and a deliberate tap highlight, safe-area padding and a scroll offset under the
sticky top bar, `theme-color`, `translate="no"` on brand, ticker and fund name, hover on every
control, a working Download link. Remaining, by design or for the React port:

- `report-v3.html:680`, `:666`: switch and range state are not in the URL (CSS-only prototype; the port keeps `stats` and the range in the URL).
- `report-v3.html:659`: the search form does not submit and has no inline error (mock).
- `report-v3.html:677`: "Check for newer data" has no action (mock).
- `report-v3.html:672`, `build_prototype.py:70`: dates are formatted by hand ("8 Aug 2024"), not with `Intl.DateTimeFormat`; the port should use Intl.
- `report-v3.html:746` and the other bar tables: each table is a focusable scroll region (`tabindex="0"`), which adds tab stops; kept so the wide statistics view scrolls from the keyboard.
- `report-v3.css:212`, `:216`: the current section is static plus a `:target` follow; scroll-spy belongs to the port.
- `report-v3.html:707` and every heading and button: sentence case on purpose (project rule), not Title Case.
- `report-v3.css:190`: native date inputs keep the browser's own picker.

## Notes for the port

- Demo values, keyed by ticker in the generator: company name and listing (`SECURITY`), years of
  price history (`HISTORY_YEARS`; a preset longer than the history is disabled with the reason
  shown), historical performance (`PERFORMANCE`), world beta against the ACWI fund (`WORLD`). The
  residual, Kalman and shrunk panels use demo values too; each panel says so.
- Kept on purpose: evidence colours on direction words and bars (green positive, red negative,
  always with the word and the sign); five factor hues in the risk and rolling charts, because
  they encode identity, not interaction; the teal rule on the verdict band as the one accent
  surface.
- The IBM Plex Latin subset has no Greek; the Kalman column is labelled "Drift", not lambda.
