# NSE Trading Agent

A deterministic, chronology-safe research system for NSE index, futures, and cash-equity strategies. This is research software—not a live trading system or a claim of profitability.

## Research status

| Version | Status | Conclusion |
|---|---|---|
| V1 | Frozen; holdout consumed | Simple SMA selection failed its reserved holdout |
| V2 | Frozen development baseline | Trend-Momentum reduced exposure but lagged buy-and-hold |
| V3 Step 1 | Frozen checkpoint | Continuous capital captured little of the benchmark |
| V3 Step 2 | Frozen checkpoint | Real futures execution had weak reward relative to risk |
| V3 Step 3 | Frozen limited checkpoint | BANKNIFTY generalized weakly; paper foundations added |
| V3 Step 4 | Frozen negative checkpoint | Adjusted 10-stock portfolio lost money and underperformed |
| V3 Step 5 | Frozen limited negative current-snapshot checkpoint | 105 symbols acquired; 94 pass history/liquidity gates |
| V3 Step 6 | Frozen retirement checkpoint | Dynamic cohorts confirm benchmark failure; retirement rule triggered |
| V4 Step 1 | Frozen limited inconclusive checkpoint | Monthly 12−1 relative strength passes 4/5 pillars; not promotable or retired |
| V4 Step 2 | Frozen promoted development baseline | Fixed NIFTY 200-SMA overlay passes all 5 promotion pillars |
| V4 Step 3 | Active paper-readiness infrastructure | ₹1 lakh broker-neutral workflow with deterministic evidence generation; prospective observation not yet started |

Frozen V1/V2 parameters and evidence must not be revised in response to later results. Reserved holdouts remain untouched until a version is explicitly ready for one-time evaluation.

## Current strategy

The frozen V2 signal policy is long-only Trend-Momentum:

- SMA 20/50, RSI 14, MACD 12/26/9, and ATR 14
- configurable 2× entry-ATR stop
- signal after the daily close; execution at the next available open
- no indicator optimization in V3 generalization experiments

V3 changes data, instruments, capital continuity, portfolio construction, and execution realism without rewriting this signal policy.

## Latest development evidence

V3 Step 4 uses ten liquid NIFTY 50 stocks, one shared ₹10,00,000 account, at most five positions, and a reserved 250-session tail beginning 2025-09-01.

| Metric | Result |
|---|---:|
| Strategy P&L / return | **−₹70,833.50 / −7.08%** |
| Maximum drawdown | ₹99,412.50 |
| Completed trades / win rate | 34 / 23.53% |
| Accepted symbol-windows | 30 / 280 |
| Equal-capital benchmark P&L | **₹10,36,786.25** |
| Excess P&L | **−₹11,07,619.75** |

This is negative development evidence and must not be optimized away. The 2026-09-04 membership snapshot is applied retrospectively, so survivorship bias remains. The reserved tail was not evaluated.

V3 Step 5 replaces the flat fee proxy with component-level delivery charges and
adds strict point-in-time membership controls. Official bhavcopies cover all 105
unique symbols in the current three-index snapshot; 94 pass the declared history
and liquidity gates. Historical membership snapshots remain unavailable, so Step 5
is frozen only as a limited negative research/infrastructure checkpoint—not as
profitable evidence, a survivorship-free comparison, deployment approval, or
permission to use holdouts.

V3 Step 6 removes the all-symbol intersection-calendar distortion. Fixed-period
dynamic cohorts retain each exchange session and evaluate symbols only when their
own data, training, liquidity, and declared membership mode allow it. The unchanged
Trend-Momentum policy remains profitable in some development cohorts but fails the
predeclared benchmark-capture and drawdown retirement pillars. No reserved equity
session from 2025-09-01 onward was evaluated.

V4 begins a genuinely new cross-sectional hypothesis rather than tuning retired
Trend-Momentum. Step 1 ranks positive 12-minus-1-month momentum monthly and holds
up to ten equal-target-weight stocks. It is profitable across all three development
cohorts and beats passive in two, but its 36.21% long-history drawdown exceeds the
predeclared 20% promotion ceiling. With one failed pillar, it is neither promoted
nor retired at this checkpoint.

V4 Step 2 adds only the predeclared NIFTY 50 200-session SMA month-end regime
overlay. It reduces long-history drawdown to 19.76% while retaining positive fixed-
cohort and doubled-cost results, so it passes all five development promotion
pillars. Promotion means eligible for later staged evaluation—not deployment or
permission to consume any reserve now.

V4 trades whole shares of constituent cash stocks drawn from NIFTY 50, NIFTY
Next 50, and BANKNIFTY membership. It does not trade an index, index future, or
option; NIFTY 50 index prices are regime and benchmark inputs only. Step 3 adds a
dry-run-first, restart-safe local paper workflow with default ₹1,00,000 capital and
₹10,000 fixed targets. This is readiness infrastructure, not prospective profit
evidence or deployment approval.

## Repository guide

| Location | Contents |
|---|---|
| [`src/trading_agent/`](src/trading_agent/) | Domain models, signals, data, execution, and research engines |
| [`scripts/README.md`](scripts/README.md) | Download, validation, comparison, and reproduction commands |
| [`data/README.md`](data/README.md) | Dataset layout, provenance, schemas, and adjustment policy |
| [`logs/README.md`](logs/README.md) | Version snapshots, results, definitions, and frozen-state rules |
| [`tests/`](tests/) | Unit and integration tests, including chronology and restart safety |

## Source layout

```text
src/trading_agent/
├── core/       # configuration and domain models
├── signals/    # indicators, features, and signal policies
├── data/       # typed loaders and NSE clients
├── execution/  # futures accounting and paper execution
├── research/   # backtests, walk-forward, and portfolio studies
└── main.py     # baseline reporting
```

## Quick start

```bash
uv run pytest -q
uv run trading-agent
```

Dataset preparation and V3 commands are in [`scripts/README.md`](scripts/README.md).

## Research rules

- Never use future candles, later membership snapshots, or holdout results during selection.
- Close signals execute no earlier than the next available open.
- Report costs, adverse slippage, drawdown, exposure, turnover, rejected orders, and a matching benchmark.
- Keep raw source data separate from adjusted data.
- Never present development, survivorship-biased, or paper results as live evidence.
- Material changes require a new version and log.
- No live broker adapter or credentials are enabled.

## Abbreviations

| Term | Meaning |
|---|---|
| ATR | Average True Range |
| DD | Drawdown |
| EMA | Exponential Moving Average |
| F&O | Futures and Options |
| MACD | Moving Average Convergence Divergence |
| MTM | Mark-to-Market |
| NSE | National Stock Exchange of India |
| OHLCV | Open, High, Low, Close, and Volume |
| OOS | Out-of-Sample |
| P&L | Profit and Loss |
| PIT | Point in Time |
| RSI | Relative Strength Index |
| RS | Relative Strength |
| SEBI | Securities and Exchange Board of India |
| SMA | Simple Moving Average |
| STT | Securities Transaction Tax |
| 12−1 | 252-session momentum excluding the latest 21 sessions |

Metric definitions are in [`logs/README.md`](logs/README.md).

## Risk context

SEBI reported that 93% of individual traders in the overall Indian equity F&O segment lost money during FY22–FY24. This is not a NIFTY-only statistic. See the [SEBI September 2024 release](https://www.sebi.gov.in/media-and-notifications/press-releases/sep-2024/updated-sebi-study-reveals-93-of-individual-traders-incurred-losses-in-equity-fando-between-fy22-and-fy24-aggregate-losses-exceed-1-8-lakh-crores-over-three-years_86906.html).
