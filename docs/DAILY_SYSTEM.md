# Daily Decision and Paper-Trading System

## What “daily” means

The system runs once for every declared trading session. It evaluates the newest
validated information and records an outcome for each relevant stock. It does not
force a trade.

The five possible outcomes are:

| Outcome | Meaning |
|---|---|
| BUY | All trade satisfiers passed and the desired quantity is higher |
| SELL | All trade satisfiers passed and the desired quantity is lower |
| HOLD | All satisfiers passed and the current quantity is already correct |
| DEFER | Required evidence or a target for an open position is missing |
| BLOCK | A satisfier, kill switch, or reconciliation control failed |

HOLD, DEFER, and BLOCK are preserved in the journal. This makes “the system chose
not to trade” distinguishable from “the system never ran.”

## V5 Step 1 boundary

Step 1 is a strategy-neutral control plane. A later, separately frozen V5 policy
will calculate target quantities and named satisfiers. Step 1 validates those
intents, creates decisions, queues necessary quantity changes, paper-fills them at
later opens, and measures results.

It does not yet decide which market indicators constitute a good entry or exit.
That belongs to V5 Step 2 and must be declared before evaluation.

## Daily lifecycle

```text
validated close and strategy target
              ↓
    check every named satisfier
              ↓
 BUY / SELL / HOLD / DEFER / BLOCK
              ↓
  necessary order waits for later open
              ↓
 fees + adverse slippage + paper fill
              ↓
 exact-date closing marks and NIFTY close
              ↓
 equity, return, drawdown and excess return
```

Orders are deterministic and restart-safe. Sales execute before purchases. A
missing opening price defers only that order. The kill switch or a position mismatch
blocks execution. Oversized buys are rejected, while risk limits never prevent an
existing appreciated position from being reduced.

## What a satisfier is

A satisfier is a named Boolean precondition supplied with the daily target. Future
V5 examples might include:

- market data is complete and fresh;
- point-in-time membership is known;
- the market regime permits exposure;
- the stock satisfies the fixed strategy signal;
- portfolio and per-order risk limits permit the change; and
- expected and paper positions reconcile.

Every declared satisfier must be true before Step 1 emits BUY or SELL. An incomplete
record becomes DEFER. A known failed satisfier becomes BLOCK. The exact V5 Step 2
list will be versioned rather than invented differently each day.

## Daily evaluation

After execution, exact-date closes mark every open position. The system records:

- cash and market value;
- total equity and net return after fees;
- equity high, current drawdown, and maximum drawdown;
- positions and accumulated modeled fees;
- NIFTY 50 price return from the daily system’s inception; and
- return in excess of that benchmark.

These are paper figures, not real fills or proof of profitability.

## Relationship with V4

V4 continues unchanged as the monthly relative-strength baseline. V5 runs in a
separate state and journal. Comparing them helps answer whether daily flexibility
adds value after its additional turnover and costs.

An LLM may explain daily records but cannot create targets, change satisfiers, or
approve a blocked trade in the deterministic V5 control plane.
