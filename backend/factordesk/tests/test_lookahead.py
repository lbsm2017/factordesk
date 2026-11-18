"""Look-ahead tests (test-oracle T102-T104) and static scans for the "Avoid" list (T95, T99)."""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from factordesk.analytics.rolling import ex_ante_betas, rolling_betas
from factordesk.analytics.sample import build_sample
from factordesk.data.audit import audit_prices
from factordesk.data.prices import PriceHistory
from factordesk.pipeline import assemble_report
from factordesk.report.schema import FactorReport
from factordesk.tests.fixtures.dgp import (
    FETCHED_AT,
    MU,
    SIGMA_F,
    dgp_a,
    factor_frame,
    price_history,
    rng_for,
)

NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)
T_STAR = 1800  # rows 1..1800 (1-based) of the returns are identical in every input
PACKAGE = Path(__file__).resolve().parents[1]
FORBIDDEN_ATTRS = {"bfill", "backfill", "interpolate"}
ROW_LEVEL_AUDIT_CODES = {
    "nan_price",
    "non_positive_price",
    "distribution_mismatch",
    "adjustment_on_non_event_day",
    "large_return",
    "suspected_missing_split_adjustment",
    "possible_unrecorded_split",
}


def _perturbed(variant: bool) -> tuple[PriceHistory, pd.DataFrame, PriceHistory, pd.DataFrame]:
    """DGP-A and a copy whose rows after ``t*`` are redrawn, with a dividend and a 2:1 split."""
    rng = rng_for(102)
    d = dgp_a(rng)
    n = len(d.ret)
    ret = d.ret.copy()
    ret[500] = -0.45  # an extreme day before t*: the audit flags it in both copies
    base = price_history(ret, d.dates).frame
    base_div = np.zeros(n + 1)
    base_div[700] = 1.0  # a dividend Adj Close does not reflect: audit finding before t*
    base["dividends"] = base_div
    ret2 = ret.copy()
    f2 = d.f.copy()
    rf2 = d.rf.copy()
    ret2[T_STAR:] = rng.normal(0.0004, 0.015, n - T_STAR)
    f2[T_STAR:] = rng.multivariate_normal(MU, SIGMA_F, size=n - T_STAR)
    rf2[T_STAR:] = rng.uniform(0.00005, 0.0002, n - T_STAR)
    prices = 100.0 * np.concatenate([[1.0], np.cumprod(1.0 + ret2)])
    frame = base.copy()
    adj = prices.copy()
    close = prices.copy()
    div = base_div.copy()
    splits = np.zeros(n + 1)
    div_row, split_row = 2000, 2200  # price rows, both after t*
    div[div_row] = 0.004 * close[div_row - 1]
    splits[split_row] = 2.0
    if variant:
        # What later corporate actions do to history: back-adjustment of every earlier row.
        adj[:div_row] *= 0.97
        close[:split_row] *= 0.5
    frame["adj_close"], frame["close"] = adj, close
    frame["dividends"], frame["splits"] = div, splits
    assert np.array_equal(prices[: T_STAR + 1], base["adj_close"].to_numpy()[: T_STAR + 1])
    original = PriceHistory("SYN", base, FETCHED_AT, "synthetic")
    perturbed = PriceHistory("SYN", frame, FETCHED_AT, "synthetic")
    return original, d.factors, perturbed, factor_frame(f2, rf2, d.dates)


def _stamped(rep: FactorReport, cutoff: date) -> dict[str, list[float | None]]:
    """Every rolling series value stamped on or before ``cutoff``, keyed by window/kind/factor."""
    out: dict[str, list[float | None]] = {}
    for w in rep.rolling:
        k = sum(1 for d in w.dates if d <= cutoff)
        for name in w.betas:
            beta, se = w.betas[name][:k], w.se[name][:k]
            out[f"{w.window}/beta/{name}"] = beta
            out[f"{w.window}/se/{name}"] = se
            out[f"{w.window}/ci_low/{name}"] = [
                None if b is None or s is None or w.ci_z is None else b - w.ci_z * s
                for b, s in zip(beta, se, strict=True)
            ]
    return out


def _assert_same(
    a: dict[str, list[float | None]], b: dict[str, list[float | None]], tol: float
) -> None:
    assert a.keys() == b.keys()
    for key in a:
        x = np.array([np.nan if v is None else v for v in a[key]])
        y = np.array([np.nan if v is None else v for v in b[key]])
        assert x.shape == y.shape, key
        np.testing.assert_allclose(x, y, rtol=0, atol=tol, equal_nan=True, err_msg=key)


def _audit_rows(history: PriceHistory, cutoff: date) -> dict[str, list[date]]:
    report = audit_prices(history.frame)
    rows = {
        f.code: [d for d in f.dates if d <= cutoff]
        for f in report.findings
        if f.code in ROW_LEVEL_AUDIT_CODES
    }
    return {code: dates for code, dates in rows.items() if dates}


@pytest.mark.parametrize("variant", [False, True], ids=["redraw", "redraw+back-adjust"])
def test_t102_perturbation_after_t_star(variant: bool) -> None:
    hist, fac, hist2, fac2 = _perturbed(variant)
    cutoff = pd.Timestamp(fac.index[T_STAR - 1]).date()
    tol = 1e-10 if variant else 1e-12
    rep = assemble_report("SYN", hist, fac, now=NOW, factors_downloaded_at=None)
    rep2 = assemble_report("SYN", hist2, fac2, now=NOW, factors_downloaded_at=None)
    _assert_same(_stamped(rep, cutoff), _stamped(rep2, cutoff), tol)

    s, s2 = build_sample(hist, fac), build_sample(hist2, fac2)
    cut = pd.Timestamp(cutoff)
    for window in (126, 252):
        rb, rb2 = rolling_betas(s, window), rolling_betas(s2, window)
        for a, b in (
            (rb.alpha, rb2.alpha),
            (rb.alpha_se, rb2.alpha_se),
            (rb.r2, rb2.r2),
        ):
            np.testing.assert_allclose(
                a.loc[:cut].to_numpy(), b.loc[:cut].to_numpy(), atol=tol, rtol=0
            )
        np.testing.assert_allclose(
            ex_ante_betas(rb).loc[:cut].to_numpy(),
            ex_ante_betas(rb2).loc[:cut].to_numpy(),
            atol=tol,
            rtol=0,
        )
    np.testing.assert_allclose(
        s.xret.loc[:cut].to_numpy(), s2.xret.loc[:cut].to_numpy(), atol=tol, rtol=0
    )
    rows = _audit_rows(hist, cutoff)
    assert {"large_return", "distribution_mismatch"} <= rows.keys()  # the comparison is not vacuous
    assert rows == _audit_rows(hist2, cutoff)


def test_t103_truncation() -> None:
    d = dgp_a(rng_for(103))
    cutoff = pd.Timestamp(d.factors.index[T_STAR - 1]).date()
    full = assemble_report("SYN", d.history, d.factors, now=NOW, factors_downloaded_at=None)
    trunc_hist = PriceHistory("SYN", d.history.frame.iloc[: T_STAR + 1], FETCHED_AT, "synthetic")
    trunc = assemble_report(
        "SYN", trunc_hist, d.factors.iloc[:T_STAR], now=NOW, factors_downloaded_at=None
    )
    _assert_same(_stamped(full, cutoff), _stamped(trunc, cutoff), 1e-12)
    for stat in (
        trunc.regression,
        trunc.average_beta,
        trunc.return_contribution,
        trunc.risk_contribution,
    ):
        assert stat.sample.end == cutoff
    assert trunc.data.actual_end == cutoff


# ----------------------------------------------------------------------------- static scans
def _modules(*parts: str) -> list[Path]:
    return sorted(p for part in parts for p in (PACKAGE / part).glob("*.py"))


def _calls(tree: ast.AST, attr: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attr
    ]


def _is_negative(node: ast.expr) -> bool:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return True
    return isinstance(node, ast.Constant) and isinstance(node.value, int | float) and node.value < 0


def test_t104_static_scan_for_look_ahead() -> None:
    problems: list[str] = []
    files = _modules("analytics", "data")
    assert any(p.name == "rolling.py" for p in files)
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in _calls(tree, "shift"):
            args = list(call.args) + [k.value for k in call.keywords if k.arg == "periods"]
            if args and _is_negative(args[0]):
                problems.append(f"{path.name}:{call.lineno} negative shift")
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.keyword)
                and node.arg == "center"
                and isinstance(node.value, ast.Constant)
                and node.value.value is True
            ):
                problems.append(f"{path.name}: center=True")
            if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
                problems.append(f"{path.name}: {node.attr}")
        for call in _calls(tree, "fillna"):
            if any(k.arg == "method" for k in call.keywords):
                problems.append(f"{path.name}:{call.lineno} fillna(method=...)")
        for call in _calls(tree, "pct_change"):
            ok = any(
                k.arg == "fill_method"
                and isinstance(k.value, ast.Constant)
                and k.value.value is None
                for k in call.keywords
            )
            if not ok:
                problems.append(f"{path.name}:{call.lineno} pct_change without fill_method=None")
    assert problems == []


def test_t95_t99_static_scan_of_analytics() -> None:
    problems: list[str] = []
    for path in _modules("analytics"):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        if _calls(tree, "fillna"):
            problems.append(f"{path.name}: fillna")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import | ast.ImportFrom):
                names = [a.name for a in node.names] + [getattr(node, "module", "") or ""]
                if any(n.split(".")[0] == "sklearn" for n in names):
                    problems.append(f"{path.name}: sklearn import")
        if "fit_regularized" in text or "hasconst=False" in text:
            problems.append(f"{path.name}: regularised or no-constant fit")
    for name in ("regression.py", "rolling.py"):
        assert "with_intercept(" in (PACKAGE / "analytics" / name).read_text(encoding="utf-8")
    assert problems == []
