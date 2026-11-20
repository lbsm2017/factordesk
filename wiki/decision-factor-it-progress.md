# Decision: Factor it shows real progress

Date: 2026-11-20
Status: Decided; built on feature branches, not yet on `dev` (PRs #40 and #46 were open on 2026-11-20)

## In one sentence

When the user presses Factor it, the page shows the steps the backend has really finished, using server-sent events, and a failed re-run keeps the old report on screen under a banner that names the previous ticker.

## What we decided

- On 2026-11-20 the owner added one item to Sprint 4: a better look and feel from the click on Factor it until the report is on screen ([sprint record](../docs/sprints/sprint-4.md), S4-5).
- Design decision 5, 2026-11-20: progress is real. The page shows steps the backend has finished, not steps timed by a clock. The plain report endpoints keep working as they are.
- Design decision 6, 2026-11-20: calm, quick motion of about 150 to 250 ms and no spinner. Reduced-motion users get no animation.
- On 2026-11-20 the coordinator accepted choice 3 of the mockup README ([docs/design/sprint-4](../docs/design/sprint-4/README.md)): when a re-run fails, the old report stays under a banner that ends "The report below is the previous one, for {OLD TICKER}." This reverses the earlier rule that a stale report is never shown under an error. The coordinator flagged it to the owner for the demo. It is not yet an owner decision.

## How it works

Claims about code are as described in PRs #40 and #46 on 2026-11-20.

- PR #40 (backend) adds three stream routes with the same inputs as the plain ones: ticker (GET), portfolio (POST) and upload (POST), each ending in `/stream`. They answer with `text/event-stream`.
- The events are `step` (id, label, index, total), `report` (the same report as the plain endpoint) and `error` (the usual error body plus the HTTP status). A comment line is sent every 15 seconds as keep-alive.
- The steps, in order: prices, exchange rates (EUR only), factor data, fitting the models, building the sections. An upload has no price step.
- A cached report sends `report` at once with no steps.
- Errors found inside the run are `error` events. Errors the framework raises before the run (bad query value, invalid body, missing file, file over 1 MB) stay plain HTTP errors. The frontend handles both.
- PR #46 (frontend) reads the stream with `fetch`. It falls back to the plain endpoint only on a 404 or 405, a network failure, or an answer that is not an event stream, and only before the first event.
- The placeholder page has one placeholder per real panel, with its real title and final height, in registry order. Panels reveal about 60 ms apart, so nothing moves after it shows.
- On a re-run the old report stays at 0.6 opacity, inert, with a thin progress bar and a chip naming the new request.
- One polite status line tells screen-reader users "Step n of total" and "The report for X is ready."

## Why

- A silent wait of several seconds on a cold run feels broken. Real steps tell the user what is happening and that it is moving.
- Timed steps would be wrong when a step is slow or cached.
- Keeping the old report during a re-run avoids a blank page and lets the user compare. A banner naming the previous ticker removes the risk of mistaking the old report for the new one, which was the reason for the old rule.

## What it costs us

- A second set of endpoints to keep in step with the plain ones.
- A request that joins a run another request already started gets no step events, only the report.
- In a EUR portfolio the exchange-rate and factor steps arrive one after the other, because the rates are first loaded inside the factor step.
- On a failed re-run the old report stays on screen with a banner. A reader who ignores the banner could take it for the new result. This is the reversed rule.
- Portfolio mode: an error on the first run returns to the composer with its inline error, not to the error page.

## What would change our mind

- The owner rejecting the banner at the demo: the earlier rule (error page only) comes back.
- Proxies or hosts that buffer event streams, which would make the plain-endpoint fallback the normal path.

## Sources

- [Sprint 4 record](../docs/sprints/sprint-4.md): S4-5, design decisions 5 and 6.
- [Sprint 4 mockups and coordinator decisions](../docs/design/sprint-4/README.md).
- PRs #40 (progress streams) and #46 (Factor it experience).
- Related: [Dashboard v2](decision-dashboard-v2.md), [Dashboard server and interface](decision-dashboard-server-and-interface.md)
