"""Sprint 3 spike S3-6: measure oil, gas and carbon legs before building the Energy section.

Reproduces every number of ``docs/research/energy-factor-spike.md``. It changes no app code and
writes no file except the data caches (default ``data/``, git-ignored).

Run from the repository root::

    uv run python scripts/energy_factor_spike.py [--data-dir data] [--out table.md]

Legs (all on the French daily calendar, or the French monthly month-ends)
    MKT   French Mkt-RF.
    OIL   log return of Brent spot, FRED DCOILBRENTEU.
    GAS   log return of Henry Hub spot, FRED DHHNGSP (non-positive prices dropped and counted).
    CO2   KRBN total return minus French RF (Yahoo; first month 2020-07).
    COMM  DBC total return minus French RF.
Subjects (excess return over RF)
    SPY, XLE, XLU, and 60/40 = IVV 60% / IEF 40% by ``analytics.backtest.run_backtest`` (monthly
    rebalance, no cost, daily simple returns).

Alignment follows ``analytics.macro``: a daily leg return counts only when the leg's previous
level date is the calendar's previous date (``daily_leg_returns``), so a missing FRED day (``.``)
removes that day and the next one; nothing is filled. Monthly legs compound to month-ends
(``monthly_leg_returns``). Inference is ``regression.ols_hac`` (Newey-West; small-sample
scaling and Student-t for monthly). VIF is ``regression.vif``.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from factordesk.analytics.backtest import run_backtest
from factordesk.analytics.macro import daily_leg_returns, monthly_leg_returns, summed_beta
from factordesk.analytics.regression import ols_hac, vif
from factordesk.data.factors import load_ff5_daily
from factordesk.data.fred import load_fred_series
from factordesk.data.french import load_ff5_monthly
from factordesk.data.prices import YFinanceProvider

START = pd.Timestamp("2007-01-01")
CARBON_START = pd.Timestamp("2020-08-01")
SUBJECTS = ("SPY", "XLE", "XLU", "60/40")
LEGS = ("MKT", "OIL", "GAS", "CO2", "COMM")
SPIKE_DAYS = 5
T_FLAG = 2.0

LEVELS: dict[str, pd.Series] = {}
FRESH: list[tuple[str, str, str]] = []
NOTES: list[str] = []


# ------------------------------------------------------------------------------ data loading
def fred_levels(series_id: str, data_dir: Path) -> pd.Series:
    """Series levels with non-positive prices set to NaN; counts go to ``NOTES``."""
    got = load_fred_series(series_id, data_dir=data_dir)
    raw = got.values.astype("float64")  # noqa: PD011
    n_missing = int(raw.isna().sum())
    n_bad = int((raw <= 0).sum())
    bad_dates = ", ".join(d.date().isoformat() for d in raw.index[raw <= 0][:10])
    NOTES.append(
        f"{series_id}: {len(raw)} rows, {raw.first_valid_index():%Y-%m-%d} to "
        f"{raw.last_valid_index():%Y-%m-%d}; {n_missing} missing ('.'); "
        f"{n_bad} non-positive prices dropped"
        + (f" ({bad_dates})" if n_bad else "")
        + (f"; {got.note}" if got.note else "")
    )
    return raw.where(raw > 0)


def price_levels(provider: YFinanceProvider, ticker: str) -> pd.Series:
    frame = provider.fetch(ticker).frame
    return frame["adj_close"].astype("float64")


def load_all(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The daily and the monthly frames: legs, RF and subject excess returns."""
    provider = YFinanceProvider(cache_dir=data_dir / "prices")
    ff_d = load_ff5_daily(data_dir=data_dir)[["Mkt-RF", "RF"]].astype("float64")
    ff_m = load_ff5_monthly(data_dir=data_dir)[["Mkt-RF", "RF"]].astype("float64")
    brent = fred_levels("DCOILBRENTEU", data_dir)
    gas = fred_levels("DHHNGSP", data_dir)
    for ticker in ("SPY", "XLE", "XLU", "IVV", "IEF", "KRBN", "DBC"):
        LEVELS[ticker] = price_levels(provider, ticker)

    cal_d = pd.DatetimeIndex(ff_d.index)
    ids_m = pd.DatetimeIndex(ff_m.index)

    def daily(levels: pd.Series, log: bool) -> pd.Series:
        r = daily_leg_returns(levels, cal_d)
        return np.log1p(r) if log else r

    d = pd.DataFrame(index=cal_d[1:])
    d["RF"] = ff_d["RF"].reindex(d.index)
    d["MKT"] = ff_d["Mkt-RF"].reindex(d.index)
    d["OIL"] = daily(brent, True)
    d["GAS"] = daily(gas, True)
    d["CO2"] = daily(LEVELS["KRBN"], False) - d["RF"]
    d["COMM"] = daily(LEVELS["DBC"], False) - d["RF"]
    legs = pd.DataFrame({t: LEVELS[t] for t in ("IVV", "IEF")}).pipe(lambda f: f / f.shift(1) - 1.0)
    bt = run_backtest(legs.dropna(how="all"), {"IVV": 0.6, "IEF": 0.4}, ff_d["RF"])
    NOTES.append(
        f"60/40 by run_backtest: IVV 0.6 / IEF 0.4, monthly rebalance, cost 0, window "
        f"{bt.start} to {bt.end}, {len(bt.rebalance_dates)} rebalances."
    )
    for t in ("SPY", "XLE", "XLU"):
        d[t] = daily(LEVELS[t], False) - d["RF"]
    d["60/40"] = bt.ret.reindex(d.index) - d["RF"]

    m = pd.DataFrame(index=ids_m)
    m["RF"] = ff_m["RF"]
    m["MKT"] = ff_m["Mkt-RF"]
    m["OIL"] = np.log1p(monthly_leg_returns(brent, ids_m))
    m["GAS"] = np.log1p(monthly_leg_returns(gas, ids_m))
    m["CO2"] = monthly_leg_returns(LEVELS["KRBN"], ids_m) - m["RF"]
    m["COMM"] = monthly_leg_returns(LEVELS["DBC"], ids_m) - m["RF"]
    for t in ("SPY", "XLE", "XLU"):
        m[t] = monthly_leg_returns(LEVELS[t], ids_m) - m["RF"]
    comp = (1.0 + bt.ret).groupby(bt.ret.index.to_period("M")).prod() - 1.0
    comp.index = comp.index.to_timestamp(how="end").normalize()
    m["60/40"] = comp.reindex(ids_m) - m["RF"]

    # Lag-1 columns (daily): the leg's value on the calendar's previous date.
    for leg in ("OIL", "GAS", "CO2"):
        d[f"{leg}_l"] = d[leg].shift(1)
    FRESH.append(("French daily FF5 (Mkt-RF, RF)", f"{cal_d[-1]:%Y-%m-%d}", ""))
    FRESH.append(("French monthly FF5", f"{ids_m[-1]:%Y-%m-%d}", ""))
    for ticker in ("SPY", "XLE", "XLU", "IVV", "IEF", "KRBN", "DBC"):
        FRESH.append((f"Yahoo {ticker}", f"{LEVELS[ticker].dropna().index[-1]:%Y-%m-%d}", ""))
    for sid, lv in (("FRED DCOILBRENTEU", brent), ("FRED DHHNGSP", gas)):
        FRESH.append((sid, f"{lv.dropna().index[-1]:%Y-%m-%d}", ""))
    return d.loc[START:], m.loc[START:]


# --------------------------------------------------------------------------------- helpers
def sample(df: pd.DataFrame, cols: list[str], start: pd.Timestamp) -> pd.DataFrame:
    return df.loc[start:, cols].dropna()


def fit(df: pd.DataFrame, y: str, xs: list[str], monthly: bool):  # noqa: ANN201
    return ols_hac(
        df[y].to_numpy(),
        df[xs].to_numpy(),
        names=xs,
        small_sample=monthly,
    )


def fmt(x: float, nd: int = 3) -> str:
    return f"{x:+.{nd}f}"


def table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def span(df: pd.DataFrame) -> str:
    return f"{df.index[0]:%Y-%m-%d} to {df.index[-1]:%Y-%m-%d}, n={len(df)}"


# ------------------------------------------------------------------------------- sections
def corr_section(d: pd.DataFrame, m: pd.DataFrame, out: list[str]) -> None:
    out.append("## 1. Correlation matrices\n")
    for name, df in (("daily", d), ("monthly", m)):
        for tag, cols, start in (
            ("carbon window", list(LEGS), CARBON_START),
            ("full window, no CO2", ["MKT", "OIL", "GAS", "COMM"], START),
        ):
            s = sample(df, cols, start)
            c = s.corr()
            out.append(f"**{name}, {tag}** ({span(s)})\n")
            out.append(
                table([""] + cols, [[r] + [f"{c.loc[r, k]:+.2f}" for k in cols] for r in cols])
            )


def vif_section(d: pd.DataFrame, m: pd.DataFrame, out: list[str]) -> None:
    out.append("## 2. VIF\n")
    models = (
        ("L = MKT,OIL,GAS (2007+)", ["MKT", "OIL", "GAS"], START),
        ("L on carbon window", ["MKT", "OIL", "GAS"], CARBON_START),
        ("C = L + CO2 (2020-08+)", ["MKT", "OIL", "GAS", "CO2"], CARBON_START),
        ("L + COMM (2007+)", ["MKT", "OIL", "GAS", "COMM"], START),
        ("L + COMM on carbon window", ["MKT", "OIL", "GAS", "COMM"], CARBON_START),
        ("C + COMM (2020-08+)", list(LEGS), CARBON_START),
    )
    for name, df in (("daily", d), ("monthly", m)):
        rows = []
        for label, cols, start in models:
            s = sample(df, cols, start)
            v = dict(zip(cols, vif(s.to_numpy()), strict=True))
            rows.append([label, str(len(s))] + [f"{v[k]:.2f}" if k in v else "" for k in LEGS])
        out.append(f"**{name}**\n")
        out.append(table(["model", "n"] + list(LEGS), rows))


def beta_section(d: pd.DataFrame, m: pd.DataFrame, out: list[str]) -> None:
    out.append("## 3. Betas and Newey-West t-statistics\n")
    out.append(
        "Cell = beta (t). Beta is the excess return per 1.00 of the leg return "
        "(log for OIL and GAS). L = MKT,OIL,GAS; C = L + CO2.\n"
    )
    for name, df in (("daily", d), ("monthly", m)):
        monthly = name == "monthly"
        rows = []
        for sub in SUBJECTS:
            for label, xs, start in (
                ("L 2007+", ["MKT", "OIL", "GAS"], START),
                ("L 2020-08+", ["MKT", "OIL", "GAS"], CARBON_START),
                ("C 2020-08+", ["MKT", "OIL", "GAS", "CO2"], CARBON_START),
            ):
                s = sample(df, [sub, *xs], start)
                f = fit(s.rename(columns={sub: "y"}), "y", xs, monthly)
                cells = {
                    x: f"{fmt(f.params[i + 1])} ({f.zvalues[i + 1]:+.1f})" for i, x in enumerate(xs)
                }
                rows.append(
                    [sub, label, str(f.nobs)]
                    + [cells.get(k, "") for k in ("MKT", "OIL", "GAS", "CO2")]
                    + [f"{f.rsquared:.2f}"]
                )
        out.append(f"**{name}**\n")
        out.append(table(["subject", "model", "n", "MKT", "OIL", "GAS", "CO2", "R2"], rows))


def lag_section(d: pd.DataFrame, out: list[str]) -> list[str]:
    out.append("## 4. Lag test (daily)\n")
    out.append(
        "Added OIL_l, GAS_l, CO2_l (the leg's value on the previous trading day). Cell = "
        "summed beta (b0+b1) / t of the lag term alone. `*` marks |t_lag| > 2.\n"
    )
    rows = []
    flagged: list[str] = []
    for sub in SUBJECTS:
        for label, legs, start in (
            ("L+lags 2007+", ["OIL", "GAS"], START),
            ("C+lags 2020-08+", ["OIL", "GAS", "CO2"], CARBON_START),
        ):
            xs = ["MKT", *legs, *[f"{x}_l" for x in legs]]
            s = sample(d, [sub, *xs], start)
            f = fit(s.rename(columns={sub: "y"}), "y", xs, False)
            row = [sub, label, str(f.nobs)]
            for leg in ("OIL", "GAS", "CO2"):
                if leg not in legs:
                    row.append("")
                    continue
                i0 = xs.index(leg) + 1
                i1 = xs.index(f"{leg}_l") + 1
                b, _ = summed_beta(f.params, f.cov, i0, i1)
                t_lag = float(f.zvalues[i1])
                star = "*" if abs(t_lag) > T_FLAG else ""
                if star:
                    flagged.append(f"{sub} {label} {leg}: t_lag={t_lag:+.2f}")
                row.append(f"{fmt(b)} / {t_lag:+.1f}{star}")
            rows.append(row)
    out.append(table(["subject", "model", "n", "OIL", "GAS", "CO2"], rows))
    out.append("Flagged: " + ("; ".join(flagged) if flagged else "none") + "\n")
    return flagged


def spike_section(d: pd.DataFrame, m: pd.DataFrame, out: list[str]) -> None:
    out.append("## 5. Gas spike influence\n")
    out.append(
        f"GAS beta with all rows and without the {SPIKE_DAYS} rows of largest |GAS| in the "
        "sample. Cell = beta (t).\n"
    )
    for name, df, label, xs, start in (
        ("daily", d, "L 2007+", ["MKT", "OIL", "GAS"], START),
        ("daily", d, "C 2020-08+", ["MKT", "OIL", "GAS", "CO2"], CARBON_START),
        ("monthly", m, "L 2007+", ["MKT", "OIL", "GAS"], START),
    ):
        monthly = name == "monthly"
        base = sample(df, [*SUBJECTS, *xs], start)
        top = base["GAS"].abs().nlargest(SPIKE_DAYS).index
        g = base["GAS"]
        share = float((g.loc[top] ** 2).sum() / (g**2).sum())
        out.append(
            f"**{name}, {label}** (n={len(base)}). Largest |GAS|: "
            + ", ".join(f"{t:%Y-%m-%d} ({g.loc[t]:+.3f})" for t in top)
            + f". These {SPIKE_DAYS} rows hold {share:.0%} of the sum of squared GAS returns; "
            f"GAS excess kurtosis {float(g.kurt()):.1f}.\n"
        )
        rows = []
        for sub in SUBJECTS:
            s = base[[sub, *xs]].rename(columns={sub: "y"})
            a = fit(s, "y", xs, monthly)
            b = fit(s.drop(index=top), "y", xs, monthly)
            i = xs.index("GAS") + 1
            rows.append(
                [
                    sub,
                    f"{fmt(a.params[i])} ({a.zvalues[i]:+.1f})",
                    f"{fmt(b.params[i])} ({b.zvalues[i]:+.1f})",
                    f"{(b.params[i] - a.params[i]):+.3f}",
                ]
            )
        out.append(table(["subject", "all rows", f"without top {SPIKE_DAYS}", "change"], rows))


def fresh_section(out: list[str]) -> None:
    out.append("## 6. Freshness\n")
    today = datetime.now(UTC).date()
    rows = []
    for series, last, _ in FRESH:
        age = (today - date.fromisoformat(last)).days
        rows.append([series, last, str(age)])
    out.append(f"Today: {today}.\n")
    out.append(table(["series", "last observation", "calendar days old"], rows))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--out", type=Path, default=None, help="also write the tables to this file")
    args = ap.parse_args()

    d, m = load_all(args.data_dir)
    out: list[str] = ["## 0. Data and samples\n"]
    out += [f"- {n}" for n in NOTES]
    out.append(
        "- Daily sample (all legs, from 2007-01): "
        + span(d.dropna(subset=["MKT", "OIL", "GAS", "COMM"]))
        + "."
    )
    out.append(
        f"- Daily carbon sample (from 2020-08): {span(sample(d, list(LEGS), CARBON_START))}."
    )
    out.append(f"- Monthly sample (L legs): {span(m.dropna(subset=['MKT', 'OIL', 'GAS']))}.")
    out.append(f"- Monthly carbon sample: {span(sample(m, list(LEGS), CARBON_START))}.")
    all_d = d.loc[START:, ["MKT"]].dropna()
    lost = {leg: int(d.loc[START:, leg].isna().sum()) for leg in ("OIL", "GAS", "CO2", "COMM")}
    out.append(
        f"- Daily rows 2007+ on the French calendar: {len(all_d)}. Rows without a leg return "
        f"(missing FRED day or the day after one; KRBN and DBC start dates): {lost}.\n"
    )
    corr_section(d, m, out)
    vif_section(d, m, out)
    beta_section(d, m, out)
    lag_section(d, out)
    spike_section(d, m, out)
    fresh_section(out)
    text = "\n".join(out)
    print(text)
    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
