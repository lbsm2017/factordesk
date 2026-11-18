export interface EmptyStateProps {
  /** Why there is nothing to show (the statistic's `reason`). */
  reason: string;
  /** One next step. */
  action: string;
}

/** A `--sunk` box for a statistic whose status is not "ok" (design section D). */
export function EmptyState({ reason, action }: EmptyStateProps) {
  return (
    <div className="empty">
      <p className="empty-what">{reason}</p>
      <p className="empty-do">{action}</p>
    </div>
  );
}
