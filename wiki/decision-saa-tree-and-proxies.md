# Decision: SAA tree and default proxies

Date: 2026-11-19
Status: Decided

## In one sentence

Portfolios are built in a three-level tree (asset class, sub-asset class, ETF) that starts from a prefilled template of US-listed proxy ETFs, and alternatives stay out of version 1.

## What we decided

- The tree mirrors the layout of the Venn and Risk Pro SAA editors.
- The depth is fixed: asset class, then sub-asset class, then ETF. Cash is a leaf too.
- The tree starts from a prefilled template. Users can add, rename, delete or swap rows.
- Each sub-asset class starts at 0%.
- A portfolio holds between 1 and 50 holdings.
- The same ETF may appear in two sleeves. This is our call, flagged for the owner to check.
- Alternatives are hidden in version 1, because no proxies have been settled for them.

## Why

- The three levels match the editors that users already know.
- A prefilled template gives a working portfolio before the user sets anything up.
- The proxies are US-listed ETFs with long histories, so the backtest can start early.
- Alternatives wait until their proxies are researched.

## Default proxy table (draft, to be validated in epic E5)

| Asset class | Sub-asset class: proxy ETF |
|---|---|
| Cash | USD T-bill (French risk-free rate) |
| Bonds | Global: BWX. Europe: IGOV (to be decided). USA: AGG. USA Treasury: IEF. USA Corporate: LQD. High Yield: HYG. Emerging: EMB |
| Equities | Europe: IEV or EZU. USA: IVV. APAC: EPP and EWJ. Emerging: EEM. Thematic: QQQ. Global: ACWI |
| Commodities | Gold: GLD. Diversified: DBC |
| Alternatives | Hidden in version 1. Proxies still to be researched |

- ACWI (from March 2008) and EMB (from December 2007) set the common start date when they are held. The interface says so.
- IGOV is a placeholder for the Europe bonds slot. No US-listed euro government ETF with a long history has been found.
- Each ETF's inception date and history still need checking. This is an open item for epic E5.

## What it costs us

- A proxy is not the same as its asset class. A Treasury fund is an imperfect stand-in for a whole bond sleeve.
- A short ETF history shortens the backtest for the whole portfolio.
- The Europe bonds slot has a weak proxy, so that sleeve is the least reliable part of the template.
- The template is a draft until E5 validates it, so the default numbers may change.

## What would change our mind

- If a long-history euro government bond ETF is found on a US exchange, we replace IGOV.
- If alternatives proxies are researched, we open that tier in a later release.
- If euro-based users become a priority, UCITS ETFs replace US-listed proxies, with the European mode.

## Sources

- [Next-stage spec](../docs/specs/next-stage-track-record-and-portfolio.md): tree design, draft default proxy template, and the owner's deferred list.
- [Next-stage research](../docs/research/next-stage-research.md): sections B6 and the open verification items.

## Related decisions

- [Portfolio backtest rules](decision-portfolio-backtest-rules.md)
- [USD only in version 1](decision-usd-only-v1-portfolios.md)
- [European mode, regional factors and currency](decision-european-mode-and-currency.md)
