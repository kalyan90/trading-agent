# Research history and frozen checkpoints

Logs are evidence, not disposable output. Frozen logs must not be regenerated after changing parameters, data scope, execution, accounting, or evaluation rules.

```text
logs/
├── v1/  # SMA experiments, selection, slippage, benchmark, consumed holdout
├── v2/  # frozen Trend-Momentum development comparison
└── v3/  # continuous, futures, BANKNIFTY, equities, and paper checkpoints
```

## Measurement definitions

| Term | Definition |
|---|---|
| Completed trade | One executed entry and corresponding exit |
| Training P&L | Ending equity minus initial capital, including open-position MTM |
| OOS P&L | P&L from the following accepted test segment |
| Exposure | Eligible bars invested; multi-stock exposure is occupied capacity |
| Drawdown | Largest peak-to-subsequent-equity decline |
| Benchmark | Matching buy-and-hold over identical instruments and dates |
| Rejected window | Training P&L or completed-trade gate failed |
| Excess P&L | Strategy P&L minus benchmark P&L |
| ATR stop | Close threshold scheduling an exit for the next open |

## V1 frozen baseline

V1 compared SMA Basic and SMA Crossover across periods 3, 10, 20, 30, and 50. It used 120/40 chronological windows, positive P&L plus five completed trades, ₹1,00,000 reset capital, one abstract NIFTY unit, ₹20 round-trip cost, five-point slippage, and no forced liquidation.

| Final holdout metric | Result |
|---|---:|
| Accepted windows | 2 / 7 |
| OOS P&L | **−₹362.45** |
| Completed trades | 6 |
| Benchmark P&L | ₹1,633.60 |
| Excess P&L | **−₹1,996.05** |
| Benchmark beat rate | 0% |

The holdout is consumed. `v1/experiment-v1-final-holdout-logs.txt` must never be presented as unseen evidence again.

## V2 frozen Trend-Momentum

V2 fixed SMA 20/50, RSI 14, MACD 12/26/9, ATR 14, a 2× entry-ATR stop, 250/40 windows, and the positive-P&L/five-trade gate. There is no parameter search or pristine V2 holdout.

| Development metric | Result |
|---|---:|
| Accepted windows | 6 / 28 |
| OOS P&L | ₹584.60 |
| Completed trades | 7 |
| Average exposure | 32.50% |
| Benchmark P&L | ₹4,027.30 |
| Excess P&L | −₹3,442.70 |

See `v2/experiment-v2-development.txt`.

## V3 Step 1 — continuous portfolio

The frozen V2 policy was carried across adjacent accepted windows with one ₹1,00,000 account. Rejected-window starts liquidate positions at the next valid open.

| Metric | Result |
|---|---:|
| P&L / return | ₹634.55 / 0.63% |
| Completed trades | 8 |
| Maximum drawdown | ₹1,094.45 |
| Exposure | 6.96% |
| Benchmark P&L | ₹11,465.10 |

See `v3/experiment-v3-step1-continuous.txt`.

## V3 Step 2 — futures execution

Spot-derived signals execute through dated NIFTY futures contracts with historical lots, settlement, expiry rolls, adverse slippage, costs, and a separate margin proxy. Frozen at `v3.2.1-configurable-futures-fix`.

Development produced ₹49,260 unconstrained P&L on ₹1,00,000 with ₹57,857.50 drawdown. This positive result had weak reward relative to risk and benchmark. See `v3/experiment-v3-step2-futures.txt`.

## V3 Step 3 — BANKNIFTY and paper scaffold

Frozen as limited checkpoint `v3.3-banknifty-paper-scaffold`; it did not consume the BANKNIFTY holdout or establish deployability.

| Metric | Continuous spot | ₹10 lakh funded futures |
|---|---:|---:|
| P&L | ₹834.10 | ₹11,550.57 |
| Maximum drawdown | ₹3,912.25 | ₹1,05,477.51 |
| Benchmark P&L | ₹25,454.40 | ₹3,39,217.42 |

See `v3/experiment-v3-step3-banknifty.txt`.

## V3 Step 4 — active equity pilot

Implemented but not frozen. Ten current NIFTY 50 constituents use one shared ₹10 lakh account, five positions, 20% allocations, whole shares, ₹0.05 per-side slippage, and simplified ₹20 round-trip cost.

| Development metric | Result |
|---|---:|
| Accepted symbol-windows | 30 / 280 |
| P&L / return | **−₹70,833.50 / −7.08%** |
| Maximum drawdown | ₹99,412.50 |
| Trades / win rate | 34 / 23.53% |
| Benchmark P&L | **₹10,36,786.25** |
| Excess P&L | **−₹11,07,619.75** |

TCS was the only positive independent sleeve and still lagged its benchmark. The BANKNIFTY-stock subgroup lost ₹7,974.80. NIFTY Next 50 was not run because the pilot contains no member. Current membership is retrospective, and the holdout from 2025-09-01 remains untouched.

See `v3/experiment-v3-step4-equity-pilot.txt` and `v3/experiment-v3-step4-paper-validation.txt`.

## Interpretation rule

Positive development is not proof of a deployable edge. Negative development is not permission to mine parameters until it becomes positive. New strategy logic, gates, costs, membership histories, or portfolio policies require a new version and separate log.
`logs/v3/experiment-v3-step5.txt` is a frozen limited negative current-snapshot
checkpoint. It does not
replace either Step 4 log; its comparisons are survivorship-biased and its reserved
tail is untouched.

V3 Step 6 is documented in `v3/experiment-v3-step6-dynamic-calendar.txt`. It is
unfrozen development evidence and does not replace any frozen log. The cross-version
interpretation is in `V1_TO_V3_REVIEW.md`.

V4 is a new hypothesis family. `v4/experiment-v4-step1-relative-strength.txt`
is a frozen limited inconclusive fixed-parameter checkpoint; it must not be
described as promoted, retired, deployable, or a tuned continuation of V3.

`v4/experiment-v4-step2-regime-overlay.txt` records the unfrozen Step 2 development
overlay. Passing its pillars authorizes only continued staged research, not a
holdout run or deployment.
