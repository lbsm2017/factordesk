import type { ReactNode } from "react";
import { useShowStats } from "../../state/stats";
import { EmptyState } from "./EmptyState";
import { HowComputed } from "./HowComputed";

/** Panels that sit side by side from 1280 px (prototype v4a): Price with Drawdown, Return with Risk sources. */
const PAIR_CLASS: Readonly<Record<string, string>> = { price: "s-7", performance: "s-5", returns: "s-7", risk: "s-5" };
/** Risk sources grows three number columns with statistics on; it then takes the full row and Return sources with it. */
const WIDE_WITH_STATS = new Set(["returns", "risk"]);

export interface PanelProps {
  /** Element id, also the link target (for example "price", "exposures"). */
  id: string;
  title: string;
  /** The plain-words question under the title; shown as the takeaway line only while there is no `outcome`. */
  question?: string;
  /** The outcome sentence under the title (DV4.9); the question moves to its title attribute. */
  outcome?: string | null;
  /** Short text on the right of the title row: a period, a unit or a headline figure (v4a). */
  aside?: ReactNode;
  /** Legend or control on the right of the title row. */
  legend?: ReactNode;
  /** Reading line above the body (76ch). */
  reading?: ReactNode;
  /** One-sentence footnote under the body. */
  footnote?: ReactNode;
  /** Method detail folded into "How this is computed". */
  how?: ReactNode;
  /** Statistic with status != "ok": renders EmptyState instead of the body, and no footnote. */
  empty?: { reason: string; action: string };
  children?: ReactNode;
}

/**
 * The common panel anatomy (prototype v4a): a title row with the title on the left and the
 * optional `aside` text and `legend` on the right, then the outcome sentence (or, without one, the question) as the takeaway line, the
 * reading, the body, and the footnote with "How this is computed".
 */
export function Panel({ id, title, question, outcome, aside, legend, reading, footnote, how, empty, children }: PanelProps) {
  const stats = useShowStats();
  const pair = stats && WIDE_WITH_STATS.has(id) ? undefined : PAIR_CLASS[id];
  const headingId = `${id}-title`;
  return (
    <section className={pair ? `panel ${pair}` : "panel"} id={id} aria-labelledby={headingId}>
      <div className="panel-head">
        <h2 id={headingId}>{title}</h2>
        {aside ? <div className="pm">{aside}</div> : null}
        {legend}
      </div>
      {outcome && !empty ? (
        <p className="q outcome" title={question || undefined}>
          {outcome}
        </p>
      ) : question ? (
        <p className="q">{question}</p>
      ) : null}
      {empty ? (
        <EmptyState reason={empty.reason} action={empty.action} />
      ) : (
        <>
          {reading ? <p className="reading">{reading}</p> : null}
          {children}
          {footnote || how ? (
            <div className="foot">
              {footnote ? <p>{footnote}</p> : null}
              {how ? <HowComputed>{how}</HowComputed> : null}
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
