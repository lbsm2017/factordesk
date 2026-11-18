# Decisions log

This is the earlier flat list. The per-decision pages are linked from [index.md](index.md) and give the reasoning; this page is kept for history.

Each entry is dated 2026-11-18.

- 2026-11-18: Stack is FastAPI (Python backend), Vite + React + TypeScript frontend, and Apache ECharts for charts (`docs/PLAN.md`, Context).
- 2026-11-18: v1 prices come from yfinance only. Alpaca is a stub: placeholder keys in `.env.example` and `.env`, no adapter calls (`docs/PLAN.md`, Context).
- 2026-11-18: Python 3.12 is provisioned with uv, which needs no admin rights. System Python was not installed (`docs/PLAN.md`, Environment findings).
- 2026-11-18: The wiki lives in `wiki/` inside the project repo (`docs/PLAN.md`, Needs your approval).
- 2026-11-18: Deferred to later sprints: peer comparison (next), factor-mimicking hedge, CAPM/FF3/FF5/+MOM model comparison, portfolio mode, screener, out-of-sample stability score (`docs/PLAN.md`, Deferred). Alpaca live adapter, Carhart momentum toggle, watchlist and CSV/PDF export are in the Next horizon (`docs/PLAN.md`, Roadmap).
