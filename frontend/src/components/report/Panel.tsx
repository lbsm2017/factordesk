import type { ReactNode } from "react";
import { EmptyState } from "./EmptyState";
import { HowComputed } from "./HowComputed";

export interface PanelProps {
  /** Element id, also the link target (for example "price", "exposures"). */
  id: string;
  title: string;
  /** The plain-words question under the title. */
  question?: string;
  /** Legend or control on the right of the head. */
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

/** The common panel anatomy of design section D. */
export function Panel({ id, title, question, legend, reading, footnote, how, empty, children }: PanelProps) {
  const headingId = `${id}-title`;
  return (
    <section className="panel" id={id} aria-labelledby={headingId}>
      <div className="panel-head">
        <div>
          <h2 id={headingId}>{title}</h2>
          {question ? <p className="q">{question}</p> : null}
        </div>
        {legend}
      </div>
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
