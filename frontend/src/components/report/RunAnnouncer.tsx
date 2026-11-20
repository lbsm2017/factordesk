/**
 * The page's one status line for a run (Sprint 4 mockup 1, keyboard and screen readers): hidden
 * from sight, polite, read whole. The step list is not a live region; this sentence says each
 * step as it starts, and that the report is ready at the end. It stays in the page in every state,
 * so a screen reader has registered it before the text changes.
 */
export function RunAnnouncer({ text }: { text: string }) {
  return (
    <p className="vh" role="status" aria-live="polite" aria-atomic="true" data-testid="run-status">
      {text}
    </p>
  );
}
