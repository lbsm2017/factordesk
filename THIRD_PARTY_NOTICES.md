# Third-party notices

factordesk's own code is under the [factordesk Noncommercial License 1.0](LICENSE). The built package (the wheel) also ships
a compiled dashboard page and font files made by others. Their licences and notices are below.
Libraries that are only installed as dependencies (pandas, FastAPI and the rest) keep their own
licence files in their own packages; the full list with versions is in
[docs/references.md](docs/references.md#software).

## Code bundled into the dashboard page

| Package | Version | Licence | Copyright |
| --- | --- | --- | --- |
| [Apache ECharts](https://echarts.apache.org/) | 6.1.0 | Apache-2.0 | The Apache Software Foundation |
| [ZRender](https://github.com/ecomfe/zrender) | 6.1.0 | BSD-3-Clause | Baidu Inc. |
| [React and React DOM](https://react.dev/) | 19.3.1 | MIT | Meta Platforms, Inc. and affiliates |
| [scheduler](https://github.com/facebook/react) | 0.28.0 | MIT | Meta Platforms, Inc. and affiliates |
| [TanStack Query](https://tanstack.com/query) | 5.108.0 | MIT | Tanner Linsley |
| [Downshift](https://github.com/downshift-js/downshift) | 9.5.0 | MIT | PayPal |
| [compute-scroll-into-view](https://github.com/scroll-into-view/compute-scroll-into-view) | 3.2.2 | MIT | Cody Olsen |
| [prop-types](https://github.com/facebook/prop-types), react-is | 15.8.1, 18.3.1 | MIT | Meta Platforms, Inc. and affiliates |
| [@babel/runtime](https://babel.dev/) | 7.29.14 | MIT | Sebastian McKenzie and other contributors |
| [tslib](https://github.com/microsoft/tslib) | 2.9.1 | 0BSD | Microsoft Corporation |

The full licence texts are in each package's folder under `frontend/node_modules/` after
`npm --prefix frontend ci`, and at the links above.

The NOTICE file of Apache ECharts reads:

```text
Apache ECharts
Copyright 2017-2026 The Apache Software Foundation

This product includes software developed at
The Apache Software Foundation (https://www.apache.org/).
```

## Fonts

All fonts are under the [SIL Open Font License 1.1](https://openfontlicense.org/). The licence text
sits next to each font file.

| Font | Where | Copyright |
| --- | --- | --- |
| IBM Plex Sans | `frontend/src/assets/fonts/`, `docs/design/prototype/fonts/` | IBM Corp., Reserved Font Name "Plex" |
| Instrument Sans | `backend/factordesk/report/fonts/`, `docs/design/prototype/fonts/` | The Instrument Sans Project Authors |
| STIX Two | `backend/factordesk/report/fonts/`, `docs/design/prototype/fonts/` | The STIX Fonts Project Authors |

## Cited works

`docs/research/causal_factor_investing_agent_kb.md` is the project owner's own study notes on
López de Prado (2023), *Causal Factor Investing* (Cambridge University Press, open access under
[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)). The book is cited as a source for
scientific rigour. None of factordesk's algorithms are taken from it, and the ideas attributed to
the book remain its author's.

## Data

No market or factor data is stored in this repository or in the package. factordesk downloads data
on your machine at run time, and that data stays under each provider's terms. See
[Data sources and their terms](wiki/guide-data-sources.md).
