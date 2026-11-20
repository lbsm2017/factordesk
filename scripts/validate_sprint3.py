"""Sprint 3 real-data validation: measure the currency, energy and holdings features.

Builds reports in-process through the app's own service layer (``ReportService`` over
``default_deps``), on real downloaded data, with no server. It changes no app code and writes no
file except the data caches (default ``data/``, git-ignored) and, with ``--out``, a JSON of the
measured numbers.

Run from the repository root::

    uv run python scripts/validate_sprint3.py [--data-dir data] [--out numbers.json]
        [--baseline PATH_TO_CHECKOUT_OF_688db25]

Checks (see ``docs/sprints/sprint-3.md``, section Verification)
    1. SPY in EUR against SXR8.DE (EUR listing): monthly correlation, annual return gap.
    2. 60/40 (IVV 60, IEF 40) in EUR with IEF hedged against USD: annual returns, and the hedged
       IEF leg minus IEF in USD against the EUR-USD cash gap.
    3. Euro cash index, 2023 compounded return.
    4. Energy panel in USD: XLE, SPY, XLU.
    5. Balanced SAA in USD and EUR: holdings group totals, total return, risk shares.
    6. The USD SPY report against the checkout of the dev commit before the sprint.
    7. SPY tail risk by horizon.

``--dump-spy FILE`` is internal: it writes the SPY USD reports (FF5 and FF6) as JSON and exits;
check 6 runs it in the baseline checkout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

PRESET_BALANCED = [
    ("cash_usd", 2),
    ("fi_na_gov", 10),
    ("fi_na_ig", 10),
    ("fi_tips", 5),
    ("fi_na_hy", 3),
    ("eq_na_large", 33),
    ("eq_eur_large", 8),
    ("eq_japan_pacific", 4),
    ("eq_em", 6),
    ("eq_usa_small", 4),
    ("alt_pe", 4),
    ("alt_real_estate", 6),
    ("com_gold", 5),
]
"""``frontend/src/portfolio/presets.ts``, preset ``saa`` (percent of the portfolio)."""
PRESET_6040 = [("eq_na_large", 60), ("fi_na_gov", 40)]
PRESET_IEF = [("fi_na_gov", 100)]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--out", default=None, help="write the measured numbers as JSON")
    ap.add_argument("--baseline", default=None, help="checkout of the dev commit before the sprint")
    ap.add_argument(
        "--sxr8-start",
        default="2010-11-02",
        help="first day of the SXR8.DE comparison: its Yahoo history is stale before 2010-11-01",
    )
    ap.add_argument("--dump-spy", default=None, help=argparse.SUPPRESS)
    return ap.parse_args()


ARGS = parse_args()
os.environ["DATA_DIR"] = str(Path(ARGS.data_dir).resolve())

import pandas as pd  # noqa: E402
from factordesk.api import portfolio_report as pr  # noqa: E402
from factordesk.api.deps import default_deps  # noqa: E402
from factordesk.api.portfolio_models import PortfolioTree, load_library  # noqa: E402
from factordesk.api.runtime import Runtime  # noqa: E402
from factordesk.api.service import ReportService  # noqa: E402
from factordesk.report.schema import FactorReport  # noqa: E402

CAPTURED: dict[tuple[str, str], Any] = {}
_ORIGINAL_BACKTEST = pr.backtest_portfolio


def _spy_backtest(plan: Any, histories: Any, rf: Any, ctx: Any = None, listings: Any = None) -> Any:
    """Calls the real backtest and keeps its subject (the net daily returns) for the checks."""
    out = _ORIGINAL_BACKTEST(plan, histories, rf, ctx, listings)
    CAPTURED[(plan.name, "USD" if ctx is None else ctx.ref)] = out[0]
    return out


pr.backtest_portfolio = _spy_backtest


def make_service() -> ReportService:
    return ReportService(Runtime(default_deps()))


# ----------------------------------------------------------------------------- helpers
def tree_of(name: str, lines: list[tuple[str, int]], ccy: str) -> PortfolioTree:
    """The tree the composer builds from a preset: asset class, library line, instrument."""
    library = {line.id: line for line in load_library().lines}
    classes: dict[str, list[dict[str, Any]]] = {}
    for i, (line_id, pct) in enumerate(lines):
        line = library[line_id]
        if line.proxy_kind == "risk_free":
            leaf: dict[str, Any] = {
                "id": f"h{i}",
                "kind": "cash",
                "ticker": None,
                "label": "USD cash",
            }
        else:
            leaf = {"id": f"h{i}", "kind": "holding", "ticker": line.proxy, "label": line.proxy}
        leaf["weight"] = pct / 100.0
        classes.setdefault(line.asset_class, []).append(
            {
                "id": f"s{i}",
                "kind": "group",
                "label": line.sub_asset_class,
                "library_id": line_id,
                "children": [leaf],
            }
        )
    body: dict[str, Any] = {
        "version": 1,
        "name": name,
        "cost_bps": 0.0,
        "root": {
            "id": "root",
            "kind": "group",
            "label": "Portfolio",
            "children": [
                {"id": f"ac{k}", "kind": "group", "label": label, "children": subs}
                for k, (label, subs) in enumerate(classes.items())
            ],
        },
    }
    if ccy != "USD":
        body["reference_currency"] = ccy
    return PortfolioTree.model_validate(body)


async def converted_prices(svc: ReportService, ticker: str, ccy: str) -> tuple[pd.Series, str]:
    """Adjusted close of ``ticker`` in ``ccy`` as the report sees it, and its listing currency."""
    from factordesk.analytics.currency import listing_currency
    from factordesk.api.currency_ctx import CurrencyContext

    now = svc._now()  # pyright: ignore[reportPrivateUsage]
    security = await svc._security(ticker, now.date())  # pyright: ignore[reportPrivateUsage]
    listing, scale = listing_currency(ticker, security)
    history = await svc._history(ticker, now.date())  # pyright: ignore[reportPrivateUsage]
    ctx = CurrencyContext(ccy, svc.deps.currency)  # type: ignore[arg-type]
    history = await svc.runtime.run(
        svc._to_reference,  # pyright: ignore[reportPrivateUsage]
        ticker,
        history,
        listing,
        scale,
        ctx,
    )
    adj = history.frame["adj_close"].astype("float64")
    return adj[adj > 0].dropna(), listing


def cagr_of(prices: pd.Series) -> float:
    years = (prices.index[-1] - prices.index[0]).days / 365.25
    return float((prices.iloc[-1] / prices.iloc[0]) ** (1.0 / years) - 1.0)


def energy_rows(report: FactorReport) -> dict[str, Any]:
    section = report.energy
    assert section is not None and section.status == "ok" and section.long_model is not None
    out: dict[str, Any] = {}
    for model in (section.long_model, section.carbon_model):
        if model is None:
            continue
        for row in model.rows:
            out[f"{model.key}:{row.code}"] = {"beta": row.beta, "t": row.t, "p": row.p}
        out[f"{model.key}:n_obs"] = model.n_obs
        out[f"{model.key}:start"] = str(model.start)
    return out


# ----------------------------------------------------------------------------- checks
def compare_series(a: pd.Series, b: pd.Series) -> dict[str, Any]:
    """Monthly and daily correlation, annual return of each and their gap, on common dates."""
    common = a.index.intersection(b.index)
    a, b = a.loc[common], b.loc[common]
    both = pd.DataFrame({"spy": a, "sxr8": b})
    month = both.resample("ME").last().pct_change().dropna()
    daily = both.pct_change().dropna()
    return {
        "window_start": str(common[0].date()),
        "window_end": str(common[-1].date()),
        "n_days": len(common),
        "n_months": len(month),
        "monthly_corr": float(month["spy"].corr(month["sxr8"])),
        "daily_corr": float(daily["spy"].corr(daily["sxr8"])),
        "cagr_spy_eur": cagr_of(a),
        "cagr_sxr8": cagr_of(b),
        "gap": cagr_of(a) - cagr_of(b),
        "tracking_error_monthly_annualised": float(
            (month["spy"] - month["sxr8"]).std(ddof=1) * math.sqrt(12)
        ),
        "worst_month_gap": float((month["spy"] - month["sxr8"]).abs().max()),
    }


def timing_diagnostics(a: pd.Series, b: pd.Series) -> dict[str, Any]:
    """Why monthly figures are not exact: the two prices are not struck at the same moment.

    SXR8 closes on Xetra (17:30 Frankfurt), SPY at the New York close (22:00 Frankfurt), and the
    ECB rate is fixed at 14:10. A US move after 17:30 reaches SXR8 on the next day, so a month-end
    can differ by about one day of market move. Measures: the quarterly and annual correlation
    (the same noise on a bigger return), and the R2 of daily SXR8 on SPY in EUR today and
    yesterday.
    """
    import numpy as np

    common = a.index.intersection(b.index)
    both = pd.DataFrame({"spy": a.loc[common], "sxr8": b.loc[common]})
    out: dict[str, Any] = {}
    for label, rule in (("quarterly_corr", "QE"), ("annual_corr", "YE")):
        r = both.resample(rule).last().pct_change().dropna()
        out[label] = float(r["spy"].corr(r["sxr8"]))
    d = both.pct_change().dropna()
    x = pd.DataFrame({"t": d["spy"], "t_1": d["spy"].shift(1)}).dropna()
    y = d["sxr8"].loc[x.index]
    for label, cols in (
        ("daily_r2_same_day", ["t"]),
        ("daily_r2_same_and_previous_day", ["t", "t_1"]),
    ):
        design = np.column_stack([np.ones(len(x)), x[cols].to_numpy()])
        beta, *_ = np.linalg.lstsq(design, y.to_numpy(), rcond=None)
        resid = y.to_numpy() - design @ beta
        out[label] = float(1.0 - resid.var() / y.var())
    return out


async def check1(svc: ReportService) -> dict[str, Any]:
    spy_eur, spy_ccy = await converted_prices(svc, "SPY", "EUR")
    sxr8, sxr8_ccy = await converted_prices(svc, "SXR8.DE", "EUR")
    stale = int((sxr8.loc[: ARGS.sxr8_start].pct_change() == 0).sum())
    full = compare_series(spy_eur, sxr8)
    cut = compare_series(spy_eur, sxr8.loc[ARGS.sxr8_start :])
    report = await svc.report("SPY", model="ff6", ccy="EUR")
    perf = report.performance
    return {
        "spy_listing": spy_ccy,
        "sxr8_listing": sxr8_ccy,
        "sxr8_zero_return_days_before_start": stale,
        "sxr8_start_used": ARGS.sxr8_start,
        "from_start_used": cut,
        "timing_diagnostics": timing_diagnostics(spy_eur, sxr8.loc[ARGS.sxr8_start :]),
        "from_first_common_date": full,
        "report_spy_eur_cagr_own_window": None
        if perf is None or perf.returns is None
        else perf.returns.cagr,
        "report_spy_eur_own_window": None
        if perf is None or perf.periods is None
        else f"{perf.periods.start} to {perf.periods.end}",
        "pass": cut["monthly_corr"] > 0.99 and abs(cut["gap"]) < 0.005,
    }


async def run_portfolio(
    svc: ReportService, name: str, lines: list[tuple[str, int]], ccy: str
) -> tuple[FactorReport, Any]:
    tree = tree_of(name, lines, ccy)
    report = await svc.portfolio_report(tree, None, None, None, "ff6")
    return report, CAPTURED[(name, ccy)]


def returns_of(r: FactorReport) -> dict[str, float]:
    assert r.performance is not None and r.performance.returns is not None
    assert r.performance.periods is not None
    return {
        "cagr": r.performance.returns.cagr,
        "cumulative": r.performance.returns.cumulative_return,
        "years": r.performance.periods.years,
    }


async def check2(svc: ReportService) -> dict[str, Any]:
    from factordesk.data import rates

    r_eur, s_eur = await run_portfolio(svc, "6040", PRESET_6040, "EUR")
    r_usd, s_usd = await run_portfolio(svc, "6040", PRESET_6040, "USD")
    i_eur, ie = await run_portfolio(svc, "IEF only", PRESET_IEF, "EUR")
    i_usd, iu = await run_portfolio(svc, "IEF only", PRESET_IEF, "USD")

    # Hedged IEF leg minus IEF in USD, against c_eur - RF, on days whose interval is the same
    # in both backtests (same previous date), so that a gap is not compared with a single day.
    assert svc.deps.currency is not None
    rate = svc.deps.currency.eur_rate().rate
    assert rate is not None
    loaded = await svc._factors()  # pyright: ignore[reportPrivateUsage]
    cal_e, cal_u = ie.calendar, iu.calendar
    prev_e = pd.Series(cal_e[:-1], index=cal_e[1:])
    prev_u = pd.Series(cal_u[:-1], index=cal_u[1:])
    both = prev_e.index.intersection(prev_u.index)
    same = both[prev_e.loc[both].to_numpy() == prev_u.loc[both].to_numpy()]
    cash_e = rates.cash_returns(rate, cal_e)
    rf_e = pr._compounded_rf(loaded.frame["RF"], cal_e)  # pyright: ignore[reportPrivateUsage]
    leg_gap = (ie.returns.loc[same] - iu.returns.loc[same]).dropna()
    cash_gap = (cash_e - rf_e).loc[leg_gap.index].dropna()
    idx = leg_gap.index.intersection(cash_gap.index)
    leg_gap, cash_gap = leg_gap.loc[idx], cash_gap.loc[idx]
    mean_leg, mean_cash = float(leg_gap.mean()) * 252, float(cash_gap.mean()) * 252
    # Independent recomputation of the hedged leg from the USD prices: R_usd - rf + c_eur.
    ief_usd_prices, _ = await converted_prices(svc, "IEF", "USD")
    r_usd_on_eur_cal = ief_usd_prices.reindex(cal_e).pct_change().iloc[1:]
    expected = (r_usd_on_eur_cal - rf_e + cash_e).dropna()
    both_idx = expected.index.intersection(ie.returns.dropna().index)
    resid = (ie.returns.loc[both_idx] - expected.loc[both_idx]).abs()
    ief_eur_prices, _ = await converted_prices(svc, "IEF", "EUR")
    unhedged = ief_eur_prices.reindex(cal_e).pct_change().iloc[1:].loc[both_idx]
    resid_unhedged = (ie.returns.loc[both_idx] - unhedged).abs()
    ri, ru = returns_of(i_eur), returns_of(i_usd)
    r6e, r6u = returns_of(r_eur), returns_of(r_usd)
    return {
        "6040_eur": r6e,
        "6040_usd": r6u,
        "6040_cagr_gap_eur_minus_usd": r6e["cagr"] - r6u["cagr"],
        "ief_eur_hedged": ri,
        "ief_usd": ru,
        "ief_cagr_gap_hedged_minus_usd": ri["cagr"] - ru["cagr"],
        "n_days_compared": len(idx),
        "hedge_leg_gap_annualised_mean": mean_leg,
        "cash_gap_annualised_mean": mean_cash,
        "hedge_vs_cash_difference": mean_leg - mean_cash,
        "daily_corr_leg_vs_cash": float(leg_gap.corr(cash_gap)),
        "max_abs_daily_residual_vs_cash_gap": float((leg_gap - cash_gap).abs().max()),
        "engine_vs_formula_n_days": len(both_idx),
        "engine_vs_formula_max_abs_residual": float(resid.max()),
        "engine_vs_formula_mean_abs_residual": float(resid.mean()),
        "engine_vs_unhedged_eur_max_abs_residual": float(resid_unhedged.max()),
        "6040_eur_window": [str(s_eur.calendar[0].date()), str(s_eur.calendar[-1].date())],
        "6040_usd_window": [str(s_usd.calendar[0].date()), str(s_usd.calendar[-1].date())],
        "pass": abs(mean_leg - mean_cash) < 0.0015 and float(resid.max()) < 1e-6,
    }


async def check3(svc: ReportService) -> dict[str, Any]:
    from factordesk.data import rates

    assert svc.deps.currency is not None
    res = svc.deps.currency.eur_rate()
    assert res.rate is not None
    dates = pd.bdate_range("2022-12-30", "2023-12-29")
    cash = rates.cash_returns(res.rate, dates)
    total = float((1.0 + cash).prod() - 1.0)
    return {
        "rate_source": res.credit,
        "rate_first_date": str(res.rate.index[0].date()),
        "rate_last_date": str(res.rate.index[-1].date()),
        "return_2023": total,
        "mean_rate_2023": float(res.rate.loc["2023-01-01":"2023-12-31"].mean()),
        "pass": 0.030 <= total <= 0.036,
    }


async def check4(svc: ReportService) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for ticker in ("XLE", "SPY", "XLU"):
        report = await svc.report(ticker, model="ff6")
        out[ticker] = energy_rows(report)
        assert report.energy is not None
        out[ticker]["frequency"] = report.energy.frequency
    xle = out["XLE"]["long:oil"]
    spy = out["SPY"]
    spy_keys = [k for k in spy if k.endswith((":oil", ":gas", ":co2"))]
    xle_ok = xle["beta"] > 0.1 and xle["t"] > 3.0
    spy_ok = all(abs(spy[k]["beta"]) < 0.05 for k in spy_keys)
    out["xle_ok"], out["spy_ok"] = xle_ok, spy_ok
    out["pass"] = xle_ok and spy_ok
    return out


def holdings_checks(report: FactorReport) -> dict[str, Any]:
    section = report.holdings
    assert section is not None
    rows = section.rows
    kids: dict[str, list[Any]] = {}
    for r in rows:
        if r.parent_id is not None:
            kids.setdefault(r.parent_id, []).append(r)
    worst = 0.0
    n_groups = 0
    for r in rows:
        if r.kind != "group":
            continue
        n_groups += 1
        members = kids.get(r.id, [])
        for field in ("target_weight", "end_weight", "contribution", "risk_share"):
            got, parts = getattr(r, field), [getattr(m, field) for m in members]
            if got is None or any(p is None for p in parts):
                continue
            worst = max(worst, abs(got - sum(parts)))
    top = [r for r in rows if r.parent_id is None]
    perf = (
        report.performance.returns.cumulative_return
        if report.performance and report.performance.returns
        else float("nan")
    )
    contrib_sum = sum(r.contribution for r in top)
    shares = [r.risk_share for r in top]
    share_sum = (
        None if any(s is None for s in shares) else float(sum(s for s in shares if s is not None))
    )
    return {
        "n_rows": len(rows),
        "n_groups": n_groups,
        "worst_group_vs_leaves": worst,
        "holdings_total_return": section.total_return,
        "performance_cumulative_return": perf,
        "total_return_diff": section.total_return - perf,
        "top_level_contribution_sum": contrib_sum,
        "contribution_sum_diff": contrib_sum - section.total_return,
        "risk_share_sum": share_sum,
        "risk_share_reason": section.risk_share_reason,
        "n_days": section.n_days,
        "window": f"{section.window_start} to {section.window_end}",
        "pass": worst < 1e-9
        and abs(section.total_return - perf) < 1e-9
        and share_sum is not None
        and abs(share_sum - 1.0) < 1e-9,
    }


async def check5(svc: ReportService) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for ccy in ("USD", "EUR"):
        report, _ = await run_portfolio(svc, "Balanced SAA", PRESET_BALANCED, ccy)
        out[ccy] = holdings_checks(report)
    out["pass"] = out["USD"]["pass"] and out["EUR"]["pass"]
    return out


def key_figures(report: FactorReport) -> dict[str, Any]:
    reg = report.regression
    assert reg is not None
    return {
        "alpha_annual": reg.alpha_annual,
        "r2": reg.r2,
        "adj_r2": reg.adj_r2,
        "sigma_e_annual": reg.sigma_e_annual,
        "betas": {f.name: f.beta for f in reg.factors},
        "se": {f.name: f.se for f in reg.factors},
    }


def close(a: Any, b: Any, tol: float = 1e-9) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k], tol) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(close(x, y, tol) for x, y in zip(a, b, strict=True))
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= tol * max(1.0, abs(a), abs(b))
    return a == b


async def dump_spy(path: str) -> None:
    svc = make_service()
    out: dict[str, Any] = {}
    for model in ("ff5", "ff6"):
        report = await svc.report("SPY", model=model)  # type: ignore[arg-type]
        out[model] = {"full": json.loads(report.model_dump_json()), "key": key_figures(report)}
    Path(path).write_text(json.dumps(out), encoding="utf-8")


async def check6(svc: ReportService) -> dict[str, Any]:
    if ARGS.baseline is None:
        return {"skipped": "no --baseline checkout given", "pass": None}
    tmp = Path(ARGS.data_dir).resolve() / "spy_baseline.json"
    here = Path(__file__).resolve()
    proc = subprocess.run(
        [
            "uv",
            "run",
            "python",
            str(here),
            "--data-dir",
            str(Path(ARGS.data_dir).resolve()),
            "--dump-spy",
            str(tmp),
        ],
        cwd=ARGS.baseline,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return {"skipped": f"baseline run failed: {proc.stderr[-600:]}", "pass": None}
    old = json.loads(tmp.read_text(encoding="utf-8"))
    out: dict[str, Any] = {}
    ok = True
    for model in ("ff5", "ff6"):
        new_report = await svc.report("SPY", model=model)  # type: ignore[arg-type]
        new_full = json.loads(new_report.model_dump_json())
        new_key = key_figures(new_report)
        same_key = close(old[model]["key"], new_key)
        diff_sections = sorted(
            k
            for k in set(new_full) | set(old[model]["full"])
            if not close(new_full.get(k), old[model]["full"].get(k))
        )
        out[model] = {
            "key_figures_equal": same_key,
            "alpha_annual": new_key["alpha_annual"],
            "r2": new_key["r2"],
            "betas": new_key["betas"],
            "baseline_alpha_annual": old[model]["key"]["alpha_annual"],
            "baseline_r2": old[model]["key"]["r2"],
            "baseline_betas": old[model]["key"]["betas"],
            "sections_that_differ": diff_sections,
            "differing_keys_inside": {
                k: sorted(
                    kk
                    for kk in set(new_full.get(k) or {}) | set(old[model]["full"].get(k) or {})
                    if not close((new_full.get(k) or {}).get(kk), old[model]["full"][k].get(kk))
                )
                for k in diff_sections
                if isinstance(new_full.get(k), dict) and isinstance(old[model]["full"].get(k), dict)
            },
        }
        ok = ok and same_key
    out["pass"] = ok
    return out


async def check7(svc: ReportService) -> dict[str, Any]:
    report = await svc.report("SPY", model="ff6")
    section = report.tail_risk
    assert section is not None
    perf = report.performance
    years = perf.periods.years if perf is not None and perf.periods is not None else 0.0
    rows: dict[str, Any] = {}
    for h in section.by_horizon or []:
        hist = {}
        if h.figures:
            hist = {
                f"{f.measure}@{f.level}": f.value if f.value is not None else f"none ({f.reason})"
                for f in h.figures
                if f.method == "historical"
            }
        rows[h.horizon] = {
            "status": h.status,
            "n_obs": None if h.series is None else h.series.n_obs,
            "reason": h.reason,
            "historical": hist,
        }
    ok = (
        set(rows) == {"daily", "monthly", "quarterly"}
        and all(r["status"] == "ok" for r in rows.values())
        and years > 0
        and abs(rows["monthly"]["n_obs"] - 12 * years) <= 3
        and abs(rows["quarterly"]["n_obs"] - 4 * years) <= 2
    )
    return {"years": years, "frequency": section.frequency, "horizons": rows, "pass": ok}


async def main() -> None:
    svc = make_service()
    results: dict[str, Any] = {}
    for name, fn in (
        ("1", check1),
        ("2", check2),
        ("3", check3),
        ("4", check4),
        ("5", check5),
        ("6", check6),
        ("7", check7),
    ):
        print(f"check {name} ...", flush=True)
        try:
            results[name] = await fn(svc)
        except Exception as exc:  # report and go on: one failing check must not hide the rest
            results[name] = {"error": f"{type(exc).__name__}: {exc}", "pass": False}
        print(json.dumps(results[name], indent=2, default=str), flush=True)
    print("\nSUMMARY")
    for name, res in results.items():
        flag = "SKIP" if res.get("pass") is None else ("PASS" if res["pass"] else "FAIL")
        print(f"  check {name}: {flag}")
    if ARGS.out:
        Path(ARGS.out).write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    if ARGS.dump_spy:
        asyncio.run(dump_spy(ARGS.dump_spy))
    else:
        asyncio.run(main())
    sys.exit(0)
