/**
 * The placeholder page of a first run (Sprint 4 mockup 1, frame c): one grey panel per panel of the
 * real report, with its real title, at its final height, in the order of `panelRegistry.ts`. The lists
 * are fixed here, one per mode; the backend does not send them. Summary is not listed: the run
 * card takes its place. The Colophon has no placeholder.
 */

export type ReportMode = "ticker" | "track" | "portfolio";

export interface PlaceholderPanel {
  /** The panel's name in `panelRegistry.ts`. */
  name: string;
  title: string;
  /** Final height in px. */
  height: number;
  /** The id the real panel uses (`Panel` pairs by id); the placeholder pairs the same way. */
  pairId?: string;
  /** `chart`: a flat block in the body; `lines`: bars of text. */
  body: "chart" | "lines";
}

const PRICE: PlaceholderPanel = { name: "price", title: "Price", height: 420, pairId: "price", body: "chart" };
const HOLDINGS: PlaceholderPanel = { name: "holdings", title: "Holdings", height: 520, body: "lines" };

const TICKER: readonly PlaceholderPanel[] = [
  PRICE,
  { name: "performance", title: "Drawdown", height: 420, pairId: "performance", body: "chart" },
  { name: "tail_risk", title: "Tail risk", height: 360, body: "lines" },
  { name: "exposures", title: "Factor exposures", height: 520, body: "lines" },
  { name: "alpha_strip", title: "Alpha across models", height: 300, pairId: "alpha-strip", body: "lines" },
  { name: "world_beta", title: "World beta", height: 300, pairId: "world-beta", body: "lines" },
  { name: "macro", title: "Macro sensitivities", height: 420, body: "lines" },
  { name: "energy", title: "Energy & carbon", height: 420, body: "lines" },
  { name: "returns", title: "Return sources", height: 560, pairId: "returns", body: "chart" },
  { name: "risk", title: "Risk sources", height: 560, pairId: "risk", body: "lines" },
  { name: "rolling", title: "Exposure over time", height: 600, body: "chart" },
  { name: "residual_alpha", title: "Beyond the factors", height: 280, body: "lines" },
  { name: "kalman", title: "Tracked day by day", height: 480, body: "chart" },
  { name: "shrunk", title: "Adjusted for noise", height: 480, body: "lines" },
  { name: "lead_lag", title: "Timing-adjusted betas (lead-lag)", height: 320, body: "lines" },
  { name: "fragility", title: "Fragility", height: 320, body: "lines" },
  { name: "data", title: "Data and audit", height: 560, body: "lines" },
  { name: "regression_detail", title: "Regression detail", height: 900, body: "lines" },
];

const TRACK: readonly PlaceholderPanel[] = [
  { ...PRICE, title: "Growth of 100" },
  ...TICKER.filter((p) => ["exposures", "returns", "risk", "rolling", "data", "regression_detail"].includes(p.name)),
];

/** The placeholder panels of a mode, in page order, after the run card. */
export function placeholderPanels(mode: ReportMode): readonly PlaceholderPanel[] {
  if (mode === "track") return TRACK;
  if (mode === "portfolio") return [PRICE, HOLDINGS, ...TICKER.slice(1)];
  return TICKER;
}
