# Trading Strategy Guide for Beginners

## First: what this project is

This project is a research and paper-trading system for India’s National Stock
Exchange (NSE). It asks a simple question: can a fixed, explainable set of rules
select a small group of relatively strong stocks while avoiding some major market
declines?

It is not a promise of profit, investment advice, or a live trading bot. The latest
strategy is still waiting for forward paper evidence.

## A few basic ideas

A **stock** is a small ownership share in a company. An **index**, such as NIFTY 50,
is a calculated basket representing a part of the market. V4 buys company shares;
it does not buy NIFTY, futures, or options.

A **signal** is a rule-based instruction such as “this stock qualifies for the
portfolio.” A **position** is a stock currently held. **Return** is the percentage
gain or loss. **Drawdown** is the fall from the portfolio’s earlier highest value.
A **benchmark** is the simple alternative against which the strategy is compared.

## The current V4 strategy in one paragraph

At each month-end, V4 considers current constituents of NIFTY 50, NIFTY Next 50,
and NIFTY Bank. It ranks stocks by their positive 12−1 relative strength: roughly
the return over the preceding year while ignoring the most recent month. It may
hold up to ten highest-ranked affordable stocks. It invests only when the NIFTY 50
month-end close is strictly above its trailing 200-session simple moving average.
Signals use the closing data, and orders wait until each stock’s next available
market open. The default paper account starts with ₹1,00,000.

## The monthly decision, step by step

### 1. Establish the eligible universe

The system uses a constituent snapshot that was known on or before the decision
date. This “point-in-time” rule prevents a future index membership list from being
pretended to have existed in the past.

The three index groups overlap, so duplicate symbols are removed. A stock also
needs adequate price history and median trading volume before it can be ranked.

### 2. Measure 12−1 relative strength

For every eligible stock, the system compares:

- the closing price about 252 trading sessions ago; and
- the closing price about 21 trading sessions ago.

Conceptually:

```text
relative strength = price 21 sessions ago / price 252 sessions ago − 1
```

The latest 21 sessions are skipped. This reduces dependence on very recent moves
that may quickly reverse. Only positive scores qualify. Higher positive scores rank
first; the stock symbol breaks an exact tie deterministically.

This is relative strength in the price-momentum sense. It is not the RSI technical
indicator used by the older V2/V3 Trend-Momentum strategy.

### 3. Check the market regime

The system calculates the average of exactly 200 NIFTY 50 closing observations,
including the month-end close.

```text
NIFTY close > 200-session average  → risk-on
NIFTY close ≤ 200-session average  → risk-off
```

Missing month-end data or fewer than 200 observations means risk-off. Nothing is
filled forward from a later date.

During risk-on, the ranked stocks may be held. During risk-off, the target is cash,
and existing positions are scheduled for sale at their later available opens.

### 4. Convert rankings into whole-share targets

With default capital of ₹1,00,000 and at most ten positions, each position has a
fixed ₹10,000 target. The system buys whole shares only.

If a stock costs more than its target after estimated charges, it is skipped and
the next ranked stock is considered. Unused money remains as cash. There is no
borrowing, leverage, fractional share, or forced investment.

For example, if a share’s adverse estimated price is ₹2,400, a ₹10,000 target can
hold at most four shares before fees. If the top-ranked share costs ₹12,000, it is
unaffordable for that slot, so ranking continues to the next candidate.

### 5. Trade no earlier than the next open

The month-end close creates the signal, but that same closing price cannot be used
as an execution price. Each order waits for that stock’s first available open on a
later session. Missing or suspended stocks are deferred independently.

Sales and reductions occur before purchases and increases. The model applies
adverse ₹0.05 slippage and the declared cash-equity fee schedule. This protects the
backtest from assuming free or impossibly well-timed execution.

### 6. Preserve evidence

Every monthly decision has explicit signal and evidence dates. The local paper
coordinator preserves plans, orders, skips, fees, cash, and positions. Operational
reports checksum and archive inputs, state, journal records, and results.

## What V1, V2, V3, and V4 mean

- **V1** tested a simpler moving-average strategy and failed its one-time holdout.
- **V2** added Trend-Momentum indicators: SMA, RSI, MACD, and ATR.
- **V3** tested that policy across realistic futures and stock portfolios. Its
  unchanged strategy ultimately failed the declared benchmark/drawdown rules.
- **V4** starts a different hypothesis: monthly cross-sectional relative strength
  with a NIFTY 50 regime filter. It does not tune the retired V3 strategy.

Negative results are retained. A later version does not rewrite what an earlier
version actually achieved.

## What the historical V4 evidence says

V4 Step 1 produced encouraging development returns, but its long-history drawdown
was 36.21%, above the declared 20% ceiling. Step 2 added one predeclared NIFTY 50
200-session-average filter and reduced development drawdown to 19.76%, passing all
five development promotion pillars.

“Promoted” means worthy of forward paper observation. It does not mean profitable
in the future, safe to deploy, or approved for real-money trading.

## How forward success will be judged

The frozen policy must complete at least 12 prospective months. The gate requires:

- positive paper return after modeled costs;
- maximum drawdown no greater than 20%;
- a declared comparison with NIFTY 50;
- no duplicate-decision or reconciliation failures; and
- no strategy-parameter change during observation.

Even passing these conditions would justify another controlled review—not an
automatic transition to live trading.

## Important risks and limitations

- Historical membership is incomplete, so older development comparisons include
  survivorship limitations.
- Corporate actions and dividends can affect real economic returns.
- Paper opening prices and modeled slippage may differ from actual fills.
- ₹1,00,000 limits diversification when shares are expensive.
- Momentum strategies can reverse sharply or remain in cash during recoveries.
- One year provides limited statistical evidence.
- Taxes, broker-specific charges, outages, and human operational errors still
  matter.

The safest mental model is: V4 is a fixed hypothesis being measured, not a machine
that has discovered a dependable source of income.
