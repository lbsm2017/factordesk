"""Sprint 4 real-data validation: measure the Developed Europe factor set.

Builds reports in-process through the app's own service layer (``ReportService`` over
``default_deps``), on real downloaded data, with no server. It changes no app code and writes no
file except the data caches (default ``data/``, git-ignored) and, with ``--out``, a JSON of the
measured numbers.

Run from the repository root::

    uv run python scripts/validate_sprint4.py [--data-dir data] [--out numbers.json]
        [--baseline PATH_TO_CHECKOUT_OF_DEV]

``--baseline`` is a directory that holds ``backend/factordesk`` as it is on dev (a checkout, or
``git archive origin/dev backend``). Check 3 runs the SPY dump in it, with the same Python
and the same data cache, and compares.

Checks (see ``docs/sprints/sprint-4.md``, item S4-8 and design decisions 1 to 4)
    1. VGK and EXSA.DE in EUR: R2 with the Europe set above R2 with the US set (FF5 and FF6).
    2. SPY in USD: R2 with the US set above R2 with the Europe set (FF5 and FF6).
    3. SPY in USD with the US set against dev: every figure equal.
    4. EUR with the Europe set: the market factor against ``(1+MktRF+RF)(1+f)-1-c_eur`` built by
       hand from the raw Europe file, the ECB dollar rate and the euro cash rate.
    5. VGK monthly in EUR (an uploaded record): the same R2 ordering as check 1.
    6. Balanced SAA with the Europe set, in USD and EUR: the holdings totals tie out.
    7. SPY: the world beta, macro and energy sections are the same with both sets.

``--dump-spy FILE`` is internal: it writes the SPY USD reports (FF5 and FF6) as JSON and exits;
check 3 runs it in the baseline checkout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
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


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--out", default=None, help="write the measured numbers as JSON")
    ap.add_argument("--baseline", default=None, help="checkout (or export) of dev")
    ap.add_argument("--dump-spy", default=None, help=argparse.SUPPRESS)
    return ap.parse_args()


ARGS = parse_args()
os.environ["DATA_DIR"] = str(Path(ARGS.data_dir).resolve())

import pandas as pd  # noqa: E402
from factordesk.api.deps import default_deps  # noqa: E402
from factordesk.api.portfolio_models import PortfolioTree, load_library  # noqa: E402
from factordesk.api.runtime import Runtime  # noqa: E402
from factordesk.api.service import ReportService  # noqa: E402
from factordesk.report.schema import FactorReport  # noqa: E402


def make_service() -> ReportService:
    return ReportService(Runtime(default_deps()))


# ----------------------------------------------------------------------------- helpers
def tree_of(name: str, lines: list[tuple[str, int]], ccy: str, factor_set: str) -> PortfolioTree:
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
    if factor_set != "us":
        body["factor_set"] = factor_set
    return PortfolioTree.model_validate(body)


async def converted_prices(svc: ReportService, ticker: str, ccy: str) -> pd.Series:
    """Adjusted close of ``ticker`` in ``ccy`` as the report sees it."""
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
    return adj[adj > 0].dropna()


def fit_of(report: FactorReport) -> dict[str, Any]:
    reg, data = report.regression, report.data
    assert reg is not None
    return {
        "r2": reg.r2,
        "adj_r2": reg.adj_r2,
        "alpha_annual": reg.alpha_annual,
        "sigma_e_annual": reg.sigma_e_annual,
        "betas": {f.name: f.beta for f in reg.factors},
        "n_obs": data.n_obs,
        "window": f"{data.actual_start} to {data.actual_end}",
        "factor_set": report.factor_set or "us",
        "factors_source_url": data.factors_source_url,
        "factors_last_date": str(data.factors_last_date),
    }


def vintage_of(frame: pd.DataFrame) -> dict[str, Any]:
    """File stamps of a joined FF6 frame: both files, as ``join_momentum`` records them."""
    out: dict[str, Any] = {
        "factor_set": frame.attrs.get("factor_set"),
        "first_date": frame.attrs.get("first_date"),
        "last_date": frame.attrs.get("last_date"),
        "rows": len(frame),
    }
    for part in ("ff5", "mom"):
        info = dict(frame.attrs.get(part) or {})
        out[part] = {
            k: info.get(k)
            for k in (
                "key",
                "downloaded_at",
                "last_modified",
                "crsp_stamp",
                "stamp_source",
                "sha256",
                "first_date",
                "last_date",
            )
        }
    return out


# ----------------------------------------------------------------------------- check 1, 2, 5
async def ordering(svc: ReportService, ticker: str, ccy: str, expect_higher: str) -> dict[str, Any]:
    """R2 of ``ticker`` with each set, FF5 and FF6; ``expect_higher`` is the set that must win."""
    out: dict[str, Any] = {}
    ok = True
    for model in ("ff5", "ff6"):
        runs = {
            fs: fit_of(await svc.report(ticker, model=model, ccy=ccy, factor_set=fs))  # type: ignore[arg-type]
            for fs in ("us", "europe")
        }
        other = "europe" if expect_higher == "us" else "us"
        win = runs[expect_higher]["r2"] > runs[other]["r2"]
        ok = ok and win
        out[model] = {
            "us": runs["us"],
            "europe": runs["europe"],
            "r2_gain_europe_minus_us": runs["europe"]["r2"] - runs["us"]["r2"],
            "expected_higher": expect_higher,
            "pass": win,
        }
    out["pass"] = ok
    return out


async def timing_diagnostic(svc: ReportService, ticker: str) -> dict[str, Any]:
    """Information only: why a US-listed European fund can fit the Europe factors worse.

    VGK closes in New York, after the European markets; news of the US afternoon reaches Europe
    the next morning. Daily R2 (five factors, EUR) of the fund on the US factors and on the
    Europe factors, on the dates all three series share; then on the Europe factors of the same
    day and of the next Europe trading day.
    """
    import numpy as np

    now = svc._now()  # pyright: ignore[reportPrivateUsage]
    loaded = await svc._factors()  # pyright: ignore[reportPrivateUsage]
    ctx = svc.deps.currency
    from factordesk.api.currency_ctx import CurrencyContext

    frames = {
        fs: await svc._model_frame(loaded, now, "ff5", CurrencyContext("EUR", ctx), fs)  # type: ignore[arg-type]  # pyright: ignore[reportPrivateUsage]
        for fs in ("us", "europe")
    }
    prices = await converted_prices(svc, ticker, "EUR")
    codes = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
    common = prices.index.intersection(frames["us"].index).intersection(frames["europe"].index)
    ret = prices.loc[common].pct_change().dropna()

    def r2(y: pd.Series, x: pd.DataFrame) -> float:
        design = np.column_stack([np.ones(len(x)), x.to_numpy()])
        beta, *_ = np.linalg.lstsq(design, y.to_numpy(), rcond=None)
        return float(1.0 - (y.to_numpy() - design @ beta).var() / y.var())

    out: dict[str, Any] = {
        "n_common_days": len(ret),
        "window": f"{ret.index[0].date()} to {ret.index[-1].date()}",
    }
    for fs, frame in frames.items():
        rf = frame["RF"].loc[ret.index]
        out[f"r2_same_day_{fs}"] = r2(ret - rf, frame.loc[ret.index, codes])
    eu = frames["europe"]
    lead = eu[codes].shift(-1).loc[ret.index]
    both = pd.concat([eu.loc[ret.index, codes], lead.add_suffix("_next")], axis=1).dropna()
    y = (ret - eu["RF"].loc[ret.index]).loc[both.index]
    out["r2_europe_same_and_next_day"] = r2(y, both)
    out["note"] = "information only; not part of the pass rule"
    return out


async def check1(svc: ReportService) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for ticker in ("VGK", "EXSA.DE"):
        out[ticker] = await ordering(svc, ticker, "EUR", "europe")
    out["pass"] = all(out[t]["pass"] for t in ("VGK", "EXSA.DE"))
    out["timing_diagnostic_vgk"] = await timing_diagnostic(svc, "VGK")
    return out


async def check2(svc: ReportService) -> dict[str, Any]:
    return await ordering(svc, "SPY", "USD", "us")


async def check5(svc: ReportService) -> dict[str, Any]:
    """VGK monthly: the month-end prices in EUR, sent as an uploaded record in EUR."""
    from factordesk.api.routes_upload import build_upload_report

    prices = await converted_prices(svc, "VGK", "EUR")
    month_end = prices.resample("ME").last()
    returns = month_end.pct_change().dropna()
    last_full = (pd.Timestamp(svc._now()) - pd.offsets.MonthEnd(1)).normalize().tz_localize(None)  # pyright: ignore[reportPrivateUsage]
    returns = returns[returns.index <= last_full]
    raw = ("date,return\n" + "\n".join(f"{d:%Y-%m-%d},{v!r}" for d, v in returns.items())).encode()
    out: dict[str, Any] = {"record_months": len(returns), "first": str(returns.index[0].date())}
    ok = True
    for model in ("ff5", "ff6"):
        runs: dict[str, Any] = {}
        for fs in ("us", "europe"):
            report = await svc.runtime.run(
                build_upload_report, raw, "VGK monthly", None, svc.runtime, model, "EUR", "EUR", fs
            )
            runs[fs] = fit_of(report)
        win = runs["europe"]["r2"] > runs["us"]["r2"]
        ok = ok and win
        out[model] = {
            **runs,
            "r2_gain_europe_minus_us": runs["europe"]["r2"] - runs["us"]["r2"],
            "pass": win,
        }
    out["pass"] = ok
    return out


# ----------------------------------------------------------------------------- check 3
def close(a: Any, b: Any, tol: float = 0.0) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k], tol) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(close(x, y, tol) for x, y in zip(a, b, strict=True))
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= tol * max(1.0, abs(a), abs(b))
    return a == b


def max_difference(a: Any, b: Any) -> float:
    """Largest absolute difference between two JSON trees of the same shape (0 when equal)."""
    if isinstance(a, dict) and isinstance(b, dict):
        return max([max_difference(a[k], b[k]) for k in a.keys() & b.keys()] or [0.0])
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return max([max_difference(x, y) for x, y in zip(a, b, strict=True)] or [0.0])
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(float(a) - float(b))
    return 0.0


def differing_paths(a: Any, b: Any, path: str = "$") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out: list[str] = []
        for k in sorted(a.keys() | b.keys()):
            if k not in a or k not in b:
                out.append(f"{path}.{k} (missing on one side)")
            else:
                out += differing_paths(a[k], b[k], f"{path}.{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path} (length {len(a)} against {len(b)})"]
        return [
            p
            for i, (x, y) in enumerate(zip(a, b, strict=True))
            for p in differing_paths(x, y, f"{path}[{i}]")
        ]
    return [] if a == b else [path]


def dump_spy(path: str) -> None:
    import factordesk

    async def run() -> dict[str, Any]:
        svc = make_service()
        out: dict[str, Any] = {"package_file": str(factordesk.__file__)}
        for model in ("ff5", "ff6"):
            report = await svc.report("SPY", model=model)  # type: ignore[arg-type]
            out[model] = json.loads(report.model_dump_json())
        return out

    Path(path).write_text(json.dumps(asyncio.run(run())), encoding="utf-8")


async def check3(svc: ReportService) -> dict[str, Any]:
    if ARGS.baseline is None:
        return {"skipped": "no --baseline checkout given", "pass": None}
    base = Path(ARGS.baseline).resolve()
    tmp = Path(ARGS.data_dir).resolve() / "spy_baseline_dev.json"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(base / "backend")
    proc = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--data-dir",
            str(Path(ARGS.data_dir).resolve()),
            "--dump-spy",
            str(tmp),
        ],
        cwd=str(base),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return {"skipped": f"baseline run failed: {proc.stderr[-800:]}", "pass": None}
    old = json.loads(tmp.read_text(encoding="utf-8"))
    out: dict[str, Any] = {"baseline_package_file": old["package_file"]}
    ok = str(base) in old["package_file"]
    out["baseline_is_the_checkout"] = ok
    for model in ("ff5", "ff6"):
        new_full = json.loads(
            (await svc.report("SPY", model=model, factor_set="us")).model_dump_json()  # type: ignore[arg-type]
        )
        a = {k: v for k, v in new_full.items() if k != "generated_at"}
        b = {k: v for k, v in old[model].items() if k != "generated_at"}
        same = a == b
        paths = differing_paths(a, b)
        reg = new_full["regression"]
        out[model] = {
            "identical_except_generated_at": same,
            "largest_numeric_difference": max_difference(a, b),
            "differing_paths": paths[:20],
            "n_differing_paths": len(paths),
            "r2": reg["r2"],
            "baseline_r2": old[model]["regression"]["r2"],
            "alpha_annual": reg["alpha_annual"],
            "baseline_alpha_annual": old[model]["regression"]["alpha_annual"],
        }
        ok = ok and same
    out["pass"] = ok
    return out


# ----------------------------------------------------------------------------- check 4
def hand_cash(rate: pd.Series, prev: pd.Timestamp, day: pd.Timestamp) -> float:
    """Euro cash return over (prev, day], from the compounded ACT/360 index.

    The index grows by ``1 + rate * days / 360`` across each fixing (a fixing runs to the next
    one) and is read on a date as the last full-period level times simple interest since the
    last fixing. The return is the ratio of the two readings, so a date inside a fixing period
    (a holiday with no fixing) is handled as the index defines it.
    """
    r = rate.dropna()

    def level(x: pd.Timestamp) -> float:
        fixings = r.loc[:x]
        grown = 1.0
        for (d0, r0), d1 in zip(fixings.iloc[:-1].items(), fixings.index[1:], strict=True):
            grown *= 1.0 + float(r0) * (d1 - d0).days / 360.0  # type: ignore[operator]
        return grown * (1.0 + float(fixings.iloc[-1]) * (x - fixings.index[-1]).days / 360.0)

    return level(day) / level(prev) - 1.0


async def check4(svc: ReportService) -> dict[str, Any]:
    from factordesk.api.currency_ctx import CurrencyContext
    from factordesk.data import french, rates
    from factordesk.data.ecb import load_ecb_series

    now = svc._now()  # pyright: ignore[reportPrivateUsage]
    data_dir = svc.deps.data_dir
    raw = french.load_ff6("daily", data_dir=data_dir, now=now, factor_set="europe")
    loaded = await svc._factors()  # pyright: ignore[reportPrivateUsage]
    ctx = CurrencyContext("EUR", svc.deps.currency)  # type: ignore[arg-type]
    app = await svc._model_frame(loaded, now, "ff6", ctx, "europe")  # pyright: ignore[reportPrivateUsage]
    per_eur, _ = load_ecb_series("EXR", "D.USD.EUR.SP00.A", data_dir=data_dir, now=now)
    eur_per_usd = (1.0 / per_eur).dropna()
    eur_rate = rates.load_eur_overnight(data_dir=data_dir, now=now).rate
    assert eur_rate is not None

    def usd_in_eur(day: pd.Timestamp) -> float:
        return float(eur_per_usd.loc[:day].iloc[-1])

    pick = [0.05, 0.30, 0.55, 0.80, 1.0]
    days = [app.index[min(int(q * len(app)), len(app) - 1)] for q in pick]
    rows: list[dict[str, Any]] = []
    for day in days:
        pos = int(raw.index.get_loc(day))  # type: ignore[arg-type]
        prev = raw.index[pos - 1]
        f = usd_in_eur(day) / usd_in_eur(prev) - 1.0
        c = hand_cash(eur_rate, prev, day)
        mkt, rf, smb = (
            float(raw.loc[day, "Mkt-RF"]),
            float(raw.loc[day, "RF"]),
            float(raw.loc[day, "SMB"]),
        )
        by_hand = (1.0 + mkt + rf) * (1.0 + f) - 1.0 - c
        rows.append(
            {
                "date": str(day.date()),
                "previous_row": str(prev.date()),
                "raw_mkt_rf": mkt,
                "raw_rf": rf,
                "usd_in_eur_return": f,
                "eur_cash_return": c,
                "mkt_by_hand": by_hand,
                "mkt_in_app": float(app.loc[day, "Mkt-RF"]),
                "mkt_abs_diff": abs(by_hand - float(app.loc[day, "Mkt-RF"])),
                "rf_abs_diff": abs(c - float(app.loc[day, "RF"])),
                "smb_abs_diff": abs(smb * (1.0 + f) - float(app.loc[day, "SMB"])),
            }
        )
    worst = max(max(r["mkt_abs_diff"], r["rf_abs_diff"], r["smb_abs_diff"]) for r in rows)
    return {
        "vintage": vintage_of(raw),
        "converted_rows": len(app),
        "raw_rows": len(raw),
        "samples": rows,
        "largest_abs_difference": worst,
        "pass": worst < 1e-9,
    }


# ----------------------------------------------------------------------------- check 6
def holdings_checks(report: FactorReport) -> dict[str, Any]:
    section = report.holdings
    assert section is not None
    rows = section.rows
    kids: dict[str, list[Any]] = {}
    for r in rows:
        if r.parent_id is not None:
            kids.setdefault(r.parent_id, []).append(r)
    worst, n_groups = 0.0, 0
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
        "factor_set": report.factor_set or "us",
        "n_rows": len(rows),
        "n_groups": n_groups,
        "worst_group_vs_leaves": worst,
        "holdings_total_return": section.total_return,
        "performance_cumulative_return": perf,
        "total_return_diff": section.total_return - perf,
        "top_level_contribution_sum": contrib_sum,
        "contribution_sum_diff": contrib_sum - section.total_return,
        "risk_share_sum": share_sum,
        "n_days": section.n_days,
        "window": f"{section.window_start} to {section.window_end}",
        "r2_ff6": None if report.regression is None else report.regression.r2,
        "pass": report.factor_set == "europe"
        and worst < 1e-9
        and abs(section.total_return - perf) < 1e-9
        and share_sum is not None
        and abs(share_sum - 1.0) < 1e-9,
    }


async def check6(svc: ReportService) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for ccy in ("USD", "EUR"):
        tree = tree_of(f"Balanced SAA Europe {ccy}", PRESET_BALANCED, ccy, "europe")
        report = await svc.portfolio_report(tree, None, None, None, "ff6")
        out[ccy] = holdings_checks(report)
    out["pass"] = out["USD"]["pass"] and out["EUR"]["pass"]
    return out


# ----------------------------------------------------------------------------- check 7
async def check7(svc: ReportService) -> dict[str, Any]:
    out: dict[str, Any] = {}
    ok = True
    for model in ("ff5", "ff6"):
        us = json.loads(
            (await svc.report("SPY", model=model, factor_set="us")).model_dump_json()  # type: ignore[arg-type]
        )
        eu = json.loads(
            (await svc.report("SPY", model=model, factor_set="europe")).model_dump_json()  # type: ignore[arg-type]
        )
        res: dict[str, Any] = {
            "window_us": us["data"]["actual_start"] + " to " + us["data"]["actual_end"],
            "window_europe": eu["data"]["actual_start"] + " to " + eu["data"]["actual_end"],
        }
        for section in ("world_beta", "macro", "energy"):
            a, b = us.get(section), eu.get(section)
            same = a == b
            res[section] = {
                "present_us": a is not None,
                "present_europe": b is not None,
                "identical": same,
                "differing_paths": [] if same else differing_paths(a, b, section)[:25],
                "n_differing_paths": 0 if same else len(differing_paths(a, b, section)),
                "largest_numeric_difference": 0.0 if same else max_difference(a, b),
            }
            ok = ok and same
        out[model] = res
    out["pass"] = ok
    return out


# ----------------------------------------------------------------------------- main
async def vintages(svc: ReportService) -> dict[str, Any]:
    from factordesk.data import french

    now = svc._now()  # pyright: ignore[reportPrivateUsage]
    out: dict[str, Any] = {
        "run_date": datetime.now(UTC).date().isoformat(),
        "app_now": now.isoformat(),
    }
    for fs in ("us", "europe"):
        for freq in ("daily", "monthly"):
            frame = french.load_ff6(freq, data_dir=svc.deps.data_dir, now=now, factor_set=fs)  # type: ignore[arg-type]
            out[f"{fs}_{freq}"] = vintage_of(frame)
    out["spy_last_price_date"] = str(
        (await svc._history("SPY", now.date())).frame.index[-1].date()  # pyright: ignore[reportPrivateUsage]
    )
    return out


async def main() -> None:
    svc = make_service()
    results: dict[str, Any] = {}
    print("vintages ...", flush=True)
    results["vintages"] = await vintages(svc)
    print(json.dumps(results["vintages"], indent=2, default=str), flush=True)
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
            import traceback

            results[name] = {
                "error": f"{type(exc).__name__}: {exc}",
                "trace": traceback.format_exc()[-1500:],
                "pass": False,
            }
        print(json.dumps(results[name], indent=2, default=str), flush=True)
    print("\nSUMMARY")
    for name, res in results.items():
        if name == "vintages":
            continue
        flag = "SKIP" if res.get("pass") is None else ("PASS" if res["pass"] else "FAIL")
        print(f"  check {name}: {flag}")
    if ARGS.out:
        Path(ARGS.out).write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    if ARGS.dump_spy:
        dump_spy(ARGS.dump_spy)
    else:
        asyncio.run(main())
    sys.exit(0)
