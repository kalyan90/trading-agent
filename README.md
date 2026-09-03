# NSE Trading Agent

A deterministic research backtester for daily NIFTY 50 market data. It contains a frozen V1 baseline and a separately frozen V2 Trend-Momentum strategy.

## Current research status

- V1 is frozen and its final holdout has already been consumed. Do not tune V1 or rerun that holdout as if it were unbiased.
- V2 is evaluated only on development walk-forward windows.
- No parameter optimization is performed for V2.
- The legacy `--final-holdout` option is retained for compatibility but refuses to rerun the consumed V1 holdout.
- V3 Step 1 is a frozen continuous-portfolio checkpoint of the V2 signal policy.
- V3 Step 2 now executes that unchanged spot-derived policy against actual dated NIFTY futures contracts. It remains development research, not a deployment model.

## V1: deterministic baseline

### Objective and scope

V1 established the minimum trustworthy research pipeline before introducing richer indicators or AI components. It tested whether simple SMA strategies could generalize through chronological walk-forward evaluation after costs and adverse execution assumptions.

V1 trades one abstract NIFTY index unit. It is a signal-research model, not yet a directly tradable NIFTY futures, ETF, or options implementation. Backtest profitability must not be interpreted as live profitability evidence.

### Research progression

1. The initial SMA backtester was converted to close-signal/next-open execution to prevent same-candle lookahead.
2. Chronological 120/40 walk-forward windows replaced a single in-sample result.
3. Candidate selection compared raw training P&L with training P&L divided by drawdown.
4. Acceptance policies were evaluated conservatively. The baseline gate—positive training P&L and at least five completed trades—was retained instead of mining thresholds.
5. Accounting was corrected so `total_profit` means realized closed-trade P&L while `total_pnl` includes a final open position marked to market. Selection, acceptance, and reporting use `total_pnl`.
6. Capital, position size, transaction cost, absolute adverse slippage, exposure, drawdown, and a matching buy-and-hold benchmark were added before V1 was frozen.
7. Slippage sensitivity was measured at 0, 5, and 10 points using the full selection and acceptance pipeline—not by subtracting costs after the fact.
8. The risk-adjusted selector and five-point slippage model were frozen before the reserved holdout was opened.
9. The one-time final holdout failed. V1 was retained unchanged as the historical baseline.

### Frozen V1 metadata

| Field | Frozen value | Definition |
|---|---:|---|
| Candidate strategies | SMA Basic, SMA Crossover | Long-only deterministic SMA rules |
| Candidate SMA periods | 3, 10, 20, 30, 50 | Training-only candidate search space |
| Selector | Risk-adjusted | Highest training P&L divided by maximum drawdown |
| Acceptance gate | P&L > ₹0 and ≥5 completed trades | Both conditions evaluated on training data |
| Training window | 120 candles | Rolling historical training segment |
| Test window | 40 candles | Following non-overlapping OOS segment |
| Reserved holdout | 250 candles | One-time final evaluation segment, now consumed |
| Development dates | 2020-01-01 to 2025-08-29 | Data used for V1 research and freezing |
| Holdout dates | 2025-09-01 to 2026-09-02 | Previously unseen data used once for final V1 evaluation |
| Initial capital | ₹100,000 | Independently reset for each backtest window |
| Position size | 1 | One abstract index unit |
| Transaction cost | ₹20 | Round-trip cost split across entry and exit |
| Slippage | 5 points | Buy open +5; sell open −5 |
| Forced liquidation | False | Final open positions are marked to market |

### V1 development evidence

The final development comparison used 32 windows. The P&L selector produced greater absolute OOS P&L, while the already frozen risk selector accepted fewer windows and produced slightly lower drawdown. Both materially underperformed their matching benchmarks.

| Metric | P&L selector | Frozen risk selector |
|---|---:|---:|
| Accepted windows | 9 | 6 |
| Rejected windows | 23 | 26 |
| Total OOS P&L | ₹2,252.10 | ₹1,363.35 |
| Average OOS P&L | ₹250.23 | ₹227.22 |
| Average OOS return | 0.25% | 0.23% |
| Profitable windows | 5/9 | 4/6 |
| Completed OOS trades | 29 | 18 |
| Average win rate | 28.70% | 41.67% |
| Average drawdown | ₹736.62 | ₹708.93 |
| Average exposure | 59.44% | 59.17% |
| Benchmark P&L | ₹5,402.10 | ₹2,873.65 |
| Excess P&L | −₹3,150.00 | −₹1,510.30 |
| Benchmark beat rate | 33.33% | 33.33% |

### V1 slippage sensitivity

This earlier development experiment used the P&L-selected baseline and showed that the apparent edge survived simulated friction but degraded substantially. Slippage also changed training selection and acceptance, so the effect was not merely an after-the-fact cost deduction.

| Absolute slippage | Accepted windows | Strategy OOS P&L | Benchmark P&L | Excess P&L | Benchmark beat rate |
|---:|---:|---:|---:|---:|---:|
| 0 points | 9 | ₹2,572.10 | ₹5,447.10 | −₹2,875.00 | 33.33% |
| 5 points | 9 | ₹2,252.10 | ₹5,402.10 | −₹3,150.00 | 33.33% |
| 10 points | 8 | ₹1,275.80 | ₹3,817.80 | −₹2,542.00 | 37.50% |

Relative to zero slippage, OOS P&L fell by ₹320 at five points and ₹1,296.30 at ten points. Evidence across the friction experiments favored the risk-adjusted selector’s robustness, which is why it was frozen even though the final apples-to-apples development summary later showed higher absolute P&L for the raw-P&L selector.

### V1 final holdout result

The holdout contained seven chronological windows. Only two passed the frozen training gate.

| Metric | Frozen V1 result |
|---|---:|
| Accepted / rejected windows | 2 / 5 |
| Total OOS P&L | **−₹362.45** |
| Average OOS P&L | −₹181.22 |
| Average OOS return | −0.18% |
| Profitable windows | 1/2 |
| Completed OOS trades | 6 |
| Average closed-trade win rate | 0.00% |
| Average drawdown | ₹889.45 |
| Average exposure | 65.00% |
| Benchmark P&L | **₹1,633.60** |
| Excess P&L | **−₹1,996.05** |
| Benchmark beat rate | **0.00%** |

The profitable-window count and zero closed-trade win rate are compatible: with forced liquidation disabled, an open position can finish a window with positive marked-to-market P&L without recording a winning closed trade.

**V1 conclusion:** the SMA baseline was profitable during development but failed its reserved holdout and lost to buy-and-hold in every accepted holdout window. Its holdout is consumed; V1 must not be tuned and rerun as though the same period were unseen.

## V2 metadata

| Field | Fixed value | Definition |
|---|---:|---|
| Strategy | Trend-Momentum | Long-only deterministic signal policy |
| Fast SMA | 20 candles | Shorter trend average |
| Slow SMA | 50 candles | Longer trend average and indicator warm-up |
| RSI | 14 candles | Momentum filter |
| MACD | 12/26/9 | Fast EMA, slow EMA, and signal EMA periods |
| ATR | 14 candles | Volatility measurement used by the fixed risk stop |
| ATR stop | 2 × entry ATR | Close-based risk exit, executed at the following open |
| Training window | 250 candles | Historical observations used for the train gate |
| Test window | 40 candles | Subsequent out-of-sample observations |
| Acceptance gate | P&L > ₹0 and ≥5 completed trades | Both conditions must pass using training data only |
| Initial capital | ₹100,000 | Starting cash for each independent backtest |
| Position size | 1 | One index unit while invested |
| Transaction cost | ₹20 | Round-trip cost, split equally across entry and exit |
| Slippage | 5 points | Absolute adverse movement: +5 on buys and −5 on sells |
| Forced liquidation | False | Final open positions are marked to market |
| Optimization | None | The fixed strategy is run once per window |

## V2 frozen-state snapshot

**Status:** complete and frozen as the deterministic Trend-Momentum baseline. V2 may be reproduced, but changing its strategy, parameters, gate, execution model, or window definitions creates a new version.

**Evaluation scope:** development-only walk-forward research over data through 2025-08-29. V2 has no pristine final holdout. The period used for V1's final holdout was already known when V2 was designed and therefore cannot provide unbiased V2 evidence.

| Frozen V2 result | Value |
|---|---:|
| Total development windows | 28 |
| Accepted / rejected windows | 6 / 22 |
| Positive-P&L training windows | 18 |
| Training windows with ≥5 trades | 12 |
| Total OOS P&L | ₹584.60 |
| Average OOS P&L | ₹97.43 |
| Average OOS return | 0.10% |
| Profitable accepted windows | 4/6 |
| Profitable-window rate | 66.67% |
| Completed OOS trades | 7 |
| Average closed-trade win rate | 50.00% |
| Average drawdown | ₹294.89 |
| Average P&L/DD | 1.18 |
| Average exposure | 32.50% |
| Matching benchmark P&L | ₹4,027.30 |
| Excess P&L | −₹3,442.70 |
| Benchmark beat rate | 16.67% |
| Training ATR-stop signals | 5 |
| Accepted OOS ATR-stop signals | 0 |

**V2 conclusion:** V2 improved win rate, drawdown, risk-adjusted P&L, and exposure relative to V1's development result, but produced lower absolute P&L and weaker benchmark-relative performance. Its ATR rule did not activate in accepted OOS windows. V2 is a useful low-exposure research baseline, not evidence of a deployable profitable strategy.

## Signal definitions

- **Buy:** fast SMA is above slow SMA, MACD is above its signal line, and RSI is greater than 50 but less than 70.
- **Sell:** fast SMA falls below slow SMA, or MACD falls below its signal line.
- **Risk exit:** while invested, a close at or below the entry execution price minus two times the ATR known when the entry signal was created schedules a sell for the next open.
- **Hold:** indicators are warming up or neither entry nor exit condition is satisfied.
- A signal is calculated after the current candle closes and can execute only at the next candle's open. Future candles are never included in feature calculation.

## Measurement definitions

- **Completed trade:** one executed entry and its corresponding executed exit. The five-trade gate means five completed round trips, not five signals or five individual orders.
- **Training P&L:** ending portfolio equity minus initial capital, including a marked-to-market open position.
- **OOS P&L:** P&L from an accepted window's test segment only.
- **Exposure:** percentage of eligible bars during which the portfolio holds a position.
- **Benchmark:** buy one unit at the first eligible open and mark it to market over the same evaluation period, using the same costs and slippage.
- **Rejected window:** a window whose training result fails either acceptance condition. Its test segment is not evaluated.
- **ATR stop signal:** a risk exit scheduled by the fixed ATR threshold. Diagnostics report these separately from ordinary trend or momentum exits.

## Abbreviations

| Abbreviation | Meaning |
|---|---|
| ATR | Average True Range |
| DD | Drawdown |
| EMA | Exponential Moving Average |
| ETF | Exchange-Traded Fund |
| MACD | Moving Average Convergence Divergence |
| MTM | Mark-to-Market |
| NSE | National Stock Exchange of India |
| OOS | Out-of-Sample |
| P&L | Profit and Loss |
| RSI | Relative Strength Index |
| SMA | Simple Moving Average |
| FO | Futures and Options |
| SPAN | Standard Portfolio Analysis of Risk |

## Usage

```bash
uv run pytest -q
uv run trading-agent
```

The second command runs the development comparison and prints V2 training diagnostics. It does not consume a new holdout.

## Source layout

The Python package is grouped by responsibility so later V3 work does not turn the package root into a flat collection of unrelated modules:

```text
src/trading_agent/
├── core/       # frozen configuration and domain models
├── signals/    # indicators, feature construction, and signal policies
├── data/       # local CSV loading and the NSE historical-data client
├── execution/  # futures cash, settlement, and margin accounting
├── research/   # backtests, walk-forward experiments, and V3 evaluations
└── main.py     # command-line reporting only
```

Future broker and paper-trading adapters belong in `execution/` beside the broker-independent account model. They should not be mixed into deterministic signal or research code.

## Research logs

Research output is versioned so historical evidence remains separate from later strategy development:

```text
logs/
├── v1/
│   ├── early SMA and in-sample experiments
│   ├── walk-forward and accounting iterations
│   ├── selector, acceptance, slippage, and benchmark experiments
│   ├── experiment-v1-logs.txt
│   └── experiment-v1-final-holdout-logs.txt
├── v2/
│   └── experiment-v2-development.txt
└── v3/
    ├── experiment-v3-step1-continuous.txt
    └── experiment-v3-step2-futures.txt
```

- `logs/v1/` is the preserved V1 research trail, including the one-time consumed holdout output. These files are historical records and must not be regenerated to claim new evidence.
- `logs/v2/experiment-v2-development.txt` is the reproducible development comparison generated from the completed V2 implementation. It contains V1 development metrics for comparison, V2 metrics, train-gate diagnostics, and ATR-stop activation counts.
- V2 currently has no pristine final-holdout log. Creating one would require genuinely untouched future data or a separately reserved dataset.
- `logs/v3/experiment-v3-step1-continuous.txt` records the first continuous-portfolio development evaluation without changing the frozen V2 log.

To refresh the V2 development record after a reproducibility-only run:

```bash
uv run trading-agent | tee logs/v2/experiment-v2-development.txt
```

Do not use that command after changing frozen V2. A material strategy or evaluation change belongs to a new version and a new log file.

## Version conclusions

- **V1:** completed and frozen after failing its consumed final holdout. It remains the historical baseline.
- **V2:** completed and frozen as a deterministic Trend-Momentum strategy with an ATR risk exit. Its reported results are development evidence, not pristine holdout evidence.
- **V3 Step 1:** carries one portfolio across chronological test windows. Accepted adjacent windows preserve positions and pending signals; entry is disabled in rejected windows, and an existing position is liquidated at the first rejected-window open using normal costs and slippage.
- Later V3 steps may introduce realistic tradable contract sizing, paper trading, regime classification, or an AI decision layer. Those changes must remain separate from frozen V1 and V2.

## V3 continuous-evaluation policy

- Every 40-candle decision window is gated using only its preceding 250 candles.
- Cash, positions, entry ATR, pending actions, and equity persist across adjacent accepted windows.
- When a rejected window begins, any open position is sold at that first open with five-point adverse slippage and the normal exit cost.
- No signals or entries are produced inside rejected windows.
- The benchmark buys one unit at the first evaluation open and remains invested through the same complete continuous period.
- This is development research. It is not a new holdout and does not revise the frozen V2 result.

## V3 Step 1 frozen-state snapshot

**Status:** frozen research checkpoint. This freezes the continuous-evaluation policy and its result, not the whole V3 program. Later V3 work must be labeled Step 2 or a new version and must write a separate log.

**Signal policy:** the frozen V2 Trend-Momentum strategy and parameters are reused unchanged. V3 Step 1 changes only portfolio continuity and rejected-window handling.

| Frozen V3 Step 1 result | Value |
|---|---:|
| Total decision windows | 28 |
| Accepted / rejected windows | 6 / 22 |
| Continuous starting capital | ₹100,000 |
| Continuous final equity | ₹100,634.55 |
| Continuous P&L | ₹634.55 |
| Continuous return | 0.63% |
| Completed trades | 8 |
| Gate-forced liquidations | 1 |
| Maximum drawdown | ₹1,094.45 |
| Exposure | 6.96% |
| Continuous benchmark P&L | ₹11,465.10 |
| Excess P&L | −₹10,830.55 |

**V3 Step 1 conclusion:** carrying one portfolio removes the misleading implication that each test window starts with fresh capital and no prior state. The strategy remained profitable in development with very low exposure, but its drawdown exceeded the reset-window V2 average and it captured only a small fraction of the continuous benchmark's gain. This checkpoint does not justify deployment or parameter tuning.

## V3 Step 2: instrument specification

V3 Step 2 begins the transition from an abstract one-unit index model to an explicit tradable-instrument model. The contract metadata is intentionally separate from signals and portfolio evaluation.

| Field | Current snapshot |
|---|---:|
| Instrument | NIFTY 50 index futures |
| Exchange symbol | NIFTY |
| Market lot | 65 units |
| Monetary value per point per lot | ₹65 |
| Effective monthly expiry | 27 January 2026 |
| Official reference | NSE/FAOP/70616 |

The model now applies actual futures OHLC and settlement prices, historical expiry dates, and dated market lots to strategy execution. V1, V2, and V3 Step 1 remain unchanged one-unit index research; only the separate V3 Step 2 result uses futures monetary accounting.

### Historical futures data

Official NSE NIFTY futures contract history for 2020 through 2026 is stored in `data/futures/`, one CSV per calendar year. It retains individual expiries, settlement prices, volume, open interest, underlying value, and the market lot reported for each contract-day row. See `data/futures/README.md` for provenance, coverage, schema, and reproduction instructions.

The source files remain raw. The execution layer builds a front-month series by selecting the nearest unexpired contract on each session, holds it through its expiry session, settles that leg using the expiry settlement price with adverse slippage, and enters the successor at its next available open. Missing source values are not fabricated; rows without the required price fields are excluded by the typed loader, while blank market lots are resolved only from other rows for the same expiry.

### NSE historical-data API

`NseHistoricalClient` provides reusable project APIs for both official datasets:

```python
from datetime import date
from trading_agent.data.nse import NseHistoricalClient

client = NseHistoricalClient()
index_rows = client.fetch_index_history(date(2026, 1, 1), date(2026, 1, 31))
future_rows = client.fetch_futures_history(date(2026, 1, 1), date(2026, 1, 31))
```

Both methods handle NSE session cookies, 27-day chunks, retries, normalization, and duplicate removal. Network calls are never made during module import or normal backtests.

```bash
uv run python scripts/download_nse_index.py --start-year 2020 --end-year 2026
uv run python scripts/download_nse_futures.py --start-year 2020 --end-year 2026
```

Index files default to `data/index/`; futures files default to `data/futures/`. Downloaded data must pass repository integrity checks before research use.

## V3 Step 2: real futures execution

**Status:** implemented development experiment; not yet a frozen release checkpoint.

- The V2 gate and Trend-Momentum signals still use spot NIFTY data. This preserves the frozen signal policy while testing a tradable execution instrument.
- A signal formed at a spot close executes only at the next session for which a futures open is available.
- Buys pay futures open +5 points and sells receive futures open −5 points. Each point is multiplied by that contract's historical NSE market lot.
- ₹20 is charged per completed futures round trip, split equally between entry and exit. A rollover closes one contract leg and opens the next, so both orders incur their respective half-cost.
- Futures notional is not deducted from cash. Equity is cash plus variation P&L marked to the active contract's settlement price.
- The unconstrained result does not impose margin. A separate capital-constrained scenario applies a transparent 15% initial-margin and 12% maintenance-margin proxy, settles variation P&L to cash daily, rejects unaffordable entries, and schedules maintenance breaches for liquidation at the following available open. These fixed rates are research assumptions, not historical NSE SPAN evidence.

The development evaluation covers 2020-12-30 through 2025-07-04 and uses historical lots of 75, 50, and 25. Five spot sessions had no matching executable futures row and were skipped; pending actions execute at the next available futures open.

| V3 Step 2 development result | Value |
|---|---:|
| Accepted / rejected windows | 6 / 22 |
| Starting capital | ₹100,000 |
| Final equity | ₹149,260.00 |
| Futures P&L | ₹49,260.00 |
| Capital-normalized return | 49.26% |
| Strategy exits | 8 |
| Gate-forced liquidations | 1 |
| Mechanical contract rolls while invested | 3 |
| Maximum drawdown | ₹57,857.50 |
| Exposure | 7.00% |
| Missing futures sessions | 5 |
| Continuous futures benchmark P&L, unconstrained | ₹353,475.00 |

The ₹49,260 result is primarily the monetary effect of historical lot sizing on the same sparse signal exposure; it is not evidence that V3 found a stronger signal. The ₹57,857.50 drawdown—larger than the profit—also shows why margin and capital adequacy must be modeled before paper trading.

### Capital-constrained result

V3 futures capital is now ₹10,00,000. This does not alter the frozen ₹1,00,000 V1/V2 configurations. With the 15%/12% margin proxy, all eight strategy positions can be funded and no margin call occurs.

| ₹10,00,000 funded scenario | Value |
|---|---:|
| Final equity | ₹10,46,860.87 |
| Net P&L | ₹46,860.87 |
| Net return | 4.69% |
| Strategy exits / rolls | 8 / 3 |
| Rejected entries / margin calls | 0 / 0 |
| Peak required margin | ₹1,78,638.75 |
| Minimum free cash | ₹8,42,404.61 |
| Total modeled charges | ₹2,619.13 |
| Equally funded futures benchmark P&L | ₹3,41,304.78 |

Charges include ₹20 assumed retail brokerage per order, GST on brokerage plus exchange and SEBI charges, buyer-side futures stamp duty, SEBI turnover fees, and dated seller-side STT: 0.01% before 1 April 2023, 0.0125% through 30 September 2024, and 0.02% afterward. The exchange transaction rate is a configurable research assumption and must be checked against the chosen broker's contract notes.

NSE Clearing states that actual equity-derivatives initial margin is SPAN-based, collected upfront, and calculated from changing daily risk parameters. Its public data catalogue identifies historical margin and daily SPAN data, but the exact contract-level archive was not exposed as a stable bulk endpoint during this implementation. Therefore the 15%/12% schedule remains an explicit proxy rather than fabricated historical SPAN data. See the [NSE Clearing margin methodology](https://www.nseclearing.in/risk-management/equity-derivatives/margins), [SPAN methodology](https://www.nseclearing.in/risk-management/equity-derivatives/nsccl-span), [public clearing-data catalogue](https://www.nseclearing.in/data-list-nse-clearing), and [official statutory levy table](https://www.nseindia.com/static/invest/first-time-investor-sebi-turnover-fees-stt-other-levies).
