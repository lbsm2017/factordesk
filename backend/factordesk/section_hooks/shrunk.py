"""Pipeline hook of the ShrunkBetas section (docs/specs/shrunk-betas.md; contract SC2.4).

``build_shrunk_betas`` returns one section per scope, ``full_sample`` then ``latest_window``
(SD7), built from the finished regressions of the report. It reads the context and the portfolio
frames of ``ctx.inputs`` and nothing else: it never changes a core section, never reads another
feature's section, and never raises for data reasons (a failure becomes a section with a status
and a reason, CODING_STANDARDS section 8). OLS betas, tags and every other number stay as they
are (TSB18).

When the context holds no portfolio inputs (``ctx.inputs.shrinkage_portfolios is None``: factors
were injected, or the loader was told to stay offline) the feature did not run and the hook returns
``None``. An empty or incomplete mapping means the files were wanted but are missing: the sections
are then ``failed`` with ``prior_unavailable`` and the rest of the report is unaffected.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from factordesk.analytics.regression import OLSHACFit
from factordesk.analytics.sample import DegenerateInputError
from factordesk.analytics.shrinkage import (
    DELTA,
    POWER_ALPHA,
    SingularCovarianceError,
    posterior,
    power_statements,
    window_fit,
)
from factordesk.analytics.shrinkage_prior import (
    CROSS_SECTIONS,
    PriorEstimate,
    PriorFailure,
    estimate_prior,
)
from factordesk.config import get_settings
from factordesk.data.portfolios import Fetcher, load_portfolio_frames
from factordesk.report.base import FACTOR_NAMES, SampleInfo, Status
from factordesk.report.sections.shrunk import (
    DatasetStamp,
    FactorName,
    PowerStatement,
    Scope,
    ShrinkagePrior,
    ShrunkBeta,
    ShrunkBetas,
    ShrunkLabel,
)
from factordesk.section_hooks.context import SectionContext

logger = logging.getLogger(__name__)

NEEDED_KEYS: tuple[str, ...] = tuple(key for keys in CROSS_SECTIONS.values() for key in keys)
"""Dataset keys the reference prior reads."""
_FACTORS: tuple[FactorName, ...] = ("Mkt-RF", "SMB", "HML", "RMW", "CMA")


def load_shrinkage_inputs(
    now: datetime,
    *,
    offline: bool,
    data_dir: Path | None = None,
    fetch: Fetcher | None = None,
) -> Mapping[str, pd.DataFrame] | None:
    """The portfolio frames of the prior (SB2.2) by dataset key; ``None`` when not fetched.

    Offline (tests, injected factors): nothing is read or downloaded and the result is ``None``.
    Online: the cached files, downloading what is missing or stale; keys that could not be loaded
    are absent from the mapping (never an exception), so the hook reports ``prior_unavailable``.
    """
    if offline:
        return None
    directory = Path(get_settings().data_dir) if data_dir is None else data_dir
    return load_portfolio_frames(directory, now, fetch)


# ------------------------------------------------------------------------------------ vintage
def vintage_problem(
    portfolios: Mapping[str, pd.DataFrame], factor_frame: pd.DataFrame
) -> str | None:
    """Why the portfolio files and the factor file are not one vintage (SB2.3), or ``None``.

    Compares, where known: the CRSP stamps of the files (``frame.attrs["crsp_stamp"]``), the stamp
    of the factor frame if it carries one, and the last date of every file. The factor loader does
    not record a stamp today, so the last dates are the check that is always available: files of
    one release end on the same date.
    """
    stamps = {
        key: str(portfolios[key].attrs["crsp_stamp"])
        for key in NEEDED_KEYS
        if portfolios[key].attrs.get("crsp_stamp")
    }
    factor_stamp = factor_frame.attrs.get("crsp_stamp")
    if factor_stamp:
        stamps["factors"] = str(factor_stamp)
    if len(set(stamps.values())) > 1:
        listing = ", ".join(f"{k} {v}" for k, v in sorted(stamps.items()))
        return f"the portfolio and factor files come from different CRSP releases ({listing})"
    factor_last = pd.Timestamp(str(factor_frame.index[-1])).date()
    for key in NEEDED_KEYS:
        last = pd.Timestamp(str(portfolios[key].index[-1])).date()
        if last != factor_last:
            return (
                f"the portfolio file {key} ends on {last} but the factor file ends on "
                f"{factor_last}, so they are not from one release"
            )
    return None


def _reason(message: str, code: str) -> str:
    return f"{message[:1].upper()}{message[1:]} ({code})."


def _prior_outcome(
    ctx: SectionContext, portfolios: Mapping[str, pd.DataFrame]
) -> PriorEstimate | PriorFailure:
    """The prior for this report (SB2), or why it is not available (SB7.1)."""
    if all(key in portfolios for key in NEEDED_KEYS):
        problem = vintage_problem(portfolios, ctx.factor_frame)
        if problem is not None:
            return PriorFailure("failed", "prior_vintage_mismatch", problem)
    return estimate_prior(ctx.factor_frame, portfolios, ctx.sample.end)


def _text(value: object) -> str | None:
    return None if value is None else str(value)


def _prior_model(prior: PriorEstimate, portfolios: Mapping[str, pd.DataFrame]) -> ShrinkagePrior:
    stamps = [
        DatasetStamp(
            key=key,
            crsp_stamp=_text(portfolios[key].attrs.get("crsp_stamp")),
            sha256=_text(portfolios[key].attrs.get("sha256")),
            last_modified=_text(portfolios[key].attrs.get("last_modified")),
        )
        for key in NEEDED_KEYS
    ]
    return ShrinkagePrior(
        source=prior.source,
        centre=[float(v) for v in prior.centre],
        tau=[float(v) for v in prior.tau],
        tau_by_cross_section={
            name: [float(v) for v in values] for name, values in prior.tau_by_cross_section.items()
        },
        n_portfolios=dict(prior.n_portfolios),
        window_start=prior.window_start,
        window_end=prior.window_end,
        window_rows=prior.window_rows,
        datasets=stamps,
        fallback_reason=None,
    )


# ------------------------------------------------------------------------------------ sections
def _not_ok(
    scope: Scope, window: int | None, hac_lags: int, info: SampleInfo, status: Status, reason: str
) -> ShrunkBetas:
    return ShrunkBetas(
        status=status,
        reason=reason,
        sample=info,
        scope=scope,
        window=window,
        hac_lags=hac_lags,
        prior=None,
        betas=[],
        power=[],
        labels=["L-DESC"],
    )


def _section(
    scope: Scope,
    window: int | None,
    fit: OLSHACFit,
    prior_model: ShrinkagePrior,
    prior: PriorEstimate,
    info: SampleInfo,
) -> ShrunkBetas:
    """The ok section for one regression: posterior and power under the prior (SB3, SB5)."""
    try:
        post = posterior(fit.params[1:], fit.cov[1:, 1:], prior.centre, prior.tau)
    except SingularCovarianceError as exc:
        reason = _reason(str(exc), "singular_covariance")
        return _not_ok(scope, window, fit.lags, info, "failed", reason)
    power = power_statements([float(s) for s in post.se_hac], fit.nobs, FACTOR_NAMES)
    labels: list[ShrunkLabel] = ["L-DESC", "L-SHRINK", "L-SHRINK-PRIOR", "L-CRED", "L-MDE"]
    if any(post.moved_away):
        labels.append("L-CORR-MOVE")
    return ShrunkBetas(
        status="ok",
        reason=None,
        sample=info,
        scope=scope,
        window=window,
        hac_lags=fit.lags,
        prior=prior_model,
        betas=[
            ShrunkBeta(
                factor=name,
                beta_ols=float(post.b_ols[j]),
                se_hac=float(post.se_hac[j]),
                beta_shrunk=float(post.b_post[j]),
                sd_post=float(post.sd_post[j]),
                cred95_low=float(post.cred_low[j]),
                cred95_high=float(post.cred_high[j]),
                pull=float(post.pull[j]),
                moved_away=post.moved_away[j],
            )
            for j, name in enumerate(_FACTORS)
        ],
        power=[
            PowerStatement(
                factor=name,
                mde80=p.mde80,
                alpha_level=POWER_ALPHA,
                delta=DELTA,
                extra_years_to_detect_delta=p.extra_years,
                text=p.text,
            )
            for name, p in zip(_FACTORS, power, strict=True)
        ],
        labels=labels,
    )


def build_shrunk_betas(ctx: SectionContext) -> list[ShrunkBetas] | None:
    """One section per scope (``full_sample``, ``latest_window``), or ``None`` when not computed."""
    portfolios = ctx.inputs.shrinkage_portfolios
    if portfolios is None:
        return None
    outcome = _prior_outcome(ctx, portfolios)
    prior_model = None if isinstance(outcome, PriorFailure) else _prior_model(outcome, portfolios)
    window = ctx.primary_window
    rolling = next((r for r in ctx.core.rolling if r.window == window), None)
    y = ctx.sample.xret.to_numpy(dtype=np.float64)
    factors = ctx.sample.factors.to_numpy(dtype=np.float64)

    def scope_section(
        scope: Scope,
        win: int | None,
        fit_of: Callable[[], OLSHACFit],
        inherited: tuple[Status, str | None],
    ) -> ShrunkBetas:
        info = ctx.sample_info(win)
        status, why = inherited
        if status != "ok":  # SB7.1: the underlying regression is not ok
            return _not_ok(scope, win, 0, info, status, why or "The regression is not ok.")
        try:
            fit = fit_of()
        except DegenerateInputError as exc:
            reason = f"The regression could not be computed: {exc.reason}."
            return _not_ok(scope, win, 0, info, "failed", reason)
        if prior_model is None or isinstance(outcome, PriorFailure):
            assert isinstance(outcome, PriorFailure)
            reason = _reason(outcome.message, outcome.code)
            return _not_ok(scope, win, fit.lags, info, outcome.status, reason)
        return _section(scope, win, fit, prior_model, outcome, info)

    core_reg = ctx.core.regression
    short: tuple[Status, str | None] = (
        "insufficient_data",
        f"{ctx.sample.n} rows in the sample, fewer than the window of {window}",
    )
    return [
        scope_section(
            "full_sample", None, lambda: ctx.regression.fit, (core_reg.status, core_reg.reason)
        ),
        scope_section(
            "latest_window",
            window,
            lambda: window_fit(y, factors, window),
            short if rolling is None else (rolling.status, rolling.reason),
        ),
    ]
