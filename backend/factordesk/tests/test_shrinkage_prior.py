"""Reference prior of the shrunk betas (spec SB11: TSB07-TSB09, TSB16, TSB17, TSB20).

Seeds: ``default_rng(20261118 + 700 + NN)`` for ``TSBNN``. Synthetic portfolios only: the files of
the Ken French library are never committed.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from numpy.typing import NDArray

from factordesk.analytics.regression import hac_lags
from factordesk.analytics.shrinkage_prior import (
    CENTRE,
    MIN_PORTFOLIOS,
    TAU_FLOOR,
    WINDOW_ROWS,
    PriorEstimate,
    PriorFailure,
    combine_tau,
    estimate_prior,
    fit_portfolios,
    raw_tau_squared,
    usable_columns,
    window_dates,
)
from factordesk.tests.fixtures.dgp import MU, SIGMA_F, default_rf, factor_frame, rng_for

FloatArray = NDArray[np.float64]

TAU_TRUE = np.array([0.2, 0.5, 0.3, 0.3, 0.25])
M0 = np.array(CENTRE)
N_ROWS = 3000
XS = {"x": ("p1",), "y": ("p2",)}
"""Two synthetic cross-sections (the real ones are ``CROSS_SECTIONS``)."""


def _seed(nn: int) -> np.random.Generator:
    return rng_for(700 + nn)


class World:
    """Factors, risk-free rate and two synthetic cross-sections of portfolios (``N_ROWS`` days)."""

    def __init__(self, rng: np.random.Generator, n_port: int = 60, resid_sd: float = 0.004) -> None:
        self.dates = pd.bdate_range("2010-01-04", periods=N_ROWS, name="date")
        self.f = rng.multivariate_normal(MU, SIGMA_F, size=N_ROWS)
        self.rf = default_rf(N_ROWS)
        self.factors = factor_frame(self.f, self.rf, self.dates)
        self.portfolios: dict[str, pd.DataFrame] = {}
        for key in ("p1", "p2"):
            beta = M0 + TAU_TRUE * rng.standard_normal((n_port, 5))
            e = rng.normal(0.0, resid_sd, size=(N_ROWS, n_port))
            ret = self.rf[:, None] + self.f @ beta.T + e
            self.portfolios[key] = pd.DataFrame(
                ret, index=self.dates, columns=[f"{key}_{i}" for i in range(n_port)]
            )

    def t_end(self, position: int = N_ROWS - 1) -> date:
        return self.dates[position].date()


def _prior(
    world: World,
    t_end: date | None = None,
    portfolios: dict[str, pd.DataFrame] | None = None,
    factors: pd.DataFrame | None = None,
) -> PriorEstimate:
    out = estimate_prior(
        world.factors if factors is None else factors,
        world.portfolios if portfolios is None else portfolios,
        world.t_end() if t_end is None else t_end,
        cross_sections=XS,
    )
    assert isinstance(out, PriorEstimate), out
    return out


# ------------------------------------------------------------------------------------- TSB07
def test_tsb07_method_of_moments_recovers_the_true_spread() -> None:
    rng = _seed(7)
    n_port = 200
    dates = pd.bdate_range("2010-01-04", periods=WINDOW_ROWS)
    f = rng.multivariate_normal(MU, SIGMA_F, size=WINDOW_ROWS)
    beta = M0 + TAU_TRUE * rng.standard_normal((n_port, 5))
    excess = pd.DataFrame(
        f @ beta.T + rng.normal(0.0, 0.004, size=(WINDOW_ROWS, n_port)), index=dates
    )
    fits = fit_portfolios(excess, f)
    assert fits.betas.shape == (n_port, 5) and fits.beta_var.shape == (n_port, 5)
    raw = raw_tau_squared(fits, M0)
    mean_var = fits.beta_var.mean(axis=0)
    bound = 4.0 * np.sqrt(2.0 / n_port) * (TAU_TRUE**2 + mean_var)
    assert (np.abs(raw - TAU_TRUE**2) <= bound).all(), (raw, TAU_TRUE**2, bound)
    # (b) the algebra, from the per-portfolio fits
    direct = ((fits.betas - M0) ** 2).mean(axis=0) - fits.beta_var.mean(axis=0)
    assert np.abs(raw - direct).max() <= 1e-12
    # the lag rule of the prior regressions is L(2520) = 8 (SB2.2 step 2)
    assert hac_lags(WINDOW_ROWS) == 8


def test_tsb07_hac_variance_matches_a_single_reference_fit() -> None:
    from factordesk.tests.fixtures.reference import hac_fit

    rng = _seed(7)
    dates = pd.bdate_range("2010-01-04", periods=WINDOW_ROWS)
    f = rng.multivariate_normal(MU, SIGMA_F, size=WINDOW_ROWS)
    y = f @ M0 + rng.normal(0.0, 0.004, size=WINDOW_ROWS)
    fits = fit_portfolios(pd.DataFrame({"a": y}, index=dates), f)
    ref = hac_fit(y, f, 8)
    assert np.allclose(fits.betas[0], ref.params[1:], rtol=0, atol=1e-12)
    assert np.allclose(fits.beta_var[0], np.diag(ref.cov)[1:], rtol=1e-10, atol=0)


# ------------------------------------------------------------------------------------- TSB08
def test_tsb08_max_rule_and_floor() -> None:
    a = np.array([0.04, 0.16, 0.09, 0.0004, 0.01])
    b = np.array([0.0036, 0.64, 0.09, -0.001, 0.0001])
    tau, per = combine_tau([a, b])
    assert np.allclose(tau, [0.2, 0.8, 0.3, 0.05, 0.1], rtol=0, atol=1e-15)
    assert np.allclose(per[0], [0.2, 0.4, 0.3, 0.02, 0.1], rtol=0, atol=1e-15)
    assert np.allclose(per[1], [0.06, 0.8, 0.3, 0.0, 0.01], rtol=0, atol=1e-15)
    assert TAU_FLOOR == 0.05
    # negative raw values map to 0 before the maximum: both negative gives the floor
    only_negative, _ = combine_tau([np.full(5, -1.0), np.full(5, -0.5)])
    assert np.array_equal(only_negative, np.full(5, TAU_FLOOR))


# ------------------------------------------------------------------------------------- TSB09
def test_tsb09_missing_values_in_the_window_drop_a_portfolio() -> None:
    world = World(_seed(9), n_port=60)
    t_end = world.t_end()
    dates = window_dates(pd.DatetimeIndex(world.dates), t_end)
    frames = {k: v.copy() for k, v in world.portfolios.items()}
    frames["p1"].iloc[N_ROWS - 100, 0] = np.nan  # inside the window
    frames["p1"].iloc[5, 1] = np.nan  # before the window: kept
    kept, dropped = usable_columns(frames["p1"], dates)
    assert dropped == 1 and kept.shape == (WINDOW_ROWS, 59)
    assert "p1_0" not in kept.columns and "p1_1" in kept.columns
    prior = _prior(world, portfolios=frames)
    assert prior.n_portfolios == {"x": 59, "y": 60}
    assert prior.n_dropped == {"x": 1, "y": 0}


def test_tsb09_dates_missing_from_a_file_count_as_missing() -> None:
    world = World(_seed(9), n_port=45)
    short = world.portfolios["p1"].iloc[N_ROWS - 1000 :]
    out = estimate_prior(
        world.factors, {**world.portfolios, "p1": short}, world.t_end(), cross_sections=XS
    )
    assert isinstance(out, PriorFailure)
    assert out.status == "insufficient_data" and out.code == "prior_cross_section_too_small"


def test_tsb09_fewer_than_forty_usable_portfolios_is_insufficient() -> None:
    world = World(_seed(9), n_port=MIN_PORTFOLIOS)
    assert isinstance(_prior(world), PriorEstimate)  # exactly 40 is enough
    frames = {k: v.copy() for k, v in world.portfolios.items()}
    frames["p2"].iloc[N_ROWS - 1, 7] = np.nan
    out = estimate_prior(world.factors, frames, world.t_end(), cross_sections=XS)
    assert isinstance(out, PriorFailure)
    assert (out.status, out.code) == ("insufficient_data", "prior_cross_section_too_small")
    assert "39 usable portfolios" in out.message and "y" in out.message


def test_tsb09_short_factor_window_is_insufficient() -> None:
    world = World(_seed(9), n_port=45)
    out = estimate_prior(world.factors, world.portfolios, world.t_end(2518), cross_sections=XS)
    assert isinstance(out, PriorFailure) and out.code == "prior_cross_section_too_small"
    ok = estimate_prior(world.factors, world.portfolios, world.t_end(2519), cross_sections=XS)
    assert isinstance(ok, PriorEstimate)


def test_missing_dataset_is_prior_unavailable() -> None:
    world = World(_seed(9), n_port=45)
    out = estimate_prior(
        world.factors, {"p1": world.portfolios["p1"]}, world.t_end(), cross_sections=XS
    )
    assert isinstance(out, PriorFailure)
    assert (out.status, out.code) == ("failed", "prior_unavailable")
    assert "p2" in out.message
    empty = estimate_prior(world.factors, {}, world.t_end(), cross_sections=XS)
    assert isinstance(empty, PriorFailure) and empty.code == "prior_unavailable"


def test_estimate_describes_its_window_and_sources() -> None:
    world = World(_seed(9), n_port=45)
    prior = _prior(world, t_end=world.t_end(2799))
    assert prior.window_rows == WINDOW_ROWS
    assert prior.window_end == world.t_end(2799)
    assert prior.window_start == world.t_end(2799 - WINDOW_ROWS + 1)
    assert prior.source == "reference_ff_portfolios_v1"
    assert np.array_equal(prior.centre, M0)
    assert set(prior.tau_by_cross_section) == {"x", "y"}
    assert (prior.tau >= TAU_FLOOR).all()
    expected = np.maximum(np.max([v for v in prior.tau_by_cross_section.values()], axis=0), 0.05)
    assert np.array_equal(prior.tau, expected)
    # the synthetic truth is recovered to within a loose band
    assert np.abs(prior.tau - np.maximum(TAU_TRUE, 0.05)).max() < 0.1


# ------------------------------------------------------------------------- look-ahead (TSB16/17)
def test_tsb16_rows_after_t_end_cannot_change_the_prior() -> None:
    rng = _seed(16)
    world = World(rng, n_port=45)
    t_pos = 2799
    t_end = world.t_end(t_pos)
    base = _prior(world, t_end)

    frames = {k: v.copy() for k, v in world.portfolios.items()}
    factors = world.factors.copy()
    after = slice(t_pos + 1, N_ROWS)
    for frame in frames.values():
        frame.iloc[after, :] = rng.normal(0.0, 0.05, size=frame.iloc[after, :].shape)
    factors.iloc[after, :5] = rng.normal(0.0, 0.05, size=factors.iloc[after, :5].shape)
    factors.iloc[after, 5] = 0.0001
    perturbed = _prior(world, t_end, frames, factors)
    assert np.abs(perturbed.tau - base.tau).max() <= 1e-12
    assert perturbed.n_portfolios == base.n_portfolios
    for key in base.tau_by_cross_section:
        assert (
            np.abs(perturbed.tau_by_cross_section[key] - base.tau_by_cross_section[key]).max()
            <= 1e-12
        )

    # control: a row inside the window does change tau (the test bites)
    inside = {k: v.copy() for k, v in world.portfolios.items()}
    inside["p1"].iloc[t_pos - 1000, :] += 0.2
    assert np.abs(_prior(world, t_end, inside).tau - base.tau).max() > 1e-4


def test_tsb17_truncated_files_give_the_same_prior() -> None:
    world = World(_seed(17), n_port=45)
    t_pos = 2799
    t_end = world.t_end(t_pos)
    full = _prior(world, t_end)
    cut = pd.Timestamp(t_end)
    truncated = {k: v.loc[v.index <= cut] for k, v in world.portfolios.items()}
    short = _prior(world, t_end, truncated, world.factors.loc[world.factors.index <= cut])
    assert np.array_equal(short.tau, full.tau)
    assert short.n_portfolios == full.n_portfolios
    assert (short.window_start, short.window_end) == (full.window_start, full.window_end)


def test_prior_does_not_mutate_its_inputs() -> None:
    world = World(_seed(17), n_port=45)
    before = {k: v.copy() for k, v in world.portfolios.items()}
    factors_before = world.factors.copy()
    _prior(world)
    for key, frame in before.items():
        pd.testing.assert_frame_equal(world.portfolios[key], frame)
    pd.testing.assert_frame_equal(world.factors, factors_before)


# -------------------------------------------------------------------------------- TSB20 (live)
@pytest.mark.live
def test_tsb20_real_portfolio_files_parse_and_spy_barely_moves(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    from factordesk.analytics.sample import build_sample
    from factordesk.analytics.shrinkage import posterior, window_fit
    from factordesk.data.factors import load_ff5_daily
    from factordesk.data.portfolios import load_portfolio_frames
    from factordesk.data.prices import YFinanceProvider

    now = datetime.now(UTC)
    frames = load_portfolio_frames(tmp_path, now)
    factors = load_ff5_daily(data_dir=tmp_path, now=now)
    last = pd.Timestamp(str(factors.index[-1])).date()
    prior = estimate_prior(factors, frames, last)
    assert isinstance(prior, PriorEstimate), prior
    assert prior.n_portfolios == {"industry49": 49, "size_char75": 75}

    spy = build_sample(YFinanceProvider(now=lambda: now).fetch("SPY"), factors, date(2010, 1, 4))
    fit = window_fit(spy.xret.to_numpy(), spy.factors.to_numpy(), spy.n)
    post = posterior(fit.params[1:], fit.cov[1:, 1:], prior.centre, prior.tau)
    assert float(post.pull.max()) < 0.02

    # A listing 2-3 years before the factor file ends (RDDT, spec SB8.2): the style betas move.
    new = build_sample(YFinanceProvider(now=lambda: now).fetch("RDDT"), factors)
    short = window_fit(new.xret.to_numpy(), new.factors.to_numpy(), new.n)
    post_new = posterior(short.params[1:], short.cov[1:, 1:], prior.centre, prior.tau)
    assert float(post_new.pull[1:].max()) > 0.2
