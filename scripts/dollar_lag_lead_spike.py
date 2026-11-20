"""Sprint 4 spike S4-7: does the dollar term of the macro section need a lag, a lead, or neither?

Reproduces every number of ``docs/research/dollar-lag-lead-spike.md``. It changes no app code and
writes no file except the data caches (default ``data/``, git-ignored).

Run from the repository root::

    uv run python scripts/dollar_lag_lead_spike.py [--data-dir data] [--out table.md]

The model is the macro regression of ``analytics.macro`` (market, TERM, DEF, COMM, INFL and the
dollar leg), built by ``macro.build_design`` itself, so the legs, the alignment rule and the EUR
conversion are the app's. The dollar leg is
    USD view: the Fed broad dollar index, FRED DTWEXBGS (noon New York fixing), simple return;
    EUR view: f, the return of the US dollar in euros from ECB reference rates (about 14:10 CET).
Specifications (the same-day dollar term is in every one of them)
    none         same-day term only
    lag          + the previous day's dollar return (what the app does today)
    lead         + the next day's dollar return
    lag+lead     + both
    no dollar    the dollar leg removed (a baseline for the adjusted R2, not a candidate)
Every specification of one subject and view is fitted on the same rows (those where the same-day,
lag and lead terms all exist), so the adjusted R2 values are comparable.

Subjects (excess return over cash): SPY, VGK, EFA, IEF (TERM and DEF dropped from its model:
IEF is the TERM leg), and 60/40 = IVV 60% / IEF 40% by
``analytics.backtest.run_backtest`` (monthly rebalance, no cost, converted as one line in the
EUR view, so it is not hedged). Control: EXSA.DE (STOXX Europe 600 on Xetra, euro listing,
closes 17:30 CET), euro views only, to test the close-time reading.

Views: USD; EUR with the ECB fixing (the app); EUR-noon, the same with FRED H.10 (noon New
York, the app's fallback source), to test whether the lead follows the fixing time.

The EUR views convert each US line as the app does: ``(1 + R)(1 + f) - 1 - c``, with ``c`` the
euro cash return and the market factor converted by ``currency.convert_factors``.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
from factordesk.analytics import macro
from factordesk.analytics.backtest import run_backtest
from factordesk.analytics.currency import EuroLegs, convert_factors
from factordesk.analytics.regression import ols_hac
from factordesk.data import fx, rates
from factordesk.data.factors import load_ff5_daily
from factordesk.data.fred import DOLLAR_SERIES, load_fred_series
from factordesk.data.prices import YFinanceProvider
from scipy import stats

START = pd.Timestamp("2007-01-01")
SUBJECTS = ("SPY", "VGK", "EFA", "IEF", "60/40")
CONTROL = "EXSA.DE"
SPECS: tuple[str, ...] = ("none", "lag", "lead", "lag+lead")
T_FLAG = 2.0
VIEWS = ("USD", "EUR", "EUR-noon")

NOTES: list[str] = []
FRESH: list[tuple[str, str]] = []


# ------------------------------------------------------------------------------ data loading
class Data:
    """Everything loaded once: levels, French factors, the dollar index, the EUR sources."""

    def __init__(self, data_dir: Path) -> None:
        now = datetime.now(UTC)
        self.provider = YFinanceProvider(cache_dir=data_dir / "prices")
        ff = load_ff5_daily(data_dir=data_dir)[["Mkt-RF", "RF"]].astype("float64")
        self.ff = ff
        self.cal = pd.DatetimeIndex(ff.index)
        self.levels = {t: self.adj_close(t) for t in macro.LEG_TICKERS}
        for t in ("SPY", "VGK", "EFA", "IVV", CONTROL):
            self.levels[t] = self.adj_close(t)
        dollar = load_fred_series(DOLLAR_SERIES, data_dir=data_dir)
        self.dollar = dollar.values.astype("float64")  # noqa: PD011
        NOTES.append(
            f"{DOLLAR_SERIES}: {len(self.dollar)} rows, {self.dollar.first_valid_index():%Y-%m-%d} "
            f"to {self.dollar.last_valid_index():%Y-%m-%d}, {int(self.dollar.isna().sum())} "
            "missing ('.')"
        )
        rate = rates.load_eur_overnight(data_dir=data_dir, now=now)
        if rate.rate is None:
            raise SystemExit(f"euro cash rate unavailable: {rate.notice}")
        self.eur_rate = rate.rate
        self.now = now
        self.data_dir = data_dir
        FRESH.append(("French daily FF5", f"{self.cal[-1]:%Y-%m-%d}"))
        FRESH.append((f"FRED {DOLLAR_SERIES}", f"{self.dollar.dropna().index[-1]:%Y-%m-%d}"))
        for t, lv in self.levels.items():
            FRESH.append((f"Yahoo {t}", f"{lv.dropna().index[-1]:%Y-%m-%d}"))

    def adj_close(self, ticker: str) -> pd.Series:
        return self.provider.fetch(ticker).frame["adj_close"].astype("float64")

    def fx_returns(self, calendar: pd.DatetimeIndex, noon: bool = False) -> pd.Series:
        """USD in EUR, indexed by ``calendar[1:]``: ECB fixings, or FRED H.10 DEXUSEU (noon New
        York) when ``noon`` is true (the app's own fallback source, read directly here because a
        cached ECB file would otherwise be used)."""
        if noon:
            usd_per_eur, _ = fx._fred_leg("EUR", self.data_dir, self.now, None)  # noqa: SLF001
            price = 1.0 / fx._price_on(usd_per_eur, calendar)  # noqa: SLF001
            out = (price / price.shift(1) - 1.0).iloc[1:].rename("fx")
            note = f"USD/EUR source (noon variant): {fx.SOURCE_FRED} DEXUSEU"
        else:
            got = fx.fx_returns("USD", "EUR", calendar, data_dir=self.data_dir, now=self.now)
            if got.series is None:
                raise SystemExit(f"USD/EUR unavailable: {got.notice}")
            out = got.series
            note = f"USD/EUR source (ECB variant): {got.source}"
        if note not in NOTES:
            NOTES.append(note)
        return out

    def cash(self, calendar: pd.DatetimeIndex) -> pd.Series:
        return rates.cash_returns(self.eur_rate, calendar)


def simple_returns(levels: pd.Series, calendar: pd.DatetimeIndex) -> pd.Series:
    """Daily returns of a price series on ``calendar[1:]`` (the app's alignment rule)."""
    return macro.daily_leg_returns(levels, calendar)


def sixty_forty(d: Data) -> pd.Series:
    legs = pd.DataFrame({t: d.levels[t] for t in ("IVV", "IEF")}).pipe(
        lambda f: f / f.shift(1) - 1.0
    )
    bt = run_backtest(legs.dropna(how="all"), {"IVV": 0.6, "IEF": 0.4}, d.ff["RF"])
    NOTES.append(
        f"60/40 by run_backtest: IVV 0.6 / IEF 0.4, monthly rebalance, cost 0, window "
        f"{bt.start} to {bt.end}."
    )
    return bt.ret.astype("float64")


# ------------------------------------------------------------------------------------ design
class Design:
    """The macro design of one subject and view, plus the dollar leg and its lag and lead."""

    def __init__(self, name: str, view: str, d: Data, usd_returns: pd.Series | None) -> None:
        self.name, self.view = name, view
        own_calendar = name == CONTROL
        cal = pd.DatetimeIndex(d.levels[CONTROL].dropna().index) if own_calendar else d.cal
        cal = cal[cal >= START - pd.Timedelta(days=10)]
        index = cal[1:]
        if name == CONTROL:
            ret = simple_returns(d.levels[CONTROL], cal)  # euro listing, no conversion
        elif name == "60/40":
            assert usd_returns is not None
            ret = usd_returns.reindex(index)
        else:
            ret = simple_returns(d.levels[name], cal)
        ff = d.ff.reindex(index)
        if view == "USD":
            rf = ff["RF"]
            mkt = ff["Mkt-RF"]
            xret = ret - rf
            euro = None
            self.leg = macro.daily_leg_returns(d.dollar, cal)
        else:
            noon = view == "EUR-noon"
            f = d.fx_returns(cal, noon)
            c = d.cash(cal)
            # The factors are converted on the French calendar, then read on the subject's rows.
            f_fr = d.fx_returns(d.cal, noon)
            c_fr = d.cash(d.cal)
            conv = convert_factors(d.ff, f_fr, c_fr)
            mkt = conv["Mkt-RF"].reindex(index)
            rf = c.reindex(index)
            if name == CONTROL:
                xret = ret - rf
            else:
                xret = (1.0 + ret) * (1.0 + f.reindex(index)) - 1.0 - rf
            euro = EuroLegs(fx=f.reindex(index), usd_rf=ff["RF"])
            self.leg = f.reindex(index)
        ok = xret.notna() & mkt.notna() & rf.notna() & (index >= START)
        rows = index[ok.to_numpy()]
        sample: Any = SimpleNamespace(
            frequency="daily",
            xret=xret.loc[rows],
            rf=rf.loc[rows],
            factors=pd.DataFrame({"mkt_rf": mkt.loc[rows]}),
            n=len(rows),
        )
        dollar = d.dollar if view == "USD" else None
        design = macro.build_design(sample, cal, d.levels, dollar, euro)
        self.base = design
        # IEF is its own TERM leg and sits inside DEF, so for IEF those two columns are dropped.
        drop = {"term", "def"} if name == "IEF" else set()
        kept = [i for i, c in enumerate(design.codes) if c not in drop]
        self.codes = tuple(design.codes[i] for i in kept)
        self.x = design.x[:, kept]
        leg = self.leg.reindex(index)
        shifts = {
            -2: leg.shift(-2),  # lead 2
            -1: leg.shift(-1),  # lead 1
            1: leg.shift(1),  # lag 1
            2: leg.shift(2),  # lag 2
        }
        self.shifted = {
            k: v.reindex(design.dates).to_numpy(dtype="float64") for k, v in shifts.items()
        }
        self.same = self.x[:, self.codes.index("usd")]
        self.d = d
        self.cal = cal

    # -- fitting ------------------------------------------------------------------------
    def columns(self, spec: str) -> tuple[list[str], np.ndarray]:
        """Regressors of ``spec``: the five macro columns, the same-day dollar, then extras."""
        names = list(self.codes)
        cols = [self.x[:, i] for i in range(len(names))]
        extra: dict[str, np.ndarray] = {
            "lag": self.shifted[1],
            "lead": self.shifted[-1],
        }
        if spec == "no dollar":
            keep = [i for i, c in enumerate(names) if c != "usd"]
            return [names[i] for i in keep], np.column_stack([cols[i] for i in keep])
        for key in ("lag", "lead"):
            if key in spec:
                names.append(key)
                cols.append(extra[key])
        return names, np.column_stack(cols)

    def keep(self) -> np.ndarray:
        """Rows where the same-day, lag and lead dollar terms all exist (common sample)."""
        m = np.isfinite(self.same) & np.isfinite(self.shifted[1]) & np.isfinite(self.shifted[-1])
        return m

    def fit(self, spec: str) -> tuple[list[str], Any, int]:
        """Names, the fit and the row count of ``spec`` on the common sample."""
        keep = self.keep()
        names, x = self.columns(spec)
        return names, ols_hac(self.base.y[keep], x[keep], names=names), int(keep.sum())


def term(fit: Any, names: list[str], key: str) -> tuple[float, float] | None:
    """Coefficient and HAC t of the named regressor (None when absent)."""
    if key not in names:
        return None
    i = 1 + names.index(key)
    return float(fit.params[i]), float(fit.zvalues[i])


def combined(fit: Any, names: list[str], keys: list[str]) -> tuple[float, float]:
    """Sum of the named coefficients and its HAC t (full covariance)."""
    idx = [1 + names.index(k) for k in keys]
    w = np.zeros(len(fit.params))
    w[idx] = 1.0
    b = float(w @ fit.params)
    se = float(np.sqrt(max(w @ fit.cov @ w, 0.0)))
    return b, b / se


def wald_p(fit: Any, names: list[str], keys: list[str]) -> float:
    """Joint test that the named coefficients are zero (HAC covariance, chi-square)."""
    idx = [1 + names.index(k) for k in keys]
    b = fit.params[idx]
    v = fit.cov[np.ix_(idx, idx)]
    stat = float(b @ np.linalg.solve(v, b))
    return float(stats.chi2.sf(stat, len(idx)))


# ------------------------------------------------------------------------------------ output
def fmt(x: float, nd: int = 3) -> str:
    return f"{x:+.{nd}f}"


def cell(t: tuple[float, float] | None, nd: int = 3) -> str:
    if t is None:
        return ""
    star = "*" if abs(t[1]) > T_FLAG else ""
    return f"{fmt(t[0], nd)} ({t[1]:+.1f}){star}"


def table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def span(design: Design) -> str:
    dates = design.base.dates[design.keep()]
    return f"{dates[0]:%Y-%m-%d} to {dates[-1]:%Y-%m-%d}, n={len(dates)}"


def spec_section(designs: dict[tuple[str, str], Design], out: list[str]) -> list[str]:
    out.append("## 1. Lag, lead, both or neither\n")
    out.append(
        "Cell = coefficient (Newey-West t); `*` marks |t| > 2. `same` is the same-day dollar "
        "beta. `sum` adds every dollar term (the beta the app reports). `p(added)` is the joint "
        "Wald test of the added terms. `dR2` is the change of the adjusted R2 against `none`, in "
        "basis points (0.01 of a percentage point of R2 is 1 bp).\n"
    )
    flagged: list[str] = []
    for view in VIEWS:
        rows: list[list[str]] = []
        for sub in (*SUBJECTS, *([CONTROL] if view != "USD" else [])):
            des = designs[(sub, view)]
            fits = {s: des.fit(s) for s in (*SPECS, "no dollar")}
            base_adj = fits["none"][1].rsquared_adj
            for spec in (*SPECS, "no dollar"):
                names, fit, n = fits[spec]
                same = term(fit, names, "usd")
                lag = term(fit, names, "lag")
                lead = term(fit, names, "lead")
                total = None
                keys = [k for k in ("usd", "lag", "lead") if k in names]
                if keys:
                    total = combined(fit, names, keys)
                added = [k for k in ("lag", "lead") if k in names]
                p_add = f"{wald_p(fit, names, added):.3f}" if added else ""
                if lead is not None and abs(lead[1]) > T_FLAG and spec == "lead":
                    flagged.append(f"{view} {sub}: lead t={lead[1]:+.1f}")
                if lag is not None and abs(lag[1]) > T_FLAG and spec == "lag":
                    flagged.append(f"{view} {sub}: lag t={lag[1]:+.1f}")
                rows.append(
                    [
                        sub,
                        spec,
                        str(n),
                        cell(same),
                        cell(lag),
                        cell(lead),
                        cell(total),
                        p_add,
                        f"{fit.rsquared_adj:.4f}",
                        f"{(fit.rsquared_adj - base_adj) * 1e4:+.1f}",
                    ]
                )
        out.append(f"**{view} view**\n")
        out.append(
            table(
                [
                    "subject",
                    "spec",
                    "n",
                    "same",
                    "lag",
                    "lead",
                    "sum",
                    "p(added)",
                    "adjR2",
                    "dR2 bp",
                ],
                rows,
            )
        )
    return flagged


def profile_section(designs: dict[tuple[str, str], Design], out: list[str]) -> None:
    out.append("## 2. Where the dollar effect sits in time\n")
    out.append(
        "One regression per subject with the dollar return of days t+2, t+1 (leads), t, t-1 and "
        "t-2 (lags) next to the other macro factors, on the rows where all five exist. Cell = "
        "coefficient (Newey-West t). `lead share` = lead(1) / (lead(1) + same-day).\n"
    )
    for view in VIEWS:
        rows: list[list[str]] = []
        for sub in (*SUBJECTS, *([CONTROL] if view != "USD" else [])):
            des = designs[(sub, view)]
            keep = np.isfinite(des.same)
            for k in (-2, -1, 1, 2):
                keep &= np.isfinite(des.shifted[k])
            names = [*des.codes, "lead2", "lead1", "lag1", "lag2"]
            x = np.column_stack(
                [des.x, des.shifted[-2], des.shifted[-1], des.shifted[1], des.shifted[2]]
            )
            fit = ols_hac(des.base.y[keep], x[keep], names=names)
            t = {k: term(fit, names, k) for k in ("lead2", "lead1", "usd", "lag1", "lag2")}
            assert t["lead1"] is not None and t["usd"] is not None
            share = t["lead1"][0] / (t["lead1"][0] + t["usd"][0])
            rows.append(
                [sub, str(int(keep.sum()))]
                + [cell(t[k]) for k in ("lead2", "lead1", "usd", "lag1", "lag2")]
                + [f"{share:.0%}" if abs(t["usd"][0]) > 0.05 else "n/a"]
            )
        out.append(f"**{view} view**\n")
        out.append(table(["subject", "n", "t+2", "t+1", "same", "t-1", "t-2", "lead share"], rows))


def timing_section(out: list[str]) -> None:
    out.append("## 3. Close times\n")
    out.append(
        "All times CET. NY = New York (6 hours behind CET; 5 hours in the weeks when the two "
        "regions are on different summer time).\n"
    )
    rows = [
        ["US fund close (SPY, IEF, VGK and EFA as traded in the US)", "16:00 NY = 22:00 CET"],
        ["Xetra close (EXSA.DE)", "17:30 CET"],
        ["Fed broad dollar index, FRED DTWEXBGS", "noon NY = 18:00 CET (H.10 noon buying rates)"],
        ["ECB euro reference rate (the app's EUR source)", "about 14:10 CET"],
    ]
    out.append(table(["event", "time"], rows))
    out.append(
        "Reading. A day-t return measured close to close covers (t-1 close, t close). The dollar "
        "return of day t covers (t-1 fixing, t fixing). The part of the fund's day that falls "
        "after the day-t fixing is the dollar move of the next fixing window, so a fixing that "
        "is earlier than the close puts the missing overlap in the dollar return of day t+1: "
        "a lead. A lag would be right only if the fixing came after the close of the same day. "
        "For the ECB fixing against a US close the fund's day ends 7 hours 50 minutes after the "
        "fixing (about a third of the 24 hours); against a Xetra close it is 3 hours 20 minutes "
        "(about 14%). Against the noon New York index and a US close it is 4 hours (17%).\n"
    )


def fixing_section(designs: dict[tuple[str, str], Design], out: list[str]) -> None:
    out.append("## 4. Does the lead follow the fixing time?\n")
    out.append(
        "Close-time reading predicts that the lead is larger when the dollar fixing is earlier "
        "against the subject's close. Same subjects, three dollar legs: the Fed index (noon "
        "New York, USD view), the ECB rate (14:10 CET, EUR view) and the FRED H.10 euro rate "
        "(noon New York, EUR view with the app's fallback source). Cell = lead coefficient "
        "(t) in the `lead` model, and its share of the lead plus same-day coefficient. Hours "
        "between the fixing and the subject's close: US fund 22:00 CET, EXSA.DE 17:30 CET; "
        "noon New York is 18:00 CET and the ECB fixing 14:10 CET.\n"
    )
    rows: list[list[str]] = []
    for sub in (*SUBJECTS, CONTROL):
        row = [sub]
        for view in VIEWS:
            if (sub, view) not in designs:
                row.append("")
                continue
            names, fit, _ = designs[(sub, view)].fit("lead")
            lead = term(fit, names, "lead")
            same = term(fit, names, "usd")
            assert lead is not None and same is not None
            share = lead[0] / (lead[0] + same[0]) if abs(same[0]) > 0.05 else float("nan")
            row.append(f"{cell(lead)}; {share:.0%}" if share == share else cell(lead))
        rows.append(row)
    out.append(
        table(
            ["subject", "USD: Fed index, noon NY", "EUR: ECB, 14:10 CET", "EUR: H.10, noon NY"],
            rows,
        )
    )


def fresh_section(out: list[str]) -> None:
    out.append("## 5. Freshness\n")
    today = datetime.now(UTC).date()
    rows = []
    for series, last in FRESH:
        rows.append([series, last, str((today - date.fromisoformat(last)).days)])
    out.append(f"Today: {today}.\n")
    out.append(table(["series", "last observation", "calendar days old"], rows))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--out", type=Path, default=None, help="also write the tables to this file")
    args = ap.parse_args()

    d = Data(args.data_dir)
    mix = sixty_forty(d)
    designs: dict[tuple[str, str], Design] = {}
    for view in VIEWS:
        for sub in (*SUBJECTS, CONTROL):
            if sub == CONTROL and view == "USD":
                continue
            designs[(sub, view)] = Design(sub, view, d, mix)

    out: list[str] = ["## 0. Data and samples\n"]
    out += [f"- {n}" for n in NOTES]
    for (sub, view), des in designs.items():
        out.append(f"- {view} {sub}: common sample {span(des)}.")
    out.append("")
    flagged = spec_section(designs, out)
    out.append("Single-term |t| > 2: " + ("; ".join(flagged) if flagged else "none") + "\n")
    profile_section(designs, out)
    timing_section(out)
    fixing_section(designs, out)
    fresh_section(out)
    text = "\n".join(out)
    print(text)
    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
