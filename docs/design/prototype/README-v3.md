# Dashboard v2 prototype (rev 3)

The visual target for Dashboard v2, for owner approval before the React port. It is a static
HTML page built from the mock fixture; the switches, segmented controls and the phone drawer work
in a browser without JavaScript. The rev 2 files next to it (`build_prototype.py`, `report.css`,
`report*.html`, `shot_*.png`) are unchanged.

| File | What it is |
|---|---|
| `build_prototype_v3.py` | Generator (stdlib only). Reads `backend/factordesk/tests/fixtures/mock_report.json`, writes `report-v3.html` and `report-v3-empty.html`. Imports formatting helpers from `build_prototype.py`. |
| `report-v3.css` | Stylesheet, inlined by the generator. Token block at the top (light, then dark). |
| `report-v3.html` | The prototype with the full mock data. Open it in Chrome or Edge. |
| `report-v3-empty.html` | Every statistic set to "not enough data". |
| `contrast_v3.py` | Reads the token blocks and prints the contrast of every text and UI pair. |
| `shoot_v3.py` | Screenshots and layout measurements with headless Chrome. |
| `fonts/ibm-plex-sans.woff2` | IBM Plex Sans, Latin subset, variable weight 400 to 700 (Google Fonts build of the IBM release). Licence: `fonts/IBMPlexSans-OFL.txt`. |
| `shot_v3_*.png` | Screenshots, listed below. |

## Design plan

**Subject, audience, job.** A factor profile of one stock for an investor or an adviser's
client who does not read statistics. The first screen gives the verdict in words; the evidence is
one scroll or one switch away.

**Palette** (owner palette of 2026-11-18, tokens in `report-v3.css`):

| Token | Light | Dark | Role |
|---|---|---|---|
| `--rail` | `#141A33` | `#080C1A` | navy sidebar |
| `--rail-cyan` | `#3CC8E8` | `#3CC8E8` | current section, switches on, "Factor it"; never text on white |
| `--page` / `--surface` | `#F4F6FA` / `#FFFFFF` | `#0B1022` / `#141A33` | page / panels |
| `--ink` / `--ink-2` / `--ink-3` | `#0E1430` / `#4A5470` / `#5A6482` | `#EEF1FA` / `#A9B3D1` / `#97A2C4` | text |
| `--accent` | `#0B7285` teal | `#3CC8E8` | links, selected segment, focus ring |
| `--hi` / `--hi-50` | `#3A3F9E` / `#EEEFFB` | `#A6ABFF` / `#22285A` | verdict band, estimate dots |
| `--pos` / `--neg` / `--caution` | `#0A7A55` / `#C23345` / `#8A5A00` | `#4CD6A0` / `#FF8A98` / `#F2BC57` | evidence, each with a 50-tint |

**Type.** IBM Plex Sans only (STIX is gone with the formula). Body 16, captions and the smallest
text 14, tables 15 tabular, outcome lines 19, panel titles 24, tile values 32, verdict 38
(32 under 1100 px, 28 on phones). Headings 600, values 600, body 400. Sentence case, no all-caps
labels, no monospace, no eyebrows, no numbered markers.

**Layout.**

```text
+-- navy rail 280 ------+-- canvas, grey page, max 1560, 40 px gutters ----------------+
| factordesk            | SPY  SPDR S&P 500 ETF Trust         [Factor data] [2 warn]   |
| [SPY      ][Factor it]| Listed on NYSE Arca, priced in US dollars                    |
| [3Y|5Y|Full history]  | +-- verdict band (indigo tint, radius 12) ----------------+  |
| From [..]  To [..]    | | One plain headline sentence, 38 px                       |  |
| Analysed ... 559 days | | [Beyond its risks] [How much it explains] [Specific risk]|  |
| Factor data ... old   | +----------------------------------------------------------+  |
| Check for newer data  | caution band: two lines + Details                            |
| Show statistics  (o-) | How it performed: 4 values in one ruled panel                |
| Dark theme       (o-) | What drives it: [Market, wide] [World beta tile]             |
| Sections (icons)      |                 [Size] [Value] [Profitability] [Investment]  |
|  > Summary            | Panels (white, radius 12): outcome sentence, then            |
|    ...                |   1440+: chart-table left, reading right (two-up)            |
| [Download report]     |   wide tables (world, Kalman, shrunk, rolling): two-up 1760+ |
+-----------------------+---------------------------------------------------------------+
```

Under 1100 px the tiles stack and the factor cards go two by two; under 900 px the rail becomes a
navy top bar with a menu button and a drawer; under 720 px bar tables become stacked rows.

**Principles.**

1. Outcome first: every panel opens with one plain sentence that states the result.
2. One memorable element, the verdict band; everything else is white panels and hairlines.
3. Statistics on demand: "Show statistics" adds t, p, intervals, VIF and the extra columns; with
   it off no table shows more than 6 columns.
4. Colour is never the only signal: words ("Clear evidence", "Could be noise"), signs and
   position carry the meaning too.
5. Motion only answers an action (switch thumb, drawer, disclosure chevron); none with reduced
   motion.

**Review against the generic defaults, and what changed.**

- The first draft put the five factor cards in one row of identical tiles. Changed: the market,
  which dominates almost every stock, gets a wide lead card beside the world-beta tile, and the four
  style factors sit below. That keeps every row at four tiles or fewer and makes the hierarchy
  visible.
- The default verdict would be a big alpha number with a gradient. Changed: the headline is a
  sentence; numbers are subordinate, in tiles, each with its own instrument (an interval line
  against zero, an explained-share meter, a specific-risk meter) instead of three identical stat
  tiles.
- The card-kit default (one radius, soft shadow everywhere) was replaced by a radius rule
  (12 panels and the band, 8 nested tiles, 6 tables and controls, 999 pills and switches), no
  drop shadows on content, tables with a strong 2 px header rule instead of boxed cells.
- The first build (before the owner palette) used an unboxed light sidebar and unboxed sections;
  the owner's references asked for a navy icon rail and white panels on a grey page, so both
  changed.
- Kept out: gradient washes, tracked capitals, middle-dot meta strings, monospace labels, arrows
  appended to links.
- ui-taste asks for a generated target image first. No image generator is available here, so
  these screenshots are the target.

## Rebuild

```sh
python docs/design/prototype/build_prototype_v3.py          # report-v3.html
python docs/design/prototype/build_prototype_v3.py --empty  # report-v3-empty.html
python docs/design/prototype/contrast_v3.py                 # contrast table, exit 1 on a failure
```

`--on dark,stats,menu,win126 --out PATH` pre-checks inputs; `shoot_v3.py` uses it for the
dark, statistics and drawer shots.

## Screenshots

```sh
python docs/design/prototype/shoot_v3.py           # every shot
python docs/design/prototype/shoot_v3.py measure   # scrollWidth, clientWidth, scrollHeight
```

Headless Chrome CLI only (`--screenshot`, `--dump-dom`). On Windows the headless window is at least
500 px wide, so 390 px shots render the page in a 390 px iframe and crop the PNG with a small
stdlib PNG decoder in `shoot_v3.py`. Set `CHROME` if Chrome is not at the default path.

Shots: `shot_v3_1920_light`, `shot_v3_1440_light`, `shot_v3_1440_dark`, `shot_v3_1440_stats_on`,
`shot_v3_1024_light`, `shot_v3_390_light`, `shot_v3_390_drawer`, `shot_v3_1440_full_light`,
`shot_v3_1440_full_dark`, `shot_v3_390_full_light`, `shot_v3_1440_empty`, and tall crops:
`shot_v3_crop_drivers`, `shot_v3_crop_exposures_stats_off`, `shot_v3_crop_exposures_stats_on`,
`shot_v3_crop_performance`, `shot_v3_crop_risk_rolling`, `shot_v3_crop_deeper`,
`shot_v3_crop_audit_stats_on`, `shot_v3_390_crop_tables`.

## Checks

**Contrast** (`contrast_v3.py`, WCAG 2 ratio; text needs 4.5, UI marks 3.0). All pairs pass.

| Pair | Light | Dark | Use |
|---|---|---|---|
| ink on page / surface | 16.71 / 18.08 | 16.73 / 15.18 | text |
| ink on verdict tint | 15.82 | 12.24 | verdict headline |
| indigo on verdict tint | 7.71 | 6.51 | |
| ink-2 on page / surface / tint | 6.95 / 7.52 / 6.58 | 9.05 / 8.21 / 6.62 | secondary text |
| ink-3 on surface / soft | 5.87 / 5.42 | 6.76 / 6.20 | ticks, footnotes |
| teal on surface / page / teal tint | 5.59 / 5.16 / 5.06 | 8.67 / 9.55 / 6.16 | links |
| ink on teal tint | 16.39 | 10.78 | world tile, callouts |
| on-accent on teal | 5.59 | 9.55 | selected segment |
| positive on surface / tint | 5.35 / 4.80 | 9.33 / 7.93 | |
| negative on surface / tint | 5.45 / 4.77 | 7.62 / 6.89 | |
| caution on tint, ink on caution tint | 5.47, 16.69 | 8.34, 12.82 | notice band |
| slate on slate tint | 6.59 | 6.60 | neutral pill |
| rail text / secondary / cyan on navy | 17.14 / 8.21 / 8.67 | 19.48 / 9.33 / 9.85 | rail |
| cyan / white on rail highlight | 7.38 / 14.59 | 8.47 / 16.75 | current section |
| navy on cyan | 8.67 | 9.85 | "Factor it", selected range |
| navy on white field | 17.14 | 17.14 | rail inputs |
| control line on surface (UI) | 3.77 | 3.78 | borders |
| switch track off on rail (UI) | 3.78 | 4.30 | |
| zero line on surface (UI) | 3.77 | 3.78 | |

**Horizontal scroll** (`shoot_v3.py measure`: a script in the page writes
`scrollWidth x clientWidth x scrollHeight` into a meta tag, read back with `--dump-dom`; at 390 px
the page posts it from the iframe): 390 px 390/390, 1024 px 1008/1008, 1440 px 1424/1424, with
statistics off, on, and the drawer open. No horizontal scroll.

**Smallest font size** in `report-v3.css`: 14 px (`--fs-cap`); no em, rem or percentage font
sizes.

**Vercel web interface guidelines** (fetched from `vercel-labs/web-interface-guidelines`). Fixed:
skip link, heading order in the verdict band (tiles are h3), field names and an example
placeholder, no colour transition (only transform), `touch-action` and a deliberate tap
highlight, safe-area padding and a scroll offset under the sticky top bar, `theme-color`,
`translate="no"` on the brand, ticker and fund name, hover on every control, a working
Download link. Remaining, by design or for the React port:

- `report-v3.html:742`, `:729`: switch and segment state is not in the URL (CSS-only prototype; the port keeps `stats`, `theme` and the range in the URL).
- `report-v3.html:722`: the search form does not submit and has no inline error (mock).
- `report-v3.html:739`: "Check for newer data" has no action (mock).
- `report-v3.html:734`, `build_prototype.py:70`: dates are formatted by hand ("8 Aug 2024"), not with `Intl.DateTimeFormat`; the port should use Intl.
- `report-v3.html:809` and the other bar tables: each table is a focusable scroll region (`tabindex="0"`), which adds tab stops; kept so the wide statistics view can be scrolled from the keyboard.
- `report-v3.css:251`, `:255`: the current section is static plus a `:target` follow; scroll-spy belongs to the port.
- `report-v3.html:766` and every heading and button: sentence case is kept on purpose (project rule), not the guideline's Title Case.
- `report-v3.css:229`: native date inputs keep the browser's own picker; the rail sets white fields with navy text.

## Notes for the port

- Demo values, keyed by ticker in the generator: company name and listing (`SECURITY`),
  historical performance (`PERFORMANCE`), world beta against the ACWI fund (`WORLD`). The residual,
  Kalman and shrunk panels use demo values too, because the mock fixture has none; each panel says
  so in a caution-coloured line.
- The performance chart reuses the mock price shape, scaled to the keyed worst fall, so the dates
  in the tile and the chart agree.
- Evidence colours follow the brief: a negative tilt (for example toward large companies) shows in
  the negative colour. Words and the sign carry the meaning; flag at review if this reads as "bad".
- The IBM Plex Latin subset has no Greek; the Kalman column is labelled "Drift", not lambda.
