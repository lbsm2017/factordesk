# Decision: report design, where colour is evidence

Date: 2026-11-18
Status: Decided

## In one sentence

The report is a quiet, single-file page in which colour appears only where it carries data, every chart is also a table, and the fitted equation is the one bold element.

## What we decided

- Colour encodes data only: sign (blue for positive, copper for negative) or factor identity (five distinct hues). There is no brand accent.
- Sign is never carried by colour alone: it also has position left or right of a zero line and an explicit plus or minus on each number. Status messages use shapes and words, not colour.
- Each bar panel is a real table, with numbers in aligned columns beside the bars.
- The fitted equation, typeset as mathematics, is the single bold element.
- The report is one HTML file with fonts embedded, no external scripts, styles or fonts, and works when double-clicked.

## Why

We wanted readers to learn from marks, not decoration. The design replaced the plan's red-and-green sign pair with blue and copper. The design document does not state why; the usual reason is that red and green are hard to tell apart for many colour-blind readers. The blue and copper pair passed a colour-vision simulation with worst-case separation of 25.7 against a floor of 8. We rejected a card-and-big-number dashboard look, a generic accent colour and a dotted-zero font (the first font made numbers look like code). We rejected a system font stack because figure widths would differ by machine and none reliably has a math italic.

## How it works

- Insignificant results are drawn faded with a full-colour outline and the word "No" in a "Significant" column.
- Residual and idiosyncratic shares are hatched, and every mark has its name beside it.
- Fonts: Instrument Sans for text and STIX Two for the equation, embedded as base64 (about 61 KB). Page weight with fonts was 226 KB in the prototype.
- Factor hue sets passed checks on all pairs: worst colour-blind distance 10.0 to 10.2 against a floor of 8.
- Light and dark themes follow the system setting, and print forces light colours.

## What it costs us

- Less visual variety than a typical dashboard; some readers may find it austere.
- Not verified as of 2026-11-18: screen readers, Firefox, Safari, forced-colours mode and real long-history data.
- The embedded fonts need their licence files shipped with the renderer.
- Contradiction: the plan's UI direction says red and green with glyphs, and a dark terminal-style dashboard with other fonts. The report design supersedes it for the report; dashboard styling is a separate, unbuilt question.
- Wording gap: the page says "t" while the data says "z".

## What would change our mind

User testing showing the table-plus-bar layout slows reading, a failed accessibility audit, or a need for interactive charts that the single-file format cannot support.

## Sources

- [docs/design/report-design.md](../docs/design/report-design.md), principles, sections A, B, F, H.
- [SECURITY.md](../SECURITY.md): the report loads no external scripts, styles or fonts.
- [docs/PLAN.md](../docs/PLAN.md), "UI / design direction".

## Related decisions

- [Thin slice on SPY first](decision-thin-slice-on-spy-first.md)
- [Which betas count as reliable](decision-which-betas-count-as-reliable.md)
- [Return and risk attribution](decision-return-and-risk-attribution.md)
