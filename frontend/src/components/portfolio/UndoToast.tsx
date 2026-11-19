import { useEffect } from "react";
import type { Deleted } from "../../portfolio/store";

export const UNDO_MS = 8000;

export interface UndoToastProps {
  deleted: Deleted | null;
  onUndo: () => void;
  onDismiss: () => void;
}

/**
 * "Deleted Growth · Undo": shown for a few seconds after a portfolio is deleted. The delete has
 * already happened; Undo puts the portfolio back where it was. The region is always in the page,
 * so a screen reader announces the text when it appears.
 */
export function UndoToast({ deleted, onUndo, onDismiss }: UndoToastProps) {
  useEffect(() => {
    if (deleted === null) return;
    const id = window.setTimeout(onDismiss, UNDO_MS);
    return () => window.clearTimeout(id);
  }, [deleted, onDismiss]);

  return (
    <div role="status" aria-live="polite" data-testid="undo-region">
      {deleted !== null ? (
        <div className="toast">
          <span>
            Deleted <b>{deleted.item.tree.name}</b>
          </span>
          <span aria-hidden="true">·</span>
          <button type="button" className="linkbtn" onClick={onUndo}>
            Undo
          </button>
        </div>
      ) : null}
    </div>
  );
}
