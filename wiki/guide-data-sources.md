# Data sources and their terms

Last updated 2026-11-28. Where factordesk's data comes from, what each source is used for, and the terms that apply to it.

factordesk's **code** is under the [factordesk Noncommercial License](../LICENSE). The **data** it
downloads is not covered by that licence: it stays under each provider's terms, and you are
responsible for following them when you run factordesk. No data is stored in this repository;
everything is downloaded to your own machine at run time
([decision](decision-no-data-and-no-secrets-in-the-repo.md)).

| Source | Used for | Terms in short |
| --- | --- | --- |
| [Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) | Every factor return and the risk-free rate: US and Developed Europe five factors and momentum, and the portfolio files behind the shrunk-beta prior | The page carries a copyright notice by Eugene F. Fama and Kenneth R. French; no terms page was found on 2026-11-18. Please credit them. |
| Yahoo Finance, through [yfinance](https://ranaroussi.github.io/yfinance/) | Daily prices, dividends and splits of the analysed ticker, of every portfolio proxy and of the ACWI, IEUR, IEF, LQD, DBC, TIP, IEI, KRBN and FXF ETFs; name, exchange and currency | Yahoo's terms forbid commercial use and collecting data by automated means without permission, and the yfinance README says the API is "intended for personal use only". factordesk obtains no permission from Yahoo for you, so use it for personal research. |
| [FRED](https://fred.stlouisfed.org/legal/), Federal Reserve Bank of St. Louis | The broad US dollar index, Brent crude and Henry Hub gas (from the U.S. Energy Information Administration), and fallback exchange and €STR rates | The series used are marked "Public Domain: Citation Requested". Free to use; cite the source and that it was accessed via FRED. |
| [ECB Data Portal](https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html) | Euro reference exchange rates, €STR and EONIA | Free to reuse, also commercially, if the source is quoted ("Source: ECB statistics"). |
| [Swiss National Bank data portal](https://www.snb.ch/en/srv/disclaimer_copyright) | SARON, for Swiss franc cash | Non-commercial use. SARON is licensed by SIX Index Ltd; commercial use needs a SIX licence. |

The wording of each source is quoted and dated in [docs/references.md](../docs/references.md).
How each file is cached and refreshed is in
[Install and use factordesk](guide-install-and-use.md#factor-data).

factordesk is not affiliated with, endorsed by or vetted by Yahoo, the yfinance project, iShares,
MSCI, Dartmouth College, Kenneth R. French, Eugene F. Fama, the Federal Reserve, the U.S. Energy
Information Administration, the European Central Bank, the Swiss National Bank or SIX
([decision](decision-project-name-factordesk.md)).
