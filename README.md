# NSE Trading Agent

A deterministic research backtester for daily NIFTY 50 market data. It contains a frozen V1 baseline and a separately frozen V2 Trend-Momentum strategy.

## Current research status

- V1 is frozen and its final holdout has already been consumed. Do not tune V1 or rerun that holdout as if it were unbiased.
- V2 is evaluated only on development walk-forward windows.
- No parameter optimization is performed for V2.
- The legacy `--final-holdout` option is retained for compatibility but refuses to rerun the consumed V1 holdout.

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

## Usage

```bash
uv run pytest -q
uv run trading-agent
```

The second command runs the development comparison and prints V2 training diagnostics. It does not consume a new holdout.

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
└── v2/
    └── experiment-v2-development.txt
```

- `logs/v1/` is the preserved V1 research trail, including the one-time consumed holdout output. These files are historical records and must not be regenerated to claim new evidence.
- `logs/v2/experiment-v2-development.txt` is the reproducible development comparison generated from the completed V2 implementation. It contains V1 development metrics for comparison, V2 metrics, train-gate diagnostics, and ATR-stop activation counts.
- V2 currently has no pristine final-holdout log. Creating one would require genuinely untouched future data or a separately reserved dataset.

To refresh the V2 development record after a reproducibility-only run:

```bash
uv run trading-agent | tee logs/v2/experiment-v2-development.txt
```

Do not use that command after changing frozen V2. A material strategy or evaluation change belongs to a new version and a new log file.

## Version conclusions

- **V1:** completed and frozen after failing its consumed final holdout. It remains the historical baseline.
- **V2:** completed and frozen as a deterministic Trend-Momentum strategy with an ATR risk exit. Its reported results are development evidence, not pristine holdout evidence.
- A future V3 may introduce regime classification, realistic tradable contract sizing, continuous portfolio evaluation, paper trading, or an AI decision layer. Those changes must remain separate from frozen V1 and V2.
