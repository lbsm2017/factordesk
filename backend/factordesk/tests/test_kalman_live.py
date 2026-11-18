"""Kalman-betas live tests on the real SPY series (kalman-betas spec TKB24, KB9.1).

Marker ``live``: the tests run only with ``-m live``. They read the cached price history of SPY
(``<data>/prices/SPY_*.parquet``) and the cached factor file (``<data>/factors/ff5_daily.parquet``)
and never touch the network, so they need those two files. ``<data>`` is ``FACTORDESK_LIVE_DATA``
or the ``data`` folder of the checkout; a test is skipped when a file is missing.

TKB24 as written in the spec also asks for MSTR (the Mkt-RF beta 504 rows after 2020-08-11). No
MSTR history is cached, so that half is not run here. The look-ahead checks of TKB13, TKB14, TKB16
and TKB17 are repeated on the real series: the future rows are replaced by a perturbation of the
real returns and every earlier stamp must be unchanged to 1e-12 (spec TKB13). Observed on the
cached series: at most 1.1e-15, not exactly 0. The last bits of a batched numpy matrix product
depend on the memory layout of its input, so two runs on equal values held in different arrays
can differ by that much; a run on the very same array repeats exactly.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from numpy.typing import NDArray

from factordesk.analytics.kalman import KalmanResult, filter_path, kalman_betas
from factordesk.analytics.sample import FACTOR_CODES, build_sample
from factordesk.data.prices import SOURCE_YFINANCE, PriceHistory
from factordesk.pipeline import assemble_report
from factordesk.report.schema import FactorReport
from factordesk.tests.test_kalman import B, _smoothed  # pyright: ignore[reportPrivateUsage]

pytestmark = pytest.mark.live

TOL = 1e-12

FloatArray = NDArray[np.float64]
REPO = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get("FACTORDESK_LIVE_DATA", REPO / "data"))
NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)


def _load() -> tuple[PriceHistory, pd.DataFrame]:
    found = sorted((DATA / "prices").glob("SPY_*.parquet"))
    factors_path = DATA / "factors" / "ff5_daily.parquet"
    if not found or not factors_path.is_file():
        pytest.skip(f"cached SPY prices and factor file not found under {DATA}")
    frame = pd.read_parquet(found[-1])
    frame.attrs = {}
    factors = pd.read_parquet(factors_path)
    factors.index = pd.DatetimeIndex(factors.index, name="date")
    return PriceHistory("SPY", frame, NOW, SOURCE_YFINANCE, ()), factors


@pytest.fixture(scope="module")
def inputs() -> tuple[PriceHistory, pd.DataFrame]:
    return _load()


@pytest.fixture(scope="module")
def full_report(inputs: tuple[PriceHistory, pd.DataFrame]) -> FactorReport:
    history, factors = inputs
    return assemble_report("SPY", history, factors, now=NOW, factors_downloaded_at=NOW)


@pytest.fixture(scope="module")
def xy(inputs: tuple[PriceHistory, pd.DataFrame]) -> tuple[FloatArray, FloatArray]:
    history, factors = inputs
    sample = build_sample(history, factors, None, None)
    y = sample.xret.to_numpy(dtype=np.float64)
    f = sample.factors.loc[:, list(FACTOR_CODES)].to_numpy(dtype=np.float64)
    return y, f


def test_tkb24_spy_since_2010(inputs: tuple[PriceHistory, pd.DataFrame]) -> None:
    history, factors = inputs
    report = assemble_report(
        "SPY", history, factors, now=NOW, factors_downloaded_at=NOW, start=date(2010, 1, 4)
    )
    section = report.kalman_betas
    assert section is not None and section.status == "ok"
    assert 0.90 <= section.latest["Mkt-RF"].beta <= 1.10
    w_eq = section.vintages[-1].w_eq
    assert w_eq is not None and 60 <= w_eq <= 2000
    json.dumps(section.model_dump(mode="json"), allow_nan=False)


def test_spy_full_history_matches_the_spec_demonstration(full_report: FactorReport) -> None:
    """Spec KB9.1 (same factor file, SHA-256 e5857722...): latest values, sd and vintages."""
    section = full_report.kalman_betas
    assert section is not None and section.status == "ok"
    assert section.warnings == []
    assert len(section.dates) == full_report.data.n_obs == 8474
    assert len(section.vintages) == 32
    expected = {
        "Mkt-RF": (0.988, 0.029),
        "SMB": (-0.104, 0.042),
        "HML": (0.023, 0.041),
        "RMW": (0.006, 0.043),
        "CMA": (0.003, 0.056),
    }
    for name, (beta, sd) in expected.items():
        assert section.latest[name].beta == pytest.approx(beta, abs=0.002), name
        assert section.latest[name].sd == pytest.approx(sd, abs=0.0006), name
    windows = [v.w_eq for v in section.vintages]
    assert all(w is not None for w in windows)
    assert windows[0] == pytest.approx(294, abs=1)
    after_2008 = [v.w_eq for v in section.vintages if v.valid_from >= date(2009, 2, 2)]
    assert all(w is not None and 126 <= w <= 148 for w in after_2008)
    assert all(v.lam_at_bound == "none" for v in section.vintages)
    # The SPY timing noise before 2009 fires the quality gate, so the tail label is present.
    assert full_report.quality_gate.fired is True and "L-KTAIL" in section.labels


def test_spy_latest_beta_lies_between_the_rolling_betas_within_the_band(
    full_report: FactorReport,
) -> None:
    section = full_report.kalman_betas
    assert section is not None
    roll = {r.window: r for r in full_report.rolling}
    for name, latest in section.latest.items():
        assert latest.band_low <= latest.beta <= latest.band_high
        for window in (126, 252):
            value = roll[window].betas[name][-1]
            assert value is not None
            assert abs(value - latest.beta) <= 0.05, (name, window)


def _same(a: KalmanResult, b: KalmanResult, stamp: int) -> None:
    """Every output stamped at a row <= ``stamp`` (1-based) is the same to ``TOL``."""
    for name in ("alpha", "betas", "band_low", "band_high", "ex_ante"):
        x, z = getattr(a, name)[:stamp], getattr(b, name)[:stamp]
        assert np.array_equal(np.isnan(x), np.isnan(z)), name
        assert np.nan_to_num(np.abs(x - z)).max() <= TOL, name
    assert np.array_equal(a.vintage_index[:stamp], b.vintage_index[:stamp])


def _future_perturbed(
    y: FloatArray, f: FloatArray, last_kept: int
) -> tuple[FloatArray, FloatArray]:
    """Rows after ``last_kept`` replaced by a distorted copy of the real rows."""
    y2, f2 = y.copy(), f.copy()
    y2[last_kept:] = -3.0 * y2[last_kept:] + 0.002
    f2[last_kept:] = 2.0 * f2[last_kept:][::-1]
    return y2, f2


def test_spy_filtered_and_predicted_betas_do_not_look_ahead(
    xy: tuple[FloatArray, FloatArray],
) -> None:
    y, f = (a[:3000] for a in xy)
    star = 2000
    y2, f2 = _future_perturbed(y, f, star)
    base, other = kalman_betas(y, f), kalman_betas(y2, f2)
    _same(base, other, star)
    done = [v for v in base.vintages if v.rows <= star]
    assert len(done) == 6
    for v0, v1 in zip(done, other.vintages, strict=False):
        assert abs(v0.lam - v1.lam) <= TOL * max(v0.lam, 1e-300) + 1e-300
        assert abs(v0.resid_var - v1.resid_var) <= TOL * v0.resid_var
    assert np.abs(base.betas[star:] - other.betas[star:]).max() > 1e-3
    cut = kalman_betas(y[:star], f[:star])
    _same(base, cut, star)


def test_spy_ex_ante_beta_ignores_the_day_it_explains(xy: tuple[FloatArray, FloatArray]) -> None:
    y, f = (a[:1600] for a in xy)
    t = 1400  # 1-based stamp, inside a vintage
    y2, f2 = y.copy(), f.copy()
    y2[t - 1] *= 10
    f2[t - 1] *= 10
    base, other = kalman_betas(y, f), kalman_betas(y2, f2)
    assert np.abs(base.ex_ante[t - 1] - other.ex_ante[t - 1]).max() <= TOL
    assert np.abs(base.betas[t - 1] - other.betas[t - 1]).max() > 1e-4


def test_spy_a_smoother_would_fail_the_same_check(xy: tuple[FloatArray, FloatArray]) -> None:
    y, f = (a[:900] for a in xy)
    star = 700
    y2, f2 = _future_perturbed(y, f, star)
    m_inv = np.linalg.inv(np.cov(f[:star], rowvar=False, ddof=1))
    smoothed = _smoothed(y, f, 1e-4, m_inv)[star - 2]
    smoothed2 = _smoothed(y2, f2, 1e-4, m_inv)[star - 2]
    assert np.abs(smoothed - smoothed2).max() > 1e-6
    before = filter_path(y, f, 1e-4, drift_shape=m_inv).states[: star - 1]
    after = filter_path(y2, f2, 1e-4, drift_shape=m_inv).states[: star - 1]
    assert np.abs(before[B - 1 :] - after[B - 1 :]).max() <= TOL
