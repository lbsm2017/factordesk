import { useMemo, useState } from "react";
import type { RefObject } from "react";
import type { ApiError, LibraryLine } from "../../api/types";
import { addLineWithWeight, libraryById, runnable, withCost } from "../../portfolio/composer";
import { normalise, remainderToCash } from "../../portfolio/tree";
import type { PortfolioTree } from "../../portfolio/tree";
import { LibraryPicker } from "./LibraryPicker";
import { LivePanel, RunDock } from "./LivePanel";
import { TreePanel } from "./TreePanel";

export interface ComposerProps {
  tree: PortfolioTree;
  library: readonly LibraryLine[];
  running: boolean;
  /** The refusal of the last run, shown above the split view. */
  error: ApiError | null;
  onChange: (tree: PortfolioTree) => void;
  onRun: () => void;
  headingRef: RefObject<HTMLHeadingElement | null>;
}

const PICKER_BUTTON = "pf-open-picker";

/**
 * The composer: the allocation tree on the left, the sticky live panel on the right (under the
 * tree on a narrow screen, with the total and Run docked at the bottom), and the library picker.
 */
export function Composer({ tree, library, running, error, onChange, onRun, headingRef }: ComposerProps) {
  const [picking, setPicking] = useState(false);
  const byId = useMemo(() => libraryById(library), [library]);
  const inTree = useMemo(
    () => new Set(tree.root.children.flatMap((ac) => ac.children.map((sub) => sub.library_id))),
    [tree],
  );
  const classes = useMemo(() => new Set(library.map((l) => l.asset_class)).size, [library]);
  const [now] = useState(() => new Date());
  const canRun = runnable(tree).ok;

  const closePicker = () => {
    setPicking(false);
    window.setTimeout(() => document.getElementById(PICKER_BUTTON)?.focus(), 0);
  };

  return (
    <>
      {error !== null ? (
        <div className="pf-error" role="alert" data-testid="portfolio-error">
          <svg className="glyph" viewBox="0 0 16 16" aria-hidden="true">
            <rect x="3" y="3" width="10" height="10" />
          </svg>
          <div>
            <b>
              <span className="vh">Error: </span>
              {error.message}
            </b>
            <span className="do">{error.action}</span>
          </div>
        </div>
      ) : null}
      <div className="composer">
        <TreePanel
          tree={tree}
          library={byId}
          libraryCount={{ classes, lines: library.length }}
          onChange={onChange}
          onOpenPicker={() => setPicking(true)}
          pickerButtonId={PICKER_BUTTON}
          headingRef={headingRef}
        />
        <LivePanel
          tree={tree}
          library={byId}
          now={now}
          running={running}
          onCost={(bps) => onChange(withCost(tree, bps))}
          onNormalise={() => onChange(normalise(tree))}
          onRemainderToCash={() => onChange(remainderToCash(tree, library))}
          onRun={onRun}
        />
      </div>
      {picking ? (
        <LibraryPicker
          library={library}
          inTree={inTree}
          onAdd={(line) => onChange(addLineWithWeight(tree, line, 0))}
          onClose={closePicker}
        />
      ) : null}
      {picking ? null : <RunDock tree={tree} running={running} canRun={canRun} onRun={onRun} />}
    </>
  );
}
