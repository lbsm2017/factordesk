"""Progress of a report run: the steps the backend has really reached.

``step(id)`` is called by the service and the pipeline at the step points. The reporter is a
context variable; the default does nothing, so every plain endpoint, the CLI and the tests run as
before. The stream routes (``routes_stream``) install a ``StepReporter`` for one run. The
variable is copied into the tasks and the worker threads the run starts, so a call from a worker
thread reaches the reporter of the request that started it.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol

from factordesk.report.schema import ProgressStep, ProgressStepId

LABELS: dict[ProgressStepId, str] = {
    "prices": "Downloading prices",
    "fx": "Loading exchange rates",
    "factors": "Loading factor data",
    "models": "Fitting the models",
    "sections": "Building the sections",
}
"""Step ids in run order, with the label of each."""


def plan_of(*, prices: bool = True, fx: bool = False) -> list[ProgressStepId]:
    """The steps of one run, in order: ``prices`` unless the input has none (an upload), ``fx``
    only when exchange rates are loaded."""
    return [step for step in LABELS if (step != "prices" or prices) and (step != "fx" or fx)]


class Reporter(Protocol):
    def step(self, step_id: ProgressStepId) -> None: ...


class _Silent:
    def step(self, step_id: ProgressStepId) -> None:
        return None


_SILENT = _Silent()
_reporter: ContextVar[Reporter] = ContextVar("factordesk_progress_reporter", default=_SILENT)


def step(step_id: ProgressStepId) -> None:
    """Say that the run has reached ``step_id``."""
    _reporter.get().step(step_id)


@contextmanager
def reporting(reporter: Reporter) -> Generator[None]:
    """Send the steps of the code inside the block (and of the tasks and threads it starts) to
    ``reporter``."""
    token = _reporter.set(reporter)
    try:
        yield
    finally:
        _reporter.reset(token)


class StepReporter:
    """Turns calls into ``ProgressStep`` events for the steps of ``plan``, each sent once, in
    order. Reaching a later step sends the earlier ones that were not sent yet, so a step the
    run did not need to announce (cached prices) still shows as done. A step outside the plan
    is ignored. Safe to call from any thread; ``emit`` must be too."""

    def __init__(self, plan: Sequence[ProgressStepId], emit: Callable[[ProgressStep], None]):
        self._plan = list(plan)
        self._emit = emit
        self._next = 0
        self._lock = threading.Lock()

    def step(self, step_id: ProgressStepId) -> None:
        if step_id not in self._plan:
            return
        position = self._plan.index(step_id)
        with self._lock:
            while self._next <= position:
                current = self._plan[self._next]
                self._next += 1
                self._emit(
                    ProgressStep(
                        step=current,
                        label=LABELS[current],
                        index=self._next,
                        total=len(self._plan),
                    )
                )
