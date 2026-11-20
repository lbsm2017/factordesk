# Sprint 4 mockups (S4-0): build spec

Three pages, one stylesheet. They are the spec for S4-4 (factor set UI), S4-5 (Factor it experience) and S4-6 ("What EUR changes" panel). Plan: [sprint-4.md](../../sprints/sprint-4.md). Open the HTML files in a browser; the PNGs are at 1440 px and 390 px.

| File | What it shows | Build item |
|---|---|---|
| `1-factor-it-flow.html` | Frames a to g: idle, busy, placeholder page, reveal, re-run, error, cached | S4-5 |
| `2-factor-set-switch.html` | US \| Europe switch, header pills, phone top bar. The two switches work on the page | S4-4 |
| `3-what-eur-changes.html` | The trigger and the side panel, ticker and portfolio view | S4-6 |
| `sprint4.css` | New styles only. Every colour is a token | all |

PNGs: `1-factor-it-flow-1440.png`, `1-factor-it-flow-390.png`, `2-factor-set-switch-1440.png`, `2-factor-set-switch-390.png`, `2-factor-set-switch-390-drawer.png`, `3-what-eur-changes-1440.png`, `3-what-eur-changes-390.png`, `3-what-eur-changes-390-drawer.png`.

Dashed tags and the captions above each frame are mockup notes, not product. Mock figures are not real.

## Rules that apply everywhere

- **Tokens only.** No colour literal outside `tokens.css`. Surfaces `--surface`, `--page`, `--sunk`, `--line`, `--grid`; text `--ink`, `--ink-2`, `--ink-3`; accent `--accent`, `--accent-50`; navy rail `--rail`, `--rail-hover`, `--rail-line`, `--rail-track`, `--rail-cyan`; error `--neg`, `--neg-50`, `--neg-t`; step marks `--mark-ns`.
- **New tokens** (add to `tokens.css`): `--dur-fast: 150ms`, `--dur: 200ms`, `--stagger: 60ms`. Easing is the existing `--ease` (`cubic-bezier(0.2, 0, 0, 1)`).
- **Motion.** 150 to 250 ms, one easing. Only `opacity`, `transform`, and `width` of a progress bar change. Nothing changes the layout. No spinner anywhere. One slow pulse exists (the running step dot and the re-run chip dot: opacity 0.35 to 1, 1200 ms, alternate).
- **Reduced motion.** Under `prefers-reduced-motion: reduce` there is no animation and no transition: no fade, no rise, no pulse, no bar growth (the bar jumps), no drawer or panel slide. Every state is still shown, by text and shape. The step pulse becomes a solid dot.
- **Never colour alone.** Each step shows a word (Done, Working, Waiting, Failed, Not run) and a different mark shape.
- **Type and shape** stay as in `tokens.css`: nothing under 14 px, panels 8 px, controls 6 px, one 1 px border, no shadow.
- **Text.** Plain English, short sentences, no formulas, no jargon.

## Page 1: the Factor it flow

### Order of events

| Time | What the user sees |
|---|---|
| 0 ms, click | Button turns busy (frame b). Press is ignored while busy. Start call goes out |
| about 50 ms | Start call answers. **Cached** (`cached: true`): go to frame g. **Not cached**: show the step list and the placeholder page (frames b and c) |
| each step end | The step turns Done, the next one Working, the bars grow (200 ms) |
| last step done | Reveal (frame d), at most 700 ms |
| error | Frame f |

If the progress channel fails or is not available, fall back to the plain report request and show the placeholder page with the card heading and no step list and no bar. The page must still end in the report or in an error.

### a. Idle

The sidebar as it ships, plus the new Factor set row (page 2). Button text **Factor it**. Landing text in the canvas is unchanged.

### b. Busy button and step list

**Button.** Same size and place. It gets `aria-disabled="true"` (not `disabled`, so focus stays), text **Factoring…**, fill `--rail-hover`, border `--rail-track`, text `--rail-text`, `cursor: progress`. Hover does not change it. A 3 px line along the bottom edge (`.btn-prog`, track `--rail-line`, fill `--rail-cyan`) has width `max(4%, done / total)` and grows in `--dur` with `--ease`. On finish or error the button returns to **Factor it** at once.

**Page.** The report region has `aria-busy="true"`. From top: the header (frame c), then the **run card** in the exact place of the Summary panel, with the same 380 px minimum height, then the placeholder panels.

**Run card.** A normal `.panel`.
- Heading (h2, `tabindex="-1"`): `Building the report for {TICKER}`. Right side (`.pm`): `Step {n} of {total}` where n is done + 1.
- Line under the heading: `This takes a few seconds. The report opens here.`
- Thin bar: 4 px, track `--grid`, fill `--accent`, radius 2 px, width `max(4%, done / total)`, width transition `--dur`.
- List `ol.steps`, rows 48 px high, a 1 px `--grid` line between rows. Columns: mark 20 px, name, state word at the right.

**Steps, exact text, in this order.** Show only the steps the run really has.

1. `Downloading prices`
2. `Loading exchange rates` (EUR only; in USD the step is left out and the total is 4)
3. `Loading factor data`
4. `Fitting the models`
5. `Building the sections`

**Step states.**

| State | Mark | Name | Word |
|---|---|---|---|
| Waiting | empty ring, 2 px `--mark-ns` | `--ink-3` | `Waiting` |
| Working | ring `--accent`, inner dot `--accent` pulsing | `--ink`, 600 | `Working` in `--accent`, 600 |
| Done | filled `--accent` disc, white check | `--ink-2` | `Done` |
| Failed | filled `--neg` disc, white cross | `--ink`, 600 | `Failed` in `--neg`, 600 |
| Not run (after a failure) | as Waiting | `--ink-3` | `Not run` |

State changes fade colour in `--dur-fast`. Only steps the backend has really finished show Done. Never time a step by a clock.

### c. Placeholder page

- The real header: the ticker is real text, 26 px, 700. The name, badge, listing line and the four analysis facts are grey bars (`--border`, radius 2 px). Fact labels stay real text. Use the grey text `0 Aug 0000` so the facts keep their final width.
- One placeholder per panel, with its **real title** in `h2`, at a fixed final height, in the order of `panelRegistry.ts`. Pairs (Price with Drawdown, Return sources with Risk sources, Alpha across models with World beta) pair from 1280 px exactly as the real panels do, so the page does not re-flow at reveal.
- Body: a `--sunk` block with 3 to 7 bars in `--line` and, for chart panels, a flat block in `--grid`. Static, no shimmer.
- **No element id and no landmark** on placeholders (`aria-hidden="true"`). The sidebar section list reads ids from the page, so it stays empty until the real panels exist.
- Heights (px): Summary 380 (the run card), Price 420, Drawdown 420, Tail risk 360, Factor exposures 520, Alpha across models 300, World beta 300, Macro sensitivities 420, Energy & carbon 420, Return sources 560, Risk sources 560, Exposure over time 600, Beyond the factors 280, Tracked day by day 480, Adjusted for noise 480, Timing-adjusted betas (lead-lag) 320, Fragility 320, Data and audit 560, Regression detail 900. Holdings (portfolio only) 520.
- Which panels: a fixed list per mode, kept in one file next to the registry. Ticker mode is the list in the mockup. Portfolio mode adds Holdings after Price. Track record mode: Summary, Price ("Growth of 100"), Factor exposures, Return sources, Risk sources, Exposure over time, Data and audit, Regression detail. The Colophon has no placeholder.
- A panel whose report field turns out empty collapses during the reveal (height and opacity to 0 in `--dur-fast`). It only moves placeholders that are still below the reveal point.
- This replaces `frontend/src/components/report/LoadingFrame.tsx` and its old panel list. `frame.css` heights are replaced by the table above.

### d. Reveal

When the report arrives, panels replace their placeholders from top to bottom.

| Time after the data arrives | What happens |
|---|---|
| 0 ms | Run card fades out (opacity, 150 ms). Header facts and Summary fade in (200 ms, rise 6 px) |
| 60 ms, 120 ms, … | Next panel in page order, 60 ms apart (`--stagger`). Each: opacity 0 to 1 and `translateY(6px)` to 0, 200 ms, `--ease` |
| panel 8 | Last animated panel. The reveal ends about 620 ms after the data arrives |
| 480 ms | Every panel after the eighth swaps with no animation. It is below the fold |
| 0 ms | Sidebar section list items appear (opacity, 150 ms) |

**No layout jump.** A panel never moves after it appears: all panels under it are still placeholders when it appears. Moves happen only below the reveal point. Animate `transform` and `opacity` only. Keep `overflow-anchor: auto` so a user who scrolled during the wait keeps their place. Focus is not moved. When the reveal ends, set `aria-busy="false"`.

Reduced motion: every panel appears at once, no rise, no fade.

### e. Re-run (a report is already on screen)

- The old report stays in place at `opacity: 0.6` (transition `--dur`), with `inert` and `aria-busy="true"`. It is not clickable and not tabbable.
- No run card, no placeholder page. Nothing in the page moves.
- A **thin bar** sticks to the top of the canvas: 3 px, track `--grid`, fill `--accent`, `position: sticky; top: 0; z-index: 6`. On phones `top: 56px`, under the top bar. Width follows the steps as in frame b.
- A **chip** sticks under the bar, at the right (phones: full width): `--surface` fill, 1 px `--line`, 36 px high. Content: a 8 px pulsing `--accent` dot, `Updating {NEW TICKER}` in 600, then `{current step name}, step {n} of {total}` in `--ink-2`. Example: `Updating QQQ` and `Fitting the models, step 4 of 5`.
- The chip says which request is running because the old report may be for another ticker, set or currency. The old figures stay readable but dimmed.
- When the new report is ready: the dim lifts and the report swaps with the same reveal as frame d, with the first panel at 0 ms. The bar fills to 100 % and fades out (150 ms).
- **Remove** the rule in `frame.css` that blanks `.ticker`, `.abar dd` and the Summary figures under `[aria-busy="true"]`. The re-run keeps the old figures on purpose. The first run uses the placeholder page, which has no old figures.

### f. Error

First run: the error replaces the placeholder page. In this order: the ticker as the page heading (h1), the notice (the existing `.notice` look with the square glyph; role `alert`), the buttons, and the step card.

- Notice: `message` (what happened), then `action` (what to do), as `ErrorFrame.tsx` does today.
- Buttons: **Try again** (accent filled; runs the same request) and **Change ticker** (outline; moves focus to the Ticker field).
- The step card shows the steps that ran as Done, the failed step as Failed, the rest as Not run. Heading: `The report for {TICKER} stopped`. Right side: `Stopped at step {n} of {total}`. No line under the heading.
- Focus moves to the notice when it appears (`tabindex="-1"` on its container).
- The sidebar button returns to **Factor it**.

Re-run error: the old report stays, at full strength (the dim lifts, `inert` is removed). A banner sits above it: `--neg-50` fill, 1 px `--neg-t`, role `alert`, the message, the action, a **Try again** button and a **Dismiss** link. The message ends with `The report below is the previous one, for {OLD TICKER}.` This replaces today's rule that a stale report is never shown under an error. The banner removes any chance of mistaking the old report for the new one.

**Exact error texts** (the backend's `message` and `action` fields):

| Case | message | action | Failed step |
|---|---|---|---|
| Unknown ticker | We could not find XYZQ. The price source has no data for this ticker. | Check the spelling, or add the exchange suffix, for example VOD.L. Then press Factor it. | Downloading prices |
| Too little history | XYZQ does not have enough price history for the models. | Choose Full history, or a ticker that has been listed for longer. | Downloading prices |
| Price source did not answer | The price source did not answer in time. Your ticker is fine. | Press Try again. If it still fails, wait a minute and try once more. | Downloading prices |
| No exchange rates (EUR) | The euro exchange rates did not load. | Press Try again, or switch the currency to USD. | Loading exchange rates |
| No factor data | The factor data is not available. | Press Check for newer factor data in the sidebar, then press Try again. | Loading factor data |
| Anything else | Something went wrong while building the report. | Press Try again. If it fails twice, restart the server and read its log. | the step that stopped |

### g. Cached report

The start call answers `cached: true`. The page fetches the report and draws it at once: no run card, no placeholder page, no fade (the swap is instant, as today). The button is busy only for the length of the fetch, normally under 300 ms. Section list items appear with the panels. Same for the re-run case: the old report is replaced with no dim.

### Keyboard and screen readers (page 1)

- The step list is not a live region. A separate visually hidden element (`class="vh"`, `role="status"`, `aria-live="polite"`, `aria-atomic="true"`) says one sentence per change, when a step **starts**: `Step 3 of 5: Loading factor data.` It says `The report for SPY is ready.` at the end. On error the notice has `role="alert"` and the status element stays quiet. In a re-run the same status element is used (the chip is `aria-hidden="true"`).
- `aria-busy="true"` on the report region (first run) or on the old report (re-run), `false` at the end. The button uses `aria-disabled="true"`, not `disabled`, so it keeps focus. Enter and Space do nothing while it is busy.
- The ticker field stays editable while busy. A new submit is ignored until the run ends (v1: no cancel).
- Focus is not moved on start. On phones the drawer closes as today. On error, focus moves to the notice. After a successful run focus stays where it was.
- The placeholder page is `aria-hidden`. The run card is the only reachable content. Its heading is `tabindex="-1"`.
- Colour is never the only signal (see the rules above).

## Page 2: the factor set switch

- **Place.** In the first sidebar group, directly under the currency row. Label `Factor set`, segmented control `US | Europe`, same style as `USD | EUR` (class `seg-range`, native radio buttons in a `role="radiogroup"` named by the label). Add `.fs-row` and `.fs-seg` as in `sprint4.css`: `margin-top: 8px` between rows; the Europe option is at least 64 px wide. The row does not fit beside the currency row in the 288 px rail, so the two rows stack.
- **Default** is US, in both currencies. Europe works in USD and in EUR.
- **URL.** `fs=europe`. The US set omits the parameter, as the currency omits `ccy=USD`.
- **Note** under the row, only for Europe: `Factors: Developed Europe, five factors plus momentum. Macro, energy and world beta keep their US inputs.` (`Developed Europe` in bold, `--rail-text`.) No note for US.
- **Report header.** A pill after the badge and the currency pill. US: `US factors`, quiet (transparent fill, 1 px `--control-line`, `--ink-2`). Europe: `Europe factors`, accent (`--accent-50` fill, 1 px `--accent`, `--accent` text), the same as `Figures in EUR`. The pill shows for both sets, so the header always names the set.
- **Analysis bar.** A new item `Factor set` with `US` or `Developed Europe`, after `Factor data`. It also shows in USD.
- **Summary.** With the Europe set, one more note under the key figures, with the info icon: `Factors are the Fama-French Developed Europe set: five factors plus momentum, from 1990.`
- **Phone.** The drawer holds both rows. The top bar shows the currency chip as today and, only for Europe, a second chip `Europe` (24 px, 1 px `--rail-cyan`, `--rail-cyan` text). The US set adds no chip.
- **Keyboard.** As the currency switch: Tab enters the group, the arrow keys move and select, Tab leaves. Changing the set refetches the report, using the same flow as page 1. The status line announces `Factor set: Europe. Updating the report.`
- **Phone sizes.** Inner options are 44 px high under 900 px, as the other segmented controls.

## Page 3: "What EUR changes" side panel

- **Trigger.** A text button with the info icon, `What EUR changes`, in the page header after the pills. Only while the currency is EUR. Style: `--accent`, 600, underlined (1 px, offset 3 px), 32 px high, 44 px high touch area on phones.
- **Panel.** A right-hand panel, 360 px wide (phones: 92 % of the width, at most 360 px), full height, `--surface`, 1 px `--line` on its left edge, over a `--scrim` overlay. It slides in with `transform` (200 ms, `--ease`). Reduced motion: no slide.
- **Roles.** `role="dialog"`, `aria-modal="true"`, named by its heading. On open, focus goes to the Close button. Tab stays inside. Escape, the Close button (44 px) and a click on the overlay close it. On close, focus returns to the trigger.
- **Texts (about 60 words).** Heading `What EUR changes`. Lines, each with a check icon:
  1. `Prices are converted to euros every day, at the ECB reference rate.`
  2. `Cash earns the euro overnight rate (€STR), not the US rate.`
  3. Portfolio view: `US dollar bond funds (IEF, LQD, HYG, EMB, TIP) are hedged to the euro. Shares, gold and European or global bond funds are not.` Ticker and track record view: `Nothing is hedged: a US ticker still moves with the dollar.`
  4. Footer line: portfolio `The hedge is an estimate from the rate gap, not a fund's own hedge.` Ticker: `A portfolio view hedges its US dollar bond lines.`
  Bold: `every day`, `euro overnight rate`, `hedged`.
- Source: [decision-reference-currency](../../../wiki/decision-reference-currency.md) (conversion, €STR, hedge table, "synthetic estimate from the rate gap").

## Choices made (simplest option, change if you disagree)

1. **Step card in the Summary slot**, not a floating card, so removing it never moves the page.
2. **No cancel button** in v1. A run takes a few seconds.
3. **Re-run error keeps the old report** under a banner, instead of today's error-only page.
4. **US set shows a quiet pill** rather than no pill, so the header always names the set.
5. **Side panel, not an inline panel**, because the canvas has no spare column. It opens from a link next to the EUR pill.
6. **The hedge sentence depends on the mode.** The wiki hedges only library lines of a portfolio. Single tickers and uploads are shown unhedged. Please confirm for uploads.
7. **No elapsed times** on done steps.
8. **Per-mode placeholder lists** are fixed in the frontend; the backend does not send them.

## What the UI gets from the API (S4-5 backend contract, fixed 2026-11-20)

This replaces the earlier draft of this section (run id, per-step status). The backend lane builds the contract below; the UI derives the step states from it.

- Streaming endpoints, server-sent events read with `fetch` (one parser for all three):
  `GET /api/report/{ticker}/stream`, `POST /api/report/portfolio/stream`, `POST /api/report/upload/stream`. They take the same parameters as the plain endpoints.
- `event: step` with data `{"step", "label", "index", "total"}`. When a step arrives, every earlier step is **done** and this one is **running**; later steps are **waiting**.
- `event: report` with data = the `FactorReport`. All steps are done, and the reveal starts.
- `event: error` with data = the `ApiError` plus `status`. The running step becomes **failed**, and the later ones become **not run**. The message and the action come from the `ApiError`.
- A cache hit sends `report` at once, with no steps (frame g).
- If the stream fails before its first event, the UI falls back to the plain endpoint, with no step list.

## Coordinator decisions (2026-11-20)

Choices 1–8 above are accepted as the build spec. Specifically:
- Choice 3: the re-run error banner is accepted, because it names the previous ticker. It is flagged to the owner at the demo, since it reverses the old rule.
- Choice 6: confirmed. Single tickers and uploads are converted unhedged. Only the library bond lines of a portfolio are hedged (Sprint 3 hedge table).
