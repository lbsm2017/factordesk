import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { Panel } from "./Panel";

export const PANEL_FAILED = "This section could not be shown.";
export const PANEL_FAILED_ACTION = "The rest of the report is not affected. Reload the page to try again.";

export interface PanelBoundaryProps {
  /** Id, title and question of the frame that replaces a panel that failed. */
  id: string;
  title: string;
  question: string;
  children?: ReactNode;
}

interface State {
  failed: boolean;
}

/**
 * Keeps a failure inside one panel (a chunk that does not load, an error while rendering) from
 * unmounting the whole report. The fallback is the common `Panel` frame with its empty state.
 */
export class PanelBoundary extends Component<PanelBoundaryProps, State> {
  override state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`Panel "${this.props.id}" failed to render`, error, info.componentStack);
  }

  override render() {
    if (!this.state.failed) return this.props.children;
    const { id, title, question } = this.props;
    return (
      <Panel id={id} title={title} question={question} empty={{ reason: PANEL_FAILED, action: PANEL_FAILED_ACTION }} />
    );
  }
}
