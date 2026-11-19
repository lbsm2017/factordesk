# Decision: USD only in version 1

Date: 2026-11-19
Status: Decided

## In one sentence

Version 1 works only in US dollars, uses US-listed proxy ETFs for portfolios, and earns the French risk-free rate on cash, while a euro base and UCITS funds wait for a later European mode.

## What we decided

- Currency is USD only in version 1. Inputs in other currencies are not supported.
- Portfolios use US-listed proxy ETFs. Cash earns the French daily risk-free rate.
- Track-record uploads assume USD.
- EUR/USD appears only as a macro sensitivity. It measures euro exposure for a USD-based investor. It does not make a portfolio euro-based.
- A euro base currency and UCITS ETFs come later, with the European mode. The mode is proposed in [European mode, regional factors and currency](decision-european-mode-and-currency.md). This decision sets the timing and does not replace that proposal.
- The owner made this call on 2026-11-19.

## Why

- One currency keeps the first releases easy to check against the source data.
- US-listed proxies have long histories, which the proxy table depends on.
- The sources record the decision, not a longer argument. The owner placed the euro base and UCITS work in a later release.

## How it works

- Each portfolio return is a USD return. Cash earns the French daily risk-free rate, divided by 100.
- Factor regressions use the US factor set that the Ken French library publishes for US tickers.
- The European file route and the currency conversion step stay in the European mode proposal until that mode is approved.

## What it costs us

- A euro-based investor sees dollar returns, not euro returns.
- US-listed proxies may not match what a European investor can buy.
- No long-history US-listed euro government bond ETF was found. The bonds Europe slot is a placeholder.
- The EUR/USD macro factor is spot only and has no interest-rate carry.
- Users with euro holdings must wait for the European mode.

## What would change our mind

- If euro-based users become a priority, the European mode and UCITS proxies move up the roadmap.
- If the European mode is approved with a different currency rule, this page is updated to match.
- If a long-history US-listed euro bond ETF appears, the Europe bonds proxy is revisited.

## Sources

- [Next-stage spec](../docs/specs/next-stage-track-record-and-portfolio.md): owner decisions on currency, the deferred list, and the release plan (R5 and later).
- [Next-stage research](../docs/research/next-stage-research.md): section C3 on EUR/USD, and section C5 on prior art.

## Related decisions

- [European mode, regional factors and currency](decision-european-mode-and-currency.md)
- [SAA tree and proxies](decision-saa-tree-and-proxies.md)
- [Portfolio backtest rules](decision-portfolio-backtest-rules.md)
- [Factor models and macro](decision-factor-models-and-macro.md)
